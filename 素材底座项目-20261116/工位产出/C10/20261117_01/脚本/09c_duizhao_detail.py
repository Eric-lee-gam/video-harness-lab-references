from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\原始副本\规则\出镜文件夹确认图\对照表.md")
ls = p.read_text(encoding="utf-8").splitlines()
# print from 逐格明细 to end, but maybe first 40 of that plus a couple sections
idx=next(i for i,L in enumerate(ls) if "逐格明细" in L)
print("start", idx, "total", len(ls))
print("\n".join(f"{i+1}|{ls[i]}" for i in range(idx, min(idx+45, len(ls)))))
print("\n----- TAIL 20 -----")
print("\n".join(f"{i+1}|{ls[i]}" for i in range(max(idx, len(ls)-20), len(ls))))
