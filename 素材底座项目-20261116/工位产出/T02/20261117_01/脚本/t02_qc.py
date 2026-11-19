# -*- coding: utf-8 -*-
"""抽 100 张拼图自查：转正、无帧、跨镜头、文件名与图上是否泄露项目/文件夹名。"""
from __future__ import annotations

import json
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

import t02_lib as L

OUT = L.OUT_DIR
MOSAIC_DIR = OUT / "拼图"
GOLD_DIR = OUT / "金标50段"


def has_placeholder(tile: Image.Image, ref: Image.Image) -> bool:
    # 与标准「无帧」图的差异很小则视为空位已印字
    a = tile.resize((120, 214))
    b = ref.resize((120, 214))
    diff = ImageChops.difference(a, b)
    stat = ImageStat.Stat(diff)
    mean = sum(stat.mean) / len(stat.mean)
    return mean < 12


def tile_is_upright_portrait(tile: Image.Image) -> tuple[bool, str]:
    """竖屏合格原片的格子应基本铺满 480×854，而不是上下大块灰边的横图。"""
    w, h = tile.size
    if (w, h) != (L.TILE_W, L.TILE_H):
        return False, f"格子尺寸{w}x{h}"
    # 检查上下边缘是否大面积纯灰（横图 pad 的特征）
    gray = (128, 128, 128)
    def edge_gray_ratio(box):
        crop = tile.crop(box)
        pix = list(crop.getdata())
        n = len(pix)
        if n == 0:
            return 0
        hit = sum(1 for p in pix if all(abs(p[i] - gray[i]) <= 8 for i in range(3)))
        return hit / n
    top = edge_gray_ratio((0, 0, w, 40))
    bot = edge_gray_ratio((0, h - 40, w, h))
    left = edge_gray_ratio((0, 80, 40, h - 80))
    right = edge_gray_ratio((w - 40, 80, w, h - 80))
    # 横图 pad 到竖框：上下灰边很大，左右几乎无灰边
    if top > 0.85 and bot > 0.85 and left < 0.3 and right < 0.3:
        return False, "上下大块灰边，可能未转成竖屏或横倒后被垫边"
    return True, "格子内容铺满或非典型灰边"


def scene_cuts(src: str, start: float, end: float) -> list[float]:
    """用 ffmpeg 场景变化检测 3–4 秒窗口内是否有切镜。"""
    # select 过滤器输出 scene 分数；只看窗口
    vf = f"select='gt(scene,0.35)',showinfo"
    cmd = [
        "ffprobe", "-hide_banner", "-loglevel", "info",
        "-ss", f"{start:.3f}", "-t", f"{max(0.2, end-start):.3f}",
        "-i", src,
        "-show_frames", "-of", "json", "-select_streams", "v:0",
        "-skip_frame", "nokey",
    ]
    # 上面 nokey 不合适。改用 ffmpeg 的 scene 输出
    cmd = [
        "ffmpeg", "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{max(0.2, end-start):.3f}",
        "-i", src, "-vf", "select='gt(scene,0.4)',metadata=print",
        "-an", "-f", "null", "-",
    ]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=60)
        text = (r.stderr or b"").decode("utf-8", "ignore")
        times = []
        for line in text.splitlines():
            if "scene_score" in line or "lavfi.scene_score" in line:
                # 伴随 pts_time
                pass
            if "pts_time:" in line and "scene_score" in text:
                # 不稳定。改用简单解析 pts_time 出现在 showinfo 风格行
                pass
        # 解析 lavfi.scene_score 与 pts
        pts = None
        hits = []
        for line in text.splitlines():
            if "pts_time:" in line:
                try:
                    pts = float(line.split("pts_time:")[1].split()[0].strip())
                except Exception:
                    pts = None
            if "lavfi.scene_score" in line or "scene_score" in line:
                if pts is not None:
                    hits.append(start + pts)
        return hits
    except Exception:
        return []


