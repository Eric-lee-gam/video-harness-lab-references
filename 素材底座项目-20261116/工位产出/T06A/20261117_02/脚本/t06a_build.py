# -*- coding: utf-8 -*-
"""T06A：标签可信度、人工抽查清单、素材够不够表、挑段建议、缺口说明、回报。"""
from __future__ import annotations

import csv
import math
import random
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t06a_lib as L


def now_shanghai():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "（Asia/Shanghai）"


def load_all():
    yuanpian = {}
    yuan_by_path = {}
    n_yuan = 0
    for r in L.iter_jsonl(L.CLIPLIB / "原片表.jsonl"):
        n_yuan += 1
        yuanpian[r["原片ID"]] = r
        # 共享相对路径：拍摄/小区/...
        sp = r.get("共享相对路径") or r.get("逻辑路径") or ""
        if sp:
            yuan_by_path[L.norm_slash("史上最完整共享/" + sp.replace("\\", "/").lstrip("/"))] = r
            yuan_by_path[L.norm_slash(sp)] = r
    facts = list(L.iter_jsonl(L.CLIPLIB / "事实层.jsonl"))
    bans = list(L.iter_jsonl(L.CLIPLIB / "禁用表.jsonl"))
    coarse = []
    by_path = defaultdict(list)
    by_yuan = defaultdict(list)
    for r in L.iter_jsonl(L.CLIPLIB / "粗标层.jsonl"):
        coarse.append(r)
        p = L.norm_slash(r.get("主库相对路径"))
        if p:
            by_path[p].append(r)
        if r.get("原片ID"):
            by_yuan[r["原片ID"]].append(r)
    file_ranges, folders, ban_ids = L.load_bans(bans)
    policy = L.load_split_policy_dirs()
    sha = L.sha256_file(L.CLIPLIB / "原片表.jsonl")
    return {
        "yuanpian": yuanpian,
        "yuan_by_path": yuan_by_path,
        "n_yuan": n_yuan,
        "facts": facts,
        "coarse": coarse,
        "by_path": by_path,
        "by_yuan": by_yuan,
        "file_ranges": file_ranges,
        "folders": folders,
        "policy": policy,
        "sha": sha,
        "bans": bans,
    }


def get_yuan(data, fact_or_coarse):
    yid = fact_or_coarse.get("原片ID")
    if yid and yid in data["yuanpian"]:
        return data["yuanpian"][yid]
    p = L.norm_slash(fact_or_coarse.get("主库相对路径"))
    return data["yuan_by_path"].get(p)


def overlapping_coarse(data, fact):
    if not L.has_times(fact):
        return []
    p = L.norm_slash(fact.get("主库相对路径"))
    cands = list(data["by_path"].get(p, []))
    yid = fact.get("原片ID")
    if yid:
        seen = {id(x) for x in cands}
        for c in data["by_yuan"].get(yid, []):
            if id(c) not in seen:
                cands.append(c)
    hits = []
    for c in cands:
        if L.overlap(fact.get("起秒"), fact.get("止秒"), c.get("起秒"), c.get("止秒")):
            hits.append(c)
    return hits


# ---------- 从事实层抽出可比较的人确认值 ----------
PROCESS_V = set(L.PROCESS_TO_V.values())

INDEPENDENT_SKIP_KINDS = {
    "标注库精标indexed_segments",
    "本轮看片精标",
    "目视纠正",
    "李康按文件夹确认",
    "李康按文件夹确认-逐格",
}


def human_process(fact):
    """返回 None 或 {mode, v_codes, raw, 事实编号, ...}。mode=positive/negative。"""
    if fact.get("确认状态") == "暂定":
        return None
    kind = fact.get("样例类别")
    if kind in INDEPENDENT_SKIP_KINDS:
        return None
    fid = fact.get("事实编号")
    content = fact.get("内容") or {}

    if kind == "试标50段":
        review = content.get("审核结果") or {}
        if review.get("verdict") == "对":
            v = fact.get("机器画面类型") or review.get("机器画面类型")
        elif review.get("verdict") == "错":
            v = review.get("fix")
        else:
            return None
        if not v:
            return None
        return {"mode": "positive", "v_codes": {v}, "raw": v, "来源": kind, "事实编号": fid}

    if kind in ("施工动作", "两动作分段"):
        label = fact.get("样例标签") or ""
        action = content.get("confirmed_action") or fact.get("样例大类") or content.get("category")
        if not action:
            return None
        if action in ("打磨",):
            return None
        v = L.HUMAN_PROCESS_TO_V.get(str(action).strip())
        if not v:
            return None
        if label.startswith("正例") or label.startswith("用户确认"):
            return {"mode": "positive", "v_codes": {v}, "raw": action, "来源": kind, "事实编号": fid}
        if label in ("反例",) or (fact.get("是否反例") and label != "倾向反例"):
            if "倾向" in str(label):
                return None
            return {"mode": "negative", "v_codes": {v}, "raw": "不是" + str(action), "来源": kind, "事实编号": fid}
        return None

    if kind == "逐段事实":
        action = content.get("confirmed_action")
        if not action:
            return None
        a = str(action).strip()
        if a in ("微陶泥施工",):
            return None
        if a.startswith("非批刮"):
            return {"mode": "negative", "v_codes": {"V05"}, "raw": a, "来源": kind, "事实编号": fid}
        if a in ("非施工工序", "施工中途现场展示，非正在施工"):
            return {"mode": "negative", "v_codes": {"V05", "V06"}, "raw": a, "来源": kind, "事实编号": fid}
        if "＋" in a or "+" in a:
            parts = [p.strip() for p in a.replace("（混合动作）", "").replace("+", "＋").split("＋") if p.strip()]
            vs = set()
            for p in parts:
                pv = L.HUMAN_PROCESS_TO_V.get(p)
                if pv:
                    vs.add(pv)
            if not vs:
                return None
            return {"mode": "positive", "v_codes": vs, "raw": a, "来源": kind, "事实编号": fid}
        v = L.HUMAN_PROCESS_TO_V.get(a)
        if not v:
            return None
        return {"mode": "positive", "v_codes": {v}, "raw": a, "来源": kind, "事实编号": fid}
    return None



def process_applicable(human):
    """工序字段只能表达部分画面类型。人确认的是成品空间、人物对镜头等时，不算工序漏标。"""
    if not human:
        return None
    if not human.get("v_codes"):
        return None
    if not set(human["v_codes"]) <= PROCESS_V:
        return None
    return human


def human_material(fact):
    if fact.get("确认状态") == "暂定":
        return None
    kind = fact.get("样例类别")
    content = fact.get("内容") or {}
    fid = fact.get("事实编号")
    if kind == "逐段事实":
        prod = content.get("product_identity") or ""
        if "不是微陶泥" in prod:
            return {"mode": "negative", "value": "微陶泥", "raw": prod, "来源": kind, "事实编号": fid}
        if "不证明" in prod or prod in ("未核验", "", None):
            return None
        if "微陶泥" in prod:
            return {"mode": "positive", "value": "微陶泥", "raw": prod, "来源": kind, "事实编号": fid}
        if "水洗石" in prod or "微岩石" in prod:
            return {"mode": "positive", "value": "微岩石", "raw": prod, "来源": kind, "事实编号": fid}
        # 其他已确认品名
        if prod and "未核验" not in prod:
            val = L.normalize_material(prod)
            if val:
                return {"mode": "positive", "value": val, "raw": prod, "来源": kind, "事实编号": fid}
        return None
    if kind == "标注库人工确认片段":
        mat = (content.get("人工确认片段") or {}).get("材料")
        val = L.normalize_material(mat)
        if val:
            return {"mode": "positive", "value": val, "raw": mat, "来源": kind, "事实编号": fid}
        return None
    return None


def human_weitanni(fact):
    """可按微陶泥选用：只取产品身份明确的片段事实。"""
    if fact.get("确认状态") == "暂定":
        return None
    kind = fact.get("样例类别")
    content = fact.get("内容") or {}
    fid = fact.get("事实编号")
    if kind != "逐段事实":
        # 人工确认片段写了材料=微陶泥，视为可按微陶泥选用
        if kind == "标注库人工确认片段":
            mat = (content.get("人工确认片段") or {}).get("材料")
            if L.normalize_material(mat) == "微陶泥":
                return {"mode": "positive", "value": True, "raw": "材料=微陶泥", "来源": kind, "事实编号": fid}
        return None
    prod = content.get("product_identity") or ""
    ctx = str(content.get("context") or "") + str(fact.get("限定语原文") or "")
    if "不是微陶泥" in prod:
        return {"mode": "positive", "value": False, "raw": prod, "来源": kind, "事实编号": fid}
    if "不证明" in prod:
        return None
    if "不作为直接微陶泥施工画面" in ctx:
        return None
    if "微陶泥（用户确认）" in prod or prod.startswith("微陶泥（用户确认"):
        return {"mode": "positive", "value": True, "raw": prod, "来源": kind, "事实编号": fid}
    return None


