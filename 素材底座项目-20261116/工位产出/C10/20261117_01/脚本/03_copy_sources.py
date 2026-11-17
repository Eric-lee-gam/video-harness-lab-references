from pathlib import Path
import shutil, json, sqlite3, csv

out = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01")
raw = out / "原始副本"
(raw / "镜序").mkdir(parents=True, exist_ok=True)
(raw / "标注库").mkdir(parents=True, exist_ok=True)
(raw / "规则").mkdir(parents=True, exist_ok=True)

jx_root = Path(r"D:\CutFrame项目完整整理_20261116")
aa = jx_root / r"local\action-annotation"
cf_ai = jx_root / r"local\cutframe\ai"
cf = jx_root / r"local\cutframe"
ann_root = Path(r"\\192.168.110.36\obsidian\素材标注")
rule_root = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116")

print("=== action-annotation top-level data files ===")
for p in sorted(aa.iterdir(), key=lambda x: x.name.lower()):
    if p.is_file():
        print(f"FILE {p.name}\t{p.stat().st_size}")
    else:
        # only name the dir, don't recurse into thumbs
        nfiles = 0
        try:
            nfiles = sum(1 for _ in p.iterdir())
        except Exception:
            nfiles = -1
        print(f"DIR  {p.name}/\t{nfiles} entries")

print("\n=== before-/discovery json at action-annotation top and one level down ===")
for p in aa.iterdir():
    name = p.name.lower()
    if p.is_file() and (".before-" in name or "discovery" in name or ".before." in name):
        print("TOP", p.name, p.stat().st_size)
    elif p.is_dir():
        for q in p.iterdir():
            n = q.name.lower()
            if q.is_file() and (".before-" in n or "discovery" in n):
                print("SUB", q.relative_to(aa), q.stat().st_size)

# copy function
def copy_file(src: Path, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    print(f"COPIED {src} -> {dest} ({dest.stat().st_size})")

# jingxu sqlite/json needed
copies = [
    (cf_ai / "learning.sqlite3", raw / "镜序" / "learning.sqlite3"),
    (cf_ai / "identity-evidence.json", raw / "镜序" / "identity-evidence.json"),
    (cf / "catalog.sqlite3", raw / "镜序" / "catalog.sqlite3"),
]
# coverage files may be in action-annotation
for name in ["sample-coverage.json", "person-coverage.json"]:
    cand = list(aa.glob(name)) + list(cf_ai.glob(name))
    if cand:
        copies.append((cand[0], raw / "镜序" / cand[0].name))
        print("FOUND", cand[0])
    else:
        print("MISSING coverage", name)
        # search top-level only under action-annotation and cutframe/ai already done
        # search a few known places
        for base in [aa, cf_ai, jx_root, jx_root / "outputs"]:
            p = base / name
            if p.exists():
                print("FOUND at", p)
                copies.append((p, raw / "镜序" / name))

# all top-level json in action-annotation
for p in sorted(aa.iterdir()):
    if p.is_file() and p.suffix.lower() == ".json":
        copies.append((p, raw / "镜序" / "action-annotation" / p.name))

print("\n=== copying jingxu sources ===")
for src, dest in copies:
    if not src.exists():
        print("MISSING", src)
        continue
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        print("SKIP exists", dest.name, dest.stat().st_size)
        continue
    copy_file(src, dest)

# annotation library data files
ann_files = [
    r"小区视频素材标注与索引设计.md",
    r"小区全库\数据\AI剪辑检索索引.jsonl",
    r"测试阿明搅拌\数据\AI剪辑检索索引.jsonl",
    r"微陶泥施工\施工镜头.jsonl",
    r"小区全库\数据\按用途检索.jsonl",
    r"小区全库\数据\本轮看片精标.jsonl",
    r"小区全库\数据\机器片段复核.jsonl",
    r"小区全库\数据\目视纠正.jsonl",
]
print("\n=== copying annotation library ===")
for rel in ann_files:
    src = ann_root / rel
    dest = raw / "标注库" / rel
    if not src.exists():
        print("MISSING ANN", src)
        continue
    if dest.exists() and dest.stat().st_size == src.stat().st_size:
        print("SKIP exists", rel, dest.stat().st_size)
        continue
    copy_file(src, dest)

# rules
rule_files = [
    r"试标50段\审核结果_李康_20261116.json",
    r"试标50段\_对应表.csv",
    r"人物身份确认办法.md",
]
# also look for 出镜文件夹确认图\对照表.md mentioned in T10 report
extra_rule = rule_root / r"出镜文件夹确认图\对照表.md"
print("\n=== copying rules ===")
for rel in rule_files:
    src = rule_root / rel
    dest = raw / "规则" / rel
    if not src.exists():
        print("MISSING RULE", src)
        continue
    copy_file(src, dest)
if extra_rule.exists():
    copy_file(extra_rule, raw / "规则" / r"出镜文件夹确认图\对照表.md")
else:
    print("MISSING", extra_rule)
    # search
    for p in rule_root.rglob("对照表.md"):
        print("FOUND 对照表", p)

print("\nDONE COPY")
