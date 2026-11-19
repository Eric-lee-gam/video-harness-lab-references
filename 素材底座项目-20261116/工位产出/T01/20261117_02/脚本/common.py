# -*- coding: utf-8 -*-
"""T01 20261117_02 共用：路径从配置读取，脚本内不写共享盘地址。"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8))


def this_output_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def project_dir() -> Path:
    return Path(__file__).resolve().parents[4]


def fragment_dir() -> Path:
    return project_dir() / "片段库"


def config_path() -> Path:
    return fragment_dir() / "配置" / "素材库.json"


def load_config(path: Path | None = None) -> dict:
    p = path or config_path()
    if not p.exists():
        raise FileNotFoundError(f"找不到配置文件：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


def to_posix(s: str) -> str:
    return s.replace("\\", "/").strip("/")


def join_unc(*parts: str) -> str:
    cleaned = [str(p).replace("/", "\\") for p in parts if p is not None and str(p) != ""]
    if not cleaned:
        return ""
    head = cleaned[0]
    rest = [p.strip("\\") for p in cleaned[1:]]
    if head.startswith("\\\\"):
        return "\\".join([head.rstrip("\\")] + rest)
    return "\\".join([head.rstrip("\\")] + rest)


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def format_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts, SHANGHAI).isoformat(timespec="seconds")


def full_path_from_record(share_root: str, rec: dict) -> Path:
    rel = rec.get("共享相对路径") or ""
    return Path(join_unc(share_root, rel))


def write_json(path: Path, obj, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    safe_replace(tmp, path)


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    safe_replace(tmp, path)


def safe_replace(tmp: Path, dest: Path) -> None:
    try:
        tmp.replace(dest)
        return
    except PermissionError:
        pass
    try:
        if dest.exists():
            dest.unlink()
        tmp.replace(dest)
        return
    except PermissionError:
        pass
    shutil.copy2(tmp, dest)
    try:
        tmp.unlink()
    except OSError:
        pass


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_jsonl(path: Path) -> list:
    return list(iter_jsonl(path))


def orientation(width, height, rotation) -> str | None:
    """按显示宽高判断画幅。旋转 90/270 时交换宽高；高大于宽为竖，其余为横（含正方形）。"""
    if width is None or height is None:
        return None
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return None
    rot = 0
    if rotation not in (None, ""):
        try:
            rot = abs(int(round(float(rotation)))) % 360
        except (TypeError, ValueError):
            rot = 0
    if rot in (90, 270):
        w, h = h, w
    return "竖" if h > w else "横"


def normalize_rotation(rot):
    if rot in (None, ""):
        return 0
    try:
        val = float(rot)
    except (TypeError, ValueError):
        return 0
    if abs(val) < 0.5:
        return 0
    if abs(val - round(val)) < 1e-6:
        return int(round(val))
    return val


def sanitize_error(msg: str) -> str:
    if not msg:
        return "ffprobe失败"
    s = msg.replace("\r", " ").replace("\n", " ").strip()
    s = re.sub(r"\\\\[^\s\"']+", "", s)
    s = re.sub(r"[A-Za-z]:\\[^\s\"']+", "", s)
    s = re.sub(r"\s+", " ", s).strip(" :")
    low = s.lower()
    if "moov atom not found" in low or "moov" in low:
        return "ffprobe失败：moov atom not found（文件损坏或不完整）"
    if "超时" in s:
        return s[:200]
    if s:
        return ("ffprobe失败：" + s)[:200]
    return "ffprobe失败"


def parse_rotation_from_stream(v: dict):
    rot = v.get("rotation")
    tags = v.get("tags") or {}
    if rot in (None, "") and tags.get("rotate") not in (None, ""):
        rot = tags.get("rotate")
    for sd in v.get("side_data_list") or []:
        if not isinstance(sd, dict):
            continue
        if sd.get("rotation") not in (None, ""):
            rot = sd.get("rotation")
    return rot


def probe_file(path: Path, timeout: int = 30) -> dict:
    # 必须用 -show_streams，才能读到 Display Matrix 里的 rotation。
    # -show_entries stream=rotation 读不到 side_data，会把带矩阵旋转的竖屏误判成横屏。
    cmd = [
        "ffprobe", "-v", "error",
        "-probesize", "5000000",
        "-analyzeduration", "5000000",
        "-select_streams", "v:0",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            return {
                "ok": False,
                "error": sanitize_error(proc.stderr or proc.stdout or "ffprobe失败"),
                "用时秒": elapsed,
            }
        data = json.loads(proc.stdout or "{}")
        fmt = data.get("format") or {}
        streams = data.get("streams") or []
        v = streams[0] if streams else {}
        dur = v.get("duration") or fmt.get("duration")
        width, height = v.get("width"), v.get("height")
        rot = parse_rotation_from_stream(v)
        has_matrix = False
        for sd in v.get("side_data_list") or []:
            if isinstance(sd, dict) and (
                sd.get("rotation") not in (None, "")
                or "displaymatrix" in sd
                or "Display Matrix" in str(sd.get("side_data_type") or "")
            ):
                has_matrix = True
                break
        return {
            "ok": True,
            "时长": float(dur) if dur not in (None, "") else None,
            "宽": int(width) if width not in (None, "") else None,
            "高": int(height) if height not in (None, "") else None,
            "旋转角度": normalize_rotation(rot),
            "有DisplayMatrix": has_matrix,
            "用时秒": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"超时{timeout}秒", "用时秒": time.perf_counter() - t0}
    except Exception as e:
        return {"ok": False, "error": sanitize_error(f"{type(e).__name__}: {e}"), "用时秒": time.perf_counter() - t0}
