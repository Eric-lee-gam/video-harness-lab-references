from pathlib import Path
root = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
t10 = root / r"工位产出\T10\20261117_01"
lib = root / "片段库"
fb = root / "问题反馈"

def list_dir(p, depth=2, prefix=""):
    if not p.exists():
        print(f"{prefix}MISSING: {p}")
        return
    items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    for i in items:
        if i.is_dir():
            try:
                n = sum(1 for _ in i.iterdir())
            except Exception as e:
                n = f"err {e}"
            print(f"{prefix}[DIR] {i.name}/  ({n})")
            if depth > 1:
                list_dir(i, depth-1, prefix+"  ")
        else:
            print(f"{prefix}{i.name}\t{i.stat().st_size}")

print("=== T10 output ===")
list_dir(t10, 3)
print("\n=== 片段库 ===")
list_dir(lib, 2)
print("\n=== 问题反馈 ===")
list_dir(fb, 2)
