# -*- coding: utf-8 -*-
"""按已批准分配挑出正好 2000 段，并切出起止秒。随机种子 20261117。"""
from __future__ import annotations

import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

import t02_lib as L

OUT = L.OUT_DIR


def alloc_map():
    path = L.PROJECT_ROOT / "工位产出" / "T06A" / "20261117_03" / "统计" / "挑段分配.json"
    data = L.load_json(path)
    rows = {r["代码"]: r for r in data["行"]}
    return data, rows


def build_eligible(data):
    eligible = []
    reasons = Counter()
    for y in data["yuans"]:
        if not L.t06a.yuan_eligible(y):
            if (y.get("画幅") != "竖"):
                reasons["非竖屏或画幅空"] += 1
            elif y.get("可用状态") != "可用":
                reasons[f"可用状态={y.get('可用状态')}"] += 1
            elif not L.t06a.dedup_ok(y):
                reasons["重复组副本"] += 1
            else:
                reasons["yuan_eligible未通过"] += 1
            continue
        extra = L.extra_exclude_reason(y, data["cleanup"], data["water_ids"])
        if extra:
            reasons[extra] += 1
            continue
        if L.t06a.is_banned(
            L.main_rel_for_ban(y),
            y.get("原片ID"),
            None,
            None,
            data["file_ranges"],
            data["folders"],
        ):
            reasons["禁用表(文件夹级)"] += 1
            continue
        eligible.append(y)
    data["eligible"] = eligible
    data["eligible_ids"] = {y["原片ID"] for y in eligible if y.get("原片ID")}
    data["exclude_reasons"] = reasons
    return eligible, reasons


def collect_hits(data, v_code):
    """与 T06A query_v_code 相同的有效工序口径，再加上本批排除规则。"""
    hits_by_yuan = {}
    n_raw = 0
    for c in data["coarse"]:
        if c.get("范围") != "范围内":
            continue
        fields = c.get("原字段") or {}
        name = L.t06a.effective_process(fields)
        if L.t06a.process_to_v(name) != v_code:
            continue
        n_raw += 1
        yuan = L.get_yuan(data, c)
        if yuan is None or yuan.get("原片ID") not in data["eligible_ids"]:
            continue
        if not L.is_selectable(yuan, data):
            continue
        st = L.t06a.as_float(c.get("起秒"))
        en = L.t06a.as_float(c.get("止秒"))
        if st is None or en is None:
            continue
        if L.segment_banned(yuan, st, en, data):
            continue
        yid = yuan["原片ID"]
        rec = {
            "yuan": yuan,
            "coarse": c,
            "start": st,
            "end": en,
            "粗标编号": c.get("粗标编号"),
            "记录种类": c.get("记录种类"),
            "有效工序": name,
        }
        # 同一原片保留更像样的一条：施工镜头优先，其次更长
        prev = hits_by_yuan.get(yid)
        if prev is None:
            hits_by_yuan[yid] = rec
            continue
        kind_rank = {"施工镜头": 0, "分时段": 1, "用途片段": 2}
        better = (
            kind_rank.get(rec["记录种类"], 9),
            -(en - st),
            rec["粗标编号"] or "",
        ) < (
            kind_rank.get(prev["记录种类"], 9),
            -(prev["end"] - prev["start"]),
            prev["粗标编号"] or "",
        )
        if better:
            hits_by_yuan[yid] = rec
    return hits_by_yuan, n_raw


def finalize_segment(data, yuan, start, end, cut_info, meta):
    if start is None or end is None:
        return None
    if L.segment_banned(yuan, start, end, data):
        # 若落在仅时段禁用上，尝试错开（美女人设已整夹排除，R09 几乎不会碰到）
        return None
    start, end = L.fmt_sec(start), L.fmt_sec(end)
    if end - start < 0.5:
        return None
    rec = {
        "片段ID": L.segment_id(yuan["原片ID"], start, end),
        "原片ID": yuan["原片ID"],
        "起秒": start,
        "止秒": end,
        "逻辑路径": yuan.get("逻辑路径"),
        "项目名": L.t06a.project_folder(yuan),
        "库ID": yuan.get("库ID"),
        "时长": yuan.get("时长"),
        "宽": yuan.get("宽"),
        "高": yuan.get("高"),
        "旋转角度": yuan.get("旋转角度"),
        "画幅": yuan.get("画幅"),
        "目录原名": yuan.get("目录原名"),
        "切段": cut_info,
        **meta,
    }
    return rec


