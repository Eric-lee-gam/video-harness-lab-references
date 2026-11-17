# -*- coding: utf-8 -*-
"""C10 item 6: sample 30 coarse records + recount by four directories."""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c10_common import *

SEED = RANDOM_SEED
ann = RAW / "标注库"

# Build original indexes
# timeline: id:timeline:start-end:index  (from T10 peek: c9533ca4e18976d8:timeline:0.0-5.268:0)
# 施工镜头: id:start-end
# 用途: id:start-end

def num_eq(a, b):
    if a in (None, "") and b in (None, ""):
        return True
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def which_dir(rel_or_unc: str) -> str | None:
    s = norm_path(rel_or_unc)
    mapping = [
        (r"拍摄\小区", "小区"),
        (r"拍摄\测试", "测试"),
        (r"拍摄\阿明", "阿明"),
        (r"拍摄\搅拌", "搅拌"),
        (r"\扒扒", "扒扒"),
        (r"拍摄\扒扒", "扒扒"),
    ]
    # check more specific first already ordered
    for needle, name in mapping:
        if needle in s:
            return name
    return None


# Load originals into lookup dicts (values: parent, item, kind)
timeline_idx = {}  # key string and tuple
construction_idx = {}
usage_idx = {}
# also count by dir at source
src_counts = {
    "小区全库/数据/AI剪辑检索索引.jsonl#timeline": Counter(),
    "测试阿明搅拌/数据/AI剪辑检索索引.jsonl#timeline": Counter(),
    "微陶泥施工/施工镜头.jsonl": Counter(),
    "小区全库/数据/按用途检索.jsonl": Counter(),
}
src_rows = {
    "小区全库/数据/AI剪辑检索索引.jsonl#timeline": 0,
    "测试阿明搅拌/数据/AI剪辑检索索引.jsonl#timeline": 0,
    "微陶泥施工/施工镜头.jsonl": 0,
    "小区全库/数据/按用途检索.jsonl": 0,
}

def add_timeline(path, src_name):
    n = 0
    for o in iter_jsonl(path):
        rel = rel_from_any_path(o.get("source_path") or o.get("path") or "")
        d = which_dir(rel or o.get("source_path") or "")
        for i, tl in enumerate(o.get("timeline") or []):
            n += 1
            src_counts[src_name][d] += 1
            st, en = tl.get("start"), tl.get("end")
            key = f"{o.get('id')}:timeline:{st}-{en}:{i}"
            rec = {"parent": o, "item": tl, "dir": d, "rel": rel, "key": key}
            timeline_idx[key] = rec
            timeline_idx[(o.get("id"), "timeline", st, en, i)] = rec
    src_rows[src_name] = n
    return n

add_timeline(ann / "小区全库" / "数据" / "AI剪辑检索索引.jsonl", "小区全库/数据/AI剪辑检索索引.jsonl#timeline")
add_timeline(ann / "测试阿明搅拌" / "数据" / "AI剪辑检索索引.jsonl", "测试阿明搅拌/数据/AI剪辑检索索引.jsonl#timeline")

n = 0
for o in iter_jsonl(ann / "微陶泥施工" / "施工镜头.jsonl"):
    n += 1
    rel = rel_from_any_path(o.get("source_path") or o.get("path") or "")
    d = which_dir(rel or o.get("source_path") or "")
    src_counts["微陶泥施工/施工镜头.jsonl"][d] += 1
    st, en = o.get("start"), o.get("end")
    key = f"{o.get('id')}:{st}-{en}"
    rec = {"parent": None, "item": o, "dir": d, "rel": rel, "key": key}
    construction_idx.setdefault(key, []).append(rec)
    construction_idx.setdefault((o.get("id"), st, en), []).append(rec)
src_rows["微陶泥施工/施工镜头.jsonl"] = n

n = 0
for o in iter_jsonl(ann / "小区全库" / "数据" / "按用途检索.jsonl"):
    n += 1
    rel = rel_from_any_path(o.get("path") or o.get("source_path") or "")
    d = which_dir(rel or o.get("path") or "")
    src_counts["小区全库/数据/按用途检索.jsonl"][d] += 1
    st, en = o.get("start"), o.get("end")
    key = f"{o.get('id')}:{st}-{en}"
    rec = {"parent": None, "item": o, "dir": d, "rel": rel, "key": key}
    usage_idx[key] = rec
    usage_idx[(o.get("id"), st, en)] = rec
src_rows["小区全库/数据/按用途检索.jsonl"] = n

