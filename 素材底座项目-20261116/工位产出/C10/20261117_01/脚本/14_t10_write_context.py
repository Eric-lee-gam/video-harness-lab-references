from pathlib import Path
scripts = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\脚本")

# print relevant function defs and copy calls
for name in ["t10_lib.py", "write_config.py", "_fix_lib.py", "_annotate_conflicts.py", "_fix_verify.py", "t10_coarse.py", "t10_facts.py", "t10_eval.py", "t10_bans.py", "t10_post.py", "t10_join_yuanpian.py"]:
    p = scripts/name
    if not p.exists():
        print("MISSING", name)
        continue
    text=p.read_text(encoding="utf-8")
    print("="*60, name)
    # first 80 lines often have path constants
    print("\n".join(text.splitlines()[:80]))
    print("----- copy/shutil/LIB/OUT -----")
    for i,line in enumerate(text.splitlines(),1):
        l=line.lower()
        if any(s in l for s in ["shutil", "copy2", "copytree", "copy(", "LIB", "OUT =", "ISSUES", "write_jsonl", "write_json", "片段库"]):
            if "encoding" in l and "open" in l and "w" not in line:
                continue
            print(f"  {i}: {line.rstrip()[:220]}")
