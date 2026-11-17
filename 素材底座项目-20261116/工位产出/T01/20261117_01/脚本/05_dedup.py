# -*- coding: utf-8 -*-
"""字节数和时长相同的先归为疑似重复，再用前 1MB 哈希确认。每组指定一条进入选材。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
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


def full_path(cfg: dict, rec: dict) -> Path:
    libs = {x["库ID"]: x for x in cfg["库"]}
    lib = libs[rec["库ID"]]
    return Path(join_unc(lib["根路径"], rec["库内相对路径"].replace("/", "\\")))


def head_hash(path: Path, n: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = n
        while remaining > 0:
            chunk = f.read(min(65536, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return h.hexdigest()


def duration_key(val) -> str | None:
    if val is None:
        return None
    try:
        return f"{round(float(val), 3):.3f}"
    except (TypeError, ValueError):
        return None


def pick_canonical(members: list[dict]) -> dict:
    def score(r):
        path = r.get("共享相对路径") or ""
        unused = "/用不太上的/" in f"/{path}/" or path.endswith("/用不太上的")
        return (
            1 if unused else 0,
            0 if r.get("镜序素材ID") else 1,
            0 if r.get("标注库ID") else 1,
            path,
        )
    return sorted(members, key=score)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    parser.add_argument("--out-dir", default=str(this_output_dir()))
    args = parser.parse_args()
    cfg = load_config(Path(args.config))
    out_dir = Path(args.out_dir)
    table_path = fragment_dir() / "原片表.jsonl"
    records = list(iter_jsonl(table_path))

    groups_size_dur = defaultdict(list)
    no_dur = []
    for r in records:
        dk = duration_key(r.get("时长"))
        if dk is None:
            no_dur.append(r)
            continue
        groups_size_dur[(r["字节数"], dk)].append(r)

    suspects = {k: v for k, v in groups_size_dur.items() if len(v) > 1}
    print(f"疑似重复组 {len(suspects)}，涉及 {sum(len(v) for v in suspects.values())} 条；无时长未参与 {len(no_dur)}", flush=True)

    confirmed = []
    rejected = []
    errors = []
    hash_cache = {}
    group_i = 0
    for (size, dur), members in sorted(suspects.items(), key=lambda x: (-len(x[1]), x[0][0])):
        hashes = {}
        for r in members:
            p = full_path(cfg, r)
            try:
                if r["原片ID"] not in hash_cache:
                    hash_cache[r["原片ID"]] = head_hash(p)
                hashes[r["原片ID"]] = hash_cache[r["原片ID"]]
            except OSError as e:
                errors.append({"原片ID": r["原片ID"], "逻辑路径": r["逻辑路径"], "error": str(e)})
        by_hash = defaultdict(list)
        for r in members:
            h = hashes.get(r["原片ID"])
            if h:
                by_hash[h].append(r)
        if len(members) >= 2 and not any(len(v) > 1 for v in by_hash.values()):
            rejected.append({
                "字节数": size,
                "时长": dur,
                "条数": len(members),
                "说明": "字节数和时长相同，但前1MB哈希不同，不作为重复组",
                "原片ID": [r["原片ID"] for r in members],
            })
        for h, ms in by_hash.items():
            if len(ms) < 2:
                continue
            group_i += 1
            gid = f"D{group_i:04d}"
            canon = pick_canonical(ms)
            item = {
                "重复组": gid,
                "字节数": size,
                "时长": dur,
                "前1MB哈希": h,
                "条数": len(ms),
                "进入选材": canon["原片ID"],
                "成员": [
                    {
                        "原片ID": r["原片ID"],
                        "逻辑路径": r["逻辑路径"],
                        "角色": "进入选材" if r["原片ID"] == canon["原片ID"] else "组内副本",
                    }
                    for r in sorted(ms, key=lambda x: x["逻辑路径"])
                ],
            }
            confirmed.append(item)
            for r in records:
                if r["原片ID"] in {m["原片ID"] for m in ms}:
                    r["重复组"] = {
                        "组号": gid,
                        "角色": "进入选材" if r["原片ID"] == canon["原片ID"] else "组内副本",
                    }

    write_jsonl(table_path, records)
    write_jsonl(out_dir / "统计" / "原片表副本.jsonl", records)
    summary = {
        "时间": now_iso(),
        "原片条数": len(records),
        "疑似组数_按字节数和时长": len(suspects),
        "疑似条数": sum(len(v) for v in suspects.values()),
        "确认重复组数": len(confirmed),
        "确认重复条数": sum(x["条数"] for x in confirmed),
        "进入选材条数": len(confirmed),
        "组内副本条数": sum(x["条数"] - 1 for x in confirmed),
        "哈希不同排除组数": len(rejected),
        "哈希读取失败": len(errors),
        "无时长未参与": len(no_dur),
        "选材规则": "优先不在“用不太上的”目录，其次有镜序编号，其次有标注库ID，再按路径排序。",
    }
    write_json(out_dir / "统计" / "重复组摘要.json", summary)
    write_json(out_dir / "核对" / "重复组.json", confirmed)
    write_json(out_dir / "核对" / "疑似重复但哈希不同.json", rejected)
    write_json(out_dir / "核对" / "重复组哈希失败.json", errors)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