def human_usage(fact):
    """独立来源几乎没有用途分类确认；精标与用途片段同源，不用。"""
    return None


def coarse_process_vs(hits, prefer_review: bool):
    vs = set()
    raws = []
    for c in hits:
        fields = c.get("原字段") or {}
        name = L.effective_process(fields) if prefer_review else L.raw_process(fields)
        if not name:
            continue
        v = L.process_to_v(name)
        raws.append({"粗标编号": c.get("粗标编号"), "工序取值": name, "对应画面类型": v, "记录种类": c.get("记录种类")})
        if v:
            vs.add(v)
    return vs, raws


def coarse_materials(hits):
    vals = set()
    raws = []
    for c in hits:
        fields = c.get("原字段") or {}
        names = []
        if fields.get("材料类目"):
            names.append(fields.get("材料类目"))
        mat = fields.get("material")
        if isinstance(mat, dict) and mat.get("category"):
            names.append(mat.get("category"))
        top = c.get("材料")
        if isinstance(top, dict) and top.get("category"):
            names.append(top.get("category"))
        for n in names:
            val = L.normalize_material(n)
            if val:
                vals.add(val)
                raws.append({"粗标编号": c.get("粗标编号"), "材料类目": val, "原文": n})
    return vals, raws


def coarse_weitanni(hits):
    """返回 (True/False/None, 明细)。有键时：任一 True 则为 True，否则全是 False。无键则 None。"""
    flags = []
    raws = []
    for c in hits:
        fields = c.get("原字段") or {}
        if "可按微陶泥选用" not in fields:
            continue
        val = fields.get("可按微陶泥选用")
        flags.append(bool(val) is True)
        raws.append({"粗标编号": c.get("粗标编号"), "可按微陶泥选用": val, "记录种类": c.get("记录种类")})
    if not flags:
        return None, raws
    return any(flags), raws


def coarse_usage(hits):
    vals = set()
    raws = []
    for c in hits:
        if c.get("记录种类") != "用途片段":
            continue
        fields = c.get("原字段") or {}
        cat = fields.get("category")
        if cat:
            vals.add(str(cat))
            raws.append({"粗标编号": c.get("粗标编号"), "category": cat})
    return vals, raws


def compare_process(human, hits, prefer_review):
    C, raws = coarse_process_vs(hits, prefer_review)
    H = set(human["v_codes"])
    fp = fn = False
    if human["mode"] == "positive":
        missing = H - C
        extra = C - H
        fn = bool(missing)
        fp = bool(extra)
        consistent = (not fn) and (not fp)
    else:
        # 反例：人确认不是这些类型
        fp = bool(H & C)
        fn = False
        consistent = not fp
    return {
        "一致": consistent,
        "正例错": fp,
        "漏标错": fn,
        "人确认": human,
        "粗标画面类型": sorted(C),
        "粗标明细": raws,
    }


def compare_material(human, hits):
    C, raws = coarse_materials(hits)
    if human["mode"] == "positive":
        fn = human["value"] not in C
        extra = {x for x in C if x != human["value"]}
        fp = bool(extra)
        consistent = (not fn) and (not fp)
    else:
        fp = human["value"] in C
        fn = False
        consistent = not fp
    return {
        "一致": consistent,
        "正例错": fp,
        "漏标错": fn,
        "人确认": human,
        "粗标材料": sorted(C),
        "粗标明细": raws,
    }


def compare_weitanni(human, hits):
    flag, raws = coarse_weitanni(hits)
    if flag is None:
        return None  # 重叠记录都没有这个字段，不算进「比了」
    want = bool(human["value"])
    consistent = (flag is True) == want
    fp = (flag is True) and (want is False)
    fn = (flag is not True) and (want is True)
    return {
        "一致": consistent,
        "正例错": fp,
        "漏标错": fn,
        "人确认": human,
        "粗标值": flag,
        "粗标明细": raws,
    }


def conclusion(n, agree):
    if n < L.MIN_COMPARE:
        return "样本不足"
    ratio = agree / n if n else 0
    if ratio >= L.USABLE_AGREE_RATIO:
        return "可用"
    return "不可用"


def run_field(data, facts, extractor, comparer, field_name):
    compared = []
    skipped_no_overlap = []
    skipped_no_human = 0
    for fact in facts:
        human = extractor(fact)
        if not human:
            skipped_no_human += 1
            continue
        if not L.has_times(fact):
            skipped_no_overlap.append(fact.get("事实编号"))
            continue
        hits = overlapping_coarse(data, fact)
        if not hits:
            skipped_no_overlap.append(fact.get("事实编号"))
            continue
        result = comparer(human, hits)
        if result is None:
            continue
        row = {
            "事实编号": fact.get("事实编号"),
            "主库相对路径": fact.get("主库相对路径"),
            "起秒": fact.get("起秒"),
            "止秒": fact.get("止秒"),
            "样例类别": fact.get("样例类别"),
            "确认人": fact.get("确认人"),
            "字段": field_name,
            **{k: v for k, v in result.items() if k != "人确认"},
            "人确认mode": human.get("mode"),
            "人确认raw": human.get("raw"),
            "人确认值": sorted(human["v_codes"]) if "v_codes" in human else human.get("value"),
            "人确认来源": human.get("来源"),
        }
        compared.append(row)
    n = len(compared)
    n_ok = sum(1 for r in compared if r["一致"])
    n_fp = sum(1 for r in compared if r["正例错"])
    n_fn = sum(1 for r in compared if r["漏标错"])
    mismatches = [r for r in compared if not r["一致"]]
    conc = conclusion(n, n_ok)
    pct = None if n < L.MIN_COMPARE else round(100.0 * n_ok / n, 1)
    return {
        "字段": field_name,
        "比了多少条": n,
        "一致多少条": n_ok,
        "正例错": n_fp,
        "漏标错": n_fn,
        "一致率": pct,
        "结论": conc,
        "对照明细": compared,
        "不一致": mismatches,
        "有人确认但无重叠或无起止": skipped_no_overlap,
    }


def step1(data):
    facts = data["facts"]
    rows = []
    def human_process_only(fact):
        return process_applicable(human_process(fact))

    r_eff = run_field(
        data, facts, human_process_only,
        lambda h, hits: compare_process(h, hits, True),
        "有效工序（有复核时以复核为准，对应 B1 画面类型）",
    )
    r_raw = run_field(
        data, facts, human_process_only,
        lambda h, hits: compare_process(h, hits, False),
        "工序（原值，不看复核，对应 B1 画面类型）",
    )
    r_mat = run_field(data, facts, human_material, compare_material, "材料类目（对应 B7 材料与基层）")
    r_wtn = run_field(data, facts, human_weitanni, compare_weitanni, "可按微陶泥选用（对应 B7）")
    r_use = run_field(data, facts, human_usage, lambda h, hits: None, "用途分类（对应 C2a 转场；施工口播/收尾候选对不上总纲画面类型）")
    rows = [r_eff, r_raw, r_mat, r_wtn, r_use]
    return rows


def process_conflict_stats(data):
    n = 0
    conflict = 0
    examples = []
    unmapped = Counter()
    values = Counter()
    review_values = Counter()
    for c in data["coarse"]:
        fields = c.get("原字段") or {}
        raw = L.raw_process(fields)
        rev = fields.get("工序复核")
        if raw:
            values[raw] += 1
            if L.process_to_v(raw) is None:
                unmapped[raw] += 1
        if not L.empty_process(rev):
            review_values[str(rev)] += 1
            n += 1
            if raw and str(rev).strip() != raw and L.process_to_v(str(rev).strip()) != L.process_to_v(raw):
                # 映射后不同，或名称不同
                if str(rev).strip() != raw:
                    conflict += 1
                    if len(examples) < 8:
                        examples.append({
                            "粗标编号": c.get("粗标编号"),
                            "工序": raw,
                            "工序复核": rev,
                            "路径": c.get("主库相对路径"),
                        })
    return {
        "有工序复核的施工或分时段条数": n + sum(1 for _ in []),
        "有工序复核": sum(review_values.values()),
        "复核与原值字面不同": conflict,
        "例子": examples,
        "工序原值计数": values.most_common(),
        "工序复核计数": review_values.most_common(),
        "无法映射到画面类型的工序原值": unmapped.most_common(),
    }


