# -*- coding: utf-8 -*-
"""Twelve Labs HTTP helpers. Standard library only. Never log or print the API key."""

from __future__ import annotations

import json
import os
import re
import ssl
import time
import uuid
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlsplit
import urllib.request
import http.client

API_BASE = "https://api.twelvelabs.io/v1.3"
API_HOST = "api.twelvelabs.io"
API_PREFIX = "/v1.3"

# Stop immediately on these (quota / billing / upgrade). Do not retry-spam.
QUOTA_CODES = {
    "usage_limit_exceeded",
    "workload_allowance_exhausted",
    "asset_limit_exceeded",
    "storage_limit_exceeded",
    "managed_intelligence_allowance_exhausted",
    "allowance_exhausted",
    "4302",
}
QUOTA_MESSAGE_RE = re.compile(
    r"(usage[_\s-]?limit|quota|allowance|overage|upgrade|payment required|"
    r"insufficient (?:quota|credit|storage)|storage (?:limit|exceed)|"
    r"free plan|please upgrade|billing|额度|超限|升级|付费)",
    re.I,
)

SENSITIVE_HEADER_RE = re.compile(
    r"(?i)(x-api-key|authorization|api[-_]?key|token|secret)\s*[:=]\s*.+"
)



def _safe_proxy_label(url: str) -> str:
    p = urlsplit(url)
    host = p.hostname or "?"
    port = f":{p.port}" if p.port else ""
    auth = "（有认证信息，已隐藏）" if (p.username or p.password) else ""
    return f"{p.scheme or 'http'}://{host}{port}{auth}"


def get_https_proxy() -> str | None:
    """Use environment or OS proxy settings. Never return or log credentials to callers unnecessarily."""
    proxies = {}
    try:
        proxies = urllib.request.getproxies() or {}
    except Exception:
        proxies = {}
    url = proxies.get("https") or proxies.get("http")
    if not url:
        for name in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
            val = os.environ.get(name)
            if val:
                url = val
                break
    return url or None


class QuotaError(RuntimeError):
    def __init__(self, status: int, code: str | None, message: str, body: Any = None):
        self.status = status
        self.code = code
        self.user_message = message
        self.body = body
        super().__init__(f"额度不足或需要付费: status={status} code={code} message={message}")


class ApiError(RuntimeError):
    def __init__(self, status: int, code: str | None, message: str, body: Any = None, retry_after: float | None = None):
        self.status = status
        self.code = code
        self.user_message = message
        self.body = body
        self.retry_after = retry_after
        super().__init__(f"API错误: status={status} code={code} message={message}")


def get_api_key() -> str:
    key = os.environ.get("TWELVELABS_API_KEY")
    if key and key.strip():
        return key.strip()
    raise SystemExit("TWELVELABS_API_KEY: 还没有读到")


def key_status_label() -> str:
    key = os.environ.get("TWELVELABS_API_KEY")
    return "已设置" if (key and key.strip()) else "还没有读到"


def redact_text(text: str, key: str | None = None) -> str:
    if not text:
        return text
    out = SENSITIVE_HEADER_RE.sub(r"\1: ***", text)
    k = key or os.environ.get("TWELVELABS_API_KEY") or ""
    if k and k in out:
        out = out.replace(k, "***")
    # common bearer / raw key fragments if server echoes them
    out = re.sub(r"(?i)(tlk_|tl_[A-Za-z0-9]|sk-)[A-Za-z0-9._\-]{8,}", "***", out)
    return out


def redact_obj(obj: Any, key: str | None = None) -> Any:
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if re.search(r"(?i)(api[-_]?key|authorization|token|secret|password)", str(k)):
                out[k] = "***"
            else:
                out[k] = redact_obj(v, key)
        return out
    if isinstance(obj, list):
        return [redact_obj(x, key) for x in obj]
    if isinstance(obj, str):
        return redact_text(obj, key)
    return obj


def _parse_retry_after(headers: dict[str, str]) -> float | None:
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return max(0.0, float(raw))
    except ValueError:
        return None


