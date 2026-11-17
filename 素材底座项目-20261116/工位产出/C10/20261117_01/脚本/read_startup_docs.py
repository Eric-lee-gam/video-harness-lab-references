from pathlib import Path
files = [
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\共同约定.md",
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\共同约定-v0.4补充.md",
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\T10-现成数据接入.md",
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\回报.md",
    r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\任务书-v0.4\C10-检查现成数据接入.md",
]
for p in files:
    path = Path(p)
    print("=" * 80)
    print(f"FILE: {path}")
    print(f"SIZE: {path.stat().st_size}")
    print("=" * 80)
    print(path.read_text(encoding="utf-8"))
    print()
