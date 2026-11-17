from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果\04_named_and_notime.txt")
ls = p.read_text(encoding="utf-8").splitlines()
# print from 水洗石 onwards until 美女人设, then from 片段级, then 对照表
start=None
for i,L in enumerate(ls):
    if "NEEDLE '水洗石'" in L or "NEEDLE \"水洗石\"" in L:
        start=i
        break
print("start", start)
# print lines from water stone to before 美女人设
for i,L in enumerate(ls):
    if any(x in L for x in ["水洗石","不是微陶泥","本片段不是微陶泥","NEEDLE 'P24'","NEEDLE 'P17'","==== named hits in originals","RULE ","FILE "]):
        print(f"{i}: {L}")
print("\n\n======= NOTIME AND DUZHAO =======")
# find 片段级
for i,L in enumerate(ls):
    if "片段级无起止" in L or L.startswith("count=") or L.startswith("  ") and ("src=" in L or L.strip().startswith("ex ") or L.startswith("  L") or L.startswith("==== FILE") or L.startswith("lines=") or L.startswith("headings") or L.startswith("  L")):
        print(f"{i}: {L}")
# just print from 片段级 to end
idx=None
for i,L in enumerate(ls):
    if "片段级无起止秒" in L:
        idx=i
        break
print("\n----- from notime to end -----")
print("\n".join(ls[idx:]))
