from pathlib import Path
import os, shutil, json, sqlite3

out = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01")
raw = out / "原始副本"
(raw / "镜序").mkdir(parents=True, exist_ok=True)
(raw / "标注库").mkdir(parents=True, exist_ok=True)
(raw / "规则").mkdir(parents=True, exist_ok=True)

jx_root = Path(r"D:\CutFrame项目完整整理_20261116")
ann_root = Path(r"\\192.168.110.36\obsidian\素材标注")
rule_root = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116")
csv_path = Path(r"C:\Users\leega\AppData\Local\Temp\share-video-inventory-20261114\36-gongxiang.csv")
share_main = Path(r"\\192.168.110.36\共享本公司\史上最完整共享")

print("=== path exists ===")
for name, p in {
    "jx_root": jx_root,
    "ann_root": ann_root,
    "rule_root": rule_root,
    "36-gongxiang.csv": csv_path,
    "share_main": share_main,
    "拍摄": share_main / "拍摄",
}.items():
    print(f"{name}: exists={p.exists()}  {p}")

print("\n=== jingxu top ===")
if jx_root.exists():
    for p in sorted(jx_root.iterdir(), key=lambda x: x.name.lower()):
        print(("DIR " if p.is_dir() else "FILE"), p.name, p.stat().st_size if p.is_file() else "")

# list action-annotation without opening gpt-pilot
aa = jx_root / r"local\action-annotation"
print("\n=== action-annotation files ===")
if aa.exists():
    for p in sorted(aa.rglob("*")):
        rel = p.relative_to(aa)
        if p.is_file():
            print(f"{rel}\t{p.stat().st_size}")

# never walk gpt-pilot; just check it exists
gp = jx_root / r"local\gpt-pilot"
print("\ngpt-pilot exists (NOT OPENED):", gp.exists())

print("\n=== annotation library listing ===")
if ann_root.exists():
    def walk(base, depth=3, prefix=""):
        try:
            items = sorted(base.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        except Exception as e:
            print(prefix, "ERR", e)
            return
        for i in items:
            if i.is_dir():
                print(f"{prefix}[DIR] {i.name}/")
                if depth > 1:
                    walk(i, depth-1, prefix+"  ")
            else:
                print(f"{prefix}{i.name}\t{i.stat().st_size}")
    walk(ann_root, 3)
