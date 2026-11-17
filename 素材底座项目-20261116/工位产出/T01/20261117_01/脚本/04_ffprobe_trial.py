# -*- coding: utf-8 -*-
"""对缺少时长或宽高的原片用 ffprobe 读文件头。先试跑 200 个并计时；推算超过 3 小时就停下。"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    config_path,
    fragment_dir,
    iter_jsonl,
    load_config,
    now_iso,
    this_output_dir,
    write_json,
    write_jsonl,
    join_unc,
)
from importlib.machinery import SourceFileLoader

# reuse orientation from 03
_build = SourceFileLoader("t01_build", str(Path(__file__).with_name("03_build_table.py"))).load_module()
orientation = _build.orientation


def probe_file(path: Path, timeout: int = 30) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-probesize", "5000000",
        "-analyzeduration", "5000000",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,duration,rotation:stream_tags=rotate:format=duration",
        "-of", "json",
        str(path),
    ]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        elapsed = time.perf_counter() - t0
        if proc.returncode != 0:
            return {"ok": False, "error": (proc.stderr or proc.stdout or "ffprobe失败").strip()[:500], "用时秒": elapsed}
        data = json.loads(proc.stdout or "{}")
        fmt = data.get("format") or {}
        streams = data.get("streams") or []
        v = streams[0] if streams else {}
        dur = v.get("duration") or fmt.get("duration")
        width, height = v.get("width"), v.get("height")
        rot = v.get("rotation")
        tags = v.get("tags") or {}
        if rot in (None, "") and tags.get("rotate") not in (None, ""):
            rot = tags.get("rotate")
        for sd in v.get("side_data_list") or []:
            if sd.get("rotation") not in (None, ""):
                rot = sd.get("rotation")
        return {
            "ok": True,
            "时长": float(dur) if dur not in (None, "") else None,
            "宽": int(width) if width not in (None, "") else None,
            "高": int(height) if height not in (None, "") else None,
            "旋转角度": float(rot) if rot not in (None, "") else 0,
            "用时秒": elapsed,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"超时{timeout}秒", "用时秒": time.perf_counter() - t0}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "用时秒": time.perf_counter() - t0}


def full_path(cfg: dict, rec: dict) -> Path:
    libs = {x["库ID"]: x for x in cfg["库"]}
    lib = libs[rec["库ID"]]
    return Path(join_unc(lib["根路径"], rec["库内相对路径"].replace("/", "\\")))


def apply_probe(rec: dict, result: dict) -> dict:
    rec = dict(rec)
    src = dict(rec.get("出处") or {})
    if result.get("ok"):
        if rec.get("时长") is None and result.get("时长") is not None:
            rec["时长"] = result["时长"]
            src["时长"] = "ffprobe"
        if rec.get("宽") is None and result.get("宽") is not None:
            rec["宽"] = result["宽"]
            rec["高"] = result["高"]
            rec["旋转角度"] = result.get("旋转角度") or 0
            src["宽高旋转"] = "ffprobe"
        rec["画幅"] = orientation(rec.get("宽"), rec.get("高"), rec.get("旋转角度"))
        rec.pop("时长或画幅读取失败原因", None)
    else:
        rec["时长或画幅读取失败原因"] = result.get("error") or "ffprobe失败"
    rec["出处"] = src
    return rec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    parser.add_argument("--out-dir", default=str(this_output_dir()))
    parser.add_argument("--trial", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261117)
    parser.add_argument("--limit-hours", type=float, default=3.0)
    parser.add_argument("--run-rest", action="store_true")
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    out_dir = Path(args.out_dir)
    table_path = fragment_dir() / "原片表.jsonl"
    need_path = out_dir / "核对" / "待ffprobe.jsonl"
    trial_path = out_dir / "统计" / "ffprobe试跑.json"
    results_path = out_dir / "统计" / "ffprobe结果.jsonl"

    records = list(iter_jsonl(table_path))
    need = [
        r for r in records
        if r.get("时长") is None or r.get("宽") is None or r.get("高") is None
    ]
    print(f"待探测 {len(need)} / 总 {len(records)}", flush=True)
    if not need:
        write_json(trial_path, {"时间": now_iso(), "待探测": 0, "说明": "无需ffprobe"})
        print("无需 ffprobe")
        return

    rng = random.Random(args.seed)
    trial_n = min(args.trial, len(need))
    trial_set = list(need)
    rng.shuffle(trial_set)
    trial = trial_set[:trial_n]

    print(f"试跑 {len(trial)} 个, seed={args.seed}", flush=True)
    t0 = time.perf_counter()
    trial_results = []
    by_id = {r["原片ID"]: r for r in records}

    for i, rec in enumerate(trial, 1):
        path = full_path(cfg, rec)
        result = probe_file(path)
        result["原片ID"] = rec["原片ID"]
        result["逻辑路径"] = rec["逻辑路径"]
        result["试跑"] = True
        trial_results.append(result)
        by_id[rec["原片ID"]] = apply_probe(rec, result)
        if i % 20 == 0 or not result.get("ok"):
            print(f"  {i}/{len(trial)} ok={result.get('ok')} {result.get('用时秒'):.2f}s {rec['逻辑路径'][-60:]} {result.get('error','')[:80]}", flush=True)

    elapsed = time.perf_counter() - t0
    ok_n = sum(1 for x in trial_results if x.get("ok"))
    avg = elapsed / len(trial) if trial else 0
    remaining = len(need) - len(trial)
    estimate_rest = avg * remaining
    estimate_all = avg * len(need)
    limit = args.limit_hours * 3600
    stop = estimate_all > limit

    report = {
        "时间": now_iso(),
        "试跑条数": len(trial),
        "成功": ok_n,
        "失败": len(trial) - ok_n,
        "试跑用时秒": round(elapsed, 2),
        "平均每条秒": round(avg, 4),
        "待探测总数": len(need),
        "剩余条数": remaining,
        "推算剩余秒": round(estimate_rest, 1),
        "推算全部秒": round(estimate_all, 1),
        "推算全部小时": round(estimate_all / 3600, 2),
        "上限小时": args.limit_hours,
        "是否超过上限": stop,
        "随机种子": args.seed,
        "失败样例": [x for x in trial_results if not x.get("ok")][:20],
    }
    write_json(trial_path, report)
    # append results
    existing = []
    if results_path.exists():
        existing = list(iter_jsonl(results_path))
    write_jsonl(results_path, existing + trial_results)

    # 写回原片表（试跑已完成的先写入）
    new_rows = [by_id[r["原片ID"]] for r in records]
    write_jsonl(table_path, new_rows)
    write_jsonl(out_dir / "统计" / "原片表副本.jsonl", new_rows)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if stop:
        print("推算超过 3 小时，已停下，未继续全量跑。")
        return
    if not args.run_rest:
        print("推算未超过上限。本脚本未加 --run-rest，不自动全量跑；由调用方决定。")
        return

    # 全量剩余
    done_ids = {x["原片ID"] for x in existing + trial_results}
    rest = [r for r in need if r["原片ID"] not in done_ids]
    print(f"继续全量剩余 {len(rest)}", flush=True)
    rest_results = []
    t1 = time.perf_counter()
    for i, rec in enumerate(rest, 1):
        path = full_path(cfg, rec)
        result = probe_file(path)
        result["原片ID"] = rec["原片ID"]
        result["逻辑路径"] = rec["逻辑路径"]
        result["试跑"] = False
        rest_results.append(result)
        by_id[rec["原片ID"]] = apply_probe(by_id[rec["原片ID"]], result)
        if i % 100 == 0:
            print(f"  rest {i}/{len(rest)} {time.perf_counter()-t1:.1f}s", flush=True)
        if i % 500 == 0:
            write_jsonl(table_path, [by_id[r["原片ID"]] for r in records])
            write_jsonl(results_path, existing + trial_results + rest_results)
    write_jsonl(results_path, existing + trial_results + rest_results)
    write_jsonl(table_path, [by_id[r["原片ID"]] for r in records])
    write_jsonl(out_dir / "统计" / "原片表副本.jsonl", [by_id[r["原片ID"]] for r in records])
    print(f"全量剩余完成 {len(rest)} 用时 {time.perf_counter()-t1:.1f}s")


if __name__ == "__main__":
    main()
