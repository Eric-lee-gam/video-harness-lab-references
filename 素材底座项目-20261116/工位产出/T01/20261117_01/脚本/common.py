# -*- coding: utf-8 -*-
"""T01 共用函数：路径只从配置或共同约定读取，脚本内不写共享盘地址。"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8))

VIDEO_EXTS = {
    ".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".wmv",
    ".mpg", ".mpeg", ".ts", ".flv", ".webm", ".3gp", ".insv", ".mxf",
}

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff", ".gif"}

PASSWORD_NAME_MARK = "资料账号密码"

# 词表第四节里、落在本批四个目录范围内的限制目录（用正斜杠相对共享盘根）
VOCAB_LIMIT_DIRS = [
    {
        "相对前缀": "拍摄/小区/汉黄社区(阿姨不要用)",
        "目录限制原文": "阿姨不要用",
        "可用状态": "可用",
        "词表条数": 130,
    },
    {
        "相对前缀": "拍摄/小区/汉阳4个卫生间（打码）",
        "目录限制原文": "打码",
        "可用状态": "需打码后可用",
        "词表条数": 53,
    },
    {
        "相对前缀": "拍摄/小区/南湖名都（业主露脸需要打码）",
        "目录限制原文": "业主露脸需要打码",
        "可用状态": "需打码后可用",
        "词表条数": 44,
    },
    {
        "相对前缀": "拍摄/小区/新华家园(需要打码）",
        "目录限制原文": "需要打码",
        "可用状态": "需打码后可用",
        "词表条数": 41,
    },
    {
        "相对前缀": "拍摄/小区/2其他/用不太上的",
        "目录限制原文": "用不太上的",
        "可用状态": "可用",
        "词表条数": 559,
    },
]

UNLISTED_LIMIT_WORDS = ("打码", "不要用", "禁用", "离职", "不能用", "禁止")


def this_output_dir() -> Path:
    # .../工位产出/T01/20261117_01/脚本/common.py
    return Path(__file__).resolve().parents[1]


def project_dir() -> Path:
    # 脚本/本批次/任务号/工位产出/项目文件夹
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


def parse_share_root_from_conventions(text: str) -> str:
    # 从共同约定表格“主库（只读）”那一格的反引号路径读取。
    m = re.search(r"主库（只读）\s*\|\s*`([^`]+)`", text)
    if not m:
        raise ValueError("共同约定.md 里没有解析到“主库（只读）”路径")
    return m.group(1).strip()


def read_share_root() -> str:
    conv = project_dir() / "共同约定.md"
    return parse_share_root_from_conventions(conv.read_text(encoding="utf-8"))


def to_posix(s: str) -> str:
    return s.replace("\\", "/").strip("/")


def join_unc(*parts: str) -> str:
    # 保留 UNC 开头的两个反斜杠
    cleaned = [str(p).replace("/", "\\") for p in parts if p is not None and str(p) != ""]
    if not cleaned:
        return ""
    head = cleaned[0]
    rest = [p.strip("\\") for p in cleaned[1:]]
    if head.startswith("\\\\"):
        return "\\".join([head.rstrip("\\")] + rest)
    return "\\".join([head.rstrip("\\")] + rest)


def logical_path(prefix: str, share_rel_posix: str) -> str:
    return f"{prefix.rstrip('/')}/{to_posix(share_rel_posix)}"


def format_mtime(ts: float) -> str:
    return datetime.fromtimestamp(ts, SHANGHAI).isoformat(timespec="seconds")


def now_iso() -> str:
    return datetime.now(SHANGHAI).isoformat(timespec="seconds")


def write_json(path: Path, obj, indent: int = 2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    tmp.replace(path)


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def classify_source_type(lib_default: str, share_rel_posix: str) -> str:
    parts = to_posix(share_rel_posix).split("/")
    # 拍摄/<库>/<一级目录>/...
    if len(parts) >= 3 and parts[2] == "展厅":
        return "自拍·展厅"
    return lib_default


def match_limit(share_rel_posix: str) -> dict | None:
    rel = to_posix(share_rel_posix)
    # 长前缀优先
    items = sorted(VOCAB_LIMIT_DIRS, key=lambda x: len(x["相对前缀"]), reverse=True)
    for item in items:
        pref = item["相对前缀"]
        if rel == pref or rel.startswith(pref + "/"):
            return item
    return None


def project_name(share_rel_posix: str) -> str:
    parts = to_posix(share_rel_posix).split("/")
    # 拍摄/小区/<项目>/...
    if len(parts) >= 3:
        return parts[2]
    if len(parts) == 2:
        return parts[1]
    return ""


def dir_original_name(share_rel_posix: str) -> str:
    parts = to_posix(share_rel_posix).split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])
