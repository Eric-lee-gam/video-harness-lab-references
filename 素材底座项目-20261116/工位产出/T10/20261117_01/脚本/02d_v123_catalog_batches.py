# -*- coding: utf-8 -*-
import json, sqlite3, csv
from pathlib import Path
from collections import Counter, defaultdict

OUTDIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
ANN = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
LEARN = OUTDIR / r"镜序副本\learning.sqlite3"
CATALOG = OUTDIR / r"镜序副本\catalog.sqlite3"
RULES = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116")

conn = sqlite3.connect("file:" + LEARN.as_posix() + "?mode=ro&immutable=1", uri=True)
cur = conn.cursor()
print("=== V1 V2 V3 full ===")
for rid, created, status, reviewer, payload in cur.execute(
    "SELECT id, created, status, reviewer, payload FROM rules WHERE id IN ('confirmed-V1','confirmed-V2','confirmed-V3')"
):
    p = json.loads(payload)
    print("ID", rid, "created", created, "status", status, "reviewer", reviewer)
    print(json.dumps(p, ensure_ascii=False, indent=2, default=str))
    print("---")
conn.close()

print("=== CATALOG ===")
conn = sqlite3.connect("file:" + CATALOG.as_posix() + "?mode=ro&immutable=1", uri=True)
cur = conn.cursor()
tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print("tables", tables)
for t in tables:
    n = cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
    cols = [c[1] for c in cur.execute("PRAGMA table_info(%s)" % t)]
    print("TABLE", t, "n=", n, "cols=", cols)
    row = cur.execute("SELECT * FROM %s LIMIT 1" % t).fetchone()
    if row:
        rec = dict(zip(cols, row))
        # shorten
        for k,v in list(rec.items()):
            if isinstance(v, str) and len(v)>160:
                rec[k] = v[:160] + "..."
        print(" sample", json.dumps(rec, ensure_ascii=False, default=str))
    # useful group by
    for c in cols:
        if c.lower() in ("root", "kind", "type", "status", "ext", "library", "source"):
            print("  group", c, cur.execute("SELECT %s, COUNT(*) FROM %s GROUP BY %s" % (c,t,c)).fetchall())
conn.close()

print("=== BATCHES STATUS ===")
def load(name):
    return json.loads((ANN/name).read_text(encoding="utf-8"))

def summarize(name, data):
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        for k in data.keys() if isinstance(data, dict) else []:
            if isinstance(data[k], list) and data[k] and isinstance(data[k][0], dict):
                rows = data[k]
                print(name, "using", k, "n", len(rows), "top_keys", list(data.keys()))
                break
        else:
            print(name, "NO ROWS keys", list(data.keys()) if isinstance(data, dict) else type(data))
            return
    else:
        print(name, "rows", len(rows), "top_keys", [k for k in data.keys() if k != "rows"] if isinstance(data, dict) else None)
    st = Counter()
    lab = Counter()
    ids = []
    for r in rows:
        st[str(r.get("status"))] += 1
        lab[str(r.get("confirmed_label") or r.get("label") or r.get("suggested_label"))] += 1
        ids.append(r.get("sample_id") or r.get("id"))
    print("  ids", ids)
    print("  status", dict(st), "labels", dict(lab))
    print("  keys", list(rows[0].keys()) if rows else None)

for name in (["batch-01.json","batch-02.json","batch-03.json","batch-04.json"]
             + [f"product-0{i}.json" for i in range(1,9)]
             + ["person-01.json","person-02.json","person-03.json","person-04.json","person-05.json","person-07.json",
                "P24-boundary-proposal.json"]):
    summarize(name, load(name))

print("=== AMING INDEX ===")
aming = load("aming-source-rule-index.json")
if isinstance(aming, dict):
    print("keys", list(aming.keys()))
    for k,v in aming.items():
        if isinstance(v, list):
            print(" ", k, "list", len(v), "itemtype", type(v[0]).__name__ if v else None)
            if v and isinstance(v[0], dict):
                print("    keys", list(v[0].keys()))
                print("    item0", json.dumps(v[0], ensure_ascii=False)[:400])
        elif isinstance(v, dict):
            print(" ", k, "dict", len(v), "sub", list(v.keys())[:15])
            # maybe values are entries
            vs = list(v.values())
            if vs and isinstance(vs[0], dict):
                print("    value keys", list(vs[0].keys()))
                print("    first key", list(v.keys())[0])
                print("    first val", json.dumps(vs[0], ensure_ascii=False)[:400])
        else:
            print(" ", k, type(v).__name__, str(v)[:200])
elif isinstance(aming, list):
    print("list", len(aming))
    if aming:
        print("item0", json.dumps(aming[0], ensure_ascii=False)[:400])

print("=== TRIAL 50 ===")
trial = json.loads((RULES/r"试标50段\审核结果_李康_20261116.json").read_text(encoding="utf-8"))
print("type", type(trial).__name__)
if isinstance(trial, dict):
    print("keys", list(trial.keys()))
    for k,v in trial.items():
        if isinstance(v, list):
            print(" ", k, "n", len(v), "keys", list(v[0].keys()) if v and isinstance(v[0], dict) else None)
            if v:
                print("  item0", json.dumps(v[0], ensure_ascii=False)[:500])
        else:
            print(" ", k, str(v)[:200])
else:
    print("list", len(trial))
    if trial:
        print("keys", list(trial[0].keys()) if isinstance(trial[0], dict) else None)
        print("item0", json.dumps(trial[0], ensure_ascii=False)[:500])
        # status counts
        if isinstance(trial[0], dict):
            print("status", dict(Counter(str(x.get("结果") or x.get("结论") or x.get("status") or x.get("审核结果")) for x in trial)))

with (RULES/r"试标50段\_对应表.csv").open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
print("对应表 n", len(rows), "fields", list(rows[0].keys()) if rows else None)
print("row0", json.dumps(rows[0], ensure_ascii=False)[:400] if rows else None)
