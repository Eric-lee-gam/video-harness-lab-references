# -*- coding: utf-8 -*-
"""C10 item 2: sample 30 facts with independent seed, compare to originals."""
from __future__ import annotations

import csv
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c10_common import *

SEED = RANDOM_SEED
facts = load_jsonl(LIB / "事实层.jsonl")
aa = RAW / "镜序" / "action-annotation"
ann = RAW / "标注库"

# ---------- build source indexes ----------
conn = open_sqlite_ro(RAW / "镜序" / "learning.sqlite3")
rules = {}
for row in conn.execute("SELECT id, status, reviewer, created, payload FROM rules"):
    rules[row["id"]] = {
        "id": row["id"], "status": row["status"], "reviewer": row["reviewer"],
        "created": row["created"],
        "payload": json.loads(row["payload"]) if row["payload"] else {},
    }
conn.close()

connc = open_sqlite_ro(RAW / "镜序" / "catalog.sqlite3")
catalog = {}
for row in connc.execute("SELECT id, root, rel, name FROM assets"):
    catalog[row["id"]] = {"id": row["id"], "root": row["root"], "rel": row["rel"], "name": row["name"]}
connc.close()

json_rows = {}  # (filename, sample_id) -> row
for p in sorted(aa.glob("*.json")):
    nl = p.name.lower()
    if ".before-" in nl or "discovery" in nl:
        continue
    obj = load_json(p)
    if isinstance(obj, dict) and "rows" in obj:
        for r in obj["rows"]:
            sid = r.get("sample_id")
            if sid:
                json_rows[(p.name, sid)] = r

trial = load_json(RAW / "规则" / "试标50段" / "审核结果_李康_20261116.json")
trial_map = {r["seg"]: r for r in trial["结果"]}
with (RAW / "规则" / "试标50段" / "_对应表.csv").open(encoding="utf-8-sig", newline="") as f:
    trial_csv = {r["seg"]: r for r in csv.DictReader(f)}

duizhao_text = (RAW / "规则" / "出镜文件夹确认图" / "对照表.md").read_text(encoding="utf-8")
folder_map = {}
for m in re.finditer(r"^\| (sheet_\d+\.jpg) \| `([^`]+)` \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$", duizhao_text, re.M):
    folder_map[m.group(1)] = {
        "sheet": m.group(1), "folder": m.group(2).strip(),
        "videos": m.group(3).strip(), "frames": m.group(4).strip(), "who": m.group(5).strip(),
    }

detail_map = {}  # keys: (sheet, grid, filename) and (sheet, filename)
cur_sheet = cur_folder = None
in_table = False
header = None
for line in duizhao_text.splitlines():
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
        detail_map[(cur_sheet, row.get("格"), row.get("原片"))] = row
        detail_map[(cur_sheet, row.get("原片"))] = row
        continue
    if in_table and not line.startswith("|"):
        in_table = False

corr_map = {r["id"]: r for r in load_jsonl(ann / "小区全库" / "数据" / "目视纠正.jsonl")}
fine_map = {}
for r in load_jsonl(ann / "小区全库" / "数据" / "本轮看片精标.jsonl"):
    fine_map[r["id"]] = r
    fine_map[(r["id"], r.get("start"), r.get("end"))] = r

def index_lookups(path):
    by_id = {}
    segs = {}
    humans = {}
    for o in iter_jsonl(path):
        oid = o.get("id")
        by_id[oid] = o
        for i, seg in enumerate(o.get("indexed_segments") or []):
            st, en = seg.get("start"), seg.get("end")
            segs[(oid, st, en, i)] = (o, seg, i)
            segs[(oid, str(st), str(en), i)] = (o, seg, i)
        for i, hum in enumerate(o.get("人工确认片段") or []):
            humans[(oid, i)] = (o, hum, i)
            if isinstance(hum, dict):
                humans[(oid, hum.get("start"), hum.get("end"))] = (o, hum, i)
    return by_id, segs, humans

