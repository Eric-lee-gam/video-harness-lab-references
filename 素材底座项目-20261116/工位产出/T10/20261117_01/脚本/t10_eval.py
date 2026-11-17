# -*- coding: utf-8 -*-
"""Convert learning.sqlite3 feedback and adoptions into 评价与采用.jsonl."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t10_lib as L


def build_run_index(cur):
    runs = {}
    cand_index = {}  # (run_id, candidate_id) -> item
    for rid, created, payload, result in cur.execute("SELECT id, created, payload, result FROM runs"):
        try:
            p = json.loads(payload) if payload else {}
        except Exception:
            p = {}
        try:
            r = json.loads(result) if result else {}
        except Exception:
            r = {}
        query = None
        context = None
        if isinstance(p, dict):
            query = p.get("query") or p.get("text") or p.get("prompt")
            context = p.get("context")
        if isinstance(r, dict):
            query = query or r.get("query")
            context = context or r.get("context")
        items = []
        if isinstance(r, dict) and isinstance(r.get("items"), list):
            items = r["items"]
        elif isinstance(r, list):
            items = r
        rec = {"id": rid, "created": created, "payload": p, "result": r, "query": query, "context": context, "items": items}
        runs[rid] = rec
        for it in items:
            if not isinstance(it, dict):
                continue
            cid = it.get("id") or it.get("candidate_id")
            if cid:
                cand_index[(rid, cid)] = it
        runs[rid] = rec
    return runs, cand_index


def run():
    catalog = L.load_catalog()
    ann = L.load_ann_indexes()
    conn = L.ro_sqlite(L.LEARN)
    cur = conn.cursor()
    runs, cand_index = build_run_index(cur)
    out = []
    unconverted = []

    # feedback
    n_fb = 0
    n_fb_located = 0
    for row in cur.execute(
        "SELECT id, created, run_id, candidate_id, reviewer, verdict, reason_code, reason FROM feedback"
    ):
        fid, created, run_id, candidate_id, reviewer, verdict, reason_code, reason = row
        n_fb += 1
        run = runs.get(run_id) or {}
        item = cand_index.get((run_id, candidate_id))
        loc = {"主库相对路径": None, "镜序素材ID": None, "标注库ID": None, "范围": "范围外", "目录": None, "定位依据": [], "定位到文件": False}
        start = end = None
        convert_ok = True
        fail_reason = None
        if item is None:
            convert_ok = False
            fail_reason = "检索记录中找不到对应 candidate_id"
        else:
            loc = L.locate(
                asset_id=item.get("asset_id"),
                path=item.get("path"),
                root=item.get("root"),
                rel=item.get("rel"),
                catalog=catalog,
                ann=ann,
            )
            start = item.get("start")
            end = item.get("end")
            if loc.get("定位到文件"):
                n_fb_located += 1
        rec = {
            "类型": "评价",
            "评价或采用ID": fid,
            "创建时间": created,
            "文案": run.get("query"),
            "文案上下文": run.get("context"),
            "主库相对路径": loc.get("主库相对路径"),
            "原片ID": None,
            "镜序素材ID": loc.get("镜序素材ID"),
            "起秒": start,
            "止秒": end,
            "合适与否": verdict,
            "原因代码": reason_code,
            "原因": reason,
            "评价人": reviewer,
            "检索ID": run_id,
            "候选ID": candidate_id,
            "范围": loc.get("范围"),
            "目录": loc.get("目录"),
            "定位到文件": loc.get("定位到文件"),
            "定位依据": loc.get("定位依据"),
            "来源文件": "local/cutframe/ai/learning.sqlite3#feedback",
            "来源条目标识": fid,
            "转出成功": convert_ok,
            "转不出原因": fail_reason,
            "候选原文摘录": {k: item.get(k) for k in ("asset_id", "name", "path", "rel", "root", "start", "end", "score", "reason") } if item else None,
        }
        if not convert_ok:
            unconverted.append({"类型": "评价", "id": fid, "原因": fail_reason, "run_id": run_id, "candidate_id": candidate_id})
        out.append(rec)

    # adoptions
    n_ad = 0
    n_ad_located = 0
    action_counts = {}
    for row in cur.execute(
        "SELECT id, created, project_id, task_id, run_id, candidate_id, action, payload FROM adoptions"
    ):
        aid, created, project_id, task_id, run_id, candidate_id, action, payload = row
        n_ad += 1
        action_counts[action] = action_counts.get(action, 0) + 1
        try:
            p = json.loads(payload) if payload else {}
        except Exception:
            p = {"_raw": payload}
        run = runs.get(run_id) or {}
        item = cand_index.get((run_id, candidate_id))
        # prefer payload path, fallback to run candidate
        asset_id = p.get("asset_id") or (item or {}).get("asset_id")
        path = p.get("path") or (item or {}).get("path")
        root = p.get("root") or (item or {}).get("root")
        rel = p.get("rel") or (item or {}).get("rel")
        start = p.get("start") if "start" in p else (item or {}).get("start")
        end = p.get("end") if "end" in p else (item or {}).get("end")
        loc = L.locate(asset_id=asset_id, path=path, root=root, rel=rel, catalog=catalog, ann=ann)
        convert_ok = True
        fail_reason = None
        if not (asset_id or path or rel):
            convert_ok = False
            fail_reason = "采用事件 payload 与检索记录都没有素材路径或 asset_id"
            unconverted.append({"类型": "采用", "id": aid, "原因": fail_reason, "run_id": run_id, "candidate_id": candidate_id})
        if loc.get("定位到文件"):
            n_ad_located += 1
        rec = {
            "类型": "采用",
            "评价或采用ID": aid,
            "创建时间": created,
            "文案": run.get("query"),
            "文案上下文": run.get("context"),
            "主库相对路径": loc.get("主库相对路径"),
            "原片ID": None,
            "镜序素材ID": loc.get("镜序素材ID"),
            "起秒": start,
            "止秒": end,
            "动作": action,
            "合适与否": action,
            "原因": p.get("reason"),
            "评价人": None,
            "项目ID": project_id,
            "任务ID": task_id,
            "检索ID": run_id,
            "候选ID": candidate_id,
            "范围": loc.get("范围"),
            "目录": loc.get("目录"),
            "定位到文件": loc.get("定位到文件"),
            "定位依据": loc.get("定位依据"),
            "来源文件": "local/cutframe/ai/learning.sqlite3#adoptions",
            "来源条目标识": aid,
            "转出成功": convert_ok,
            "转不出原因": fail_reason,
            "payload": p,
        }
        out.append(rec)

    conn.close()
    dest = L.CLIPLIB / "评价与采用.jsonl"
    L.write_jsonl(dest, out)
    L.write_jsonl(L.OUT / "片段库副本" / "评价与采用.jsonl", out)
    meta = {
        "评价条数": n_fb,
        "评价定位到素材": n_fb_located,
        "评价未定位": n_fb - n_fb_located,
        "采用条数": n_ad,
        "采用定位到素材": n_ad_located,
        "采用动作": action_counts,
        "转不出": unconverted,
        "总条数": len(out),
        "评价一半以上定位不到": (n_fb and (n_fb - n_fb_located) / n_fb > 0.5),
    }
    L.write_json(L.OUT / "统计" / "评价与采用汇总.json", meta)
    print("feedback", n_fb, "located", n_fb_located)
    print("adoptions", n_ad, "located", n_ad_located, "actions", action_counts)
    print("unconverted", len(unconverted))
    print("WROTE", dest, len(out))
    return out, meta


if __name__ == "__main__":
    run()