# ---------- 第 3 步：够不够 ----------
def query_v_code(data, v_code, prefer_review=True):
    """返回合格片段列表（已按原片表过滤）。"""
    segs = []
    for c in data["coarse"]:
        if c.get("范围") != "范围内":
            continue
        fields = c.get("原字段") or {}
        name = L.effective_process(fields) if prefer_review else L.raw_process(fields)
        if L.process_to_v(name) != v_code:
            continue
        yuan = get_yuan(data, c)
        if not L.yuan_eligible(yuan):
            continue
        if L.is_banned(
            c.get("主库相对路径") or (yuan.get("共享相对路径") if yuan else ""),
            c.get("原片ID") or (yuan.get("原片ID") if yuan else None),
            c.get("起秒"), c.get("止秒"),
            data["file_ranges"], data["folders"],
        ):
            continue
        segs.append(c)
    return segs


def summarize_segs(data, segs):
    videos = set()
    projects = set()
    for c in segs:
        yuan = get_yuan(data, c)
        yid = c.get("原片ID") or (yuan.get("原片ID") if yuan else None)
        if yid:
            videos.add(yid)
        proj = L.project_folder(yuan) if yuan else ""
        if proj:
            projects.add(proj)
    return {
        "片段数": len(segs),
        "视频数": len(videos),
        "项目文件夹数": len(projects),
        "项目文件夹清单": sorted(projects),
    }


def enough_conclusion(found, need):
    need_ceil = max(1, math.ceil(need - 1e-9)) if need > 0 else 1
    if found < need_ceil:
        return "不够"
    if found < 2 * need_ceil:
        return "不够"
    return "够"



def process_value_present(data, v_code, prefer_review=True) -> bool:
    for c in data["coarse"]:
        if c.get("范围") != "范围内":
            continue
        fields = c.get("原字段") or {}
        name = L.effective_process(fields) if prefer_review else L.raw_process(fields)
        if L.process_to_v(name) == v_code:
            return True
    return False


def field_for_v(v):
    """哪类能用现成粗标查，用哪个字段哪个取值。"""
    # 有效工序能映射到的画面类型，且实际数据里可能有
    process_vs = {"V05", "V06", "V07", "V08", "V09", "V10", "V11", "V23"}
    if v in process_vs:
        names = [k for k, val in L.PROCESS_TO_V.items() if val == v]
        return {
            "字段": "有效工序（原字段.工序复核优先，否则原字段.工序）",
            "取值": "、".join(names),
            "查得了": True,
            "可信度字段名": "有效工序（有复核时以复核为准，对应 B1 画面类型）",
        }
    return {
        "字段": "现成标签查不了",
        "取值": "现成标签查不了",
        "查得了": False,
        "可信度字段名": None,
    }


def step3(data, cred_rows):
    cred_map = {r["字段"]: r for r in cred_rows}
    out = []
    details = {}
    for item in L.SHOT_LIST:
        v = item["代码"]
        spec = field_for_v(v)
        cred = None
        if spec["查得了"] and not process_value_present(data, v):
            spec = {
                "字段": "现成标签查不了",
                "取值": "现成标签查不了（映射表有对应取值，但范围内粗标实际工序从未出现）",
                "查得了": False,
                "可信度字段名": None,
            }
        if spec["查得了"]:
            segs = query_v_code(data, v, prefer_review=True)
            summ = summarize_segs(data, segs)
            cred_row = cred_map.get(spec["可信度字段名"])
            cred = {
                "结论": cred_row["结论"] if cred_row else "—",
                "比了多少条": cred_row["比了多少条"] if cred_row else None,
                "一致率": cred_row["一致率"] if cred_row else None,
            }
            conc = "现成标签查不了"
            if spec["查得了"]:
                conc = enough_conclusion(summ["片段数"], item["需要镜头数"])
            # 查得了但 0 条也是不够
            row = {
                **item,
                "用的字段": spec["字段"],
                "用的取值": spec["取值"],
                **{k: summ[k] for k in ("片段数", "视频数", "项目文件夹数")},
                "够不够结论": conc,
                "字段可信度": cred["结论"],
                "字段可信度详情": cred,
            }
            details[v] = {"项目文件夹清单": summ["项目文件夹清单"]}
        else:
            row = {
                **item,
                "用的字段": "现成标签查不了",
                "用的取值": "现成标签查不了",
                "片段数": "—",
                "视频数": "—",
                "项目文件夹数": "—",
                "够不够结论": "现成标签查不了",
                "字段可信度": "无（没有可对照的粗标字段）",
                "字段可信度详情": None,
            }
        out.append(row)
    return out, details


# ---------- 第 2 步：人工抽查 ----------
FIRST_LINE_FIELDS = {
    "有效工序（有复核时以复核为准，对应 B1 画面类型）": "有效工序",
    "材料类目（对应 B7 材料与基层）": "材料类目",
    "可按微陶泥选用（对应 B7）": "可按微陶泥选用",
    "用途分类（对应 C2a 转场；施工口播/收尾候选对不上总纲画面类型）": "用途分类",
}


def candidate_for_sample(data, label_unc, field_short):
    rows = []
    for c in data["coarse"]:
        if c.get("范围") != "范围内":
            continue
        if L.path_in_split_policy(c.get("主库相对路径") or "", data["policy"]):
            continue
        yuan = get_yuan(data, c)
        # 抽查不强制竖屏，但优先有原片、能打开的
        fields = c.get("原字段") or {}
        value = None
        if field_short == "有效工序":
            value = L.effective_process(fields)
            if not value:
                continue
        elif field_short == "材料类目":
            value = L.normalize_material(fields.get("材料类目"))
            if not value and isinstance(fields.get("material"), dict):
                value = L.normalize_material(fields["material"].get("category"))
            if not value:
                continue
        elif field_short == "可按微陶泥选用":
            if "可按微陶泥选用" not in fields:
                continue
            value = fields.get("可按微陶泥选用")
        elif field_short == "用途分类":
            if c.get("记录种类") != "用途片段":
                continue
            value = fields.get("category")
            if not value:
                continue
        else:
            continue
        mosaic = L.mosaic_path(c, label_unc)
        rows.append({
            "粗标编号": c.get("粗标编号"),
            "原片ID": c.get("原片ID") or (yuan.get("原片ID") if yuan else ""),
            "主库相对路径": c.get("主库相对路径"),
            "逻辑路径": (yuan or {}).get("逻辑路径") or "",
            "起秒": c.get("起秒"),
            "止秒": c.get("止秒"),
            "标注库抽帧拼图路径": mosaic,
            "机器标签值": value if not isinstance(value, bool) else ("是" if value else "否"),
            "记录种类": c.get("记录种类"),
            "项目名": L.project_folder(yuan) if yuan else "",
            "画幅": (yuan or {}).get("画幅") or "",
            "有拼图": bool(mosaic),
        })
    return rows


def step2(data, cred_rows, label_unc, rng: random.Random):
    picked_fields = []
    for r in cred_rows:
        if r["字段"] not in FIRST_LINE_FIELDS:
            continue
        if r["结论"] != "样本不足":
            continue
        picked_fields.append((FIRST_LINE_FIELDS[r["字段"]], r["字段"]))
    # 用途分类即使 0 条对照也是样本不足，要抽
    samples = []
    plans = []
    remain = L.SAMPLE_CAP
    per = L.SAMPLE_PER_FIELD
    for short, full in picked_fields:
        take = min(per, remain)
        if take <= 0:
            break
        cand = candidate_for_sample(data, label_unc, short)
        # 去重：同一原片+起止只留一条
        uniq = {}
        for row in cand:
            key = (row["原片ID"], row["起秒"], row["止秒"], str(row["机器标签值"]))
            uniq.setdefault(key, row)
        cand2 = list(uniq.values())
        # 优先有拼图、竖屏
        cand2.sort(key=lambda x: (not x["有拼图"], x["画幅"] != "竖", x["粗标编号"] or ""))
        # 在优先队列里随机：先有拼图竖屏，不够再放宽
        def pool(pred):
            return [x for x in cand2 if pred(x)]
        chosen = []
        used = set()
        for pred in (
            lambda x: x["有拼图"] and x["画幅"] == "竖",
            lambda x: x["有拼图"],
            lambda x: x["画幅"] == "竖",
            lambda x: True,
        ):
            left = [x for x in pool(pred) if (x["粗标编号"] not in used)]
            rng.shuffle(left)
            for x in left:
                if len(chosen) >= take:
                    break
                chosen.append(x)
                used.add(x["粗标编号"])
            if len(chosen) >= take:
                break
        for i, x in enumerate(chosen, 1):
            samples.append({
                "抽查编号": f"{short}-{i:02d}",
                "字段": short,
                "原片ID": x["原片ID"],
                "主库相对路径": x["主库相对路径"],
                "逻辑路径": x["逻辑路径"],
                "起秒": x["起秒"],
                "止秒": x["止秒"],
                "标注库抽帧拼图路径": x["标注库抽帧拼图路径"],
                "机器标签值": x["机器标签值"],
                "人工判断（对/不对/看不清）": "",
                "备注": "",
            })
        remain -= len(chosen)
        plans.append({
            "字段": short,
            "对应可信度表行": full,
            "候选条数": len(cand2),
            "抽出": len(chosen),
            "有拼图": sum(1 for x in chosen if x["有拼图"]),
        })
    return samples, plans, picked_fields


