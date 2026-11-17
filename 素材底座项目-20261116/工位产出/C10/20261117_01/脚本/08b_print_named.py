from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果\04_named_and_notime.txt")
text = p.read_text(encoding="utf-8")
# print first 120 lines then last remaining if needed
ls = text.splitlines()
print("TOTAL", len(ls))
# split to two files for reading
mid = p.parent
(mid/"04a_named.txt").write_text("\n".join(ls[:120]), encoding="utf-8")
(mid/"04b_rest.txt").write_text("\n".join(ls[120:]), encoding="utf-8")
print("split 120 /", len(ls)-120)
print("\n".join(ls[:120]))
