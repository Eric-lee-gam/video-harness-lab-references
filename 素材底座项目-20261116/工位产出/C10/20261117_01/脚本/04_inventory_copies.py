from pathlib import Path

out = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\原始副本")
print("=== copied tree ===")
for p in sorted(out.rglob("*")):
    if p.is_file():
        print(f"{p.relative_to(out)}\t{p.stat().st_size}")

aa = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
print("\n=== action-annotation JSON/MD/TXT/CSV only (top-level) ===")
for p in sorted(aa.iterdir(), key=lambda x: x.name.lower()):
    if p.is_file() and p.suffix.lower() in {".json", ".md", ".txt", ".csv", ".sqlite3", ".sqlite"}:
        print(f"{p.name}\t{p.stat().st_size}")

# search coverage files without walking gpt-pilot or visual-cache heavily
print("\n=== search coverage json (limited places) ===")
jx = Path(r"D:\CutFrame项目完整整理_20261116")
places = [
    jx,
    jx / "outputs",
    jx / "cutframe-studio",
    jx / "local" / "action-annotation",
    jx / "local" / "cutframe",
    jx / "local" / "cutframe" / "ai",
    jx / "local" / "cutframe" / "imports",
    jx / "local" / "cutframe" / "metadata",
]
for base in places:
    if not base.exists():
        print("missing place", base)
        continue
    for p in base.glob("*coverage*.json"):
        print("FOUND", p, p.stat().st_size)
    for p in base.glob("sample-*.json"):
        print("FOUND", p, p.stat().st_size)
    for p in base.glob("person-*.json"):
        print("FOUND", p, p.stat().st_size)

# maybe under outputs one level
outputs = jx / "outputs"
if outputs.exists():
    print("\n=== outputs top ===")
    for p in sorted(outputs.iterdir(), key=lambda x: x.name.lower()):
        print(("DIR " if p.is_dir() else "FILE"), p.name, p.stat().st_size if p.is_file() else "")
