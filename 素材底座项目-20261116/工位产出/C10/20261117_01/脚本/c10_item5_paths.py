# -*- coding: utf-8 -*-
"""C10 item 5: every fact path exists on the share, and catalog path matches."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c10_common import *

facts = load_jsonl(LIB / "事实层.jsonl")

# Independent confirmation of catalog root mapping (do not rely only on T10 config)
connc = open_sqlite_ro(RAW / "镜序" / "catalog.sqlite3")
catalog = {}
for row in connc.execute("SELECT id, root, rel, name FROM assets"):
    catalog[row["id"]] = {"id": row["id"], "root": row["root"], "rel": row["rel"], "name": row["name"]}
# pick one sample per known root and see if the mapped UNC exists
mapping_checks = []
for root, prefix in CATALOG_ROOT_TO_REL.items():
    row = connc.execute("SELECT id, root, rel, name FROM assets WHERE root=? LIMIT 1", (root,)).fetchone()
    if not row:
        mapping_checks.append({"root": root, "ok": False, "reason": "登记表无此 root"})
        continue
    rel = catalog_relpath(row["root"], row["rel"])
    unc = unc_from_rel(rel)
    exists = unc.exists()
    mapping_checks.append({
        "root": root, "id": row["id"], "rel": row["rel"],
        "mapped_主库相对路径": rel, "unc": str(unc), "exists": exists, "ok": exists,
    })
connc.close()

csv_official = Path(r"C:\Users\leega\AppData\Local\Temp\share-video-inventory-20261114\36-gongxiang.csv")

rows_out = []
missing_share = []
catalog_mismatch = []
catalog_unknown_root = []
no_jingxu_id = []
id_not_in_catalog = []

for f in facts:
    fid = f.get("事实编号")
    rel = f.get("主库相对路径")
    unc = unc_from_rel(rel) if rel else None
    exists = None
    exists_err = None
    if unc is not None:
        try:
            exists = unc.exists()
        except Exception as e:
            exists_err = repr(e)
            exists = False
    if not exists:
        missing_share.append({
            "事实编号": fid,
            "主库相对路径": rel,
            "unc": str(unc) if unc else None,
            "确认级别": f.get("确认级别"),
            "范围": f.get("范围"),
            "定位到文件(T10自称)": f.get("定位到文件"),
            "error": exists_err,
        })

    jid = f.get("镜序素材ID")
    cat_rel = None
    cat_cmp = None
    if jid in (None, "", []):
        no_jingxu_id.append(fid)
        cat_cmp = "无镜序素材ID"
    elif jid not in catalog:
        id_not_in_catalog.append({"事实编号": fid, "镜序素材ID": jid, "主库相对路径": rel})
        cat_cmp = "登记表无此ID"
    else:
        asset = catalog[jid]
        cat_rel = catalog_relpath(asset["root"], asset["rel"])
        if cat_rel is None:
            catalog_unknown_root.append({
                "事实编号": fid,
                "镜序素材ID": jid,
                "root": asset["root"],
                "rel": asset["rel"],
                "主库相对路径": rel,
            })
            cat_cmp = f"root={asset['root']} 无本批已核实的前缀映射"
        else:
            if paths_equal(cat_rel, rel):
                cat_cmp = "一致"
            else:
                cat_cmp = "不一致"
                catalog_mismatch.append({
                    "事实编号": fid,
                    "镜序素材ID": jid,
                    "root": asset["root"],
                    "登记表算出的路径": cat_rel,
                    "事实层主库相对路径": rel,
                })

    rows_out.append({
        "事实编号": fid,
        "exists": exists,
        "catalog": cat_cmp,
        "确认级别": f.get("确认级别"),
    })

# T10 claimed 定位不到 0 via 登记表/索引; official CSV missing
t10_missing_list = []  # from report: 定位不到 0 条

result = {
    "item": 5,
    "official_csv_exists": csv_official.exists(),
    "official_csv_path": str(csv_official),
    "catalog_root_mapping_checks": mapping_checks,
    "facts_n": len(facts),
    "share_exists_n": len(facts) - len(missing_share),
    "share_missing_n": len(missing_share),
    "share_missing": missing_share,
    "catalog_mismatch_n": len(catalog_mismatch),
    "catalog_mismatch": catalog_mismatch,
    "catalog_unknown_root_n": len(catalog_unknown_root),
    "catalog_unknown_root": catalog_unknown_root,
    "no_jingxu_id_n": len(no_jingxu_id),
    "id_not_in_catalog_n": len(id_not_in_catalog),
    "id_not_in_catalog": id_not_in_catalog,
    "t10_reported_missing": t10_missing_list,
    "t10_reported_missing_n": 0,
}
# pass: all exist (or missing list equals T10's list) AND all catalog comparisons consistent
# folder-level / no jingxu id: only share exists required
# unknown root: not a mismatch if T10 also said no mapping; still need share exists
mapping_ok = all(c.get("ok") for c in mapping_checks)
missing_list_matches_t10 = [x["主库相对路径"] for x in missing_share] == t10_missing_list
result["pass"] = (len(missing_share)==0 and len(catalog_mismatch)==0 and len(id_not_in_catalog)==0 and mapping_ok)
result["notes"] = (
    "官方 36-gongxiang.csv 在约定位置不存在，与 T10 回报一致，本项按共享盘实存 + 镜序登记表路径对照。"
    "chengdu/suzhou 没有在本批输入里写明主库目录，若事实层出现这两类 root 只记录、不按前缀强行对照。"
)
dump_json(MID / "item5_paths.json", result)
print("ITEM5 pass", result["pass"])
print("mapping", json.dumps(mapping_checks, ensure_ascii=False, indent=2))
print("exists", result["share_exists_n"], "missing", result["share_missing_n"])
if missing_share[:10]:
    print("missing sample", json.dumps(missing_share[:10], ensure_ascii=False)[:2000])
print("catalog mismatch", len(catalog_mismatch), "unknown root", len(catalog_unknown_root), "no id", len(no_jingxu_id), "id missing", len(id_not_in_catalog))
if catalog_mismatch[:5]:
    print(json.dumps(catalog_mismatch[:5], ensure_ascii=False)[:1500])
if catalog_unknown_root[:5]:
    print("unknown", json.dumps(catalog_unknown_root[:5], ensure_ascii=False)[:1000])
if id_not_in_catalog[:5]:
    print("not in cat", json.dumps(id_not_in_catalog[:5], ensure_ascii=False)[:1000])
print("csv exists", csv_official.exists())
