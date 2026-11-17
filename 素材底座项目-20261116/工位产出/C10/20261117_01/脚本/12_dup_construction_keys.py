from pathlib import Path
import json, sys
from collections import Counter, defaultdict
sys.path.insert(0, r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\脚本")
from c10_common import *

# source key uniqueness in 施工镜头
src_keys = defaultdict(list)
for i,o in enumerate(iter_jsonl(RAW/"标注库"/"微陶泥施工"/"施工镜头.jsonl")):
    key=f"{o.get('id')}:{o.get('start')}-{o.get('end')}"
    src_keys[key].append({"line": i, "工序": o.get("工序"), "画面": o.get("画面"), "证据": o.get("证据")})

dups={k:v for k,v in src_keys.items() if len(v)>1}
print("construction rows", sum(len(v) for v in src_keys.values()), "unique keys", len(src_keys), "dup keys", len(dups))
# how many extra rows
extra=sum(len(v)-1 for v in dups.values())
print("extra rows due to dups", extra)

# 用途 and timeline uniqueness too?
# check a few dup patterns
proc_same=0
proc_diff=0
for k,v in dups.items():
    procs=set(x["工序"] for x in v)
    if len(procs)==1:
        proc_same+=1
    else:
        proc_diff+=1
print("dup keys same 工序", proc_same, "diff 工序", proc_diff)

# coarse records with this key and generally dup keys
want=set(dups)
coarse_for_dups=defaultdict(list)
# also usage keys
with (LIB/"粗标层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        o=json.loads(line)
        if o.get("来源文件","").endswith("施工镜头.jsonl") and o.get("来源条目标识") in want:
            coarse_for_dups[o.get("来源条目标识")].append({
                "粗标编号": o.get("粗标编号"),
                "工序": (o.get("原字段") or {}).get("工序"),
                "画面": (o.get("原字段") or {}).get("画面"),
            })

print("dup keys that appear in coarse", len(coarse_for_dups))
# compare counts
missing_pair=0
count_mismatch=[]
for k,v in dups.items():
    cout=coarse_for_dups.get(k, [])
    if len(cout)!=len(v):
        count_mismatch.append((k, len(v), len(cout), [x["工序"] for x in v], [x["工序"] for x in cout]))
print("keys with src/out count mismatch", len(count_mismatch))
if count_mismatch[:8]:
    for row in count_mismatch[:8]:
        print(" mismatch", row)

# specifically our key
k="173b9cd3cde8d71936c0:0.0-4.5817"
print("\nOUR KEY src", dups.get(k))
print("OUR KEY coarse", coarse_for_dups.get(k))

# 工序 sets match?
proc_mismatch=[]
for k,v in dups.items():
    src_p=sorted(x["工序"] or "" for x in v)
    out_p=sorted(x["工序"] or "" for x in coarse_for_dups.get(k, []))
    if src_p!=out_p:
        proc_mismatch.append((k, src_p, out_p))
print("工序 multiset mismatch among dups", len(proc_mismatch))
if proc_mismatch[:5]:
    print(proc_mismatch[:5])