def _interesting_headers(headers: dict[str, str]) -> dict[str, str]:
    keep = {}
    for k, v in headers.items():
        lk = k.lower()
        if lk.startswith("x-ratelimit") or lk in {
            "retry-after",
            "x-request-id",
            "x-ratelimit-dimensions",
            "content-type",
        }:
            keep[k] = v
    return keep


def _decode_body(raw: bytes, content_type: str | None) -> Any:
    if not raw:
        return None
    text = raw.decode("utf-8", errors="replace")
    ctype = (content_type or "").lower()
    if "json" in ctype or text[:1] in "{[":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def _extract_error(status: int, body: Any) -> tuple[str | None, str]:
    code = None
    message = ""
    if isinstance(body, dict):
        code = body.get("code") or body.get("error_code") or body.get("error")
        if isinstance(code, dict):
            code = code.get("code") or code.get("name")
        if code is not None:
            code = str(code)
        message = (
            body.get("message")
            or body.get("msg")
            or (body.get("error") if isinstance(body.get("error"), str) else None)
            or ""
        )
        if not message:
            message = json.dumps(redact_obj(body), ensure_ascii=False)
    elif body is not None:
        message = str(body)
    message = redact_text(str(message))
    return code, message or f"HTTP {status}"


def is_quota_error(status: int, code: str | None, message: str) -> bool:
    if code and str(code) in QUOTA_CODES:
        return True
    if status in (402, 4302):
        return True
    # 422 with quota-like code/message; 403/409 sometimes used for plan limits
    blob = f"{code or ''} {message or ''}"
    if "4302" in blob:
        return True
    if status in (402, 422, 403, 409) and QUOTA_MESSAGE_RE.search(blob):
        return True
    if status == 429 and QUOTA_MESSAGE_RE.search(blob) and not re.search(r"(?i)rate limit|too many requests", blob):
        return True
    if QUOTA_MESSAGE_RE.search(blob) and re.search(
        r"(?i)exceed|exhausted|reached|upgrade|付费|超限|不够|不足", blob
    ):
        return True
    return False


