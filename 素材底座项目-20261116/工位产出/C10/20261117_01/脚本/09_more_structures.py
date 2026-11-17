from pathlib import Path
import json, csv, collections

raw = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\原始副本")
lib = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
mid = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果")

def brief(obj, n=2000):
    s=json.dumps(obj, ensure_ascii=False)
    return s if len(s)<=n else s[:n]+"..."

# 试标
js=json.loads((raw/"规则"/"试标50段"/"审核结果_李康_20261116.json").read_text(encoding="utf-8"))
print("试标 type", type(js), "len" if not isinstance(js, dict) else "keys", (len(js) if isinstance(js,list) else list(js.keys())[:20]))
if isinstance(js, dict):
    for k,v in js.items():
        if isinstance(v, list):
            print(f"  {k} list {len(v)} first {brief(v[0], 800)}")
        else:
            print(f"  {k} {brief(v, 300)}")
elif isinstance(js, list):
    print("n", len(js), "keys", list(js[0].keys()) if js and isinstance(js[0], dict) else None)
    print(brief(js[0], 1200))

# csv
with (raw/"规则"/"试标50段"/"_对应表.csv").open(encoding="utf-8-sig", newline="") as f:
    rows=list(csv.DictReader(f))
print("\n对应表 n", len(rows), "cols", list(rows[0].keys()) if rows else None)
print(brief(rows[0], 500))
print(brief(rows[1], 500) if len(rows)>1 else "")

# 目视纠正 first 2
print("\n目视纠正")
with (raw/"标注库"/"小区全库"/"数据"/"目视纠正.jsonl").open(encoding="utf-8") as f:
    recs=[json.loads(l) for l in f if l.strip()]
print("n", len(recs), "keys", list(recs[0].keys()))
print(brief(recs[0], 800))

# 本轮看片精标
print("\n本轮看片精标")
with (raw/"标注库"/"小区全库"/"数据"/"本轮看片精标.jsonl").open(encoding="utf-8") as f:
    recs=[json.loads(l) for l in f if l.strip()]
print("n", len(recs), "keys", list(recs[0].keys()))
print(brief(recs[0], 800))

# AI index one record with indexed_segments and 人工确认
print("\n小区索引 sample with 人工确认/indexed_segments")
n=0
n_idx=0
n_human=0
n_tl=0
keys=None
ex_human=None
ex_idx=None
with (raw/"标注库"/"小区全库"/"数据"/"AI剪辑检索索引.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        o=json.loads(line)
        n+=1
        if keys is None:
            keys=list(o.keys())
        tl=o.get("timeline") or []
        n_tl += len(tl) if isinstance(tl, list) else 0
        segs=o.get("indexed_segments") or []
        n_idx += len(segs) if isinstance(segs, list) else 0
        hum=o.get("人工确认片段") or o.get("人工确认") or []
        if isinstance(hum, list):
            n_human += len(hum)
            if hum and ex_human is None:
                ex_human={"id": o.get("id"), "source_path": o.get("source_path") or o.get("path"), "人工确认片段": hum, "keys": list(o.keys())}
        if segs and ex_idx is None:
            ex_idx={"id": o.get("id"), "source_path": o.get("source_path"), "indexed_segments": segs[:1], "timeline0": (tl[:1] if tl else None), "keys": list(o.keys())}
print("小区 n", n, "timeline", n_tl, "indexed_segments", n_idx, "人工确认片段总数", n_human)
print("keys", keys)
print("ex_idx", brief(ex_idx, 1500))
print("ex_human", brief(ex_human, 1500))

# 测试阿明搅拌 counts
print("\n测试阿明搅拌 index")
n=n_idx=n_human=n_tl=0
kinds=collections.Counter()
dirs=collections.Counter()
with (raw/"标注库"/"测试阿明搅拌"/"数据"/"AI剪辑检索索引.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        o=json.loads(line)
        n+=1
        kinds[o.get("kind") or o.get("type") or ""] += 1
        sp=str(o.get("source_path") or o.get("path") or "")
        if "\\测试\\" in sp or "/测试/" in sp or "\\测试/" in sp:
            dirs["测试"]+=1
        elif "\\阿明\\" in sp or "/阿明/" in sp:
            dirs["阿明"]+=1
        elif "\\搅拌\\" in sp or "/搅拌/" in sp:
            dirs["搅拌"]+=1
        else:
            dirs["other:"+sp[:80]]+=1
        tl=o.get("timeline") or []
        n_tl += len(tl) if isinstance(tl,list) else 0
        segs=o.get("indexed_segments") or []
        n_idx += len(segs) if isinstance(segs,list) else 0
        hum=o.get("人工确认片段") or []
        if isinstance(hum,list):
            n_human += len(hum)
print("n", n, "timeline", n_tl, "indexed", n_idx, "human segs", n_human, "kinds", dict(kinds), "dirs", dict(dirs))

# 施工镜头 / 用途 first + counts by dir
print("\n施工镜头")
n=0
dirs=collections.Counter()
with (raw/"标注库"/"微陶泥施工"/"施工镜头.jsonl").open(encoding="utf-8") as f:
    rec=None
    for line in f:
        if not line.strip():
            continue
        o=json.loads(line)
        n+=1
        if rec is None:
            rec=o
        sp=str(o.get("source_path") or o.get("path") or "")
        hit=False
        for d in ["拍摄\\小区","拍摄\\测试","拍摄\\阿明","拍摄\\搅拌","拍摄/小区","拍摄/测试","拍摄/阿明","拍摄/搅拌","扒扒"]:
            if d in sp:
                dirs[d]+=1
                hit=True
                break
        if not hit:
            dirs["other"]+=1
print("n", n, "dirs", dict(dirs), "keys", list(rec.keys()))
print(brief(rec, 800))

print("\n按用途检索")
n=0
cats=collections.Counter()
with (raw/"标注库"/"小区全库"/"数据"/"按用途检索.jsonl").open(encoding="utf-8") as f:
    rec=None
    for line in f:
        if not line.strip():
            continue
        o=json.loads(line)
        n+=1
        if rec is None:
            rec=o
        cats[o.get("category") or o.get("用途") or ""] += 1
print("n", n, "cats", dict(cats), "keys", list(rec.keys()))
print(brief(rec, 800))

# coarse first record full keys
print("\n粗标层 first record")
with (lib/"粗标层.jsonl").open(encoding="utf-8") as f:
    o=json.loads(next(l for l in f if l.strip()))
print("keys", list(o.keys()))
print(brief(o, 2000))

# the one 逐格 with start no end
print("\n逐格 with partial time")
facts=[]
with (lib/"事实层.jsonl").open(encoding="utf-8") as f:
    facts=[json.loads(l) for l in f if l.strip()]
for r in facts:
    if r.get("来源文件")=="出镜文件夹确认图/对照表.md#明细":
        a=r.get("起秒") not in (None,"")
        b=r.get("止秒") not in (None,"")
        if a^b or a or b:
            print(brief(r, 2000))

# 人物身份确认办法 first 40 lines
print("\n===== 人物身份确认办法 =====")
text=(raw/"规则"/"人物身份确认办法.md").read_text(encoding="utf-8")
print(text[:2500])
print("...TOTAL LINES", len(text.splitlines()))
