# -*- coding: utf-8 -*-
"""检索结果与事实层自动对一遍。"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8))
ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
BATCH = ROOT / "工位产出" / "T12" / "20261118_01"
MAP_CSV = BATCH / "编号对应表.csv"
CONCAT_CSV = BATCH / "拼接清单_重编码.csv"
RESULT_JSONL = BATCH / "检索结果.jsonl"
FACT_JSONL = ROOT / "片段库" / "事实层.jsonl"
OUT_CSV = BATCH / "事实层自动对照表.csv"
OUT_JSON = BATCH / "统计" / "事实层自动对照.json"

# 查询画面类型 -> 事实层动作关键词（正例匹配）
POS_PATTERNS = {
    "V05": [r"批刮", r"抹平", r"墙面基面上的批刮", r"基面批刮"],
    "V06": [r"滚涂", r"罩面"],
    "V11": [r"材料桶", r"取料", r"搅拌"],
    "V08": [r"拆砸", r"拆砖", r"砸墙", r"铲除", r"贴砖"],
    "V07": [r"铲修", r"铲墙", r"铲除"],
}
# 明确反例：事实层确认是其他动作，却被查成某类
NEG_FOR = {
    "V05": [r"取料", r"滚涂", r"打磨", r"罩面", r"讲解", r"样板", r"非批刮", r"非施工", r"清洁", r"覆膜"],
    "V06": [r"批刮", r"取料", r"打磨", r"非施工"],
}


def now_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"


def load_map() -> dict[str, dict]:
    rows = list(csv.DictReader(MAP_CSV.open(encoding="utf-8-sig")))
    by_name = {}
    by_oid = {}
    by_path = {}
    for r in rows:
        name = r.get("文件名") or ""
        if name:
            by_name[name] = r
            by_name[name.replace(".mp4", "")] = r
        oid = r.get("原片ID") or ""
        if oid:
            by_oid[oid] = r
        rel = (r.get("主库相对路径") or "").replace("/", "\\").lower()
        if rel:
            by_path[rel] = r
    return {"by_name": by_name, "by_oid": by_oid, "by_path": by_path}


def load_concat() -> dict[str, list[dict]]:
    if not CONCAT_CSV.exists():
        return {}
    groups = defaultdict(list)
    for r in csv.DictReader(CONCAT_CSV.open(encoding="utf-8-sig")):
        groups[r["合成文件名"]].append(r)
    return groups


def fact_action_text(rec: dict) -> str:
    c = rec.get("内容") or {}
    parts = []
    if isinstance(c, dict):
        for k in ("confirmed_action", "context", "description", "evidence", "product_identity"):
            v = c.get(k)
            if v:
                parts.append(str(v))
    if rec.get("限定语原文"):
        parts.append(str(rec["限定语原文"]))
    return " ".join(parts)


def overlaps(a0: float, a1: float, b0: float, b1: float) -> bool:
    return max(a0, b0) < min(a1, b1)


def local_to_original_span(local_name: str, start: float, end: float, concat: dict[str, list[dict]], mp) -> list[tuple[str, float, float, str]]:
    """Map a result span back to original copy / 原片ID spans. Returns list of (原片ID, start, end, 副本文件名)."""
    if local_name in concat:
        out = []
        for m in concat[local_name]:
            cs = float(m["合成内起始秒"])
            ce = float(m["合成内结束秒"])
            if overlaps(start, end, cs, ce):
                # clip overlap into member-local time
                o0 = max(0.0, start - cs)
                o1 = min(float(m["归一化时长秒"] or m["副本时长秒"] or 0) or (ce - cs), end - cs)
                if o1 > o0:
                    out.append((m.get("原片ID") or "", o0, o1, m.get("副本文件名") or ""))
        return out
    # plain copy
    info = mp["by_name"].get(local_name) or mp["by_name"].get(local_name.replace(".mp4", ""))
    oid = (info or {}).get("原片ID") or ""
    return [(oid, start, end, local_name)]


def main() -> int:
    mp = load_map()
    concat = load_concat()
    facts = [json.loads(l) for l in FACT_JSONL.open(encoding="utf-8") if l.strip()]
    # only 范围内
    facts = [f for f in facts if f.get("范围") == "范围内"]

    # index facts by 原片ID
    by_oid: dict[str, list[dict]] = defaultdict(list)
    for f in facts:
        oid = f.get("原片ID") or ""
        if oid:
            by_oid[oid].append(f)

    results = []
    if RESULT_JSONL.exists():
        with RESULT_JSONL.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))

    # group queries by 画面类型代码
    by_code: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r.get("status") not in {"ok", "empty"}:
            continue
        by_code[r.get("画面类型代码") or ""].append(r)

    rows = []
    detail = {}
    for code, qs in sorted(by_code.items()):
        name = qs[0].get("画面类型") or code
        pos_res = []
        neg_wrong = []
        # collect all top10 hits as (oid, start, end, query_id)
        hits = []
        for q in qs:
            for item in q.get("results") or []:
                local = item.get("副本文件名") or ""
                try:
                    st = float(item.get("start") or 0)
                    en = float(item.get("end") or 0)
                except (TypeError, ValueError):
                    continue
                spans = local_to_original_span(local, st, en, concat, mp)
                for oid, o0, o1, copy_name in spans:
                    hits.append({
                        "查询编号": q.get("查询编号"),
                        "查询文本": q.get("查询文本"),
                        "副本文件名": local,
                        "映射副本": copy_name,
                        "原片ID": oid,
                        "start": o0,
                        "end": o1,
                        "score": item.get("score"),
                    })

        # positives: facts whose action matches this type
        pats = POS_PATTERNS.get(code, [])
        pos_facts = []
        for f in facts:
            if f.get("是否反例"):
                continue
            text = fact_action_text(f)
            if pats and any(re.search(p, text) for p in pats):
                pos_facts.append(f)
            elif not pats:
                # no explicit confirmed_action mapping for this visual type
                pass

        found_pos = []
        for f in pos_facts:
            oid = f.get("原片ID") or ""
            try:
                fs, fe = float(f.get("起秒") or 0), float(f.get("止秒") or 0)
            except (TypeError, ValueError):
                continue
            for h in hits:
                if h["原片ID"] == oid and overlaps(h["start"], h["end"], fs, fe):
                    found_pos.append({"事实编号": f.get("事实编号"), "hit": h})
                    break

        # negatives: facts that are explicitly NOT this action, but hit top10
        neg_pats = NEG_FOR.get(code, [])
        neg_facts = []
        for f in facts:
            text = fact_action_text(f)
            if f.get("是否反例") and pats and any(re.search(p, text) for p in pats):
                # counterexample labeled as this type? treat as negative target for presence
                neg_facts.append(f)
            elif neg_pats and any(re.search(p, text) for p in neg_pats):
                # confirmed other action
                # exclude if also matches positive
                if pats and any(re.search(p, text) for p in pats):
                    continue
                neg_facts.append(f)

        wrong = []
        for f in neg_facts:
            oid = f.get("原片ID") or ""
            try:
                fs, fe = float(f.get("起秒") or 0), float(f.get("止秒") or 0)
            except (TypeError, ValueError):
                continue
            for h in hits:
                if h["原片ID"] == oid and overlaps(h["start"], h["end"], fs, fe):
                    wrong.append({"事实编号": f.get("事实编号"), "动作文本": fact_action_text(f)[:120], "hit": h})
                    break

        note = ""
        if len(pos_facts) < 5:
            note = "样本不足"
        if not pats:
            note = (note + "；" if note else "") + "本类在事实层没有稳定的 confirmed_action 映射，正例按规则标为不可自动对照"

        row = {
            "画面类型代码": code,
            "画面类型": name,
            "查询条数": len(qs),
            "事实层正例数": len(pos_facts) if pats else 0,
            "正例进入前10数": len(found_pos) if pats else "",
            "事实层反例/他动作数": len(neg_facts),
            "反例错进前10数": len(wrong),
            "备注": note or ("有映射" if pats else "无动作映射"),
        }
        rows.append(row)
        detail[code] = {
            **row,
            "正例事实编号": [f.get("事实编号") for f in pos_facts],
            "命中正例": found_pos,
            "错进": wrong,
        }

    fields = ["画面类型代码", "画面类型", "查询条数", "事实层正例数", "正例进入前10数", "事实层反例/他动作数", "反例错进前10数", "备注"]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps({"时间": now_str(), "按类": detail}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写了 {OUT_CSV} 共 {len(rows)} 类")
    for r in rows:
        print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
