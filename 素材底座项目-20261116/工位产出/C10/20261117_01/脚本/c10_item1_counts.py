# -*- coding: utf-8 -*-
"""C10 item 1: recount original files vs T10 outputs. Independent of T10 converters."""
from __future__ import annotations

import collections
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c10_common import *

aa = RAW / "镜序" / "action-annotation"
result = {"item": 1, "source_counts": {}, "output_counts": {}, "comparisons": [], "notes": []}


def add_cmp(name, source_n, output_n, expected_known, t10_claim, explanation_ok, detail):
    entry = {
        "name": name,
        "source_n": source_n,
        "output_n": output_n,
        "known_n": expected_known,
        "t10_claim": t10_claim,
        "equal_or_explained": explanation_ok,
        "detail": detail,
    }
    result["comparisons"].append(entry)
    return entry


# ---------- source counts ----------
conn = open_sqlite_ro(RAW / "镜序" / "learning.sqlite3")
rules = list(conn.execute("SELECT id, status, reviewer, created, payload FROM rules"))
feedback = list(conn.execute("SELECT id FROM feedback"))
adoptions = list(conn.execute("SELECT id, action FROM adoptions"))
runs = list(conn.execute("SELECT id FROM runs"))
confirmed = [r for r in rules if r["id"].startswith("confirmed-")]
approved = [r for r in rules if r["status"] == "approved"]
result["source_counts"]["rules_total"] = len(rules)
result["source_counts"]["rules_approved"] = len(approved)
result["source_counts"]["confirmed_facts"] = len(confirmed)
result["source_counts"]["confirmed_ids"] = [r["id"] for r in confirmed]
result["source_counts"]["feedback"] = len(feedback)
result["source_counts"]["adoptions"] = len(adoptions)
result["source_counts"]["adoptions_by_action"] = dict(collections.Counter(r["action"] for r in adoptions))
result["source_counts"]["runs"] = len(runs)
# 36 vs 33
ev = load_json(RAW / "镜序" / "identity-evidence.json")
segs = ev["segments"] if isinstance(ev, dict) else ev
snap_ids = []
for s in segs:
    sid = s.get("id") or s.get("sample_id")
    snap_ids.append(sid)
result["source_counts"]["identity_evidence_segments"] = len(segs)
result["source_counts"]["identity_evidence_ids"] = snap_ids
conf_ids = [r["id"] for r in confirmed]
# snapshot items may use sample_id like P1 not confirmed-P1
snap_set = set()
for s in segs:
    if s.get("id"):
        snap_set.add(s["id"])
    if s.get("sample_id"):
        snap_set.add(s["sample_id"])
        snap_set.add("confirmed-" + str(s["sample_id"]))
missing_in_snap = [i for i in conf_ids if i not in snap_set and i.replace("confirmed-", "") not in snap_set]
result["source_counts"]["confirmed_missing_from_snapshot"] = missing_in_snap
# created times for those three
miss_meta = []
for r in confirmed:
    if r["id"] in missing_in_snap:
        pay = json.loads(r["payload"]) if r["payload"] else {}
        miss_meta.append({
            "id": r["id"],
            "created": r["created"],
            "sample_id": pay.get("sample_id"),
            "source_record": pay.get("source_record"),
            "asset_id": pay.get("asset_id"),
            "start": pay.get("start"),
            "end": pay.get("end"),
            "evidence": pay.get("evidence"),
        })
result["source_counts"]["snapshot_gap_meta"] = miss_meta
conn.close()

connc = open_sqlite_ro(RAW / "镜序" / "catalog.sqlite3")
n_assets = connc.execute("SELECT COUNT(*) FROM assets").fetchone()[0]
roots = {r[0]: r[1] for r in connc.execute("SELECT root, COUNT(*) FROM assets GROUP BY root")}
result["source_counts"]["catalog_assets"] = n_assets
result["source_counts"]["catalog_roots"] = roots
connc.close()

