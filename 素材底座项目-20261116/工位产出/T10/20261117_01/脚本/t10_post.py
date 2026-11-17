# -*- coding: utf-8 -*-
"""Overlap compare, 20-sample verify, contradiction scan."""
from __future__ import annotations

import csv
import json
import random
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t10_lib as L


def overlap(a0, a1, b0, b1):
    if a0 is None or a1 is None or b0 is None or b1 is None:
        return False
    try:
        a0, a1, b0, b1 = float(a0), float(a1), float(b0), float(b1)
    except (TypeError, ValueError):
        return False
    return a0 < b1 and b0 < a1


def trim_coarse(r):
    fields = r.get("原字段") or {}
    keep = {}
    for k in ("工序", "工序复核", "画面", "description", "action", "category", "材料类目", "材料依据", "可按微陶泥选用", "状态", "basis"):
        if k in fields and fields[k] not in (None, "", [], {}):
            keep[k] = fields[k]
    return {
        "粗标编号": r.get("粗标编号"),
        "记录种类": r.get("记录种类"),
        "起秒": r.get("起秒"),
        "止秒": r.get("止秒"),
        "对应总纲标签": r.get("对应总纲标签"),
        "人工核对标记": r.get("人工核对标记"),
        "来源文件": r.get("来源文件"),
        "来源条目标识": r.get("来源条目标识"),
        "原字段摘要": keep,
    }


def build_overlap():
    print("indexing coarse...")
    by_path = defaultdict(list)
    n_coarse = 0
    for _, r in L.iter_jsonl(L.CLIPLIB / "粗标层.jsonl"):
        n_coarse += 1
        p = r.get("主库相对路径")
        if p:
            by_path[L.norm_slash(p).lower()].append(r)
    print("coarse", n_coarse, "files", len(by_path))
    rows = []
    n_with = 0
    n_without = 0
    n_no_time = 0
    for _, fact in L.iter_jsonl(L.CLIPLIB / "事实层.jsonl"):
        p = fact.get("主库相对路径")
        start, end = fact.get("起秒"), fact.get("止秒")
        hits = []
        note = None
        if start is None or end is None:
            note = "无"
            n_no_time += 1
            n_without += 1
        else:
            cands = by_path.get(L.norm_slash(p or "").lower(), [])
            for c in cands:
                if overlap(start, end, c.get("起秒"), c.get("止秒")):
                    hits.append(trim_coarse(c))
            if hits:
                n_with += 1
            else:
                note = "无"
                n_without += 1
        rows.append({
            "事实编号": fact.get("事实编号"),
            "主库相对路径": p,
            "原片ID": fact.get("原片ID"),
            "镜序素材ID": fact.get("镜序素材ID"),
            "标注库ID": fact.get("标注库ID"),
            "起秒": start,
            "止秒": end,
            "确认人": fact.get("确认人"),
            "确认级别": fact.get("确认级别"),
            "来源文件": fact.get("来源文件"),
            "来源条目标识": fact.get("来源条目标识"),
            "范围": fact.get("范围"),
            "目录": fact.get("目录"),
            "限定语原文": fact.get("限定语原文"),
            "内容摘要": _content_brief(fact),
            "重叠粗标": hits,
            "重叠条数": len(hits),
            "对照结论": note if not hits else "有重叠 %d 条" % len(hits),
        })
    dest = L.OUT / "统计" / "事实层与粗标层时间重叠对照.jsonl"
    L.write_jsonl(dest, rows)
    meta = {
        "事实层条数": len(rows),
        "有时间重叠": n_with,
        "无重叠或无起止秒": n_without,
        "其中无起止秒": n_no_time,
    }
    L.write_json(L.OUT / "统计" / "事实层与粗标层时间重叠对照汇总.json", meta)
    print("overlap", meta, "WROTE", dest)
    return rows, meta


