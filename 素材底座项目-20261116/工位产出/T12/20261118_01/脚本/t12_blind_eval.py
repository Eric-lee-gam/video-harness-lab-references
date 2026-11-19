# -*- coding: utf-8 -*-
"""准备盲评三件套：人工评判表、评判页、来源对应表。总数不超过 300 行。"""

from __future__ import annotations

import csv
import html
import json
import random
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

SHANGHAI = timezone(timedelta(hours=8))
ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
BATCH = ROOT / "工位产出" / "T12" / "20261118_01"
MAP_CSV = BATCH / "编号对应表.csv"
RESULT_JSONL = BATCH / "检索结果.jsonl"
QUERY_CSV = BATCH / "查询清单.csv"
COARSE = ROOT / "片段库" / "粗标层.jsonl"
OUT_JUDGE = BATCH / "人工评判表.csv"
OUT_HTML = BATCH / "评判页.html"
OUT_SRC = BATCH / "来源对应表.csv"
SEED = 20261118
MAX_ROWS = 300
MAX_PER_SIDE = 10


def now_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"


def load_map() -> dict[str, dict]:
    by_oid = {}
    by_path = {}
    sample_oids = set()
    for r in csv.DictReader(MAP_CSV.open(encoding="utf-8-sig")):
        oid = r.get("原片ID") or ""
        name = r.get("文件名") or ""
        if oid:
            by_oid[oid] = r
            sample_oids.add(oid)
        rel = (r.get("主库相对路径") or "").replace("/", "\\").lower()
        if rel:
            by_path[rel] = r
    return {"by_oid": by_oid, "by_path": by_path, "sample_oids": sample_oids}


def uri_for_local(path: Path) -> str:
    # file URI for Windows path
    s = str(path.resolve()).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", s):
        return "file:///" + quote(s, safe="/:")
    return "file://" + quote(s, safe="/:")


