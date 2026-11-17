# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库\原片表.jsonl")
keys=Counter(); n=0; first=None
id_names=Counter()
for line in p.open(encoding="utf-8"):
    if not line.strip():
        continue
    o=json.loads(line)
    n+=1
    keys.update(o.keys())
    if first is None:
        first=o
print("n", n, "keys", dict(keys))
# print first with short values
t={}
for k,v in first.items():
    if isinstance(v,str) and len(v)>180:
        t[k]=v[:180]+"..."
    else:
        t[k]=v
print(json.dumps(t, ensure_ascii=False, indent=2, default=str))
