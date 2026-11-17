# -*- coding: utf-8 -*-
import json, sqlite3
from pathlib import Path
from collections import Counter, defaultdict

OUTDIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
CATALOG = OUTDIR / r"镜序副本\catalog.sqlite3"
LABEL = OUTDIR / "标注库副本"
ANN = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")

conn = sqlite3.connect("file:" + CATALOG.as_posix() + "?mode=ro&immutable=1", uri=True)
cur = conn.cursor()
for root in ["chengdu", "suzhou", "xiaoq", "baba"]:
    rows = cur.execute("SELECT rel FROM assets WHERE root=? LIMIT 3", (root,)).fetchall()
    print("ROOT", root, rows)
conn.close()

# classify 测试阿明搅拌 by path
c=Counter(); n=0; no_tl=0
kinds=Counter()
with (LABEL/r"测试阿明搅拌\数据\AI剪辑检索索引.jsonl").open(encoding="utf-8") as f:
    for line in f:
        o=json.loads(line)
        n+=1
        p=o.get("source_path") or ""
        kinds[o.get("kind")] += 1
        if "\\拍摄\\测试" in p or "/拍摄/测试" in p:
            key="测试"
        elif "\\拍摄\\阿明" in p or "/拍摄/阿明" in p:
            key="阿明"
        elif "\\拍摄\\搅拌" in p or "/拍摄/搅拌" in p:
            key="搅拌"
        else:
            key="其他:"+p[:80]
        c[key]+=1
        if not o.get("timeline"):
            no_tl += 1
print("测试阿明搅拌 dirs", dict(c), "n", n, "no_timeline", no_tl, "kinds", dict(kinds))

# 施工镜头 path dirs
c2=Counter(); n2=0
with (LABEL/r"微陶泥施工\施工镜头.jsonl").open(encoding="utf-8") as f:
    for line in f:
        o=json.loads(line)
        n2+=1
        p=o.get("source_path") or ""
        if "\\拍摄\\小区" in p: k="小区"
        elif "\\拍摄\\测试" in p: k="测试"
        elif "\\拍摄\\阿明" in p: k="阿明"
        elif "\\拍摄\\搅拌" in p: k="搅拌"
        elif "\\扒扒" in p: k="扒扒"
        else: k="其他"
        c2[k]+=1
print("施工镜头 dirs", dict(c2), "n", n2)

# 按用途
c3=Counter(); cat=Counter(); n3=0
with (LABEL/r"小区全库\数据\按用途检索.jsonl").open(encoding="utf-8") as f:
    for line in f:
        o=json.loads(line)
        n3+=1
        cat[o.get("category")]+=1
        p=o.get("path") or ""
        if "\\拍摄\\小区" in p: k="小区"
        elif "\\拍摄\\测试" in p: k="测试"
        elif "\\拍摄\\阿明" in p: k="阿明"
        elif "\\拍摄\\搅拌" in p: k="搅拌"
        elif "\\扒扒" in p: k="扒扒"
        else: k="其他"
        c3[k]+=1
print("用途 dirs", dict(c3), "cat", dict(cat), "n", n3)

# indexed_segments basis
basis=Counter(); nseg=0
for rel in [r"小区全库\数据\AI剪辑检索索引.jsonl", r"测试阿明搅拌\数据\AI剪辑检索索引.jsonl"]:
    with (LABEL/rel).open(encoding="utf-8") as f:
        for line in f:
            o=json.loads(line)
            for s in o.get("indexed_segments") or []:
                nseg+=1
                basis[str(s.get("basis") or "")[:40]] += 1
print("indexed_segments", nseg, "basis", dict(basis))

# 对照表 folders count
text = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116\出镜文件夹确认图\对照表.md").read_text(encoding="utf-8")
rows=0
for line in text.splitlines():
    if line.startswith("| sheet_"):
        rows+=1
print("对照表 sheet rows", rows)

# person-07 keys
p7=json.loads((ANN/"person-07.json").read_text(encoding="utf-8"))
print("person-07 top", list(p7.keys()) if isinstance(p7, dict) else type(p7))
if isinstance(p7, dict) and p7.get("rows"):
    print("person-07 row keys", list(p7["rows"][0].keys()))
    print("V2 source", json.dumps(p7["rows"][1].get("source"), ensure_ascii=False)[:400] if len(p7["rows"])>1 else None)
