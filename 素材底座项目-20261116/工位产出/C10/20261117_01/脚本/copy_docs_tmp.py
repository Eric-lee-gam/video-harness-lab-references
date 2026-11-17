from pathlib import Path
out = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\_tmp_docs")
out.mkdir(exist_ok=True)
files = {
    "共同约定.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\共同约定.md",
    "共同约定-v0.4补充.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\共同约定-v0.4补充.md",
    "T10-现成数据接入.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\T10-现成数据接入.md",
    "T10回报.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\回报.md",
    "C10-检查现成数据接入.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\C10-检查现成数据接入.md",
}
for name, src in files.items():
    text = Path(src).read_text(encoding="utf-8")
    dest = out / name
    dest.write_text(text, encoding="utf-8")
    print(f"{name}: {len(text.splitlines())} lines, {len(text)} chars")
