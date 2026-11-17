from pathlib import Path
import json, sys
sys.path.insert(0, r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\脚本")
from c10_common import *

# find coarse record C054766
found=None
with (LIB/"粗标层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        o=json.loads(line)
        if o.get("粗标编号")=="C054766" or o.get("来源条目标识")=="173b9cd3cde8d71936c0:0.0-4.5817":
            if o.get("粗标编号")=="C054766":
                found=o
                break
print("COARSE", json.dumps(found, ensure_ascii=False)[:4000])

# all construction source rows with this id or this key
hits=[]
key="173b9cd3cde8d71936c0:0.0-4.5817"
oid="173b9cd3cde8d71936c0"
for i,o in enumerate(iter_jsonl(RAW/"标注库"/"微陶泥施工"/"施工镜头.jsonl")):
    if o.get("id")==oid or (str(o.get("id"))+":"+str(o.get("start"))+"-"+str(o.get("end")))==key:
        hits.append((i,o))
    # also close times
    if str(o.get("id")).startswith("173b9cd3cde8d71936c0"):
        hits.append((i,o))
print("\nSOURCE HITS", len(hits))
for i,o in hits:
    print("--- line", i, "id", o.get("id"), "start", o.get("start"), "end", o.get("end"), "工序", o.get("工序"))
    print(json.dumps(o, ensure_ascii=False)[:1500])

# maybe id is shorter and many rows share prefix? also search by path+times from coarse
if found:
    path=found.get("主库相对路径")
    st,en=found.get("起秒"), found.get("止秒")
    print("\nSEARCH by path+times", path, st, en)
    n=0
    for i,o in enumerate(iter_jsonl(RAW/"标注库"/"微陶泥施工"/"施工镜头.jsonl")):
        rel=rel_from_any_path(o.get("source_path") or o.get("path") or "")
        if rel and paths_equal(rel, path) and float(o.get("start") or 0)==float(st) and abs(float(o.get("end") or 0)-float(en))<1e-6:
            n+=1
            print("MATCH", i, "id", o.get("id"), "工序", o.get("工序"), "全字段keys", list(o.keys()))
            print(json.dumps(o, ensure_ascii=False)[:2000])
    print("path+time matches", n)
