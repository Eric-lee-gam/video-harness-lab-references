# -*- coding: utf-8 -*-
"""T12 第 1 步：挑上传样本。只写产出文件夹，不改共享盘/原片，不调用 Twelve Labs。"""
from __future__ import annotations

import csv
import json
import random
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from t12_lib import (
    B1_TAG_TO_CODE,
    OUT_ROOT,
    PROJECT_ROOT,
    RULES_ROOT,
    SEED,
    T07_PICTURE_TYPES,
    TARGET_AIM_SEC,
    TARGET_MAX_SEC,
    TARGET_MIN_SEC,
    dur_of,
    exclude_reasons,
    fmt_hours,
    is_under_xiaoqu_or_test,
    load_ban_rules,
    load_jsonl,
    load_unusable_30,
    load_yuanpian,
    looks_like_file_path,
    master_relpath,
    norm_key,
    resolve_yuan,
    share_path,
    top_dir,
)

PER_CATEGORY_CAP = 8
PER_PROJECT_UNLABELED = 1


def now_sh() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "（Asia/Shanghai）"


def load_trial50():
    p = RULES_ROOT / "试标50段" / "_对应表.csv"
    text = p.read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(text.splitlines()))
    return p, rows


def collect_fact_videos(by_id, by_path):
    """范围内、落到具体文件的事实层片段所在视频。文件夹级事实不展开成整夹视频。"""
    found = {}  # 原片ID -> {rec, facts, unmatched notes}
    folder_facts = []
    unmatched = []
    for rec in load_jsonl(PROJECT_ROOT / "片段库" / "事实层.jsonl"):
        if rec.get("范围") != "范围内":
            continue
        path = rec.get("主库相对路径") or ""
        if rec.get("确认级别") == "文件夹级" or not looks_like_file_path(path):
            folder_facts.append(rec)
            continue
        yuan = resolve_yuan(by_id, by_path, rec.get("原片ID"), path)
        if not yuan:
            unmatched.append(rec)
            continue
        oid = yuan["原片ID"]
        slot = found.setdefault(oid, {"rec": yuan, "facts": []})
        slot["facts"].append(rec)
    return found, folder_facts, unmatched


def collect_trial_videos(by_id, by_path, trial_rows):
    found = {}
    unmatched = []
    for row in trial_rows:
        path = row.get("原片") or ""
        yuan = resolve_yuan(by_id, by_path, None, path)
        if not yuan:
            unmatched.append(row)
            continue
        oid = yuan["原片ID"]
        slot = found.setdefault(oid, {"rec": yuan, "segs": []})
        slot["segs"].append(row.get("seg") or "")
    return found, unmatched


def load_coarse_index():
    """原片ID -> 出现过的画面类型代码集合；以及是否有任何粗标记录。"""
    has_any = set()
    codes = defaultdict(set)
    for rec in load_jsonl(PROJECT_ROOT / "片段库" / "粗标层.jsonl"):
        oid = rec.get("原片ID")
        if not oid:
            continue
        has_any.add(oid)
        for t in rec.get("对应总纲标签") or []:
            code = B1_TAG_TO_CODE.get(str(t))
            if code:
                codes[oid].add(code)
    return has_any, codes


def add_item(selected, oid, rec, reason):
    if oid in selected:
        if reason not in selected[oid]["reasons"]:
            selected[oid]["reasons"].append(reason)
        return "dup"
    selected[oid] = {"rec": rec, "reasons": [reason]}
    return "new"