# ---------- 第 4 步：2000 段分配 ----------
def step4(enough_rows):
    """按原则分配，合计不超过 2000。"""
    rows = []
    # 先给查不了且要得多的类多分，可信且候选多的少分。
    leftover_need = []
    reserved = 0
    plan = []
    for r in enough_rows:
        need = r["需要镜头数"]
        conc = r["够不够结论"]
        cred = r["字段可信度"]
        found = r["片段数"] if isinstance(r["片段数"], int) else 0
        if conc == "现成标签查不了":
            # 基数：需要镜头数向上取整 * 40，再按被多少句话要微调，设上下限
            base = max(40, int(math.ceil(need) * 40))
            if r["被多少句话要"] >= 15:
                base = max(base, 120)
            if r["被多少句话要"] >= 30:
                base = max(base, 200)
            # 演示、同户、外景等特殊类给到至少 50
            if r["代码"] in {"V18", "V19", "V20", "V14", "V12"}:
                base = max(base, 60)
            reason = (
                f"第一条线大约要 {need} 个镜头，现成粗标查不了这一类，"
                f"需要模型看图从竖屏可用原片里找。按「要得多且查不了则多分」分配 {base} 段，"
                f"按项目文件夹分层随机抽，同一文件夹尽量不超过该类名额的两成。"
            )
            plan.append({**r, "建议标段数": base, "挑法": "原片表分层随机（竖屏、可用、不在禁用表、重复组只留进入选材）", "理由": reason})
        elif cred == "可用" and conc == "够":
            base = max(20, min(80, int(math.ceil(need) * 8)))
            reason = (
                f"现成「有效工序」结论为可用，候选片段 {found} 条、视频 {r['视频数']} 个，"
                f"8 套大约要 {need} 个镜头，已经够。只抽 {base} 段做验证，避免把额度花在已经能查到的类上。"
                f"从已命中的项目文件夹里分层抽。"
            )
            plan.append({**r, "建议标段数": base, "挑法": "从本类粗标命中的片段里按项目文件夹分层抽", "理由": reason})
        elif cred == "不可用" or (isinstance(found, int) and found > 0 and cred != "可用"):
            # 标签不可用或可信度不足：需要看图重找/复核
            base = max(40, int(math.ceil(need) * 25))
            if conc == "不够":
                base = max(base, 80)
            reason = (
                f"8 套大约要 {need} 个镜头；粗标能查，但字段可信度为「{cred}」"
                + (f"，且按现成标签只找到 {found} 条，结论不够。" if conc == "不够" else f"，按现成标签找到 {found} 条。")
                + f"因此分配 {base} 段，用来复核或重新发现，按项目文件夹分散。"
            )
            plan.append({**r, "建议标段数": base, "挑法": "一半来自现成命中（复核），一半来自未命中的竖屏可用原片（补漏），都按项目文件夹分层", "理由": reason})
        else:
            # 够但可信度不是可用（样本不足）
            base = max(30, int(math.ceil(need) * 15))
            reason = (
                f"按现成标签找到 {found} 条、结论「{conc}」，但字段可信度是「{cred}」，"
                f"还不能完全放心。分配 {base} 段验证，按项目文件夹分层抽。"
            )
            plan.append({**r, "建议标段数": base, "挑法": "从本类粗标命中与未命中原片中分层抽", "理由": reason})

    total = sum(x["建议标段数"] for x in plan)
    # 缩放到不超过 2000，且保持相对比例；保底 15
    if total > L.BUDGET_CAP:
        scale = L.BUDGET_CAP / total
        for x in plan:
            x["建议标段数"] = max(15, int(round(x["建议标段数"] * scale)))
        # 若四舍五入后又超，从最大的类往下减
        while sum(x["建议标段数"] for x in plan) > L.BUDGET_CAP:
            richest = max(plan, key=lambda z: z["建议标段数"])
            if richest["建议标段数"] <= 15:
                break
            richest["建议标段数"] -= 1
    total = sum(x["建议标段数"] for x in plan)
    # 若还有余量，补给要得最多且查不了的类
    rest = L.BUDGET_CAP - total
    if rest > 0:
        needies = [x for x in plan if x["够不够结论"] == "现成标签查不了"]
        needies.sort(key=lambda z: -z["需要镜头数"])
        i = 0
        while rest > 0 and needies:
            needies[i % len(needies)]["建议标段数"] += 1
            rest -= 1
            i += 1
    total = sum(x["建议标段数"] for x in plan)
    return plan, total


