# -*- coding: utf-8 -*-
"""T10 20261117_03：对应总纲标签返工脚本（默认只干跑，不改正式库）。

李康已定（2026-11-17）：
- 映射补进「上罩面」「滚刷涂布」「铺料找平」，并重写受影响记录的对应总纲标签。
- 对应总纲标签以复核优先，只保留一个 B1 画面类型。
- 检索不要只用未复核的工序原值。

本批未改正式 片段库\\粗标层.jsonl，等总指挥复核后再用 --apply。

推荐规则（与 T06A 20261117_03 有效工序一致，见返工说明）：
- 空复核（None / 空 / 未据此确认 / 待确认 / 瓷釉改色或底漆）回退到工序原值。
- B1 映射采用 T10 原表 + T06A PROCESS_TO_V 已补取值（不仅三项）。
- 只改「对应总纲标签」里的 B1，其它标签原样保留。
- 一条只保留一个 B1。

用法：
  C:\\Python314\\python.exe t10_rewrite_gang_labels.py           # 只干跑
  C:\\Python314\\python.exe t10_rewrite_gang_labels.py --apply  # 先备份再改正式库
"""
from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
COARSE = ROOT / "片段库" / "粗标层.jsonl"
OUT = ROOT / "工位产出" / "T10" / "20261117_03"
BACKUP_DIR = OUT / "输入副本"

V_TO_B1 = {
    "V05": "B1 画面类型=V05 施工·批刮覆盖",
    "V06": "B1 画面类型=V06 施工·滚涂",
    "V11": "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）",
    "V23": "B1 画面类型=V23 施工现场·其他",
    "V08": "B1 画面类型=V08 拆砸/贴砖（传统做法）",
    "V07": "B1 画面类型=V07 铲修旧墙/旧顶",
    "V09": "B1 画面类型=V09 铺保护膜/贴胶带",
    "V10": "B1 画面类型=V10 保洁/清扫（施工前后）",
}

# T10 原 PROCESS_TO_GANG + T06A PROCESS_TO_V 已补项（V 代码转成完整 B1 句）
PROCESS_TO_V = {
    "批刮摊料": "V05",
    "批刮覆盖": "V05",
    "批刮": "V05",
    "墙面基面上的批刮": "V05",
    "基面批刮": "V05",
    "铺料找平": "V05",
    "刮刀批刮": "V05",
    "批刀批刮": "V05",
    "滚涂": "V06",
    "滚涂罩面": "V06",
    "罩面": "V06",
    "上罩面": "V06",
    "滚刷涂布": "V06",
    "滚涂（基层未明）": "V06",
    "罩面（工序）": "V06",
    "搅拌配料": "V11",
    "取料": "V11",
    "纯取料": "V11",
    "材料桶展示": "V11",
    "备料或展示": "V11",
    "基层处理": "V23",
    "其他工序": "V23",
    "拆除": "V08",
    "铲除": "V07",
    "覆膜保护": "V09",
    "清洁": "V10",
    "抹布擦地面": "V10",
}

# 问题单字面只要排除「未据此确认」。T06A empty_process 还把下面这些当空。
T06A_EMPTY = {"", "None", "null", "未据此确认", "待确认", "瓷釉改色或底漆"}
LITERAL_EMPTY = {"", "None", "null", "未据此确认"}
THREE_NEW = {"上罩面", "滚刷涂布", "铺料找平"}


def empty_process(val, empty_set) -> bool:
    if val is None:
        return True
    return str(val).strip() in empty_set


def effective_process(proc, rev, empty_set):
    if not empty_process(rev, empty_set):
        return str(rev).strip()
    if not empty_process(proc, empty_set):
        return str(proc).strip()
    return None


def to_b1(name):
    if not name:
        return None
    v = PROCESS_TO_V.get(name)
    return V_TO_B1.get(v) if v else None


def split_labels(labels):
    if not labels:
        return []
    if isinstance(labels, str):
        return [x.strip() for x in labels.split("|") if x.strip()]
    return list(labels)


