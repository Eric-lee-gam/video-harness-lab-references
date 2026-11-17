from pathlib import Path
src = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\_reads")
files = {
    "01_共同约定.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\共同约定.md",
    "02_共同约定-v0.4补充.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\共同约定-v0.4补充.md",
    "03_T10-现成数据接入.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\T10-现成数据接入.md",
    "04_素材标注现状.md": r"D:\codex-work\codex-company\video-harness-lab\references\素材标注现状-20261116\素材标注现状.md",
}
for name, p in files.items():
    text = Path(p).read_text(encoding="utf-8")
    dest = src / name
    dest.write_text(text, encoding="utf-8")
    print(f"{name}\t{len(text)}\t{len(text.splitlines())} lines")