def pick_class(data, rng, v_code, quota, alloc_row, used_ids):
    name = L.t06a.V_NAME.get(v_code, alloc_row.get("画面类型") if alloc_row else v_code)
    method = (alloc_row or {}).get("挑法") or ""
    notes = {}
    picked_recs = []

    def id_fn_yuan(y):
        return y.get("原片ID") or ""

    def folder_fn_yuan(y):
        return L.t06a.project_folder(y) or "(空项目名)"

    if v_code in L.HALF_CLASSES:
        n_hit, n_miss = L.split_half(quota)
        hits_map, n_raw = collect_hits(data, v_code)
        notes["粗标有效工序原始命中条数"] = n_raw
        notes["合格命中原片数"] = len(hits_map)
        hit_cands = [rec["yuan"] for rec in hits_map.values() if rec["yuan"]["原片ID"] not in used_ids]
        hit_picked, hit_stat = L.stratified_pick(
            hit_cands, n_hit, rng, folder_fn_yuan, id_fn_yuan
        )
        notes["命中抽取"] = hit_stat
        for y in hit_picked:
            rec = hits_map[y["原片ID"]]
            a, b, info = L.cut_from_window(data, y, rec["start"], rec["end"])
            info["来源时段"] = rec["粗标编号"]
            info["记录种类"] = rec["记录种类"]
            info["有效工序"] = rec["有效工序"]
            item = finalize_segment(
                data, y, a, b, info,
                {
                    "画面类型代码": v_code,
                    "画面类型": name,
                    "挑法": "现成命中（复核）",
                    "分配挑法": method,
                    "粗标编号": rec["粗标编号"],
                    "记录种类": rec["记录种类"],
                    "有效工序": rec["有效工序"],
                },
            )
            if item:
                picked_recs.append(item)
                used_ids.add(y["原片ID"])

        # 补漏：未命中该画面类型的合格原片
        hit_ids = set(hits_map)
        miss_cands = [
            y for y in data["eligible"]
            if y["原片ID"] not in used_ids and y["原片ID"] not in hit_ids
        ]
        miss_picked, miss_stat = L.stratified_pick(
            miss_cands, n_miss, rng, folder_fn_yuan, id_fn_yuan
        )
        notes["补漏抽取"] = miss_stat
        for y in miss_picked:
            a, b, info = L.cut_from_yuan(data, y)
            item = finalize_segment(
                data, y, a, b, info,
                {
                    "画面类型代码": v_code,
                    "画面类型": name,
                    "挑法": "未命中补漏",
                    "分配挑法": method,
                    "粗标编号": info.get("来源时段"),
                    "记录种类": info.get("记录种类"),
                },
            )
            if item:
                picked_recs.append(item)
                used_ids.add(y["原片ID"])
        notes["命中目标"] = n_hit
        notes["补漏目标"] = n_miss
        notes["命中实际"] = sum(1 for r in picked_recs if r["挑法"] == "现成命中（复核）")
        notes["补漏实际"] = sum(1 for r in picked_recs if r["挑法"] == "未命中补漏")
    else:
        cands = [y for y in data["eligible"] if y["原片ID"] not in used_ids]
        picked, stat = L.stratified_pick(cands, quota, rng, folder_fn_yuan, id_fn_yuan)
        notes["分层抽取"] = stat
        for y in picked:
            a, b, info = L.cut_from_yuan(data, y)
            item = finalize_segment(
                data, y, a, b, info,
                {
                    "画面类型代码": v_code,
                    "画面类型": name,
                    "挑法": "原片表分层随机",
                    "分配挑法": method,
                    "粗标编号": info.get("来源时段"),
                    "记录种类": info.get("记录种类"),
                },
            )
            if item:
                picked_recs.append(item)
                used_ids.add(y["原片ID"])

    # 若切段失败导致不足，从同类剩余候选再补
    if len(picked_recs) < quota:
        notes["切段失败后补抽"] = quota - len(picked_recs)
        if v_code in L.HALF_CLASSES:
            hits_map, _ = collect_hits(data, v_code)
            hit_ids = set(hits_map)
            # 优先补同一挑法的缺口
            need_hit = notes.get("命中目标", 0) - notes.get("命中实际", 0)
            need_miss = notes.get("补漏目标", 0) - notes.get("补漏实际", 0)
            extra_pools = []
            if need_hit > 0:
                extra_pools.append((
                    "现成命中（复核）",
                    [hits_map[i]["yuan"] for i in hits_map if i not in used_ids],
                    need_hit,
                    True,
                    hits_map,
                ))
            if need_miss > 0:
                extra_pools.append((
                    "未命中补漏",
                    [y for y in data["eligible"] if y["原片ID"] not in used_ids and y["原片ID"] not in hit_ids],
                    need_miss,
                    False,
                    None,
                ))
        else:
            extra_pools = [(
                "原片表分层随机",
                [y for y in data["eligible"] if y["原片ID"] not in used_ids],
                quota - len(picked_recs),
                False,
                None,
            )]
        for method_name, pool, need, is_hit, hits_map in extra_pools:
            if need <= 0 or not pool:
                continue
            more, stat = L.stratified_pick(pool, need, rng, folder_fn_yuan, id_fn_yuan)
            notes.setdefault("补抽", []).append({"挑法": method_name, **stat})
            for y in more:
                if len(picked_recs) >= quota:
                    break
                if is_hit:
                    rec = hits_map[y["原片ID"]]
                    a, b, info = L.cut_from_window(data, y, rec["start"], rec["end"])
                    info["来源时段"] = rec["粗标编号"]
                    info["记录种类"] = rec["记录种类"]
                    info["有效工序"] = rec["有效工序"]
                    meta = {
                        "画面类型代码": v_code,
                        "画面类型": name,
                        "挑法": method_name,
                        "分配挑法": method,
                        "粗标编号": rec["粗标编号"],
                        "记录种类": rec["记录种类"],
                        "有效工序": rec["有效工序"],
                    }
                else:
                    a, b, info = L.cut_from_yuan(data, y)
                    meta = {
                        "画面类型代码": v_code,
                        "画面类型": name,
                        "挑法": method_name,
                        "分配挑法": method,
                        "粗标编号": info.get("来源时段"),
                        "记录种类": info.get("记录种类"),
                    }
                item = finalize_segment(data, y, a, b, info, meta)
                if item:
                    picked_recs.append(item)
                    used_ids.add(y["原片ID"])

    return picked_recs, notes


