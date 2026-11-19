# -*- coding: utf-8 -*-
"""把短于 4 秒的副本拼成 >= 4 秒的合成件。不改原副本。"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SHANGHAI = timezone(timedelta(hours=8))  # Asia/Shanghai, no tzdata needed
MIN_SEC = 4.0

BATCH = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T12\20261118_01")
COPIES = BATCH / "副本"
SHORT_CSV = BATCH / "短于4秒清单.csv"
MAP_CSV = BATCH / "编号对应表.csv"
OUT_DIR = BATCH / "短片合成_重编码"
STATS = BATCH / "统计"
CONCAT_LIST = BATCH / "拼接清单_重编码.csv"
CONCAT_JSON = STATS / "短片拼接结果_重编码.json"


def now_str() -> str:
    return datetime.now(SHANGHAI).strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"


def ffprobe_duration(path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe 失败: {path.name}: {r.stderr.strip()}")
    return float(r.stdout.strip())


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def find_col(row: dict, candidates: list[str]) -> str | None:
    keys = list(row.keys())
    for c in candidates:
        if c in row:
            return c
    lower = {k.lower(): k for k in keys}
    for c in candidates:
        if c.lower() in lower:
            return lower[c.lower()]
    return None


def map_shorts() -> list[dict]:
    shorts = load_csv(SHORT_CSV)
    mapping = load_csv(MAP_CSV)
    if not shorts or not mapping:
        raise SystemExit("短于4秒清单或编号对应表为空")
    m0 = mapping[0]
    path_col = find_col(m0, ["主库相对路径", "共享相对路径", "原路径", "相对路径"])
    name_col = find_col(m0, ["副本文件名", "编号文件名", "文件名", "副本", "t12文件名"])
    id_col = find_col(m0, ["原片ID", "原片id"])
    if not path_col or not name_col:
        raise SystemExit(f"编号对应表列名无法识别: {list(m0.keys())}")
    by_path = {}
    by_id = {}
    for row in mapping:
        rel = (row.get(path_col) or "").replace("/", "\\")
        if rel:
            by_path[rel.lower()] = row
        oid = (row.get(id_col) or "") if id_col else ""
        if oid:
            by_id[oid] = row
    out = []
    for s in shorts:
        rel = (s.get("主库相对路径") or "").replace("/", "\\")
        oid = s.get("原片ID") or ""
        m = by_path.get(rel.lower()) or (by_id.get(oid) if oid else None)
        if not m:
            raise SystemExit(f"编号对应表找不到短片: {rel} / {oid}")
        copy_name = m[name_col]
        if not copy_name.lower().endswith(".mp4"):
            copy_name = copy_name + ".mp4"
        copy_path = COPIES / copy_name
        if not copy_path.is_file():
            raise SystemExit(f"副本不存在: {copy_path}")
        dur = ffprobe_duration(copy_path)
        out.append({
            "主库相对路径": s.get("主库相对路径") or "",
            "原片ID": oid,
            "项目名": s.get("项目名") or "",
            "为什么选它": s.get("为什么选它") or "",
            "清单时长秒": s.get("时长秒") or s.get("时长") or "",
            "副本文件名": copy_name,
            "副本路径": str(copy_path),
            "副本时长秒": round(dur, 3),
        })
    return out


def group_shorts(items: list[dict]) -> list[list[dict]]:
    """先按项目名成组（同类/就近）；已满 4 秒的组保留；未满的按清单顺序再合并。"""
    by_proj: dict[str, list[dict]] = defaultdict(list)
    order: list[str] = []
    for it in items:
        p = it["项目名"] or "（无项目）"
        if p not in by_proj:
            order.append(p)
        by_proj[p].append(it)

    kept: list[list[dict]] = []
    leftovers: list[list[dict]] = []
    for p in order:
        grp = by_proj[p]
        total = sum(x["副本时长秒"] for x in grp)
        if total + 1e-6 >= MIN_SEC:
            kept.append(grp)
        else:
            leftovers.append(grp)

    merged: list[list[dict]] = []
    buf: list[dict] = []
    buf_dur = 0.0
    for grp in leftovers:
        buf.extend(grp)
        buf_dur += sum(x["副本时长秒"] for x in grp)
        if buf_dur + 1e-6 >= MIN_SEC:
            merged.append(buf)
            buf, buf_dur = [], 0.0
    if buf:
        if merged:
            merged[-1].extend(buf)
        elif kept:
            kept[-1].extend(buf)
        else:
            # 全部加起来仍不足 4 秒，留给主程序记过并跳过
            merged.append(buf)
    return kept + merged


def has_audio(path: Path) -> bool:
    cmd = [
        "ffprobe", "-v", "error", "-select_streams", "a",
        "-show_entries", "stream=codec_name", "-of", "csv=p=0",
        str(path),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0 and bool(r.stdout.strip())


def run_ffmpeg(cmd: list[str], label: str) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"{label} 失败: {r.stderr.strip() or r.stdout.strip() or r.returncode}")


def normalize_clip(src: Path, dest: Path) -> float:
    """统一 30fps / 720p / AAC，无音轨的补静音。不改原副本。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    vf = "fps=30,scale=-2:720,setsar=1,format=yuv420p"
    vopts = [
        "-vf", vf, "-r", "30",
        "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
        "-pix_fmt", "yuv420p",
    ]
    aopts = ["-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "44100"]
    if has_audio(src):
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(src),
            *vopts, *aopts, "-movflags", "+faststart", str(dest),
        ]
    else:
        dur = ffprobe_duration(src)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(src),
            "-f", "lavfi", "-t", f"{dur:.6f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            *vopts, "-map", "0:v:0", "-map", "1:a:0", *aopts, "-shortest",
            "-movflags", "+faststart", str(dest),
        ]
    run_ffmpeg(cmd, f"normalize {src.name}")
    return ffprobe_duration(dest)


