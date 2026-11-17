from pathlib import Path
ls = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果\04_named_and_notime.txt").read_text(encoding="utf-8").splitlines()
idx=next(i for i,L in enumerate(ls) if "片段级无起止秒" in L)
# print from idx to before 对照表 headings flood - maybe first 40 lines of this section plus FILE headers
end=len(ls)
for i,L in enumerate(ls[idx:], idx):
    if "==== FILE" in L:
        # print this and next 5 structure lines only later
        pass
print("\n".join(ls[idx:idx+30]))
print("----- FILE STARTS -----")
for i,L in enumerate(ls[idx:], idx):
    if L.startswith("==== FILE") or L.startswith("lines=") or L.startswith("headings"):
        print(L)
# count sheet / 明细 headers
print("----- selected headings -----")
for L in ls[idx:]:
    if L.strip().startswith("L") and ("##" in L or "###" in L or "汇总" in L or "逐格" in L):
        print(L)
