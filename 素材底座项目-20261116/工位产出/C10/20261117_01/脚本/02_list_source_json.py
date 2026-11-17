from pathlib import Path
import json

jx_root = Path(r"D:\CutFrame项目完整整理_20261116")
aa = jx_root / r"local\action-annotation"
cf_ai = jx_root / r"local\cutframe\ai"
cf = jx_root / r"local\cutframe"

print("=== cutframe files (no gpt-pilot) ===")
# list local/cutframe without descending into anything named gpt-pilot
local = jx_root / "local"
for p in sorted(local.iterdir(), key=lambda x: x.name.lower()):
    print(("DIR " if p.is_dir() else "FILE"), p.name)

print("\n=== local/cutframe (non-recursive top + ai + catalog) ===")
if cf.exists():
    for p in sorted(cf.iterdir(), key=lambda x: x.name.lower()):
        if p.name.lower() == "gpt-pilot":
            print("DIR gpt-pilot  (SKIPPED, not opened)")
            continue
        print(("DIR " if p.is_dir() else "FILE"), p.name, p.stat().st_size if p.is_file() else "")

if cf_ai.exists():
    print("\n--- cutframe/ai ---")
    for p in sorted(cf_ai.rglob("*")):
        if "gpt-pilot" in p.parts:
            continue
        if p.is_file():
            print(f"{p.relative_to(cf_ai)}\t{p.stat().st_size}")

print("\n=== action-annotation JSON/MD/CSV/SQLite only ===")
for p in sorted(aa.rglob("*")):
    if p.is_file() and p.suffix.lower() in {".json", ".md", ".csv", ".sqlite", ".sqlite3", ".txt"}:
        print(f"{p.relative_to(aa)}\t{p.stat().st_size}")

print("\n=== before- / discovery filenames in jingxu (json only, no gpt-pilot) ===")
count_before = 0
count_disc = 0
examples_before = []
examples_disc = []
for base in [jx_root / "local" / "action-annotation", jx_root / "local" / "cutframe"]:
    if not base.exists():
        continue
    for p in base.rglob("*"):
        if "gpt-pilot" in p.parts:
            continue
        if not p.is_file():
            continue
        name = p.name.lower()
        rel = str(p.relative_to(jx_root))
        if ".before-" in name or name.endswith(".before") or ".before." in name:
            count_before += 1
            if len(examples_before) < 80:
                examples_before.append(f"{rel}\t{p.stat().st_size}")
        if "discovery" in name:
            count_disc += 1
            if len(examples_disc) < 80:
                examples_disc.append(f"{rel}\t{p.stat().st_size}")
print("before count", count_before)
for e in examples_before:
    print("BEFORE", e)
print("discovery count", count_disc)
for e in examples_disc:
    print("DISC", e)