# official action/product/person files
def official_rows(pattern_prefix):
    files = []
    for p in sorted(aa.glob("*.json")):
        n = p.name
        nl = n.lower()
        if ".before-" in nl or "discovery" in nl:
            continue
        if n.startswith(pattern_prefix) and n.endswith(".json"):
            if n in ("person-coverage.json",) or n.endswith("-selected.json") or n.endswith("-target.json") or "search-audit" in n or n.endswith("-long-input.json"):
                # not the confirmation batches named in the task input table
                continue
            obj = load_json(p)
            if isinstance(obj, dict) and "rows" in obj:
                files.append((n, obj["rows"]))
    return files

batch_files = official_rows("batch-")
product_files = official_rows("product-")
person_files = official_rows("person-")
# person-07 included; person-01..05, 07 yes

def status_bucket(st: str) -> str:
    st = st or ""
    if "未定案" in st or "倾向反例" in st:
        return "tentative"
    if "暂不展示" in st or "待人工确认" in st:
        return "not_confirmed"
    if "已确认" in st or "用户已确认" in st or "已逐人确认" in st or "已人工确认" in st or "出镜禁用" in st:
        return "confirmed"
    if st == "":
        return "blank"
    return "other:" + st

batch_status = collections.Counter()
batch_ids = []
for name, rows in batch_files:
    for r in rows:
        b = status_bucket(r.get("status"))
        batch_status[b] += 1
        batch_ids.append({"file": name, "sample_id": r.get("sample_id"), "status": r.get("status"), "bucket": b})

prod_status = collections.Counter()
prod_ids = []
for name, rows in product_files:
    for r in rows:
        b = status_bucket(r.get("status"))
        prod_status[b] += 1
        prod_ids.append({"file": name, "sample_id": r.get("sample_id"), "status": r.get("status"), "bucket": b})

person_rows_all = []
for name, rows in person_files:
    for r in rows:
        person_rows_all.append((name, r))

result["source_counts"]["action_batches"] = {
    "files": [n for n,_ in batch_files],
    "total_rows": sum(len(r) for _,r in batch_files),
    "by_bucket": dict(batch_status),
    "ids": batch_ids,
}
result["source_counts"]["products"] = {
    "files": [n for n,_ in product_files],
    "total_rows": sum(len(r) for _,r in product_files),
    "by_bucket": dict(prod_status),
    "ids": prod_ids,
}
result["source_counts"]["persons"] = {
    "files": [n for n,_ in person_files],
    "total_rows": len(person_rows_all),
    "ids": [{"file": n, "sample_id": r.get("sample_id"), "status": r.get("status")} for n,r in person_rows_all],
}

p24 = load_json(aa / "P24-boundary-proposal.json")["rows"]
result["source_counts"]["P24_rows"] = len(p24)
result["source_counts"]["P24_ids"] = [r.get("sample_id") for r in p24]
result["source_counts"]["P24_actions"] = [
    {"id": r.get("sample_id"), "action": r.get("confirmed_action") or r.get("suggested_action"), "start": (r.get("source") or {}).get("start"), "end": (r.get("source") or {}).get("end")}
    for r in p24
]

restr = load_json(aa / "person-usage-restrictions.json")
result["source_counts"]["usage_restriction_rules"] = len(restr.get("rules") or [])
aming = load_json(aa / "aming-source-rule-index.json")
result["source_counts"]["aming_source_rules"] = len(aming.get("rows") or [])
splitp = load_json(aa / "split-policy.json")
result["source_counts"]["split_policy_groups"] = len(splitp.get("exposed_directory_groups") or [])

cov_s = load_json(aa / "sample-coverage.json")
cov_p = load_json(aa / "person-coverage.json")
result["source_counts"]["sample_coverage_excerpt"] = {
    "updated": cov_s.get("updated"),
    "confirmed": cov_s.get("confirmed"),
    "tentative": cov_s.get("tentative"),
    "product_phase_confirmed": cov_s.get("product_phase_confirmed"),
    "product_phase_business_excluded": cov_s.get("product_phase_business_excluded"),
    "confirmed_derived_action_segments": cov_s.get("confirmed_derived_action_segments"),
    "person_confirmed_clips": cov_s.get("person_confirmed_clips"),
    "person_confirmed_subject_observations": cov_s.get("person_confirmed_subject_observations"),
    "person_business_prohibited_clips": cov_s.get("person_business_prohibited_clips"),
}
result["source_counts"]["person_coverage"] = {
    "updated": cov_p.get("updated"),
    "keys": list(cov_p.keys()),
    "summary": {k: cov_p[k] for k in cov_p if not isinstance(cov_p[k], (list, dict))},
}

