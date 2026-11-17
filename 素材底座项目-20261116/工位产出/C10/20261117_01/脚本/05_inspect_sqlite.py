from pathlib import Path
import json, sqlite3, csv, collections

out = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01")
raw = out / "原始副本"
report_dir = out / "检查中间结果"
report_dir.mkdir(exist_ok=True)

lines = []
def log(s=""):
    lines.append(s)
    print(s)

# complete inventory of json in aa already copied
aa_copy = raw / "镜序" / "action-annotation"
log("=== copied action-annotation json ===")
for p in sorted(aa_copy.glob("*.json"), key=lambda x: x.name.lower()):
    log(f"{p.name}\t{p.stat().st_size}")

# find sample-coverage
aa = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
log("\n=== coverage files at aa top ===")
for p in sorted(aa.glob("*coverage*")):
    log(f"{p.name}\t{p.stat().st_size}")
    dest = raw / "镜序" / "action-annotation" / p.name
    if not dest.exists():
        import shutil
        shutil.copy2(p, dest)
        log("copied " + p.name)

# sqlite schemas
def inspect_sqlite(path):
    uri = "file:" + path.as_posix() + "?mode=ro&immutable=1"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    log(f"\n=== SQLITE {path.name} tables: {tables} ===")
    for t in tables:
        cols = list(cur.execute(f"PRAGMA table_info({t})"))
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        coln = ", ".join(c[1] for c in cols)
        log(f"  {t}: {n} rows; cols: {coln}")
    return conn

learning = raw / "镜序" / "learning.sqlite3"
catalog = raw / "镜序" / "catalog.sqlite3"
if not learning.exists() or not catalog.exists():
    log(f"MISSING sqlite learning={learning.exists()} catalog={catalog.exists()}")
    # copy if needed
    import shutil
    src_l = Path(r"D:\CutFrame项目完整整理_20261116\local\cutframe\ai\learning.sqlite3")
    src_c = Path(r"D:\CutFrame项目完整整理_20261116\local\cutframe\catalog.sqlite3")
    if not learning.exists():
        shutil.copy2(src_l, learning)
        log("copied learning")
    if not catalog.exists():
        shutil.copy2(src_c, catalog)
        log("copied catalog")

conn_l = inspect_sqlite(learning)
conn_c = inspect_sqlite(catalog)

# rules breakdown
log("\n=== learning.rules breakdown ===")
cur = conn_l.cursor()
for row in cur.execute("SELECT status, COUNT(*) c FROM rules GROUP BY status"):
    log(f"  status={row[0]} count={row[1]}")
# id patterns
for row in cur.execute("SELECT CASE WHEN id LIKE 'confirmed-%' THEN 'confirmed' ELSE 'other' END k, status, COUNT(*) FROM rules GROUP BY 1,2"):
    log(f"  kind={row[0]} status={row[1]} count={row[2]}")
# sample confirmed ids
ids = [r[0] for r in cur.execute("SELECT id FROM rules WHERE id LIKE 'confirmed-%' ORDER BY id")]
log(f"  confirmed ids ({len(ids)}): {ids}")

# feedback / adoptions / runs
for t in ["feedback", "adoptions", "runs", "rule_events"]:
    try:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        log(f"  {t}={n}")
    except Exception as e:
        log(f"  {t} err {e}")

# adoptions status
try:
    for row in cur.execute("SELECT verdict, COUNT(*) FROM feedback GROUP BY verdict"):
        log(f"  feedback verdict={row[0]} {row[1]}")
except Exception as e:
    log(f"feedback group err {e}")
    # peek columns via one row
    row = cur.execute("SELECT * FROM feedback LIMIT 1").fetchone()
    log("feedback keys " + ", ".join(row.keys()))
    log(str(dict(row))[:2000])

row = cur.execute("SELECT * FROM adoptions LIMIT 1").fetchone()
log("adoptions keys " + ", ".join(row.keys()))
log(str(dict(row))[:2000])

row = cur.execute("SELECT * FROM runs LIMIT 1").fetchone()
log("runs keys " + ", ".join(row.keys()))
log("runs sample keys done")

# catalog roots
log("\n=== catalog roots ===")
curc = conn_c.cursor()
# peek one
row = curc.execute("SELECT * FROM assets LIMIT 1").fetchone()
log("assets keys " + ", ".join(row.keys()))
log(str(dict(row))[:2000])
try:
    for row in curc.execute("SELECT root, COUNT(*) FROM assets GROUP BY root"):
        log(f"  root={row[0]} {row[1]}")
except Exception:
    # maybe different col name
    log("root group failed, cols already printed")

conn_l.close(); conn_c.close()

(report_dir / "01_schema_sqlite.txt").write_text("\n".join(lines), encoding="utf-8")
print("\nWROTE", report_dir / "01_schema_sqlite.txt")