def new_labels(old_labels, new_b1):
    parts = split_labels(old_labels)
    non_b1 = [x for x in parts if not str(x).startswith("B1 ")]
    old_b1 = [x for x in parts if str(x).startswith("B1 ")]
    if new_b1:
        # keep first B1 position if any
        if old_b1:
            out = []
            inserted = False
            for x in parts:
                if str(x).startswith("B1 "):
                    if not inserted:
                        out.append(new_b1)
                        inserted = True
                else:
                    out.append(x)
            return out
        return parts + [new_b1]
    return non_b1


def analyze(empty_set):
    stats = Counter()
    examples = {}
    n = 0
    with COARSE.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            o = json.loads(line)
            n += 1
            orig = o.get("原字段") or {}
            proc, rev = orig.get("工序"), orig.get("工序复核")
            eff = effective_process(proc, rev, empty_set)
            new_b1 = to_b1(eff)
            old = [x for x in split_labels(o.get("对应总纲标签")) if str(x).startswith("B1 ")]
            old_u = list(dict.fromkeys(old))
            planned = [new_b1] if new_b1 else []
            kind = "不变"
            if old_u != planned:
                if new_b1 and not old_u:
                    kind = "新补B1"
                elif new_b1 and len(old_u) >= 2:
                    kind = "多B1收成一个"
                elif new_b1 and old_u and old_u != [new_b1]:
                    kind = "单B1被复核改写"
                elif not new_b1 and old_u:
                    kind = "有效工序无映射将去掉B1"
                else:
                    kind = "其他变化"
            stats[kind] += 1
            if kind != "不变":
                examples.setdefault(kind, [])
                if len(examples[kind]) < 8:
                    examples[kind].append({
                        "粗标编号": o.get("粗标编号"),
                        "工序": proc,
                        "工序复核": rev,
                        "有效工序": eff,
                        "旧B1": old,
                        "新B1": new_b1,
                    })
    return {"总条数": n, "分类": dict(stats), "例子": examples}


def apply_rewrite():
    OUT.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    bak = BACKUP_DIR / "粗标层.jsonl"
    if not bak.exists():
        print("backup ->", bak)
        shutil.copy2(COARSE, bak)
    else:
        print("backup already exists, reuse", bak)
    tmp = COARSE.with_name("粗标层.jsonl.t10_20261117_03.tmp")
    n = changed = 0
    empty_set = T06A_EMPTY
    with COARSE.open(encoding="utf-8") as src, tmp.open("w", encoding="utf-8", newline="\n") as dst:
        for line in src:
            if not line.strip():
                continue
            o = json.loads(line)
            n += 1
            orig = o.get("原字段") or {}
            eff = effective_process(orig.get("工序"), orig.get("工序复核"), empty_set)
            new_b1 = to_b1(eff)
            old_labels = o.get("对应总纲标签")
            planned = new_labels(old_labels, new_b1)
            if planned != split_labels(old_labels):
                o["对应总纲标签"] = planned
                changed += 1
            dst.write(json.dumps(o, ensure_ascii=False) + "\n")
    # count check
    with tmp.open(encoding="utf-8") as f:
        m = sum(1 for line in f if line.strip())
    if m != n:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"count mismatch tmp={m} src={n}, official not replaced")
    shutil.move(str(tmp), str(COARSE))
    return {"总条数": n, "改写条数": changed, "备份": str(bak)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="备份后改正式粗标层。默认只干跑。")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    a = {
        "问题单字面空值": analyze(LITERAL_EMPTY),
        "T06A有效工序空值（推荐）": analyze(T06A_EMPTY),
    }
    path = OUT / "干跑对照.json"
    path.write_text(json.dumps(a, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v["分类"] for k, v in a.items()}, ensure_ascii=False, indent=2))
    if args.apply:
        result = apply_rewrite()
        print("APPLIED", result)
    else:
        print("dry-run only, official coarse file not changed")


if __name__ == "__main__":
    main()
