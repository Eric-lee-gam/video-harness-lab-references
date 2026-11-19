# -*- coding: utf-8 -*-
"""C01 20261117_02：只重查第 3 项（抽 50 条看文件）。不改片段库或 T01 产出。"""
from __future__ import annotations

import json
import random
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from c01_common import (
    C01_OUT,
    EXPECTED_TABLE_COUNT,
    EXPECTED_TABLE_MTIME,
    EXPECTED_TABLE_SHA256,
    NEW_SEED,
    OLD_SEED,
    PREV_SAMPLE_PATH,
    TABLE_PATH,
    file_meta,
    format_mtime,
    full_path_from_record,
    load_json,
    load_origin_table,
    now_iso,
    orientation,
    probe_file,
    read_share_root,
    rot_equal,
    sha256_file,
    write_json,
)


def compare_one(rec: dict, share_root: str, seq: int) -> dict:
    path = full_path_from_record(share_root, rec)
    exists = path.is_file()
    size_actual = None
    size_ok = False
    if exists:
        try:
            size_actual = path.stat().st_size
            size_ok = size_actual == rec.get("字节数")
        except OSError as e:
            size_actual = f"stat失败:{e}"
            size_ok = False
    probe = {"ok": False, "error": "文件不存在，未探测"} if not exists else probe_file(path)
    dur_ok = dim_ok = rot_ok = aspect_ok = False
    aspect_mine = None
    if probe.get("ok"):
        table_dur = rec.get("时长")
        p_dur = probe.get("时长")
        if table_dur is None and p_dur is None:
            dur_ok = True
        elif table_dur is not None and p_dur is not None:
            try:
                dur_ok = abs(float(table_dur) - float(p_dur)) <= 0.1
            except (TypeError, ValueError):
                dur_ok = False
        dim_ok = (probe.get("宽") == rec.get("宽")) and (probe.get("高") == rec.get("高"))
        rot_ok = rot_equal(rec.get("旋转角度"), probe.get("旋转角度"))
        aspect_mine = orientation(probe.get("宽"), probe.get("高"), probe.get("旋转角度"))
        aspect_ok = aspect_mine == rec.get("画幅")
    all_ok = exists and size_ok and probe.get("ok") and dur_ok and dim_ok and rot_ok and aspect_ok
    return {
        "序号": seq,
        "原片ID": rec.get("原片ID"),
        "逻辑路径": rec.get("逻辑路径"),
        "库ID": rec.get("库ID"),
        "共享相对路径": rec.get("共享相对路径"),
        "出处宽高旋转": (rec.get("出处") or {}).get("宽高旋转"),
        "出处旋转画幅返工": (rec.get("出处") or {}).get("旋转画幅返工"),
        "文件存在": exists,
        "原片表字节数": rec.get("字节数"),
        "实际字节数": size_actual,
        "字节数一致": size_ok,
        "ffprobe成功": bool(probe.get("ok")),
        "ffprobe错误": probe.get("error"),
        "原片表时长": rec.get("时长"),
        "探测时长": probe.get("时长"),
        "时长一致": dur_ok,
        "原片表宽": rec.get("宽"),
        "探测宽": probe.get("宽"),
        "原片表高": rec.get("高"),
        "探测高": probe.get("高"),
        "宽高一致": dim_ok,
        "原片表旋转角度": rec.get("旋转角度"),
        "探测旋转角度": probe.get("旋转角度"),
        "旋转一致": rot_ok,
        "原片表画幅": rec.get("画幅"),
        "C01判定画幅": aspect_mine,
        "画幅一致": aspect_ok,
        "全部一致": all_ok,
        "探测用时秒": probe.get("用时秒"),
    }


