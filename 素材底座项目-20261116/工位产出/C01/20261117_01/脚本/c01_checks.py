# -*- coding: utf-8 -*-
"""C01 八项检查。每项数字均由本脚本从原始数据重算。"""
from __future__ import annotations

import ast
import hashlib
import json
import random
import re
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from c01_common import (
    ADDRESS_PATTERNS,
    ANN_OTHER_PATH,
    ANN_XIAOQ_PATH,
    C01_OUT,
    CATALOG_PATH,
    CONFIG_PATH,
    FRAGMENT_DIR,
    INVENTORY_CSV,
    IN_SCOPE_LIBS,
    PROJECT_DIR,
    SEED,
    TABLE_PATH,
    T01_OUT,
    T01_SCRIPTS,
    VOCAB_LIMIT_DIRS,
    file_meta,
    head_hash,
    iter_jsonl,
    jingxu_id,
    join_unc,
    load_catalog_xiaoq,
    load_json,
    now_iso,
    orientation,
    path_under_prefix,
    probe_file,
    sha256_file,
    share_rel_from_source_path,
    to_posix,
    write_json,
    write_jsonl,
)


def check1_counts(videos: list[dict], records: list[dict]) -> dict:
    scan_by_lib = Counter(r["库ID"] for r in videos)
    table_by_lib = Counter(r.get("库ID") for r in records)
    table_by_dir = Counter()
    for r in records:
        rel = to_posix(r.get("共享相对路径") or "")
        for lib in IN_SCOPE_LIBS:
            if path_under_prefix(rel, lib["相对根路径"]):
                table_by_dir[lib["库ID"]] += 1
                break

    # 路径去重：逻辑路径、共享相对路径
    logical = [r.get("逻辑路径") for r in records]
    share_rels = [to_posix(r.get("共享相对路径") or "") for r in records]
    lib_rels = [(r.get("库ID"), to_posix(r.get("库内相对路径") or "")) for r in records]

    def dups(seq):
        c = Counter(seq)
        return [{"值": k, "次数": v} for k, v in c.items() if k and v > 1]

    cmp = []
    all_equal = True
    for lib in IN_SCOPE_LIBS:
        lid = lib["库ID"]
        scan_n = scan_by_lib.get(lid, 0)
        table_n = table_by_lib.get(lid, 0)
        table_n2 = table_by_dir.get(lid, 0)
        equal = scan_n == table_n == table_n2
        if not equal:
            all_equal = False
        cmp.append({
            "库ID": lid,
            "目录名": lib["目录名"],
            "C01扫描视频数": scan_n,
            "原片表按库ID": table_n,
            "原片表按相对路径前缀": table_n2,
            "相等": equal,
            "差_扫描减原片表库ID": scan_n - table_n,
        })

    # 集合对照
    scan_paths = {to_posix(r["共享相对路径"]) for r in videos}
    table_paths = {to_posix(r.get("共享相对路径") or "") for r in records}
    only_scan = sorted(scan_paths - table_paths)
    only_table = sorted(table_paths - scan_paths)

    dup_logical = dups(logical)
    dup_share = dups(share_rels)
    dup_librel = dups(lib_rels)

    no_dups = not (dup_logical or dup_share or dup_librel)
    passed = all_equal and no_dups and not only_scan and not only_table

    # 相对约定 21152 / 分库
    expected = {"xiaoq": 20515, "ceshi": 330, "aming": 238, "jiaoban": 69}
    vs_expected = {
        lib["库ID"]: {
            "约定": expected[lib["库ID"]],
            "扫描": scan_by_lib.get(lib["库ID"], 0),
            "差": scan_by_lib.get(lib["库ID"], 0) - expected[lib["库ID"]],
        }
        for lib in IN_SCOPE_LIBS
    }

    mismatch_n = len(only_scan) + len(only_table) + sum(abs(x["差_扫描减原片表库ID"]) for x in cmp)
    denom = max(len(records), len(videos), 1)
    mismatch_rate = mismatch_n / denom

    result = {
        "项": 1,
        "名称": "条数",
        "通过": passed,
        "随机种子": None,
        "原片表条数": len(records),
        "C01扫描视频数": len(videos),
        "分库对照": cmp,
        "相对补充约定": vs_expected,
        "官方清单CSV存在": INVENTORY_CSV.exists(),
        "官方清单CSV路径": str(INVENTORY_CSV),
        "重复逻辑路径": dup_logical,
        "重复共享相对路径": dup_share,
        "重复库内相对路径": [
            {"库ID": k[0], "库内相对路径": k[1], "次数": v}
            for (k, v) in Counter(lib_rels).items()
            if k[0] and k[1] and v > 1
        ],
        "仅扫描有": only_scan,
        "仅原片表有": only_table,
        "不一致条数": mismatch_n,
        "不一致比例": round(mismatch_rate, 6),
        "是否超过百分之一": mismatch_rate > 0.01,
    }
    return result


