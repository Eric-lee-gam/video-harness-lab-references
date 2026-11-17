from pathlib import Path
scripts = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\脚本")
# write_config tail
p=scripts/"write_config.py"
ls=p.read_text(encoding="utf-8").splitlines()
print("write_config last 20:")
print("\n".join(f"{i+1}|{l}" for i,l in list(enumerate(ls))[-20:]))

print("\n===== shutil / copy across all scripts =====")
for p in sorted(scripts.glob("*.py")):
    for i,l in enumerate(p.read_text(encoding="utf-8").splitlines(),1):
        if "shutil" in l or "copy2(" in l or "copytree(" in l or ".copy(" in l:
            print(f"{p.name}:{i}: {l.strip()[:220]}")

print("\n===== _fix_lib / _annotate / _fix_verify path vars =====")
for name in ["_fix_lib.py", "_annotate_conflicts.py", "_fix_verify.py"]:
    print("----", name)
    print((scripts/name).read_text(encoding="utf-8")[:2500])
    print()
