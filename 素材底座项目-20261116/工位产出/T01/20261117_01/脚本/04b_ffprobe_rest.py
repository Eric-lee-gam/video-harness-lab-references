# -*- coding: utf-8 -*-
"""继续探测尚未完成的原片（跳过试跑已完成的）。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import config_path, fragment_dir, iter_jsonl, load_config, now_iso, this_output_dir, write_json, write_jsonl

# reuse probe helpers
import importlib.util
spec = importlib.util.spec_from_file_location("t01_ffprobe", Path(__file__).with_name("04_ffprobe_trial.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    parser.add_argument("--out-dir", default=str(this_output_dir()))
    parser.add_argument("--checkpoint-every", type=int, default=500)
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    out_dir = Path(args.out_dir)
    table_path = fragment_dir() / "原片表.jsonl"
    results_path = out_dir / "统计" / "ffprobe结果.jsonl"
    records = list(iter_jsonl(table_path))
    done = {}
    if results_path.exists():
        for row in iter_jsonl(results_path):
            done[row["原片ID"]] = row

    need = [r for r in records if r.get("时长") is None or r.get("宽") is None or r.get("高") is None]
    # also skip if we already have a failed probe result recorded
    rest = [r for r in need if r["原片ID"] not in done]
    print(f"原片 {len(records)} 已探测结果 {len(done)} 仍缺字段 {len(need)} 本次要跑 {len(rest)}", flush=True)
    t0 = time.perf_counter()
    new_results = []
    by_id = {r["原片ID"]: r for r in records}
    ok = fail = 0
    for i, rec in enumerate(rest, 1):
        path = mod.full_path(cfg, rec)
        result = mod.probe_file(path)
        result["原片ID"] = rec["原片ID"]
        result["逻辑路径"] = rec["逻辑路径"]
        result["试跑"] = False
        new_results.append(result)
        by_id[rec["原片ID"]] = mod.apply_probe(by_id[rec["原片ID"]], result)
        if result.get("ok"):
            ok += 1
        else:
            fail += 1
            print(f"  FAIL {rec['逻辑路径']} {result.get('error','')[:200]}", flush=True)
        if i % 50 == 0:
            elapsed = time.perf_counter() - t0
            rate = elapsed / i
            eta = rate * (len(rest) - i)
            print(f"  {i}/{len(rest)} ok={ok} fail={fail} 用时{elapsed:.0f}s 预计剩余{eta/60:.1f}分钟", flush=True)
        if i % args.checkpoint_every == 0:
            write_jsonl(table_path, [by_id[r["原片ID"]] for r in records])
            existing = list(done.values())
            write_jsonl(results_path, existing + new_results)
            write_jsonl(out_dir / "统计" / "原片表副本.jsonl", [by_id[r["原片ID"]] for r in records])
            print(f"  checkpoint {i}", flush=True)

    write_jsonl(results_path, list(done.values()) + new_results)
    write_jsonl(table_path, [by_id[r["原片ID"]] for r in records])
    write_jsonl(out_dir / "统计" / "原片表副本.jsonl", [by_id[r["原片ID"]] for r in records])
    summary = {
        "时间": now_iso(),
        "本次条数": len(rest),
        "成功": ok,
        "失败": fail,
        "用时秒": round(time.perf_counter() - t0, 2),
    }
    write_json(out_dir / "统计" / "ffprobe全量续跑.json", summary)
    still = sum(1 for r in by_id.values() if r.get("时长") is None or r.get("宽") is None or r.get("高") is None)
    has_reason = sum(1 for r in by_id.values() if r.get("时长或画幅读取失败原因"))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"仍缺字段 {still}，其中已写失败原因 {has_reason}")


if __name__ == "__main__":
    main()
