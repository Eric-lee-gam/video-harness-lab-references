# -*- coding: utf-8 -*-
"""按查询清单跑 Marengo Search，只跑清单里的查询，不另外多跑。"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from t12_api import (  # noqa: E402
    ApiError,
    QuotaError,
    TwelveClient,
    key_status_label,
    redact_obj,
    redact_text,
    safe_id,
)

SHANGHAI = timezone(timedelta(hours=8))
BATCH = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T12\20261118_01")
STATS = BATCH / "统计"
QUERY_CSV = BATCH / "查询清单.csv"
RESULT_JSONL = BATCH / "检索结果.jsonl"
SEARCH_LOG = STATS / "检索控制台.log"
INDEX_JSON = STATS / "索引信息.json"
UPLOAD_LOG = STATS / "上传进度.jsonl"


def now_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"


def log(msg: str) -> None:
    line = f"{now_str()} {redact_text(msg)}"
    print(line, flush=True)
    STATS.mkdir(parents=True, exist_ok=True)
    with SEARCH_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def load_index_id() -> str:
    if not INDEX_JSON.exists():
        raise SystemExit("找不到索引信息")
    meta = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    idx = meta.get("index_id")
    if not idx:
        raise SystemExit("索引信息里没有 index_id")
    return str(idx)


def load_id_map() -> dict[str, str]:
    """video_id / indexed_asset_id / asset_id -> local_name"""
    mp: dict[str, str] = {}
    if not UPLOAD_LOG.exists():
        return mp
    last: dict[str, dict] = {}
    with UPLOAD_LOG.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = rec.get("local_name")
            if name:
                last[name] = rec
    for name, rec in last.items():
        for key in ("video_id", "indexed_asset_id", "asset_id"):
            val = rec.get(key)
            if val:
                mp[str(val)] = name
    return mp


def already_done() -> set[str]:
    done = set()
    if not RESULT_JSONL.exists():
        return done
    with RESULT_JSONL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            qid = rec.get("查询编号")
            if qid and rec.get("status") in {"ok", "empty"}:
                done.add(qid)
    return done


def main() -> int:
    if key_status_label() != "已设置":
        log("密钥环境变量: 还没有读到，停止检索")
        return 2
    if not QUERY_CSV.exists():
        raise SystemExit(f"找不到查询清单: {QUERY_CSV}")
    if RESULT_JSONL.exists():
        log(f"检索结果已存在，将跳过已完成的查询，追加未完成的：{RESULT_JSONL}")

    with QUERY_CSV.open(encoding="utf-8-sig", newline="") as f:
        queries = list(csv.DictReader(f))
    if not queries:
        raise SystemExit("查询清单为空")
    log(f"查询清单 {len(queries)} 条，将严格按清单检索，不多跑")

    index_id = load_index_id()
    idmap = load_id_map()
    log(f"index_id={index_id} 已映射视频编号 {len(set(idmap.values()))} 个")

    client = TwelveClient()
    if client._proxy_label:
        log(f"通过系统代理访问 API: {client._proxy_label}")
    done = already_done()
    n_run = 0
    for q in queries:
        qid = q.get("查询编号") or ""
        text = (q.get("查询文本") or "").strip()
        if not qid or not text:
            log(f"跳过空查询行: {q}")
            continue
        if qid in done:
            log(f"{qid} 已有结果，跳过")
            continue
        try:
            status, body, hdrs = client.search(
                index_id,
                text,
                search_options=["visual", "audio"],
                page_limit=10,
                group_by="clip",
                operator="or",
            )
            data = []
            if isinstance(body, dict):
                data = body.get("data") or body.get("results") or body.get("clips") or []
            elif isinstance(body, list):
                data = body
            rows = []
            for i, item in enumerate(data[:10], start=1):
                if not isinstance(item, dict):
                    continue
                vid = safe_id(item, "video_id", "indexed_asset_id", "id")
                rows.append({
                    "rank": item.get("rank") or i,
                    "video_id": item.get("video_id"),
                    "indexed_asset_id": item.get("indexed_asset_id") or vid,
                    "副本文件名": idmap.get(str(vid or "")) or idmap.get(str(item.get("video_id") or "")) or "",
                    "start": item.get("start"),
                    "end": item.get("end"),
                    "score": item.get("score"),
                    "confidence": item.get("confidence"),
                    "raw": redact_obj({k: item[k] for k in item if k not in {"raw"}}),
                })
            rec = {
                "ts": now_str(),
                "查询编号": qid,
                "画面类型代码": q.get("画面类型代码"),
                "画面类型": q.get("画面类型"),
                "查询种类": q.get("查询种类"),
                "查询文本": text,
                "index_id": index_id,
                "http_status": status,
                "status": "ok" if rows else "empty",
                "结果数": len(rows),
                "说明": "" if len(rows) == 10 else f"前10不足，实际 {len(rows)} 个",
                "results": rows,
            }
            with RESULT_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())
            n_run += 1
            log(f"{qid} {q.get('查询种类')} 「{text}」 结果 {len(rows)} 个")
        except QuotaError as e:
            rec = {
                "ts": now_str(), "查询编号": qid, "查询文本": text,
                "status": "quota_stopped", "http_status": e.status,
                "code": e.code, "error": e.user_message, "index_id": index_id,
            }
            with RESULT_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log(f"额度不足，停止检索。HTTP {e.status} code={e.code} {e.user_message}")
            return 4
        except ApiError as e:
            rec = {
                "ts": now_str(), "查询编号": qid, "查询文本": text,
                "status": "error", "http_status": e.status,
                "code": e.code, "error": e.user_message, "index_id": index_id,
            }
            with RESULT_JSONL.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            log(f"{qid} 检索失败 HTTP {e.status} {e.user_message}")
            return 1
        time.sleep(1.0)
    log(f"检索结束，本轮新跑 {n_run} 条，清单共 {len(queries)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
