# -*- coding: utf-8 -*-
"""Backfill 原片ID from T01 原片表.jsonl into T10 outputs. Does not modify 原片表."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t10_lib as L

YUAN = L.CLIPLIB / "原片表.jsonl"


def add_key(index, key, rec):
    if not key:
        return
    index.setdefault(key, rec)


def build_index():
    by_ann = {}
    by_jx = {}
    by_path = {}
    n = 0
    empty_ann = 0
    for _, o in L.iter_jsonl(YUAN):
        n += 1
        yuan_id = o.get("原片ID")
        if not yuan_id:
            continue
        slim = {
            "原片ID": yuan_id,
            "逻辑路径": o.get("逻辑路径"),
            "标注库ID": o.get("标注库ID") or None,
            "镜序素材ID": o.get("镜序素材ID") or None,
            "共享相对路径": o.get("共享相对路径"),
        }
        if o.get("标注库ID"):
            add_key(by_ann, str(o["标注库ID"]), slim)
        else:
            empty_ann += 1
        if o.get("镜序素材ID"):
            add_key(by_jx, str(o["镜序素材ID"]), slim)
        # paths
        for raw in (o.get("共享相对路径"), o.get("逻辑路径"), o.get("库内相对路径")):
            if not raw:
                continue
            s = str(raw)
            if s.startswith("@shared/"):
                s = "史上最完整共享/" + s[len("@shared/"):]
            s = L.norm_slash(s)
            add_key(by_path, s.lower(), slim)
            if s.lower().startswith("拍摄" + L.BS.lower() if False else ("拍摄" + "\\").lower()):
                add_key(by_path, ("史上最完整共享\\" + s).lower(), slim)
            if s.lower().startswith("史上最完整共享\\"):
                add_key(by_path, s[len("史上最完整共享\\"):].lower(), slim)
    print("原片表", n, "ann", len(by_ann), "jingxu", len(by_jx), "path", len(by_path), "empty_ann", empty_ann)
    return by_ann, by_jx, by_path


def find(rec, by_ann, by_jx, by_path):
    aid = rec.get("标注库ID")
    if aid and str(aid) in by_ann:
        return by_ann[str(aid)], "标注库ID"
    jid = rec.get("镜序素材ID")
    if jid and str(jid) in by_jx:
        return by_jx[str(jid)], "镜序素材ID"
    p = rec.get("主库相对路径")
    if p:
        key = L.norm_slash(p).lower()
        if key in by_path:
            return by_path[key], "主库相对路径"
        if key.startswith("史上最完整共享\\"):
            k2 = key[len("史上最完整共享\\"):]
            if k2 in by_path:
                return by_path[k2], "主库相对路径去前缀"
    return None, None


def update_file(path: Path, by_ann, by_jx, by_path):
    rows = []
    hit = miss = 0
    how = {}
    for _, rec in L.iter_jsonl(path):
        found, via = find(rec, by_ann, by_jx, by_path)
        if found:
            rec["原片ID"] = found["原片ID"]
            rec["原片ID说明"] = "已按 T01 原片表通过%s接上" % via
            if not rec.get("标注库ID") and found.get("标注库ID"):
                rec["标注库ID"] = found["标注库ID"]
            if not rec.get("镜序素材ID") and found.get("镜序素材ID"):
                rec["镜序素材ID"] = found["镜序素材ID"]
            hit += 1
            how[via] = how.get(via, 0) + 1
        else:
            rec["原片ID"] = rec.get("原片ID") or None
            rec["原片ID说明"] = "T01 原片表已出现，本条仍未对上原片 ID"
            miss += 1
        rows.append(rec)
    L.write_jsonl(path, rows)
    print(path.name, "hit", hit, "miss", miss, "via", how)
    return {"文件": path.name, "条数": len(rows), "接到原片ID": hit, "未接上": miss, "对接途径": how}


if __name__ == "__main__":
    by_ann, by_jx, by_path = build_index()
    stats = []
    for name in ("事实层.jsonl", "评价与采用.jsonl", "禁用表.jsonl", "线索.jsonl", "粗标层.jsonl"):
        stats.append(update_file(L.CLIPLIB / name, by_ann, by_jx, by_path))
    L.write_json(L.OUT / "统计" / "原片ID对接.json", stats)
    print("DONE")
