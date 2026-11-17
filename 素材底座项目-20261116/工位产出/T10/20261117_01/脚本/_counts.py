from pathlib import Path
root = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
for p in sorted(root.rglob("*.jsonl")) + sorted(root.rglob("*.json")):
    if p.suffix == ".jsonl":
        n = sum(1 for line in p.open(encoding="utf-8") if line.strip())
        print(f"{n:8d}  {p}  {p.stat().st_size}")
    else:
        print(f"{'json':>8s}  {p}  {p.stat().st_size}")