# 试标 50
trial = load_json(RAW / "规则" / "试标50段" / "审核结果_李康_20261116.json")
trial_results = trial["结果"] if isinstance(trial, dict) and "结果" in trial else trial
trial_n = len(trial_results)
with (RAW / "规则" / "试标50段" / "_对应表.csv").open(encoding="utf-8-sig", newline="") as f:
    trial_csv = list(csv.DictReader(f))
result["source_counts"]["trial50_json"] = trial_n
result["source_counts"]["trial50_csv"] = len(trial_csv)
result["source_counts"]["trial50_seg_match"] = sorted(x["seg"] for x in trial["结果"]) == sorted(r["seg"] for r in trial_csv)

# 对照表 folders + 明细
duizhao = (RAW / "规则" / "出镜文件夹确认图" / "对照表.md").read_text(encoding="utf-8")
folder_rows = []
for m in re.finditer(r"^\| (sheet_\d+\.jpg) \| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", duizhao, re.M):
    folder_rows.append({"sheet": m.group(1), "folder": m.group(2).strip(), "videos": m.group(3).strip(), "frames": m.group(4).strip(), "who": m.group(5).strip()})
result["source_counts"]["duizhao_folders"] = len(folder_rows)
result["source_counts"]["duizhao_folder_sheets"] = [r["sheet"] for r in folder_rows]

# parse 明细 tables
detail_rows = []
cur_sheet = None
cur_folder = None
in_table = False
header = None
for line in duizhao.splitlines():
    m = re.match(r"^### (sheet_\d+\.jpg)（(.+)）", line)
    if m:
        cur_sheet, cur_folder = m.group(1), m.group(2)
        in_table = False
        header = None
        continue
    if cur_sheet and line.startswith("|") and re.match(r"^\| ?格 ?", line):
        header = [c.strip() for c in line.strip().strip("|").split("|")]
        in_table = True
        continue
    if in_table and re.match(r"^\|?[-:| ]+$", line.replace(" ", "")):
        continue
    if in_table and line.startswith("|"):
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        row = {"sheet": cur_sheet, "folder": cur_folder}
        for i, h in enumerate(header):
            if i < len(cols):
                row[h] = cols[i]
        detail_rows.append(row)
        continue
    if in_table and not line.startswith("|"):
        in_table = False
result["source_counts"]["duizhao_detail_rows"] = len(detail_rows)
# 17881 split?
result["source_counts"]["duizhao_detail_17881"] = [r for r in detail_rows if "17881" in json.dumps(r, ensure_ascii=False)]

# annotation sources
def count_jsonl(path):
    n = 0
    with path.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                n += 1
    return n

ann = RAW / "标注库"
idx_xq_n = count_jsonl(ann / "小区全库" / "数据" / "AI剪辑检索索引.jsonl")
idx_t_n = count_jsonl(ann / "测试阿明搅拌" / "数据" / "AI剪辑检索索引.jsonl")
const_n = count_jsonl(ann / "微陶泥施工" / "施工镜头.jsonl")
use_n = count_jsonl(ann / "小区全库" / "数据" / "按用途检索.jsonl")
fine_n = count_jsonl(ann / "小区全库" / "数据" / "本轮看片精标.jsonl")
rev_n = count_jsonl(ann / "小区全库" / "数据" / "机器片段复核.jsonl")
corr_n = count_jsonl(ann / "小区全库" / "数据" / "目视纠正.jsonl")

def index_stats(path):
    n = 0
    n_tl = n_idx = n_hum = n_hum_files = 0
    kinds = collections.Counter()
    no_tl = 0
    for o in iter_jsonl(path):
        n += 1
        kinds[o.get("kind") or ""] += 1
        tl = o.get("timeline") or []
        if isinstance(tl, list):
            n_tl += len(tl)
            if len(tl) == 0:
                no_tl += 1
        segs = o.get("indexed_segments") or []
        if isinstance(segs, list):
            n_idx += len(segs)
        hum = o.get("人工确认片段") or []
        if isinstance(hum, list) and hum:
            n_hum += len(hum)
            n_hum_files += 1
    return {"rows": n, "timeline": n_tl, "indexed_segments": n_idx, "human_files": n_hum_files, "human_segs": n_hum, "kinds": dict(kinds), "no_timeline": no_tl}