xq_id, xq_segs, xq_hum = index_lookups(ann / "小区全库" / "数据" / "AI剪辑检索索引.jsonl")
ts_id, ts_segs, ts_hum = index_lookups(ann / "测试阿明搅拌" / "数据" / "AI剪辑检索索引.jsonl")
all_id = {**ts_id, **xq_id}  # xq last? overlap unlikely; keep both with prefix
# prefer explicit file later


def num_eq(a, b):
    if a in (None, "") and b in (None, ""):
        return True
    if a in (None, "") or b in (None, ""):
        return False
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def contains_text(hay, needle):
    if needle in (None, "", [], {}):
        return True
    if isinstance(needle, (dict, list)):
        return json.dumps(needle, ensure_ascii=False) in (hay if isinstance(hay, str) else json.dumps(hay, ensure_ascii=False))
    return str(needle) in (hay if isinstance(hay, str) else json.dumps(hay, ensure_ascii=False))


def issues_new():
    return []


def compare_path(fact, src_path, issues, label="path"):
    rel = rel_from_any_path(src_path) if src_path else None
    out = fact.get("主库相对路径")
    if src_path and rel and not paths_equal(rel, out):
        issues.append({"field": label, "src": rel, "out": out})
    if src_path and not rel:
        issues.append({"field": label, "src_raw": src_path, "out": out, "note": "未能抽出相对路径"})


def compare_times(fact, st, en, issues):
    if not num_eq(fact.get("起秒"), st) or not num_eq(fact.get("止秒"), en):
        issues.append({"field": "起止秒", "src": [st, en], "out": [fact.get("起秒"), fact.get("止秒")]})


def lookup_index_seg(key_str, which="auto"):
    # formats: id:start-end:idx
    parts = key_str.split(":")
    if len(parts) < 3:
        return None
    oid = parts[0]
    idx = int(parts[-1])
    mid = ":".join(parts[1:-1])  # start-end, start may contain no extra colon
    # start-end split at last hyphen? times like 2.2-4.4333
    if "-" not in mid:
        return None
    # careful: negative start? unlikely
    i = mid.find("-")
    # if start is negative, first char -, find second
    if mid.startswith("-"):
        i = mid.find("-", 1)
    st_s, en_s = mid[:i], mid[i+1:]
    try:
        st, en = float(st_s), float(en_s)
    except ValueError:
        st, en = st_s, en_s
    for segs in (xq_segs, ts_segs):
        rec = segs.get((oid, st, en, idx)) or segs.get((oid, st_s, en_s, idx))
        if rec:
            return rec
        # try float-key match by scanning keys with same oid+idx
        for (koid, kst, ken, ki), val in segs.items():
            if koid==oid and ki==idx and num_eq(kst, st) and num_eq(ken, en):
                return val
    return None


def lookup_human(key_str):
    # formats: id:人工确认:start-end:index   or id:start-end or id:index
    if ":人工确认:" in key_str:
        oid, rest = key_str.split(":人工确认:", 1)
        parts = rest.split(":")
        idx = int(parts[-1]) if parts and parts[-1].isdigit() else None
        mid = ":".join(parts[:-1]) if idx is not None else rest
        if "-" in mid:
            i = mid.find("-") if not mid.startswith("-") else mid.find("-", 1)
            st_s, en_s = mid[:i], mid[i+1:]
            try:
                st, en = float(st_s), float(en_s)
            except ValueError:
                st, en = st_s, en_s
            rec = xq_hum.get((oid, st, en)) or ts_hum.get((oid, st, en))
            if rec:
                return ("hum", rec)
            if idx is not None:
                rec = xq_hum.get((oid, idx)) or ts_hum.get((oid, idx))
                if rec:
                    return ("hum", rec)
    rec = lookup_index_seg(key_str)
    if rec:
        return ("seg?", rec)
    if ":" in key_str:
        oid, rest = key_str.split(":", 1)
        if rest.isdigit():
            i = int(rest)
            return ("hum", xq_hum.get((oid, i)) or ts_hum.get((oid, i)))
        if "-" in rest and rest.count(":")==0:
            i = rest.find("-")
            st_s, en_s = rest[:i], rest[i+1:]
            try:
                st, en = float(st_s), float(en_s)
            except ValueError:
                st, en = st_s, en_s
            return ("hum", xq_hum.get((oid, st, en)) or ts_hum.get((oid, st, en)))
    return None


