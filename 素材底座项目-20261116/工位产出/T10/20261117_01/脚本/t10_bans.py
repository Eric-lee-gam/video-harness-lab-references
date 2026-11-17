# -*- coding: utf-8 -*-
"""Convert person bans and Aming source-rule clues."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t10_lib as L


def run():
    catalog = L.load_catalog()
    ann = L.load_ann_indexes()
    bans = []
    # official 1 rule
    data = json.loads((L.ANN / "person-usage-restrictions.json").read_text(encoding="utf-8"))
    for rule in data.get("rules") or []:
        src = rule.get("reference_source") or {}
        loc = L.locate(asset_id=src.get("id"), path=src.get("path"), root=src.get("root"), rel=src.get("rel"), catalog=catalog, ann=ann)
        rec = {
            "类型": "人物禁用",
            "规则ID": rule.get("rule_id"),
            "主库相对路径": loc.get("主库相对路径"),
            "原片ID": None,
            "镜序素材ID": loc.get("镜序素材ID"),
            "起秒": src.get("start"),
            "止秒": src.get("end"),
            "禁用原文": rule.get("evidence"),
            "决定原文": rule.get("decision"),
            "确认人": rule.get("confirmed_by"),
            "确认时间": rule.get("confirmed_at"),
            "适用范围": "仅已知已确认时段，不自动按外貌扩展",
            "apply_to_directory": rule.get("apply_to_directory"),
            "known_confirmed_ranges": rule.get("known_confirmed_ranges"),
            "other_appearances": rule.get("other_appearances"),
            "生产工具拦截": rule.get("production_tool_enforcement"),
            "镜序拦截说明": "镜序自己还没把它接进拦截。" + str(rule.get("production_tool_enforcement") or ""),
            "来源文件": "local/action-annotation/person-usage-restrictions.json",
            "来源条目标识": rule.get("rule_id"),
            "范围": loc.get("范围"),
            "目录": loc.get("目录"),
            "定位到文件": loc.get("定位到文件"),
            "完整规则原文": rule,
        }
        bans.append(rec)

    # 对照表中明确“不能用”的文件夹级禁用，另记并上报
    reported = []
    text = (L.RULES / "出镜文件夹确认图" / "对照表.md").read_text(encoding="utf-8")
    # sheet_05 already known in 专有词表, still add to ban table because it is a person/material ban
    for line in text.splitlines():
        if "不能用" in line or "不要用" in line:
            if line.startswith("| sheet_"):
                parts = [p.strip() for p in line.strip().strip("|").split("|")]
                if len(parts) >= 5:
                    folder = parts[1].strip().strip("`")
                    rel = folder if folder.startswith("史上最完整共享") else "史上最完整共享" + L.BS + folder
                    loc = L.locate(path=rel, catalog=catalog, ann=ann)
                    loc["主库相对路径"] = rel
                    loc["范围"] = L.range_flag(rel)
                    loc["目录"] = L.which_dir(rel)
                    bans.append({
                        "类型": "素材禁用或人物禁用（文件夹级）",
                        "规则ID": parts[0] + ":" + folder,
                        "主库相对路径": rel,
                        "原片ID": None,
                        "镜序素材ID": None,
                        "起秒": None,
                        "止秒": None,
                        "禁用原文": parts[4],
                        "确认人": "李康",
                        "确认时间": "2026-11-16",
                        "来源文件": "出镜文件夹确认图/对照表.md",
                        "来源条目标识": parts[0],
                        "范围": loc.get("范围"),
                        "目录": loc.get("目录"),
                        "定位到文件": False,
                        "确认级别": "文件夹级",
                        "说明": "来自李康按文件夹看图确认，不是镜序拦截规则；发现后写入禁用表并上报",
                    })
                    reported.append({"来源": parts[0], "文件夹": folder, "原文": parts[4]})

    dest = L.CLIPLIB / "禁用表.jsonl"
    L.write_jsonl(dest, bans)
    L.write_jsonl(L.OUT / "片段库副本" / "禁用表.jsonl", bans)

    # clues: aming source rules
    aming = json.loads((L.ANN / "aming-source-rule-index.json").read_text(encoding="utf-8"))
    clues = []
    for row in aming.get("rows") or []:
        loc = L.locate(asset_id=row.get("id"), root=row.get("root"), rel=row.get("rel"), catalog=catalog, ann=ann)
        clues.append({
            "类型": "阿明来源规则",
            "主库相对路径": loc.get("主库相对路径"),
            "原片ID": None,
            "镜序素材ID": loc.get("镜序素材ID") or row.get("id"),
            "起秒": None,
            "止秒": None,
            "内容": row,
            "来源规则原文": row.get("source_rule"),
            "主要讲解者": row.get("principal_speaker_identity"),
            "未逐片核实": row.get("clip_person_visible") or "未逐片核实",
            "核实标记": "未逐片核实",
            "范围说明": aming.get("scope"),
            "确认级别": "文件夹级",
            "来源文件": "local/action-annotation/aming-source-rule-index.json",
            "来源条目标识": row.get("id"),
            "范围": loc.get("范围"),
            "目录": loc.get("目录"),
            "定位到文件": loc.get("定位到文件"),
        })
    dest2 = L.CLIPLIB / "线索.jsonl"
    L.write_jsonl(dest2, clues)
    L.write_jsonl(L.OUT / "片段库副本" / "线索.jsonl", clues)

    # confirm V2 anti-example in 事实层
    v2_hits = []
    facts_path = L.CLIPLIB / "事实层.jsonl"
    for i, rec in L.iter_jsonl(facts_path):
        blob = json.dumps(rec, ensure_ascii=False)
        path = rec.get("主库相对路径") or ""
        if "二印小区厨卫" in path and "人物出镜" in path:
            if rec.get("来源条目标识") in ("confirmed-V2", "V2") or "不是阿明" in blob:
                v2_hits.append({
                    "事实编号": rec.get("事实编号"),
                    "来源条目标识": rec.get("来源条目标识"),
                    "主库相对路径": path,
                    "起秒": rec.get("起秒"),
                    "止秒": rec.get("止秒"),
                    "确认人": rec.get("确认人"),
                    "内容摘要": rec.get("内容", {}).get("description") if isinstance(rec.get("内容"), dict) else None,
                })
        elif rec.get("来源条目标识") == "confirmed-V2":
            v2_hits.append({
                "事实编号": rec.get("事实编号"),
                "来源条目标识": rec.get("来源条目标识"),
                "主库相对路径": path,
                "起秒": rec.get("起秒"),
                "止秒": rec.get("止秒"),
            })

    meta = {
        "禁用表条数": len(bans),
        "人物禁用原文条数": sum(1 for b in bans if b.get("类型") == "人物禁用"),
        "线索条数": len(clues),
        "阿明来源规则updated": aming.get("updated"),
        "阿明来源规则scope": aming.get("scope"),
        "线索定位到文件": sum(1 for c in clues if c.get("定位到文件")),
        "二印小区厨卫人物出镜反例": v2_hits,
        "新发现禁用上报": reported,
    }
    L.write_json(L.OUT / "统计" / "禁用与线索汇总.json", meta)
    print("bans", len(bans), "clues", len(clues), "v2_hits", v2_hits, "new bans", reported)
    print("WROTE", dest, dest2)
    return bans, clues, meta


if __name__ == "__main__":
    run()
