# -*- coding: utf-8 -*-
"""随机抽 50 条，对照原文件夹核对路径、来源、限制。"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    classify_source_type,
    config_path,
    fragment_dir,
    iter_jsonl,
    load_config,
    match_limit,
    now_iso,
    this_output_dir,
    write_json,
    join_unc,
)


def full_path(cfg: dict, rec: dict) -> Path:
    libs = {x["库ID"]: x for x in cfg["库"]}
    lib = libs[rec["库ID"]]
    return Path(join_unc(lib["根路径"], rec["库内相对路径"].replace("/", "\\")))


def expected_source(cfg: dict, rec: dict) -> str:
    libs = {x["库ID"]: x for x in cfg["库"]}
    lib = libs[rec["库ID"]]
    return classify_source_type(lib["来源类型"], rec["共享相对路径"])


def expected_limit(rec: dict):
    item = match_limit(rec["共享相对路径"])
    if item:
        return item["可用状态"], item["目录限制原文"]
    return "可用", ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    parser.add_argument("--out-dir", default=str(this_output_dir()))
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=20261117)
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    out_dir = Path(args.out_dir)
    records = list(iter_jsonl(fragment_dir() / "原片表.jsonl"))
    rng = random.Random(args.seed)
    sample = records[:]
    rng.shuffle(sample)
    sample = sample[: args.n]

    rows = []
    ok = 0
    for rec in sample:
        path = full_path(cfg, rec)
        exists = path.is_file()
        size_ok = False
        size_actual = None
        if exists:
            size_actual = path.stat().st_size
            size_ok = size_actual == rec["字节数"]
        exp_src = expected_source(cfg, rec)
        exp_avail, exp_limit = expected_limit(rec)
        src_ok = rec.get("来源类型") == exp_src
        avail_ok = rec.get("可用状态") == exp_avail
        limit_ok = (rec.get("目录限制原文") or "") == exp_limit
        all_ok = exists and size_ok and src_ok and avail_ok and limit_ok
        if all_ok:
            ok += 1
        rows.append({
            "原片ID": rec["原片ID"],
            "逻辑路径": rec["逻辑路径"],
            "库ID": rec["库ID"],
            "共享相对路径": rec["共享相对路径"],
            "路径存在": exists,
            "字节数一致": size_ok,
            "来源类型": rec.get("来源类型"),
            "来源类型应是": exp_src,
            "来源正确": src_ok,
            "可用状态": rec.get("可用状态"),
            "可用状态应是": exp_avail,
            "限制原文": rec.get("目录限制原文") or "",
            "限制原文应是": exp_limit,
            "限制正确": avail_ok and limit_ok,
            "全部正确": all_ok,
        })

    report = {
        "时间": now_iso(),
        "抽检条数": len(rows),
        "随机种子": args.seed,
        "全部正确": ok,
        "不正确": len(rows) - ok,
        "抽中的原片ID": [r["原片ID"] for r in rows],
        "抽中的逻辑路径": [r["逻辑路径"] for r in rows],
        "明细": rows,
    }
    write_json(out_dir / "核对" / "随机抽检50条.json", report)
    print(f"抽检 {len(rows)}，全部正确 {ok}，不正确 {len(rows)-ok}")
    if len(rows) - ok:
        for r in rows:
            if not r["全部正确"]:
                print("FAIL", r["逻辑路径"], r)


if __name__ == "__main__":
    main()
