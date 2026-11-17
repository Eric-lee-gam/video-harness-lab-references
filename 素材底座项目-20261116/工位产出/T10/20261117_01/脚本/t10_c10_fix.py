# -*- coding: utf-8 -*-
"""T10 C10 修订：只改三处。不编造起止秒，不改原片表/素材库.json，不写共享盘或镜序完整包。"""
from __future__ import annotations

import json
import shutil
from collections import defaultdict
from pathlib import Path

CLIP = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
OUT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
SRC_CONS = OUT / "标注库副本" / "微陶泥施工" / "施工镜头.jsonl"
FACTS = CLIP / "事实层.jsonl"
COARSE = CLIP / "粗标层.jsonl"

# ---------- 1 + 3: 事实层 ----------
facts = []
with FACTS.open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            facts.append(json.loads(line))

fix1 = {
    "目视纠正改确认级别为原片级": [],
    "对照表逐格补无起止秒并改为格子级": [],
    "F0191补无起止秒且保留起秒6、不编造止秒": [],
}
fix3 = []

for r in facts:
    fid = r.get("事实编号")
    src = r.get("来源文件") or ""
    level = r.get("确认级别")
    start, end = r.get("起秒"), r.get("止秒")
    complete = start is not None and end is not None and start != "" and end != ""

    if level == "片段级" and not complete:
        if src.endswith("目视纠正.jsonl"):
            # 源文件本身没有起止秒，已有无起止秒标记；级别改为与源相符的原片级
            r["无起止秒"] = True
            r["确认级别"] = "原片级"
            # 起止秒保持原文（空），不编造
            fix1["目视纠正改确认级别为原片级"].append(fid)
        elif "对照表.md#明细" in src and start is None and end is None:
            r["无起止秒"] = True
            r["确认级别"] = "格子级"
            fix1["对照表逐格补无起止秒并改为格子级"].append(fid)
        elif fid == "F0191":
            r["无起止秒"] = True
            # 确认级别仍为片段级：原文有「约第 6 秒起入镜」，起秒=6 保留，止秒保持为空
            if r.get("起秒") != 6 or r.get("止秒") is not None:
                raise SystemExit("F0191 起止秒与预期不符，停止以免误改: %s %s" % (r.get("起秒"), r.get("止秒")))
            fix1["F0191补无起止秒且保留起秒6、不编造止秒"].append(fid)
        else:
            raise SystemExit("未预期的片段级缺起止记录: %s %s start=%s end=%s" % (fid, src, start, end))

    if fid == "F0018" or r.get("来源条目标识") == "confirmed-P3":
        content = r.get("内容") or {}
        text = (content.get("product_identity") if isinstance(content, dict) else None) or ""
        if "本片段不是微陶泥" not in str(text):
            raise SystemExit("F0018 原文未找到「本片段不是微陶泥」，停止: %s" % text)
        before = r.get("是否反例")
        r["是否反例"] = True
        fix3.append({"事实编号": fid, "来源条目标识": r.get("来源条目标识"), "改前": before, "改后": True, "依据字段": text})

# rewrite 事实层
tmp_f = FACTS.with_name("事实层.jsonl.tmp")
with tmp_f.open("w", encoding="utf-8", newline="\n") as f:
    for r in facts:
        f.write(json.dumps(r, ensure_ascii=False, default=str))
        f.write("\n")
tmp_f.replace(FACTS)

# ---------- 2: 粗标层施工镜头来源条目标识 ----------
# 源文件行号（从 1 起，只计非空行，与 jsonl 行一致）
source_rows = []
with SRC_CONS.open(encoding="utf-8") as f:
    for lineno, line in enumerate(f, 1):
        if not line.strip():
            continue
        source_rows.append((lineno, json.loads(line)))

def sig(obj):
    return (
        obj.get("id"),
        obj.get("start"),
        obj.get("end"),
        obj.get("工序"),
    )

# queue unused source line numbers by signature
src_q = defaultdict(list)
for lineno, obj in source_rows:
    src_q[sig(obj)].append(lineno)