def write_markdown(path: Path, total, by_code, alloc_rows, notes_by_code, reasons, sha_ok, sha, eligible_n):
    lines = []
    lines.append("# T02 挑段清单对照")
    lines.append("")
    lines.append(f"日期：{L.now_iso()}（Asia/Shanghai）")
    lines.append(f"随机种子：`{L.SEED}`")
    lines.append(f"原片表 sha256：`{sha}`，与 T01 返工后预期一致：{'是' if sha_ok else '否'}")
    lines.append(f"合格候选原片：{eligible_n} 条。最终挑出 {total} 段。")
    lines.append("")
    lines.append("## 与批准分配逐类对照")
    lines.append("")
    lines.append("| 代码 | 画面类型 | 批准 | 实际 | 其中命中 | 其中补漏 | 其中分层随机 | 是否相符 | 放宽 |")
    lines.append("|---|---|---:|---:|---:|---:|---:|---|---|")
    all_ok = True
    for code, quota in L.ALLOC_ORDER:
        recs = by_code[code]
        name = L.t06a.V_NAME.get(code, "")
        n = len(recs)
        n_hit = sum(1 for r in recs if r["挑法"] == "现成命中（复核）")
        n_miss = sum(1 for r in recs if r["挑法"] == "未命中补漏")
        n_rand = sum(1 for r in recs if r["挑法"] == "原片表分层随机")
        ok = n == quota
        if not ok:
            all_ok = False
        note = notes_by_code[code]
        relaxed = []
        for key in ("命中抽取", "补漏抽取", "分层抽取"):
            st = note.get(key) or {}
            if st.get("放宽") or st.get("无视上限补齐"):
                relaxed.append(f"{key}实际夹上限{st.get('实际上限')}（建议{st.get('建议上限')}）")
        lines.append(
            f"| {code} | {name} | {quota} | {n} | {n_hit or '—'} | {n_miss or '—'} | {n_rand or '—'} | "
            f"{'相符' if ok else '不符'} | {'; '.join(relaxed) if relaxed else '否'} |"
        )
    lines.append("")
    lines.append(f"合计实际 {total}，批准 2000，整体{'相符' if all_ok and total == 2000 else '不符'}。")
    lines.append("")
    lines.append("## 候选排除原因（原片级，未进入合格池）")
    lines.append("")
    for k, v in reasons.most_common():
        lines.append(f"- {k}：{v}")
    lines.append("")
    lines.append("## 放宽与补抽细节")
    lines.append("")
    for code, quota in L.ALLOC_ORDER:
        note = notes_by_code[code]
        interesting = {k: v for k, v in note.items() if k not in {"粗标有效工序原始命中条数"} or True}
        # 只写有放宽或不足的类
        flags = []
        for key in ("命中抽取", "补漏抽取", "分层抽取"):
            st = note.get(key) or {}
            if st.get("放宽") or st.get("无视上限补齐") or (st and st.get("抽到", 0) < st.get("目标", 0)):
                flags.append(f"{key}={st}")
        if note.get("补抽") or flags:
            lines.append(f"### {code} {L.t06a.V_NAME.get(code,'')}")
            lines.append("")
            lines.append("```json")
            import json
            lines.append(json.dumps(note, ensure_ascii=False, indent=2))
            lines.append("```")
            lines.append("")
    if not any(True for _ in lines if _.startswith("### ")):
        lines.append("各类均未放宽两成上限，也无需补抽。")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return all_ok and total == 2000


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "脚本").mkdir(exist_ok=True)
    (OUT / "统计").mkdir(exist_ok=True)
    started = L.now_iso()
    print(f"[{started}] 开始加载数据", flush=True)
    data = L.load_all()
    print(f"原片 {len(data['yuans'])} 粗标 {len(data['coarse'])} sha_ok={data['yuan_sha_ok']} 清理排除 {len(data['cleanup'])} 水洗石ID {len(data['water_ids'])}", flush=True)
    if len(data["cleanup"]) != 30:
        print(f"警告：清理清单解析到 {len(data['cleanup'])} 条，期望 30", flush=True)
    L.build_cut_index(data)
    eligible, reasons = build_eligible(data)
    print(f"合格候选原片 {len(eligible)}", flush=True)
    for k, v in reasons.most_common():
        print(f"  排除 {k}: {v}", flush=True)

    _, alloc_rows = alloc_map()
    rng = random.Random(L.SEED)
    used_ids = set()
    all_rows = []
    by_code = defaultdict(list)
    notes_by_code = {}

    for code, quota in L.ALLOC_ORDER:
        recs, notes = pick_class(data, rng, code, quota, alloc_rows.get(code), used_ids)
        by_code[code] = recs
        notes_by_code[code] = notes
        all_rows.extend(recs)
        print(
            f"{code} 目标{quota} 实际{len(recs)} 已占用原片{len(used_ids)}",
            flush=True,
        )

    # 稳定编号：按分配表顺序已追加；拼图匿名名按最终清单顺序
    for i, rec in enumerate(all_rows, 1):
        rec["拼图文件名"] = L.anonymous_name(i)
        rec["抽帧时间戳"] = L.frame_times(rec["起秒"], rec["止秒"], rec.get("时长"))

    # 校验
    ids = [r["片段ID"] for r in all_rows]
    assert len(ids) == len(set(ids)), "片段ID 重复"
    assert len({r["原片ID"] for r in all_rows}) == len(all_rows), "原片重复"
    # 不跨过切点。两位小数取整后，与切点相差不超过 0.02 秒视为落在边界上，不是跨镜。
    cross = 0
    boundary = 0
    for r in all_rows:
        cuts = data["cuts"].get(r["原片ID"], set())
        for p in cuts:
            if r["起秒"] + 0.02 < p < r["止秒"] - 0.02:
                cross += 1
                r.setdefault("问题", []).append(f"跨越切点{p}")
            elif r["起秒"] + 1e-9 < p < r["止秒"] - 1e-9:
                boundary += 1
    print(f"跨越切点段数 {cross}（另有 {boundary} 段切点只在起止 0.02 秒边界内，视为对齐）", flush=True)

    L.write_jsonl(OUT / "挑段清单.jsonl", all_rows)
    L.write_json(OUT / "统计" / "挑段对照.json", {
        "开始": started,
        "结束": L.now_iso(),
        "种子": L.SEED,
        "合计": len(all_rows),
        "原片表sha256": data["yuan_sha256"],
        "sha一致": data["yuan_sha_ok"],
        "合格候选原片": len(eligible),
        "清理排除条数": len(data["cleanup"]),
        "水洗石原片ID数": len(data["water_ids"]),
        "排除原因": dict(reasons),
        "各类": {
            code: {
                "批准": quota,
                "实际": len(by_code[code]),
                "明细": notes_by_code[code],
                "项目文件夹数": len({r["项目名"] for r in by_code[code]}),
                "挑法计数": dict(Counter(r["挑法"] for r in by_code[code])),
            }
            for code, quota in L.ALLOC_ORDER
        },
        "跨越切点段数": cross,
    })
    ok = write_markdown(
        OUT / "挑段清单对照.md",
        len(all_rows), by_code, alloc_rows, notes_by_code,
        reasons, data["yuan_sha_ok"], data["yuan_sha256"], len(eligible),
    )
    print(f"写完 {OUT} 共 {len(all_rows)} 段 对照相符={ok}", flush=True)
    if not ok:
        sys.exit(2)


if __name__ == "__main__":
    main()
