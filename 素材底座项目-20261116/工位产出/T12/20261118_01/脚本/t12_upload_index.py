# -*- coding: utf-8 -*-
"""上传副本与短片合成件到 Twelve Labs，建立 Marengo 3.0 索引。可断点续传。只用免费档。"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
import traceback
from datetime import datetime, timedelta, timezone
from pathlib import Path

# same folder import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from t12_api import (  # noqa: E402
    ApiError,
    QuotaError,
    TwelveClient,
    _interesting_headers,
    key_status_label,
    poll_until,
    redact_obj,
    redact_text,
    safe_id,
)

SHANGHAI = timezone(timedelta(hours=8))  # Asia/Shanghai, no tzdata needed
BATCH = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T12\20261118_01")
COPIES = BATCH / "副本"
CONCAT_DIR = BATCH / "短片合成_重编码"
STATS = BATCH / "统计"
UPLOAD_CSV = BATCH / "上传清单.csv"
MAP_CSV = BATCH / "编号对应表.csv"
CONCAT_LIST = BATCH / "拼接清单_重编码.csv"
INDEX_NAME = "t12-20261118-01"
LOG_JSONL = STATS / "上传进度.jsonl"
STATE_JSON = STATS / "上传状态.json"
INDEX_JSON = STATS / "索引信息.json"
CONSOLE_LOG = STATS / "上传控制台.log"
LOCK_FILE = STATS / "上传进程.lock"
MAX_DIRECT_BYTES = 200 * 1024 * 1024
DIRECT_WAIT = 4.0  # seconds courtesy after each file

USAGE_PROBE_PATHS = (
    "/usage",
    "/billing",
    "/billing/usage",
    "/account",
)


def now_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def log_console(msg: str) -> None:
    line = f"{now_str()} {redact_text(msg)}"
    print(line, flush=True)
    STATS.mkdir(parents=True, exist_ok=True)
    with CONSOLE_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": now_iso(), **obj}
    rec = redact_obj(rec)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(redact_obj(obj), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def find_col(row: dict, candidates: list[str]) -> str | None:
    for c in candidates:
        if c in row:
            return c
    lower = {k.lower(): k for k in row}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock() -> None:
    STATS.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            old = int(data.get("pid") or 0)
        except Exception:
            old = 0
        if old and pid_running(old) and old != os.getpid():
            log_console(f"已有上传进程在跑 pid={old}，本进程退出，不另开第二个。")
            raise SystemExit(3)
    write_json(LOCK_FILE, {"pid": os.getpid(), "started": now_str()})


def release_lock() -> None:
    try:
        if LOCK_FILE.exists():
            data = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            if int(data.get("pid") or 0) == os.getpid():
                LOCK_FILE.unlink()
    except Exception:
        pass


def load_progress() -> dict[str, dict]:
    last: dict[str, dict] = {}
    if not LOG_JSONL.exists():
        return last
    with LOG_JSONL.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = rec.get("local_name")
            if name:
                last[name] = rec
    return last


def build_upload_items() -> list[dict]:
    uploads = load_csv(UPLOAD_CSV)
    mapping = load_csv(MAP_CSV)
    if not uploads or not mapping:
        raise SystemExit("上传清单或编号对应表为空")
    m0 = mapping[0]
    path_col = find_col(m0, ["主库相对路径", "共享相对路径", "原路径", "相对路径"])
    name_col = find_col(m0, ["副本文件名", "编号文件名", "文件名", "副本", "t12文件名"])
    id_col = find_col(m0, ["原片ID", "原片id"])
    if not path_col or not name_col:
        raise SystemExit(f"编号对应表列名无法识别: {list(m0.keys())}")
    by_path = {}
    by_id = {}
    for row in mapping:
        rel = (row.get(path_col) or "").replace("/", "\\")
        if rel:
            by_path[rel.lower()] = row
        oid = (row.get(id_col) or "") if id_col else ""
        if oid:
            by_id[oid] = row

    items = []
    seen = set()
    for row in uploads:
        flag = (row.get("是否短于4秒") or "").strip()
        is_short = flag in {"是", "Y", "y", "1", "true", "True"}
        if is_short:
            continue
        rel = (row.get("主库相对路径") or "").replace("/", "\\")
        oid = row.get("原片ID") or ""
        m = by_path.get(rel.lower()) or (by_id.get(oid) if oid else None)
        if not m:
            raise SystemExit(f"编号对应表找不到: {rel} / {oid}")
        name = m[name_col]
        if not name.lower().endswith(".mp4"):
            name = name + ".mp4"
        if name in seen:
            continue
        path = COPIES / name
        if not path.is_file():
            raise SystemExit(f"副本不存在: {path}")
        seen.add(name)
        items.append({
            "local_name": name,
            "local_path": str(path),
            "kind": "copy",
            "原片ID": oid,
            "清单时长秒": row.get("时长秒") or row.get("时长") or "",
        })

    if not CONCAT_LIST.is_file():
        raise SystemExit(f"找不到拼接清单，请先跑 t12_concat_shorts.py: {CONCAT_LIST}")
    concat_rows = load_csv(CONCAT_LIST)
    concat_files: dict[str, dict] = {}
    for row in concat_rows:
        fname = row.get("合成文件名") or ""
        if not fname or fname in concat_files:
            continue
        try:
            dur = float(row.get("合成后时长秒") or 0)
        except ValueError:
            dur = 0.0
        cpath = Path(row.get("合成路径") or (CONCAT_DIR / fname))
        concat_files[fname] = {"dur": dur, "path": cpath, "row": row}
    for fname, info in concat_files.items():
        if info["dur"] + 1e-6 < 4.0:
            log_console(f"合成件仍短于4秒，跳过不传: {fname} ({info['dur']}秒)")
            continue
        if not info["path"].is_file():
            raise SystemExit(f"合成件不存在: {info['path']}")
        if fname in seen:
            continue
        seen.add(fname)
        items.append({
            "local_name": fname,
            "local_path": str(info["path"]),
            "kind": "concat",
            "原片ID": "",
            "清单时长秒": info["dur"],
        })
    return items


def validate_items(items: list[dict]) -> None:
    too_big = []
    missing = []
    for it in items:
        p = Path(it["local_path"])
        if not p.is_file():
            missing.append(it["local_name"])
            continue
        size = p.stat().st_size
        it["size_bytes"] = size
        if size > MAX_DIRECT_BYTES:
            too_big.append((it["local_name"], size))
    if missing:
        raise SystemExit("文件缺失: " + ", ".join(missing[:20]))
    if too_big:
        raise SystemExit(
            "有文件超过本地直接上传 200 MB 上限，本脚本只用 direct 上传，已停止: "
            + ", ".join(f"{n}({s}字节)" for n, s in too_big)
        )


def snapshot_state(items: list[dict], last: dict[str, dict], extra: dict) -> None:
    counts: dict[str, int] = {}
    for it in items:
        st = (last.get(it["local_name"]) or {}).get("status") or "pending"
        counts[st] = counts.get(st, 0) + 1
    write_json(STATE_JSON, {
        "更新时间": now_str(),
        "总待传": len(items),
        "状态计数": counts,
        **extra,
    })


def probe_usage(client: TwelveClient) -> dict:
    found = {}
    for path in USAGE_PROBE_PATHS:
        try:
            status, body, hdrs = client.get(path, expected=(200, 201))
            found[path] = {
                "http_status": status,
                "headers": _interesting_headers(hdrs),
                "body": redact_obj(body),
            }
            log_console(f"用量接口 {path}: HTTP {status}（已记下数字，未写密钥）")
        except QuotaError:
            raise
        except ApiError as e:
            found[path] = {"http_status": e.status, "error": redact_text(e.user_message), "note": "无法读取，不猜测额度"}
            log_console(f"用量接口 {path}: HTTP {e.status}，查不到，不猜测额度")
        except Exception as e:
            found[path] = {"error": redact_text(str(e)), "note": "无法读取，不猜测额度"}
            log_console(f"用量接口 {path}: 失败，查不到，不猜测额度")
    return found


def list_indexes(client: TwelveClient) -> list[dict]:
    items: list[dict] = []
    page = 1
    while page <= 20:
        path = f"/indexes?page={page}&page_limit=50"
        try:
            status, body, _ = client.get(path)
        except ApiError as e:
            if page == 1:
                log_console(f"列出索引失败: HTTP {e.status} {e.user_message}")
            break
        rows = []
        if isinstance(body, list):
            rows = body
        elif isinstance(body, dict):
            rows = body.get("data") or body.get("indexes") or body.get("items") or []
        if not rows:
            break
        items.extend([r for r in rows if isinstance(r, dict)])
        if len(rows) < 50:
            break
        page += 1
    return items


def ensure_index(client: TwelveClient) -> dict:
    if INDEX_JSON.exists():
        try:
            meta = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
            idx = meta.get("index_id")
            if idx:
                try:
                    _, body, _ = client.get(f"/indexes/{idx}")
                    log_console(f"沿用已记录索引 index_id={idx} name={INDEX_NAME}")
                    meta["retrieve"] = redact_obj(body) if isinstance(body, dict) else None
                    meta["沿用"] = True
                    write_json(INDEX_JSON, meta)
                    return meta
                except ApiError as e:
                    log_console(f"已记录 index_id 读取失败 HTTP {e.status}，将按名称查找或新建")
        except Exception:
            pass

    existing = list_indexes(client)
    for row in existing:
        name = row.get("index_name") or row.get("name") or row.get("indexName")
        idx = safe_id(row, "_id", "id", "index_id")
        if name == INDEX_NAME and idx:
            meta = {
                "index_id": idx,
                "index_name": INDEX_NAME,
                "创建时间": now_str(),
                "沿用已有同名索引": True,
                "raw": redact_obj(row),
            }
            write_json(INDEX_JSON, meta)
            log_console(f"沿用已有同名索引 index_id={idx}")
            return meta

    payload = {
        "index_name": INDEX_NAME,
        "models": [{"model_name": "marengo3.0", "model_options": ["visual", "audio"]}],
    }
    status, body, hdrs = client.post_json("/indexes", payload, expected=(200, 201, 202))
    idx = safe_id(body if isinstance(body, dict) else {}, "_id", "id", "index_id")
    if not idx:
        raise RuntimeError("创建索引成功但响应里没有 id")
    meta = {
        "index_id": idx,
        "index_name": INDEX_NAME,
        "创建时间": now_str(),
        "http_status": status,
        "headers": _interesting_headers(hdrs),
        "raw": redact_obj(body) if isinstance(body, dict) else None,
        "models": payload["models"],
        "addons": "无",
    }
    write_json(INDEX_JSON, meta)
    log_console(f"已创建索引 index_id={idx} name={INDEX_NAME}")
    return meta


def wait_asset_ready(client: TwelveClient, asset_id: str) -> dict:
    def fn():
        _, body, _ = client.get(f"/assets/{asset_id}")
        return body if isinstance(body, dict) else {"status": "unknown", "raw": body}

    body = poll_until(
        fn,
        is_done=lambda b: str(b.get("status") or "").lower() == "ready",
        is_failed=lambda b: str(b.get("status") or "").lower() in {"failed", "error", "rejected"},
        interval=5.0,
        max_interval=20.0,
        timeout=30 * 60,
        label=f"asset {asset_id}",
    )
    return body


def wait_indexed_ready(client: TwelveClient, index_id: str, indexed_id: str) -> dict:
    def fn():
        _, body, _ = client.get(f"/indexes/{index_id}/indexed-assets/{indexed_id}")
        return body if isinstance(body, dict) else {"status": "unknown", "raw": body}

    body = poll_until(
        fn,
        is_done=lambda b: str(b.get("status") or "").lower() in {"ready", "complete", "completed"},
        is_failed=lambda b: str(b.get("status") or "").lower() in {"failed", "error", "rejected"},
        interval=15.0,
        max_interval=60.0,
        timeout=3 * 60 * 60,
        label=f"indexed {indexed_id}",
    )
    return body


def submit_index(client: TwelveClient, index_id: str, asset_id: str, local_name: str, kind: str) -> dict:
    payload = {
        "asset_id": asset_id,
        "enable_video_stream": False,
        "user_metadata": {"local_name": local_name, "kind": kind, "batch": "20261118_01"},
    }
    _, body, _ = client.post_json(f"/indexes/{index_id}/indexed-assets", payload, expected=(200, 201, 202))
    if not isinstance(body, dict):
        raise ApiError(0, None, "索引提交响应不是 JSON 对象")
    return body


DONE_UPLOAD_STATUSES = {"index_submitted", "index_ready", "index_failed_final"}
TERMINAL_FAIL = {"asset_failed_final", "index_failed_final", "skipped"}


def process_item(client: TwelveClient, index_id: str, item: dict, prev: dict | None) -> dict:
    name = item["local_name"]
    path = Path(item["local_path"])
    kind = item["kind"]
    size = item.get("size_bytes") or path.stat().st_size
    attempt = int((prev or {}).get("attempt") or 0)
    status = (prev or {}).get("status") or "pending"
    asset_id = (prev or {}).get("asset_id")
    indexed_id = (prev or {}).get("indexed_asset_id") or (prev or {}).get("video_id")

    if status in {"index_ready", "index_submitted"} and indexed_id:
        return prev or {}
    if status in TERMINAL_FAIL:
        return prev or {}

    # retry once after a failure
    if status.endswith("_failed") or status in {"asset_failed", "index_failed", "upload_failed"}:
        if attempt >= 2:
            final = dict(prev or {})
            final["status"] = "asset_failed_final" if "asset" in status or "upload" in status else "index_failed_final"
            append_jsonl(LOG_JSONL, {**final, "local_name": name, "note": "已按任务书重试一次，不再重试"})
            return final
        log_console(f"{name}: 上次失败，开始第 {attempt + 1} 次重试")
        asset_id = None
        indexed_id = None

    if status in {"asset_ready", "asset_created"} and asset_id and not indexed_id:
        # continue from indexing
        pass
    elif not asset_id or status in {"pending", "upload_started", "upload_failed", "asset_failed"}:
        attempt = attempt + 1
        append_jsonl(LOG_JSONL, {
            "local_name": name, "local_path": str(path), "size_bytes": size,
            "index_id": index_id, "kind": kind, "status": "upload_started", "attempt": attempt,
        })
        log_console(f"上传开始 {name} ({size} 字节) attempt={attempt}")
        _, body, _ = client.upload_asset_direct(path, filename=name, enable_hls=False, enable_thumbnail=False)
        asset_id = safe_id(body if isinstance(body, dict) else {}, "_id", "id", "asset_id")
        if not asset_id:
            raise ApiError(0, None, "上传响应没有 asset_id")
        append_jsonl(LOG_JSONL, {
            "local_name": name, "local_path": str(path), "size_bytes": size,
            "index_id": index_id, "asset_id": asset_id, "kind": kind,
            "status": "asset_created", "attempt": attempt,
            "upload_response_keys": list(body.keys()) if isinstance(body, dict) else [],
        })
        log_console(f"已创建 asset {name} asset_id={asset_id}")

    # wait ready
    ast = wait_asset_ready(client, asset_id)
    ast_status = str(ast.get("status") or "").lower()
    if ast_status != "ready":
        err = redact_text(json.dumps(redact_obj(ast.get("error") or ast), ensure_ascii=False))
        rec = {
            "local_name": name, "local_path": str(path), "size_bytes": size,
            "index_id": index_id, "asset_id": asset_id, "kind": kind,
            "status": "asset_failed", "attempt": attempt, "error": err, "asset_status": ast_status,
        }
        append_jsonl(LOG_JSONL, rec)
        log_console(f"asset 处理失败 {name} status={ast_status}")
        return rec

    append_jsonl(LOG_JSONL, {
        "local_name": name, "local_path": str(path), "size_bytes": size,
        "index_id": index_id, "asset_id": asset_id, "kind": kind,
        "status": "asset_ready", "attempt": attempt,
    })

    body = submit_index(client, index_id, asset_id, name, kind)
    indexed_id = safe_id(body, "_id", "id", "indexed_asset_id", "video_id")
    rec = {
        "local_name": name, "local_path": str(path), "size_bytes": size,
        "index_id": index_id, "asset_id": asset_id,
        "indexed_asset_id": indexed_id,
        "video_id": safe_id(body, "video_id") or indexed_id,
        "kind": kind, "status": "index_submitted", "attempt": attempt,
    }
    append_jsonl(LOG_JSONL, rec)
    log_console(f"已提交索引 {name} indexed_asset_id={indexed_id}")
    return rec


def wait_all_indexed(client: TwelveClient, index_id: str, items: list[dict]) -> dict[str, dict]:
    last = load_progress()
    pending = []
    for it in items:
        rec = last.get(it["local_name"]) or {}
        if rec.get("status") == "index_submitted" and (rec.get("indexed_asset_id") or rec.get("video_id")):
            pending.append(it["local_name"])
        elif rec.get("status") == "index_ready":
            continue
    log_console(f"开始等待索引完成，待确认 {len(pending)} 条")
    # batch poll with reasonable interval, not busy-wait
    remaining = set(pending)
    interval = 20.0
    start = time.time()
    timeout = 6 * 60 * 60
    while remaining:
        if time.time() - start > timeout:
            log_console("等待索引超时，停止轮询")
            break
        done_this = []
        for name in list(remaining):
            rec = last.get(name) or {}
            indexed_id = rec.get("indexed_asset_id") or rec.get("video_id")
            try:
                _, body, _ = client.get(f"/indexes/{index_id}/indexed-assets/{indexed_id}")
            except QuotaError:
                raise
            except ApiError as e:
                log_console(f"查询索引状态失败 {name}: HTTP {e.status} {e.user_message}")
                time.sleep(5)
                continue
            st = str((body or {}).get("status") if isinstance(body, dict) else "").lower()
            if st in {"ready", "complete", "completed"}:
                rec = dict(rec)
                rec.update({
                    "local_name": name, "status": "index_ready",
                    "indexed_status": st, "index_id": index_id,
                    "indexed_asset_id": indexed_id,
                    "video_id": safe_id(body, "video_id") or rec.get("video_id") or indexed_id,
                })
                append_jsonl(LOG_JSONL, rec)
                last[name] = rec
                done_this.append(name)
            elif st in {"failed", "error", "rejected"}:
                rec = dict(rec)
                rec.update({
                    "local_name": name, "status": "index_failed",
                    "indexed_status": st, "index_id": index_id,
                    "indexed_asset_id": indexed_id,
                    "error": redact_text(json.dumps(redact_obj(body), ensure_ascii=False)),
                })
                # one retry of index submit if attempts < 2
                attempt = int(rec.get("attempt") or 1)
                if attempt < 2 and rec.get("asset_id"):
                    try:
                        log_console(f"{name}: 索引失败，重试提交一次")
                        body2 = submit_index(client, index_id, rec["asset_id"], name, rec.get("kind") or "copy")
                        new_id = safe_id(body2, "_id", "id", "indexed_asset_id", "video_id")
                        rec.update({
                            "status": "index_submitted",
                            "attempt": attempt + 1,
                            "indexed_asset_id": new_id,
                            "video_id": safe_id(body2, "video_id") or new_id,
                        })
                        append_jsonl(LOG_JSONL, rec)
                        last[name] = rec
                        continue
                    except QuotaError:
                        raise
                    except Exception as e:
                        rec["status"] = "index_failed_final"
                        rec["error"] = redact_text(str(e))
                else:
                    rec["status"] = "index_failed_final"
                append_jsonl(LOG_JSONL, rec)
                last[name] = rec
                done_this.append(name)
        for name in done_this:
            remaining.discard(name)
        last = load_progress()
        remaining = {
            it["local_name"]
            for it in items
            if (last.get(it["local_name"]) or {}).get("status") == "index_submitted"
        }
        ready_n = sum(1 for it in items if (last.get(it["local_name"]) or {}).get("status") == "index_ready")
        fail_n = sum(1 for it in items if "fail" in ((last.get(it["local_name"]) or {}).get("status") or ""))
        log_console(f"索引进度: ready={ready_n} failed={fail_n} waiting={len(remaining)}")
        snapshot_state(items, last, {"index_id": index_id, "阶段": "等待索引"})
        if remaining:
            time.sleep(interval)
            interval = min(90.0, interval * 1.2)
    return load_progress()


def main() -> int:
    STATS.mkdir(parents=True, exist_ok=True)
    log_console(f"密钥环境变量: {key_status_label()}")
    if key_status_label() != "已设置":
        log_console("读不到 TWELVELABS_API_KEY，停止。不会猜测，也不会去文件或聊天记录里找。")
        return 2

    acquire_lock()
    quota_stopped = False
    quota_info = None
    index_id = None
    try:
        items = build_upload_items()
        validate_items(items)
        total_bytes = sum(it["size_bytes"] for it in items)
        log_console(f"待上传 {len(items)} 个文件，总大小 {total_bytes} 字节（{total_bytes/1024/1024/1024:.4f} GB）")

        client = TwelveClient()
        if client._proxy_label:
            log_console(f"将通过系统代理访问 API: {client._proxy_label}")
        else:
            log_console("未检测到系统代理，将直连 API")
        usage = probe_usage(client)
        indexes_before = list_indexes(client)
        log_console(f"账号现有索引数: {len(indexes_before)}")
        write_json(STATS / "接口探测_经代理.json", {
            "时间": now_str(),
            "用量探测": usage,
            "已有索引数": len(indexes_before),
            "已有索引名": [
                {
                    "index_id": safe_id(r, "_id", "id", "index_id"),
                    "index_name": r.get("index_name") or r.get("name"),
                }
                for r in indexes_before
            ],
        })

        meta = ensure_index(client)
        index_id = meta["index_id"]

        last = load_progress()
        snapshot_state(items, last, {"index_id": index_id, "阶段": "开始上传", "用量探测已做": True})

        for i, item in enumerate(items, start=1):
            last = load_progress()
            prev = last.get(item["local_name"])
            st = (prev or {}).get("status")
            if st in {"index_submitted", "index_ready"}:
                continue
            if st in TERMINAL_FAIL:
                continue
            try:
                rec = process_item(client, index_id, item, prev)
                last[item["local_name"]] = rec
                if rec.get("status") in {"asset_failed", "upload_failed", "index_failed"} and int(rec.get("attempt") or 0) < 2:
                    rec = process_item(client, index_id, item, rec)
                    last[item["local_name"]] = rec
            except QuotaError as e:
                quota_stopped = True
                quota_info = {"status": e.status, "code": e.code, "message": e.user_message}
                append_jsonl(LOG_JSONL, {
                    "local_name": item["local_name"],
                    "index_id": index_id,
                    "status": "quota_stopped",
                    "error": e.user_message,
                    "http_status": e.status,
                    "code": e.code,
                })
                log_console(f"额度不足或需要付费，立即停止。HTTP {e.status} code={e.code} message={e.user_message}")
                break
            except Exception as e:
                err = redact_text(str(e))
                tb = redact_text(traceback.format_exc())
                rec = {
                    "local_name": item["local_name"],
                    "local_path": item["local_path"],
                    "index_id": index_id,
                    "status": "upload_failed",
                    "attempt": int((prev or {}).get("attempt") or 0) + 1,
                    "error": err,
                }
                append_jsonl(LOG_JSONL, rec)
                log_console(f"上传异常 {item['local_name']}: {err}")
                # retry once immediately if first failure
                if rec["attempt"] < 2:
                    try:
                        rec = process_item(client, index_id, item, rec)
                        last[item["local_name"]] = rec
                    except QuotaError as qe:
                        quota_stopped = True
                        quota_info = {"status": qe.status, "code": qe.code, "message": qe.user_message}
                        log_console(f"额度不足或需要付费，立即停止。HTTP {qe.status} code={qe.code}")
                        append_jsonl(LOG_JSONL, {
                            "local_name": item["local_name"], "index_id": index_id,
                            "status": "quota_stopped", "error": qe.user_message,
                            "http_status": qe.status, "code": qe.code,
                        })
                        break
                    except Exception as e2:
                        rec = {
                            "local_name": item["local_name"], "index_id": index_id,
                            "status": "asset_failed_final",
                            "attempt": rec["attempt"],
                            "error": redact_text(str(e2)),
                        }
                        append_jsonl(LOG_JSONL, rec)
                        last[item["local_name"]] = rec
                        log_console(f"重试仍失败 {item['local_name']}: {redact_text(str(e2))}")
                else:
                    rec["status"] = "asset_failed_final"
                    append_jsonl(LOG_JSONL, rec)
                    last[item["local_name"]] = rec
            if i % 5 == 0 or i == len(items):
                snapshot_state(items, load_progress(), {"index_id": index_id, "阶段": "上传中", "已处理序号": i})
            time.sleep(DIRECT_WAIT)

        last = load_progress()
        if not quota_stopped:
            last = wait_all_indexed(client, index_id, items)

        last = load_progress()
        counts: dict[str, int] = {}
        for it in items:
            st = (last.get(it["local_name"]) or {}).get("status") or "pending"
            counts[st] = counts.get(st, 0) + 1
        write_json(STATE_JSON, {
            "更新时间": now_str(),
            "index_id": index_id,
            "index_name": INDEX_NAME,
            "总待传": len(items),
            "状态计数": counts,
            "额度停止": quota_stopped,
            "额度信息": quota_info,
            "阶段": "额度停止" if quota_stopped else "上传与索引阶段结束",
        })
        log_console(f"本阶段结束。状态计数={counts} 额度停止={quota_stopped}")
        return 4 if quota_stopped else 0
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
