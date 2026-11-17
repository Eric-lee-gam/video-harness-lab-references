# -*- coding: utf-8 -*-
"""C10 item 3: named-record checks. Read originals independently."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c10_common import *

facts = load_jsonl(LIB / "事实层.jsonl")
bans = load_jsonl(LIB / "禁用表.jsonl")
aa = RAW / "镜序" / "action-annotation"

def dump(o):
    return json.dumps(o, ensure_ascii=False)

def find_facts(pred):
    return [r for r in facts if pred(r)]

def find_bans(pred):
    return [r for r in bans if pred(r)]

conn = open_sqlite_ro(RAW / "镜序" / "learning.sqlite3")

def rule(rid):
    row = conn.execute("SELECT id, status, reviewer, created, payload FROM rules WHERE id=?", (rid,)).fetchone()
    if not row:
        return None
    pay = json.loads(row["payload"]) if row["payload"] else {}
    return {"id": row["id"], "status": row["status"], "reviewer": row["reviewer"], "created": row["created"], "payload": pay}

checks = []

def add(name, ok, detail):
    checks.append({"name": name, "ok": ok, "detail": detail})

# 1) 二印小区厨卫 人物出镜 主要人物不是阿明
v2 = rule("confirmed-V2")
v2_facts = find_facts(lambda r: r.get("来源条目标识")=="confirmed-V2" or r.get("样例编号")=="V2")
ok = False
detail = {}
if v2 and v2_facts:
    f = v2_facts[0]
    pay = v2["payload"]
    path_ok = "二印小区厨卫" in (f.get("主库相对路径") or "") and "人物出镜" in (f.get("主库相对路径") or "")
    ev = str(pay.get("evidence") or "")
    text_ok = "主要人物" in ev and "不是" in ev and "阿明" in ev
    in_limit = ev in (f.get("限定语原文") or "") or ev in dump(f)
    times_ok = f.get("起秒")==pay.get("start") and f.get("止秒")==pay.get("end")
    # 0-8
    times_ok = times_ok or (float(f.get("起秒") or -1)==float(pay.get("start")) and float(f.get("止秒") or -1)==float(pay.get("end")))
    neg_ok = f.get("是否反例") is True
    asset_ok = f.get("镜序素材ID")==pay.get("asset_id")
    ok = path_ok and text_ok and in_limit and times_ok and neg_ok and asset_ok and len(v2_facts)==1
    detail = {
        "facts": [f.get("事实编号") for f in v2_facts],
        "path": f.get("主库相对路径"),
        "times": [f.get("起秒"), f.get("止秒")],
        "src_times": [pay.get("start"), pay.get("end")],
        "evidence": ev,
        "asset": pay.get("asset_id"),
        "是否反例": f.get("是否反例"),
        "checks": {"path_ok": path_ok, "text_ok": text_ok, "in_limit": in_limit, "times_ok": times_ok, "neg_ok": neg_ok, "asset_ok": asset_ok},
    }
else:
    detail = {"v2_rule_found": bool(v2), "facts": [x.get("事实编号") for x in v2_facts]}
add("二印小区厨卫\\人物出镜 一段主要人物不是阿明", ok, detail)

# 2) 两条“这是水洗石”
# originals: P21, P22 product identity 水洗石
p21 = rule("confirmed-P21")
p22 = rule("confirmed-P22")
f21 = find_facts(lambda r: r.get("来源条目标识")=="confirmed-P21")
f22 = find_facts(lambda r: r.get("来源条目标识")=="confirmed-P22")

def water_ok(ruleobj, flist):
    if not ruleobj or len(flist)!=1:
        return False, {"rule": bool(ruleobj), "n": len(flist)}
    f=flist[0]; pay=ruleobj["payload"]
    prod = str(pay.get("product_identity") or "")
    ev = pay.get("evidence")
    evs = ev if isinstance(ev, list) else [ev]
    ev_text = dump(ev)
    has_water = "水洗石" in prod or "水洗石" in ev_text or "水洗石" in dump(pay)
    times_ok = float(f.get("起秒"))==float(pay.get("start")) and float(f.get("止秒"))==float(pay.get("end"))
    asset_ok = f.get("镜序素材ID")==pay.get("asset_id")
    # exact phrase 这是水洗石 may not appear; require 水洗石 identity preserved
    preserved = "水洗石" in (f.get("限定语原文") or "") and "水洗石" in dump(f.get("内容"))
    okk = has_water and times_ok and asset_ok and preserved
    return okk, {
        "事实编号": f.get("事实编号"),
        "path": f.get("主库相对路径"),
        "product_identity": prod,
        "evidence": ev,
        "times": [f.get("起秒"), f.get("止秒"), pay.get("start"), pay.get("end")],
        "phrase_这是水洗石_in_source": "这是水洗石" in dump(pay),
        "has_water": has_water, "times_ok": times_ok, "asset_ok": asset_ok, "preserved": preserved,
    }

ok21, d21 = water_ok(p21, f21)
ok22, d22 = water_ok(p22, f22)
add("两条“这是水洗石”的记录", ok21 and ok22, {
    "说明": "原文没有一字不差的“这是水洗石”，而是 product_identity=水洗石，evidence 写“材料不是微陶泥，是其他材料叫水洗石”。事实层保留了这两条（P21、P22）。",
    "P21": d21, "P22": d22,
})

# 3) 一条“本片段不是微陶泥”
p3 = rule("confirmed-P3")
f3 = find_facts(lambda r: r.get("来源条目标识")=="confirmed-P3")
ok=False; detail={}
if p3 and f3:
    f=f3[0]; pay=p3["payload"]
    # look for exact phrase in payload
    phrase="本片段不是微陶泥"
    in_src = phrase in dump(pay)
    in_out = phrase in (f.get("限定语原文") or "") or phrase in dump(f.get("内容"))
    times_ok = float(f.get("起秒"))==float(pay.get("start")) and float(f.get("止秒"))==float(pay.get("end"))
    asset_ok = f.get("镜序素材ID")==pay.get("asset_id")
    ok = in_src and in_out and times_ok and asset_ok
    # 是否反例 is False in T10 output — record as note, not necessarily fail named check if content is present
    detail = {
        "事实编号": f.get("事实编号"),
        "path": f.get("主库相对路径"),
        "phrase_in_source": in_src,
        "phrase_in_output": in_out,
        "product_identity": pay.get("product_identity"),
        "evidence": pay.get("evidence"),
        "context": pay.get("context"),
        "times": [f.get("起秒"), f.get("止秒")],
        "是否反例": f.get("是否反例"),
        "note_是否反例": "原文明确“本片段不是微陶泥”，事实层 是否反例=false，作为另外发现的问题记录，不作为本条点名“找不到”失败。",
    }
add("一条“本片段不是微陶泥”的记录", ok, detail)

# 4) P24 先取料后批刮 两个区间
p24 = load_json(aa / "P24-boundary-proposal.json")["rows"]
fa = find_facts(lambda r: r.get("来源条目标识")=="P24-A")
fb = find_facts(lambda r: r.get("来源条目标识")=="P24-B")

def p24_check(sid, flist):
    src = next((r for r in p24 if r.get("sample_id")==sid), None)
    if not src or len(flist)!=1:
        return False, {"src": bool(src), "n": len(flist)}
    f=flist[0]
    st=(src.get("source") or {}).get("start")
    en=(src.get("source") or {}).get("end")
    action=src.get("confirmed_action") or src.get("suggested_action")
    times_ok = float(f.get("起秒"))==float(st) and float(f.get("止秒"))==float(en)
    action_in = action in dump(f.get("内容")) or action in (f.get("限定语原文") or "")
    # path same file
    return times_ok and action_in, {
        "事实编号": f.get("事实编号"),
        "action": action,
        "src_times": [st, en],
        "out_times": [f.get("起秒"), f.get("止秒")],
        "path": f.get("主库相对路径"),
        "times_ok": times_ok, "action_in": action_in,
        "confirmed_label": src.get("confirmed_label"),
    }

oka, da = p24_check("P24-A", fa)
okb, db = p24_check("P24-B", fb)
# order: 取料 then 批刮
order_ok = False
if oka and okb:
    order_ok = ("取料" in str(da.get("action")) and "批刮" in str(db.get("action")) and float(da["src_times"][0]) < float(db["src_times"][0]))
add("P24 一段里先取料后批刮、分成两个区间", oka and okb and order_ok, {"P24-A": da, "P24-B": db, "order_ok": order_ok})

# 5) 汉阳月印府(6.7全屋)\美女人设 出镜人禁用
restr = load_json(aa / "person-usage-restrictions.json")
rules = restr.get("rules") or []
r09_src = None
for r in rules:
    if r.get("reference_sample")=="R09" or r.get("rule_id")=="R09-person-no-production" or "离职" in dump(r):
        r09_src = r
        break
ban_hits = find_bans(lambda b: "美女人设" in (b.get("主库相对路径") or "") or "R09" in str(b.get("规则ID") or "") or "R09" in str(b.get("来源条目标识") or ""))
f_r09 = find_facts(lambda r: r.get("来源条目标识")=="confirmed-R09")
ok=False
if r09_src and ban_hits:
    b=ban_hits[0]
    ev = r09_src.get("evidence") or ""
    ev_ok = ev and ev in (b.get("禁用原文") or "") or ev in dump(b)
    path_ok = "汉阳月印府" in (b.get("主库相对路径") or "") and "美女人设" in (b.get("主库相对路径") or "")
    # times
    src_src = r09_src.get("reference_source") or {}
    times_ok = b.get("起秒")==src_src.get("start") and b.get("止秒")==src_src.get("end")
    intercept_note = "还没把它接进拦截" in dump(b) or "未接入正式工具" in dump(b)
    ok = ev_ok and path_ok and times_ok and intercept_note
    detail = {
        "ban_ids": [x.get("规则ID") for x in ban_hits],
        "path": b.get("主库相对路径"),
        "禁用原文": b.get("禁用原文"),
        "source_evidence": ev,
        "source_decision": r09_src.get("decision"),
        "times": [b.get("起秒"), b.get("止秒"), src_src.get("start"), src_src.get("end")],
        "拦截说明": b.get("镜序拦截说明"),
        "also_in_facts": [x.get("事实编号") for x in f_r09],
        "ev_ok": ev_ok, "path_ok": path_ok, "times_ok": times_ok, "intercept_note": intercept_note,
    }
else:
    detail = {"src_found": bool(r09_src), "bans": len(ban_hits)}
add("汉阳月印府(6.7全屋)\\美女人设 出镜人禁用", ok, detail)

# 6) P17 是微陶泥但不是批刮，定义来自用户纠正
p17 = rule("confirmed-P17")
f17 = find_facts(lambda r: r.get("来源条目标识")=="confirmed-P17")
scrape = load_json(aa / "scraping-label-rule.json")
ok=False; detail={}
if p17 and f17:
    f=f17[0]; pay=p17["payload"]
    ev=str(pay.get("evidence") or "")
    # 第一确实的微陶泥，第二但不是在批刮
    ev_ok = "微陶泥" in ev and "不是在批刮" in ev
    ev_in = ev in (f.get("限定语原文") or "") or ev in dump(f.get("内容"))
    times_ok = float(f.get("起秒"))==float(pay.get("start")) and float(f.get("止秒"))==float(pay.get("end"))
    # scraping-label-rule should mention P17 and user correction; not required to be a fact itself
    rule_src_ok = "P17" in dump(scrape) and "用户" in dump(scrape)
    # 内容 should keep both: 微陶泥 material positive, 批刮 action negative
    content_ok = "微陶泥" in dump(f) and "不是在批刮" in dump(f)
    ok = ev_ok and ev_in and times_ok and content_ok
    detail = {
        "事实编号": f.get("事实编号"),
        "path": f.get("主库相对路径"),
        "evidence": ev,
        "product_identity": pay.get("product_identity"),
        "context": pay.get("context"),
        "times": [f.get("起秒"), f.get("止秒")],
        "scraping_label_rule_source": scrape.get("source"),
        "scraping_definition": scrape.get("definition"),
        "是否反例": f.get("是否反例"),
        "ev_ok": ev_ok, "ev_in": ev_in, "times_ok": times_ok, "content_ok": content_ok, "rule_src_ok": rule_src_ok,
    }
add("P17 是微陶泥但不是批刮（批刮定义来自用户纠正）", ok, detail)

conn.close()

result = {
    "item": 3,
    "pass": all(c["ok"] for c in checks),
    "failed": [c["name"] for c in checks if not c["ok"]],
    "checks": checks,
    "need_report_likang": any(not c["ok"] for c in checks),
    "need_report_reason": "第3项点名的记录有找不到的或与原文不一致" if any(not c["ok"] for c in checks) else "",
}
dump_json(MID / "item3_named.json", result)
print("ITEM3 pass=", result["pass"], "failed=", result["failed"])
for c in checks:
    print(("OK  " if c["ok"] else "FAIL"), c["name"])