def ffmpeg_concat(parts: list[Path], dest: Path, workdir: Path) -> list[float]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    workdir.mkdir(parents=True, exist_ok=True)
    norms = []
    durs = []
    for i, src in enumerate(parts, start=1):
        npath = workdir / f"{dest.stem}_p{i:02d}_{src.stem}.mp4"
        durs.append(normalize_clip(src, npath))
        norms.append(npath)
    lst = dest.with_suffix(".concat.txt")
    with lst.open("w", encoding="utf-8") as f:
        for pth in norms:
            s = str(pth).replace("\\", "/").replace("'", "'\\''")
            f.write(f"file '{s}'\n")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(lst),
        "-c", "copy", "-movflags", "+faststart",
        str(dest),
    ]
    try:
        run_ffmpeg(cmd, f"concat copy {dest.name}")
        method = "normalize+concat_copy"
    except RuntimeError:
        cmd2 = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "0", "-i", str(lst),
            "-c:v", "libx264", "-preset", "fast", "-profile:v", "high", "-level", "4.1",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-ac", "2", "-ar", "44100",
            "-movflags", "+faststart", str(dest),
        ]
        run_ffmpeg(cmd2, f"concat reencode {dest.name}")
        method = "normalize+concat_reencode"
    sidecar = dest.with_suffix(".method.txt")
    sidecar.write_text(method, encoding="utf-8")
    return durs