def main() -> int:
    rng = random.Random(SEED)
    mp = load_map()
    queries = list(csv.DictReader(QUERY_CSV.open(encoding="utf-8-sig")))
    # use 平常话 query text as the visible description
    plain = {}
    for q in queries:
        if q.get("查询种类") == "平常话":
            plain[q.get("画面类型代码")] = q.get("查询文本")
    results = []
    with RESULT_JSONL.open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    # TL candidates: prefer 平常话 results; if empty use 行话
    tl_by_code: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r.get("status") not in {"ok", "empty"}:
            continue
        code = r.get("画面类型代码") or ""
        kind = r.get("查询种类")
        for item in r.get("results") or []:
            local = item.get("副本文件名") or ""
            if not local:
                continue
            tl_by_code[code].append({
                "画面类型代码": code,
                "画面类型": r.get("画面类型"),
                "平常话描述": plain.get(code) or r.get("查询文本"),
                "副本文件名": local,
                "起秒": item.get("start"),
                "止秒": item.get("end"),
                "来源": "TwelveLabs",
                "来源细项": f"{r.get('查询编号')}/{kind}",
                "分数": item.get("score"),
            })

    # coarse candidates only for codes that exist in 粗标层 B1 tags, and only within sample videos
    tag_for = {
        "V05": "B1 画面类型=V05 施工·批刮覆盖",
        "V06": "B1 画面类型=V06 施工·滚涂",
        "V11": "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）",
        "V23": "B1 画面类型=V23 施工现场·其他",
    }
    coarse_by_code: dict[str, list[dict]] = defaultdict(list)
    wanted = set(tag_for.values())
    with COARSE.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            oid = rec.get("原片ID") or ""
            if oid not in mp["sample_oids"]:
                continue
            tags = rec.get("对应总纲标签") or []
            for code, tag in tag_for.items():
                if tag in tags:
                    info = mp["by_oid"].get(oid)
                    if not info:
                        continue
                    coarse_by_code[code].append({
                        "画面类型代码": code,
                        "画面类型": next((q.get("画面类型") for q in queries if q.get("画面类型代码") == code), code),
                        "平常话描述": plain.get(code) or "",
                        "副本文件名": info.get("文件名"),
                        "起秒": rec.get("起秒"),
                        "止秒": rec.get("止秒"),
                        "来源": "粗标层",
                        "来源细项": rec.get("粗标编号") or "",
                        "分数": "",
                    })

    codes = sorted(set(list(tl_by_code) + list(plain)))
    pooled = []
    notes = {}
    for code in codes:
        tl = tl_by_code.get(code) or []
        # unique by (副本, 起, 止)
        def uniq(items):
            seen = set()
            out = []
            for it in items:
                key = (it["副本文件名"], round(float(it["起秒"] or 0), 3), round(float(it["止秒"] or 0), 3))
                if key in seen:
                    continue
                seen.add(key)
                out.append(it)
            return out
        tl = uniq(tl)
        cr = uniq(coarse_by_code.get(code) or [])
        rng.shuffle(tl)
        rng.shuffle(cr)
        take_tl = tl[:MAX_PER_SIDE]
        take_cr = cr[:MAX_PER_SIDE]
        if not take_cr:
            notes[code] = "粗标层查不了的类，只放 Twelve Labs 的结果"
        for it in take_tl + take_cr:
            pooled.append(it)

    if len(pooled) > MAX_ROWS:
        pooled = pooled[:MAX_ROWS]

    # shuffle for blind table
    order = list(range(len(pooled)))
    rng.shuffle(order)
    judge_rows = []
    src_rows = []
    for i, idx in enumerate(order, start=1):
        it = pooled[idx]
        rid = f"R{i:03d}"
        judge_rows.append({
            "行号": rid,
            "查询的平常话描述": it["平常话描述"],
            "画面类型": it["画面类型"],
            "副本文件名": it["副本文件名"],
            "起秒": it["起秒"],
            "止秒": it["止秒"],
            "合适/不合适/看不清": "",
        })
        src_rows.append({
            "行号": rid,
            "来源": it["来源"],
            "来源细项": it["来源细项"],
            "画面类型代码": it["画面类型代码"],
            "画面类型": it["画面类型"],
            "副本文件名": it["副本文件名"],
            "起秒": it["起秒"],
            "止秒": it["止秒"],
            "分数": it.get("分数", ""),
            "备注": notes.get(it["画面类型代码"], ""),
        })

    with OUT_JUDGE.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["行号", "查询的平常话描述", "画面类型", "副本文件名", "起秒", "止秒", "合适/不合适/看不清"])
        w.writeheader()
        w.writerows(judge_rows)
    with OUT_SRC.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["行号", "来源", "来源细项", "画面类型代码", "画面类型", "副本文件名", "起秒", "止秒", "分数", "备注"])
        w.writeheader()
        w.writerows(src_rows)

    # HTML page with video clips
    copies = BATCH / "副本"
    concat = BATCH / "短片合成_重编码"
    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='utf-8'>",
        "<title>T12 盲评页</title>",
        "<style>body{font-family:sans-serif;max-width:980px;margin:24px auto;padding:0 12px}",
        ".card{border:1px solid #ccc;border-radius:8px;padding:12px;margin:16px 0}",
        "video{max-width:100%;background:#000}</style></head><body>",
        f"<h1>T12 盲评页</h1><p>生成时间：{html.escape(now_str())}。请按行填写「合适 / 不合适 / 看不清」。本页不显示来源。</p>",
    ]
    for row in judge_rows:
        name = row["副本文件名"]
        path = copies / name
        if not path.exists():
            path = concat / name
        uri = uri_for_local(path) if path.exists() else ""
        try:
            st = float(row["起秒"] or 0)
            en = float(row["止秒"] or 0)
        except (TypeError, ValueError):
            st, en = 0.0, 0.0
        parts.append("<div class='card'>")
        parts.append(f"<h3>{html.escape(row['行号'])} · {html.escape(str(row['画面类型']))}</h3>")
        parts.append(f"<p>{html.escape(str(row['查询的平常话描述']))}</p>")
        parts.append(f"<p>文件 {html.escape(str(name))}　{st:.2f}s – {en:.2f}s</p>")
        if uri:
            # media fragment approximates clip
            parts.append(
                f"<video controls preload='metadata' src='{html.escape(uri)}#t={st:.2f},{en:.2f}'></video>"
            )
        else:
            parts.append("<p style='color:red'>找不到本地视频文件</p>")
        parts.append("</div>")
    parts.append("</body></html>")
    OUT_HTML.write_text("\n".join(parts), encoding="utf-8")
    print(f"盲评行数 {len(judge_rows)}；写了 {OUT_JUDGE.name} / {OUT_HTML.name} / {OUT_SRC.name}")
    print("仅粗标层可查的类:", sorted(tag_for))
    print("粗标层取到条数:", {k: len(v) for k, v in coarse_by_code.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