# Count coarse layer (stream, don't keep all)
coarse_by_src = Counter()
coarse_by_dir = Counter()
coarse_n = 0
# For sampling we need random 30 from 65971 without loading all if possible.
# Reservoir or load identifiers only, or load all dicts - 112MB file may be ~66000 * ~1.7KB = ok in memory actually T10 said 112MB file. Loading all JSON objects might use more RAM (maybe 400MB). Should be fine.

# To sample fairly, collect line offsets or load all. We'll load all 原字段 comparisons only for 30 samples, so we can first collect list of (idx, 来源, 标识, 目录) then sample, then re-read those lines... simpler to reservoir sample 30 full records while counting.

rng = random.Random(SEED)
sample = []  # reservoir
with (LIB / "粗标层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        o = json.loads(line)
        coarse_n += 1
        coarse_by_src[o.get("来源文件")] += 1
        coarse_by_dir[o.get("目录")] += 1
        # reservoir sampling
        if len(sample) < 30:
            sample.append(o)
        else:
            j = rng.randint(0, coarse_n - 1)
            if j < 30:
                sample[j] = o

# WARNING: reservoir with randint as above uses changing rng state during the scan, then we'd have a sample, but the report should record the algorithm.
# For reproducibility, better: use seed to choose 30 indices first, but we don't know n until scanned.
# We already know n=65971 from item 1. Use rng.sample(range(65971), 30) instead for a clean, documented sample.
# I'll re-sample properly with known n.

n_expected = coarse_n
rng2 = random.Random(SEED)
indices = sorted(rng2.sample(range(n_expected), 30))
index_set = set(indices)
sample = []
i = 0
with (LIB / "粗标层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        if i in index_set:
            sample.append((i, json.loads(line)))
        i += 1
        if len(sample) == 30:
            break
# keep order of indices
sample.sort(key=lambda x: x[0])

PATH_KEYS = {"source_path", "path", "preview", "preview_path", "rel", "evidence"}

def lookup(rec):
    src = rec.get("来源文件") or ""
    sid = rec.get("来源条目标识")
    if "AI剪辑检索索引.jsonl#timeline" in src:
        return "timeline", timeline_idx.get(sid)
    if src.endswith("施工镜头.jsonl"):
        hit = construction_idx.get(sid) or []
        return "construction", hit
    if src.endswith("按用途检索.jsonl"):
        return "usage", usage_idx.get(sid)
    return "unknown", None


def compare_record(rec):
    issues = []
    kind, hit = lookup(rec)
    if not hit:
        return False, [{"reason": "原始行找不到", "来源文件": rec.get("来源文件"), "来源条目标识": rec.get("来源条目标识")}], kind
    # construction keys may point to several source rows (same id+times, different 工序)
    candidates = hit if isinstance(hit, list) else [hit]
    # prefer exact 原字段 match
    orig = rec.get("原字段") or {}
    chosen = None
    for h in candidates:
        if orig and h["item"] == orig:
            chosen = h
            break
    if chosen is None:
        chosen = candidates[0]
    hit = chosen
    item = hit["item"]
    parent = hit["parent"]
    # times
    st = item.get("start")
    en = item.get("end")
    if not num_eq(rec.get("起秒"), st) or not num_eq(rec.get("止秒"), en):
        issues.append({"field": "起止秒", "src": [st, en], "out": [rec.get("起秒"), rec.get("止秒")]})
    # path
    src_path = None
    if parent:
        src_path = parent.get("source_path") or parent.get("path")
    src_path = item.get("source_path") or item.get("path") or src_path
    rel = rel_from_any_path(src_path) if src_path else hit.get("rel")
    if rel and not paths_equal(rel, rec.get("主库相对路径")):
        issues.append({"field": "主库相对路径", "src": rel, "out": rec.get("主库相对路径")})
    # 原字段 should match item (plus maybe inherited fields)
    orig = rec.get("原字段") or {}
    # compare overlapping keys in item vs 原字段
    for k, val in item.items():
        if k in PATH_KEYS:
            # path compare loosely if present
            if k in orig and orig.get(k) != val and not paths_equal(str(orig.get(k)), str(val)):
                issues.append({"field": f"原字段.{k}", "src": val, "out": orig.get(k)})
            continue
        if k in orig:
            if orig.get(k) != val:
                # allow numeric eq
                if not num_eq(orig.get(k), val):
                    issues.append({"field": f"原字段.{k}", "src": val, "out": orig.get(k)})
        # not requiring every key to be copied if 原字段 is a subset? C10 says 核对字段值 — missing keys are issues if value is meaningful
        elif val not in (None, "", [], {}):
            issues.append({"field": f"原字段缺 {k}", "src": val if not isinstance(val, (list, dict)) else k})
    if rec.get("标注库ID") and item.get("id") and rec.get("标注库ID") != item.get("id") and (not parent or rec.get("标注库ID") != parent.get("id")):
        issues.append({"field": "标注库ID", "src": item.get("id") or (parent or {}).get("id"), "out": rec.get("标注库ID")})
    # directory
    if hit.get("dir") and rec.get("目录") and hit["dir"] != rec.get("目录") and not (hit["dir"]=="扒扒" and rec.get("范围")=="范围外"):
        # 扒扒 may be labeled 扒扒
        if rec.get("目录") != hit["dir"]:
            issues.append({"field": "目录", "src": hit["dir"], "out": rec.get("目录")})
    return len(issues)==0, issues, kind

results = []
for idx, rec in sample:
    ok, issues, kind = compare_record(rec)
    results.append({
        "index": idx,
        "粗标编号": rec.get("粗标编号"),
        "来源文件": rec.get("来源文件"),
        "来源条目标识": rec.get("来源条目标识"),
        "目录": rec.get("目录"),
        "范围": rec.get("范围"),
        "主库相对路径": rec.get("主库相对路径"),
        "起秒": rec.get("起秒"),
        "止秒": rec.get("止秒"),
        "ok": ok,
        "kind": kind,
        "issues": issues,
    })

failed = [r for r in results if not r["ok"]]

# compare counts
# Coarse by dir vs source by dir (sum over files)
src_dir_total = Counter()
for src, c in src_counts.items():
    src_dir_total.update(c)

# Explain diffs if any
count_cmp = []
for d in ["小区", "测试", "阿明", "搅拌", "扒扒", None]:
    count_cmp.append({
        "目录": d,
        "原始合计": src_dir_total.get(d, 0),
        "粗标层": coarse_by_dir.get(d, 0),
        "equal": src_dir_total.get(d, 0) == coarse_by_dir.get(d, 0),
    })
# leftover dirs
for d in set(list(src_dir_total) + list(coarse_by_dir)):
    if d not in ["小区", "测试", "阿明", "搅拌", "扒扒", None]:
        count_cmp.append({
            "目录": d,
            "原始合计": src_dir_total.get(d, 0),
            "粗标层": coarse_by_dir.get(d, 0),
            "equal": src_dir_total.get(d, 0) == coarse_by_dir.get(d, 0),
        })

src_file_cmp = []
for src, n in src_rows.items():
    src_file_cmp.append({
        "来源文件": src,
        "原始条数": n,
        "粗标层": coarse_by_src.get(src, 0),
        "equal": n == coarse_by_src.get(src, 0),
        "原始分目录": dict(src_counts[src]),
    })

pass_30 = len(failed)==0
pass_counts = all(x["equal"] for x in src_file_cmp)
# dir diffs must be explained in T10 report if any
unexplained = [x for x in count_cmp if not x["equal"]]
# If only None vs something, investigate

result = {
    "item": 6,
    "seed": SEED,
    "sample_method": "random.Random(26111710).sample(range(粗标层条数), 30)，按行号抽取",
    "coarse_n": coarse_n,
    "sample_n": 30,
    "sample_indices": [r["index"] for r in results],
    "sample_粗标编号": [r["粗标编号"] for r in results],
    "sample_pass": pass_30,
    "failed_n": len(failed),
    "failed_ids": [r["粗标编号"] for r in failed],
    "results": results,
    "source_file_counts": src_file_cmp,
    "dir_counts": count_cmp,
    "coarse_by_src": dict(coarse_by_src),
    "coarse_by_dir": dict(coarse_by_dir),
    "src_dir_total": dict(src_dir_total),
    "count_pass": pass_counts and not unexplained,
    "unexplained_dir_diffs": unexplained,
    "pass": pass_30 and pass_counts and not unexplained,
}
dump_json(MID / "item6_coarse.json", result)
print("ITEM6 pass", result["pass"], "sample_pass", pass_30, "count_pass", result["count_pass"], "failed", result["failed_ids"])
print("coarse_n", coarse_n, "by dir", dict(coarse_by_dir))
print("src dir", dict(src_dir_total))
print("file cmp", json.dumps(src_file_cmp, ensure_ascii=False)[:2000])
if unexplained:
    print("DIR DIFF", unexplained)
for r in results:
    print(("OK  " if r["ok"] else "FAIL"), r["粗标编号"], r["kind"], r["来源条目标识"], "issues", r["issues"][:2] if r["issues"] else [])
