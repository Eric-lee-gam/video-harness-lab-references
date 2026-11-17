# -*- coding: utf-8 -*-
"""根据扫描清单建原片表，并对照镜序编号、标注库 ID、来源与限制。不读共享盘地址以外的配置字段。"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    VOCAB_LIMIT_DIRS,
    classify_source_type,
    config_path,
    dir_original_name,
    fragment_dir,
    iter_jsonl,
    load_config,
    match_limit,
    now_iso,
    project_name,
    this_output_dir,
    to_posix,
    write_json,
    write_jsonl,
    logical_path,
)

SHANGHAI = timezone(timedelta(hours=8))
EXPECTED_COUNTS = {"xiaoq": 20515, "ceshi": 330, "aming": 238, "jiaoban": 69}


def jingxu_id(alias: str, rel_posix: str) -> str:
    return hashlib.sha256(f"{alias}/{to_posix(rel_posix)}".encode("utf-8")).hexdigest()[:32]


def new_origin_id(lib_id: str, rel_posix: str) -> str:
    return "N" + hashlib.sha256(f"{lib_id}/{to_posix(rel_posix)}".encode("utf-8")).hexdigest()[:16]


def share_rel_from_ann_path(source_path: str, share_root: str) -> str | None:
    if not source_path:
        return None
    src = to_posix(source_path)
    root = to_posix(share_root)
    src_cf = src.casefold()
    root_cf = root.casefold()
    if src_cf.startswith(root_cf + "/"):
        return src[len(root) + 1 :]
    if src_cf == root_cf:
        return ""
    marker = Path(share_root).name.replace("\\", "/")
    token = marker + "/"
    i = src.find(token)
    if i >= 0:
        return src[i + len(token) :]
    i = src.casefold().find(token.casefold())
    if i >= 0:
        return src[i + len(token) :]
    return None


def parse_stamp(stamp) -> float | None:
    if stamp is None or stamp == "":
        return None
    try:
        n = int(stamp)
    except (TypeError, ValueError):
        return None
    if n > 10**16:
        return n / 1e9
    if n > 10**13:
        return n / 1e6
    if n > 10**10:
        return n / 1e3
    return float(n)


def orientation(width, height, rotation) -> str | None:
    if width is None or height is None:
        return None
    try:
        w, h = int(width), int(height)
    except (TypeError, ValueError):
        return None
    rot = 0
    if rotation not in (None, ""):
        try:
            rot = abs(int(round(float(rotation)))) % 360
        except (TypeError, ValueError):
            rot = 0
    if rot in (90, 270):
        w, h = h, w
    return "竖" if h > w else "横"


def load_scan_videos(scan_path: Path):
    rows = [r for r in iter_jsonl(scan_path) if r.get("是视频")]
    rows.sort(key=lambda r: (r["库ID"], r["共享相对路径"]))
    return rows


def load_catalog(db_path: Path):
    uri = f"file:{db_path.as_posix()}?mode=ro&immutable=1"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    assets = []
    for r in con.execute("SELECT id, root, rel, size, stamp, meta, error, available FROM assets"):
        assets.append(dict(r))
    con.close()
    return assets


def load_annotation(path: Path, share_root: str, 标注库名: str):
    recs = []
    for o in iter_jsonl(path):
        rel = share_rel_from_ann_path(o.get("source_path") or "", share_root)
        recs.append({
            "标注库名": 标注库名,
            "标注库ID": o.get("id"),
            "source_path": o.get("source_path"),
            "共享相对路径": rel,
            "project": o.get("project"),
            "kind": o.get("kind"),
            "duration_seconds": o.get("duration_seconds"),
            "audio_status": o.get("audio_status"),
            "directory_limits": o.get("directory_limits"),
        })
    return recs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    parser.add_argument("--out-dir", default=str(this_output_dir()))
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    out_dir = Path(args.out_dir)
    check_dir = out_dir / "核对"
    stat_dir = out_dir / "统计"
    inp = out_dir / "输入副本"
    check_dir.mkdir(parents=True, exist_ok=True)
    stat_dir.mkdir(parents=True, exist_ok=True)

    share_root = cfg["共享盘根路径"]
    prefix = cfg.get("逻辑路径前缀", "@shared")
    libs = {lib["库ID"]: lib for lib in cfg["库"]}

    scan_videos = load_scan_videos(inp / "扫描清单.jsonl")
    print(f"扫描视频 {len(scan_videos)}", flush=True)

    assets = load_catalog(inp / "catalog.sqlite3")
    xiaoq_assets = [a for a in assets if a["root"] == "xiaoq"]
    print(f"镜序 assets 全表 {len(assets)}, 小区 {len(xiaoq_assets)}", flush=True)

    ann_xiaoq = load_annotation(inp / "标注库_小区全库_AI剪辑检索索引.jsonl", share_root, "小区全库")
    ann_other = load_annotation(inp / "标注库_测试阿明搅拌_AI剪辑检索索引.jsonl", share_root, "测试阿明搅拌")
    annotations = ann_xiaoq + ann_other
    print(f"标注库 小区全库 {len(ann_xiaoq)}, 测试阿明搅拌 {len(ann_other)}", flush=True)

    # ---- 与约定条数、镜序登记表比扫描结果 ----
    count_cmp = {}
    for lib_id, lib in libs.items():
        n = sum(1 for r in scan_videos if r["库ID"] == lib_id)
        count_cmp[lib_id] = {
            "目录名": lib["目录名"],
            "扫描视频数": n,
            "补充约定条数": EXPECTED_COUNTS.get(lib_id),
            "差": n - EXPECTED_COUNTS.get(lib_id, 0),
        }

    # ---- 镜序对照（只对小区库） ----
    catalog_by_rel = {}
    catalog_by_rel_cf = defaultdict(list)
    for a in xiaoq_assets:
        rel = to_posix(a["rel"])
        catalog_by_rel[rel] = a
        catalog_by_rel_cf[rel.casefold()].append(a)

    scan_xiaoq = [r for r in scan_videos if r["库ID"] == "xiaoq"]
    disk_by_rel = {r["库内相对路径"]: r for r in scan_xiaoq}
    disk_by_rel_cf = defaultdict(list)
    for r in scan_xiaoq:
        disk_by_rel_cf[r["库内相对路径"].casefold()].append(r)

    jingxu_exact = 0
    jingxu_case = 0
    path_case_diffs = []
    id_mismatch = []  # 同路径但编号不同
    catalog_unmatched = []
    matched_catalog_ids = set()
    scan_match = {}  # 库内相对路径 -> asset

    for r in scan_xiaoq:
        rel = r["库内相对路径"]
        a = catalog_by_rel.get(rel)
        how = "精确路径"
        if a is None:
            cands = catalog_by_rel_cf.get(rel.casefold(), [])
            if len(cands) == 1:
                a = cands[0]
                how = "大小写不同"
                path_case_diffs.append({
                    "扫描路径": rel,
                    "登记表路径": to_posix(a["rel"]),
                    "镜序素材ID": a["id"],
                })
        if a is None:
            continue
        computed = jingxu_id("xiaoq", rel)
        computed_reg = jingxu_id("xiaoq", to_posix(a["rel"]))
        rec = {
            "扫描路径": rel,
            "登记表路径": to_posix(a["rel"]),
            "匹配方式": how,
            "登记表ID": a["id"],
            "按扫描路径计算": computed,
            "按登记表路径计算": computed_reg,
        }
        if a["id"] != computed_reg:
            rec["问题"] = "登记表ID与算法不符"
            id_mismatch.append(rec)
        elif how == "大小写不同" and computed != a["id"]:
            rec["问题"] = "路径大小写不同导致按扫描路径计算的编号与登记表不同"
            id_mismatch.append(rec)
        jingxu_exact += (how == "精确路径")
        jingxu_case += (how == "大小写不同")
        matched_catalog_ids.add(a["id"])
        scan_match[rel] = {"asset": a, "how": how}

    for a in xiaoq_assets:
        if a["id"] not in matched_catalog_ids:
            catalog_unmatched.append({
                "镜序素材ID": a["id"],
                "登记表路径": to_posix(a["rel"]),
                "字节数": a["size"],
                "stamp": a["stamp"],
                "error": a["error"],
            })

    disk_unmatched = [r for r in scan_xiaoq if r["库内相对路径"] not in scan_match]

    # 第二轮：剩余两边按字节数+修改时间对（1秒容差）
    size_time_matches = []
    leftover_catalog = []
    used_disk = set()
    disk_by_size = defaultdict(list)
    for r in disk_unmatched:
        disk_by_size[r["字节数"]].append(r)
    for a in [x for x in xiaoq_assets if x["id"] not in matched_catalog_ids]:
        ts = parse_stamp(a["stamp"])
        cands = []
        for r in disk_by_size.get(a["size"] or -1, []):
            if r["库内相对路径"] in used_disk:
                continue
            if ts is None:
                continue
            if abs(r["修改时间戳"] - ts) <= 1.0:
                cands.append(r)
        if len(cands) == 1:
            r = cands[0]
            used_disk.add(r["库内相对路径"])
            scan_match[r["库内相对路径"]] = {"asset": a, "how": "字节数+修改时间"}
            matched_catalog_ids.add(a["id"])
            size_time_matches.append({
                "扫描路径": r["库内相对路径"],
                "登记表路径": to_posix(a["rel"]),
                "镜序素材ID": a["id"],
                "字节数": r["字节数"],
                "扫描修改时间": r["修改时间"],
            })
        else:
            leftover_catalog.append({
                "镜序素材ID": a["id"],
                "登记表路径": to_posix(a["rel"]),
                "字节数": a["size"],
                "stamp": a["stamp"],
                "error": a["error"],
                "候选数": len(cands),
            })

    leftover_disk = [r for r in disk_unmatched if r["库内相对路径"] not in used_disk and r["库内相对路径"] not in scan_match]

    # 航天花园专项
    hangtian = {
        "扫描": [r["库内相对路径"] for r in scan_xiaoq if "航天花园" in r["库内相对路径"]],
        "登记表": [to_posix(a["rel"]) for a in xiaoq_assets if "航天花园" in (a["rel"] or "")],
    }
    hangtian_scan_set = set(hangtian["扫描"])
    hangtian_cat_set = set(hangtian["登记表"])
    hangtian_report = {
        "扫描条数": len(hangtian["扫描"]),
        "登记表条数": len(hangtian["登记表"]),
        "仅扫描有": sorted(hangtian_scan_set - hangtian_cat_set),
        "仅登记表有": sorted(hangtian_cat_set - hangtian_scan_set),
        "路径相同": len(hangtian_scan_set & hangtian_cat_set),
    }
    # 大小写集合
    hs_cf = {p.casefold(): p for p in hangtian_scan_set}
    hc_cf = {p.casefold(): p for p in hangtian_cat_set}
    hangtian_report["仅扫描有_忽略大小写"] = sorted(k for k in hs_cf if k not in hc_cf)
    hangtian_report["仅登记表有_忽略大小写"] = sorted(k for k in hc_cf if k not in hs_cf)
    hangtian_report["大小写不同"] = [
        {"扫描路径": hs_cf[k], "登记表路径": hc_cf[k]}
        for k in hs_cf if k in hc_cf and hs_cf[k] != hc_cf[k]
    ]

    # ---- 标注库对照 ----
    # 只拿视频类；照片和读取异常单独记
    ann_by_rel = {}
    ann_by_rel_cf = defaultdict(list)
    ann_non_video = []
    ann_no_path = []
    dup_ann_paths = []
    for rec in annotations:
        kind = rec.get("kind")
        # 小区全库没有 kind 字段，视为视频
        is_video = kind in (None, "", "视频", "读取异常")
        if rec["共享相对路径"] is None:
            ann_no_path.append(rec)
            continue
        rel = to_posix(rec["共享相对路径"])
        rec = {**rec, "共享相对路径": rel, "是视频": is_video}
        if not is_video:
            ann_non_video.append(rec)
            continue
        if rel in ann_by_rel:
            dup_ann_paths.append({"路径": rel, "已有ID": ann_by_rel[rel]["标注库ID"], "重复ID": rec["标注库ID"]})
        else:
            ann_by_rel[rel] = rec
        ann_by_rel_cf[rel.casefold()].append(rec)

    ann_match = {}
    ann_how_counter = Counter()
    for r in scan_videos:
        rel = r["共享相对路径"]
        a = ann_by_rel.get(rel)
        how = "精确路径"
        if a is None:
            cands = [x for x in ann_by_rel_cf.get(rel.casefold(), [])]
            if len(cands) == 1:
                a = cands[0]
                how = "大小写不同"
        if a is not None:
            ann_match[rel] = {"ann": a, "how": how}
            ann_how_counter[how] += 1

    matched_ann_ids = {v["ann"]["标注库ID"] for v in ann_match.values()}
    unmatched_scan = [r for r in scan_videos if r["共享相对路径"] not in ann_match]
    unmatched_ann = [a for rel, a in ann_by_rel.items() if a["标注库ID"] not in matched_ann_ids]

    # 标注库没有字节数和修改时间，第二轮无法按字段对。记入原因。
    ann_second_pass_note = "标注库索引记录不含字节数、修改时间字段，第二轮（字节数+修改时间）无法执行。"

    # 分库统计
    def lib_of_share_rel(rel: str) -> str | None:
        relp = to_posix(rel)
        for lib in cfg["库"]:
            pref = lib["相对根路径"]
            if relp == pref or relp.startswith(pref + "/"):
                return lib["库ID"]
        return None

    ann_stats = {}
    for lib_id, lib in libs.items():
        s = [r for r in scan_videos if r["库ID"] == lib_id]
        m = [r for r in s if r["共享相对路径"] in ann_match]
        u = [r for r in s if r["共享相对路径"] not in ann_match]
        ann_only = [a for a in unmatched_ann if lib_of_share_rel(a["共享相对路径"]) == lib_id]
        rate = (len(m) / len(s)) if s else 0
        ann_stats[lib_id] = {
            "目录名": lib["目录名"],
            "扫描视频数": len(s),
            "按路径对上": len(m),
            "扫描未对上": len(u),
            "标注库有扫描没有": len(ann_only),
            "对上比例": round(rate, 4),
            "是否达到九成": rate >= 0.9,
        }

    # ---- 组装原片表 ----
    records = []
    need_probe = []
    limit_counts = Counter()
    source_types = Counter()
    for r in scan_videos:
        lib = libs[r["库ID"]]
        share_rel = r["共享相对路径"]
        src_type = classify_source_type(lib["来源类型"], share_rel)
        source_types[src_type] += 1
        limit = match_limit(share_rel)
        avail = "可用"
        limit_text = ""
        if limit:
            avail = limit["可用状态"]
            limit_text = limit["目录限制原文"]
            limit_counts[limit["相对前缀"]] += 1

        jx = scan_match.get(r["库内相对路径"]) if r["库ID"] == "xiaoq" else None
        asset = jx["asset"] if jx else None
        ann = ann_match.get(share_rel, {}).get("ann")

        meta = {}
        if asset and asset.get("meta"):
            try:
                meta = json.loads(asset["meta"]) or {}
            except json.JSONDecodeError:
                meta = {}

        duration = None
        duration_src = None
        if meta.get("duration") not in (None, ""):
            duration = float(meta["duration"])
            duration_src = "镜序"
        elif ann and ann.get("duration_seconds") not in (None, ""):
            duration = float(ann["duration_seconds"])
            duration_src = "标注库"

        width = meta.get("width")
        height = meta.get("height")
        rotation = meta.get("rotation")
        dim_src = "镜序" if width not in (None, "") and height not in (None, "") else None
        aspect = orientation(width, height, rotation) if dim_src else None

        ann_id = ann["标注库ID"] if ann else ""
        origin_id = ann_id if ann_id else new_origin_id(r["库ID"], r["库内相对路径"])
        jx_id = asset["id"] if asset else ""
        if asset:
            # 镜序ID以登记表为准
            jx_id = asset["id"]

        sound = ""
        if ann and ann.get("audio_status"):
            sound = ann["audio_status"]
        elif meta.get("audio") is True:
            sound = "有音轨"
        elif meta.get("audio") is False:
            sound = "无音轨"

        rec = {
            "原片ID": origin_id,
            "逻辑路径": logical_path(prefix, share_rel),
            "标注库ID": ann_id,
            "镜序素材ID": jx_id,
            "字节数": r["字节数"],
            "修改时间": r["修改时间"],
            "时长": duration,
            "宽": width if width not in (None, "") else None,
            "高": height if height not in (None, "") else None,
            "旋转角度": rotation if rotation not in (None, "") else None,
            "画幅": aspect,
            "来源类型": src_type,
            "项目名": project_name(share_rel),
            "目录原名": dir_original_name(share_rel),
            "可用状态": avail,
            "目录限制原文": limit_text,
            "重复组": None,
            "声音": sound,
            "库ID": r["库ID"],
            "库内相对路径": r["库内相对路径"],
            "共享相对路径": share_rel,
            "出处": {
                "时长": duration_src,
                "宽高旋转": dim_src,
                "来源类型": "目录",
                "可用状态": "专有词表.md 第四节 / 目录" if limit else "目录默认可用",
                "标注对照": ann_match.get(share_rel, {}).get("how"),
                "镜序对照": (jx or {}).get("how"),
                "声音": "标注库" if (ann and ann.get("audio_status")) else ("镜序" if meta.get("audio") is not None else None),
            },
        }
        if rec["宽"] is None or rec["高"] is None or rec["时长"] is None:
            need_probe.append({
                "原片ID": origin_id,
                "逻辑路径": rec["逻辑路径"],
                "共享相对路径": share_rel,
                "库ID": r["库ID"],
                "库内相对路径": r["库内相对路径"],
                "缺时长": rec["时长"] is None,
                "缺宽高": rec["宽"] is None or rec["高"] is None,
                "字节数": r["字节数"],
            })
        records.append(rec)

    # 限制条数对照
    limit_cmp = []
    for item in VOCAB_LIMIT_DIRS:
        actual = limit_counts.get(item["相对前缀"], 0)
        limit_cmp.append({
            "相对前缀": item["相对前缀"],
            "词表条数": item["词表条数"],
            "本批实有视频数": actual,
            "差": actual - item["词表条数"],
            "可用状态": item["可用状态"],
            "目录限制原文": item["目录限制原文"],
        })

    # 写出原片表
    out_table = fragment_dir() / "原片表.jsonl"
    write_jsonl(out_table, records)
    write_jsonl(stat_dir / "原片表副本.jsonl", records)

    # 各类清单
    write_jsonl(check_dir / "镜序_登记表未在扫描中.jsonl", leftover_catalog)
    write_jsonl(check_dir / "镜序_扫描未在登记表中.jsonl", [
        {"库内相对路径": r["库内相对路径"], "共享相对路径": r["共享相对路径"], "字节数": r["字节数"], "修改时间": r["修改时间"]}
        for r in leftover_disk
    ])
    write_json(check_dir / "镜序_路径大小写不同.json", path_case_diffs)
    write_json(check_dir / "镜序_编号不一致.json", id_mismatch)
    write_json(check_dir / "镜序_字节数修改时间补对.json", size_time_matches)
    write_json(check_dir / "航天花园拍摄对照.json", hangtian_report)

    write_jsonl(check_dir / "标注库_扫描未对上.jsonl", [
        {"库ID": r["库ID"], "共享相对路径": r["共享相对路径"], "字节数": r["字节数"], "修改时间": r["修改时间"], "猜测原因": "标注库索引中无此相对路径；索引不含字节数和修改时间，无法做第二轮对"}
        for r in unmatched_scan
    ])
    write_jsonl(check_dir / "标注库_索引有扫描没有.jsonl", unmatched_ann)
    write_json(check_dir / "标注库_非视频或无路径.json", {
        "非视频": ann_non_video,
        "无路径": ann_no_path,
        "重复路径": dup_ann_paths,
        "第二轮说明": ann_second_pass_note,
    })
    write_jsonl(check_dir / "待ffprobe.jsonl", need_probe)

    # 主库清单缺失说明 + 与约定条数差
    inventory_note = {
        "约定清单路径": r"C:\Users\leega\AppData\Local\Temp\share-video-inventory-20261114\36-gongxiang.csv",
        "是否找到": False,
        "处理": "按任务书只读重扫四个目录，并与补充约定条数、镜序小区登记表对照",
        "与补充约定比较": count_cmp,
        "扫描总视频数": len(scan_videos),
        "补充约定总视频数": sum(EXPECTED_COUNTS.values()),
    }
    write_json(check_dir / "主库清单对照.json", inventory_note)

    summary = {
        "时间": now_iso(),
        "原片表条数": len(records),
        "原片表路径": str(out_table),
        "与补充约定比较": count_cmp,
        "镜序": {
            "登记表小区行数": len(xiaoq_assets),
            "精确路径对上": jingxu_exact,
            "大小写不同对上": jingxu_case,
            "字节数+修改时间对上": len(size_time_matches),
            "登记表未对上": len(leftover_catalog),
            "扫描未对上": len(leftover_disk),
            "编号不一致": len(id_mismatch),
            "路径大小写不同": len(path_case_diffs),
            "算法自检_按登记表路径计算与ID不符": sum(1 for x in id_mismatch if x.get("问题") == "登记表ID与算法不符"),
        },
        "航天花园拍摄": hangtian_report,
        "标注库": {
            "分库": ann_stats,
            "路径对上": dict(ann_how_counter),
            "扫描未对上": len(unmatched_scan),
            "索引有扫描没有_视频": len(unmatched_ann),
            "非视频": len(ann_non_video),
            "无路径": len(ann_no_path),
            "重复路径": len(dup_ann_paths),
            "第二轮": ann_second_pass_note,
            "四库是否都达九成": all(v["是否达到九成"] for v in ann_stats.values()),
        },
        "限制目录对照": limit_cmp,
        "来源类型分布": dict(source_types),
        "已有时长": sum(1 for r in records if r["时长"] is not None),
        "已有宽高": sum(1 for r in records if r["宽"] is not None and r["高"] is not None),
        "已有画幅": sum(1 for r in records if r["画幅"]),
        "待ffprobe": len(need_probe),
        "待ffprobe_缺时长": sum(1 for x in need_probe if x["缺时长"]),
        "待ffprobe_缺宽高": sum(1 for x in need_probe if x["缺宽高"]),
        "原片ID沿用标注库": sum(1 for r in records if r["标注库ID"]),
        "原片ID新编N前缀": sum(1 for r in records if not r["标注库ID"]),
    }
    write_json(stat_dir / "对照摘要.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
