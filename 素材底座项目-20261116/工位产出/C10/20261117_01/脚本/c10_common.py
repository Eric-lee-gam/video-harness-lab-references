# -*- coding: utf-8 -*-
"""C10 independent helpers. Do not import or run T10 conversion scripts."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

OUT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01")
RAW = OUT / "原始副本"
MID = OUT / "检查中间结果"
SCRIPTS = OUT / "脚本"
PROJ = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
LIB = PROJ / "片段库"
T10 = PROJ / r"工位产出\T10\20261117_01"
JX_ROOT = Path(r"D:\CutFrame项目完整整理_20261116")
SHARE_UNC_ROOT = Path(r"\\192.168.110.36\共享本公司")
ANN_UNC = Path(r"\\192.168.110.36\obsidian\素材标注")
REL_PREFIX = "史上最完整共享"

# Independent random seed — must not reuse T10's 20261117
RANDOM_SEED = 26111710

CATALOG_ROOT_TO_REL = {
    "xiaoq": r"史上最完整共享\拍摄\小区",
    "baba": r"史上最完整共享\扒扒",
    # chengdu / suzhou: mapping not established from this batch's inputs
}

PYTHON = r"C:\Python314\python.exe"

MID.mkdir(parents=True, exist_ok=True)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def dump_json(path: Path, obj, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=indent, default=str) + "\n", encoding="utf-8")


def open_sqlite_ro(path: Path):
    uri = "file:" + Path(path).resolve().as_posix() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def norm_path(p) -> str:
    if p is None:
        return ""
    s = str(p).replace("/", "\\")
    while "\\\\" in s and not s.startswith("\\\\"):
        s = s.replace("\\\\", "\\")
    # keep UNC prefix
    if s.startswith("\\\\"):
        # collapse only after the share root? keep as-is after replacing / 
        parts = s.split("\\")
        # ['', '', host, share, ...]
        rebuilt = ["", ""]
        for part in parts[2:]:
            if part != "":
                rebuilt.append(part)
        s = "\\".join(rebuilt)
    else:
        while "\\\\" in s:
            s = s.replace("\\\\", "\\")
    return s


def rel_from_any_path(p) -> str | None:
    """Turn a UNC or relative path into 主库相对路径 starting with 史上最完整共享."""
    if not p:
        return None
    s = norm_path(p)
    marker = REL_PREFIX
    idx = s.lower().find(marker.lower()) if False else s.find(marker)
    # case-sensitive as used in data; also try
    if idx < 0:
        low = s.lower()
        m = marker.lower()
        idx = low.find(m)
        if idx >= 0:
            # preserve original casing from s after idx? use canonical prefix
            rest = s[idx + len(marker):]
            return marker + rest
        return s
    return s[idx:]


def unc_from_rel(rel: str) -> Path:
    rel_n = norm_path(rel)
    # 主库相对路径 starts with 史上最完整共享\...
    return SHARE_UNC_ROOT / rel_n


def catalog_relpath(root: str, rel: str) -> str | None:
    prefix = CATALOG_ROOT_TO_REL.get(root)
    if not prefix:
        return None
    rel_n = norm_path(rel)
    if rel_n.startswith("\\"):
        rel_n = rel_n.lstrip("\\")
    return prefix + "\\" + rel_n


def paths_equal(a, b) -> bool:
    return norm_path(a).lower() == norm_path(b).lower()


def jsonable(obj):
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [jsonable(x) for x in obj]
    if isinstance(obj, Path):
        return str(obj)
    return obj
