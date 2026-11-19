# -*- coding: utf-8 -*-
"""T12 第 2 步：只读读取共享盘原片，在产出文件夹写成 720p 转正 MP4 副本。
不改共享盘和原片，不调用 Twelve Labs，中断可续跑。
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from t12_lib import (
    MAX_COPY_BYTES,
    OUT_ROOT,
    PROJECT_ROOT,
    SHARE_ROOT,
    SHORT_LIMIT_SEC,
    dur_of,
    fmt_hours,
    master_relpath,
    share_path,
    transcode_vf,
)

PYTHON = r"C:\Python314\python.exe"
FFMPEG_TIMEOUT_MIN = 120
WORKERS = 2  # 共享盘只读，稳妥起见少并发


def now_sh() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "（Asia/Shanghai）"


def running_ffmpeg_ffprobe() -> list[str]:
    cmd = [
        "powershell", "-NoProfile", "-Command",
        "Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(ffmpeg|ffprobe)\\.exe$' } | "
        "Select-Object ProcessId, Name, CommandLine | ConvertTo-Json -Compress",
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        out = (p.stdout or "").strip()
        return [out] if out and out not in ("[]", "null") else []
    except Exception as e:
        return [f"检查进程失败: {e}"]


def snapshot_share(rows: list[dict], by_id: dict) -> dict:
    """只读记录源文件大小与修改时间，用于证明未改共享盘。"""
    items = []
    for row in rows:
        rec = by_id[row["原片ID"]]
        src = share_path(rec)
        info = {"原片ID": row["原片ID"], "源路径": str(src)}
        try:
            st = src.stat()
            info.update({"存在": True, "字节数": st.st_size, "mtime": st.st_mtime,
                         "mtime_iso": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")})
        except FileNotFoundError:
            info.update({"存在": False, "字节数": None, "mtime": None})
        except OSError as e:
            info.update({"存在": "错误", "错误": str(e)})
        items.append(info)
    return {"时间": now_sh(), "条数": len(items), "文件": items}


def load_list():
    p = OUT_ROOT / "上传清单.csv"
    with p.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return rows


def load_yuan_by_id():
    from t12_lib import load_yuanpian
    by_id, _ = load_yuanpian()
    return by_id


def ffprobe_json(path: Path, timeout=60) -> dict:
    cmd = [
        "ffprobe", "-hide_banner", "-loglevel", "error",
        "-show_streams", "-show_format", "-show_entries",
        "stream=width,height,codec_name,duration,codec_type:stream_tags=rotate:stream_side_data:format=duration",
        "-of", "json", str(path),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"ffprobe exit {p.returncode}")
    return json.loads(p.stdout or "{}")


def rotation_from_probe(info: dict):
    for st in info.get("streams") or []:
        if st.get("codec_type") != "video":
            continue
        tags = st.get("tags") or {}
        if tags.get("rotate") not in (None, "", "0"):
            try:
                return float(tags["rotate"])
            except ValueError:
                return tags["rotate"]
        for sd in st.get("side_data_list") or []:
            if "rotation" in sd and sd.get("rotation") not in (None, 0, 0.0, "0"):
                return sd.get("rotation")
            # Display Matrix sometimes only has a matrix field; ffprobe often also emits rotation
        return 0
    return None


def verify_copy(path: Path, expect_dur: float, expect_portrait: bool) -> tuple[bool, str, dict]:
    info = ffprobe_json(path)
    fmt = info.get("format") or {}
    vstreams = [s for s in (info.get("streams") or []) if s.get("codec_type") == "video"]
    if not vstreams:
        return False, "没有视频流", info
    v = vstreams[0]
    w, h = int(v.get("width") or 0), int(v.get("height") or 0)
    dur = float(fmt.get("duration") or v.get("duration") or 0)
    rot = rotation_from_probe(info)
    problems = []
    if v.get("codec_name") != "h264":
        problems.append(f"编码是{v.get('codec_name')}不是h264")
    if expect_portrait and h < w:
        problems.append(f"转正后仍是横幅 {w}x{h}")
    if w <= 0 or h <= 0:
        problems.append("宽高无效")
    # 720p：短边应为 720（极小源若已按公式放大也会是 720）；允许 2 像素偶数舍入
    short = min(w, h)
    if short not in (720,) and short < 718:
        # 源本身短边小于 720 且我们本应放大；若仍很小则有问题
        problems.append(f"短边不是720（{w}x{h}）")
    if rot not in (None, 0, 0.0, "0"):
        problems.append(f"副本仍带旋转元数据 {rot}")
    if expect_dur and abs(dur - expect_dur) > max(0.6, expect_dur * 0.08):
        problems.append(f"时长偏差 源{expect_dur:.3f} 副本{dur:.3f}")
    ok = not problems
    return ok, "；".join(problems) if problems else "ok", {"宽": w, "高": h, "时长": dur, "旋转": rot, "编码": v.get("codec_name")}


def choose_bitrate_kbps(total_sec: float, n_files: int) -> int:
    """把副本总大小压在 2.5 GB 以内，预留余量。"""
    budget = 2.20 * 1024 * 1024 * 1024  # 字节，留 0.3 GB 余量给容器开销
    if total_sec <= 0:
        return 1200
    audio_bytes = 96_000 / 8 * total_sec
    overhead = 80_000 * n_files  # 每文件容器开销粗估
    video_bytes = budget - audio_bytes - overhead
    bps = video_bytes * 8 / total_sec
    kbps = int(bps / 1000)
    # 下限保证能看清测试画面，上限避免单个过肥
    kbps = max(700, min(kbps, 2200))
    return kbps


def transcode_one(job: dict) -> dict:
    src = Path(job["src"])
    dst = Path(job["dst"])
    tmp = dst.with_suffix(".tmp.mp4")
    vf = job["vf"]
    v_kbps = job["v_kbps"]
    timeout = job["timeout"]
    started = time.time()
    result = {
        "编号": job["编号"],
        "原片ID": job["原片ID"],
        "主库相对路径": job["主库相对路径"],
        "副本": str(dst),
        "源路径": str(src),
        "开始": now_sh(),
    }
    if not src.exists():
        result.update({"status": "缺源文件", "错误": "共享盘找不到源文件（只读检查）", "用时秒": 0})
        return result
    try:
        src_st = src.stat()
        result["源字节"] = src_st.st_size
        result["源mtime"] = src_st.st_mtime
    except OSError as e:
        result.update({"status": "源无法读取", "错误": str(e), "用时秒": 0})
        return result

    if tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            pass

    cmd = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
        "-noautorotate",
        "-i", str(src),
        "-vf", vf,
        "-map", "0:v:0",
        "-map", "0:a:0?",
        "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
        "-b:v", f"{v_kbps}k", "-maxrate", f"{v_kbps}k", "-bufsize", f"{v_kbps*2}k",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "44100",
        "-movflags", "+faststart",
        "-metadata:s:v:0", "rotate=0",
        str(tmp),
    ]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        result.update({"status": "超时", "错误": f"ffmpeg 超过 {timeout} 秒", "用时秒": time.time() - started})
        return result
    except Exception as e:
        result.update({"status": "失败", "错误": str(e), "用时秒": time.time() - started})
        return result

    if p.returncode != 0 or not tmp.exists() or tmp.stat().st_size == 0:
        err = (p.stderr or p.stdout or "").strip()[:2000]
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        result.update({"status": "失败", "错误": err or f"ffmpeg exit {p.returncode}", "用时秒": time.time() - started})
        return result

    # 覆盖已有未完成文件
    if dst.exists():
        try:
            dst.unlink()
        except OSError as e:
            result.update({"status": "失败", "错误": f"无法替换旧副本: {e}", "用时秒": time.time() - started})
            return result
    tmp.replace(dst)

    ok, why, meta = verify_copy(dst, job["时长秒"], expect_portrait=True)
    result["验收"] = meta
    result["副本字节"] = dst.stat().st_size
    result["用时秒"] = time.time() - started
    result["status"] = "成功" if ok else "验收未过"
    if not ok:
        result["错误"] = why
    return result


def already_done(progress: list[dict]) -> dict:
    last = {}
    for rec in progress:
        last[rec.get("编号")] = rec
    return {k: v for k, v in last.items() if v.get("status") == "成功"}


def read_progress(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_progress(path: Path, rec: dict):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main():
    copy_dir = OUT_ROOT / "副本"
    copy_dir.mkdir(parents=True, exist_ok=True)
    (OUT_ROOT / "统计").mkdir(exist_ok=True)
    progress_path = OUT_ROOT / "统计" / "转码进度.jsonl"
    map_path = OUT_ROOT / "编号对应表.csv"

    running = running_ffmpeg_ffprobe()
    if running:
        print("已有未结束的 ffmpeg/ffprobe 进程，停止以免叠跑：", running, flush=True)
        return 2

    rows = load_list()
    by_id = load_yuan_by_id()
    if not rows:
        print("没有上传清单，请先跑 t12_select.py", flush=True)
        return 1

    # 编号按清单顺序（已按路径排序）
    jobs = []
    for i, row in enumerate(rows, 1):
        rec = by_id[row["原片ID"]]
        code = f"t12_{i:04d}"
        jobs.append({
            "编号": code,
            "文件名": code + ".mp4",
            "原片ID": row["原片ID"],
            "主库相对路径": row["主库相对路径"],
            "时长秒": float(row["时长秒"]),
            "是否短于4秒": row.get("是否短于4秒") or ("是" if float(row["时长秒"]) < SHORT_LIMIT_SEC else "否"),
            "旋转角度": rec.get("旋转角度"),
            "画幅": rec.get("画幅"),
            "src": str(share_path(rec)),
            "dst": str(copy_dir / f"{code}.mp4"),
            "vf": transcode_vf(rec.get("旋转角度")),
            "为什么选它": row.get("为什么选它") or "",
        })

    # 写编号对应表（先写，转码可续跑）
    with map_path.open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["编号", "文件名", "主库相对路径", "原片ID", "时长秒", "是否短于4秒",
                  "旋转角度", "画幅", "源路径", "副本路径", "为什么选它"]
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for j in jobs:
            w.writerow({
                "编号": j["编号"], "文件名": j["文件名"],
                "主库相对路径": j["主库相对路径"], "原片ID": j["原片ID"],
                "时长秒": f"{j['时长秒']:.3f}", "是否短于4秒": j["是否短于4秒"],
                "旋转角度": j["旋转角度"] if j["旋转角度"] is not None else "",
                "画幅": j["画幅"] or "",
                "源路径": j["src"], "副本路径": j["dst"],
                "为什么选它": j["为什么选它"],
            })

    snap0_path = OUT_ROOT / "统计" / "共享盘只读快照_转码前.json"
    if not snap0_path.exists():
        print("记录共享盘只读快照（转码前）…", flush=True)
        snap0 = snapshot_share(rows, by_id)
        snap0_path.write_text(json.dumps(snap0, ensure_ascii=False, indent=2), encoding="utf-8")
        missing = [x for x in snap0["文件"] if x.get("存在") is not True]
        print(f"源文件可访问 {snap0['条数']-len(missing)}/{snap0['条数']}，找不到 {len(missing)}", flush=True)

    total_sec = sum(j["时长秒"] for j in jobs)
    v_kbps = choose_bitrate_kbps(total_sec, len(jobs))
    print(f"视频目标码率 {v_kbps} kbps，样本总时长 {fmt_hours(total_sec)}", flush=True)

    done = already_done(read_progress(progress_path))
    pending = []
    for j in jobs:
        j["v_kbps"] = v_kbps
        j["timeout"] = max(FFMPEG_TIMEOUT_MIN, int(j["时长秒"] * 30) + 90)
        prev = done.get(j["编号"])
        dst = Path(j["dst"])
        if prev and dst.exists() and dst.stat().st_size > 0:
            continue
        if dst.exists() and j["编号"] not in done:
            # 半成品，删掉重做
            try:
                dst.unlink()
            except OSError:
                pass
        pending.append(j)

    print(f"已成功 {len(jobs)-len(pending)}，待转 {len(pending)}", flush=True)
    t0 = time.time()
    ok_n = len(jobs) - len(pending)
    fail = []

    if pending:
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = {ex.submit(transcode_one, j): j for j in pending}
            for n, fut in enumerate(as_completed(futs), 1):
                rec = fut.result()
                append_progress(progress_path, rec)
                if rec.get("status") == "成功":
                    ok_n += 1
                else:
                    fail.append(rec)
                print(
                    f"[{ok_n+len(fail)}/{len(jobs)}] {rec.get('编号')} {rec.get('status')} "
                    f"{rec.get('用时秒', 0):.1f}s {rec.get('错误', '')}",
                    flush=True,
                )

    # 汇总
    copies = list(copy_dir.glob("t12_*.mp4"))
    total_size = sum(p.stat().st_size for p in copies)
    # 按编号对应
    size_by_code = {}
    for p in copies:
        size_by_code[p.stem] = p.stat().st_size

    short_rows, up_rows = [], []
    for j in jobs:
        rec = {
            "编号": j["编号"], "文件名": j["文件名"],
            "主库相对路径": j["主库相对路径"], "原片ID": j["原片ID"],
            "时长秒": j["时长秒"], "副本字节": size_by_code.get(j["编号"], 0),
            "有副本": j["编号"] in size_by_code,
        }
        if j["时长秒"] < SHORT_LIMIT_SEC:
            short_rows.append(rec)
        else:
            up_rows.append(rec)

    uploadable_with_copy = [r for r in up_rows if r["有副本"]]
    missing_up = [r for r in up_rows if not r["有副本"]]

    summary = {
        "时间": now_sh(),
        "用时秒": time.time() - t0,
        "清单条数": len(jobs),
        "成功": ok_n,
        "失败": [{"编号": r["编号"], "status": r.get("status"), "错误": r.get("错误")} for r in fail],
        "副本文件数": len(copies),
        "副本总字节": total_size,
        "副本总大小": f"{total_size/1024/1024/1024:.4f} GB",
        "是否不超过2.5GB": total_size <= MAX_COPY_BYTES,
        "码率kbps": v_kbps,
        "可上传>=4秒": {"应有": len(up_rows), "已有副本": len(uploadable_with_copy), "缺副本": [r["编号"] for r in missing_up]},
        "短于4秒": {
            "条数": len(short_rows),
            "占样本条数比例": len(short_rows) / len(jobs) if jobs else 0,
            "占样本时长比例": sum(r["时长秒"] for r in short_rows) / total_sec if total_sec else 0,
            "已有副本": sum(1 for r in short_rows if r["有副本"]),
        },
        "副本目录": str(copy_dir),
    }
    (OUT_ROOT / "统计" / "转码结果.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("转码收工", flush=True)
    print("副本目录", copy_dir, flush=True)
    print("副本总大小", summary["副本总大小"], "限 2.5 GB，超了吗", not summary["是否不超过2.5GB"], flush=True)
    print("失败", len(fail), "可上传缺副本", len(missing_up), flush=True)

    print("记录共享盘只读快照（转码后）…", flush=True)
    snap1 = snapshot_share(rows, by_id)
    (OUT_ROOT / "统计" / "共享盘只读快照_转码后.json").write_text(
        json.dumps(snap1, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # 对比
    snap0 = json.loads(snap0_path.read_text(encoding="utf-8"))
    changed = []
    before = {x["原片ID"]: x for x in snap0["文件"]}
    for x in snap1["文件"]:
        b = before.get(x["原片ID"]) or {}
        if b.get("字节数") != x.get("字节数") or b.get("mtime") != x.get("mtime"):
            changed.append({"原片ID": x["原片ID"], "前": b, "后": x})
    (OUT_ROOT / "统计" / "共享盘快照对比.json").write_text(
        json.dumps({"改动条数": len(changed), "改动": changed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("共享盘源文件大小或mtime变化条数", len(changed), "（应为0）", flush=True)
    return 0 if not fail and not missing_up and total_size <= MAX_COPY_BYTES and not changed else 1


if __name__ == "__main__":
    sys.exit(main())
