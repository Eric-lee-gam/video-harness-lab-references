from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\脚本\c10_item6_coarse.py")
t = p.read_text(encoding="utf-8")
# Change construction_idx values to lists
old = '''    rec = {"parent": None, "item": o, "dir": d, "rel": rel, "key": key}
    construction_idx[key] = rec
    construction_idx[(o.get("id"), st, en)] = rec
'''
new = '''    rec = {"parent": None, "item": o, "dir": d, "rel": rel, "key": key}
    construction_idx.setdefault(key, []).append(rec)
    construction_idx.setdefault((o.get("id"), st, en), []).append(rec)
'''
if old not in t:
    raise SystemExit("block1 not found")
t = t.replace(old, new, 1)

old2 = '''    if src.endswith("施工镜头.jsonl"):
        hit = construction_idx.get(sid)
        if not hit:
            # try tuple
            pass
        return "construction", hit
'''
new2 = '''    if src.endswith("施工镜头.jsonl"):
        hit = construction_idx.get(sid) or []
        return "construction", hit
'''
if old2 not in t:
    raise SystemExit("block2 not found")
t = t.replace(old2, new2, 1)

old3 = '''def compare_record(rec):
    issues = []
    kind, hit = lookup(rec)
    if not hit:
        return False, [{"reason": "原始行找不到", "来源文件": rec.get("来源文件"), "来源条目标识": rec.get("来源条目标识")}], kind
    item = hit["item"]
    parent = hit["parent"]
'''
new3 = '''def compare_record(rec):
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
'''
if old3 not in t:
    raise SystemExit("block3 not found")
t = t.replace(old3, new3, 1)

# add note about dups in result dict - optional, I'll add after rerun via a small merge
p.write_text(t, encoding="utf-8")
print("patched")