class TwelveClient:
    def __init__(self, timeout: float = 120.0, upload_timeout: float = 1800.0):
        self.timeout = timeout
        self.upload_timeout = upload_timeout
        self._key = get_api_key()
        self._ctx = ssl.create_default_context()
        self._proxy = get_https_proxy()
        self._proxy_label = _safe_proxy_label(self._proxy) if self._proxy else None

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {"x-api-key": self._key, "Accept": "application/json"}
        if extra:
            h.update(extra)
        return h

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        raw_body: bytes | None = None,
        content_type: str | None = None,
        extra_headers: dict[str, str] | None = None,
        timeout: float | None = None,
        expected: tuple[int, ...] = (200, 201, 202),
    ) -> tuple[int, Any, dict[str, str]]:
        if not path.startswith("/"):
            path = "/" + path
        url_path = path if path.startswith("/v1.") else API_PREFIX + path
        headers = self._headers(extra_headers)
        body = raw_body
        if json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif content_type:
            headers["Content-Type"] = content_type
        to = timeout if timeout is not None else self.timeout
        if hasattr(body, "seek"):
            try:
                body.seek(0)
            except OSError:
                pass
        if self._proxy:
            pu = urlsplit(self._proxy)
            phost = pu.hostname
            pport = pu.port or (443 if pu.scheme == "https" else 80)
            if not phost:
                raise ApiError(0, None, "代理地址无法解析")
            conn = http.client.HTTPSConnection(phost, pport, timeout=to, context=self._ctx)
            tunnel_headers = {}
            if pu.username is not None:
                import base64
                token = base64.b64encode(f"{pu.username}:{pu.password or ''}".encode()).decode("ascii")
                tunnel_headers["Proxy-Authorization"] = "Basic " + token
            conn.set_tunnel(API_HOST, 443, headers=tunnel_headers or None)
        else:
            conn = http.client.HTTPSConnection(API_HOST, timeout=to, context=self._ctx)
        try:
            conn.connect()
            conn.putrequest(method, url_path)
            send_body = body
            if send_body is not None and not any(k.lower() == "content-length" for k in headers):
                if hasattr(send_body, "__len__"):
                    headers["Content-Length"] = str(len(send_body))
            for hk, hv in headers.items():
                conn.putheader(hk, hv)
            conn.endheaders()
            if send_body is not None:
                if hasattr(send_body, "read"):
                    while True:
                        chunk = send_body.read(1024 * 1024)
                        if not chunk:
                            break
                        conn.send(chunk)
                    if hasattr(send_body, "close"):
                        try:
                            send_body.close()
                        except OSError:
                            pass
                else:
                    conn.send(send_body)
            resp = conn.getresponse()
            raw = resp.read()
            hdrs = {k: v for k, v in resp.getheaders()}
            parsed = _decode_body(raw, hdrs.get("Content-Type"))
            status = resp.status
        finally:
            conn.close()

        if status not in expected:
            code, message = _extract_error(status, parsed)
            message = redact_text(message, self._key)
            retry_after = _parse_retry_after(hdrs)
            if is_quota_error(status, code, message):
                raise QuotaError(status, code, message, redact_obj(parsed, self._key))
            raise ApiError(status, code, message, redact_obj(parsed, self._key), retry_after)
        return status, parsed, hdrs

    def request_with_retries(
        self,
        method: str,
        path: str,
        *,
        retries: int = 3,
        **kwargs,
    ) -> tuple[int, Any, dict[str, str]]:
        last: Exception | None = None
        for attempt in range(retries + 1):
            try:
                return self.request(method, path, **kwargs)
            except QuotaError:
                raise
            except ApiError as e:
                last = e
                if e.status == 429 and not is_quota_error(e.status, e.code, e.user_message):
                    wait = e.retry_after if e.retry_after is not None else min(60, 2 ** attempt * 5)
                    time.sleep(wait)
                    continue
                if e.status >= 500 and attempt < retries:
                    time.sleep(min(60, 2 ** attempt * 3))
                    continue
                raise
            except (http.client.HTTPException, OSError, TimeoutError) as e:
                last = e
                if attempt < retries:
                    time.sleep(min(60, 2 ** attempt * 3))
                    continue
                raise ApiError(0, None, redact_text(f"网络或连接错误: {e}", self._key))
        raise last or RuntimeError("request failed")

    def get(self, path: str, **kwargs) -> tuple[int, Any, dict[str, str]]:
        return self.request_with_retries("GET", path, **kwargs)

    def post_json(self, path: str, payload: Any, **kwargs) -> tuple[int, Any, dict[str, str]]:
        return self.request_with_retries("POST", path, json_body=payload, **kwargs)

    def delete(self, path: str, **kwargs) -> tuple[int, Any, dict[str, str]]:
        expected = kwargs.pop("expected", (200, 201, 202, 204))
        return self.request_with_retries("DELETE", path, expected=expected, **kwargs)

    def upload_asset_direct(
        self,
        file_path: Path,
        *,
        filename: str | None = None,
        enable_hls: bool = False,
        enable_thumbnail: bool = False,
    ) -> tuple[int, Any, dict[str, str]]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(str(path))
        name = filename or path.name
        boundary = "----T12Boundary" + uuid.uuid4().hex
        preamble_fields = [
            ("method", "direct"),
            ("filename", name),
            ("enable_hls", "false" if not enable_hls else "true"),
            ("enable_thumbnail", "false" if not enable_thumbnail else "true"),
        ]
        header_parts = []
        for k, v in preamble_fields:
            header_parts.append(
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{k}"\r\n\r\n'
                f"{v}\r\n"
            )
        file_head = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{name}"\r\n'
            f"Content-Type: video/mp4\r\n\r\n"
        )
        header_bytes = ("".join(header_parts) + file_head).encode("utf-8")
        footer_bytes = f"\r\n--{boundary}--\r\n".encode("utf-8")
        file_size = path.stat().st_size
        total_len = len(header_bytes) + file_size + len(footer_bytes)
        body = _MultipartFileBody(header_bytes, path, footer_bytes, total_len)
        return self.request_with_retries(
            "POST",
            "/assets",
            raw_body=body,  # type: ignore[arg-type]
            content_type=f"multipart/form-data; boundary={boundary}",
            timeout=self.upload_timeout,
            expected=(200, 201, 202),
        )

    def search(
        self,
        index_id: str,
        query_text: str,
        *,
        search_options: list[str] | None = None,
        page_limit: int = 10,
        group_by: str = "clip",
        operator: str = "or",
    ) -> tuple[int, Any, dict[str, str]]:
        options = search_options or ["visual", "audio"]
        boundary = "----T12Search" + uuid.uuid4().hex
        fields: list[tuple[str, str]] = [
            ("query_text", query_text),
            ("index_id", index_id),
            ("page_limit", str(page_limit)),
            ("group_by", group_by),
            ("operator", operator),
        ]
        chunks = []
        for k, v in fields:
            chunks.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n"
            )
        for opt in options:
            chunks.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"search_options\"\r\n\r\n{opt}\r\n"
            )
        chunks.append(f"--{boundary}--\r\n")
        body = "".join(chunks).encode("utf-8")
        return self.request_with_retries(
            "POST",
            "/search",
            raw_body=body,
            content_type=f"multipart/form-data; boundary={boundary}",
            timeout=self.timeout,
            expected=(200, 201),
        )


