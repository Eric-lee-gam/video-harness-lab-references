# -*- coding: utf-8 -*-
"""Convert annotation-library machine tags into 粗标层.jsonl, then field stats."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t10_lib as L

# Conservative maps. Unmapped values stay empty.
PROCESS_TO_GANG = {
    "批刮摊料": "B1 画面类型=V05 施工·批刮覆盖",
    "批刮覆盖": "B1 画面类型=V05 施工·批刮覆盖",
    "批刮": "B1 画面类型=V05 施工·批刮覆盖",
    "墙面基面上的批刮": "B1 画面类型=V05 施工·批刮覆盖",
    "滚涂": "B1 画面类型=V06 施工·滚涂",
    "滚涂罩面": "B1 画面类型=V06 施工·滚涂",
    "罩面": "B1 画面类型=V06 施工·滚涂",
    "搅拌配料": "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）",
    "取料": "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）",
    "纯取料": "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）",
    "材料桶展示": "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）",
    "基层处理": "B1 画面类型=V23 施工现场·其他",
    "基面批刮": "B1 画面类型=V05 施工·批刮覆盖",
    "拆除": "B1 画面类型=V08 拆砸/贴砖（传统做法）",
    "铲除": "B1 画面类型=V07 铲修旧墙/旧顶",
    "覆膜保护": "B1 画面类型=V09 铺保护膜/贴胶带",
    "清洁": "B1 画面类型=V10 保洁/清扫（施工前后）",
    "抹布擦地面": "B1 画面类型=V10 保洁/清扫（施工前后）",
    "铺料找平": "B1 画面类型=V05 施工·批刮覆盖",
    "刮刀批刮": "B1 画面类型=V05 施工·批刮覆盖",
    "批刀批刮": "B1 画面类型=V05 施工·批刮覆盖",
    "上罩面": "B1 画面类型=V06 施工·滚涂",
    "滚刷涂布": "B1 画面类型=V06 施工·滚涂",
    "滚涂（基层未明）": "B1 画面类型=V06 施工·滚涂",
    "罩面（工序）": "B1 画面类型=V06 施工·滚涂",
    "备料或展示": "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）",
    "其他工序": "B1 画面类型=V23 施工现场·其他",
}
USAGE_TO_GANG = {
    "人物与动作转场": "C2a 转场镜头",
    "施工口播": "",
    "收尾候选": "",
}
CATEGORY_TO_GANG = {
    "人物与动作转场": "C2a 转场镜头",
    "施工口播": "",
    "收尾候选": "",
}


def _empty_process(val):
    if val is None:
        return True
    return str(val).strip() in {"", "None", "null", "未据此确认", "待确认", "瓷釉改色或底漆"}


def effective_process(proc, rev):
    """有复核且不是空值时用复核，否则用工序。空值集合与 T06A 有效工序一致。"""
    if not _empty_process(rev):
        return str(rev).strip()
    if not _empty_process(proc):
        return str(proc).strip()
    return None


def gang_for(**fields):
    labels = []
    # B1：有效工序只映射一次，避免工序和复核各挂一个画面类型。
    eff = effective_process(fields.get("工序"), fields.get("工序复核"))
    if eff and eff in PROCESS_TO_GANG:
        labels.append(PROCESS_TO_GANG[eff])
    for key in ("confirmed_action", "category", "category_usage"):
        val = fields.get(key)
        if not val:
            continue
        s = str(val)
        if s in PROCESS_TO_GANG:
            # 不用动作名再挂第二个 B1
            continue
        elif s in USAGE_TO_GANG:
            if USAGE_TO_GANG[s]:
                labels.append(USAGE_TO_GANG[s])
    # material
    if fields.get("材料类目") or fields.get("material_category"):
        labels.append("B7 材料与基层")
    if fields.get("可按微陶泥选用") is True or fields.get("可按微陶泥批刮选用") is True:
        labels.append("B7 材料与基层（可按微陶泥选用）")
    if fields.get("audio_status"):
        labels.append("C4 声音")
    if fields.get("directory_limits") or fields.get("usage_limits") or fields.get("limits"):
        labels.append("A3 权利与限制")
    # unique preserve order
    seen = set()
    out = []
    for x in labels:
        if x and x not in seen:
            seen.add(x)
            out.append(x)
    return out


def overlap(a0, a1, b0, b1):
    if a0 is None or a1 is None or b0 is None or b1 is None:
        return False
    try:
        a0, a1, b0, b1 = float(a0), float(a1), float(b0), float(b1)
    except (TypeError, ValueError):
        return False
    return a0 < b1 and b0 < a1


def load_human_marks():
    """Facts that should mark matching coarse rows."""
    marks = []
    path = L.CLIPLIB / "事实层.jsonl"
    for _, rec in L.iter_jsonl(path):
        rel = rec.get("主库相对路径")
        if not rel:
            continue
        src = rec.get("来源文件") or ""
        kind = rec.get("样例类别") or (rec.get("内容") or {})
        # mark annotation-human and also any fact with times on same file
        marks.append({
            "path": L.norm_slash(rel).lower(),
            "start": rec.get("起秒"),
            "end": rec.get("止秒"),
            "事实编号": rec.get("事实编号"),
            "来源文件": src,
            "确认级别": rec.get("确认级别"),
        })
    return marks


def coarse_row(*, loc, start, end, source_file, source_id, original_fields, record_kind, human_hits, extra=None):
    rec = {
        "层": "粗标层",
        "主库相对路径": loc.get("主库相对路径"),
        "原片ID": None,
        "镜序素材ID": loc.get("镜序素材ID"),
        "标注库ID": loc.get("标注库ID"),
        "起秒": start,
        "止秒": end,
        "记录种类": record_kind,
        "来源文件": source_file,
        "来源条目标识": source_id,
        "范围": loc.get("范围") or "范围外",
        "目录": loc.get("目录"),
        "定位到文件": loc.get("定位到文件"),
        "原字段": original_fields,
        "对应总纲标签": gang_for(
            工序=original_fields.get("工序") or original_fields.get("工序复核"),
            工序复核=original_fields.get("工序复核"),
            category=original_fields.get("category"),
            材料类目=original_fields.get("材料类目") or (original_fields.get("material") or {}).get("category") if isinstance(original_fields.get("material"), dict) else original_fields.get("材料类目"),
            可按微陶泥选用=original_fields.get("可按微陶泥选用"),
            可按微陶泥批刮选用=original_fields.get("可按微陶泥批刮选用") or original_fields.get("可按微陶泥批刮选用"),
            audio_status=original_fields.get("audio_status"),
            directory_limits=original_fields.get("directory_limits"),
            usage_limits=original_fields.get("usage_limits"),
            limits=original_fields.get("limits"),
        ),
        "人工核对标记": False,
        "对应事实编号": [],
        "原片ID说明": "T01 原片表尚未产出，本批先留空",
    }
    key = L.norm_slash(loc.get("主库相对路径") or "").lower()
    hits = []
    for m in human_hits.get(key, []):
        if rec["确认可匹配"] if False else True:
            if m["start"] is None or m["end"] is None or start is None or end is None:
                if m["确认级别"] == "文件夹级":
                    continue
                # whole-file human correction without seconds: mark all segments of that file
                if m["start"] is None and m["end"] is None:
                    hits.append(m["事实编号"])
            elif overlap(start, end, m["start"], m["end"]):
                hits.append(m["事实编号"])
    if hits:
        rec["人工核对标记"] = True
        rec["对应事实编号"] = hits
    if extra:
        rec.update(extra)
    return rec


def run():
    print("loading indexes...")
    catalog = L.load_catalog()
    ann = L.load_ann_indexes()
    marks = load_human_marks()
    human_hits = defaultdict(list)
    for m in marks:
        human_hits[m["path"]].append(m)
    print("human marks", len(marks), "files", len(human_hits))

    rows = []
    originals = {}  # path_l -> {目录, 有粗标, 来源}

    def touch_original(rel, directory, has_coarse, src):
        if not rel:
            return
        key = L.norm_slash(rel).lower()
        rec = originals.setdefault(key, {"主库相对路径": rel, "目录": directory, "有粗标": False, "来源": set()})
        if directory and not rec["目录"]:
            rec["目录"] = directory
        rec["来源"].add(src)
        if has_coarse:
            rec["有粗标"] = True

    # universe from indexes
    index_files = [
        (L.LABEL / "小区全库" / "数据" / "AI剪辑检索索引.jsonl", "小区全库/数据/AI剪辑检索索引.jsonl"),
        (L.LABEL / "测试阿明搅拌" / "数据" / "AI剪辑检索索引.jsonl", "测试阿明搅拌/数据/AI剪辑检索索引.jsonl"),
    ]
    n_tl = 0
    for fp, relfile in index_files:
        for lineno, o in L.iter_jsonl(fp):
            loc = L.locate(path=o.get("source_path"), ann_id=o.get("id"), catalog=catalog, ann=ann)
            d = loc.get("目录")
            touch_original(loc.get("主库相对路径"), d, False, "索引")
            timeline = o.get("timeline") or []
            for j, seg in enumerate(timeline):
                # merge parent fields needed for mapping, keep segment as 原字段 plus parent crumbs
                fields = dict(seg)
                fields["audio_status"] = o.get("audio_status")
                fields["directory_limits"] = o.get("directory_limits")
                fields["usage_limits"] = o.get("usage_limits")
                if isinstance(o.get("material"), dict):
                    fields["material"] = o["material"]
                    fields["材料类目"] = o["material"].get("category") or o["material"].get("材料类目")
                if "工序" not in fields:
                    fields["工序"] = seg.get("工序")
                row = coarse_row(
                    loc=loc, start=seg.get("start"), end=seg.get("end"),
                    source_file=relfile + "#timeline",
                    source_id="%s:timeline:%s-%s:%s" % (o.get("id"), seg.get("start"), seg.get("end"), j),
                    original_fields=fields,
                    record_kind="分时段",
                    human_hits=human_hits,
                    extra={"整段意图": o.get("whole_video_intent"), "材料": o.get("material")},
                )
                rows.append(row)
                n_tl += 1
                touch_original(loc.get("主库相对路径"), d, True, "分时段")

    print("timeline rows", n_tl)

    # 施工镜头
    n_cons = 0
    cons_fp = L.LABEL / "微陶泥施工" / "施工镜头.jsonl"
    for lineno, o in L.iter_jsonl(cons_fp):
        loc = L.locate(path=o.get("source_path"), ann_id=o.get("id"), catalog=catalog, ann=ann)
        d = loc.get("目录")
        touch_original(loc.get("主库相对路径"), d, False, "施工镜头原片")
        row = coarse_row(
            loc=loc, start=o.get("start"), end=o.get("end"),
            source_file="微陶泥施工/施工镜头.jsonl",
            source_id="%s:%s-%s" % (o.get("id"), o.get("start"), o.get("end")),
            original_fields=o,
            record_kind="施工镜头",
            human_hits=human_hits,
        )
        rows.append(row)
        n_cons += 1
        touch_original(loc.get("主库相对路径"), d, True, "施工镜头")
    print("施工镜头", n_cons)

    # 用途
    n_use = 0
    use_fp = L.LABEL / "小区全库" / "数据" / "按用途检索.jsonl"
    for lineno, o in L.iter_jsonl(use_fp):
        loc = L.locate(path=o.get("path"), catalog=catalog, ann=ann)
        d = loc.get("目录")
        touch_original(loc.get("主库相对路径"), d, False, "用途原片")
        row = coarse_row(
            loc=loc, start=o.get("start"), end=o.get("end"),
            source_file="小区全库/数据/按用途检索.jsonl",
            source_id="%s:%s-%s" % (o.get("id"), o.get("start"), o.get("end")),
            original_fields=o,
            record_kind="用途片段",
            human_hits=human_hits,
        )
        rows.append(row)
        n_use += 1
        touch_original(loc.get("主库相对路径"), d, True, "用途片段")
    print("用途", n_use)

    # catalog xiaoq not in index
    cat_by_id, _ = catalog
    xiaoq_missing = 0
    for rec in cat_by_id.values():
        if rec.get("root") != "xiaoq":
            continue
        rel = rec.get("主库相对路径")
        if not rel:
            continue
        key = L.norm_slash(rel).lower()
        if key not in originals:
            touch_original(rel, "小区", False, "镜序登记表")
            xiaoq_missing += 1
    print("catalog xiaoq not in index", xiaoq_missing)

    for i, rec in enumerate(rows, 1):
        rec["粗标编号"] = "C%06d" % i

    dest = L.CLIPLIB / "粗标层.jsonl"
    L.write_jsonl(dest, rows)
    # do not duplicate 60k+ into 片段库副本? write a pointer and counts only; also write copy for completeness? 
    # Task says other stats go to 工位产出. The official file is 片段库. Copying 60k is ok (~maybe 200MB). Skip full copy, write counts.
    print("WROTE", dest, "n", len(rows))

    # coverage by four dirs
    coverage = {}
    for d in ("小区", "测试", "阿明", "搅拌"):
        items = [v for v in originals.values() if v.get("目录") == d]
        yes = sum(1 for v in items if v["有粗标"])
        no = sum(1 for v in items if not v["有粗标"])
        coverage[d] = {"原片数": len(items), "有粗标": yes, "无粗标": no}
    other = [v for v in originals.values() if v.get("目录") not in ("小区", "测试", "阿明", "搅拌")]
    coverage["范围外或其他"] = {
        "原片数": len(other),
        "有粗标": sum(1 for v in other if v["有粗标"]),
        "无粗标": sum(1 for v in other if not v["有粗标"]),
        "目录分布": dict(Counter(v.get("目录") or "未知" for v in other)),
    }

    # field stats
    # flatten 原字段 for stats, plus top-level useful fields. Per 目录.
    # Free-text-ish fields: description, 画面, action, basis, evidence, 镜头精确描述, whole_video_intent, 整段意图...
    FREE = {
        "description", "画面", "action", "basis", "evidence", "镜头精确描述",
        "whole_video_intent", "整段意图", "intent_evidence", "quality_note",
        "confirmation_evidence", "note",
    }
    SKIP_NESTED = {"frame_times", "speech_indices", "preview", "evidence"}

    def flatten(d, prefix=""):
        items = {}
        if not isinstance(d, dict):
            return items
        for k, v in d.items():
            key = ("%s.%s" % (prefix, k)) if prefix else k
            if isinstance(v, dict):
                items.update(flatten(v, key))
            else:
                items[key] = v
        return items

    stats = {}
    by_dir_rows = defaultdict(list)
    for r in rows:
        d = r.get("目录") or "未知"
        by_dir_rows[d].append(r)

    def field_stats(subset):
        filled = Counter()
        values = defaultdict(Counter)
        text_len = defaultdict(list)
        n = len(subset)
        for r in subset:
            # top some + 原字段 flattened
            bag = {
                "记录种类": r.get("记录种类"),
                "范围": r.get("范围"),
                "目录": r.get("目录"),
                "人工核对标记": r.get("人工核对标记"),
            }
            bag.update(flatten(r.get("原字段") or {}))
            # 对应总纲标签 as joined
            bag["对应总纲标签"] = " | ".join(r.get("对应总纲标签") or []) or None
            seen_keys = set()
            for k, v in bag.items():
                if v is None or v == "" or v == [] or v == {}:
                    continue
                if isinstance(v, (list, dict)):
                    # count as filled; lists of scalars as values if short
                    filled[k] += 1
                    if isinstance(v, list) and v and not isinstance(v[0], (dict, list)):
                        for item in v:
                            values[k][str(item)] += 1
                    continue
                filled[k] += 1
                if k.split(".")[-1] in FREE or (isinstance(v, str) and len(str(v)) > 40):
                    text_len[k].append(len(str(v)))
                else:
                    values[k][str(v)] += 1
        table = []
        all_keys = sorted(set(filled) | set(values) | set(text_len))
        for k in all_keys:
            rec = {"字段": k, "填了条数": filled.get(k, 0), "总条数": n, "填写率": round(filled.get(k, 0) / n, 4) if n else 0}
            if k in text_len:
                lens = text_len[k]
                rec["类型"] = "自由文本"
                rec["平均字数"] = round(sum(lens) / len(lens), 2) if lens else 0
            else:
                rec["类型"] = "取值统计"
                # cap value listing
                common = values[k].most_common(50)
                rec["取值"] = [{ "值": a, "次数": b} for a, b in common]
                rec["不同取值数"] = len(values[k])
            table.append(rec)
        return table

    stats["全部"] = field_stats(rows)
    for d in ("小区", "测试", "阿明", "搅拌"):
        stats[d] = field_stats(by_dir_rows.get(d) or [])
    stats["范围外或其他"] = field_stats([r for r in rows if r.get("目录") not in ("小区", "测试", "阿明", "搅拌")])

    # write a compact markdown table per dir: one row per field
    md = ["# 粗标层字段取值统计", "", "总条数 %d。四个目录分开；自由文本只报填了多少条和平均字数。" % len(rows), ""]
    md.append("## 范围内原片有无粗标")
    md.append("")
    md.append("| 目录 | 原片数 | 有粗标 | 无粗标 |")
    md.append("|---|---:|---:|---:|")
    for d in ("小区", "测试", "阿明", "搅拌"):
        c = coverage[d]
        md.append("| %s | %s | %s | %s |" % (d, c["原片数"], c["有粗标"], c["无粗标"]))
    c = coverage["范围外或其他"]
    md.append("| 范围外或其他 | %s | %s | %s |" % (c["原片数"], c["有粗标"], c["无粗标"]))
    md.append("")
    for section, table in stats.items():
        md.append("## %s（%d 条粗标记录）" % (section, len(rows) if section=="全部" else len(by_dir_rows.get(section) or ([r for r in rows if r.get("目录") not in ("小区","测试","阿明","搅拌")] if section=="范围外或其他" else []))))
        md.append("")
        md.append("| 字段 | 填了条数 | 填写率 | 类型 | 平均字数或主要取值 |")
        md.append("|---|---:|---:|---|---|")
        for rec in table:
            if rec["类型"] == "自由文本":
                extra = "平均字数 %s" % rec.get("平均字数")
            else:
                tops = rec.get("取值") or []
                extra = "；".join("%s=%s" % (t["值"], t["次数"]) for t in tops[:8])
                if rec.get("不同取值数", 0) > 8:
                    extra += " 等共 %s 个取值" % rec["不同取值数"]
            md.append("| %s | %s | %s | %s | %s |" % (rec["字段"].replace("|","/"), rec["填了条数"], rec["填写率"], rec["类型"], extra.replace("|","/")))
        md.append("")

    (L.OUT / "统计" / "粗标层字段取值统计.md").write_text("\n".join(md), encoding="utf-8")
    L.write_json(L.OUT / "统计" / "粗标层覆盖.json", {
        "粗标层条数": len(rows),
        "分时段": n_tl,
        "施工镜头": n_cons,
        "用途片段": n_use,
        "人工核对标记条数": sum(1 for r in rows if r.get("人工核对标记")),
        "覆盖": coverage,
        "镜序登记表小区有但索引没有": xiaoq_missing,
    })
    # write stats json without huge value tails already capped
    L.write_json(L.OUT / "统计" / "粗标层字段取值统计.json", stats)
    print("coverage", coverage)
    print("human marked", sum(1 for r in rows if r.get("人工核对标记")))
    return rows, coverage


if __name__ == "__main__":
    run()
