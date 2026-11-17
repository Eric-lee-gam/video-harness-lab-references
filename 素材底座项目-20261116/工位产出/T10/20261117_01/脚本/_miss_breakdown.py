# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库\事实层.jsonl")
c_range=Counter(); c_level=Counter(); c_src=Counter(); n=0
examples=[]
for line in p.open(encoding="utf-8"):
    r=json.loads(line)
    if r.get("原片ID"):
        continue
    n+=1
    c_range[r.get("范围") or ""] += 1
    c_level[r.get("确认级别") or ""] += 1
    src=(r.get("来源文件") or "")[:40]
    c_src[src]+=1
    if len(examples)<15:
        examples.append((r.get("事实编号"), r.get("确认级别"), r.get("范围"), r.get("目录"), r.get("主库相对路径"), r.get("来源条目标识")))
print("miss", n, "range", dict(c_range), "level", dict(c_level))
print("src", dict(c_src))
for e in examples:
    print(e)

# eval misses
p2=Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库\评价与采用.jsonl")
er=Counter(); n2=0
for line in p2.open(encoding="utf-8"):
    r=json.loads(line)
    if r.get("原片ID"):
        continue
    n2+=1
    er[r.get("范围") or ""] += 1
    er["类型:"+str(r.get("类型"))] += 1
print("eval miss", n2, dict(er))
