from pathlib import Path
import json

# reprint just the truncated middle by re-reading 09 output? easier re-print targeted saved pieces
lib = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
raw = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\原始副本")

with (lib/"粗标层.jsonl").open(encoding="utf-8") as f:
    o=json.loads(next(l for l in f if l.strip()))
print("COARSE KEYS", list(o.keys()))
for k,v in o.items():
    s=json.dumps(v, ensure_ascii=False)
    if len(s)>300: s=s[:300]+"..."
    print(f"  {k}: {s}")

# 2nd and a 施工镜头 / 用途 type if we can find by 来源文件 in first 200
print("\n--- other coarse source types in first 5000 ---")
from collections import Counter
c=Counter(); seen={}
n=0
with (lib/"粗标层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        n+=1
        o=json.loads(line)
        src=o.get("来源文件")
        c[src]+=1
        if src not in seen:
            seen[src]=o
        if len(seen)>=8 and n>5000:
            # still need full count of sources - do later in item6
            pass
        if n>=20000 and len(seen)>=6:
            break
print("partial n", n, "sources seen", dict(c))
for src,o in seen.items():
    print(f"\nSRC {src} keys={list(o.keys())} 目录={o.get('目录')} 范围={o.get('范围')}")
    print("  来源条目标识", o.get("来源条目标识"), "起止", o.get("起秒"), o.get("止秒"), "主库", o.get("主库相对路径"))

# 逐格 partial
print("\n===== 逐格 partial time =====")
with (lib/"事实层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        r=json.loads(line)
        if r.get("来源文件")=="出镜文件夹确认图/对照表.md#明细":
            a=r.get("起秒") not in (None,"")
            b=r.get("止秒") not in (None,"")
            if a or b:
                print(json.dumps({k:r.get(k) for k in ["事实编号","来源条目标识","主库相对路径","起秒","止秒","无起止秒","内容","限定语原文","注意"]}, ensure_ascii=False)[:3000])

# 办法 first 55 lines
text=(raw/"规则"/"人物身份确认办法.md").read_text(encoding="utf-8")
print("\n===== 办法 head =====")
print("\n".join(text.splitlines()[:55]))
