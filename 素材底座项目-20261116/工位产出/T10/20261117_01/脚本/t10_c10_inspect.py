# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter, defaultdict

CLIP = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
facts = CLIP / "事实层.jsonl"
coarse = CLIP / "粗标层.jsonl"

def load_jsonl(p):
    rows = []
    with p.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                rows.append((i, json.loads(line)))
    return rows

print("=== 1. 片段级且起止不完整 ===")
inc = []
for i, r in load_jsonl(facts):
    if r.get("确认级别") != "片段级":
        continue
    start, end = r.get("起秒"), r.get("止秒")
    complete = start is not None and end is not None and start != "" and end != ""
    if not complete:
        inc.append((i, r))
print("count", len(inc))
by_src = Counter()
has_flag = Counter()
start_end = Counter()
for i, r in inc:
    src = r.get("来源文件") or ""
    by_src[src] += 1
    flag = "无起止秒" in r or r.get("无起止秒") is True or r.get("无起止秒") is False
    has_flag[str(r.get("无起止秒"))] += 1
    start_end[(r.get("起秒"), r.get("止秒"))] += 1
print("by_src", dict(by_src))
print("无起止秒 field values", dict(has_flag))
print("start,end combos", list(start_end.items())[:20], "ncombos", len(start_end))

# F0191
for i, r in inc:
    if r.get("事实编号") == "F0191" or "17881" in str(r.get("主库相对路径") or "") or "17881" in str(r.get("来源条目标识") or ""):
        print("F0191-like", r.get("事实编号"), r.get("来源条目标识"), "start", r.get("起秒"), "end", r.get("止秒"), "无起止秒", r.get("无起止秒"), "确认级别", r.get("确认级别"))
        print("  限定语", (r.get("限定语原文") or "")[:200])

print("\n=== F0018 / P3 ===")
for i, r in load_jsonl(facts):
    if r.get("事实编号") == "F0018" or r.get("来源条目标识") in ("confirmed-P3", "P3"):
        print("id", r.get("事实编号"), "src", r.get("来源条目标识"), "是否反例", r.get("是否反例"))
        c = r.get("内容") or {}
        if isinstance(c, dict):
            print("  product_identity", c.get("product_identity"))
            print("  description", c.get("description"))
            print("  confirmed_action", c.get("confirmed_action"))

print("\n=== 2. 施工镜头 来源条目标识 撞键 ===")
keys = defaultdict(list)
n_cons = 0
for i, r in load_jsonl(coarse):
    if r.get("记录种类") != "施工镜头" and "施工镜头" not in str(r.get("来源文件") or ""):
        continue
    n_cons += 1
    keys[r.get("来源条目标识")].append((i, r.get("粗标编号"), (r.get("原字段") or {}).get("工序"), r.get("起秒"), r.get("止秒")))
dups = {k: v for k, v in keys.items() if len(v) > 1}
print("施工镜头条数", n_cons, "unique keys", len(keys), "dup groups", len(dups), "extra rows", sum(len(v)-1 for v in dups.values()))
# how many dups differ by 工序
diff_proc = 0
same_proc = 0
for k, v in dups.items():
    procs = {x[2] for x in v}
    if len(procs) > 1:
        diff_proc += 1
    else:
        same_proc += 1
print("dup groups 工序不同", diff_proc, "工序相同", same_proc)
# show a few
for k, v in list(dups.items())[:5]:
    print(" key", k, "n", len(v), [(x[1], x[2], x[3], x[4]) for x in v])

# also check if non-施工 keys collide
all_keys = defaultdict(int)
for i, r in load_jsonl(coarse):
    all_keys[r.get("来源条目标识")] += 1
all_dups = sum(1 for k,n in all_keys.items() if n>1)
print("coarse all-type dup keys", all_dups)
