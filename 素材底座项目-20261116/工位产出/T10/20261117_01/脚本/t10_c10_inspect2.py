# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import defaultdict, Counter

CLIP = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
LABEL = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\标注库副本")

# 3 same-process dup groups
keys = defaultdict(list)
with (CLIP / "粗标层.jsonl").open(encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("记录种类") != "施工镜头":
            continue
        keys[r.get("来源条目标识")].append((i, r.get("粗标编号"), r.get("原字段") or {}))

print("=== same 工序 dup groups ===")
n_same = 0
for k, v in keys.items():
    if len(v) <= 1:
        continue
    procs = [x[2].get("工序") for x in v]
    if len(set(procs)) == 1:
        n_same += 1
        print("KEY", k, "n", len(v), "工序", procs[0])
        for x in v:
            fields = x[2]
            print(" ", x[1], "keys", list(fields.keys()))
            # print distinguishing fields
            brief = {a: fields.get(a) for a in ("工序", "画面", "状态", "材料依据", "材料类目", "可按微陶泥选用", "证据", "id", "start", "end")}
            print("  ", json.dumps(brief, ensure_ascii=False)[:400])

# other non-施工 dup keys
print("\n=== non-施工撞键（仅观察，不改）===")
allk = defaultdict(list)
with (CLIP / "粗标层.jsonl").open(encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if not line.strip():
            continue
        r = json.loads(line)
        allk[r.get("来源条目标识")].append((r.get("记录种类"), r.get("来源文件"), r.get("粗标编号")))
for k, v in allk.items():
    kinds = {x[0] for x in v}
    if len(v) > 1 and "施工镜头" not in kinds:
        print(k, len(v), v[:4])

# similar 是否反例 mismatches in 事实层 (observe only)
print("\n=== 事实层 是否反例 vs 原文含「不是微陶泥/反例」等（仅观察）===")
hints = ("反例", "不是微陶泥", "本片段不是微陶泥", "非微陶泥", "不是阿明")
n = 0
for line in (CLIP / "事实层.jsonl").open(encoding="utf-8"):
    r = json.loads(line)
    blob = json.dumps(r.get("内容"), ensure_ascii=False) + " " + str(r.get("限定语原文") or "")
    hit = [h for h in hints if h in blob]
    flag = r.get("是否反例")
    if hit and not flag:
        n += 1
        print(r.get("事实编号"), r.get("来源条目标识"), "是否反例=", flag, "hits", hit, "product", (r.get("内容") or {}).get("product_identity") if isinstance(r.get("内容"), dict) else None)
print("mismatch count", n)

# source 施工镜头 line count
src = LABEL / "微陶泥施工" / "施工镜头.jsonl"
print("\nsource exists", src.exists(), "lines", sum(1 for line in src.open(encoding="utf-8") if line.strip()) if src.exists() else 0)