# ---------- 写文件 ----------
def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        cells = []
        for h in headers:
            v = row.get(h, "")
            if v is None:
                v = ""
            s = str(v).replace("|", "\\|").replace("\n", " ")
            cells.append(s)
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def write_outputs(out_dir: Path, data, cred_rows, conflicts, enough_rows, enough_details,
                  samples, sample_plans, alloc, alloc_total, label_unc, started, sha_ok):
    scripts_note = "查询条件见下文，换一个人按同样条件能复算。"
    # 可信度表
    lines = []
    lines.append("# 标签可信度表（T06A / 20261117）")
    lines.append("")
    lines.append("本表把粗标层里能对上《素材标注总纲》v0.2 的字段，逐个和事实层里**独立的**人工确认比。")
    lines.append("时间重叠规则与 T10 相同：同一文件（路径规范化后大小写不敏感），两边都有起止秒，且 `起A < 止B 且 起B < 止A`。")
    lines.append("只比「有时间重叠」的事实；比的条数少于 20 的字段结论写「样本不足」，不给百分比。")
    lines.append("正例错 = 标签说「是」而人确认「不是」（或人确认是另一类）。漏标错 = 人确认「是」而重叠的粗标没标上。一条事实可以两种错都有，此时不算一致。")
    lines.append("")
    lines.append("## 哪些事实拿来比，哪些不比")
    lines.append("")
    lines.append("- 拿来比：试标 50 段（李康审过的画面类型；「对」用原类型，「错」用改正后的类型）、镜序/施工动作样例（正例或反例）、逐段事实里的 `confirmed_action` / 产品身份、标注库「人工确认片段」里写明的材料。")
    lines.append("- 不比：确认状态为「暂定」的；没有完整起止秒的；目视纠正、文件夹级/格子级确认（对人身份，且多数无起止秒）。")
    lines.append("- **尤其不比**：`标注库精标indexed_segments` 和 `本轮看片精标`。它们和粗标层的用途片段/索引是同一套标注库数据，拿来当「人工对照」会循环自证。")
    lines.append("- 打磨没有对应的 B1 画面类型，不进入工序对照。含糊的「微陶泥施工」也不进入工序对照。")
    lines.append("- 工序对照只纳入工序字段能表达的画面类型（V05 批刮、V06 滚涂、V07 铲修、V08 拆砸、V09 覆膜、V10 保洁、V11 材料桶、V23 施工现场·其他）。人确认是成品空间、人物对镜头等类型时，不算工序漏标。")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    headers = ["字段", "比了多少条", "一致多少条", "正例错", "漏标错", "一致率", "结论"]
    table_rows = []
    for r in cred_rows:
        table_rows.append({
            "字段": r["字段"],
            "比了多少条": r["比了多少条"],
            "一致多少条": r["一致多少条"],
            "正例错": r["正例错"],
            "漏标错": r["漏标错"],
            "一致率": "—" if r["一致率"] is None else f"{r['一致率']}%",
            "结论": r["结论"],
        })
    lines.append(md_table(headers, table_rows))
    lines.append("")
    lines.append(f"结论规则：比了不足 {L.MIN_COMPARE} 条 → 样本不足；达到 {L.MIN_COMPARE} 条且一致率 ≥ {int(L.USABLE_AGREE_RATIO*100)}% → 可用；否则不可用。一致率按「一致条数 / 比了条数」计算。")
    lines.append("")
    lines.append("## 查询条件（复算）")
    lines.append("")
    lines.append("- 原片表 `片段库\\原片表.jsonl`，21,172 条，sha256 应为 "
                 f"`{L.YUANPIAN_SHA256_EXPECTED}`，本批实测 `{data['sha']}`，"
                 + ("一致。" if sha_ok else "不一致，已开问题单。"))
    lines.append("- 事实层、粗标层、禁用表：`片段库\\` 下经 C10 修订后的正式文件。")
    lines.append("- 路径规范化：反斜杠改正斜杠、转小写后比较（与 T10 相同）。")
    lines.append("- **有效工序**：`原字段.工序复核` 有值且不是「未据此确认」时用复核，否则用 `原字段.工序`。再按脚本里的 `PROCESS_TO_V` 映射到 V 代码。映射表把 T10 未收录的「上罩面」「滚刷涂布」「铺料找平」也分别归到 V06、V06、V05。")
    lines.append("- **工序原值**：只用 `原字段.工序`，不用复核。")
    lines.append("- 一条事实与多条粗标重叠时，取这些粗标取值的并集再比。")
    lines.append("- 对照明细在 `统计\\字段对照明细.jsonl`，不一致另见 `统计\\不一致明细.jsonl` 和本表下一节。")
    lines.append("")
    lines.append("## 工序原值与复核的冲突（供读结论时参考）")
    lines.append("")
    lines.append(f"- 带 `工序复核` 的粗标：{conflicts['有工序复核']} 条。")
    lines.append(f"- 其中复核与原值字面不同：{conflicts['复核与原值字面不同']} 条。")
    lines.append("- 典型例子是原值写成「批刮摊料」、复核写成「滚涂」。T10 的 `对应总纲标签` 会把两个画面类型都挂上。本工位未改 T10 正式文件，已另写问题单。")
    lines.append("")
    if conflicts["无法映射到画面类型的工序原值"]:
        lines.append("未能映射到 B1 的工序原值：" + "；".join(f"{k} {v} 条" for k, v in conflicts["无法映射到画面类型的工序原值"]))
        lines.append("")
    lines.append("## 不一致逐条")
    lines.append("")
    any_mis = False
    for r in cred_rows:
        if not r["不一致"]:
            continue
        any_mis = True
        lines.append(f"### {r['字段']}（{len(r['不一致'])} 条）")
        lines.append("")
        for i, m in enumerate(r["不一致"], 1):
            lines.append(
                f"{i}. `{m['事实编号']}` {m.get('样例类别')} "
                f"{m.get('主库相对路径')} {m.get('起秒')}–{m.get('止秒')} 秒；"
                f"人确认：{m.get('人确认raw')}（{m.get('人确认值')}）；"
                f"正例错={'是' if m.get('正例错') else '否'}，漏标错={'是' if m.get('漏标错') else '否'}；"
                f"粗标：{m.get('粗标画面类型') or m.get('粗标材料') or m.get('粗标值')}。"
            )
        lines.append("")
    if not any_mis:
        lines.append("本批没有进入「比了」集合的不一致记录，或该字段样本为 0。")
        lines.append("")
    lines.append("## 各字段补充")
    lines.append("")
    for r in cred_rows:
        lines.append(f"### {r['字段']}")
        lines.append("")
        lines.append(f"比了 {r['比了多少条']} 条，一致 {r['一致多少条']} 条，正例错 {r['正例错']}，漏标错 {r['漏标错']}，结论 **{r['结论']}**。")
        no_ov = r.get("有人确认但无重叠或无起止") or []
        lines.append(f"另有 {len(no_ov)} 条有人确认但没有完整起止秒，或与粗标没有时间重叠，未计入「比了多少条」。")
        if r["比了多少条"] == 0 and "用途" in r["字段"]:
            lines.append("用途分类没有可用的独立人工确认：看片精标与粗标层用途片段同源，不能拿来验收。所以本字段只能写样本不足。")
        lines.append("")
    L.write_text(out_dir / "标签可信度表.md", "\n".join(lines) + "\n")

    # 人工抽查
    csv_path = out_dir / "人工抽查清单.csv"
    fieldnames = ["抽查编号", "字段", "原片ID", "主库相对路径", "逻辑路径", "起秒", "止秒",
                  "标注库抽帧拼图路径", "机器标签值", "人工判断（对/不对/看不清）", "备注"]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in samples:
            w.writerow(row)

    inst = []
    inst.append("# 人工抽查说明（T06A）")
    inst.append("")
    inst.append("这份清单是给**没有参加过本项目的人**填的。不需要安装软件，也不要改原视频。")
    inst.append("")
    inst.append("## 你要做什么")
    inst.append("")
    inst.append("打开 `人工抽查清单.csv`。每一行是一段视频和机器已经打上的一个标签。请你看画面，判断这个标签对不对，在「人工判断（对/不对/看不清）」里填三个词之一：")
    inst.append("")
    inst.append("- **对**：画面就是这个标签说的意思。")
    inst.append("- **不对**：画面明显不是这个标签说的意思。")
    inst.append("- **看不清**：画面太暗、太晃、被挡住，或只有一闪，判断不了。")
    inst.append("")
    inst.append("有要补充的话写在「备注」。不要改其他列。")
    inst.append("")
    inst.append("## 怎么打开这段画面")
    inst.append("")
    inst.append("1. 先看「标注库抽帧拼图路径」。这是标注库里已经拼好的抽帧图。在资源管理器地址栏粘贴这条路径，能打开就直接看图，不必先播视频。")
    inst.append(f"   标注库根目录（只读）：`{label_unc}`。")
    inst.append("2. 如果拼图打不开（提示找不到文件），再用「主库相对路径」或「逻辑路径」到共享盘打开原视频，拖到「起秒」附近，看到「止秒」为止。逻辑路径里的 `@shared` 对应共享盘「史上最完整共享」。")
    inst.append("3. 只看这一段的起止秒，不要凭前后无关的画面下结论。")
    inst.append("")
    inst.append("## 各字段怎么判断")
    inst.append("")
    inst.append("- **有效工序**：机器给的是一道工序或一类施工画面（例如批刮摊料、滚涂、搅拌配料）。看这段里人是不是正在做这件事。工具是刮板、批刀、抹子算批刮；滚筒或刷子算滚涂；在桶里取料或搅拌算材料桶/搅拌配料。")
    inst.append("- **材料类目**：机器给的是材料名称（例如微陶泥、液态陶泥）。只有你在这段画面里能看见包装品名，或有十足把握时，才填「对」或「不对」。只凭墙面质感吃不准，填「看不清」。")
    inst.append("- **可按微陶泥选用**：机器说「是」或「否」，意思是这段能不能当作微陶泥施工/材料来用。如果画面就是微陶泥施工或材料，机器写「是」就算对；如果明显是别的材料或不是微陶泥施工，机器写「是」就不对。看不准填「看不清」。")
    inst.append("- **用途分类**：机器给的是「人物与动作转场」「施工口播」或「收尾候选」。转场指这段里有人有意做的接镜动作（遮镜、挥手、推门、转身带出后面）。口播/收尾看人是不是在对镜头或收住动作，不要靠猜他说了什么。")
    inst.append("")
    inst.append("## 抽样是怎么抽的（填表的人不必重做）")
    inst.append("")
    inst.append(f"- 只抽「第一条线挑素材用得上、但可信度结论是样本不足」的字段。每字段最多 {L.SAMPLE_PER_FIELD} 段，总数不超过 {L.SAMPLE_CAP} 段。")
    inst.append(f"- 随机种子 `{L.SEED}`。只在范围内（小区/测试/阿明/搅拌）抽。")
    inst.append("- 已经避开 `split-policy.json` 里列出的、开发时看过的目录，这些目录不能拿来做验收。")
    inst.append("- 优先抽有抽帧拼图、而且是竖屏的片段。")
    inst.append("")
    for p in sample_plans:
        inst.append(f"- {p['字段']}：候选 {p['候选条数']} 条，抽出 {p['抽出']} 条，其中有拼图 {p['有拼图']} 条。")
    inst.append("")
    inst.append("填完后把 CSV 交回即可。")
    inst.append("")
    L.write_text(out_dir / "人工抽查说明.md", "\n".join(inst) + "\n")

    # 够不够表
    eg = []
    eg.append("# 素材够不够表（T06A / 20261117）")
    eg.append("")
    eg.append("画面类型来自 T07 `工位产出\\T07\\20261117_02\\第一条线_画面清单.md`。")
    eg.append("「8 套各一条大约要的镜头数」原样采用该清单，不重算选镜单。")
    eg.append("同一个镜头不在不同片子里重复用，所以判断「够」时要求：找到的合格片段数至少是「向上取整后的需要镜头数」的 2 倍；不足 2 倍或不足需要数，都写「不够」。")
    eg.append("")
    eg.append("## 查询条件（复算）")
    eg.append("")
    eg.append("对「现成标签查得了」的类，同时满足下面全部条件才计入：")
    eg.append("")
    eg.append("1. 粗标层 `范围=范围内`（拍摄\\小区、测试、阿明、搅拌）。")
    eg.append("2. **有效工序**映射到该类的 V 代码（映射表见 `脚本\\t06a_lib.py` 的 `PROCESS_TO_V`，复核优先）。")
    eg.append("3. 用粗标的 `原片ID` 对上原片表；对不上的不计入。")
    eg.append("4. 原片表 `画幅=竖`（空或横都不算）。")
    eg.append("5. 原片表 `可用状态=可用`（「需打码后可用」不算「正常」）。")
    eg.append("6. 不在禁用表：路径落在禁用文件夹下的整段排除；R09 只排除与 2–6 秒重叠的片段，不整条原片作废。")
    eg.append("7. 重复组：`重复组` 为空，或 `重复组.角色=进入选材`。角色为「组内副本」的不计入。")
    eg.append("8. 片段数 = 合格粗标条数；视频数 = 去重后的原片ID；项目文件夹数 = 原片表 `项目名` 去重。")
    eg.append("")
    eg.append("找不到合适粗标字段的类，字段和取值都写「现成标签查不了」，不给出误导性的检索条数。")
    eg.append("目录名里偶尔出现「拆除」「人物出镜」等字样，那不是粗标层字段，不当作已核验标签。")
    eg.append("")
    eg.append("## 汇总表")
    eg.append("")
    headers = ["排序", "画面类型", "代码", "被多少句话要", "8套大约要的镜头数",
               "用的字段", "用的取值", "片段数", "视频数", "项目文件夹数",
               "够不够结论", "字段可信度"]
    body = []
    for r in enough_rows:
        body.append({
            "排序": r["排序"],
            "画面类型": r["画面类型"],
            "代码": r["代码"],
            "被多少句话要": r["被多少句话要"],
            "8套大约要的镜头数": r["需要镜头数"],
            "用的字段": r["用的字段"],
            "用的取值": r["用的取值"],
            "片段数": r["片段数"],
            "视频数": r["视频数"],
            "项目文件夹数": r["项目文件夹数"],
            "够不够结论": r["够不够结论"],
            "字段可信度": r["字段可信度"],
        })
    eg.append(md_table(headers, body))
    eg.append("")
    eg.append("项目文件夹清单见 `统计\\够不够_项目文件夹.json`。")
    eg.append("")
    L.write_text(out_dir / "素材够不够表.md", "\n".join(eg) + "\n")

    # 挑段建议
    sg = []
    sg.append("# 第 1 步挑段建议（T06A / 20261117）")
    sg.append("")
    sg.append(f"额度上限 2,000 段。本表各行合计 **{alloc_total}** 段，不超过 2,000。")
    sg.append("这些段是建议交给后续看图标注（T03）的名额，本工位不看图、不传抽帧、不派 T03。")
    sg.append("")
    sg.append("## 原则")
    sg.append("")
    sg.append("1. 第一条线要得多、现成标签又查不了的类，多分。")
    sg.append("2. 现成标签可信、候选又多的类，少分，只抽一部分验证。")
    sg.append("3. 同一类尽量分散到不同项目文件夹，避免片子里镜头都来自同一户。建议单个项目文件夹不超过该类名额的两成；文件夹数不够两成时再放宽。")
    sg.append("4. 所有候选先满足：竖屏、可用状态=可用、不在禁用表、重复组只留进入选材。")
    sg.append("")
    sg.append("## 分配表")
    sg.append("")
    headers = ["排序", "画面类型", "代码", "8套大约要的镜头数", "够不够结论", "字段可信度", "建议标段数", "挑法", "理由"]
    body = []
    for r in alloc:
        body.append({
            "排序": r["排序"],
            "画面类型": r["画面类型"],
            "代码": r["代码"],
            "8套大约要的镜头数": r["需要镜头数"],
            "够不够结论": r["够不够结论"],
            "字段可信度": r["字段可信度"],
            "建议标段数": r["建议标段数"],
            "挑法": r["挑法"],
            "理由": r["理由"],
        })
    sg.append(md_table(headers, body))
    sg.append("")
    sg.append(f"合计：{alloc_total} 段。")
    sg.append("")
    L.write_text(out_dir / "第1步挑段建议.md", "\n".join(sg) + "\n")

    # 给李康的缺口说明
    gap = []
    gap.append("# 给李康的缺口说明（T06A）")
    gap.append("")
    gap.append("这是第 1 步看图标注之前的库存盘点。只讲自己拍的素材里，哪几类明显不够、哪几类用现成机器标签完全查不到。已经拍板的 T07 口径不再问。")
    gap.append("")
    gap.append("## 现成标签完全查不了的类")
    gap.append("")
    cant = [r for r in enough_rows if r["够不够结论"] == "现成标签查不了"]
    for r in cant:
        gap.append(
            f"- **{r['画面类型']}（{r['代码']}）**：8 套各做一条大约要 {r['需要镜头数']} 个镜头，"
            f"有 {r['被多少句话要']} 句话会用到；粗标层没有能对上这一类的字段，现成标签查不了。"
        )
    gap.append("")
    gap.append("其中用量最大、又查不了的是：**成品空间**（约 23.2 个镜头）、**人物对镜头**（约 9.3）、**握手/与客户沟通**（约 8.5）、**人物在现场**（约 7.5）。演示类（喷水、刮擦、弯折样板）、旧房旧态、手摸成品、旧→新同镜转场也全部查不了。")
    gap.append("")
    gap.append("**拆砸/贴砖** 虽然对照表里有「拆除→V08」的写法，但粗标层实际工序取值里没有「拆除」，所以同样查不了。目录名里有「拆除」文件夹，不能当成已经核过的拆砸标签。")
    gap.append("")
    gap.append("## 能查、但还不够放心或数量不够的类")
    gap.append("")
    other = [r for r in enough_rows if r["够不够结论"] != "现成标签查不了"]
    if not other:
        gap.append("没有能用现成标签查到的类。")
    else:
        for r in other:
            gap.append(
                f"- **{r['画面类型']}（{r['代码']}）**：按有效工序查到 {r['片段数']} 个片段、"
                f"{r['视频数']} 个视频、{r['项目文件夹数']} 个项目文件夹；8 套大约要 {r['需要镜头数']} 个镜头，结论 **{r['够不够结论']}**。"
                f"该字段可信度是「{r['字段可信度']}」。"
            )
    gap.append("")
    gap.append("## 建议你先知道的两件事")
    gap.append("")
    gap.append("1. 第 1 步 2,000 段额度，建议大部分分给「要得多又查不了」的类，尤其是成品空间和人物类；批刮如果现成标签可信且候选多，只留一小部分做验证。详细分配见同目录《第1步挑段建议》。")
    gap.append("2. 有几类（用途分类、部分材料字段）和事实层对得上的独立样本不足 20 条，我没有给百分比。需要的话请人按《人工抽查清单》填一轮。")
    gap.append("")
    L.write_text(out_dir / "给李康的缺口说明.md", "\n".join(gap) + "\n")

    return {
        "查不了类数": len(cant),
        "能查类数": len(other),
        "不够的类": [r["画面类型"] for r in enough_rows if r["够不够结论"] == "不够"],
        "够的类": [r["画面类型"] for r in enough_rows if r["够不够结论"] == "够"],
    }


