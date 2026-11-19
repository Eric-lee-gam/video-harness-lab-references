# -*- coding: utf-8 -*-
"""重探 Display Matrix 旋转并重算画幅。只改出处为 ffprobe 的旋转角度和画幅。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from common import (
    SHANGHAI,
    config_path,
    format_mtime,
    fragment_dir,
    full_path_from_record,
    iter_jsonl,
    load_config,
    load_jsonl,
    normalize_rotation,
    now_iso,
    orientation,
    probe_file,
    project_dir,
    this_output_dir,
    write_json,
    write_jsonl,
)

OUT = this_output_dir()
STATS = OUT / "统计"
CHECK = OUT / "核对"
LOCK = STATS / "full_run.lock"
RESULT_JSONL = STATS / "探测结果.jsonl"
TRIAL_JSON = STATS / "试跑结果.json"
ESTIMATE_JSON = STATS / "全量用时推算.json"
MAX_HOURS = 3.0
WORKERS_DEFAULT = 4


def load_table(path: Path) -> list[dict]:
    return load_jsonl(path)


def backup_table_path() -> Path:
    return OUT / "输入副本" / "原片表_返工前.jsonl"


def official_table_path() -> Path:
    return fragment_dir() / "原片表.jsonl"


def classify(records: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    need, hold, jingxu = [], [], []
    for rec in records:
        srcd = rec.get("出处") or {}
        dim_src = srcd.get("宽高旋转")
        dur_src = srcd.get("时长")
        rv = rec.get("旋转角度")
        r0 = rv in (None, "", 0, 0.0)
        if dim_src == "镜序":
            if rec.get("旋转角度") in (None, ""):
                hold.append({
                    "原片ID": rec.get("原片ID"),
                    "逻辑路径": rec.get("逻辑路径"),
                    "原因": "宽高来自镜序但旋转缺失",
                    "宽高旋转出处": dim_src,
                    "时长出处": dur_src,
                    "旋转角度": rv,
                    "画幅": rec.get("画幅"),
                })
            else:
                jingxu.append(rec)
            continue
        if dim_src == "ffprobe":
            need.append(rec)
            continue
        if dur_src == "ffprobe":
            hold.append({
                "原片ID": rec.get("原片ID"),
                "逻辑路径": rec.get("逻辑路径"),
                "原因": "时长出处为ffprobe但宽高旋转出处不是ffprobe也不是镜序，不自动覆盖",
                "宽高旋转出处": dim_src,
                "时长出处": dur_src,
                "旋转角度": rv,
                "画幅": rec.get("画幅"),
            })
            continue
        if r0:
            hold.append({
                "原片ID": rec.get("原片ID"),
                "逻辑路径": rec.get("逻辑路径"),
                "原因": "出处不是ffprobe，旋转为0或空，不能确认镜序已给过旋转，不自动覆盖",
                "宽高旋转出处": dim_src,
                "时长出处": dur_src,
                "旋转角度": rv,
                "画幅": rec.get("画幅"),
                "宽": rec.get("宽"),
                "高": rec.get("高"),
                "读取失败原因": rec.get("时长或画幅读取失败原因"),
            })
    return need, hold, jingxu


def load_c01_ids() -> tuple[list[str], list[str], dict]:
    p = project_dir() / "工位产出" / "C01" / "20261117_01" / "核对" / "抽检50条.json"
    c01 = json.loads(p.read_text(encoding="utf-8"))
    bad47 = [r["原片ID"] for r in c01["不一致记录"]]
    ok3 = [r["原片ID"] for r in c01["明细"] if r.get("全部一致")]
    return bad47, ok3, c01


def existing_results() -> dict[str, dict]:
    if not RESULT_JSONL.exists():
        return {}
    out = {}
    for row in iter_jsonl(RESULT_JSONL):
        oid = row.get("原片ID")
        if oid:
            out[oid] = row
    return out


def append_results(rows: list[dict]) -> None:
    STATS.mkdir(parents=True, exist_ok=True)
    with RESULT_JSONL.open("a", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def result_from_probe(rec: dict, probe: dict) -> dict:
    old_rot = rec.get("旋转角度")
    old_asp = rec.get("画幅")
    w = rec.get("宽")
    h = rec.get("高")
    row = {
        "原片ID": rec.get("原片ID"),
        "逻辑路径": rec.get("逻辑路径"),
        "原旋转角度": old_rot,
        "原画幅": old_asp,
        "原宽": w,
        "原高": h,
        "ok": bool(probe.get("ok")),
        "用时秒": probe.get("用时秒"),
    }
    if not probe.get("ok"):
        row["error"] = probe.get("error")
        row["变更"] = False
        return row
    new_rot = normalize_rotation(probe.get("旋转角度"))
    # 用原片表已有宽高 + 新旋转算画幅；宽高本身不改
    use_w = w if w not in (None, "") else probe.get("宽")
    use_h = h if h not in (None, "") else probe.get("高")
    new_asp = orientation(use_w, use_h, new_rot)
    row.update({
        "探测宽": probe.get("宽"),
        "探测高": probe.get("高"),
        "探测旋转角度": new_rot,
        "新画幅": new_asp,
        "有DisplayMatrix": probe.get("有DisplayMatrix"),
        "宽高是否与原片表一致": (probe.get("宽") == w and probe.get("高") == h),
        "变更": (new_rot != normalize_rotation(old_rot)) or (new_asp != old_asp),
    })
    return row


def probe_one(rec: dict, share_root: str) -> dict:
    path = full_path_from_record(share_root, rec)
    if not path.exists():
        return result_from_probe(rec, {"ok": False, "error": "路径不存在", "用时秒": 0})
    return result_from_probe(rec, probe_file(path))


def run_batch(recs: list[dict], share_root: str, workers: int, already: dict[str, dict], label: str) -> list[dict]:
    todo = [r for r in recs if r.get("原片ID") not in already]
    reused = [already[r["原片ID"]] for r in recs if r.get("原片ID") in already]
    print(f"{label}: 计划 {len(recs)}，已有结果 {len(reused)}，待探 {len(todo)}，并发 {workers}", flush=True)
    if not todo:
        return reused
    done_new: list[dict] = []
    t0 = time.perf_counter()
    buf: list[dict] = []
    def flush_buf():
        nonlocal buf
        if buf:
            append_results(buf)
            buf = []

    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(probe_one, rec, share_root): rec.get("原片ID") for rec in todo}
        n = 0
        for fut in as_completed(futs):
            row = fut.result()
            done_new.append(row)
            buf.append(row)
            n += 1
            if len(buf) >= 50:
                flush_buf()
            if n % 50 == 0 or n == len(todo):
                elapsed = time.perf_counter() - t0
                rate = elapsed / n if n else 0
                eta = rate * (len(todo) - n)
                print(
                    f"  {label} {n}/{len(todo)} 已用 {elapsed:.1f}s，均 {rate:.3f}s/条，剩余约 {eta/60:.1f} 分",
                    flush=True,
                )
    flush_buf()
    return reused + done_new


def cmd_trial(args) -> int:
    STATS.mkdir(parents=True, exist_ok=True)
    CHECK.mkdir(parents=True, exist_ok=True)
    records = load_table(backup_table_path())
    need, hold, jingxu = classify(records)
    write_json(CHECK / "不自动覆盖清单.json", {
        "条数": len(hold),
        "分类": dict(Counter(x["原因"] for x in hold)),
        "明细": hold,
    })
    write_json(STATS / "分类摘要.json", {
        "原片表条数": len(records),
        "需重探_宽高旋转出处ffprobe": len(need),
        "镜序已有旋转_不覆盖": len(jingxu),
        "不自动覆盖": len(hold),
        "时间": now_iso(),
    })
    bad47, ok3, c01 = load_c01_ids()
    by_id = {r["原片ID"]: r for r in records}
    missing = [i for i in bad47 if i not in by_id]
    if missing:
        raise SystemExit(f"C01 47 条有 {len(missing)} 条不在原片表")
    trial_ids = list(dict.fromkeys(bad47 + [i for i in ok3 if (by_id[i].get("出处") or {}).get("宽高旋转") == "ffprobe"]))
    trial_recs = [by_id[i] for i in trial_ids]
    cfg = load_config()
    share_root = cfg["共享盘根路径"]
    t0 = time.perf_counter()
    rows = run_batch(trial_recs, share_root, args.workers, existing_results(), "试跑")
    elapsed = time.perf_counter() - t0
    # only count newly probed times if possible
    times = [r.get("用时秒") or 0 for r in rows]
    mean = (sum(times) / len(times)) if times else 0
    wall_mean = elapsed / len(rows) if rows else 0
    n_need = len(need)
    # wall estimate uses observed wall / n with same workers
    est_sec = wall_mean * n_need if wall_mean else mean * n_need
    est_hours = est_sec / 3600
    by_trial = {r["原片ID"]: r for r in rows}
    ok47 = 0
    detail47 = []
    for item in c01["不一致记录"]:
        oid = item["原片ID"]
        r = by_trial.get(oid) or {}
        expect_rot = normalize_rotation(item.get("探测旋转角度"))
        expect_asp = item.get("C01判定画幅")
        got_rot = r.get("探测旋转角度")
        got_asp = r.get("新画幅")
        good = bool(r.get("ok")) and got_rot == expect_rot and got_asp == expect_asp
        if good:
            ok47 += 1
        detail47.append({
            "原片ID": oid,
            "逻辑路径": item.get("逻辑路径"),
            "C01探测旋转角度": item.get("探测旋转角度"),
            "C01判定画幅": expect_asp,
            "本次探测旋转角度": got_rot,
            "本次画幅": got_asp,
            "有DisplayMatrix": r.get("有DisplayMatrix"),
            "ok": r.get("ok"),
            "error": r.get("error"),
            "已纠正": good,
        })
    control = []
    for oid in ok3:
        rec = by_id[oid]
        r = by_trial.get(oid)
        control.append({
            "原片ID": oid,
            "逻辑路径": rec.get("逻辑路径"),
            "原旋转角度": rec.get("旋转角度"),
            "原画幅": rec.get("画幅"),
            "出处宽高旋转": (rec.get("出处") or {}).get("宽高旋转"),
            "本次": {k: r.get(k) for k in ("ok", "探测旋转角度", "新画幅", "有DisplayMatrix", "变更", "error")} if r else "未探（镜序不覆盖）",
        })
    matrix_n = sum(1 for r in rows if r.get("有DisplayMatrix"))
    changed_n = sum(1 for r in rows if r.get("变更"))
    fail_n = sum(1 for r in rows if not r.get("ok"))
    payload = {
        "时间": now_iso(),
        "试跑条数": len(rows),
        "C01不一致47条": 47,
        "C01_47条已纠正": ok47,
        "对照3条": control,
        "读到DisplayMatrix": matrix_n,
        "试跑变更": changed_n,
        "试跑失败": fail_n,
        "墙钟秒": round(elapsed, 2),
        "单条探测秒合计均值": round(mean, 4),
        "墙钟每条秒": round(wall_mean, 4),
        "需重探全量": n_need,
        "推算全量秒": round(est_sec, 1),
        "推算全量小时": round(est_hours, 3),
        "超过3小时": est_hours > MAX_HOURS,
        "并发": args.workers,
        "47条明细": detail47,
    }
    write_json(TRIAL_JSON, payload)
    write_json(ESTIMATE_JSON, {
        "推算全量小时": round(est_hours, 3),
        "推算全量秒": round(est_sec, 1),
        "超过3小时": est_hours > MAX_HOURS,
        "试跑条数": len(rows),
        "墙钟秒": round(elapsed, 2),
        "并发": args.workers,
        "需重探全量": n_need,
        "时间": now_iso(),
    })
    print(
        f"试跑完成：{len(rows)} 条，47 条纠正 {ok47}，DisplayMatrix {matrix_n}，"
        f"墙钟 {elapsed:.1f}s，均 {wall_mean:.3f}s/条，推算全量 {est_hours:.2f} 小时，超3小时={est_hours > MAX_HOURS}",
        flush=True,
    )
    if ok47 < 47:
        print("试跑未把 C01 47 条全部纠正，停止，不进入全量。", flush=True)
        return 2
    if est_hours > MAX_HOURS:
        print("推算超过 3 小时，按任务要求停止，不进入全量。", flush=True)
        return 3
    return 0


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    except Exception:
        return False


def acquire_full_lock() -> None:
    STATS.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            info = json.loads(LOCK.read_text(encoding="utf-8"))
        except Exception:
            info = {}
        pid = int(info.get("pid") or 0)
        if pid and pid != os.getpid() and _pid_alive(pid):
            raise SystemExit(f"已有全量任务在跑 pid={pid}，不启动第二份。信息：{info}")
        print(f"发现过期锁 pid={pid}，继续本进程。", flush=True)
    write_json(LOCK, {"pid": os.getpid(), "开始": now_iso()})


def release_full_lock() -> None:
    try:
        if LOCK.exists():
            LOCK.unlink()
    except OSError:
        pass


def cmd_full(args) -> int:
    if not TRIAL_JSON.exists():
        raise SystemExit("请先跑 --trial")
    trial = json.loads(TRIAL_JSON.read_text(encoding="utf-8"))
    if trial.get("C01_47条已纠正") != 47:
        raise SystemExit("试跑未纠正全部 47 条，不跑全量")
    if trial.get("超过3小时"):
        raise SystemExit("试跑推算超过 3 小时，不跑全量")
    acquire_full_lock()
    try:
        records = load_table(backup_table_path())
        need, hold, jingxu = classify(records)
        cfg = load_config()
        share_root = cfg["共享盘根路径"]
        already = existing_results()
        t0 = time.perf_counter()
        rows = run_batch(need, share_root, args.workers, already, "全量")
        elapsed = time.perf_counter() - t0
        ok_n = sum(1 for r in rows if r.get("ok"))
        fail_n = sum(1 for r in rows if not r.get("ok"))
        chg = sum(1 for r in rows if r.get("变更"))
        matrix_n = sum(1 for r in rows if r.get("有DisplayMatrix"))
        summary = {
            "时间": now_iso(),
            "需重探": len(need),
            "本次得到结果": len(rows),
            "成功": ok_n,
            "失败": fail_n,
            "变更": chg,
            "有DisplayMatrix": matrix_n,
            "本轮墙钟秒": round(elapsed, 2),
            "并发": args.workers,
        }
        write_json(STATS / "全量探测摘要.json", summary)
        print(json.dumps(summary, ensure_ascii=False), flush=True)
        if fail_n:
            fails = [r for r in rows if not r.get("ok")]
            write_jsonl(CHECK / "探测失败.jsonl", fails)
        return 0
    finally:
        release_full_lock()


def apply_updates(records: list[dict], results: dict[str, dict]) -> tuple[list[dict], dict]:
    changed_rot = changed_asp = changed_both = unchanged = failed = skipped = 0
    new_rows = []
    for rec in records:
        oid = rec.get("原片ID")
        srcd = rec.get("出处") or {}
        if srcd.get("宽高旋转") != "ffprobe":
            new_rows.append(rec)
            skipped += 1
            continue
        r = results.get(oid)
        if not r or not r.get("ok"):
            new_rows.append(rec)
            failed += 1
            continue
        new_rec = dict(rec)
        new_rot = r.get("探测旋转角度")
        new_asp = r.get("新画幅")
        old_rot = rec.get("旋转角度")
        old_asp = rec.get("画幅")
        rot_chg = normalize_rotation(new_rot) != normalize_rotation(old_rot)
        asp_chg = new_asp != old_asp
        if rot_chg:
            new_rec["旋转角度"] = new_rot
        if asp_chg and new_asp in ("横", "竖"):
            new_rec["画幅"] = new_asp
        if rot_chg or asp_chg:
            src = dict(srcd)
            src["旋转画幅返工"] = "T01-20261117_02"
            new_rec["出处"] = src
            if rot_chg and asp_chg:
                changed_both += 1
            elif rot_chg:
                changed_rot += 1
            else:
                changed_asp += 1
        else:
            unchanged += 1
        new_rows.append(new_rec)
    stats = {
        "总条数": len(records),
        "跳过_非ffprobe出处": skipped,
        "探测失败未改": failed,
        "旋转和画幅都改": changed_both,
        "只改旋转": changed_rot,
        "只改画幅": changed_asp,
        "探测成功但未改": unchanged,
        "改了旋转或画幅合计": changed_both + changed_rot + changed_asp,
    }
    return new_rows, stats


def distribution(records: list[dict]) -> dict:
    aspect = Counter()
    rot = Counter()
    src_wh = Counter()
    h0 = 0
    for rec in records:
        aspect[str(rec.get("画幅"))] += 1
        rot[str(rec.get("旋转角度"))] += 1
        src_wh[str((rec.get("出处") or {}).get("宽高旋转"))] += 1
        if rec.get("画幅") == "横" and rec.get("旋转角度") in (None, "", 0, 0.0):
            h0 += 1
    return {
        "条数": len(records),
        "画幅": dict(aspect),
        "旋转角度": dict(rot),
        "出处_宽高旋转": dict(src_wh),
        "仍为横且旋转为0": h0,
    }


def protected_fields_ok(old: list[dict], new: list[dict]) -> dict:
    keys = ["原片ID", "逻辑路径", "标注库ID", "镜序素材ID", "字节数", "修改时间",
            "时长", "宽", "高", "来源类型", "项目名", "目录原名", "可用状态",
            "目录限制原文", "重复组", "声音", "库ID", "库内相对路径", "共享相对路径"]
    if len(old) != len(new):
        return {"ok": False, "原因": f"条数变化 {len(old)} -> {len(new)}"}
    diffs = []
    for a, b in zip(old, new):
        for k in keys:
            if a.get(k) != b.get(k):
                diffs.append({"原片ID": a.get("原片ID"), "字段": k})
                if len(diffs) >= 10:
                    return {"ok": False, "样例": diffs}
    return {"ok": True, "检查字段": keys, "不一致": len(diffs)}


def cmd_apply(args) -> int:
    records = load_table(backup_table_path())
    results = existing_results()
    need, hold, jingxu = classify(records)
    missing = [r["原片ID"] for r in need if r["原片ID"] not in results]
    if missing:
        raise SystemExit(f"还有 {len(missing)} 条需重探但没有探测结果，不能落表")
    new_rows, stats = apply_updates(records, results)
    prot = protected_fields_ok(records, new_rows)
    if not prot.get("ok"):
        write_json(STATS / "保护字段检查失败.json", prot)
        raise SystemExit(f"保护字段被改动，已停止落表：{prot}")
    # 自检 47
    bad47, ok3, c01 = load_c01_ids()
    by_new = {r["原片ID"]: r for r in new_rows}
    ok47 = 0
    detail47 = []
    for item in c01["不一致记录"]:
        rec = by_new[item["原片ID"]]
        expect_rot = normalize_rotation(item.get("探测旋转角度"))
        expect_asp = item.get("C01判定画幅")
        good = rec.get("旋转角度") == expect_rot and rec.get("画幅") == expect_asp
        if good:
            ok47 += 1
        detail47.append({
            "原片ID": item["原片ID"],
            "表旋转角度": rec.get("旋转角度"),
            "表画幅": rec.get("画幅"),
            "期望旋转": expect_rot,
            "期望画幅": expect_asp,
            "已纠正": good,
        })
    control = []
    for oid in ok3:
        rec = by_new[oid]
        old = next(r for r in records if r["原片ID"] == oid)
        control.append({
            "原片ID": oid,
            "出处宽高旋转": (rec.get("出处") or {}).get("宽高旋转"),
            "原旋转角度": old.get("旋转角度"),
            "现旋转角度": rec.get("旋转角度"),
            "原画幅": old.get("画幅"),
            "现画幅": rec.get("画幅"),
        })
    dist_before = distribution(records)
    dist_after = distribution(new_rows)
    fails = [results[r["原片ID"]] for r in need if not results.get(r["原片ID"], {}).get("ok")]
    selfcheck = {
        "时间": now_iso(),
        "落表统计": stats,
        "保护字段": prot,
        "C01_47条已纠正": ok47,
        "C01_47条明细": detail47,
        "对照3条": control,
        "返工前分布": dist_before,
        "返工后分布": dist_after,
        "探测失败条数": len(fails),
        "不自动覆盖条数": len(hold),
        "镜序不覆盖条数": len(jingxu),
    }
    write_json(STATS / "落表统计.json", stats)
    write_json(CHECK / "C01_47条自检.json", {"已纠正": ok47, "明细": detail47, "对照3条": control})
    write_json(CHECK / "分布与残留.json", {
        "返工前": dist_before,
        "返工后": dist_after,
        "探测失败条数": len(fails),
    })
    if fails:
        write_jsonl(CHECK / "探测失败.jsonl", fails)
    after_path = OUT / "输入副本" / "原片表_返工后.jsonl"
    write_jsonl(after_path, new_rows)
    official = official_table_path()
    # 先写到旁路文件再替换，避免 PermissionError
    tmp_official = official.with_name("原片表.jsonl.rewritten")
    write_jsonl(tmp_official, new_rows)
    from common import safe_replace
    safe_replace(tmp_official, official)
    selfcheck["正式表"] = {
        "路径": "片段库/原片表.jsonl",
        "条数": len(new_rows),
        "字节数": official.stat().st_size,
        "修改时间": format_mtime(official.stat().st_mtime),
    }
    selfcheck["返工后副本"] = {
        "路径": "工位产出/T01/20261117_02/输入副本/原片表_返工后.jsonl",
        "字节数": after_path.stat().st_size,
        "修改时间": format_mtime(after_path.stat().st_mtime),
    }
    write_json(STATS / "自检.json", selfcheck)
    print(
        f"已落表：改了 {stats['改了旋转或画幅合计']} 条；"
        f"C01 47 条纠正 {ok47}；"
        f"画幅 {dist_after['画幅']}；"
        f"仍为横且旋转为0 {dist_after['仍为横且旋转为0']}；"
        f"探测失败 {len(fails)}",
        flush=True,
    )
    if ok47 < 47:
        return 2
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trial", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=WORKERS_DEFAULT)
    args = ap.parse_args()
    if not (args.trial or args.full or args.apply):
        ap.error("需要 --trial / --full / --apply 之一")
    if args.trial:
        rc = cmd_trial(args)
        if rc != 0:
            sys.exit(rc)
    if args.full:
        rc = cmd_full(args)
        if rc != 0:
            sys.exit(rc)
    if args.apply:
        rc = cmd_apply(args)
        if rc != 0:
            sys.exit(rc)


if __name__ == "__main__":
    main()
