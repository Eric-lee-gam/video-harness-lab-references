# -*- coding: utf-8 -*-
"""C01 检查共用函数。数字全部由本套脚本从原始数据重算，不复用 T01 的计算结果。"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8))

PROJECT_DIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
C01_OUT = PROJECT_DIR / "工位产出" / "C01" / "20261117_01"
T01_OUT = PROJECT_DIR / "工位产出" / "T01" / "20261117_01"
T01_SCRIPTS = T01_OUT / "脚本"
FRAGMENT_DIR = PROJECT_DIR / "片段库"
TABLE_PATH = FRAGMENT_DIR / "原片表.jsonl"
CONFIG_PATH = FRAGMENT_DIR / "配置" / "素材库.json"
CATALOG_PATH = T01_OUT / "输入副本" / "catalog.sqlite3"
ANN_XIAOQ_PATH = T01_OUT / "输入副本" / "标注库_小区全库_AI剪辑检索索引.jsonl"
ANN_OTHER_PATH = T01_OUT / "输入副本" / "标注库_测试阿明搅拌_AI剪辑检索索引.jsonl"
CONVENTIONS_PATH = PROJECT_DIR / "共同约定.md"
INVENTORY_CSV = Path(r"C:\Users\leega\AppData\Local\Temp\share-video-inventory-20261114\36-gongxiang.csv")

# 自己的随机种子，不用 T01 的 20261117
SEED = 87112617

PASSWORD_NAME_MARK = "资料账号密码"

# 独立给出的常见视频扩展名（小写，带点）
VIDEO_EXTS = {
    ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".wmv",
    ".mpg", ".mpeg", ".ts", ".flv", ".webm", ".3gp", ".insv", ".mxf",
}

IN_SCOPE_LIBS = [
    {"库ID": "xiaoq", "目录名": "小区", "相对根路径": "拍摄/小区", "镜序库别名": "xiaoq"},
    {"库ID": "ceshi", "目录名": "测试", "相对根路径": "拍摄/测试", "镜序库别名": ""},
    {"库ID": "aming", "目录名": "阿明", "相对根路径": "拍摄/阿明", "镜序库别名": ""},
    {"库ID": "jiaoban", "目录名": "搅拌", "相对根路径": "拍摄/搅拌", "镜序库别名": ""},
]

# 专有词表第四节全部限制目录；检查第 5 项只比「范围内」的
VOCAB_LIMIT_DIRS = [
    {
        "词表文件夹": r"拍摄\客户的素材(人物需打码)",
        "相对前缀": "拍摄/客户的素材(人物需打码)",
        "词表条数": 8463,
        "目录限制原文": "人物需打码",
        "范围内": False,
    },
    {
        "词表文件夹": r"小区\汉黄社区(阿姨不要用)",
        "相对前缀": "拍摄/小区/汉黄社区(阿姨不要用)",
        "词表条数": 130,
        "目录限制原文": "阿姨不要用",
        "范围内": True,
    },
    {
        "词表文件夹": r"小区\汉阳4个卫生间（打码）",
        "相对前缀": "拍摄/小区/汉阳4个卫生间（打码）",
        "词表条数": 53,
        "目录限制原文": "打码",
        "范围内": True,
    },
    {
        "词表文件夹": r"小区\南湖名都（业主露脸需要打码）",
        "相对前缀": "拍摄/小区/南湖名都（业主露脸需要打码）",
        "词表条数": 44,
        "目录限制原文": "业主露脸需要打码",
        "范围内": True,
    },
    {
        "词表文件夹": r"小区\新华家园(需要打码）",
        "相对前缀": "拍摄/小区/新华家园(需要打码）",
        "词表条数": 41,
        "目录限制原文": "需要打码",
        "范围内": True,
    },
    {
        "词表文件夹": r"小区\2其他\用不太上的",
        "相对前缀": "拍摄/小区/2其他/用不太上的",
        "词表条数": 559,
        "目录限制原文": "用不太上的",
        "范围内": True,
    },
    {
        "词表文件夹": r"拍摄\招商\嘉贝乐工厂\口播",
        "相对前缀": "拍摄/招商/嘉贝乐工厂/口播",
        "词表条数": 217,
        "目录限制原文": "",
        "范围内": False,
        "说明": "文件夹名未写限制，不在本批四个目录内",
    },
]

ADDRESS_PATTERNS = [
    re.compile(r"192\.168\.110\.36"),
    re.compile(r"共享本公司"),
    re.compile(r"史上最完整共享"),
    re.compile(r"\\\\192\."),
    re.compile(r"//192\.168"),
]


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


def file_meta(path: Path) -> dict:
    st = path.stat()
    return {
        "路径": str(path),
        "字节数": st.st_size,
        "修改时间": datetime.fromtimestamp(st.st_mtime, SHANGHAI).isoformat(timespec="seconds"),
        "sha256": sha256_file(path) if st.st_size <= 8 * 1024 * 1024 else None,
    }


def write_json(path: Path, obj, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_origin_table():
    return list(iter_jsonl(TABLE_PATH))


def jingxu_id(alias: str, rel_posix: str) -> str:
    return hashlib.sha256(f"{alias}/{to_posix(rel_posix)}".encode("utf-8")).hexdigest()[:32]


def is_apple_double(name: str) -> bool:
    return name.startswith("._")


def looks_like_mp4_by_magic(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            head = f.read(32)
    except OSError:
        return False
    return (len(head) >= 8 and head[4:8] == b"ftyp") or (b"ftyp" in head[:16])


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


def head_hash(path: Path, n: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = n
        while remaining > 0:
            chunk = f.read(min(65536, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def open_sqlite_ro(path: Path) -> sqlite3.Connection:
    uri = f"file:{path.as_posix()}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    return con


def load_catalog_xiaoq(path: Path) -> list[dict]:
    con = open_sqlite_ro(path)
    try:
        rows = []
        for r in con.execute(
            "SELECT id, root, rel, name, size, stamp, meta, error, available FROM assets WHERE root = ?",
            ("xiaoq",),
        ):
            rows.append(dict(r))
        return rows
    finally:
        con.close()


def share_rel_from_source_path(source_path: str, share_root: str) -> str | None:
    if not source_path:
        return None
    src = to_posix(source_path)
    root = to_posix(share_root)
    src_cf = src.casefold()
    root_cf = root.casefold()
    if src_cf.startswith(root_cf + "/"):
        # 用长度对齐，避免大小写造成切片偏差
        return src[len(root) + 1 :]
    if src_cf == root_cf:
        return ""
    token = "史上最完整共享/"
    i = src_cf.find(token.casefold())
    if i >= 0:
        return src[i + len(token) :]
    return None


def probe_file(path: Path, timeout: int = 30) -> dict:
    # 必须用 -show_streams，才能读到 Display Matrix 里的 rotation。
    # -show_entries stream=rotation 读不到 side_data，会把带 -90° 矩阵的竖屏误判成横屏。
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


def path_under_prefix(rel: str, prefix: str) -> bool:
    rel = to_posix(rel)
    pref = to_posix(prefix)
    return rel == pref or rel.startswith(pref + "/")


def format_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts, SHANGHAI).isoformat(timespec="seconds")