def total_sec(selected) -> float:
    return sum(dur_of(v["rec"]) for v in selected.values())


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def main():
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "脚本").mkdir(exist_ok=True)
    (OUT_ROOT / "统计").mkdir(exist_ok=True)
    rng = random.Random(SEED)

    by_id, by_path = load_yuanpian()
    unusable_ids, unusable_paths, unusable_recs = load_unusable_30()
    ban_rules = load_ban_rules()
    trial_path, trial_rows = load_trial50()
    has_coarse, coarse_codes = load_coarse_index()

    fact_found, folder_facts, fact_unmatched = collect_fact_videos(by_id, by_path)
    trial_found, trial_unmatched = collect_trial_videos(by_id, by_path, trial_rows)

    selected = {}
    dropped = []  # mandatory candidates that were removed

    def consider_mandatory(oid, rec, reason, group):
        why = exclude_reasons(rec, unusable_ids, unusable_paths, ban_rules)
        if why:
            dropped.append({
                "组": group,
                "原片ID": oid,
                "主库相对路径": master_relpath(rec),
                "时长秒": dur_of(rec),
                "为什么选它本应是": reason,
                "拿掉原因": "；".join(why),
            })
            return False
        add_item(selected, oid, rec, reason)
        return True

    for oid, slot in fact_found.items():
        n = len(slot["facts"])
        reason = f"事实层范围内片段所在视频（{n}条事实）"
        consider_mandatory(oid, slot["rec"], reason, "事实层")

    for oid, slot in trial_found.items():
        segs = "、".join(s for s in slot["segs"] if s)
        reason = f"试标50段所在视频（{segs}）"
        consider_mandatory(oid, slot["rec"], reason, "试标50段")

    after_mandatory_sec = total_sec(selected)
    after_mandatory_n = len(selected)

    # 补充：仅 拍摄\小区 和 拍摄\测试，且通过排除
    def eligible_supplement(rec) -> bool:
        if not is_under_xiaoqu_or_test(rec):
            return False
        if rec["原片ID"] in selected:
            return False
        return not exclude_reasons(rec, unusable_ids, unusable_paths, ban_rules)

    # 按类从粗标层取候选
    code_to_name = {c: n for c, n in T07_PICTURE_TYPES}
    category_pool = defaultdict(list)
    for oid, codes in coarse_codes.items():
        rec = by_id.get(oid)
        if not rec or not eligible_supplement(rec):
            continue
        for code in codes:
            category_pool[code].append(oid)

    category_stats = []
    supplements_cat = []
    # 先每类至少尽量取，受总时长上限约束
    remaining_codes = [c for c, _ in T07_PICTURE_TYPES if c in category_pool]
    # 打乱每类候选
    for code in remaining_codes:
        rng.shuffle(category_pool[code])

    # 动态 cap：若必选已经接近上限，每类少取
    budget = TARGET_AIM_SEC - total_sec(selected)
    if budget <= 0:
        per_cat = 0
    elif budget < 20 * 60:
        per_cat = 2
    else:
        per_cat = PER_CATEGORY_CAP

    taken_by_code = {code: 0 for code in remaining_codes}
    skipped_budget_by_code = {code: 0 for code in remaining_codes}
    # 第一轮：每类先取 per_cat 条（一些）
    for code in remaining_codes:
        name = code_to_name.get(code, code)
        for oid in category_pool[code]:
            if taken_by_code[code] >= per_cat:
                break
            rec = by_id[oid]
            if oid in selected:
                continue
            d = dur_of(rec)
            if total_sec(selected) + d > TARGET_MAX_SEC:
                skipped_budget_by_code[code] += 1
                continue
            reason = f"T07画面清单「{name}」（{code}）粗标层候选，随机抽取（种子{SEED}）"
            add_item(selected, oid, rec, reason)
            supplements_cat.append(oid)
            taken_by_code[code] += 1
    # 第二轮：合格无标签视频可能为 0，按类轮流继续取，补到约 3.15 小时（仍在 2.5–3.5 窗口内）
    if total_sec(selected) < TARGET_AIM_SEC and remaining_codes:
        pointers = {code: 0 for code in remaining_codes}
        progressed = True
        while total_sec(selected) < TARGET_AIM_SEC and progressed:
            progressed = False
            for code in remaining_codes:
                if total_sec(selected) >= TARGET_AIM_SEC:
                    break
                name = code_to_name.get(code, code)
                pool = category_pool[code]
                while pointers[code] < len(pool):
                    oid = pool[pointers[code]]
                    pointers[code] += 1
                    rec = by_id[oid]
                    if oid in selected:
                        continue
                    d = dur_of(rec)
                    if total_sec(selected) + d > TARGET_MAX_SEC:
                        skipped_budget_by_code[code] += 1
                        continue
                    reason = f"T07画面清单「{name}」（{code}）粗标层候选，随机抽取补足目标时长（种子{SEED}）"
                    add_item(selected, oid, rec, reason)
                    supplements_cat.append(oid)
                    taken_by_code[code] += 1
                    progressed = True
                    break
    for code in remaining_codes:
        name = code_to_name.get(code, code)
        category_stats.append({
            "代码": code,
            "画面类型": name,
            "粗标层可找到的合格候选数": len(category_pool[code]),
            "本批实际取了": taken_by_code[code],
            "因总时长上限未取": skipped_budget_by_code[code],
            "粗标层是否能找到候选": True,
        })
    for code, name in T07_PICTURE_TYPES:
        if code not in category_pool:
            category_stats.append({
                "代码": code,
                "画面类型": name,
                "粗标层可找到的合格候选数": 0,
                "本批实际取了": 0,
                "因总时长上限未取": 0,
                "粗标层是否能找到候选": False,
                "说明": "粗标层没有对应的 B1 画面类型标签，本步无法按类抽取",
            })

    # 再从各项目文件夹取粗标层没有标签的
    unlabeled_by_project = defaultdict(list)
    for oid, rec in by_id.items():
        if oid in has_coarse:
            continue
        if not eligible_supplement(rec):
            continue
        proj = rec.get("项目名") or rec.get("目录原名") or "(无项目名)"
        unlabeled_by_project[proj].append(oid)
    projects = list(unlabeled_by_project.keys())
    rng.shuffle(projects)
    for proj in projects:
        rng.shuffle(unlabeled_by_project[proj])

    supplements_unlabeled = []
    skipped_unlabeled_budget = 0
    projects_taken = 0
    for proj in projects:
        if total_sec(selected) >= TARGET_AIM_SEC:
            break
        taken_here = 0
        for oid in unlabeled_by_project[proj]:
            if taken_here >= PER_PROJECT_UNLABELED:
                break
            rec = by_id[oid]
            if oid in selected:
                continue
            d = dur_of(rec)
            if total_sec(selected) + d > TARGET_MAX_SEC:
                skipped_unlabeled_budget += 1
                continue
            if total_sec(selected) >= TARGET_AIM_SEC:
                break
            reason = f"项目「{proj}」粗标层没有标签，随机抽取（种子{SEED}）"
            add_item(selected, oid, rec, reason)
            supplements_unlabeled.append(oid)
            taken_here += 1
        if taken_here:
            projects_taken += 1

    # 若仍不足 2.5 小时，再从合格的小区/测试竖屏里按项目补（即使已有粗标，只要还没入选）
    extra_fill = []
    if total_sec(selected) < TARGET_MIN_SEC:
        fill_by_project = defaultdict(list)
        for oid, rec in by_id.items():
            if not eligible_supplement(rec):
                continue
            if oid in selected:
                continue
            proj = rec.get("项目名") or rec.get("目录原名") or "(无项目名)"
            fill_by_project[proj].append(oid)
        projs = list(fill_by_project.keys())
        rng.shuffle(projs)
        for proj in projs:
            if total_sec(selected) >= TARGET_MIN_SEC:
                break
            rng.shuffle(fill_by_project[proj])
            for oid in fill_by_project[proj][:2]:
                rec = by_id[oid]
                d = dur_of(rec)
                if total_sec(selected) + d > TARGET_MAX_SEC:
                    continue
                reason = f"总时长不足2.5小时，从项目「{proj}」再随机补入（种子{SEED}）"
                add_item(selected, oid, rec, reason)
                extra_fill.append(oid)
                if total_sec(selected) >= TARGET_MIN_SEC:
                    break

    # 输出清单：按 主库相对路径 排序，编号在第 2 步再赋
    items = []
    for oid, slot in selected.items():
        rec = slot["rec"]
        d = dur_of(rec)
        items.append({
            "主库相对路径": master_relpath(rec),
            "时长": f"{d:.3f}",
            "时长秒": f"{d:.3f}",
            "为什么选它": "；".join(slot["reasons"]),
            "原片ID": oid,
            "是否短于4秒": "是" if d < 4 else "否",
            "画幅": rec.get("画幅") or "",
            "旋转角度": rec.get("旋转角度") if rec.get("旋转角度") is not None else "",
            "项目名": rec.get("项目名") or "",
            "共享相对路径": rec.get("共享相对路径") or "",
            "可用状态": rec.get("可用状态") or "",
            "字节数": rec.get("字节数") or "",
            "来源目录": top_dir(rec),
        })
    items.sort(key=lambda r: r["主库相对路径"].lower())

    short_items = [r for r in items if float(r["时长秒"]) < 4]
    uploadable = [r for r in items if float(r["时长秒"]) >= 4]
    total = total_sec(selected)
    short_sec = sum(float(r["时长秒"]) for r in short_items)
    uploadable_sec = sum(float(r["时长秒"]) for r in uploadable)

    write_csv(
        OUT_ROOT / "上传清单.csv",
        items,
        ["主库相对路径", "时长", "为什么选它", "原片ID", "时长秒", "是否短于4秒",
         "画幅", "旋转角度", "项目名", "共享相对路径", "可用状态", "字节数", "来源目录"],
    )
    write_csv(
        OUT_ROOT / "短于4秒清单.csv",
        short_items,
        ["主库相对路径", "时长", "为什么选它", "原片ID", "时长秒", "项目名", "来源目录"],
    )
    write_csv(
        OUT_ROOT / "拿掉清单.csv",
        dropped,
        ["组", "原片ID", "主库相对路径", "时长秒", "为什么选它本应是", "拿掉原因"],
    )

    # 抽查：样本里不应再出现外传关键词
    residual_risk = []
    for r in items:
        rec = by_id[r["原片ID"]]
        why = exclude_reasons(rec, unusable_ids, unusable_paths, ban_rules)
        if why:
            residual_risk.append({"原片ID": r["原片ID"], "主库相对路径": r["主库相对路径"], "原因": "；".join(why)})

    stats = {
        "时间": now_sh(),
        "种子": SEED,
        "规则路径确认": {
            "试标50段_对应表": str(trial_path),
            "试标50段存在": trial_path.exists(),
            "审核结果": str(RULES_ROOT / "试标50段" / "审核结果_李康_20261116.json"),
            "看图说明v0.2": str(RULES_ROOT / "试标50段" / "看图标注任务说明_v0.2.md"),
            "T07对照表": str(PROJECT_ROOT / "工位产出" / "T07" / "20261117_05" / "第一条线_逐句对照表.tsv"),
            "T07画面清单采用": "工位产出\\T07\\20261117_02\\第一条线_画面清单.md（05批次未另存该清单，类型与02一致）",
        },
        "T01不能用30条载入": len(unusable_recs),
        "事实层": {
            "范围内落到文件并可对上原片表的视频数": len(fact_found),
            "文件夹级事实条数_不展开整夹": len(folder_facts),
            "对不上原片表": len(fact_unmatched),
        },
        "试标50段": {
            "对应表行数": len(trial_rows),
            "所在视频数": len(trial_found),
            "对不上原片表": len(trial_unmatched),
        },
        "必选入选后": {"条数": after_mandatory_n, "总秒": after_mandatory_sec, "总时长": fmt_hours(after_mandatory_sec)},
        "必选被拿掉": len(dropped),
        "补充_按T07类": len(supplements_cat),
        "补充_无粗标标签": len(supplements_unlabeled),
        "补充_无标签覆盖项目数": projects_taken,
        "无粗标标签的合格项目数": len(unlabeled_by_project),
        "补充_时长不足再补": len(extra_fill),
        "最终": {
            "条数": len(items),
            "总秒": total,
            "总时长": fmt_hours(total),
            "是否落在2.5到3.5小时": TARGET_MIN_SEC <= total <= TARGET_MAX_SEC,
            "可上传_不少于4秒": {"条数": len(uploadable), "总秒": uploadable_sec, "总时长": fmt_hours(uploadable_sec)},
            "短于4秒": {
                "条数": len(short_items),
                "总秒": short_sec,
                "占样本条数比例": (len(short_items) / len(items) if items else 0),
                "占样本时长比例": (short_sec / total if total else 0),
            },
        },
        "各类抽取": category_stats,
        "残留排除项_应为空": residual_risk,
        "对不上原片表的事实层路径": [
            {"主库相对路径": r.get("主库相对路径"), "原片ID": r.get("原片ID"), "事实编号": r.get("事实编号")}
            for r in fact_unmatched
        ],
        "对不上原片表的试标段": [
            {"seg": r.get("seg"), "原片": r.get("原片")} for r in trial_unmatched
        ],
        "文件夹级事实不展开": [
            {"主库相对路径": r.get("主库相对路径"), "确认级别": r.get("确认级别"), "事实编号": r.get("事实编号")}
            for r in folder_facts
        ],
    }
    (OUT_ROOT / "统计" / "选样统计.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 控制台摘要
    print("选样完成", flush=True)
    print("产出", OUT_ROOT / "上传清单.csv", flush=True)
    print("条数", len(items), "总时长", fmt_hours(total), flush=True)
    print("可上传>=4秒", len(uploadable), fmt_hours(uploadable_sec), flush=True)
    print("短于4秒", len(short_items), f"{(len(short_items)/len(items)*100 if items else 0):.2f}% 条", flush=True)
    print("必选拿掉", len(dropped), "残留风险", len(residual_risk), flush=True)
    print("时长窗口", "OK" if TARGET_MIN_SEC <= total <= TARGET_MAX_SEC else "不在2.5-3.5小时", flush=True)
    if fact_unmatched or trial_unmatched:
        print("有对不上原片表的记录，见统计/选样统计.json", flush=True)
    return 0 if (TARGET_MIN_SEC <= total <= TARGET_MAX_SEC and not residual_risk) else 1


if __name__ == "__main__":
    sys.exit(main())