def check_fact(fact):
    srcf = fact.get("来源文件") or ""
    sid = fact.get("来源条目标识")
    issues = []
    src_kind = None
    confirmer_src = None
    notes = []

    if "learning.sqlite3" in srcf:
        src_kind = "sqlite_rule"
        rec = rules.get(sid)
        if not rec:
            return {"ok": False, "issues": [{"reason": "原始 rules 找不到", "id": sid}], "src_kind": src_kind}
        pay = rec["payload"]
        compare_times(fact, pay.get("start"), pay.get("end"), issues)
        if fact.get("镜序素材ID") and pay.get("asset_id") and fact.get("镜序素材ID") != pay.get("asset_id"):
            issues.append({"field": "镜序素材ID", "src": pay.get("asset_id"), "out": fact.get("镜序素材ID")})
        # path via catalog
        asset = catalog.get(pay.get("asset_id"))
        if asset:
            crel = catalog_relpath(asset["root"], asset["rel"])
            if crel and not paths_equal(crel, fact.get("主库相对路径")):
                issues.append({"field": "主库相对路径(登记表)", "src": crel, "out": fact.get("主库相对路径"), "root": asset["root"]})
        confirmer_src = pay.get("confirmed_by") or rec.get("reviewer")
        if confirmer_src and fact.get("确认人") != confirmer_src:
            issues.append({"field": "确认人", "src": confirmer_src, "out": fact.get("确认人")})
        # 内容 should carry payload fields
        content = fact.get("内容") or {}
        for k in ("evidence", "context", "product_identity", "identities", "confirmed_action", "apply_to_directory", "text", "description"):
            if k in pay and pay[k] not in (None, "", []):
                if isinstance(content, dict) and k in content:
                    if content.get(k) != pay[k]:
                        issues.append({"field": f"内容.{k}", "src": pay[k], "out": content.get(k)})
                elif not contains_text(fact.get("限定语原文"), pay[k]) and not contains_text(content, pay[k]):
                    issues.append({"field": f"缺失原文字段 {k}", "src": pay[k]})
        # 限定语 should include evidence if present
        ev = pay.get("evidence")
        if ev:
            evs = ev if isinstance(ev, list) else [ev]
            for e in evs:
                if e and not contains_text(fact.get("限定语原文"), e) and not contains_text(content, e):
                    issues.append({"field": "限定语/evidence", "src": e})
        if pay.get("apply_to_directory") is False:
            out_lim = (fact.get("限定语原文") or "") + json.dumps(content, ensure_ascii=False)
            if "不套用到目录" not in out_lim and "apply_to_directory" not in out_lim:
                issues.append({"field": "限定语 apply_to_directory=false 未体现"})

    elif re.search(r"batch-\d+\.json", srcf) or srcf.endswith("P24-boundary-proposal.json") or "action-annotation/P24" in srcf:
        src_kind = "action_json"
        fn = Path(srcf.replace("\\", "/")).name
        rec = json_rows.get((fn, sid))
        if not rec:
            # search any official file
            rec = next((r for (f,s), r in json_rows.items() if s==sid), None)
            fn = fn or "?"
        if not rec:
            return {"ok": False, "issues": [{"reason": "原始 json 找不到", "file": srcf, "id": sid}], "src_kind": src_kind}
        src = rec.get("source") or {}
        compare_times(fact, src.get("start"), src.get("end"), issues)
        compare_path(fact, src.get("path") or src.get("rel") or rec.get("path"), issues)
        if src.get("id") and fact.get("镜序素材ID") and src.get("id") != fact.get("镜序素材ID"):
            issues.append({"field": "镜序素材ID", "src": src.get("id"), "out": fact.get("镜序素材ID")})
        confirmer_src = rec.get("confirmed_by")
        if confirmer_src and fact.get("确认人") != confirmer_src:
            issues.append({"field": "确认人", "src": confirmer_src, "out": fact.get("确认人")})
        for k in ("confirmed_label", "confirmed_action", "status", "quality_note"):
            if rec.get(k) not in (None, "", []) and not contains_text(fact.get("内容"), rec.get(k)) and not contains_text(fact.get("限定语原文"), rec.get(k)):
                issues.append({"field": k, "src": rec.get(k)})
        # 暂定 status
        if rec.get("status") and "未定案" in rec.get("status"):
            if fact.get("确认状态") not in ("暂定",) and "未定案" not in json.dumps(fact, ensure_ascii=False):
                issues.append({"field": "暂定状态未保留", "src": rec.get("status"), "out": fact.get("确认状态")})

    elif "试标50段" in srcf:
        src_kind = "trial50"
        rec = trial_map.get(sid)
        csvr = trial_csv.get(sid)
        if not rec or not csvr:
            return {"ok": False, "issues": [{"reason": "试标原始找不到", "id": sid, "json": bool(rec), "csv": bool(csvr)}], "src_kind": src_kind}
        compare_times(fact, csvr.get("起始秒"), csvr.get("结束秒"), issues)
        compare_path(fact, csvr.get("原片"), issues)
        confirmer_src = "李康"
        if fact.get("确认人") != "李康":
            issues.append({"field": "确认人", "src": "李康", "out": fact.get("确认人")})
        for k in ("verdict", "reason", "note", "机器画面类型"):
            val = rec.get(k)
            if val not in (None, "", []) and not contains_text(fact.get("内容"), val) and not contains_text(fact, val):
                issues.append({"field": k, "src": val})

    elif srcf == "出镜文件夹确认图/对照表.md":
        src_kind = "duizhao_folder"
        # 来源条目标识: sheet_15.jpg:拍摄\...
        sheet = sid.split(":", 1)[0] if sid else ""
        rec = folder_map.get(sheet)
        if not rec:
            return {"ok": False, "issues": [{"reason": "对照表文件夹行找不到", "id": sid}], "src_kind": src_kind}
        if rec["who"] not in (fact.get("限定语原文") or "") and rec["who"] not in json.dumps(fact.get("内容"), ensure_ascii=False):
            issues.append({"field": "出镜的是谁", "src": rec["who"], "out": fact.get("限定语原文")})
        if rec["folder"].replace("/", "\\") not in (fact.get("主库相对路径") or "").replace("/", "\\") and rec["folder"] not in json.dumps(fact, ensure_ascii=False):
            issues.append({"field": "文件夹路径", "src": rec["folder"], "out": fact.get("主库相对路径")})
        confirmer_src = "李康"
        if fact.get("确认人") != "李康":
            issues.append({"field": "确认人", "src": "李康", "out": fact.get("确认人")})
        if fact.get("确认级别") != "文件夹级":
            issues.append({"field": "确认级别", "src": "文件夹级", "out": fact.get("确认级别")})
        if not missing_ok_times_for_folder(fact):
            issues.append({"field": "文件夹级不应编造起止秒", "out": [fact.get("起秒"), fact.get("止秒")]})

    elif srcf.endswith("对照表.md#明细"):
        src_kind = "duizhao_detail"
        # sheet_01.jpg:01:18258_... or sheet_07.jpg:17881_...:0-5
        parts = sid.split(":") if sid else []
        rec = None
        if len(parts) >= 3 and re.match(r"sheet_\d+\.jpg", parts[0]):
            rec = detail_map.get((parts[0], parts[1], parts[2])) or detail_map.get((parts[0], parts[2]))
            # 17881 form: sheet_07.jpg:17881_...:0-5
            if rec is None:
                rec = detail_map.get((parts[0], parts[1]))
        if not rec:
            return {"ok": False, "issues": [{"reason": "对照表明细找不到", "id": sid, "parts": parts}], "src_kind": src_kind}
        judge = rec.get("李康的判断")
        if judge and judge not in (fact.get("限定语原文") or "") and judge not in json.dumps(fact.get("内容"), ensure_ascii=False):
            issues.append({"field": "李康的判断", "src": judge})
        if rec.get("原片") and rec.get("原片") not in (fact.get("主库相对路径") or "") and rec.get("原片") not in json.dumps(fact, ensure_ascii=False):
            issues.append({"field": "原片名", "src": rec.get("原片"), "out": fact.get("主库相对路径")})
        confirmer_src = "李康"
        if fact.get("确认人") != "李康":
            issues.append({"field": "确认人", "src": "李康", "out": fact.get("确认人")})
        # times only if 分段 in 来源条目标识
        if len(parts) >= 3 and re.match(r"^\d+(-\S*)?$", parts[-1]):
            # 0-5 or 6-None
            rng = parts[-1]
            if "-" in rng:
                a,b = rng.split("-", 1)
                st = 0 if a in ("", "None") else (float(a) if a.replace(".", "", 1).isdigit() else a)
                en = None if b in ("", "None") else (float(b) if b.replace(".", "", 1).isdigit() else b)
                compare_times(fact, st, en, issues)

    elif "目视纠正" in srcf:
        src_kind = "visual_corr"
        rec = corr_map.get(sid)
        if not rec:
            return {"ok": False, "issues": [{"reason": "目视纠正找不到", "id": sid}], "src_kind": src_kind}
        if rec.get("description") and rec.get("description") not in json.dumps(fact.get("内容"), ensure_ascii=False) and rec.get("description") not in (fact.get("限定语原文") or ""):
            issues.append({"field": "description", "src": rec.get("description")})
        if rec.get("basis") and rec.get("basis") not in json.dumps(fact, ensure_ascii=False):
            issues.append({"field": "basis", "src": rec.get("basis")})
        src_obj = xq_id.get(sid) or ts_id.get(sid)
        if src_obj:
            compare_path(fact, src_obj.get("source_path") or src_obj.get("path"), issues)
        if not missing_ok_times_for_folder(fact):
            # 目视纠正 has no times — should not invent
            if fact.get("起秒") not in (None, "") or fact.get("止秒") not in (None, ""):
                issues.append({"field": "目视纠正不应编造起止秒", "out": [fact.get("起秒"), fact.get("止秒")]})

    elif "本轮看片精标" in srcf:
        src_kind = "fine"
        rec = fine_map.get(sid)
        if not rec:
            rec = next((v for k,v in fine_map.items() if isinstance(k, str) and k==sid), None)
        if not rec:
            return {"ok": False, "issues": [{"reason": "本轮看片精标找不到", "id": sid}], "src_kind": src_kind}
        compare_times(fact, rec.get("start"), rec.get("end"), issues)
        compare_path(fact, rec.get("path"), issues)
        for k in ("action", "basis", "limits", "category"):
            if rec.get(k) not in (None, "", []) and not contains_text(fact.get("内容"), rec.get(k)) and not contains_text(fact, rec.get(k)):
                issues.append({"field": k, "src": rec.get(k)})

    elif "indexed_segments" in srcf:
        src_kind = "indexed_segments"
        rec = lookup_index_seg(sid)
        if not rec:
            return {"ok": False, "issues": [{"reason": "indexed_segments 找不到", "id": sid}], "src_kind": src_kind}
        obj, seg, idx = rec
        compare_times(fact, seg.get("start"), seg.get("end"), issues)
        compare_path(fact, obj.get("source_path") or obj.get("path"), issues)
        if fact.get("标注库ID") and obj.get("id") and fact.get("标注库ID") != obj.get("id"):
            issues.append({"field": "标注库ID", "src": obj.get("id"), "out": fact.get("标注库ID")})
        # field values in 内容 or original
        PATH_KEYS = {"source_path", "path", "preview", "preview_path", "rel"}
        for k, val in seg.items():
            if k in PATH_KEYS:
                continue
            if val in (None, "", [], {}):
                continue
            if not contains_text(fact.get("内容"), val) and not contains_text(fact, val):
                issues.append({"field": f"seg.{k}", "src": val if not isinstance(val, (list, dict)) else json.dumps(val, ensure_ascii=False)[:300]})

    elif "人工确认片段" in srcf:
        src_kind = "human_segs"
        rec = lookup_human(sid)
        found = rec[1] if rec else None
        if not found:
            # try parse more loosely
            return {"ok": False, "issues": [{"reason": "人工确认片段找不到", "id": sid}], "src_kind": src_kind}
        obj, hum, idx = found
        if isinstance(hum, dict):
            compare_times(fact, hum.get("start") or hum.get("起秒"), hum.get("end") or hum.get("止秒"), issues)
            PATH_KEYS = {"source_path", "path", "preview", "preview_path", "rel"}
            for k, val in hum.items():
                if k in PATH_KEYS:
                    continue
                if val in (None, "", [], {}):
                    continue
                if not contains_text(fact.get("内容"), val) and not contains_text(fact, val):
                    issues.append({"field": f"hum.{k}", "src": val if not isinstance(val, (list, dict)) else json.dumps(val, ensure_ascii=False)[:300]})
        compare_path(fact, obj.get("source_path") or obj.get("path"), issues)

    else:
        src_kind = "unknown"
        issues.append({"reason": "未实现的来源类型", "来源文件": srcf, "id": sid})

    return {
        "ok": len(issues)==0,
        "issues": issues,
        "src_kind": src_kind,
        "confirmer_src": confirmer_src,
        "notes": notes,
    }


