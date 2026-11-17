# -*- coding: utf-8 -*-
"""试标 50 段：把李康的审核结果复制进工作区（新建），和云端标注对照出统计。"""
import collections, json, os, shutil, sys

sys.dont_write_bytecode = True
D = r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116\试标50段"
SRC = r"C:\Users\leega\Downloads\审核结果.json"
DST = os.path.join(D, "审核结果_李康_20261116.json")
if os.path.exists(DST):
    print("目标已存在，不覆盖:", DST)
else:
    shutil.copyfile(SRC, DST)
    print("已复制到:", DST)

rev = {r["seg"]: r for r in json.load(open(SRC, encoding="utf-8"))["结果"]}
lab = {}
for line in open(os.path.join(D, "标注_云端.jsonl"), encoding="utf-8"):
    if line.strip():
        r = json.loads(line)
        lab[r["seg"]] = r

C = collections.Counter
print("审了:", sum(1 for r in rev.values() if r.get("verdict")), "/", len(rev))
print("画面类型 对/错:", dict(C(r.get("verdict") for r in rev.values())))
print("原因:", dict(C(r.get("reason") for r in rev.values())))
by = collections.defaultdict(C)
for s, r in rev.items():
    by[lab[s]["把握"]][r.get("verdict")] += 1
print("按模型把握分:", {k: dict(v) for k, v in by.items()})
bt = collections.defaultdict(C)
for s, r in rev.items():
    bt[lab[s]["画面类型代码"] + " " + lab[s]["画面类型"]][r.get("verdict")] += 1
print("按画面类型分:")
for k, v in sorted(bt.items()):
    print("  ", k, dict(v))
print("其余项被勾错:", dict(C(o for r in rev.values() for o in r.get("other", []))))

print("\n== 画面类型判错的")
for s, r in rev.items():
    if r.get("verdict") == "错":
        l = lab[s]
        print(f"{s} 模型={l['画面类型代码']} {l['画面类型']} → 李康={r.get('fix')} 原因={r.get('reason')} 把握={l['把握']}")
        print("    模型看见:", l["看见了什么"], "| 主动作", l["主动作"], "| 阶段", l["阶段"], "| 空间", l["空间"])
print("\n== 其余项有错或有备注的")
for s, r in rev.items():
    if r.get("other") or r.get("note"):
        l = lab[s]
        print(f"{s} [{l['画面类型代码']}] 勾错={r.get('other')} 备注={r.get('note', '')}")
        print(f"    模型: 空间={l['空间']} 阶段={l['阶段']} 人数={l['人数']} 朝向={l['朝向']} 主动作={l['主动作']} 多画面={l['多画面']}")
        print("    模型看见:", l["看见了什么"])