def check2_jingxu(videos: list[dict], records: list[dict]) -> dict:
    xiaoq_videos = [r for r in videos if r["库ID"] == "xiaoq"]
    xiaoq_table = [r for r in records if r.get("库ID") == "xiaoq"]
    assets = load_catalog_xiaoq(CATALOG_PATH)

    catalog_by_rel = {}
    for a in assets:
        rel = to_posix(a["rel"])
        catalog_by_rel[rel] = a

    disk_by_rel = {to_posix(r["库内相对路径"]): r for r in xiaoq_videos}
    table_by_rel = {to_posix(r.get("库内相对路径") or ""): r for r in xiaoq_table}

    algo_vs_catalog = []  # 登记表路径算出的编号与登记表 id 不符
    exact_ok = 0
    catalog_missing_on_disk = []
    disk_missing_in_catalog = []
    table_id_mismatch = []  # 原片表编号与算法或登记表不符
    three_way_ok = 0

    for a in assets:
        rel = to_posix(a["rel"])
        computed = jingxu_id("xiaoq", rel)
        if computed != a["id"]:
            algo_vs_catalog.append({
                "登记表路径": rel,
                "登记表ID": a["id"],
                "按算法计算": computed,
            })
        if rel not in disk_by_rel:
            catalog_missing_on_disk.append({
                "镜序素材ID": a["id"],
                "登记表路径": rel,
                "字节数": a.get("size"),
            })

    for rel, r in disk_by_rel.items():
        computed = jingxu_id("xiaoq", rel)
        a = catalog_by_rel.get(rel)
        rec = table_by_rel.get(rel)
        table_id = (rec or {}).get("镜序素材ID") or ""
        if a is None:
            disk_missing_in_catalog.append({
                "库内相对路径": rel,
                "共享相对路径": r.get("共享相对路径"),
                "字节数": r.get("字节数"),
                "按算法计算": computed,
                "原片表镜序素材ID": table_id,
            })
            if table_id:
                table_id_mismatch.append({
                    "库内相对路径": rel,
                    "问题": "扫描有、登记表无，但原片表仍写了镜序素材ID",
                    "原片表镜序素材ID": table_id,
                    "按算法计算": computed,
                })
            continue
        # 三边：算法、登记表、原片表
        if a["id"] == computed and table_id == a["id"]:
            exact_ok += 1
            three_way_ok += 1
        else:
            table_id_mismatch.append({
                "库内相对路径": rel,
                "登记表ID": a["id"],
                "按算法计算": computed,
                "原片表镜序素材ID": table_id,
                "问题": "同路径三边编号不完全一致",
            })

    # 原片表有、扫描没有的小区路径
    table_only = []
    for rel, rec in table_by_rel.items():
        if rel and rel not in disk_by_rel:
            table_only.append({
                "库内相对路径": rel,
                "逻辑路径": rec.get("逻辑路径"),
                "镜序素材ID": rec.get("镜序素材ID") or "",
            })

    # 读 T01 清单，比对集合
    t01_cat_missing = list(iter_jsonl(T01_OUT / "核对" / "镜序_登记表未在扫描中.jsonl")) if (T01_OUT / "核对" / "镜序_登记表未在扫描中.jsonl").exists() else []
    t01_disk_missing = list(iter_jsonl(T01_OUT / "核对" / "镜序_扫描未在登记表中.jsonl")) if (T01_OUT / "核对" / "镜序_扫描未在登记表中.jsonl").exists() else []
    t01_id_file = T01_OUT / "核对" / "镜序_编号不一致.json"
    t01_id_mismatch = load_json(t01_id_file) if t01_id_file.exists() else []
    if not isinstance(t01_id_mismatch, list):
        t01_id_mismatch = t01_id_mismatch if isinstance(t01_id_mismatch, list) else []

    c01_cat_set = {x["登记表路径"] for x in catalog_missing_on_disk}
    t01_cat_set = {to_posix(x.get("登记表路径") or "") for x in t01_cat_missing}
    c01_disk_set = {x["库内相对路径"] for x in disk_missing_in_catalog}
    t01_disk_set = {to_posix(x.get("库内相对路径") or "") for x in t01_disk_missing}

    lists_match = (
        c01_cat_set == t01_cat_set
        and c01_disk_set == t01_disk_set
        and len(algo_vs_catalog) == len(t01_id_mismatch)
        and not table_id_mismatch
        and not table_only
    )
    # 通过标准：三边全部一致；不一致的条数和 T01 回报清单相同
    # 已知存在不一致（航天花园 + 20 条无扩展名），所以「三边全部一致」不成立，
    # 但若不一致清单与 T01 相同，本项仍通过。
    three_way_all = (
        len(catalog_missing_on_disk) == 0
        and len(disk_missing_in_catalog) == 0
        and len(algo_vs_catalog) == 0
        and len(table_id_mismatch) == 0
        and len(table_only) == 0
    )
    passed = three_way_all or lists_match

    mismatch_n = (
        len(catalog_missing_on_disk)
        + len(disk_missing_in_catalog)
        + len(algo_vs_catalog)
        + len(table_id_mismatch)
        + len(table_only)
    )
    denom = max(len(assets), len(xiaoq_videos), 1)
    # 同一改名事件不要重复按「超过 1%」放大：用登记表未对上 + 扫描未对上 + 编号不符 的路径数
    unique_mismatch_paths = set()
    unique_mismatch_paths |= {x["登记表路径"] for x in catalog_missing_on_disk}
    unique_mismatch_paths |= {x["库内相对路径"] for x in disk_missing_in_catalog}
    unique_mismatch_paths |= {x["登记表路径"] for x in algo_vs_catalog}
    rate = len(unique_mismatch_paths) / denom

    result = {
        "项": 2,
        "名称": "镜序编号",
        "通过": passed,
        "小区扫描视频数": len(xiaoq_videos),
        "小区原片表条数": len(xiaoq_table),
        "登记表小区行数": len(assets),
        "三边路径与编号完全一致": three_way_ok,
        "登记表ID与算法不符": algo_vs_catalog,
        "登记表有扫描没有": catalog_missing_on_disk,
        "扫描有登记表没有": disk_missing_in_catalog,
        "原片表编号问题": table_id_mismatch,
        "原片表有扫描没有": table_only,
        "与T01清单一致": lists_match,
        "T01_登记表未在扫描中": sorted(t01_cat_set),
        "C01_登记表未在扫描中": sorted(c01_cat_set),
        "T01_扫描未在登记表中条数": len(t01_disk_set),
        "C01_扫描未在登记表中条数": len(c01_disk_set),
        "仅C01有的扫描未登记": sorted(c01_disk_set - t01_disk_set),
        "仅T01有的扫描未登记": sorted(t01_disk_set - c01_disk_set),
        "T01_编号不一致条数": len(t01_id_mismatch),
        "不一致路径数": len(unique_mismatch_paths),
        "不一致比例": round(rate, 6),
        "是否超过百分之一": rate > 0.01,
        "三边全部一致": three_way_all,
    }
    return result


