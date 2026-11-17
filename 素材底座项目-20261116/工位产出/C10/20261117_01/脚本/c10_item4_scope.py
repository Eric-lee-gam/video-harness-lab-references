# -*- coding: utf-8 -*-
"""C10 item 4: scope not expanded."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c10_common import *

facts = load_jsonl(LIB / "事实层.jsonl")
clues = load_jsonl(LIB / "线索.jsonl")
aa = RAW / "镜序" / "action-annotation"

# 1) fragment-level must have start/end
seg = [r for r in facts if r.get("确认级别")=="片段级"]
folder = [r for r in facts if r.get("确认级别")=="文件夹级"]
other_lvl = [r for r in facts if r.get("确认级别") not in ("片段级","文件夹级")]

def missing_time(r):
    return r.get("起秒") in (None, "") or r.get("止秒") in (None, "")

seg_missing = [r for r in seg if missing_time(r)]
folder_with_time = [r for r in folder if not missing_time(r)]

# group missing
from collections import Counter
miss_grp = Counter((r.get("来源文件"), r.get("样例类别"), r.get("无起止秒") is True) for r in seg_missing)
miss_ids = [
    {
        "事实编号": r.get("事实编号"),
        "来源文件": r.get("来源文件"),
        "来源条目标识": r.get("来源条目标识"),
        "起秒": r.get("起秒"),
        "止秒": r.get("止秒"),
        "无起止秒": r.get("无起止秒"),
        "主库相对路径": r.get("主库相对路径"),
    }
    for r in seg_missing
]

# Did originals of these actually have times that were dropped?
# 目视纠正: no start/end fields in source
# 对照表明细: generally no times except 17881 text "前 5 秒" / "约第 6 秒"
# Verify 目视纠正 source schema has no start/end
corr = load_jsonl(RAW / "标注库" / "小区全库" / "数据" / "目视纠正.jsonl")
corr_has_time_keys = any(("start" in r or "end" in r or "起秒" in r or "止秒" in r) for r in corr)

# 2) qualifier preservation for original records that say 只对本段有效 / 不套用到目录
# From sqlite confirmed payloads: apply_to_directory is false, evidence contains 不要套用整个目录 / 不要直接套到整个目录, context 仅本段
conn = open_sqlite_ro(RAW / "镜序" / "learning.sqlite3")
rows = list(conn.execute("SELECT id, payload FROM rules WHERE id LIKE 'confirmed-%'"))
conn.close()

QUAL_PATTS = [
    re.compile(r"不套用到?目录"),
    re.compile(r"不要套用整个目录"),
    re.compile(r"不要直接套到整个目录"),
    re.compile(r"只对本段"),
    re.compile(r"仅本段"),
    re.compile(r"仅所列来源时间段"),
    re.compile(r"apply_to_directory"),
]

def has_qual_text(s: str) -> list[str]:
    hits = []
    for p in QUAL_PATTS:
        if p.search(s or ""):
            hits.append(p.pattern)
    return hits

qualifier_issues = []
qualifier_ok = []
for row in rows:
    pay = json.loads(row["payload"]) if row["payload"] else {}
    src_text = json.dumps(pay, ensure_ascii=False)
    # apply_to_directory false is a qualifier even without those words
    needs = has_qual_text(src_text)
    if pay.get("apply_to_directory") is False:
        needs = needs + (["apply_to_directory=false"] if "apply_to_directory" not in ",".join(needs) else [])
    if not needs and pay.get("apply_to_directory") is not False:
        continue
    fact = next((f for f in facts if f.get("来源条目标识")==row["id"]), None)
    if not fact:
        qualifier_issues.append({"id": row["id"], "reason": "事实层找不到", "needs": needs})
        continue
    out_text = (fact.get("限定语原文") or "") + "\n" + json.dumps(fact.get("内容"), ensure_ascii=False)
    missing_bits = []
    # evidence / context phrases that are qualifier-like should appear in 限定语
    ev = pay.get("evidence")
    evs = ev if isinstance(ev, list) else ([ev] if ev else [])
    for e in evs:
        if e and has_qual_text(str(e)):
            if str(e) not in (fact.get("限定语原文") or "") and str(e) not in out_text:
                missing_bits.append({"type": "evidence", "text": e})
    ctx = pay.get("context")
    if ctx and has_qual_text(str(ctx)):
        if str(ctx) not in (fact.get("限定语原文") or "") and str(ctx) not in out_text:
            missing_bits.append({"type": "context", "text": ctx})
    prod = pay.get("product_identity")
    if prod and has_qual_text(str(prod)):
        if str(prod) not in (fact.get("限定语原文") or "") and str(prod) not in out_text:
            missing_bits.append({"type": "product_identity", "text": prod})
    if pay.get("apply_to_directory") is False:
        # must be visible in 限定语 or 内容
        if "不套用到目录" not in out_text and "apply_to_directory" not in out_text and "不套用整个目录" not in out_text:
            missing_bits.append({"type": "apply_to_directory", "text": "false"})
    if missing_bits:
        qualifier_issues.append({
            "id": row["id"],
            "事实编号": fact.get("事实编号"),
            "missing": missing_bits,
            "限定语原文": fact.get("限定语原文"),
        })
    else:
        qualifier_ok.append(row["id"])

# Also batch / P24 apply_to_directory or 仅本段
aa_files = ["batch-01.json","batch-02.json","batch-03.json","batch-04.json","P24-boundary-proposal.json"]
batch_qual_issues = []
for fn in aa_files:
    obj = load_json(aa / fn)
    for r in obj.get("rows") or []:
        src_text = json.dumps(r, ensure_ascii=False)
        needs = has_qual_text(src_text)
        if r.get("apply_to_directory") is False:
            needs.append("apply_to_directory=false")
        if not needs:
            continue
        fact = next((f for f in facts if f.get("来源条目标识")==r.get("sample_id")), None)
        if not fact:
            batch_qual_issues.append({"file": fn, "id": r.get("sample_id"), "reason": "事实层找不到"})
            continue
        out_text = (fact.get("限定语原文") or "") + "\n" + json.dumps(fact.get("内容"), ensure_ascii=False)
        missing_bits = []
        # key phrases from quality_note / confirmation notes
        for field in ("quality_note", "confirmed_label", "confirmation_note", "apply_to_directory"):
            val = r.get(field)
            if val is None:
                continue
            if field=="apply_to_directory" and val is False:
                if "不套用到目录" not in out_text and "apply_to_directory" not in out_text:
                    missing_bits.append({"field": field, "val": val})
            elif isinstance(val, str) and has_qual_text(val):
                if val not in out_text:
                    missing_bits.append({"field": field, "val": val})
        if missing_bits:
            batch_qual_issues.append({"file": fn, "id": r.get("sample_id"), "事实编号": fact.get("事实编号"), "missing": missing_bits})

# 3) 2098 source rules all in clues, none in facts
aming = load_json(aa / "aming-source-rule-index.json")
aming_rows = aming.get("rows") or []
clue_ids = {c.get("来源条目标识") for c in clues}
missing_clues = [r.get("id") for r in aming_rows if r.get("id") not in clue_ids]
facts_from_aming = [f.get("事实编号") for f in facts if "aming-source-rule" in (f.get("来源文件") or "")]
# also search fact content for typical source_rule text? too loose.
# Check 未逐片核实 preserved on all clues
clues_missing_flag = [c.get("来源条目标识") for c in clues if not (c.get("未逐片核实") or ("未逐片核实" in json.dumps(c, ensure_ascii=False)))]

# Pass standard literal: 片段级全部有起止秒 AND 来源规则没有混进事实层
literal_all_seg_have_times = len(seg_missing)==0
no_rules_in_facts = len(facts_from_aming)==0 and len(missing_clues)==0
scope_expanded = False
scope_notes = []
# Range expansion would be: dropped 仅本段/不套用到目录, or invented directory-wide application, or source rules entered facts
if qualifier_issues or batch_qual_issues:
    scope_expanded = True
    scope_notes.append("有限定语未带上")
if facts_from_aming:
    scope_expanded = True
    scope_notes.append("来源规则混进事实层")

# The 101 missing times: originals also lack times (except F0191 which faithfully keeps 约第6秒起 / no end). Not expansion.
# But literal standard fails.

result = {
    "item": 4,
    "literal_pass_standard": literal_all_seg_have_times and no_rules_in_facts and not qualifier_issues and not batch_qual_issues,
    "scope_expanded": scope_expanded,
    "need_report_likang": scope_expanded,
    "need_report_reason": "；".join(scope_notes) if scope_expanded else "",
    "片段级总数": len(seg),
    "文件夹级总数": len(folder),
    "其他级别": [r.get("事实编号") for r in other_lvl],
    "片段级缺起止秒": len(seg_missing),
    "片段级缺起止分组": {str(k): v for k,v in miss_grp.items()},
    "片段级缺起止清单": miss_ids,
    "文件夹级却有起止": [
        {"事实编号": r.get("事实编号"), "起秒": r.get("起秒"), "止秒": r.get("止秒")} for r in folder_with_time
    ],
    "目视纠正源是否自带起止字段": corr_has_time_keys,
    "限定语检查_confirmed通过": qualifier_ok,
    "限定语检查_confirmed问题": qualifier_issues,
    "限定语检查_batch_P24问题": batch_qual_issues,
    "线索源条数": len(aming_rows),
    "线索产出条数": len(clues),
    "线索缺失": missing_clues[:10],
    "线索缺失条数": len(missing_clues),
    "来源规则进入事实层": facts_from_aming,
    "线索缺未逐片核实标记": clues_missing_flag[:10],
    "线索缺未逐片核实条数": len(clues_missing_flag),
    "判断说明": (
        "片段级缺起止秒 101 条：目视纠正 41 条源文件本身只有 id/description/basis、没有起止秒；"
        "对照表逐格 59 条原文只判格子、不给整段起止；另 1 条 F0191（17881 约第 6 秒起入镜）原文没有止秒，T10 起秒=6、止秒为空，与原文一致。"
        "这些不是把“仅本段”扩大到目录，也不是丢掉了原有的起止秒。"
        "按 C10 字面“片段级记录全部有起止秒”，本项不通过；但第 4 项上报李康的条件是“事实的范围被放大了”，本次未见范围被放大。"
    ),
}
# pass field: I will set pass=False due to literal standard, with scope_expanded=False
result["pass"] = result["literal_pass_standard"]
dump_json(MID / "item4_scope.json", result)
print("ITEM4 literal_pass=", result["pass"], "scope_expanded=", scope_expanded)
print("seg", len(seg), "missing times", len(seg_missing), "groups", dict(miss_grp))
print("qual issues", len(qualifier_issues), "batch qual", len(batch_qual_issues))
print("clues missing", len(missing_clues), "aming in facts", facts_from_aming)
print("clues missing flag", len(clues_missing_flag))
if qualifier_issues[:3]:
    print("qual sample", json.dumps(qualifier_issues[:3], ensure_ascii=False)[:1500])
if batch_qual_issues[:3]:
    print("batch sample", json.dumps(batch_qual_issues[:3], ensure_ascii=False)[:1500])
