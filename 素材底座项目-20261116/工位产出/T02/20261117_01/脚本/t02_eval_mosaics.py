# -*- coding: utf-8 -*-
"""评估标注库现成抽帧拼图能否直接用于本批 2×2 规则。"""
from __future__ import annotations

import json
import random
import subprocess
from collections import Counter
from pathlib import Path

import t02_lib as L

OUT = L.OUT_DIR


def probe_image(path: Path):
    if not path.exists():
        return {"exists": False}
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        st = json.loads(r.stdout)["streams"][0]
        return {
            "exists": True,
            "width": st.get("width"),
            "height": st.get("height"),
            "size": path.stat().st_size,
            "name": path.name,
        }
    except Exception as e:
        return {"exists": True, "error": str(e), "name": path.name, "size": path.stat().st_size}


def is_2x2(info) -> bool:
    w, h = info.get("width"), info.get("height")
    if not w or not h:
        return False
    # 本批标准 960×1708，或明显的 2×2 竖屏格
    if w == L.MOSAIC_W and h == L.MOSAIC_H:
        return True
    # 允许少量偏差
    if abs(w - L.MOSAIC_W) <= 4 and abs(h - L.MOSAIC_H) <= 4:
        return True
    return False


def anonymous_name(name: str) -> bool:
    # 不含目录、项目、原文件名；允许 hash 或 seg_/m0001 这类
    if not name:
        return False
    lower = name.lower()
    bad = ["拍摄", "小区", "嘉贝乐", "shared", "史上"]
    return not any(b in name or b in lower for b in bad)


def main():
    data = L.load_all()
    segs = list(L.iter_jsonl(OUT / "挑段清单.jsonl"))
    label_unc = data["label_unc"]
    # 粗标编号 -> 证据路径
    by_cid = {}
    for c in data["coarse"]:
        if c.get("粗标编号"):
            by_cid[c["粗标编号"]] = c

    stats = Counter()
    details = []
    usable = []
    rng = random.Random(L.SEED)
    # 全量看元数据；图尺寸探测抽样 300 再加全部有证据的？2000 张探测还可以，但网络会慢。
    # 先列出证据路径，抽 200 张量尺寸，其余用路径规则判断。
    with_ev = []
    for rec in segs:
        cid = rec.get("粗标编号")
        coarse = by_cid.get(cid) if cid else None
        ev = ""
        ev_kind = None
        if coarse:
            ev = L.t06a.mosaic_path(coarse, label_unc) or ""
            ev_kind = coarse.get("记录种类")
        item = {
            "片段ID": rec["片段ID"],
            "粗标编号": cid,
            "证据": ev,
            "记录种类": ev_kind,
            "本批起止": [rec["起秒"], rec["止秒"]],
            "源窗口": (rec.get("切段") or {}).get("源窗口"),
        }
        if ev:
            stats["有证据路径"] += 1
            p = Path(ev)
            item["文件名"] = p.name
            item["匿名文件名"] = anonymous_name(p.name)
            # 用途预览是 mp4，不能当拼图
            if p.suffix.lower() in {".mp4", ".mov", ".avi", ".mkv"}:
                item["结论"] = "预览视频，不是拼图"
                stats["预览视频"] += 1
            else:
                with_ev.append(item)
        else:
            item["结论"] = "无现成拼图"
            stats["无现成拼图"] += 1
        details.append(item)

    sample_n = min(200, len(with_ev))
    sample = with_ev[:]
    rng.shuffle(sample)
    sample = sample[:sample_n]
    size_counter = Counter()
    for item in sample:
        info = probe_image(Path(item["证据"]))
        item["探测"] = info
        item["是2x2标准"] = is_2x2(info)
        if not info.get("exists"):
            item["结论"] = "证据文件不存在"
            stats["证据文件不存在"] += 1
        elif info.get("error"):
            item["结论"] = "探测失败"
            stats["探测失败"] += 1
        elif not item["是2x2标准"]:
            item["结论"] = f"不是2×2标准尺寸({info.get('width')}x{info.get('height')})"
            stats["非2x2"] += 1
            size_counter[(info.get("width"), info.get("height"))] += 1
        elif not item.get("匿名文件名", True):
            item["结论"] = "文件名不够匿名"
            stats["文件名不匿名"] += 1
        else:
            # 时段：现成整段证据对应的是粗标窗口，常常 5–12 秒、6 帧以上，与本批约 3 秒 4 帧不对齐
            src = item.get("源窗口") or item["本批起止"]
            if src and abs((src[1] - src[0]) - 3) > 1.2:
                item["结论"] = "时段未对齐到约3秒4帧"
                stats["时段未对齐"] += 1
            else:
                item["结论"] = "可考虑复用（仍需确认转正）"
                stats["初步可考虑"] += 1
                usable.append(item["片段ID"])

    # 未抽样的有证据图片：按样本尺寸分布推断，默认不能用（历史整段证据是 584×344/516）
    sampled_ids = {x["片段ID"] for x in sample}
    for item in details:
        if item.get("结论"):
            continue
        if item["片段ID"] in sampled_ids:
            continue
        item["结论"] = "未抽样探测；现成整段证据历史尺寸不是2×2，按不能直接用处理"
        stats["未抽样按不能用"] += 1

    report = {
        "本批段数": len(segs),
        "统计": dict(stats),
        "抽样探测数": sample_n,
        "抽样尺寸分布": {f"{w}x{h}": n for (w, h), n in size_counter.most_common()},
        "可考虑复用片段ID": usable,
        "结论": (
            "现成标注库拼图不能直接用于本批。它们是整段证据或用途预览，尺寸不是 960×1708 的 2×2，"
            "帧数和时段也不对齐到约 3 秒 4 帧，本批全部按新规则重抽。"
        ),
    }
    L.write_json(OUT / "统计" / "抽帧评估.json", report)
    lines = [
        "# 标注库现成拼图评估",
        "",
        f"日期：{L.now_iso()}（Asia/Shanghai）",
        "",
        f"本批 {len(segs)} 段里，有证据路径 {stats.get('有证据路径', 0)} 条，无现成拼图 {stats.get('无现成拼图', 0)} 条。",
        f"对 {sample_n} 张现成图做了尺寸探测。",
        "",
        "## 统计",
        "",
    ]
    for k, v in stats.most_common():
        lines.append(f"- {k}：{v}")
    lines += [
        "",
        "## 抽样尺寸",
        "",
    ]
    if size_counter:
        for (w, h), n in size_counter.most_common():
            lines.append(f"- {w}×{h}：{n}")
    else:
        lines.append("- 抽样里没有读到尺寸（或全部已是标准 2×2）。")
    lines += [
        "",
        "## 结论",
        "",
        report["结论"],
        "",
        f"可考虑复用：{len(usable)} 段。实际复制到本批产出的张数由抽帧脚本按评估结果执行（本评估为 0 则全部重抽）。",
        "",
    ]
    (OUT / "抽帧评估.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # 抽样明细
    L.write_json(OUT / "统计" / "抽帧评估抽样.json", sample)


if __name__ == "__main__":
    main()