def main() -> int:
    STATS.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if CONCAT_LIST.exists() or CONCAT_JSON.exists():
        print(f"已存在拼接产出，不覆盖。请检查 {CONCAT_LIST} / {CONCAT_JSON}")
        return 2

    items = map_shorts()
    groups = group_shorts(items)
    started = now_str()
    rows = []
    json_groups = []
    skipped = []
    used = set()

    for i, grp in enumerate(groups, start=1):
        names = [x["副本文件名"] for x in grp]
        durs = [x["副本时长秒"] for x in grp]
        total = sum(durs)
        out_name = f"t12_concat_{i:02d}.mp4"
        out_path = OUT_DIR / out_name
        if total + 1e-6 < MIN_SEC:
            skipped.append({
                "计划合成文件名": out_name,
                "原因": f"合并后仍短于4秒（{total:.3f}秒），按规则跳过，不上传仍短于4秒的文件",
                "副本文件名": ",".join(names),
            })
            continue
        workdir = OUT_DIR / "tmp_norm"
        norm_durs = ffmpeg_concat([Path(x["副本路径"]) for x in grp], out_path, workdir)
        method = (out_path.with_suffix(".method.txt")).read_text(encoding="utf-8").strip()
        out_path.with_suffix(".method.txt").unlink(missing_ok=True)
        actual = ffprobe_duration(out_path)
        offset = 0.0
        members = []
        for x, d in zip(grp, norm_durs):
            members.append({
                **x,
                "归一化时长秒": round(d, 3),
                "合成内起始秒": round(offset, 3),
                "合成内结束秒": round(offset + d, 3),
            })
            offset += d
            used.add(x["副本文件名"])
        rec = {
            "合成文件名": out_name,
            "合成路径": str(out_path),
            "拼接条数": len(grp),
            "成员副本": ",".join(names),
            "成员原片ID": ",".join(x["原片ID"] for x in grp),
            "成员项目名": ",".join(dict.fromkeys(x["项目名"] for x in grp)),
            "清单合计秒": round(sum(float(x["清单时长秒"] or 0) for x in grp), 3),
            "副本合计秒": round(total, 3),
            "合成后时长秒": round(actual, 3),
            "拼接方式": method,
            "合成字节数": out_path.stat().st_size,
        }
        json_groups.append({**rec, "成员明细": members})
        # flatten rows for csv: one row per source clip
        for m in members:
            rows.append({
                "合成文件名": out_name,
                "合成路径": str(out_path),
                "合成后时长秒": rec["合成后时长秒"],
                "拼接方式": method,
                "拼接条数": len(grp),
                "副本文件名": m["副本文件名"],
                "副本时长秒": m["副本时长秒"],
                "归一化时长秒": m.get("归一化时长秒", ""),
                "合成内起始秒": m["合成内起始秒"],
                "合成内结束秒": m["合成内结束秒"],
                "原片ID": m["原片ID"],
                "项目名": m["项目名"],
                "主库相对路径": m["主库相对路径"],
                "为什么选它": m["为什么选它"],
                "清单时长秒": m["清单时长秒"],
            })

    fieldnames = [
        "合成文件名", "合成路径", "合成后时长秒", "拼接方式", "拼接条数",
        "副本文件名", "副本时长秒", "归一化时长秒", "合成内起始秒", "合成内结束秒",
        "原片ID", "项目名", "主库相对路径", "为什么选它", "清单时长秒",
    ]
    write_csv(CONCAT_LIST, rows, fieldnames)
    result = {
        "时间": now_str(),
        "开始": started,
        "短片总数": len(items),
        "合成文件数": len(json_groups),
        "纳入合成的短片数": len(used),
        "跳过": skipped,
        "合成后合计秒": round(sum(g["合成后时长秒"] for g in json_groups), 3),
        "合成后合计字节": sum(g["合成字节数"] for g in json_groups),
        "说明": "第一次用-c copy因时基不同时长错乱，本文件为统一30fps重编码后再拼接的版本。按项目名先组成组，已满4秒的组单独成文件；未满的按清单顺序再合并。未改原副本。旧的短片合成/拼接清单.csv保留备查，上传使用本重编码版本。",
        "分组": json_groups,
    }
    CONCAT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"短片 {len(items)} 条，合成 {len(json_groups)} 个文件，纳入 {len(used)} 条，跳过 {len(skipped)} 组")
    for g in json_groups:
        print(f"  {g['合成文件名']}: {g['拼接条数']}条, {g['合成后时长秒']}秒, {g['拼接方式']}, 成员={g['成员副本']}")
    for s in skipped:
        print(f"  跳过: {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