def check_sample(records_by_id: dict, ids: list, share_root: str, label: str) -> list[dict]:
    rows = []
    missing = []
    for i, rid in enumerate(ids, 1):
        rec = records_by_id.get(rid)
        if rec is None:
            missing.append(rid)
            rows.append({
                "序号": i,
                "原片ID": rid,
                "逻辑路径": None,
                "全部一致": False,
                "ffprobe错误": "当前正式原片表找不到该原片ID",
            })
            print(f"  [{label}] {i}/{len(ids)} MISSING_ID {rid}", flush=True)
            continue
        row = compare_one(rec, share_root, i)
        rows.append(row)
        mark = "OK" if row["全部一致"] else "FAIL"
        print(f"  [{label}] {i}/{len(ids)} {mark} {row.get('逻辑路径')}", flush=True)
    return rows


def fail_mode(row: dict) -> str:
    keys = []
    if not row.get("文件存在"):
        keys.append("缺文件")
    if row.get("文件存在") and not row.get("字节数一致"):
        keys.append("字节数")
    if not row.get("ffprobe成功"):
        keys.append("ffprobe失败")
    if row.get("ffprobe成功") and not row.get("时长一致"):
        keys.append("时长")
    if row.get("ffprobe成功") and not row.get("宽高一致"):
        keys.append("宽高")
    if row.get("ffprobe成功") and not row.get("旋转一致"):
        keys.append("旋转")
    if row.get("ffprobe成功") and not row.get("画幅一致"):
        keys.append("画幅")
    if row.get("ffprobe错误") == "当前正式原片表找不到该原片ID":
        keys.append("原片ID不在正式表")
    return "+".join(keys) or "未分类"


def summarize(rows: list[dict], seed, label: str) -> dict:
    ok = sum(1 for r in rows if r.get("全部一致"))
    bad = [r for r in rows if not r.get("全部一致")]
    modes = Counter(fail_mode(r) for r in bad)
    return {
        "标签": label,
        "随机种子": seed,
        "抽检条数": len(rows),
        "全部一致": ok,
        "不一致": len(bad),
        "通过": ok == len(rows) and len(rows) == 50,
        "不一致原因统计": dict(modes),
        "抽中的原片ID": [r.get("原片ID") for r in rows],
        "抽中的逻辑路径": [r.get("逻辑路径") for r in rows],
        "不一致记录": bad,
    }


def yn(flag: bool) -> str:
    return "通过" if flag else "不通过"


def md_escape(s) -> str:
    return "" if s is None else str(s).replace("|", "\\|")


def write_list(a, rows, heading_ok=True):
    for row in rows:
        mark = "一致" if row.get("全部一致") else "不一致"
        a(f"{row.get('序号')}. `{row.get('原片ID')}`　`{row.get('逻辑路径')}`　{mark}")


def write_bad_details(a, bad):
    if not bad:
        return
    a("不一致的具体记录：")
    a("")
    for row in bad:
        a(
            f"- `{row.get('逻辑路径')}`（原片ID `{row.get('原片ID')}`）："
            f"存在={row.get('文件存在')} 字节数一致={row.get('字节数一致')} "
            f"时长 {row.get('原片表时长')} vs {row.get('探测时长')}（{row.get('时长一致')}） "
            f"宽高 {row.get('原片表宽')}x{row.get('原片表高')} vs {row.get('探测宽')}x{row.get('探测高')} "
            f"旋转 {row.get('原片表旋转角度')} vs {row.get('探测旋转角度')} "
            f"画幅 {row.get('原片表画幅')} vs {row.get('C01判定画幅')} "
            f"ffprobe={row.get('ffprobe成功')} {row.get('ffprobe错误') or ''} "
            f"原因={fail_mode(row)}"
        )
    a("")