def full_path_from_record(share_root: str, rec: dict) -> Path:
    rel = rec.get("共享相对路径") or ""
    return Path(join_unc(share_root, *to_posix(rel).split("/")))


def check3_sample50(records: list[dict], share_root: str, seed: int = SEED) -> dict:
    rng = random.Random(seed)
    pool = list(records)
    rng.shuffle(pool)
    sample = pool[:50]
    rows = []
    ok = 0
    t0 = time.perf_counter()
    for i, rec in enumerate(sample, 1):
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
        dur_ok = False
        dim_ok = False
        rot_ok = False
        aspect_ok = False
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
            else:
                dur_ok = False
            dim_ok = (probe.get("宽") == rec.get("宽")) and (probe.get("高") == rec.get("高"))
            # 旋转：原片表可能是 None 或 0，探测得到 0 视为一致
            t_rot = rec.get("旋转角度")
            p_rot = probe.get("旋转角度")
            try:
                t_r = 0.0 if t_rot in (None, "") else float(t_rot)
                p_r = 0.0 if p_rot in (None, "") else float(p_rot)
                rot_ok = abs(t_r - p_r) < 0.5 or abs(t_r - p_r) % 360 < 0.5
            except (TypeError, ValueError):
                rot_ok = False
            aspect_mine = orientation(probe.get("宽"), probe.get("高"), probe.get("旋转角度"))
            aspect_ok = aspect_mine == rec.get("画幅")
        all_ok = exists and size_ok and probe.get("ok") and dur_ok and dim_ok and rot_ok and aspect_ok
        if all_ok:
            ok += 1
        row = {
            "序号": i,
            "原片ID": rec.get("原片ID"),
            "逻辑路径": rec.get("逻辑路径"),
            "库ID": rec.get("库ID"),
            "共享相对路径": rec.get("共享相对路径"),
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
        rows.append(row)
        mark = "OK" if all_ok else "FAIL"
        print(f"  抽检 {i}/50 {mark} {rec.get('逻辑路径')}", flush=True)

    passed = ok == 50 and len(rows) == 50
    result = {
        "项": 3,
        "名称": "抽50条看文件",
        "通过": passed,
        "随机种子": seed,
        "抽检条数": len(rows),
        "全部一致": ok,
        "不一致": len(rows) - ok,
        "用时秒": round(time.perf_counter() - t0, 2),
        "抽中的原片ID": [r["原片ID"] for r in rows],
        "抽中的逻辑路径": [r["逻辑路径"] for r in rows],
        "不一致记录": [r for r in rows if not r["全部一致"]],
        "明细": rows,
    }
    write_json(C01_OUT / "核对" / "抽检50条.json", result)
    return result


def load_annotations(share_root: str) -> list[dict]:
    recs = []
    for path, name in ((ANN_XIAOQ_PATH, "小区全库"), (ANN_OTHER_PATH, "测试阿明搅拌")):
        for o in iter_jsonl(path):
            recs.append({
                "标注库名": name,
                "标注库ID": o.get("id"),
                "source_path": o.get("source_path"),
                "共享相对路径": share_rel_from_source_path(o.get("source_path") or "", share_root),
                "kind": o.get("kind"),
                "duration_seconds": o.get("duration_seconds"),
            })
    return recs


def check4_annotation(records: list[dict], share_root: str, seed: int = SEED) -> dict:
    anns = load_annotations(share_root)
    by_id = {}
    dups = []
    for a in anns:
        aid = a["标注库ID"]
        if not aid:
            continue
        if aid in by_id:
            dups.append({"标注库ID": aid, "已有": by_id[aid]["source_path"], "重复": a["source_path"]})
        else:
            by_id[aid] = a

    matched = [r for r in records if r.get("标注库ID")]
    unmatched_table = [r for r in records if not r.get("标注库ID")]

    t01_unmatched_path = T01_OUT / "核对" / "标注库_扫描未对上.jsonl"
    t01_unmatched = list(iter_jsonl(t01_unmatched_path)) if t01_unmatched_path.exists() else []
    t01_un_rels = {to_posix(x.get("共享相对路径") or "") for x in t01_unmatched}
    table_un_rels = {to_posix(r.get("共享相对路径") or "") for r in unmatched_table}

    rng = random.Random(seed)
    mpool = list(matched)
    rng.shuffle(mpool)
    sample30 = mpool[:30]

    rows30 = []
    ok30 = 0
    for rec in sample30:
        aid = rec.get("标注库ID")
        ann = by_id.get(aid)
        same = False
        reason = ""
        ann_rel = None
        ann_src = None
        if ann is None:
            reason = "索引中找不到该ID"
        else:
            ann_src = ann.get("source_path")
            ann_rel = to_posix(ann.get("共享相对路径") or "") if ann.get("共享相对路径") is not None else None
            rec_rel = to_posix(rec.get("共享相对路径") or "")
            if ann_rel and ann_rel == rec_rel:
                same = True
            elif ann_rel and ann_rel.casefold() == rec_rel.casefold():
                same = True
                reason = "路径仅大小写不同，仍视为同一文件"
            else:
                reason = "ID找到了但路径不是同一个文件"
        if same:
            ok30 += 1
        rows30.append({
            "原片ID": rec.get("原片ID"),
            "标注库ID": aid,
            "原片表路径": rec.get("共享相对路径"),
            "索引source_path": ann_src,
            "索引相对路径": ann_rel,
            "是同一文件": same,
            "说明": reason,
        })

    # 对不上的 10 条：以 T01 清单为抽样总体；若清单与原片表空标注库ID集合不同，另行记录
    upool = list(t01_unmatched) if t01_unmatched else [
        {"共享相对路径": r.get("共享相对路径"), "库ID": r.get("库ID"), "原片ID": r.get("原片ID")}
        for r in unmatched_table
    ]
    rng2 = random.Random(seed)
    rng2.shuffle(upool)
    sample10 = upool[:10]

    # 为「自己试着找」建索引：精确路径、大小写、文件名
    ann_by_rel = {}
    ann_by_rel_cf = defaultdict(list)
    ann_by_name = defaultdict(list)
    ann_by_name_cf = defaultdict(list)
    for a in anns:
        kind = a.get("kind")
        is_video = kind in (None, "", "视频", "读取异常")
        if not is_video or not a.get("共享相对路径"):
            continue
        rel = to_posix(a["共享相对路径"])
        if rel not in ann_by_rel:
            ann_by_rel[rel] = a
        ann_by_rel_cf[rel.casefold()].append(a)
        name = rel.rsplit("/", 1)[-1]
        ann_by_name[name].append(a)
        ann_by_name_cf[name.casefold()].append(a)

    found10 = []
    rows10 = []
    for item in sample10:
        rel = to_posix(item.get("共享相对路径") or "")
        name = rel.rsplit("/", 1)[-1] if rel else ""
        found = None
        how = ""
        if rel in ann_by_rel:
            found = ann_by_rel[rel]
            how = "精确路径（T01应能对上，本项异常）"
        elif rel and len(ann_by_rel_cf.get(rel.casefold(), [])) == 1:
            found = ann_by_rel_cf[rel.casefold()][0]
            how = "忽略大小写的路径"
        else:
            cands = ann_by_name.get(name, [])
            if name and len(cands) == 1:
                found = cands[0]
                how = "文件名唯一命中"
            else:
                cands2 = ann_by_name_cf.get(name.casefold(), []) if name else []
                if name and len(cands2) == 1:
                    found = cands2[0]
                    how = "文件名忽略大小写唯一命中"
                else:
                    how = f"未找到唯一对应（同名候选{len(cands)}）"
        rec_found = found is not None and how in {"精确路径（T01应能对上，本项异常）", "忽略大小写的路径", "文件名唯一命中", "文件名忽略大小写唯一命中"}
        # 文件名唯一命中也算「能找到对应」
        if rec_found:
            found10.append({
                "共享相对路径": rel,
                "方式": how,
                "标注库ID": found.get("标注库ID"),
                "索引路径": found.get("共享相对路径"),
            })
        rows10.append({
            "共享相对路径": rel,
            "库ID": item.get("库ID"),
            "查找方式": how,
            "是否找到对应": rec_found,
            "找到的标注库ID": (found or {}).get("标注库ID") if rec_found else None,
            "找到的索引路径": (found or {}).get("共享相对路径") if rec_found else None,
        })

    passed = (ok30 == 30 and len(rows30) == 30 and len(found10) <= 1)
    result = {
        "项": 4,
        "名称": "标注库ID",
        "通过": passed,
        "随机种子": seed,
        "索引总条数": len(anns),
        "索引ID重复": dups,
        "原片表已对上": len(matched),
        "原片表对不上": len(unmatched_table),
        "T01对不上清单条数": len(t01_unmatched),
        "T01清单与原片表空标注库ID是否相同": t01_un_rels == table_un_rels,
        "仅T01清单有": sorted(t01_un_rels - table_un_rels),
        "仅原片表空ID有": sorted(table_un_rels - t01_un_rels),
        "抽30条已对上": {
            "条数": len(rows30),
            "同一文件": ok30,
            "不是同一文件": len(rows30) - ok30,
            "抽中原片ID": [r["原片ID"] for r in rows30],
            "明细": rows30,
        },
        "抽10条T01说对不上的": {
            "条数": len(rows10),
            "C01能找到对应": len(found10),
            "明细": rows10,
            "找到的记录": found10,
        },
    }
    write_json(C01_OUT / "核对" / "标注库抽检.json", result)
    return result


def check5_limits(videos: list[dict], records: list[dict]) -> dict:
    rows = []
    all_eq = True
    for item in VOCAB_LIMIT_DIRS:
        if not item["范围内"]:
            rows.append({
                "相对前缀": item["相对前缀"],
                "词表条数": item["词表条数"],
                "范围内": False,
                "说明": "不在本批四个目录内，本项不比条数",
            })
            continue
        pref = item["相对前缀"]
        scan_n = sum(1 for r in videos if path_under_prefix(r["共享相对路径"], pref))
        # 原片表：带这个限制 = 路径落在该目录，或目录限制原文等于词表写法
        table_by_path = [r for r in records if path_under_prefix(r.get("共享相对路径") or "", pref)]
        table_by_text = [r for r in records if (r.get("目录限制原文") or "") == item["目录限制原文"]]
        # 限制原文可能被多个目录共用吗？「打码」「需要打码」不同。检查集合。
        path_set = {to_posix(r.get("共享相对路径") or "") for r in table_by_path}
        # 带该限制原文但不在该目录下的
        text_only = [
            to_posix(r.get("共享相对路径") or "")
            for r in table_by_text
            if not path_under_prefix(r.get("共享相对路径") or "", pref)
        ]
        # 在该目录下但限制原文不符
        path_text_mismatch = [
            {
                "共享相对路径": to_posix(r.get("共享相对路径") or ""),
                "目录限制原文": r.get("目录限制原文") or "",
                "可用状态": r.get("可用状态"),
            }
            for r in table_by_path
            if (r.get("目录限制原文") or "") != item["目录限制原文"]
        ]
        equal = (scan_n == len(table_by_path) == item["词表条数"])
        if not equal:
            all_eq = False
        rows.append({
            "相对前缀": pref,
            "词表条数": item["词表条数"],
            "范围内": True,
            "C01扫描视频数": scan_n,
            "原片表路径落在该目录": len(table_by_path),
            "原片表限制原文等于词表": len(table_by_text),
            "相等": equal,
            "差_扫描减词表": scan_n - item["词表条数"],
            "差_原片表路径减词表": len(table_by_path) - item["词表条数"],
            "限制原文落在其他目录": text_only,
            "该目录下限制原文不符": path_text_mismatch,
        })

    in_scope_ok = all(x.get("相等") for x in rows if x.get("范围内"))
    result = {
        "项": 5,
        "名称": "限制",
        "通过": in_scope_ok,
        "对照": rows,
        "范围内目录全部相等": in_scope_ok,
    }
    return result


def check6_dedup(records: list[dict], share_root: str, seed: int = SEED) -> dict:
    groups = defaultdict(list)
    for r in records:
        g = r.get("重复组")
        if isinstance(g, dict) and g.get("组号"):
            groups[g["组号"]].append(r)
    group_ids = sorted(groups)
    rng = random.Random(seed)
    pick = list(group_ids)
    rng.shuffle(pick)
    pick = pick[:10]

    rows = []
    all_ok = True
    for gid in pick:
        members = groups[gid]
        hashes = []
        err = []
        roles = Counter()
        for r in members:
            roles[(r.get("重复组") or {}).get("角色")] += 1
            path = full_path_from_record(share_root, r)
            try:
                h = head_hash(path)
                hashes.append({
                    "原片ID": r.get("原片ID"),
                    "逻辑路径": r.get("逻辑路径"),
                    "角色": (r.get("重复组") or {}).get("角色"),
                    "字节数": r.get("字节数"),
                    "哈希": h,
                    "文件存在": path.is_file(),
                })
            except OSError as e:
                err.append({"原片ID": r.get("原片ID"), "逻辑路径": r.get("逻辑路径"), "error": str(e)})
                hashes.append({
                    "原片ID": r.get("原片ID"),
                    "逻辑路径": r.get("逻辑路径"),
                    "角色": (r.get("重复组") or {}).get("角色"),
                    "哈希": None,
                    "error": str(e),
                })
        unique_hashes = {x["哈希"] for x in hashes if x.get("哈希")}
        hash_same = (len(unique_hashes) == 1) and (len(err) == 0) and (len(hashes) == len(members))
        one_canon = roles.get("进入选材") == 1
        ok = hash_same and one_canon and len(members) >= 2
        if not ok:
            all_ok = False
        rows.append({
            "组号": gid,
            "成员数": len(members),
            "角色统计": dict(roles),
            "哈希相同": hash_same,
            "恰好一条进入选材": one_canon,
            "通过": ok,
            "唯一哈希数": len(unique_hashes),
            "成员": hashes,
            "读取失败": err,
        })

    passed = all_ok and len(pick) == 10 and len(group_ids) >= 10
    if len(group_ids) < 10:
        passed = False
    result = {
        "项": 6,
        "名称": "重复组",
        "通过": passed,
        "随机种子": seed,
        "原片表重复组数": len(group_ids),
        "原片表重复组成员数": sum(len(v) for v in groups.values()),
        "抽组数": len(pick),
        "抽到的组号": pick,
        "明细": rows,
        "全部通过": all_ok,
    }
    write_json(C01_OUT / "核对" / "重复组抽检.json", result)
    return result


HARDCODED_ALIAS_RE = re.compile(
    r"""['"]xia[o]?q['"]|['"]baba['"]|['"]ceshi['"]|['"]aming['"]|['"]jiaoban['"]|镜序库别名"""
)



def audit_ffprobe_rotation(records: list[dict], share_root: str, seed: int = SEED, n: int = 100) -> dict:
    """对出处为 ffprobe、原片表记为横且旋转为 0 的记录再抽一批，看 Display Matrix 是否其实有旋转。"""
    pool = []
    for r in records:
        src = (r.get("出处") or {}).get("宽高旋转")
        if src != "ffprobe":
            continue
        if r.get("画幅") != "横":
            continue
        if r.get("旋转角度") not in (None, "", 0, 0.0):
            continue
        pool.append(r)
    rng = random.Random(seed)
    pick = list(pool)
    rng.shuffle(pick)
    pick = pick[:n]
    missed = []
    ok = 0
    fail_probe = 0
    t0 = time.perf_counter()
    for rec in pick:
        path = full_path_from_record(share_root, rec)
        probe = probe_file(path)
        if not probe.get("ok"):
            fail_probe += 1
            continue
        rot = probe.get("旋转角度")
        try:
            rv = 0.0 if rot in (None, "") else float(rot)
        except (TypeError, ValueError):
            rv = 0.0
        aspect = orientation(probe.get("宽"), probe.get("高"), rot)
        if abs(rv) >= 0.5 and aspect and aspect != rec.get("画幅"):
            missed.append({
                "原片ID": rec.get("原片ID"),
                "逻辑路径": rec.get("逻辑路径"),
                "原片表旋转角度": rec.get("旋转角度"),
                "原片表画幅": rec.get("画幅"),
                "探测旋转角度": rot,
                "C01判定画幅": aspect,
                "宽": probe.get("宽"),
                "高": probe.get("高"),
            })
        else:
            ok += 1
    return {
        "总体_ffprobe记为横且旋转为0": len(pool),
        "抽查条数": len(pick),
        "随机种子": seed,
        "探测失败": fail_probe,
        "画幅仍然一致": ok,
        "探测到旋转且画幅应改": len(missed),
        "用时秒": round(time.perf_counter() - t0, 2),
        "应改样例": missed[:40],
    }


def search_t01_scripts() -> dict:
    hits_addr = []
    hits_alias = []
    files = sorted(T01_SCRIPTS.glob("*.py"))
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            for pat in ADDRESS_PATTERNS:
                if pat.search(line):
                    hits_addr.append({"文件": fp.name, "行号": i, "内容": line.strip()[:300], "模式": pat.pattern})
            # 库别名：字面量出现（配置生成与算法里写死的 xiaoq 等）
            if re.search(r'["\']xiaoq["\']|["\']baba["\']|["\']ceshi["\']|["\']aming["\']|["\']jiaoban["\']', line):
                # 排除注释里对任务说明的提及可保留，仍记下来
                hits_alias.append({"文件": fp.name, "行号": i, "内容": line.strip()[:300]})
    return {"脚本文件": [f.name for f in files], "写死地址": hits_addr, "库别名字面量": hits_alias}


def check7_config(share_root: str) -> dict:
    search = search_t01_scripts()
    no_hardcoded_addr = len(search["写死地址"]) == 0

    before = file_meta(CONFIG_PATH)
    # 复制到 C01 产出再改根路径
    cfg_copy_path = C01_OUT / "统计" / "素材库_不存在路径测试.json"
    cfg = load_json(CONFIG_PATH)
    fake = json.loads(json.dumps(cfg, ensure_ascii=False))
    fake_root = r"D:\path-does-not-exist-c01-20261117\not-a-real-library"
    # 按任务书只改一个根路径（第一个库）
    if not fake.get("库"):
        raise RuntimeError("配置里没有库")
    original_first_root = fake["库"][0]["根路径"]
    fake["库"][0]["根路径"] = fake_root
    write_json(cfg_copy_path, fake)

    run_out = C01_OUT / "统计" / "missing-path-run"
    run_out.mkdir(parents=True, exist_ok=True)
    scan_py = T01_SCRIPTS / "02_scan.py"
    t0 = time.perf_counter()
    proc = subprocess.run(
        [sys.executable, str(scan_py), "--config", str(cfg_copy_path), "--out-dir", str(run_out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(T01_SCRIPTS),
    )
    elapsed = time.perf_counter() - t0
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    has_msg = "路径不存在" in combined
    scanned_elsewhere = "已扫 " in (proc.stdout or "")
    after = file_meta(CONFIG_PATH)
    original_unchanged = (
        before["字节数"] == after["字节数"]
        and before["sha256"] == after["sha256"]
        and before["修改时间"] == after["修改时间"]
    )
    # 也核对片段库原片表没被这次运行改到：02_scan 不应写原片表
    passed = no_hardcoded_addr and has_msg and proc.returncode != 0 and (not scanned_elsewhere) and original_unchanged

    result = {
        "项": 7,
        "名称": "配置",
        "通过": passed,
        "脚本里写死的共享盘地址": search["写死地址"],
        "没有写死地址": no_hardcoded_addr,
        "脚本里库别名字面量": search["库别名字面量"],
        "库别名字面量条数": len(search["库别名字面量"]),
        "配置副本": str(cfg_copy_path),
        "改之前的根路径": original_first_root,
        "改成的根路径": fake_root,
        "改的是哪个库": fake["库"][0].get("目录名"),
        "T01脚本": str(scan_py),
        "退出码": proc.returncode,
        "输出含有路径不存在": has_msg,
        "是否扫描到了别的地方": scanned_elsewhere,
        "标准输出": (proc.stdout or "")[-3000:],
        "标准错误": (proc.stderr or "")[-3000:],
        "用时秒": round(elapsed, 2),
        "原配置运行前": before,
        "原配置运行后": after,
        "原配置保持原样": original_unchanged,
        "搜索的脚本": search["脚本文件"],
    }
    write_json(C01_OUT / "核对" / "配置检查.json", result)
    return result


WRITE_ATTRS = {
    "write_text", "write_bytes", "write_json", "write_jsonl",
    "replace", "rename", "unlink", "mkdir", "touch", "rmdir",
}
WRITE_FUNCS = {
    "open", "remove", "replace", "rename", "rmtree", "move", "copy", "copy2",
    "copyfile", "copytree", "makedirs", "mkdir",
}
WRITE_MODES = set("wax+")


def _const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _brief(node, source_line: str) -> str:
    return source_line.strip()[:300]


def check8_readonly() -> dict:
    writes = []
    files = sorted(T01_SCRIPTS.glob("*.py"))
    for fp in files:
        text = fp.read_text(encoding="utf-8")
        lines = text.splitlines()
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            writes.append({"文件": fp.name, "问题": f"无法解析:{e}", "目标推断": "未知"})
            continue
        for node in ast.walk(tree):
            lineno = getattr(node, "lineno", None)
            src = lines[lineno - 1] if lineno and 1 <= lineno <= len(lines) else ""
            if isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name == "open":
                    mode = "r"
                    if len(node.args) >= 2:
                        mode = _const_str(node.args[1]) or mode
                    for kw in node.keywords or []:
                        if kw.arg == "mode" and _const_str(kw.value):
                            mode = _const_str(kw.value)
                    if any(ch in mode for ch in "wax+"):
                        # + 且是 r+ 也算写
                        if mode.startswith("r") and "+" not in mode:
                            continue
                        writes.append({
                            "文件": fp.name,
                            "行号": lineno,
                            "种类": f"open(mode={mode})",
                            "代码": _brief(node, src),
                        })
                elif name in {"write_json", "write_jsonl", "write_text", "write_bytes", "replace",
                              "rename", "unlink", "touch", "remove", "rmtree", "move", "copy",
                              "copy2", "copyfile", "copytree"}:
                    writes.append({
                        "文件": fp.name,
                        "行号": lineno,
                        "种类": name,
                        "代码": _brief(node, src),
                    })
            # Path.open
        # 补充正则，防止漏掉
        for i, line in enumerate(lines, 1):
            if re.search(r"\.(write_text|write_bytes|unlink|replace)\(", line) or re.search(
                r"\b(write_json|write_jsonl)\(", line
            ) or re.search(r"open\([^)]*['\"][wax]", line):
                # 已收录则跳过同一行
                if any(w["文件"] == fp.name and w.get("行号") == i for w in writes):
                    continue
                writes.append({"文件": fp.name, "行号": i, "种类": "正则补漏", "代码": line.strip()[:300]})

    # 根据代码与已知辅助函数，给每个写入点归类目标范围
    project_s = str(PROJECT_DIR)
    share_markers = ["192.168.110.36", "共享本公司", "史上最完整共享"]
    jingxu_markers = [r"D:\CutFrame项目完整整理_20261116", "CutFrame项目完整整理"]
    classified = []
    outside = []
    share_or_pack = []
    for w in writes:
        code = w.get("代码") or ""
        target = "未直接写出字面路径，需结合辅助函数判断"
        scope = "待确认"
        if "fragment_dir()" in code or "config_path()" in code or "片段库" in code:
            target = "项目文件夹/片段库"
            scope = "项目文件夹内"
        elif "this_output_dir()" in code or "out_dir" in code or "stat_dir" in code or "check_dir" in code:
            target = "工位产出/T01（由 this_output_dir / --out-dir 决定）"
            scope = "项目文件夹内（默认）"
        elif "tmp" in code.lower() or "with_suffix" in code:
            target = "与正式产出同目录的临时文件（随后 replace）"
            scope = "随正式目标"
        if any(m in code for m in share_markers):
            scope = "共享盘（字面量出现在写入表达式）"
            share_or_pack.append(w)
        if any(m in code for m in jingxu_markers):
            scope = "镜序完整包（字面量出现在写入表达式）"
            share_or_pack.append(w)
        # 打开方式为读的 head_hash / magic 不应在 writes 里
        item = {**w, "目标推断": target, "范围": scope}
        classified.append(item)
        if scope not in {"项目文件夹内", "项目文件夹内（默认）", "随正式目标"} and "片段库" not in (target or ""):
            if scope.startswith("共享") or scope.startswith("镜序"):
                outside.append(item)

    # 人工归纳：T01 脚本里已知写入函数的目标
    known_targets = [
        {"脚本": "common.py", "函数": "write_json / write_jsonl", "目标": "由调用方传入的 Path；自身不写死外部路径", "范围内": True},
        {"脚本": "01_write_config.py", "目标": "默认 fragment_dir()/配置/素材库.json，以及 this_output_dir()/统计/素材库.json", "范围内": True},
        {"脚本": "02_scan.py", "目标": "--out-dir 下 输入副本/扫描清单.jsonl、统计/扫描摘要.json、核对/扫描异常.jsonl；根路径不存在时也只写 out-dir 摘要", "范围内": True},
        {"脚本": "03_build_table.py", "目标": "片段库/原片表.jsonl 与 --out-dir 下统计、核对清单", "范围内": True},
        {"脚本": "04_ffprobe_trial.py / 04b_ffprobe_rest.py", "目标": "片段库/原片表.jsonl 与 --out-dir 下统计；ffprobe 只读文件头；读共享盘用 rb 打开", "范围内": True},
        {"脚本": "05_dedup.py", "目标": "片段库/原片表.jsonl 与 --out-dir 下统计、核对；读共享盘用 rb 算前1MB哈希", "范围内": True},
        {"脚本": "06_audit.py", "目标": "--out-dir/核对/随机抽检50条.json；共享盘只做 is_file/stat", "范围内": True},
        {"脚本": "07_missing_path_test.py", "目标": "this_output_dir()/统计 与 核对/不存在路径测试.json，再调用 02_scan.py --out-dir", "范围内": True},
    ]

    all_in_project = (len(share_or_pack) == 0) and all(k["范围内"] for k in known_targets)
    result = {
        "项": 8,
        "名称": "只读",
        "通过": all_in_project,
        "写入或删除调用": classified,
        "调用条数": len(classified),
        "疑似写到共享盘或镜序完整包": share_or_pack,
        "已知目标归纳": known_targets,
        "全部落在项目文件夹": all_in_project,
        "项目文件夹": str(PROJECT_DIR),
    }
    write_json(C01_OUT / "核对" / "只读检查.json", result)
    return result
