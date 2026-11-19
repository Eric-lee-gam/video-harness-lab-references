# -*- coding: utf-8 -*-
"""按新规则抽 2×2 拼图（2000 段 + 金标 50 段）。可断点续跑。"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import t02_lib as L

OUT = L.OUT_DIR
MOSAIC_DIR = OUT / "拼图"
GOLD_DIR = OUT / "金标50段"
TMP_DIR = OUT / "临时帧"
LOG_PATH = OUT / "统计" / "抽帧日志.jsonl"
PROGRESS_PATH = OUT / "统计" / "抽帧进度.json"
GOLD_CSV = L.RULES_ROOT / "试标50段" / "_对应表.csv"
WORKERS = 8
FRAME_TIMEOUT = 90
LOCK_PATH = OUT / "统计" / "抽帧.lock"
# 金标 seg_11 / seg_42：原片表 Display Matrix 为 -180、画幅为横，但画面实际是竖拍横倒。
# 按矩阵 autorotate 后仍横倒；这两条不用矩阵，强制 -noautorotate + 顺时针 90° 转正。
FORCE_PORTRAIT_CW90 = {"seg_11", "seg_42", "6fecf1b8b1ddad33", "4a5e6131206408e1"}


def check_no_ffmpeg():
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process -Name ffmpeg,ffprobe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
        capture_output=True, text=True,
    )
    ids = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
    return ids


def load_font(size=96):
    try:
        return ImageFont.truetype(str(L.FONT_PATH), size=size)
    except Exception:
        return ImageFont.load_default()


def placeholder_tile() -> Image.Image:
    img = Image.new("RGB", (L.TILE_W, L.TILE_H), (128, 128, 128))
    draw = ImageDraw.Draw(img)
    font = load_font(96)
    text = L.PLACEHOLDER_TEXT
    # 居中
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        x, y = (L.TILE_W - tw) // 2, (L.TILE_H - th) // 2
    except Exception:
        x, y = L.TILE_W // 3, L.TILE_H // 2
    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    return img


def is_good_mosaic(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 2000:
        return False
    try:
        with Image.open(path) as im:
            return im.size == (L.MOSAIC_W, L.MOSAIC_H)
    except Exception:
        return False


def extract_frame(src: str, t: float, angle, dest: Path, job_id: str = "") -> tuple[bool, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 500:
        try:
            with Image.open(dest) as im:
                if im.size == (L.TILE_W, L.TILE_H):
                    return True, "reuse"
        except Exception:
            pass
    scale = (
        f"scale={L.TILE_W}:{L.TILE_H}:force_original_aspect_ratio=decrease,"
        f"pad={L.TILE_W}:{L.TILE_H}:(ow-iw)/2:(oh-ih)/2:color=0x808080"
    )
    force = str(job_id) in FORCE_PORTRAIT_CW90
    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
    ]
    if force:
        # 忽略错误的 -180 矩阵，直接顺时针转 90° 转正
        cmd.append("-noautorotate")
        vf = "transpose=1," + scale
    else:
        # 交给 ffmpeg 按 Display Matrix / tags.rotate 转正（与 T01 原片表一致）
        vf = scale
    cmd += [
        "-ss", f"{t:.3f}",
        "-i", src,
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "3",
        str(dest),
    ]
    try:
        r = subprocess.run(
            cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=FRAME_TIMEOUT
        )
        if r.returncode != 0 or not dest.exists() or dest.stat().st_size < 200:
            err = (r.stderr or b"").decode("utf-8", "ignore")[-400:]
            return False, err or f"exit {r.returncode}"
        return True, "ok"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def compose_mosaic(tiles, dest: Path):
    canvas = Image.new("RGB", (L.MOSAIC_W, L.MOSAIC_H), (128, 128, 128))
    positions = [(0, 0), (L.TILE_W, 0), (0, L.TILE_H), (L.TILE_W, L.TILE_H)]
    for im, pos in zip(tiles, positions):
        canvas.paste(im, pos)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".tmp.jpg")
    canvas.save(tmp, format="JPEG", quality=90, optimize=True)
    tmp.replace(dest)


def do_job(job, share_root: str, placeholder: Image.Image) -> dict:
    dest = Path(job["dest"])
    if is_good_mosaic(dest):
        return {
            "id": job["id"],
            "status": "skip",
            "dest": str(dest),
            "frames": job.get("frame_times") or [],
            "placeholders": None,
        }
    src = job["src"]
    if not Path(src).exists():
        return {"id": job["id"], "status": "missing_src", "src": src, "dest": str(dest)}
    times = list(job.get("frame_times") or [])
    angle = job.get("旋转角度")
    tiles = []
    n_ph = 0
    errors = []
    tmp_root = TMP_DIR / job["id"]
    tmp_root.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        if i < len(times):
            fp = tmp_root / f"f{i}.jpg"
            ok, msg = extract_frame(src, times[i], angle, fp, job["id"])
            if ok:
                try:
                    tiles.append(Image.open(fp).convert("RGB"))
                    continue
                except Exception as e:
                    errors.append(f"open f{i}: {e}")
            else:
                errors.append(f"f{i} t={times[i]}: {msg}")
        tiles.append(placeholder.copy())
        n_ph += 1
    # 不足 4 帧已在上面补了无帧
    while len(tiles) < 4:
        tiles.append(placeholder.copy())
        n_ph += 1
    try:
        compose_mosaic(tiles, dest)
        for im in tiles:
            try:
                im.close()
            except Exception:
                pass
        status = "ok" if dest.exists() else "compose_fail"
    except Exception as e:
        status = "compose_fail"
        errors.append(str(e))
    return {
        "id": job["id"],
        "status": status,
        "dest": str(dest),
        "src": src,
        "frames": times,
        "placeholders": n_ph,
        "errors": errors,
    }


def load_gold_jobs(data) -> list[dict]:
    jobs = []
    # 逻辑路径索引
    by_rel = {}
    for y in data["yuans"]:
        rel = (y.get("共享相对路径") or "").replace("\\", "/")
        by_rel[rel] = y
        by_rel["史上最完整共享/" + rel] = y
    with GOLD_CSV.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            seg = (row.get("seg") or "").strip()
            rel = (row.get("原片") or "").replace("\\", "/")
            start = float(row["起始秒"])
            end = float(row["结束秒"])
            yuan = by_rel.get(rel)
            if yuan is None and rel.startswith("史上最完整共享/"):
                yuan = by_rel.get(rel[len("史上最完整共享/"):])
            src = L.yuan_unc(yuan, data["share_root"]) if yuan else str(Path(data["share_root"]).parent / rel.replace("/", "\\"))
            # 上面 parent 可能不对；原片列以 史上最完整共享\拍摄\... 开头，share_root 已含 史上最完整共享
            if yuan is None:
                rest = rel
                if rest.startswith("史上最完整共享/"):
                    rest = rest[len("史上最完整共享/"):]
                src = str(Path(data["share_root"]) / rest.replace("/", "\\"))
            dur = yuan.get("时长") if yuan else None
            jobs.append({
                "id": seg,
                "kind": "gold",
                "src": src,
                "dest": str(GOLD_DIR / f"{seg}.jpg"),
                "原片ID": yuan.get("原片ID") if yuan else None,
                "逻辑路径": yuan.get("逻辑路径") if yuan else None,
                "起秒": start,
                "止秒": end,
                "旋转角度": yuan.get("旋转角度") if yuan else None,
                "画幅": yuan.get("画幅") if yuan else None,
                "frame_times": L.frame_times(start, end, dur),
                "原片": rel,
            })
    return jobs


def load_batch_jobs(data) -> list[dict]:
    jobs = []
    by_id = data["by_id"]
    for rec in L.iter_jsonl(OUT / "挑段清单.jsonl"):
        yuan = by_id.get(rec["原片ID"])
        src = L.yuan_unc(yuan or rec, data["share_root"])
        jobs.append({
            "id": rec["片段ID"],
            "kind": "batch",
            "src": src,
            "dest": str(MOSAIC_DIR / rec["拼图文件名"]),
            "原片ID": rec["原片ID"],
            "逻辑路径": rec.get("逻辑路径"),
            "起秒": rec["起秒"],
            "止秒": rec["止秒"],
            "旋转角度": rec.get("旋转角度") if rec.get("旋转角度") is not None else (yuan.get("旋转角度") if yuan else None),
            "画幅": rec.get("画幅"),
            "frame_times": rec.get("抽帧时间戳") or L.frame_times(rec["起秒"], rec["止秒"], rec.get("时长")),
            "拼图文件名": rec["拼图文件名"],
            "画面类型代码": rec.get("画面类型代码"),
        })
    return jobs


def append_log(row: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_maps(batch_jobs, gold_jobs, results_by_id):
    # 对应表只给 T06 和总控：片段ID, 拼图名
    path = OUT / "对应表.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["片段ID", "拼图文件名", "画面类型代码", "原片ID", "起秒", "止秒", "出图"])
        for job in batch_jobs:
            dest = Path(job["dest"])
            ok = is_good_mosaic(dest)
            w.writerow([
                job["id"], job["拼图文件名"], job.get("画面类型代码") or "",
                job.get("原片ID") or "", job.get("起秒"), job.get("止秒"), int(ok),
            ])
    gpath = OUT / "金标50段" / "_对应表.csv"
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    with gpath.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["seg", "原片", "原片ID", "起始秒", "结束秒", "旋转角度", "画幅", "出图"])
        for job in gold_jobs:
            dest = Path(job["dest"])
            ok = is_good_mosaic(dest)
            w.writerow([
                job["id"], job.get("原片") or "", job.get("原片ID") or "",
                job.get("起秒"), job.get("止秒"), job.get("旋转角度"), job.get("画幅"), int(ok),
            ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=["gold", "batch", "all"], default="all")
    parser.add_argument("--workers", type=int, default=WORKERS)
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    MOSAIC_DIR.mkdir(parents=True, exist_ok=True)
    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    (OUT / "统计").mkdir(exist_ok=True)

    running = check_no_ffmpeg()
    if running:
        print(f"已有未结束的 ffmpeg/ffprobe 进程: {running}，停止以免叠跑。", flush=True)
        sys.exit(3)

    if LOCK_PATH.exists():
        try:
            old = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            old = {}
        pid = old.get("pid")
        # 若原进程还在，退出
        if pid and Path(rf"C:\Windows\System32").exists():
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id"],
                capture_output=True, text=True,
            )
            if str(pid) in (r.stdout or ""):
                print(f"抽帧锁被 pid={pid} 持有，退出。", flush=True)
                sys.exit(3)
    LOCK_PATH.write_text(json.dumps({"pid": os.getpid(), "time": L.now_iso()}, ensure_ascii=False), encoding="utf-8")

    started = time.time()
    try:
        print(f"[{L.now_iso()}] 加载数据", flush=True)
        data = L.load_all()
        jobs = []
        gold_jobs, batch_jobs = [], []
        if args.only in ("gold", "all"):
            gold_jobs = load_gold_jobs(data)
            jobs.extend(gold_jobs)
        if args.only in ("batch", "all"):
            batch_jobs = load_batch_jobs(data)
            jobs.extend(batch_jobs)
        print(f"任务 {len(jobs)}（金标 {len(gold_jobs)}，本批 {len(batch_jobs)}）", flush=True)

        placeholder = placeholder_tile()
        results = []
        done = skip = fail = 0
        # 预先统计已完成
        pending = []
        for job in jobs:
            if is_good_mosaic(Path(job["dest"])):
                skip += 1
            else:
                pending.append(job)
        print(f"已有合格拼图 {skip}，待抽 {len(pending)}，并发 {args.workers}", flush=True)

        results_by_id = {}
        if pending:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(do_job, job, data["share_root"], placeholder): job for job in pending}
                for i, fut in enumerate(as_completed(futs), 1):
                    job = futs[fut]
                    try:
                        rec = fut.result()
                    except Exception as e:
                        rec = {"id": job["id"], "status": "exception", "errors": [str(e)], "dest": job["dest"]}
                    results.append(rec)
                    results_by_id[rec["id"]] = rec
                    if rec.get("status") in {"ok", "skip"}:
                        done += 1
                    else:
                        fail += 1
                    append_log({**rec, "time": L.now_iso()})
                    if i % 20 == 0 or i == len(pending):
                        elapsed = time.time() - started
                        rate = i / elapsed if elapsed else 0
                        remain = (len(pending) - i) / rate if rate else 0
                        print(
                            f"[{L.now_iso()}] {i}/{len(pending)} 成功{done} 失败{fail} "
                            f"{rate:.2f} 段/秒 预计剩余 {remain/60:.1f} 分",
                            flush=True,
                        )
                        L.write_json(PROGRESS_PATH, {
                            "time": L.now_iso(),
                            "pending_total": len(pending),
                            "done_this_run": i,
                            "ok": done,
                            "fail": fail,
                            "skipped_existing": skip,
                            "elapsed_sec": round(elapsed, 1),
                        })

        # 最终对应表与摘要
        if args.only in ("gold", "all") and not gold_jobs:
            gold_jobs = load_gold_jobs(data)
        if args.only in ("batch", "all") and not batch_jobs:
            batch_jobs = load_batch_jobs(data)
        # 若只跑一部分，对应表仍按已有文件写
        if args.only == "gold":
            batch_jobs = load_batch_jobs(data) if (OUT / "挑段清单.jsonl").exists() else []
        write_maps(batch_jobs, gold_jobs, results_by_id)

        gold_ok = sum(1 for j in gold_jobs if is_good_mosaic(Path(j["dest"])))
        batch_ok = sum(1 for j in batch_jobs if is_good_mosaic(Path(j["dest"])))
        summary = {
            "结束": L.now_iso(),
            "用时秒": round(time.time() - started, 1),
            "金标任务": len(gold_jobs),
            "金标成功": gold_ok,
            "本批任务": len(batch_jobs),
            "本批成功": batch_ok,
            "本轮新抽成功": done,
            "本轮失败": fail,
            "跳过已有": skip,
            "失败列表": [r for r in results if r.get("status") not in {"ok", "skip"}],
        }
        L.write_json(OUT / "统计" / "抽帧摘要.json", summary)
        print(json.dumps({k: v for k, v in summary.items() if k != "失败列表"}, ensure_ascii=False, indent=2), flush=True)
        print(f"失败 {fail} 条", flush=True)
        missing_gold = gold_jobs and gold_ok < len(gold_jobs)
        missing_batch = (args.only in ("batch", "all")) and batch_jobs and batch_ok < len(batch_jobs)
        if missing_gold or missing_batch:
            sys.exit(1)
    finally:
        try:
            if LOCK_PATH.exists():
                LOCK_PATH.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    main()
