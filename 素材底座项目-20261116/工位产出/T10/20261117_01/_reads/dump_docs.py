import pathlib, sys
files = [
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\共同约定.md",
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\共同约定-v0.4补充.md",
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\T10-现成数据接入.md",
    r"D:\codex-work\codex-company\video-harness-lab\references\素材标注现状-20261116\素材标注现状.md",
]
out = pathlib.Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\_reads\docs_batch1.txt")
parts = []
for p in files:
    text = pathlib.Path(p).read_text(encoding="utf-8")
    parts.append("=" * 80 + "\nFILE: " + p + "\n" + "=" * 80 + "\n" + text + "\n")
out.write_text("\n".join(parts), encoding="utf-8")
print("WROTE", out, "bytes", out.stat().st_size)