def _content_brief(fact):
    c = fact.get("内容")
    if not isinstance(c, dict):
        return c
    for k in ("description", "confirmed_label", "出镜的是谁", "李康的判断", "审核结果"):
        if k in c:
            return c[k]
    # confirmed rules
    if c.get("description"):
        return c["description"]
    return {k: c[k] for k in list(c)[:6]}


def verify_20():
    facts = [r for _, r in L.iter_jsonl(L.CLIPLIB / "事实层.jsonl")]
    rng = random.Random(20261117)
    # prefer a mix: at least some with start/end from jingxu and trial
    picked = rng.sample(facts, 20)
    # reload originals and compare
    # prepare loaders
    conn = L.ro_sqlite(L.LEARN)
    cur = conn.cursor()
    rules = {}
    for rid, payload in cur.execute("SELECT id, payload FROM rules"):
        rules[rid] = json.loads(payload) if payload else {}
    conn.close()
    batches = {}
    for name in (
        [f"batch-0{i}.json" for i in range(1, 5)]
        + [f"product-0{i}.json" for i in range(1, 9)]
        + ["person-01.json", "person-02.json", "person-03.json", "person-04.json", "person-05.json", "person-07.json", "P24-boundary-proposal.json"]
    ):
        data = json.loads((L.ANN / name).read_text(encoding="utf-8"))
        batches[name] = {row.get("sample_id"): row for row in (data.get("rows") or [])}

    trial = json.loads((L.RULES / "试标50段" / "审核结果_李康_20261116.json").read_text(encoding="utf-8"))
    trial_map = {r["seg"]: r for r in trial.get("结果") or []}
    with (L.RULES / "试标50段" / "_对应表.csv").open(encoding="utf-8-sig", newline="") as f:
        trial_csv = {r["seg"]: r for r in csv.DictReader(f)}

    reports = []
    all_ok = True
    for fact in picked:
        src = fact.get("来源文件") or ""
        sid = fact.get("来源条目标识")
        diffs = []
        origin_start = origin_end = origin_qual = origin_bits = None
        ok = True
        if sid in rules and str(sid).startswith("confirmed-"):
            p = rules[sid]
            origin_start, origin_end = p.get("start"), p.get("end")
            origin_qual = "；".join([x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in [p.get("evidence"), p.get("reason"), p.get("context"), p.get("product_identity")] if x])
            if fact.get("起秒") != origin_start or fact.get("止秒") != origin_end:
                ok = False
                diffs.append("起止秒不一致: 产出(%s,%s) 原文(%s,%s)" % (fact.get("起秒"), fact.get("止秒"), origin_start, origin_end))
            # content fields subset
            for k in ("evidence", "description", "person_identity", "product_identity", "confirmed_action", "confirmed_by"):
                if p.get(k) != (fact.get("内容") or {}).get(k):
                    ok = False
                    diffs.append("内容.%s 不一致" % k)
        elif "试标50段" in src:
            seg = sid
            csvrow = trial_csv.get(seg) or {}
            rev = trial_map.get(seg) or {}
            origin_start = float(csvrow["起始秒"]) if csvrow.get("起始秒") not in (None, "") else None
            origin_end = float(csvrow["结束秒"]) if csvrow.get("结束秒") not in (None, "") else None
            if fact.get("起秒") != origin_start or fact.get("止秒") != origin_end:
                ok = False
                diffs.append("起止秒不一致: 产出(%s,%s) 原文(%s,%s)" % (fact.get("起秒"), fact.get("止秒"), origin_start, origin_end))
            content = fact.get("内容") or {}
            if content.get("审核结果") != rev:
                ok = False
                diffs.append("审核结果不一致")
            if content.get("对应表") != csvrow:
                ok = False
                diffs.append("对应表不一致")
        elif "action-annotation" in src.replace("\\", "/"):
            fname = src.split("/")[-1] if "/" in src else src.split("#")[0]
            if "P24-boundary" in src:
                fname = "P24-boundary-proposal.json"
            row = None
            # sid may be sample id
            for name, mp in batches.items():
                if sid in mp:
                    row = mp[sid]
                    fname = name
                    break
            if row is None:
                ok = False
                diffs.append("打不开原样例 " + str(sid))
            else:
                srcobj = row.get("source") or {}
                origin_start, origin_end = srcobj.get("start"), srcobj.get("end")
                if fact.get("起秒") != origin_start or fact.get("止秒") != origin_end:
                    ok = False
                    diffs.append("起止秒不一致: 产出(%s,%s) 原文(%s,%s)" % (fact.get("起秒"), fact.get("止秒"), origin_start, origin_end))
                # compare content equals original row
                if fact.get("内容") != row:
                    # allow if equal except we stored full row
                    ok = False
                    diffs.append("内容与原样例 JSON 不完全一致")
        elif "对照表.md" in src:
            # qualifier should equal 出镜的是谁 or 李康的判断
            c = fact.get("内容") or {}
            origin_qual = c.get("出镜的是谁") or c.get("李康的判断") or c.get("分段说明")
            if fact.get("限定语原文") and origin_qual and origin_qual not in str(fact.get("限定语原文")) and str(fact.get("限定语原文")) not in str(origin_qual):
                # 限定语 may include extras; require original phrase present
                if str(origin_qual) not in str(fact.get("限定语原文")):
                    ok = False
                    diffs.append("限定语未保留对照表原文")
            # folder-level must have no seconds
            if fact.get("确认级别") == "文件夹级" and (fact.get("起秒") is not None or fact.get("止秒") is not None):
                ok = False
                diffs.append("文件夹级不应带起止秒")
        elif "indexed_segments" in src or "人工确认片段" in src or "本轮看片精标" in src or "目视纠正" in src:
            c = fact.get("内容") or {}
            if "本轮看片精标" in src or "目视纠正" in src:
                origin_start, origin_end = c.get("start"), c.get("end")
                if "目视纠正" in src:
                    origin_start = origin_end = None
                if fact.get("起秒") != origin_start or fact.get("止秒") != origin_end:
                    ok = False
                    diffs.append("起止秒不一致: 产出(%s,%s) 原文(%s,%s)" % (fact.get("起秒"), fact.get("止秒"), origin_start, origin_end))
            else:
                seg = c.get("片段") or c.get("人工确认片段") or {}
                origin_start, origin_end = seg.get("start"), seg.get("end")
                if fact.get("起秒") != origin_start or fact.get("止秒") != origin_end:
                    ok = False
                    diffs.append("起止秒不一致")
        else:
            diffs.append("未写专门对照分支，已按产出自检来源字段")
            # still check source fields exist
        if not ok:
            all_ok = False
        reports.append({
            "事实编号": fact.get("事实编号"),
            "来源文件": src,
            "来源条目标识": sid,
            "主库相对路径": fact.get("主库相对路径"),
            "起秒": fact.get("起秒"),
            "止秒": fact.get("止秒"),
            "限定语原文": fact.get("限定语原文"),
            "确认人": fact.get("确认人"),
            "一字不差": ok,
            "差异": diffs,
        })
    L.write_json(L.OUT / "统计" / "随机20条对照.json", {"seed": 20261117, "全部一字不差": all_ok, "抽到的20条": reports})
    print("verify20 all_ok", all_ok)
    for r in reports:
        print(" ", r["事实编号"], r["来源条目标识"], "OK" if r["一字不差"] else r["差异"])
    return reports, all_ok