class _MultipartFileBody:
    """File-like multipart body that streams the video from disk."""

    def __init__(self, header: bytes, path: Path, footer: bytes, length: int):
        self._header = header
        self._path = path
        self._footer = footer
        self._length = length
        self._fp = None
        self._pos = 0
        self._file_size = path.stat().st_size

    def __len__(self) -> int:
        return self._length

    def _ensure_open(self):
        if self._fp is None:
            self._fp = open(self._path, "rb")
            file_off = self._pos - len(self._header)
            if 0 < file_off < self._file_size:
                self._fp.seek(file_off)

    def seek(self, pos, whence=0):
        if whence != 0 or pos != 0:
            raise OSError("only seek(0) is supported")
        self.close()
        self._pos = 0
        return 0

    def close(self):
        if self._fp is not None:
            self._fp.close()
            self._fp = None

    def read(self, n: int = -1) -> bytes:
        if n == 0:
            return b""
        self._ensure_open()
        remaining_total = self._length - self._pos
        if remaining_total <= 0:
            return b""
        if n is None or n < 0:
            n = remaining_total
        n = min(n, remaining_total)
        chunks = []
        left = n
        # header
        if self._pos < len(self._header) and left:
            take = min(left, len(self._header) - self._pos)
            chunks.append(self._header[self._pos : self._pos + take])
            self._pos += take
            left -= take
        # file
        file_start = len(self._header)
        file_end = file_start + self._file_size
        if file_start <= self._pos < file_end and left:
            take = min(left, file_end - self._pos)
            data = self._fp.read(take) if self._fp else b""
            if len(data) < take:
                # shouldn't happen
                pass
            chunks.append(data)
            self._pos += len(data)
            left -= len(data)
        # footer
        if self._pos >= file_end and left:
            footer_off = self._pos - file_end
            take = min(left, len(self._footer) - footer_off)
            chunks.append(self._footer[footer_off : footer_off + take])
            self._pos += take
            left -= take
        return b"".join(chunks)


def safe_id(obj: Any, *keys: str) -> str | None:
    if not isinstance(obj, dict):
        return None
    for k in keys:
        v = obj.get(k)
        if v:
            return str(v)
    return None


def poll_until(
    fn,
    *,
    is_done,
    is_failed,
    interval: float = 5.0,
    max_interval: float = 30.0,
    timeout: float = 3600.0,
    label: str = "",
):
    start = time.time()
    wait = interval
    last = None
    while True:
        last = fn()
        if is_done(last):
            return last
        if is_failed(last):
            return last
        if time.time() - start > timeout:
            raise TimeoutError(redact_text(f"轮询超时{('：' + label) if label else ''}"))
        time.sleep(wait)
        wait = min(max_interval, wait * 1.3)
