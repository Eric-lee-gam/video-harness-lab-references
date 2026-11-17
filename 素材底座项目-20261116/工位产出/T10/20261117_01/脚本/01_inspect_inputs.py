# -*- coding: utf-8 -*-
import json
import sqlite3
import csv
from pathlib import Path
from collections import Counter, defaultdict

OUT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
ANN = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
LEARN = OUT / r"镜序副本\learning.sqlite3"
CATALOG = OUT / r"镜序副本\catalog.sqlite3"
LABEL = OUT / "标注库副本"
RULES = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116")
report = []

def p(*a):
    line = " ".join(str(x) for x in a)
    report.append(line)
    print(line)

def ro(path: Path):
    uri = "file:" + path.as_posix() + "?mode=ro&immutable=1"
    return sqlite3.connect(uri, uri=True)

def schema(conn, name):
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    p(f"\n## SQLite {name} tables: {tables}")
    for t in tables:
        cols = list(cur.execute(f"PRAGMA table_info({t})"))
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        p(f"### {t} rows={n}")
        p("  cols:", [(c[1], c[2]) for c in cols])
        # sample 1
        row = cur.execute(f"SELECT * FROM {t} LIMIT 1").fetchone()
        if row:
            colnames = [c[1] for c in cols]
            sample = {}
            for k, v in zip(colnames, row):
                s = v if not isinstance(v, str) or len(v) < 400 else v[:400] + "..."
                sample[k] = s
            p("  sample:", json.dumps(sample, ensure_ascii=False, default=str)[:2000])

def json_summary(path: Path, title=None):
    title = title or path.name
    data = json.loads(path.read_text(encoding="utf-8"))
    p(f"\n## JSON {title}")
    p("  type:", type(data).__name__, "size_bytes=", path.stat().st_size)
    if isinstance(data, dict):
        p("  keys:", list(data.keys()))
        for k, v in data.items():
            if isinstance(v, list):
                p(f"  {k}: list len={len(v)}")
                if v:
                    p("    item0 keys:" if isinstance(v[0], dict) else "    item0 type:", type(v[0]).__name__)
                    if isinstance(v[0], dict):
                        p("    item0 keys:", list(v[0].keys()))
                        p("    item0:", json.dumps(v[0], ensure_ascii=False, default=str)[:1500])
            elif isinstance(v, dict):
                p(f"  {k}: dict keys={list(v.keys())[:30]} n={len(v)}")
            else:
                s = v if not isinstance(v, str) or len(v) < 300 else v[:300]
                p(f"  {k}: {s!r}")
    elif isinstance(data, list):
        p("  list len=", len(data))
        if data and isinstance(data[0], dict):
            p("  item0 keys:", list(data[0].keys()))
            p("  item0:", json.dumps(data[0], ensure_ascii=False, default=str)[:1500])
    return data

def jsonl_summary(path: Path, max_sample=2):
    p(f"\n## JSONL {path}")
    keys = Counter()
    n = 0
    samples = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            n += 1
            if isinstance(obj, dict):
                for k in obj:
                    keys[k] += 1
                if len(samples) < max_sample:
                    samples.append(obj)
    p(f"  rows={n}")
    p("  field_counts:", dict(keys))
    for i, s in enumerate(samples):
        # truncate long strings
        t = {}
        for k, v in s.items():
            if isinstance(v, str) and len(v) > 300:
                t[k] = v[:300] + "..."
            elif isinstance(v, list) and v:
                t[k] = f"list(len={len(v)}) first={json.dumps(v[0], ensure_ascii=False, default=str)[:400]}"
            else:
                t[k] = v
        p(f"  sample{i}:", json.dumps(t, ensure_ascii=False, default=str)[:2000])
    return n, list(keys)

# ---- sqlite ----
conn = ro(LEARN)
schema(conn, "learning")
# extra counts
cur = conn.cursor()
p("\n## learning extra counts")
# rules statuses
try:
    for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        pass
    cols = [c[1] for c in cur.execute("PRAGMA table_info(rules)")]
    p("rules cols", cols)
    # common status fields
    for col in cols:
        if col.lower() in {"status", "state", "passed", "approved", "kind", "type", "rule_id", "id", "source"} or "status" in col.lower() or "id" in col.lower():
            vals = cur.execute(f"SELECT {col}, COUNT(*) FROM rules GROUP BY {col} ORDER BY COUNT(*) DESC LIMIT 30").fetchall()
            p(f"  rules.{col} top:", vals[:30])
except Exception as e:
    p("rules extra error", e)

for t in ["feedback", "adoptions", "runs"]:
    try:
        cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})")]
        p(f"{t} cols", cols)
    except Exception as e:
        p(t, e)
conn.close()

conn = ro(CATALOG)
schema(conn, "catalog")
cur = conn.cursor()
# table names more
for t in [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")]:
    cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})")]
    p(f"catalog.{t} cols", cols)
conn.close()

# ---- action annotation finals ----
finals = [
    "batch-01.json","batch-02.json","batch-03.json","batch-04.json",
    "product-01.json","product-02.json","product-03.json","product-04.json",
    "product-05.json","product-06.json","product-07.json","product-08.json",
    "person-01.json","person-02.json","person-03.json","person-04.json",
    "person-05.json","person-07.json",
    "P24-boundary-proposal.json",
    "aming-source-rule-index.json",
]
for name in finals:
    json_summary(ANN / name)

# identity evidence already copied
json_summary(OUT / r"镜序副本\identity-evidence.json")

# trial 50
json_summary(RULES / r"试标50段\审核结果_李康_20261116.json")
p("\n## CSV 试标50段/_对应表.csv")
csv_path = RULES / r"试标50段\_对应表.csv"
with csv_path.open(encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))
p("  rows", len(rows), "fields", list(rows[0].keys()) if rows else None)
if rows:
    p("  sample0", json.dumps(rows[0], ensure_ascii=False)[:800])

# annotation jsonl
for rel in [
    r"小区全库\数据\AI剪辑检索索引.jsonl",
    r"测试阿明搅拌\数据\AI剪辑检索索引.jsonl",
    r"微陶泥施工\施工镜头.jsonl",
    r"小区全库\数据\按用途检索.jsonl",
    r"小区全库\数据\本轮看片精标.jsonl",
    r"小区全库\数据\机器片段复核.jsonl",
    r"小区全库\数据\目视纠正.jsonl",
]:
    jsonl_summary(LABEL / rel)

# write report
dest = OUT / r"_reads\input_structure_raw.txt"
dest.write_text("\n".join(report), encoding="utf-8")
p("WROTE", dest, "lines", len(report))
