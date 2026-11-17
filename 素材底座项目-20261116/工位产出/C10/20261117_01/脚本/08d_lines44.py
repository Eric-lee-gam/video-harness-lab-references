from pathlib import Path
ls = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果\04_named_and_notime.txt").read_text(encoding="utf-8").splitlines()
# print lines 44-120 exactly (named remaining)
print("===== LINES 44-119 =====")
for i in range(43, min(120, len(ls))):
    print(f"{i+1}: {ls[i]}")
