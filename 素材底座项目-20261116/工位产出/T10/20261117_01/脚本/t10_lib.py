# -*- coding: utf-8 -*-
"""T10 shared helpers. Reads addresses from 片段库/配置/路径与库名.json."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

OUT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
PROJECT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
RULES = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116")
ANN = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
CLIPLIB = PROJECT / "片段库"
CONFIG_PATH = CLIPLIB / "配置" / "路径与库名.json"
LABEL = OUT / "标注库副本"
LEARN = OUT / "镜序副本" / "learning.sqlite3"
CATALOG = OUT / "镜序副本" / "catalog.sqlite3"
EVIDENCE = OUT / "镜序副本" / "identity-evidence.json"

BS = chr(92)
SHARED_UNC = BS + BS + r"192.168.110.36" + BS + "共享本公司"


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def ro_sqlite(path: Path):
    return sqlite3.connect("file:" + Path(path).as_posix() + "?mode=ro&immutable=1", uri=True)


def norm_slash(p: str) -> str:
    if p is None:
        return ""
    s = str(p)
    if s.startswith("//") or s.startswith(BS + BS):
        rest = s[2:].replace("/", BS)
        while BS + BS in rest:
            rest = rest.replace(BS + BS, BS)
        return BS + BS + rest
    s = s.replace("/", BS)
    while BS + BS in s:
        s = s.replace(BS + BS, BS)
    return s


def to_relpath(path: str | None) -> str | None:
    if not path:
        return None
    s = norm_slash(path)
    low = s.lower()
    marker = (SHARED_UNC + BS).lower()
    marker2 = SHARED_UNC.lower()
    if low.startswith(marker):
        return s[len(SHARED_UNC + BS):].lstrip(BS)
    if low.startswith(marker2):
        return s[len(SHARED_UNC):].lstrip(BS)
    if s.startswith("史上最完整共享" + BS) or s.startswith("史上最完整共享/"):
        return norm_slash(s)
    idx = s.find("史上最完整共享" + BS)
    if idx >= 0:
        return s[idx:]
    return s if s else None


def range_flag(relpath: str | None) -> str:
    if not relpath:
        return "范围外"
    s = norm_slash(relpath)
    prefixes = [
        "史上最完整共享" + BS + "拍摄" + BS + "小区",
        "史上最完整共享" + BS + "拍摄" + BS + "测试",
        "史上最完整共享" + BS + "拍摄" + BS + "阿明",
        "史上最完整共享" + BS + "拍摄" + BS + "搅拌",
        "拍摄" + BS + "小区",
        "拍摄" + BS + "测试",
        "拍摄" + BS + "阿明",
        "拍摄" + BS + "搅拌",
    ]
    for p in prefixes:
        if s == p or s.startswith(p + BS):
            return "范围内"
    return "范围外"


def which_dir(relpath: str | None) -> str | None:
    if not relpath:
        return None
    s = norm_slash(relpath)
    mapping = [
        ("史上最完整共享" + BS + "拍摄" + BS + "小区", "小区"),
        ("史上最完整共享" + BS + "拍摄" + BS + "测试", "测试"),
        ("史上最完整共享" + BS + "拍摄" + BS + "阿明", "阿明"),
        ("史上最完整共享" + BS + "拍摄" + BS + "搅拌", "搅拌"),
        ("史上最完整共享" + BS + "扒扒", "扒扒"),
        ("拍摄" + BS + "小区", "小区"),
        ("拍摄" + BS + "测试", "测试"),
        ("拍摄" + BS + "阿明", "阿明"),
        ("拍摄" + BS + "搅拌", "搅拌"),
    ]
    for p, name in mapping:
        if s == p or s.startswith(p + BS):
            return name
    if (BS + "扒扒" + BS) in (BS + s + BS) or s.startswith("扒扒" + BS) or s == "扒扒":
        return "扒扒"
    return None


def from_root_rel(root: str | None, rel: str | None, cfg=None) -> str | None:
    cfg = cfg or load_config()
    if not rel:
        return None
    rel_n = norm_slash(rel)
    info = (cfg.get("镜序根别名") or {}).get(root or "") or {}
    prefix = info.get("主库相对路径前缀")
    if prefix:
        return prefix + BS + rel_n
    return None


def write_jsonl(path: Path, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str))
            f.write("\n")


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            yield i, json.loads(line)


def load_catalog():
    conn = ro_sqlite(CATALOG)
    cur = conn.cursor()
    by_id = {}
    by_rel = {}
    for rid, root, rel, name, size, stamp, available in cur.execute(
        "SELECT id, root, rel, name, size, stamp, available FROM assets"
    ):
        rec = {
            "id": rid,
            "root": root,
            "rel": rel,
            "name": name,
            "size": size,
            "stamp": stamp,
            "available": available,
        }
        rec["主库相对路径"] = from_root_rel(root, rel)
        by_id[rid] = rec
        if rec["主库相对路径"]:
            by_rel[norm_slash(rec["主库相对路径"]).lower()] = rec
        if rel:
            by_rel.setdefault(norm_slash(rel).lower(), rec)
        if name:
            by_rel.setdefault(("name", name.lower()), rec)
    conn.close()
    return by_id, by_rel


def load_ann_indexes():
    by_id = {}
    by_path = {}
    files = [
        LABEL / "小区全库" / "数据" / "AI剪辑检索索引.jsonl",
        LABEL / "测试阿明搅拌" / "数据" / "AI剪辑检索索引.jsonl",
    ]
    for fp in files:
        for lineno, o in iter_jsonl(fp):
            rel = to_relpath(o.get("source_path"))
            rec = {
                "标注库ID": o.get("id"),
                "source_path": o.get("source_path"),
                "主库相对路径": rel,
                "project": o.get("project"),
                "source_folder": o.get("source_folder"),
                "duration_seconds": o.get("duration_seconds"),
                "kind": o.get("kind"),
                "index_file": str(fp.relative_to(LABEL)),
            }
            if o.get("id"):
                by_id[o["id"]] = rec
            if rel:
                by_path[norm_slash(rel).lower()] = rec
    return by_id, by_path


def locate(asset_id=None, path=None, root=None, rel=None, ann_id=None,
           catalog=None, ann=None):
    cat_by_id, cat_by_rel = catalog if catalog else ({}, {})
    ann_by_id, ann_by_path = ann if ann else ({}, {})
    relpath = None
    jingxu_id = asset_id
    label_id = ann_id
    evidence = []

    if path:
        relpath = to_relpath(path) or relpath
        if relpath:
            evidence.append("源路径")
    if root and rel and not relpath:
        relpath = from_root_rel(root, rel)
        if relpath:
            evidence.append("镜序root+rel")
    if asset_id and asset_id in cat_by_id:
        rec = cat_by_id[asset_id]
        jingxu_id = rec["id"]
        if not relpath:
            relpath = rec.get("主库相对路径")
        evidence.append("镜序登记表id")
    if ann_id and ann_id in ann_by_id:
        rec = ann_by_id[ann_id]
        label_id = rec["标注库ID"]
        if not relpath:
            relpath = rec.get("主库相对路径")
        evidence.append("标注库id")
    if relpath:
        key = norm_slash(relpath).lower()
        if key in cat_by_rel:
            rec = cat_by_rel[key]
            jingxu_id = jingxu_id or rec["id"]
            evidence.append("路径对上登记表")
        if key in ann_by_path:
            rec = ann_by_path[key]
            label_id = label_id or rec["标注库ID"]
            evidence.append("路径对上标注库索引")

    located = False
    if relpath and (
        relpath.startswith("史上最完整共享" + BS)
        or which_dir(relpath)
        or "镜序登记表id" in evidence
        or "标注库id" in evidence
        or "源路径" in evidence
        or "镜序root+rel" in evidence
    ):
        located = True
    if root in ("chengdu", "suzhou") and not relpath:
        located = False

    return {
        "主库相对路径": relpath,
        "镜序素材ID": jingxu_id or None,
        "标注库ID": label_id or None,
        "范围": range_flag(relpath),
        "目录": which_dir(relpath),
        "定位依据": evidence,
        "定位到文件": located,
    }


def fact_record(*, loc, start, end, content, source_file, source_id,
                confirmer, confirmed_at, level, qualifiers=None,
                is_negative=None, confirm_status="已确认", extra=None):
    rec = {
        "层": "事实层",
        "主库相对路径": loc.get("主库相对路径"),
        "原片ID": None,
        "镜序素材ID": loc.get("镜序素材ID"),
        "标注库ID": loc.get("标注库ID"),
        "起秒": start,
        "止秒": end,
        "内容": content,
        "来源文件": source_file,
        "来源条目标识": source_id,
        "确认人": confirmer,
        "确认时间": confirmed_at,
        "范围": loc.get("范围") or "范围外",
        "目录": loc.get("目录"),
        "确认级别": level,
        "限定语原文": qualifiers,
        "是否反例": is_negative,
        "确认状态": confirm_status,
        "定位到文件": loc.get("定位到文件"),
        "定位依据": loc.get("定位依据"),
        "原片ID说明": "T01 原片表尚未产出，本批先留空，等原片表出现后再接原片 ID",
    }
    if extra:
        rec.update(extra)
    return rec