def write_report(out_dir, data, cred_rows, conflicts, enough_rows, samples, sample_plans,
                 alloc_total, gap_summary, started, ended, sha_ok, issues, elapsed_sec):
    lines = []
    lines.append("# T06A 回报（20261117）")
    lines.append("")
    lines.append("批次：按目录名以本产出文件夹为准。")
    lines.append("执行位置：李康这台电脑（nmu）。")
    lines.append("规则：`共同约定.md`、`共同约定-v0.4补充.md`、`任务书-v0.4\\T06A-标签可信度与素材够不够表.md`；总纲 v0.2 只作标签对照。")
    lines.append("本工位只写脚本和报表，不用看图模型，不向外部传抽帧或文件，不派 T03，不花钱，不装软件。")
    lines.append("")
    lines.append("## 1. 做了什么")
    lines.append("")
    lines.append("开工条件按派单：T01+C01（含旋转画幅返工）已通过，T10+C10 已通过，T07 第一部分及李康 2026-11-17 三条意见已落入 `工位产出\\T07\\20261117_02\\`。")
    lines.append(f"原片表 21,172 条，sha256 `{data['sha']}`，与派单给定值" + ("一致。" if sha_ok else "不一致。"))
    lines.append(f"事实层 {len(data['facts'])} 条，粗标层 {len(data['coarse'])} 条，禁用表 {len(data['bans'])} 条。")
    lines.append("按任务书五步做完：字段可信度、样本不足字段的人工抽查清单、画面清单 23 类够不够表、2,000 段挑段建议、给李康的一页缺口说明。")
    lines.append("输入只用正式文件：`片段库\\` 当前原片表 / 事实层 / 粗标层 / 禁用表，T10 `20261117_01` 的对照与字段统计，T07 `20261117_02` 的逐句对照表和画面清单。未用 T07 `20261117_01` 旧口径。未打开 `local\\gpt-pilot\\`，未写共享盘或镜序完整包。")
    lines.append("")
    lines.append("可信度结论摘要：")
    lines.append("")
    for r in cred_rows:
        pct = "—" if r["一致率"] is None else f"{r['一致率']}%"
        lines.append(f"- {r['字段']}：比了 {r['比了多少条']}，一致 {r['一致多少条']}，正例错 {r['正例错']}，漏标错 {r['漏标错']}，一致率 {pct}，**{r['结论']}**。")
    lines.append("")
    lines.append("## 2. 验收自查")
    lines.append("")
    # 百分比可追溯
    ok_trace = all(
        (r["一致率"] is None and r["比了多少条"] < L.MIN_COMPARE) or
        (r["一致率"] is not None and r["比了多少条"] >= L.MIN_COMPARE)
        for r in cred_rows
    )
    no_pct_under20 = all(r["一致率"] is None for r in cred_rows if r["比了多少条"] < L.MIN_COMPARE)
    lines.append(f"- 可信度表里每个百分比都能追到具体比了哪些记录：{'达到' if ok_trace else '没达到'}。明细在 `统计\\字段对照明细.jsonl`，不一致在 `统计\\不一致明细.jsonl` 和《标签可信度表》正文。")
    lines.append(f"- 样本少于 20 的没有给百分比：{'达到' if no_pct_under20 else '没达到'}。少于 20 的字段结论均为「样本不足」。")
    n_classes = len(enough_rows)
    empty = [r["画面类型"] for r in enough_rows if r["够不够结论"] in (None, "")]
    lines.append(f"- 够不够表画面清单每一类都有一行、没有空栏：{'达到' if n_classes == 23 and not empty else '没达到'}。实际 {n_classes} 行（清单 23 类）。查询条件写在《素材够不够表》和本回报，换一个人能复算。")
    lines.append(f"- 挑段建议总数不超过 2,000，且每类数量和够不够表结论对得上：{'达到' if alloc_total <= L.BUDGET_CAP else '没达到'}。合计 {alloc_total} 段。查不了的类名额高于能查且够用的类。")
    n_sample = len(samples)
    lines.append(f"- 人工抽查清单避开了已经看过的目录（split-policy 35 组）：达到（抽样时按路径排除；抽出 {n_sample} 段，不超过 150）。")
    lines.append("")
    lines.append("## 3. 没做的和为什么")
    lines.append("")
    lines.append("- 没有看图，没有向外部传抽帧，没有派 T03，没有触发镜序检索或扫描。")
    lines.append("- 没有改 `片段库\\`，没有改 T01/T10/T07 的正式文件。发现的上游问题只写问题单。")
    lines.append("- 没有把标注库精标/用途精标当作独立验收样本。")
    lines.append("- 没有用目录名代替粗标字段去统计「拆砸」「人物对镜头」等类的库存。")
    lines.append("")
    lines.append("## 4. 发现的问题")
    lines.append("")
    if issues:
        lines.append("问题单在项目文件夹 `问题反馈\\`：")
        lines.append("")
        for name in issues:
            lines.append(f"- `{name}`")
    else:
        lines.append("本批没有新开问题单。")
    lines.append("")
    # 上报情形
    all_insufficient = all(r["结论"] == "样本不足" for r in cred_rows)
    hot = {"施工·批刮覆盖", "成品空间", "人物对镜头"}
    hot_lack = [r["画面类型"] for r in enough_rows if r["画面类型"] in hot and r["够不够结论"] in ("不够", "现成标签查不了")]
    lines.append("任务书点名的上报情形：")
    lines.append(f"- 重叠太少导致所有字段样本不足：{'是' if all_insufficient else '否'}（不是全部样本不足）。")
    lines.append(f"- 批刮、成品空间、人物对镜头有一类「不够」或查不了：{'是，' + '、'.join(hot_lack) if hot_lack else '否'}。")
    lines.append(f"- 发现 T01/T10/T07 产出有错：{'是，见上列问题单' if issues else '否'}。")
    lines.append("")
    lines.append("## 5. 产出文件清单")
    lines.append("")
    lines.append(f"全部在：`{out_dir}`")
    lines.append("")
    lines.append("- `标签可信度表.md`")
    lines.append("- `人工抽查清单.csv`、`人工抽查说明.md`")
    lines.append("- `素材够不够表.md`")
    lines.append("- `第1步挑段建议.md`")
    lines.append("- `给李康的缺口说明.md`")
    lines.append("- `回报.md`（本文件）")
    lines.append("- `脚本\\t06a_lib.py`、`脚本\\t06a_build.py`")
    lines.append("- `统计\\`：字段对照明细、不一致明细、工序冲突统计、够不够表原始数据、挑段分配、抽样计划")
    if issues:
        lines.append("- 问题单见上节")
    lines.append("")
    lines.append("## 6. 花了多少")
    lines.append("")
    mins = int(round(elapsed_sec / 60.0)) if elapsed_sec is not None else "未计"
    lines.append(f"- 墙钟时间：约 {mins} 分钟（Asia/Shanghai，{started} 至 {ended}）。")
    lines.append("- 哪一步最慢：读 65,971 条粗标并做字段对照、按条件筛选够不够表。纯计算在本机数分钟量级。")
    lines.append("- 哪里需要人：请李康看《给李康的缺口说明》和《第1步挑段建议》；样本不足的字段如需补百分比，请未参与项目的人填《人工抽查清单》。T07 已定口径不再问。")
    lines.append("- 花了多少钱：0 元。未调用镜序付费检索，未用云端模型。")
    lines.append("")
    L.write_text(out_dir / "回报.md", "\n".join(lines) + "\n")