def write_report(payload: dict) -> None:
    old = payload["旧种子组"]
    new = payload["新种子组"]
    table = payload["正式表核验"]
    conclusion = payload["结论"]
    lines = []
    a = lines.append
    a("# C01 检查编号对照 · 第 3 项重查 · 检查报告 · 20261117_02")
    a("")
    a(f"检查时间：{payload['开始时间']} 至 {payload['结束时间']}（Asia/Shanghai）")
    a("执行机器：nmu")
    a("被查批次：T01 `20261117_02` 旋转与画幅返工后的正式 `片段库\\原片表.jsonl`")
    a("范围：只重查第 3 项（抽 50 条看文件）。不重做第 1、2、4–8 项。未改 T01 产出，未改片段库。")
    a("规则：以 `C01-检查编号对照.md` 第 3 项为准；对照上次 `工位产出\\C01\\20261117_01\\检查报告.md` 和 T01 `20261117_02\\回报.md`。")
    a("探测：C01 自行用 `ffprobe -show_streams` 读宽、高、时长和 Display Matrix / tags.rotate 旋转，再按宽高和旋转自判画幅。时长差 0.1 秒以内算一致。")
    a("")
    a("## 结论")
    a("")
    a(f"**{conclusion}**")
    a("")
    if payload.get("结论说明"):
        a(payload["结论说明"])
        a("")
    a("")
    a("| 组 | 种子 | 结果 | 一致 | 不一致 |")
    a("|---|---:|---|---:|---:|")
    a(f"| 上次同 50 条复核 | {old['随机种子']} | {yn(old['通过'])} | {old['全部一致']} | {old['不一致']} |")
    a(f"| 新抽 50 条 | {new['随机种子']} | {yn(new['通过'])} | {new['全部一致']} | {new['不一致']} |")
    a("")

    a("## 正式表核验")
    a("")
    a("使用当前正式 `片段库\\原片表.jsonl`，不用返工前备份。")
    a("")
    a(f"- 条数：{table['条数']}（期望 {EXPECTED_TABLE_COUNT}）")
    a(f"- 字节数：{table['运行前']['字节数']}")
    a(f"- 修改时间：{table['运行前']['修改时间']}（期望 {EXPECTED_TABLE_MTIME}，相符：{'是' if table['mtime相符'] else '否'}）")
    a(f"- sha256：`{table['运行前']['sha256']}`")
    a(f"- 与 T01 回报给出的 sha256 相符：{'是' if table['sha256相符'] else '否'}")
    a(f"- 检查结束时正式表保持原样：{'是' if table['保持原样'] else '否'}")
    a("")
    dist = table.get("画幅与旋转分布") or {}
    if dist:
        a("只读统计正式表当前分布（用于对照 T01 回报，不是第 1、2、4–8 项重查）：")
        a("")
        a(f"- 画幅：竖 {dist.get('画幅竖')}，横 {dist.get('画幅横')}，空 {dist.get('画幅空')}")
        a(f"- 旋转：-90 {dist.get('旋转-90')}，90 {dist.get('旋转90')}，-180 {dist.get('旋转-180')}，0 {dist.get('旋转0')}，空 {dist.get('旋转空')}")
        a(f"- 横且旋转为 0：{dist.get('横且旋转0')}")
        a(f"- 出处宽高旋转=ffprobe：{dist.get('出处ffprobe')}；出处含「旋转画幅返工: T01-20261117_02」：{dist.get('标注返工')}")
        a(f"- 与 T01 回报数字是否一致：{'是' if dist.get('与回报一致') else '否'}{('；' + dist['差异说明']) if dist.get('差异说明') else ''}")
        a("")

    a("## 3. 抽 50 条看文件（重查）")
    a("")
    a(f"综合结果：**{yn(old['通过'] and new['通过'])}**")
    a("")

    a("### 3A. 用原种子复核上次那 50 条")
    a("")
    a(f"结果：**{yn(old['通过'])}**")
    a("")
    a(f"- 随机种子：{old['随机种子']}（与 20261117_01 相同）")
    a(f"- 抽样来源：上次 `核对/抽检50条.json` 中按原顺序的 50 个原片ID，再到当前正式表按 ID 取记录。不依赖本次读表顺序。")
    a(f"- 按原种子对当前正式表再 shuffle 一次，抽到的 50 个 ID 与上次是否相同：{'是' if payload['旧种子组'].get('按种子重抽与上次相同') else '否'}")
    a(f"- 抽检条数：{old['抽检条数']}，全部一致 {old['全部一致']}，不一致 {old['不一致']}")
    a(f"- 其中上次 47 条不一致此次纠正情况：已一致 {old.get('上次不一致此次一致')}，仍不一致 {old.get('上次不一致此次仍不一致')}")
    a(f"- 其中上次 3 条一致此次情况：仍一致 {old.get('上次一致此次仍一致')}，变为不一致 {old.get('上次一致此次不一致')}")
    a(f"- 用时：{old.get('用时秒')} 秒")
    if old.get("不一致原因统计"):
        a(f"- 不一致原因：{old['不一致原因统计']}")
    a("")
    a("抽到的记录（原片ID / 逻辑路径 / 结果）：")
    a("")
    write_list(a, payload["旧种子组明细"])
    a("")
    write_bad_details(a, old.get("不一致记录") or [])
    a("明细在 `核对/复核不换50条.json`。")
    a("")

    a("### 3B. 用新种子另抽 50 条")
    a("")
    a(f"结果：**{yn(new['通过'])}**")
    a("")
    a(f"- 随机种子：{new['随机种子']}（不是上次的 87112617，也不是 T01 的 20261117）")
    a(f"- 抽检条数：{new['抽检条数']}，全部一致 {new['全部一致']}，不一致 {new['不一致']}")
    a(f"- 与上次 50 条原片ID重叠：{new.get('与旧组重叠条数')} 条")
    a(f"- 用时：{new.get('用时秒')} 秒")
    if new.get("不一致原因统计"):
        a(f"- 不一致原因：{new['不一致原因统计']}")
    a("")
    a("抽到的记录（原片ID / 逻辑路径 / 结果）：")
    a("")
    write_list(a, payload["新种子组明细"])
    a("")
    write_bad_details(a, new.get("不一致记录") or [])
    a("明细在 `核对/新抽50条.json`。")
    a("")

    a("## 另外发现的问题")
    a("")
    extras = payload.get("另外发现的问题") or []
    if extras:
        for i, item in enumerate(extras, 1):
            a(f"{i}. {item}")
        a("")
    else:
        a("本次重查第 3 项，没有需要另外记录的问题。")
        a("")

    a("## 被查对象未改动核验")
    a("")
    a(f"- 正式表运行前：{json.dumps(table['运行前'], ensure_ascii=False)}")
    a(f"- 正式表运行后：{json.dumps(table['运行后'], ensure_ascii=False)}")
    a(f"- 保持原样：{'是' if table['保持原样'] else '否'}")
    a("")

    a("## 产出文件清单")
    a("")
    a("- `检查报告.md`（本文件）")
    a("- `脚本/c01_common.py`、`脚本/c01_recheck3.py`")
    a("- `核对/复核不换50条.json`、`核对/新抽50条.json`、`核对/检查结果.json`")
    a("")

    a("## 花了多少")
    a("")
    a(f"- 墙钟：{payload['开始时间']}–{payload['结束时间']}（Asia/Shanghai），约 {payload.get('用时秒')} 秒。")
    a(f"- {payload.get('耗时说明') or ''}")
    a("- 花了多少钱：0。未装软件，未触发线上镜序，未向云端传抽帧。未改正式原片表。")
    a("")

    path = C01_OUT / "检查报告.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写报告 {path}", flush=True)