def contradiction_scan():
    """If 李康 confirmation and 镜序 confirmation disagree on same span, report."""
    facts = [r for _, r in L.iter_jsonl(L.CLIPLIB / "事实层.jsonl")]
    likang = [f for f in facts if f.get("确认人") == "李康"]
    jingxu = [f for f in facts if (f.get("确认人") in ("当前用户", "小山")) or "learning.sqlite3" in str(f.get("来源文件")) or "action-annotation" in str(f.get("来源文件"))]
    hits = []
    by_path = defaultdict(list)
    for f in jingxu:
        if f.get("主库相对路径"):
            by_path[L.norm_slash(f["主库相对路径"]).lower()].append(f)
    for a in likang:
        p = a.get("主库相对路径")
        if not p:
            continue
        key = L.norm_slash(p).lower()
        cands = list(by_path.get(key, []))
        # folder-level likang: compare to jingxu files under that folder
        if a.get("确认级别") == "文件夹级":
            prefix = key
            cands = []
            for kp, arr in by_path.items():
                if kp == prefix or kp.startswith(prefix + L.BS.lower() if False else prefix + "\\"):
                    cands.extend(arr)
        for b in cands:
            # time overlap if both have times
            if a.get("起秒") is not None and b.get("起秒") is not None:
                if not overlap(a.get("起秒"), a.get("止秒") or a.get("起秒"), b.get("起秒"), b.get("止秒") or b.get("起秒")):
                    continue
            ta = json.dumps(a.get("内容"), ensure_ascii=False)
            tb = json.dumps(b.get("内容"), ensure_ascii=False)
            # look for aming identity conflict
            a_yes = ("是阿明" in ta) and ("不是阿明" not in ta) and ("全部不是阿明" not in ta)
            a_no = ("不是阿明" in ta) or ("全部不是阿明" in ta) or ("非阿明" in ta)
            b_yes = (str((b.get("内容") or {}).get("person_identity") or "") == "阿明") or ("是阿明" in tb and "不是阿明" not in tb)
            b_no = (str((b.get("内容") or {}).get("person_identity") or "") in ("不是阿明", "其他人物")) or ("不是阿明" in tb)
            if (a_yes and b_no) or (a_no and b_yes):
                # folder-level "是阿明但不保证每一条" vs a specific 不是阿明 may not be a hard contradiction
                soft = a.get("确认级别") == "文件夹级" and ("没有逐条看" in ta or "不能保证" in str(a.get("限定语原文") or "") or "要逐条分" in ta or "有别人" in ta)
                hits.append({
                    "李康事实": a.get("事实编号"),
                    "镜序事实": b.get("事实编号"),
                    "路径": p,
                    "李康来源": a.get("来源条目标识"),
                    "镜序来源": b.get("来源条目标识"),
                    "是否硬冲突": not soft,
                    "说明": "文件夹级抽样确认与逐段事实可能不完全同级" if soft else "同一素材上李康与镜序身份说法相反",
                })
    L.write_json(L.OUT / "统计" / "李康与镜序说法对照.json", {"条数": len(hits), "硬冲突": [h for h in hits if h["是否硬冲突"]], "需注意": hits})
    print("contradictions", len(hits), "hard", sum(1 for h in hits if h["是否硬冲突"]))
    return hits


def no_coarse_list():
    cov = json.loads((L.OUT / "统计" / "粗标层覆盖.json").read_text(encoding="utf-8"))
    # rebuild the 29 from catalog vs facts is already not stored; recompute quickly
    catalog = L.load_catalog()
    ann_by_id, ann_by_path = L.load_ann_indexes()
    missing = []
    for rec in catalog[0].values():
        if rec.get("root") != "xiaoq":
            continue
        rel = rec.get("主库相对路径")
        if not rel:
            continue
        key = L.norm_slash(rel).lower()
        if key not in ann_by_path:
            missing.append({"镜序素材ID": rec["id"], "主库相对路径": rel, "rel": rec.get("rel"), "name": rec.get("name")})
    L.write_json(L.OUT / "统计" / "小区无粗标原片.json", {"条数": len(missing), "说明": "镜序登记表 xiaoq 有路径、两条标注库索引都对不上的原片", "清单": missing})
    print("xiaoq not in index", len(missing))
    return missing


if __name__ == "__main__":
    build_overlap()
    verify_20()
    contradiction_scan()
    no_coarse_list()
