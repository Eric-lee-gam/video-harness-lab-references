from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\脚本\c10_item1_counts.py")
t = p.read_text(encoding="utf-8")
old = 'trial_n = len(trial.get("结果") or trial if isinstance(trial, list) else [])'
new = 'trial_results = trial["结果"] if isinstance(trial, dict) and "结果" in trial else trial\ntrial_n = len(trial_results)'
if old not in t:
    raise SystemExit("pattern not found")
p.write_text(t.replace(old, new, 1), encoding="utf-8")
print("patched")