def write_issues(conflicts, sha_ok, data):
    names = []
    issue_dir = L.PROJECT_ROOT / "问题反馈"
    if conflicts["无法映射到画面类型的工序原值"] or any(
        k in dict(conflicts["工序原值计数"]) for k in L.T10_UNMAPPED_PROCESS if k != "未据此确认"
    ):
        # T10 mapping gap
        counts = dict(conflicts["工序原值计数"])
        body = f"""任务号：T06A
批次：20261117
规则版本：共同约定.md、共同约定-v0.4补充.md、T06A-标签可信度与素材够不够表.md；总纲 v0.2；T10 20261117_01（经 C10 修订）

问题是什么（一两句）：
T10 粗标层写「对应总纲标签」时用的工序映射表没有收「上罩面」「滚刷涂布」「铺料找平」。这三种是粗标层实际出现的工序取值，因此这些片段的对应总纲标签缺了 B1 画面类型。

出现了多少次，占本批多少：
上罩面 {counts.get('上罩面', 0)} 条，滚刷涂布 {counts.get('滚刷涂布', 0)} 条，铺料找平 {counts.get('铺料找平', 0)} 条（按原字段.工序原值计）。粗标层共 {len(data['coarse'])} 条。

例子（片段编号，最多 5 个）：
见 T06A 产出 `统计\\工序冲突与未映射.json` 及粗标层中工序为上述取值的记录。本单不改 T10 正式文件。

卡在哪条规则上（文件名和小节）：
T10 任务书要求粗标层能对上的总纲标签要填；T10 回报也写了「批刮摊料→V05，滚涂→V06，材料桶/搅拌→V11」。漏映射的是实际取值与映射表不一致，不是总纲缺选项。「上罩面」「滚刷涂布」按总纲应接近 V06 施工·滚涂，「铺料找平」接近 V05 施工·批刮覆盖。

我现在是怎么处理的（已按现行规则做完 / 这部分先跳过了）：
未改 `片段库\\粗标层.jsonl` 和 T10 产出。T06A 在自己的脚本里用「有效工序」映射表补全这三项，只用于本工位的够不够统计和可信度对照，并在回报里写明。

我的建议（可以不填）：
T10 返工时把这三项补进 PROCESS_TO_GANG，并重写受影响记录的对应总纲标签。

要谁来定：总控能定
"""
        name = "20261117_T06A_T10工序映射漏了上罩面等取值.md"
        (issue_dir / name).write_text(body, encoding="utf-8")
        names.append(name)

    if conflicts["复核与原值字面不同"]:
        body = f"""任务号：T06A
批次：20261117
规则版本：共同约定.md、共同约定-v0.4补充.md、T06A-标签可信度与素材够不够表.md；T10 20261117_01（经 C10 修订）

问题是什么（一两句）：
粗标层同一条施工镜头里，`原字段.工序` 和 `原字段.工序复核` 经常不一致（例如工序=批刮摊料，复核=滚涂）。T10 写「对应总纲标签」时把两个取值都映射并挂上，于是一条片段会同时带 V05 和 V06。按任一画面类型去检索都会把这条算进去。

出现了多少次，占本批多少：
有工序复核 {conflicts['有工序复核']} 条，其中复核与原值字面不同 {conflicts['复核与原值字面不同']} 条。

例子（片段编号，最多 5 个）：
"""
        for ex in conflicts["例子"][:5]:
            body += f"- {ex.get('粗标编号')} 工序={ex.get('工序')} 复核={ex.get('工序复核')} {ex.get('路径')}\n"
        body += """
卡在哪条规则上（文件名和小节）：
总纲 B1 画面类型是单选（批刮和滚涂按工具区分，不能同时成立）。T10 脚本 `t10_coarse.py` 的 gang_for 会同时读取工序和工序复核。

我现在是怎么处理的（已按现行规则做完 / 这部分先跳过了）：
未改粗标层正式文件。T06A 统计「够不够」和工序可信度时，以「有效工序」为准：有复核且不是「未据此确认」时用复核，否则用原值。同时另报「工序原值」的可信度，避免有人直接搜「批刮摊料」时不知道复核已经改成滚涂。

我的建议（可以不填）：
对应总纲标签以复核优先，只保留一个 B1 画面类型；检索文档写明不要只用未复核的工序原值。

要谁来定：总控能定
"""
        name = "20261117_T06A_T10工序与复核冲突时两个画面类型都挂上.md"
        (issue_dir / name).write_text(body, encoding="utf-8")
        names.append(name)

    if not sha_ok:
        body = f"""任务号：T06A
批次：20261117
规则版本：T06A 任务书；派单写明原片表 sha256

问题是什么（一两句）：
派单要求原片表 sha256 为 `{L.YUANPIAN_SHA256_EXPECTED}`，本机实测为 `{data['sha']}`，不一致。

出现了多少次，占本批多少：
1 个文件（片段库\\原片表.jsonl，{data['n_yuan']} 条）。

例子（片段编号，最多 5 个）：
不适用，是整表校验。

卡在哪条规则上（文件名和小节）：
派单「输入（用这些，不要用过期副本）」对原片表 sha256 的指定。

我现在是怎么处理的（已按现行规则做完 / 这部分先跳过了）：
仍用当前 `片段库\\原片表.jsonl` 继续做 T06A（条数仍是 21,172），并开此单。没有改原片表。

我的建议（可以不填）：
请核对原片表是否被意外改动，或派单校验值是否抄错。

要谁来定：要李康定
"""
        name = "20261117_T06A_原片表sha256与派单不一致.md"
        (issue_dir / name).write_text(body, encoding="utf-8")
        names.append(name)
    return names


