from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查报告.md")
print("exists", p.exists(), "size", p.stat().st_size)
text = p.read_text(encoding="utf-8")
# show first 80 and the 结论 / 需上报 sections
for i,l in enumerate(text.splitlines(),1):
    if i<=45 or l.startswith("## 第") or l.startswith("**通过") or l.startswith("**不通过") or l.startswith("## 结论") or l.startswith("**小问题") or l.startswith("**需上报"):
        print(f"{i}|{l}")
print("--- scripts ---")
for q in sorted((p.parent/"脚本").glob("c10_*.py")):
    print(q.name, q.stat().st_size)