def missing_ok_times_for_folder(fact):
    return fact.get("起秒") in (None, "") and fact.get("止秒") in (None, "")


# sample
rng = random.Random(SEED)
sample = rng.sample(facts, 30)
sample_ids = [r.get("事实编号") for r in sample]

results = []
for fact in sample:
    chk = check_fact(fact)
    results.append({
        "事实编号": fact.get("事实编号"),
        "来源文件": fact.get("来源文件"),
        "来源条目标识": fact.get("来源条目标识"),
        "样例类别": fact.get("样例类别"),
        "主库相对路径": fact.get("主库相对路径"),
        "起秒": fact.get("起秒"),
        "止秒": fact.get("止秒"),
        "确认人": fact.get("确认人"),
        "是否反例": fact.get("是否反例"),
        "确认级别": fact.get("确认级别"),
        "ok": chk["ok"],
        "src_kind": chk.get("src_kind"),
        "issues": chk.get("issues"),
        "notes": chk.get("notes"),
    })

failed = [r for r in results if not r["ok"]]
out = {
    "item": 2,
    "seed": SEED,
    "sample_n": 30,
    "sample_事实编号": sample_ids,
    "pass": len(failed)==0,
    "failed_n": len(failed),
    "failed_ids": [r["事实编号"] for r in failed],
    "results": results,
}
dump_json(MID / "item2_sample_facts.json", out)
print("ITEM2 seed", SEED, "pass", out["pass"], "failed", out["failed_n"], out["failed_ids"])
for r in results:
    flag = "OK" if r["ok"] else "FAIL"
    print(f"  {flag} {r['事实编号']} {r['src_kind']} {r['来源条目标识']} issues={r['issues'][:3] if r['issues'] else []}")
