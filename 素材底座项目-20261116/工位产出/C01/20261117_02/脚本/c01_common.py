# -*- coding: utf-8 -*-
"""C01 20261117_02 重查第 3 项共用函数。只读，不写片段库或 T01 产出。"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8))

PROJECT_DIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
C01_OUT = PROJECT_DIR / "工位产出" / "C01" / "20261117_02"
C01_PREV = PROJECT_DIR / "工位产出" / "C01" / "20261117_01"
TABLE_PATH = PROJECT_DIR / "片段库" / "原片表.jsonl"
CONVENTIONS_PATH = PROJECT_DIR / "共同约定.md"
PREV_SAMPLE_PATH = C01_PREV / "核对" / "抽检50条.json"

EXPECTED_TABLE_SHA256 = "3891213ba53acf3dbff89dd594ff195a887ad4639b661c872e4be582a2813da4"
EXPECTED_TABLE_MTIME = "2026-11-17T14:34:50+08:00"
EXPECTED_TABLE_COUNT = 21172

OLD_SEED = 87112617
# 新种子，不是 T01 的 20261117，也不是上次的 87112617
NEW_SEED = 202611171437


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def to_posix(s: str) -> str:
    return str(s).replace("\\", "/").strip("/")


def join_unc(root: str, *parts: str) -> str:
    head = str(root).replace("/", "\\")
    rest = [str(p).replace("/", "\\").strip("\\") for p in parts if p is not None and str(p) != ""]
    if head.startswith("\\\\"):
        return "\\".join([head.rstrip("\\")] + rest)
    return str(Path(head, *rest)) if rest else head


def parse_share_root_from_conventions(text: str) -> str:
    m = re.search(r"主库（只读）\s*\|\s*`([^`]+)`", text)
    if not m:
        raise ValueError("共同约定.md 里没有解析到“主库（只读）”路径")
    return m.group(1).strip()


def read_share_root() -> str:
    return parse_share_root_from_conventions(CONVENTIONS_PATH.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def format_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, SHANGHAI).isoformat(timespec="seconds")


def file_meta(path: Path, with_hash: bool = True) -> dict:
    st = path.stat()
    return {
        "路径": str(path),
        "字节数": st.st_size,
        "修改时间": format_mtime(path),
        "sha256": sha256_file(path) if with_hash else None,
    }


def write_json(path: Path, obj, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_origin_table():
    return list(iter_jsonl(TABLE_PATH))


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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


def probe_file(path: Path, timeout: int = 30) -> dict:
    # 必须用 -show_streams，才能读到 Display Matrix 里的 rotation。
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
                "error": (proc.stderr or proc.stdout or "ffprobe失败").strip()[:500],
                "用时秒": elapsed,
            }
        data = json.loads(proc.stdout or "{}")
        fmt = data.get("format") or {}
        streams = data.get("streams") or []
        v = streams[0] if streams else {}
        dur = v.get("duration") or fmt.get("duration")
        width, height = v.get("width"), v.get("height")
        rot = v.get("rotation")
        tags = v.get("tags") or {}
        if rot in (None, "") and tags.get("rotate") not in (None, ""):
            rot = tags.get("rotate")
        for sd in v.get("side_data_list") or []:
            if isinstance(sd, dict) and sd.get("rotation") not in (None, ""):
                rot = sd.get("rotation")
        return {
            "ok": True,
            "时长": float(dur) if dur not in (None, "") else None,
            "宽": int(width) if width not in (None, "") else None,
            "高": int(height) if height not in (None, "") else None,
            "旋转角度": float(rot) if rot not in (None, "") else 0,
            "用时秒": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"超时{timeout}秒", "用时秒": time.perf_counter() - t0}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "用时秒": time.perf_counter() - t0}


def full_path_from_record(share_root: str, rec: dict) -> Path:
    rel = rec.get("共享相对路径") or ""
    return Path(join_unc(share_root, *to_posix(rel).split("/")))


def rot_equal(table_rot, probe_rot) -> bool:
    try:
        t_r = 0.0 if table_rot in (None, "") else float(table_rot)
        p_r = 0.0 if probe_rot in (None, "") else float(probe_rot)
    except (TypeError, ValueError):
        return False
    diff = abs(t_r - p_r)
    return diff < 0.5 or (diff % 360) < 0.5 or abs(diff - 360) < 0.5
