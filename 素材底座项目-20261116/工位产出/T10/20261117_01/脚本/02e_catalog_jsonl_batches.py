# -*- coding: utf-8 -*-
import json, sqlite3
from pathlib import Path
from collections import Counter, defaultdict

OUTDIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
ANN = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
CATALOG = OUTDIR / r"镜序副本\catalog.sqlite3"
LABEL = OUTDIR / "标注库副本"

print("=== CATALOG assets roots / available ===")
conn = sqlite3.connect("file:" + CATALOG.as_posix() + "?mode=ro&immutable=1", uri=True)
cur = conn.cursor()
print("root", cur.execute("SELECT root, COUNT(*) FROM assets GROUP BY root").fetchall())
print("available", cur.execute("SELECT available, COUNT(*) FROM assets GROUP BY available").fetchall())
row = cur.execute("SELECT id, root, rel, name, size, stamp, meta, error, available FROM assets LIMIT 1").fetchone()
cols = ["id","root","rel","name","size","stamp","meta","error","available"]
rec = dict(zip(cols, row))
print("sample asset", json.dumps({k:(v[:200]+"..." if isinstance(v,str) and len(v)>200 else v) for k,v in rec.items()}, ensure_ascii=False, default=str))
# meta parse
if rec.get("meta"):
    try:
        meta = json.loads(rec["meta"])
        print("meta keys", list(meta.keys()) if isinstance(meta, dict) else type(meta))
        print("meta", json.dumps(meta, ensure_ascii=False, default=str)[:500])
    except Exception as e:
        print("meta parse fail", e)
# look for path in meta or construct
# sample a few roots
for root, in cur.execute("SELECT DISTINCT root FROM assets"):
    r = cur.execute("SELECT id, rel, name FROM assets WHERE root=? LIMIT 2", (root,)).fetchall()
    print("root", root, "examples", r)

print("other tables counts/sample already needed? clips/projects")
for t in ["clips","projects","categories"]:
    n=cur.execute("SELECT COUNT(*) FROM %s"%t).fetchone()[0]
    cols=[c[1] for c in cur.execute("PRAGMA table_info(%s)"%t)]
    print(t, n, cols)
    row=cur.execute("SELECT * FROM %s LIMIT 1"%t).fetchone()
    if row:
        rec=dict(zip(cols,row))
        print(" ", json.dumps({k:(v[:160]+"..." if isinstance(v,str) and len(v)>160 else v) for k,v in rec.items()}, ensure_ascii=False, default=str))
conn.close()

print("\n=== BATCH compact counts only ===")
for name in (["batch-01.json","batch-02.json","batch-03.json","batch-04.json"]
             + [f"product-0{i}.json" for i in range(1,9)]
             + ["person-01.json","person-02.json","person-03.json","person-04.json","person-05.json","person-07.json",
                "P24-boundary-proposal.json"]):
    data = json.loads((ANN/name).read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        print(name, "NO rows", list(data.keys()) if isinstance(data, dict) else type(data))
        continue
    st = Counter(str(r.get("status")) for r in rows)
    lab = Counter(str(r.get("confirmed_label") or r.get("label") or "") for r in rows)
    ids = [r.get("sample_id") or r.get("id") for r in rows]
    print("%s n=%d status=%s labels=%s ids=%s keys=%s" % (name, len(rows), dict(st), dict(lab), ids, list(rows[0].keys()) if rows else None))

print("\n=== JSONL field tree ===")

def inspect_jsonl(path, limit_dirs=8):
    path = Path(path)
    n=0
    keys=Counter()
    list_lens=defaultdict(list)
    dir_vals=Counter()
    sample_paths=[]
    codes=Counter()
    first=None
    with path.open(encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            o=json.loads(line)
            n+=1
            if not isinstance(o, dict):
                continue
            keys.update(o.keys())
            if first is None:
                first=o
            for fk in ("目录","所属目录","folder","rel","relpath","path","相对路径","主库路径","逻辑路径","source","src","file","文件","原片","路径"):
                if fk in o and isinstance(o[fk], str) and o[fk]:
                    if len(sample_paths)<3:
                        sample_paths.append((fk, o[fk]))
            if "code" in o:
                codes[str(o["code"])]+=1
            for k,v in o.items():
                if isinstance(v, list):
                    list_lens[k].append(len(v))
    print("FILE", path.name, "n", n)
    print("  keys", dict(keys))
    for k, lens in list_lens.items():
        print("  list", k, "filled", len(lens), "sum", sum(lens), "avg", round(sum(lens)/len(lens),2) if lens else 0, "minmax", (min(lens), max(lens)) if lens else None)
    if codes:
        print("  code", dict(codes))
    print("  sample_paths", sample_paths)
    # compact first record: types and list item keys
    if first:
        desc={}
        for k,v in first.items():
            if isinstance(v, list):
                if v and isinstance(v[0], dict):
                    desc[k]={"list":len(v),"item_keys":list(v[0].keys()),"item0_short":{ik:(iv[:80] if isinstance(iv,str) and len(iv)>80 else iv) for ik,iv in v[0].items()}}
                else:
                    desc[k]={"list":len(v),"first":v[0] if v else None}
            elif isinstance(v, dict):
                desc[k]={"dict_keys":list(v.keys()), "val":{ik:(iv[:80] if isinstance(iv,str) and len(iv)>80 else iv) for ik,iv in v.items()}}
            elif isinstance(v, str) and len(v)>160:
                desc[k]=v[:160]+"..."
            else:
                desc[k]=v
        print("  first", json.dumps(desc, ensure_ascii=False, default=str)[:2000])
    return n

for rel in [
    r"小区全库\数据\AI剪辑检索索引.jsonl",
    r"测试阿明搅拌\数据\AI剪辑检索索引.jsonl",
    r"微陶泥施工\施工镜头.jsonl",
    r"小区全库\数据\按用途检索.jsonl",
    r"小区全库\数据\本轮看片精标.jsonl",
    r"小区全库\数据\机器片段复核.jsonl",
    r"小区全库\数据\目视纠正.jsonl",
]:
    inspect_jsonl(LABEL/rel)