def table_distribution(records: list[dict]) -> dict:
    aspect = Counter()
    rot_bucket = Counter()
    landscape_rot0 = 0
    src_ff = 0
    marked = 0
    for r in records:
        asp = r.get("画幅")
        if asp in (None, ""):
            aspect["空"] += 1
        else:
            aspect[asp] += 1
        rot = r.get("旋转角度")
        if rot in (None, ""):
            rot_bucket["空"] += 1
            key = "空"
        else:
            try:
                rv = float(rot)
            except (TypeError, ValueError):
                rot_bucket["其他"] += 1
                key = "其他"
            else:
                if abs(rv - (-90)) < 0.5:
                    rot_bucket["-90"] += 1
                    key = "-90"
                elif abs(rv - 90) < 0.5:
                    rot_bucket["90"] += 1
                    key = "90"
                elif abs(rv - (-180)) < 0.5 or abs(rv - 180) < 0.5:
                    rot_bucket["-180"] += 1
                    key = "-180"
                elif abs(rv) < 0.5:
                    rot_bucket["0"] += 1
                    key = "0"
                else:
                    rot_bucket["其他"] += 1
                    key = "其他"
        if asp == "横" and key == "0":
            landscape_rot0 += 1
        src = (r.get("出处") or {}).get("宽高旋转")
        if src == "ffprobe":
            src_ff += 1
        if (r.get("出处") or {}).get("旋转画幅返工"):
            marked += 1
    expected = {
        "画幅竖": 20995, "画幅横": 155, "画幅空": 22,
        "旋转-90": 18255, "旋转90": 154, "旋转-180": 21, "旋转0": 2720, "旋转空": 22,
        "横且旋转0": 132,
    }
    got = {
        "画幅竖": aspect.get("竖", 0),
        "画幅横": aspect.get("横", 0),
        "画幅空": aspect.get("空", 0),
        "旋转-90": rot_bucket.get("-90", 0),
        "旋转90": rot_bucket.get("90", 0),
        "旋转-180": rot_bucket.get("-180", 0),
        "旋转0": rot_bucket.get("0", 0),
        "旋转空": rot_bucket.get("空", 0),
        "横且旋转0": landscape_rot0,
        "出处ffprobe": src_ff,
        "标注返工": marked,
        "旋转其他": rot_bucket.get("其他", 0),
    }
    diffs = []
    for k, ev in expected.items():
        if got.get(k) != ev:
            diffs.append(f"{k} 回报 {ev} / 实得 {got.get(k)}")
    got["与回报一致"] = not diffs
    got["差异说明"] = "；".join(diffs)
    return got


