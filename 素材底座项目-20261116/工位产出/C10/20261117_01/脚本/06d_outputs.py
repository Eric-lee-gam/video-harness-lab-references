from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果\02_structures.txt")
text = p.read_text(encoding="utf-8")
parts = text.split("====")
for idx in [8, 10, 12, 14]:
    print("="*40, "PART", idx, "="*40)
    print(parts[idx])