used_new = []
n_cons = 0
n_changed = 0
tmp_c = COARSE.with_name("粗标层.jsonl.tmp")
unmatched = []
with COARSE.open(encoding="utf-8") as fin, tmp_c.open("w", encoding="utf-8", newline="\n") as fout:
    for line in fin:
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("记录种类") == "施工镜头" or (r.get("来源文件") or "").endswith("施工镜头.jsonl"):
            n_cons += 1
            fields = r.get("原字段") or {}
            q = src_q[sig(fields)]
            if not q:
                unmatched.append({"粗标编号": r.get("粗标编号"), "旧标识": r.get("来源条目标识"), "sig": list(sig(fields))})
            else:
                lineno = q.pop(0)
                proc = fields.get("工序")
                old = r.get("来源条目标识")
                # 保留原 id:start-end，追加工序和源文件行号，保证唯一
                new = "%s:%s:#%s" % (old, proc if proc is not None else "", lineno)
                r["来源条目标识"] = new
                n_changed += 1
                used_new.append(new)
        fout.write(json.dumps(r, ensure_ascii=False, default=str))
        fout.write("\n")

if unmatched:
    raise SystemExit("有施工镜头对不上源文件行，已停止未替换粗标层: %s" % unmatched[:5])

# leftover source lines would mean mismatch
leftover = sum(len(v) for v in src_q.values())
if leftover != 0 or n_changed != len(source_rows):
    raise SystemExit("源文件行与粗标施工镜头条数不一致: leftover=%s changed=%s source=%s" % (leftover, n_changed, len(source_rows)))

tmp_c.replace(COARSE)

# uniqueness check
dup = [k for k, c in __import__("collections").Counter(used_new).items() if c > 1]
if dup:
    raise SystemExit("修订后仍有撞键: %s" % dup[:5])

# ---------- 抽查 ----------
def load(path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows

facts2 = load(FACTS)
# 片段级且不完整起止
inc = []
for r in facts2:
    if r.get("确认级别") == "片段级":
        start, end = r.get("起秒"), r.get("止秒")
        complete = start is not None and end is not None and start != "" and end != ""
        if not complete:
            inc.append(r)
# 101 条应都已处理：只剩 F0191 仍为片段级且无完整止秒，但已有无起止秒
f0191 = [r for r in facts2 if r.get("事实编号") == "F0191"][0]
f0018 = [r for r in facts2 if r.get("事实编号") == "F0018"][0]
# 抽查目视纠正、逐格
shi = next(r for r in facts2 if r.get("事实编号") in fix1["目视纠正改确认级别为原片级"])
ge = next(r for r in facts2 if r.get("事实编号") in fix1["对照表逐格补无起止秒并改为格子级"])

# 粗标抽查：原先撞键样例
spot_keys = {}
with COARSE.open(encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("粗标编号") in ("C041329", "C041330", "C043951", "C043952"):
            spot_keys[r["粗标编号"]] = r.get("来源条目标识")

# 施工镜头标识唯一
cons_ids = []
with COARSE.open(encoding="utf-8") as f:
    for line in f:
        r = json.loads(line)
        if r.get("记录种类") == "施工镜头":
            cons_ids.append(r.get("来源条目标识"))
from collections import Counter
c = Counter(cons_ids)

audit = {
    "事实层条数仍为": len(facts2),
    "片段级且起止不完整": [
        {"事实编号": r.get("事实编号"), "起秒": r.get("起秒"), "止秒": r.get("止秒"), "无起止秒": r.get("无起止秒"), "确认级别": r.get("确认级别")}
        for r in inc
    ],
    "F0191": {"起秒": f0191.get("起秒"), "止秒": f0191.get("止秒"), "无起止秒": f0191.get("无起止秒"), "确认级别": f0191.get("确认级别")},
    "F0018": {"是否反例": f0018.get("是否反例"), "product_identity": (f0018.get("内容") or {}).get("product_identity")},
    "目视纠正抽查": {"事实编号": shi.get("事实编号"), "确认级别": shi.get("确认级别"), "无起止秒": shi.get("无起止秒"), "起秒": shi.get("起秒"), "止秒": shi.get("止秒")},
    "对照表逐格抽查": {"事实编号": ge.get("事实编号"), "确认级别": ge.get("确认级别"), "无起止秒": ge.get("无起止秒"), "起秒": ge.get("起秒"), "止秒": ge.get("止秒")},
    "施工镜头条数": len(cons_ids),
    "施工镜头唯一标识数": len(c),
    "修订后撞键组": sum(1 for n in c.values() if n > 1),
    "施工镜头标识抽查": spot_keys,
    "fix1条数": {k: len(v) for k, v in fix1.items()},
    "fix3": fix3,
}

(OUT / "统计" / "C10修订抽查.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(audit, ensure_ascii=False, indent=2))
print("OK")