result["source_counts"]["ann_xiaoqu_index"] = index_stats(ann / "小区全库" / "数据" / "AI剪辑检索索引.jsonl")
result["source_counts"]["ann_test_index"] = index_stats(ann / "测试阿明搅拌" / "数据" / "AI剪辑检索索引.jsonl")
result["source_counts"]["ann_construction"] = const_n
result["source_counts"]["ann_usage"] = use_n
result["source_counts"]["ann_fine"] = fine_n
result["source_counts"]["ann_machine_review"] = rev_n
result["source_counts"]["ann_visual_corr"] = corr_n

# ---------- outputs ----------
facts = load_jsonl(LIB / "事实层.jsonl")
evals = load_jsonl(LIB / "评价与采用.jsonl")
bans = load_jsonl(LIB / "禁用表.jsonl")
clues = load_jsonl(LIB / "线索.jsonl")
# coarse count only (don't load 112MB list into comparisons needlessly)
coarse_n = 0
with (LIB / "粗标层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            coarse_n += 1

by_src = collections.Counter(r["来源文件"] for r in facts)
by_cat = collections.Counter(r.get("样例类别") for r in facts)
eval_types = collections.Counter(r.get("类型") for r in evals)
eval_ok = collections.Counter(r.get("转出成功") for r in evals)
clue_src = collections.Counter(r.get("来源文件") for r in clues)

result["output_counts"]["事实层"] = len(facts)
result["output_counts"]["粗标层"] = coarse_n
result["output_counts"]["评价与采用"] = len(evals)
result["output_counts"]["评价"] = eval_types.get("评价", 0)
result["output_counts"]["采用"] = eval_types.get("采用", 0)
result["output_counts"]["禁用表"] = len(bans)
result["output_counts"]["线索"] = len(clues)
result["output_counts"]["事实层_by_来源"] = dict(by_src)
result["output_counts"]["事实层_by_类别"] = dict(by_cat)
result["output_counts"]["评价转出成功"] = {str(k): v for k, v in eval_ok.items()}
result["output_counts"]["线索来源"] = dict(clue_src)
result["output_counts"]["禁用来源"] = [
    {"来源文件": b.get("来源文件"), "来源条目标识": b.get("来源条目标识"), "规则ID": b.get("规则ID")}
    for b in bans
]

# every eval id present?
fb_ids = {r["id"] for r in feedback}
# reopen? already have lists of ids from earlier - feedback was list of rows before close... we have feedback list from first conn - wait we closed and those rows might still be usable
# Actually feedback was fetched before close, rows should still be readable
# But I overwrote - feedback still in memory from start. Good.

# Need feedback/adoption ids - refetch
conn = open_sqlite_ro(RAW / "镜序" / "learning.sqlite3")
fb_ids = [r["id"] for r in conn.execute("SELECT id FROM feedback")]
ad_ids = [r["id"] for r in conn.execute("SELECT id FROM adoptions")]
conn.close()
out_eval_ids = {r.get("来源条目标识") or r.get("评价或采用ID") for r in evals if r.get("类型") == "评价"}
out_ad_ids = {r.get("来源条目标识") or r.get("评价或采用ID") for r in evals if r.get("类型") == "采用"}
# also try 评价或采用ID
if len(out_eval_ids & set(fb_ids)) < len(fb_ids):
    out_eval_ids2 = {r.get("评价或采用ID") for r in evals if r.get("类型") == "评价"}
    out_ad_ids2 = {r.get("评价或采用ID") for r in evals if r.get("类型") == "采用"}
else:
    out_eval_ids2, out_ad_ids2 = out_eval_ids, out_ad_ids

missing_fb = [i for i in fb_ids if i not in out_eval_ids and i not in {r.get("评价或采用ID") for r in evals}]
missing_ad = [i for i in ad_ids if i not in out_ad_ids and i not in {r.get("评价或采用ID") for r in evals}]
result["output_counts"]["missing_feedback_in_output"] = missing_fb
result["output_counts"]["missing_adoption_in_output"] = missing_ad
result["output_counts"]["extra_note_eval_id_fields"] = {
    "评价来源条目标识_hit": sum(1 for r in evals if r.get("类型")=="评价" and r.get("来源条目标识") in set(fb_ids)),
    "评价ID_hit": sum(1 for r in evals if r.get("类型")=="评价" and r.get("评价或采用ID") in set(fb_ids)),
    "采用来源条目标识_hit": sum(1 for r in evals if r.get("类型")=="采用" and r.get("来源条目标识") in set(ad_ids)),
    "采用ID_hit": sum(1 for r in evals if r.get("类型")=="采用" and r.get("评价或采用ID") in set(ad_ids)),
}

# confirmed 36 all in facts?
fact_rule_ids = {r["来源条目标识"] for r in facts if "learning.sqlite3" in r.get("来源文件","")}
missing_conf = [i for i in conf_ids if i not in fact_rule_ids]
result["output_counts"]["confirmed_missing_in_facts"] = missing_conf

# batch ids
fact_batch_ids = {(r["来源文件"], r["来源条目标识"]) for r in facts if "batch-" in r.get("来源文件","")}
missing_batch = []
for it in batch_ids:
    key = (f"local/action-annotation/{it['file']}", it["sample_id"])
    # also looser
    if not any(r.get("来源条目标识")==it["sample_id"] and it["file"] in r.get("来源文件","") for r in facts):
        missing_batch.append(it)
result["output_counts"]["batch_missing_in_facts"] = missing_batch

# P24
missing_p24 = [i for i in result["source_counts"]["P24_ids"] if not any(r.get("来源条目标识")==i for r in facts)]
result["output_counts"]["P24_missing_in_facts"] = missing_p24

# product confirmed should appear as confirmed-P*
prod_confirmed = [it for it in prod_ids if it["bucket"]=="confirmed"]
prod_not = [it for it in prod_ids if it["bucket"]!="confirmed"]
missing_prod = [it for it in prod_confirmed if f"confirmed-{it['sample_id']}" not in fact_rule_ids and not any(r.get("样例编号")==it["sample_id"] for r in facts)]
result["output_counts"]["product_confirmed_missing"] = missing_prod
result["output_counts"]["product_not_confirmed"] = prod_not

# persons
missing_person = []
for n,r in person_rows_all:
    sid = r.get("sample_id")
    if not sid:
        missing_person.append({"file": n, "reason": "no sample_id", "row_keys": list(r.keys())})
        continue
    if f"confirmed-{sid}" not in fact_rule_ids and not any(r2.get("来源条目标识")==sid or r2.get("样例编号")==sid for r2 in facts):
        missing_person.append({"file": n, "sample_id": sid, "status": r.get("status")})
result["output_counts"]["person_missing_in_facts"] = missing_person

# trial 50
trial_ids = [x["seg"] for x in trial["结果"]]
missing_trial = [s for s in trial_ids if not any(r.get("来源条目标识")==s for r in facts)]
result["output_counts"]["trial_missing"] = missing_trial

# duizhao folders
missing_folders = [r["sheet"] for r in folder_rows if not any(
    r["sheet"] in str(f.get("来源条目标识")) and f.get("来源文件")=="出镜文件夹确认图/对照表.md" for f in facts
)]
result["output_counts"]["duizhao_folder_missing"] = missing_folders
# detail: T10 may have split 17881 into 2, so detail facts may be 61 = 60 + 1 extra split? 60 rows + 1 extra = 61 if one row split into 2
n_detail_facts = sum(1 for f in facts if f.get("来源文件")=="出镜文件夹确认图/对照表.md#明细")
result["output_counts"]["duizhao_detail_facts"] = n_detail_facts

# clues
aming_ids = [r.get("id") for r in (aming.get("rows") or [])]
clue_ids = {c.get("来源条目标识") for c in clues}
missing_clues = [i for i in aming_ids if i not in clue_ids]
result["output_counts"]["clues_missing"] = missing_clues[:20]
result["output_counts"]["clues_missing_n"] = len(missing_clues)

# source rules in facts?
aming_in_facts = [f["事实编号"] for f in facts if "aming-source-rule" in f.get("来源文件","")]
result["output_counts"]["aming_rules_in_facts"] = aming_in_facts

# comparisons
add_cmp("逐段事实 confirmed-*", len(confirmed), len(fact_rule_ids), 36, 36, len(confirmed)==36 and not missing_conf,
        f"源 {len(confirmed)} 条，事实层含 {len(fact_rule_ids)} 条，缺失 {missing_conf}")
add_cmp("快照 identity-evidence vs 36", len(segs), len(confirmed), 33, "33，差 3 条为快照之后写入的 V1-V3",
        len(segs)==33 and set(missing_in_snap)=={"confirmed-V1","confirmed-V2","confirmed-V3"},
        f"快照 {len(segs)}，库中 {len(confirmed)}，快照没有的：{missing_in_snap} meta={miss_meta}")
add_cmp("动作样例 batch 确认+暂定", result["source_counts"]["action_batches"]["total_rows"],
        result["source_counts"]["action_batches"]["total_rows"]-len(missing_batch),
        "确认26+暂定2", "28 全部进事实层（暂定单独标）",
        result["source_counts"]["action_batches"]["by_bucket"].get("confirmed")==26
        and result["source_counts"]["action_batches"]["by_bucket"].get("tentative")==2
        and not missing_batch,
        f"bucket={result['source_counts']['action_batches']['by_bucket']} missing={missing_batch}")
add_cmp("产品样例确认", prod_status.get("confirmed",0), prod_status.get("confirmed",0)-len(missing_prod), 24, "24，已在 confirmed-P*，P16/P18 未确认未转",
        prod_status.get("confirmed")==24 and not missing_prod and {it['sample_id'] for it in prod_not}=={"P16","P18"},
        f"bucket={dict(prod_status)} missing={missing_prod} not_confirmed={prod_not}")
add_cmp("人物样例 person-01..05,07", len(person_rows_all), len(person_rows_all)-len(missing_person), "9段11次+后补V1-V3", "R01-R09 + V1-V3 已在 36 条逐段事实中",
        not missing_person, f"rows={len(person_rows_all)} missing={missing_person}")
add_cmp("P24 两动作分段", len(p24), len(p24)-len(missing_p24), 2, 2, not missing_p24, f"missing={missing_p24}")
add_cmp("评价 feedback", len(fb_ids), result["output_counts"]["评价"], 127, 127,
        len(fb_ids)==127 and result["output_counts"]["评价"]==127 and not missing_fb,
        f"missing={missing_fb} field_hits={result['output_counts']['extra_note_eval_id_fields']}")
add_cmp("采用 adoptions", len(ad_ids), result["output_counts"]["采用"], 240, 240,
        len(ad_ids)==240 and result["output_counts"]["采用"]==240 and not missing_ad,
        f"missing={missing_ad}")
add_cmp("禁用 person-usage-restrictions", result["source_counts"]["usage_restriction_rules"],
        sum(1 for b in bans if "person-usage-restrictions" in (b.get("来源文件") or "")),
        1, "禁用表 3 条（R09 原文 + 对照表两处限制）",
        result["source_counts"]["usage_restriction_rules"]==1 and any("person-usage-restrictions" in (b.get("来源文件") or "") for b in bans),
        f"禁用表共 {len(bans)} 条")
add_cmp("阿明来源规则/线索", result["source_counts"]["aming_source_rules"], result["output_counts"]["线索"], 2098, 2098,
        result["source_counts"]["aming_source_rules"]==2098 and result["output_counts"]["线索"]==2098 and result["output_counts"]["clues_missing_n"]==0,
        f"missing_n={result['output_counts']['clues_missing_n']}")
add_cmp("试标50段", trial_n, trial_n-len(missing_trial), 50, 50,
        trial_n==50 and len(trial_csv)==50 and result["source_counts"]["trial50_seg_match"] and not missing_trial,
        f"json={trial_n} csv={len(trial_csv)} missing={missing_trial}")
add_cmp("对照表文件夹级", len(folder_rows), 37-len(missing_folders), 37, 37,
        len(folder_rows)==37 and not missing_folders,
        f"folders={len(folder_rows)} missing={missing_folders}")
# 明细: 60 source rows, 61 facts because 17881 split into 2
explained_detail = (len(detail_rows)==60 and n_detail_facts==61 and any("17881" in json.dumps(r, ensure_ascii=False) for r in detail_rows))
add_cmp("对照表逐格明细", len(detail_rows), n_detail_facts, "文末逐格（T10称60条明细拆17881为两段）", "61（17881 拆成前5秒/约第6秒）",
        explained_detail, f"源明细行 {len(detail_rows)}，事实层 {n_detail_facts}；17881 源行={result['source_counts']['duizhao_detail_17881']}")
add_cmp("目视纠正", corr_n, sum(1 for f in facts if "目视纠正" in f.get("来源文件","")), 41, 41,
        corr_n==41 and sum(1 for f in facts if "目视纠正" in f.get("来源文件",""))==41,
        "")
add_cmp("本轮看片精标", fine_n, sum(1 for f in facts if "本轮看片精标" in f.get("来源文件","")), 34, 34,
        fine_n==34 and sum(1 for f in facts if "本轮看片精标" in f.get("来源文件",""))==34,
        "")
add_cmp("indexed_segments 进事实层", result["source_counts"]["ann_xiaoqu_index"]["indexed_segments"]+result["source_counts"]["ann_test_index"]["indexed_segments"],
        sum(1 for f in facts if "indexed_segments" in f.get("来源文件","")),
        "177+13", "177+13=190",
        sum(1 for f in facts if "indexed_segments" in f.get("来源文件",""))==190, "")
add_cmp("人工确认片段进事实层", result["source_counts"]["ann_xiaoqu_index"]["human_segs"]+result["source_counts"]["ann_test_index"]["human_segs"],
        sum(1 for f in facts if "人工确认片段" in f.get("来源文件","")),
        "6+8", "6+8=14",
        sum(1 for f in facts if "人工确认片段" in f.get("来源文件",""))==14, "")
add_cmp("粗标层条数（timeline+施工镜头+用途）",
        result["source_counts"]["ann_xiaoqu_index"]["timeline"]
        + result["source_counts"]["ann_test_index"]["timeline"]
        + const_n + use_n,
        coarse_n, 65971, 65971,
        coarse_n == result["source_counts"]["ann_xiaoqu_index"]["timeline"] + result["source_counts"]["ann_test_index"]["timeline"] + const_n + use_n == 65971,
        f"xq_tl={result['source_counts']['ann_xiaoqu_index']['timeline']} test_tl={result['source_counts']['ann_test_index']['timeline']} 施工={const_n} 用途={use_n} coarse={coarse_n}")
add_cmp("机器片段复核未进事实层", rev_n, sum(1 for f in facts if "机器片段复核" in f.get("来源文件","")), 13576, "只读结构、不进事实层",
        sum(1 for f in facts if "机器片段复核" in f.get("来源文件",""))==0,
        f"源 {rev_n} 条，事实层 0 条，与回报一致")
add_cmp("split-policy 未入库", result["source_counts"]["split_policy_groups"], 0, 35, "只在回报说明，不入库",
        True, "政策文件，不是片段事实")
add_cmp("登记表行数", n_assets, n_assets, 43295, 43295, n_assets==43295, f"roots={roots}")

all_ok = all(c["equal_or_explained"] for c in result["comparisons"])
result["pass"] = all_ok
result["failed"] = [c["name"] for c in result["comparisons"] if not c["equal_or_explained"]]

dump_json(MID / "item1_counts.json", result)
print("ITEM1 pass=", result["pass"], "failed=", result["failed"])
for c in result["comparisons"]:
    flag = "OK" if c["equal_or_explained"] else "FAIL"
    print(f"  {flag} {c['name']}: src={c['source_n']} out={c['output_n']} known={c['known_n']} | {c['detail'][:200]}")
print("facts", len(facts), "coarse", coarse_n, "evals", len(evals), "bans", len(bans), "clues", len(clues))