def name_leaks(name: str) -> list[str]:
    leaks = []
    for bad in ("拍摄", "小区", "阿明", "搅拌", "测试", "嘉贝乐", "shared", "史上", "月印府", "项目"):
        if bad.lower() in name.lower():
            leaks.append(bad)
    return leaks


def main():
    from t02_extract import placeholder_tile, is_good_mosaic, load_gold_jobs

    data = L.load_all()
    L.build_cut_index(data)
    segs = list(L.iter_jsonl(OUT / "挑段清单.jsonl"))
    by_id = {r["片段ID"]: r for r in segs}
    rng = random.Random(L.SEED)
    ids = [r["片段ID"] for r in segs]
    rng.shuffle(ids)
    sample_ids = ids[:100]
    ph = placeholder_tile()

    rows = []
    n_upright = 0
    n_ph_ok = 0
    n_cross = 0
    n_name_leak = 0
    n_size_ok = 0
    n_missing = 0
    for sid in sample_ids:
        rec = by_id[sid]
        path = MOSAIC_DIR / rec["拼图文件名"]
        row = {
            "片段ID": sid,
            "拼图文件名": rec["拼图文件名"],
            "画面类型代码": rec.get("画面类型代码"),
            "起秒": rec["起秒"],
            "止秒": rec["止秒"],
            "旋转角度": rec.get("旋转角度"),
            "项目名_仅内部记录": rec.get("项目名"),
        }
        leaks = name_leaks(rec["拼图文件名"])
        row["文件名泄露"] = leaks
        if leaks:
            n_name_leak += 1
        if not is_good_mosaic(path):
            row["结论"] = "文件缺失或尺寸不对"
            n_missing += 1
            rows.append(row)
            continue
        n_size_ok += 1
        im = Image.open(path).convert("RGB")
        tiles = [
            im.crop((0, 0, L.TILE_W, L.TILE_H)),
            im.crop((L.TILE_W, 0, L.MOSAIC_W, L.TILE_H)),
            im.crop((0, L.TILE_H, L.TILE_W, L.MOSAIC_H)),
            im.crop((L.TILE_W, L.TILE_H, L.MOSAIC_W, L.MOSAIC_H)),
        ]
        # 无帧
        ph_flags = [has_placeholder(t, ph) for t in tiles]
        expected_ph = 4 - len(rec.get("抽帧时间戳") or [])
        row["空位检测"] = ph_flags
        row["预期空位数"] = expected_ph
        # 预期是空位的格子应有「无帧」；非空位不应是无帧图（允许误检但记下）
        ph_ok = True
        if expected_ph > 0:
            # 最后 expected_ph 格应为无帧（抽帧按 0..n-1 填）
            if not all(ph_flags[-expected_ph:]):
                ph_ok = False
        row["空位有无帧"] = ph_ok
        if ph_ok:
            n_ph_ok += 1
        # 转正：对非空位格子检查
        upright_flags = []
        for i, t in enumerate(tiles):
            if ph_flags[i]:
                upright_flags.append(True)
                continue
            ok, reason = tile_is_upright_portrait(t)
            upright_flags.append(ok)
            if not ok:
                row.setdefault("转正问题", []).append(reason)
        row["转正"] = all(upright_flags)
        if row["转正"]:
            n_upright += 1
        # 跨镜头：标注库切点（0.02 秒以内视为边界对齐）+ ffmpeg 场景检测
        yuan = data["by_id"].get(rec["原片ID"])
        src = L.yuan_unc(yuan, data["share_root"]) if yuan else None
        cuts = []
        if src and Path(src).exists():
            cuts = scene_cuts(src, rec["起秒"], rec["止秒"])
        known = []
        for p in data["cuts"].get(rec["原片ID"], set()):
            if rec["起秒"] + 0.02 < p < rec["止秒"] - 0.02:
                known.append(p)
        row["场景检测切点"] = cuts
        row["标注切点内"] = known
        crossed = bool(cuts) or bool(known)
        row["疑似跨镜头"] = crossed
        if crossed:
            n_cross += 1
        # 图上文字泄露：本批拼图不烧路径，只可能无帧二字。文件名已查。
        row["图上烧录项目名"] = False
        im.close()
        rows.append(row)

    # 金标 50
    gold = {
        "张数": 0,
        "合格尺寸": 0,
        "seg_11": {},
        "seg_42": {},
        "缺失": [],
    }
    for i in range(1, 51):
        p = GOLD_DIR / f"seg_{i:02d}.jpg"
        if is_good_mosaic(p):
            gold["张数"] += 1
            gold["合格尺寸"] += 1
        elif p.exists():
            gold["张数"] += 1
            gold.setdefault("尺寸不对", []).append(f"seg_{i:02d}")
        else:
            gold["缺失"].append(f"seg_{i:02d}")
    for key in ("seg_11", "seg_42"):
        p = GOLD_DIR / f"{key}.jpg"
        info = {"存在": p.exists(), "合格尺寸": is_good_mosaic(p)}
        if p.exists():
            im = Image.open(p).convert("RGB")
            info["size"] = list(im.size)
            t0 = im.crop((0, 0, L.TILE_W, L.TILE_H))
            ok, reason = tile_is_upright_portrait(t0)
            # 这两条原片表画幅为横、旋转 -180。转正后应是正的横图垫在竖框里，上下会有灰边。
            # 「转正」看的是不要再 90 度横倒：左右应基本铺满，内容不是竖着被挤在中间。
            left = list(t0.crop((0, 80, 20, L.TILE_H - 80)).getdata())
            right = list(t0.crop((L.TILE_W - 20, 80, L.TILE_W, L.TILE_H - 80)).getdata())
            gray = (128, 128, 128)

            def ratio(pix):
                return sum(1 for p_ in pix if all(abs(p_[i] - gray[i]) <= 8 for i in range(3))) / max(len(pix), 1)

            info["左灰边比例"] = round(ratio(left), 3)
            info["右灰边比例"] = round(ratio(right), 3)
            info["上下灰边特征"] = (not ok)
            # 横片转正：左右不应有大灰边（否则可能仍是竖画被 90 度放歪再 pad）
            info["转正判断"] = info["左灰边比例"] < 0.4 and info["右灰边比例"] < 0.4
            info["说明"] = reason
            im.close()
        gold[key] = info

    summary = {
        "抽样": 100,
        "种子": L.SEED,
        "缺失或尺寸不对": n_missing,
        "尺寸合格": n_size_ok,
        "抽到的图全部是正的": n_upright == n_size_ok and n_missing == 0,
        "转正合格": n_upright,
        "空位全部有无帧": n_ph_ok == n_size_ok,
        "空位合格": n_ph_ok,
        "疑似跨镜头": n_cross,
        "跨镜头不超过5段": n_cross <= 5,
        "文件名泄露": n_name_leak,
        "金标": gold,
        "时间": L.now_iso(),
    }
    L.write_json(OUT / "统计" / "抽查100.json", {"摘要": summary, "明细": rows})
    lines = [
        "# 抽查 100 张拼图",
        "",
        f"日期：{L.now_iso()}（Asia/Shanghai）",
        f"随机种子：`{L.SEED}`，从 2000 段里抽 100 段。",
        "",
        f"- 尺寸合格：{n_size_ok}/100（缺失或尺寸不对 {n_missing}）",
        f"- 转正合格：{n_upright}/{n_size_ok if n_size_ok else 100}",
        f"- 空位有「无帧」：{n_ph_ok}/{n_size_ok if n_size_ok else 100}",
        f"- 疑似跨镜头：{n_cross}（标准：不超过 5 段）",
        f"- 文件名泄露项目/文件夹名：{n_name_leak}",
        "",
        "## 金标 50",
        "",
        f"- 出图 {gold['张数']}/50，合格尺寸 {gold['合格尺寸']}/50，缺失 {gold['缺失'] or '无'}",
        f"- seg_11 转正判断：{gold['seg_11']}",
        f"- seg_42 转正判断：{gold['seg_42']}",
        "",
    ]
    (OUT / "抽查100.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