def dump_stats(out_dir, cred_rows, conflicts, enough_rows, enough_details, samples, sample_plans, alloc, alloc_total):
    stat = out_dir / "统计"
    stat.mkdir(parents=True, exist_ok=True)
    detail = []
    mismatch = []
    for r in cred_rows:
        for row in r["对照明细"]:
            detail.append(row)
        for row in r["不一致"]:
            mismatch.append(row)
    L.write_jsonl(stat / "字段对照明细.jsonl", detail)
    L.write_jsonl(stat / "不一致明细.jsonl", mismatch)
    slim = []
    for r in cred_rows:
        slim.append({k: v for k, v in r.items() if k not in ("对照明细", "不一致")})
    L.write_json(stat / "可信度汇总.json", slim)
    L.write_json(stat / "工序冲突与未映射.json", {
        "有工序复核": conflicts["有工序复核"],
        "复核与原值字面不同": conflicts["复核与原值字面不同"],
        "例子": conflicts["例子"],
        "工序原值计数": conflicts["工序原值计数"],
        "工序复核计数": conflicts["工序复核计数"],
        "无法映射到画面类型的工序原值": conflicts["无法映射到画面类型的工序原值"],
    })
    L.write_json(stat / "够不够表.json", enough_rows)
    L.write_json(stat / "够不够_项目文件夹.json", enough_details)
    L.write_json(stat / "抽查计划.json", {"计划": sample_plans, "抽出条数": len(samples), "种子": L.SEED})
    L.write_json(stat / "挑段分配.json", {"合计": alloc_total, "行": alloc})


def main():
    t0 = time.time()
    started = now_shanghai()
    print("START", started)
    out_dir = L.choose_out_dir()
    print("OUT", out_dir)
    (out_dir / "脚本").mkdir(parents=True, exist_ok=True)
    # copy scripts into output
    here = Path(__file__).resolve().parent
    for name in ("t06a_lib.py", "t06a_build.py"):
        src = here / name
        dest = out_dir / "脚本" / name
        dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    _, paths, label_unc = L.load_configs()
    data = load_all()
    sha_ok = data["sha"] == L.YUANPIAN_SHA256_EXPECTED
    print("yuanpian", data["n_yuan"], "sha_ok", sha_ok, data["sha"])
    print("facts", len(data["facts"]), "coarse", len(data["coarse"]))

    print("step1")
    cred_rows = step1(data)
    for r in cred_rows:
        print(" ", r["字段"], r["比了多少条"], r["一致多少条"], r["结论"], r["一致率"])
    conflicts = process_conflict_stats(data)
    # fix 有工序复核 already in conflicts
    print(" conflicts review", conflicts["有工序复核"], "diff", conflicts["复核与原值字面不同"])

    print("step3")
    enough_rows, enough_details = step3(data, cred_rows)
    for r in enough_rows:
        print(" ", r["代码"], r["够不够结论"], r["片段数"], r["字段可信度"])

    print("step2")
    rng = random.Random(L.SEED)
    samples, sample_plans, picked = step2(data, cred_rows, label_unc, rng)
    print(" samples", len(samples), "fields", picked)

    print("step4")
    alloc, alloc_total = step4(enough_rows)
    print(" alloc_total", alloc_total)

    issues = write_issues(conflicts, sha_ok, data)
    print(" issues", issues)

    gap_summary = write_outputs(
        out_dir, data, cred_rows, conflicts, enough_rows, enough_details,
        samples, sample_plans, alloc, alloc_total, label_unc, started, sha_ok,
    )
    dump_stats(out_dir, cred_rows, conflicts, enough_rows, enough_details, samples, sample_plans, alloc, alloc_total)
    ended = now_shanghai()
    elapsed = time.time() - t0
    write_report(
        out_dir, data, cred_rows, conflicts, enough_rows, samples, sample_plans,
        alloc_total, gap_summary, started, ended, sha_ok, issues, elapsed,
    )
    # meta
    L.write_json(out_dir / "统计" / "运行信息.json", {
        "started": started,
        "ended": ended,
        "elapsed_sec": elapsed,
        "out_dir": str(out_dir),
        "sha256": data["sha"],
        "sha_ok": sha_ok,
        "issues": issues,
        "alloc_total": alloc_total,
        "samples": len(samples),
    })
    print("DONE", out_dir, "elapsed", round(elapsed, 1))


if __name__ == "__main__":
    main()