def decide(old: dict, new: dict, extras: list[str]) -> tuple[str, str]:
    if old["通过"] and new["通过"]:
        return (
            "通过",
            "第 3 项两组抽样均达到 50/50 全部一致。上次 47 条不一致已纠正，新抽 50 条也全部一致。"
            "第 1、2、4–8 项未重做，维持 20261117_01 的结论。",
        )
    failed = []
    if not old["通过"]:
        failed.append(f"原种子复核 {old['全部一致']}/{old['抽检条数']} 一致")
    if not new["通过"]:
        failed.append(f"新种子抽检 {new['全部一致']}/{new['抽检条数']} 一致")
    # 少量、不影响编号的小问题？这里第 3 项是上次返工焦点，不一致就应返工重查
    n_bad = old["不一致"] + new["不一致"]
    if n_bad <= 1 and (old.get("不一致原因统计") or new.get("不一致原因统计")):
        # 仍倾向返工重查：画幅/旋转是本批焦点。只有纯记录级笔误且与探测无关才用「小问题」。
        pass
    return (
        "要返工并重查",
        "第 3 项仍未通过：" + "；".join(failed) + "。需要 T01 再查不一致记录并返工，然后由 C01 再重查第 3 项。",
    )


def main():
    C01_OUT.mkdir(parents=True, exist_ok=True)
    (C01_OUT / "脚本").mkdir(parents=True, exist_ok=True)
    (C01_OUT / "核对").mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    started = now_iso()
    print(f"C01 第3项重查开始 {started}", flush=True)

    before = file_meta(TABLE_PATH)
    sha_ok = before["sha256"] == EXPECTED_TABLE_SHA256
    mtime_ok = before["修改时间"] == EXPECTED_TABLE_MTIME
    print(
        f"正式表 字节={before['字节数']} mtime={before['修改时间']} "
        f"sha={before['sha256']} sha相符={sha_ok} mtime相符={mtime_ok}",
        flush=True,
    )
    if not sha_ok:
        print("警告：正式表 sha256 与 T01 回报不一致，仍用当前正式表继续核。", flush=True)

    records = load_origin_table()
    print(f"原片表 {len(records)} 条", flush=True)
    by_id = {}
    dups = []
    for r in records:
        rid = r.get("原片ID")
        if rid in by_id:
            dups.append(rid)
        else:
            by_id[rid] = r

    dist = table_distribution(records)
    print(f"分布 { {k: dist[k] for k in ('画幅竖','画幅横','画幅空','横且旋转0','与回报一致')} }", flush=True)

    share_root = read_share_root()
    print(f"共享盘根路径：{share_root}", flush=True)

    prev = load_json(PREV_SAMPLE_PATH)
    prev_ids = list(prev.get("抽中的原片ID") or [])
    prev_bad_ids = {r["原片ID"] for r in (prev.get("不一致记录") or [])}
    prev_ok_ids = [rid for rid in prev_ids if rid not in prev_bad_ids]
    if len(prev_ids) != 50:
        print(f"警告：上次抽检原片ID不是 50 条，而是 {len(prev_ids)}", flush=True)

    # 按原种子对当前表顺序再抽一次，看是否仍是同一组
    rng_old = random.Random(OLD_SEED)
    reshuffle = list(records)
    rng_old.shuffle(reshuffle)
    reshuffle_ids = [r["原片ID"] for r in reshuffle[:50]]
    same_set = set(reshuffle_ids) == set(prev_ids)
    same_order = reshuffle_ids == prev_ids
    print(f"按原种子重抽与上次 ID 集合相同={same_set} 顺序相同={same_order}", flush=True)

    print("复核不换的 50 条…", flush=True)
    t1 = time.perf_counter()
    old_rows = check_sample(by_id, prev_ids, share_root, "旧组")
    old_sum = summarize(old_rows, OLD_SEED, "复核不换50条")
    old_sum["用时秒"] = round(time.perf_counter() - t1, 2)
    old_sum["按种子重抽与上次相同"] = same_set
    old_sum["按种子重抽顺序与上次相同"] = same_order
    old_sum["上次不一致此次一致"] = sum(
        1 for r in old_rows if r.get("原片ID") in prev_bad_ids and r.get("全部一致")
    )
    old_sum["上次不一致此次仍不一致"] = sum(
        1 for r in old_rows if r.get("原片ID") in prev_bad_ids and not r.get("全部一致")
    )
    old_sum["上次一致此次仍一致"] = sum(
        1 for r in old_rows if r.get("原片ID") in set(prev_ok_ids) and r.get("全部一致")
    )
    old_sum["上次一致此次不一致"] = sum(
        1 for r in old_rows if r.get("原片ID") in set(prev_ok_ids) and not r.get("全部一致")
    )
    write_json(C01_OUT / "核对" / "复核不换50条.json", {**old_sum, "明细": old_rows})

    print(f"新种子 {NEW_SEED} 另抽 50 条…", flush=True)
    t2 = time.perf_counter()
    rng_new = random.Random(NEW_SEED)
    pool = list(records)
    rng_new.shuffle(pool)
    new_ids = [r["原片ID"] for r in pool[:50]]
    overlap = set(new_ids) & set(prev_ids)
    new_rows = check_sample(by_id, new_ids, share_root, "新组")
    new_sum = summarize(new_rows, NEW_SEED, "新抽50条")
    new_sum["用时秒"] = round(time.perf_counter() - t2, 2)
    new_sum["与旧组重叠条数"] = len(overlap)
    new_sum["与旧组重叠原片ID"] = sorted(overlap)
    write_json(C01_OUT / "核对" / "新抽50条.json", {**new_sum, "明细": new_rows})

    after = file_meta(TABLE_PATH)
    unchanged = before == after

    extras = []
    if dups:
        extras.append(f"当前正式表出现重复原片ID {len(dups)} 个，样例 {dups[:10]}。此项可能牵动第 1 项，仅记录，未重做第 1 项。")
    if len(records) != EXPECTED_TABLE_COUNT:
        extras.append(f"当前正式表条数为 {len(records)}，不是期望的 {EXPECTED_TABLE_COUNT}。可能牵动第 1 项，仅记录。")
    if not sha_ok:
        extras.append(
            f"当前正式表 sha256 为 `{before['sha256']}`，与 T01 回报给出的 `{EXPECTED_TABLE_SHA256}` 不符。本次仍按当前正式表抽查。"
        )
    if not mtime_ok:
        extras.append(
            f"当前正式表修改时间为 {before['修改时间']}，与 T01 回报给出的 {EXPECTED_TABLE_MTIME} 不符。"
        )
    if not same_set:
        extras.append(
            "按原种子 87112617 对当前正式表 shuffle 后抽到的 50 个原片ID，与上次不完全相同，说明表内行顺序可能已变。"
            "本次复核仍按上次报告里的 50 个原片ID 核对，不改用新抽到的集合。"
        )
    if not dist.get("与回报一致"):
        extras.append("只读统计的画幅/旋转分布与 T01 回报不完全相同：" + (dist.get("差异说明") or ""))
    if not unchanged:
        extras.append("检查结束时正式原片表的大小、修改时间或哈希与开工时不同。C01 不应改这份文件，需要核查。")

    # 若新抽到了仍为横且旋转 0 的，记一下探测是否也确认是真横（这是预期，不算问题，除非探测不是横）
    true_h = [
        r for r in new_rows + old_rows
        if r.get("原片表画幅") == "横" and rot_equal(r.get("原片表旋转角度"), 0) and r.get("全部一致")
    ]
    if true_h:
        extras.append(
            f"两组抽样里有 {len(true_h)} 条原片表为横且旋转 0，C01 重探后也是横、旋转 0，与「真横」判断一致。"
            f"原片ID：{', '.join(r['原片ID'] for r in true_h)}。"
        )

    conclusion, note = decide(old_sum, new_sum, extras)
    ended = now_iso()
    elapsed = round(time.perf_counter() - t0, 2)
    payload = {
        "开始时间": started,
        "结束时间": ended,
        "用时秒": elapsed,
        "耗时说明": f"复核上次 50 条 {old_sum.get('用时秒')} 秒；新抽 50 条 {new_sum.get('用时秒')} 秒。",
        "结论": conclusion,
        "结论说明": note,
        "正式表核验": {
            "条数": len(records),
            "运行前": before,
            "运行后": after,
            "sha256相符": sha_ok,
            "mtime相符": mtime_ok,
            "保持原样": unchanged,
            "画幅与旋转分布": dist,
        },
        "旧种子组": old_sum,
        "新种子组": new_sum,
        "旧种子组明细": old_rows,
        "新种子组明细": new_rows,
        "另外发现的问题": extras,
    }
    slim = json.loads(json.dumps(payload, ensure_ascii=False))
    slim.pop("旧种子组明细", None)
    slim.pop("新种子组明细", None)
    write_json(C01_OUT / "核对" / "检查结果.json", slim)
    write_report(payload)
    print(json.dumps({
        "结论": conclusion,
        "旧组": f"{old_sum['全部一致']}/{old_sum['抽检条数']} {'通过' if old_sum['通过'] else '不通过'}",
        "新组": f"{new_sum['全部一致']}/{new_sum['抽检条数']} {'通过' if new_sum['通过'] else '不通过'}",
        "上报无此项": True,
        "用时秒": elapsed,
        "原文件保持原样": unchanged,
        "sha256相符": sha_ok,
    }, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
