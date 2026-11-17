from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果\02_structures.txt")
text = p.read_text(encoding="utf-8")
# split by ==== headers
parts = text.split("====")
print("N PARTS", len(parts))
for i, part in enumerate(parts):
    head = part.strip().splitlines()[0] if part.strip() else "(empty)"
    print(f"--- part {i}: {head[:80]}  lines={len(part.splitlines())} chars={len(part)}")
