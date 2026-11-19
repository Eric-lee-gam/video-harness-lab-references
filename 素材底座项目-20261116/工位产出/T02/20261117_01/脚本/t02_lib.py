# -*- coding: utf-8 -*-
"""T02 共用：路径、筛选、切段与抽帧辅助。口径与 T06A 03 的 t06a_lib 一致。"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
RULES_ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116")
T06A_SCRIPTS = PROJECT_ROOT / "工位产出" / "T06A" / "20261117_03" / "脚本"
OUT_DIR = PROJECT_ROOT / "工位产出" / "T02" / "20261117_01"
CLIPLIB = PROJECT_ROOT / "片段库"
SEED = 20261117
YUANPIAN_SHA256_EXPECTED = "3891213ba53acf3dbff89dd594ff195a887ad4639b661c872e4be582a2813da4"

SHANGHAI = timezone(timedelta(hours=8))

sys.path.insert(0, str(T06A_SCRIPTS))
import t06a_lib as t06a  # noqa: E402

TILE_W, TILE_H = 480, 854
MOSAIC_W, MOSAIC_H = TILE_W * 2, TILE_H * 2
PLACEHOLDER_TEXT = "无帧"
FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")
PYTHON = Path(r"C:\Python314\python.exe")

# 半命中/半补漏类
HALF_CLASSES = ("V05", "V23", "V06", "V11")

ALLOC_ORDER = [
    ("V05", 346),
    ("V13", 390),
    ("V01", 163),
    ("V02", 147),
    ("V24", 130),
    ("V08", 114),
    ("V16", 81),
    ("V23", 51),
    ("V06", 41),
    ("V12", 65),
    ("V03", 49),
    ("V22", 49),
    ("V11", 31),
    ("V15", 49),
    ("V18", 49),
    ("V20", 49),
    ("V19", 49),
    ("V04", 33),
    ("V14", 33),
    ("V17", 33),
    ("V10", 16),
    ("V07", 16),
    ("V21", 16),
]

SCOPE_LIBS = {"xiaoq", "ceshi", "aming", "jiaoban"}
MEIREN_MARK = "汉阳月印府(6.7全屋)/美女人设"
WATER_MARKS = ("水洗石", "微岩石")
JIABEILE_MARK = "嘉贝乐"
PASSWORD_MARK = "资料账号密码"


def now_shanghai() -> datetime:
    return datetime.now(SHANGHAI)


def now_iso() -> str:
    return now_shanghai().isoformat(timespec="seconds")


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj, indent=2):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    tmp.replace(path)


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    tmp.replace(path)


def iter_jsonl(path: Path):
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_slash(p) -> str:
    return t06a.norm_slash(p) if p else ""


def load_configs():
    lib, paths, label_unc = t06a.load_configs()
    share_root = paths["共享盘"]["主库UNC"]
    return lib, paths, label_unc, share_root


def fmt_sec(x) -> float:
    return round(float(x) + 1e-12, 2)


def segment_id(yuan_id: str, start: float, end: float) -> str:
    return f"{yuan_id}_{fmt_sec(start):.2f}_{fmt_sec(end):.2f}"


def logical_to_unc(logical: str, share_root: str) -> str:
    s = (logical or "").replace("\\", "/")
    if s.startswith("@shared/"):
        s = s[len("@shared/"):]
    elif s.startswith("@shared"):
        s = s[len("@shared"):].lstrip("/")
    return str(Path(share_root) / s.replace("/", "\\"))


def yuan_unc(yuan: dict, share_root: str) -> str:
    if yuan.get("逻辑路径"):
        return logical_to_unc(yuan["逻辑路径"], share_root)
    rel = (yuan.get("共享相对路径") or "").replace("/", "\\")
    return str(Path(share_root) / rel)


def main_rel_for_ban(yuan: dict) -> str:
    rel = yuan.get("共享相对路径") or ""
    rel = norm_slash(rel)
    if rel and not rel.startswith("史上最完整共享/"):
        rel = "史上最完整共享/" + rel.lstrip("/")
    return rel


def path_blob(yuan: dict) -> str:
    parts = [
        yuan.get("逻辑路径") or "",
        yuan.get("共享相对路径") or "",
        yuan.get("目录原名") or "",
        yuan.get("库内相对路径") or "",
        yuan.get("项目名") or "",
    ]
    return " / ".join(p.replace("\\", "/") for p in parts)


def is_meiren_dir(yuan: dict) -> bool:
    return MEIREN_MARK in path_blob(yuan)


def is_jiabeile(yuan: dict) -> bool:
    return JIABEILE_MARK in path_blob(yuan)


def is_waterstone_path(yuan: dict) -> bool:
    blob = path_blob(yuan)
    return any(m in blob for m in WATER_MARKS)


def has_dir_limit(yuan: dict) -> bool:
    return bool((yuan.get("目录限制原文") or "").strip())


def has_password_name(yuan: dict) -> bool:
    return PASSWORD_MARK in path_blob(yuan)


def load_cleanup_paths() -> set[str]:
    """T01 03 建议清理的 30 条逻辑路径（不含已读出的两条横屏超时）。"""
    src = PROJECT_ROOT / "工位产出" / "T01" / "20261117_03" / "32条时长或画幅缺口清单.json"
    keep_ok_timeout = {
        "@shared/拍摄/小区/南湖一厨一卫/26916_小区场景.MOV",
        "@shared/拍摄/小区/武昌沙湖小区 看房量尺/32303_小区场景.MOV",
    }
    paths = set()
    data = load_json(src)
    rows = data if isinstance(data, list) else data.get("记录") or data.get("行") or []
    for r in rows:
        if not isinstance(r, dict):
            continue
        logical = (r.get("逻辑路径") or "").replace("\\", "/").strip().strip("`")
        kind = str(r.get("分类") or "")
        if kind in {"moov缺失", "蔡甸小文件"} and logical:
            paths.add(logical)
    return paths


def load_waterstone_ids(facts, coarse) -> set[str]:
    ids = set()
    marks = WATER_MARKS

    def hit(obj) -> bool:
        return any(m in json.dumps(obj, ensure_ascii=False) for m in marks)

    for r in facts:
        if hit(r) and r.get("原片ID"):
            ids.add(r["原片ID"])
    for r in coarse:
        fields = r.get("原字段") or {}
        mat = fields.get("材料类目") or fields.get("material") or r.get("材料")
        text = json.dumps(mat, ensure_ascii=False) if mat is not None else ""
        if any(m in text for m in marks) and r.get("原片ID"):
            ids.add(r["原片ID"])
    return ids


def extra_exclude_reason(yuan: dict, cleanup: set[str], water_ids: set[str]) -> str | None:
    if not yuan:
        return "无原片"
    logical = (yuan.get("逻辑路径") or "").replace("\\", "/")
    if logical in cleanup:
        return "T01建议清理"
    if has_dir_limit(yuan):
        return "限制目录"
    if is_jiabeile(yuan):
        return "嘉贝乐相关目录"
    if is_meiren_dir(yuan):
        return "美女人设禁用"
    if is_waterstone_path(yuan) or (yuan.get("原片ID") in water_ids):
        return "水洗石素材"
    if has_password_name(yuan):
        return "资料账号密码文件"
    if yuan.get("库ID") not in SCOPE_LIBS:
        return "范围外目录"
    rel = (yuan.get("共享相对路径") or "").replace("\\", "/")
    if rel.startswith("扒扒/") or "/扒扒/" in rel:
        return "扒扒库"
    if yuan.get("时长") is None:
        return "无时长"
    try:
        if float(yuan.get("时长") or 0) < 1.0:
            return "时长不足1秒"
    except (TypeError, ValueError):
        return "时长无效"
    return None


def is_selectable(yuan: dict, data: dict) -> bool:
    if not t06a.yuan_eligible(yuan):
        return False
    if extra_exclude_reason(yuan, data["cleanup"], data["water_ids"]):
        return False
    if t06a.is_banned(
        main_rel_for_ban(yuan),
        yuan.get("原片ID"),
        None,
        None,
        data["file_ranges"],
        data["folders"],
    ):
        # 文件夹级禁用在此处拦截；仅时段禁用（无整段时段）不在原片级拦截
        # 但美女人设已按整夹排除。R09 只禁 2-6 秒，原片级 start/end 为空时 is_banned 不会因 file_ranges 拦截。
        return False
    return True


def segment_banned(yuan: dict, start, end, data: dict) -> bool:
    return t06a.is_banned(
        main_rel_for_ban(yuan),
        yuan.get("原片ID"),
        start,
        end,
        data["file_ranges"],
        data["folders"],
    )


def rotation_vf(angle) -> str:
    """按原片表旋转角度转正（配合 ffmpeg -noautorotate）。"""
    if angle is None or angle == "":
        return ""
    try:
        a = int(round(float(angle))) % 360
    except (TypeError, ValueError):
        return ""
    if a < 0:
        a += 360
    if a == 0:
        return ""
    if a == 90:
        return "transpose=1"
    if a == 180:
        return "hflip,vflip"
    if a == 270:
        return "transpose=2"
    # 非直角，少见；用 rotate 弧度，并以转后裁切为 0（pad 后续处理）
    rad = float(angle) * 3.141592653589793 / 180.0
    return f"rotate={rad}:c=0x808080"


def tile_vf(angle) -> str:
    parts = []
    rot = rotation_vf(angle)
    if rot:
        parts.append(rot)
    parts.append(
        f"scale={TILE_W}:{TILE_H}:force_original_aspect_ratio=decrease,"
        f"pad={TILE_W}:{TILE_H}:(ow-iw)/2:(oh-ih)/2:color=0x808080"
    )
    return ",".join(parts)


def split_half(n: int) -> tuple[int, int]:
    """多出来的 1 段给现成命中（复核）。"""
    hit = (n + 1) // 2
    return hit, n - hit


def folder_cap(n: int) -> int:
    cap = int(n * 0.2)
    return cap if cap >= 1 else 1


def stratified_pick(candidates, n, rng, folder_fn, id_fn):
    """按项目文件夹分层抽取 n 条，单夹不超过两成；不够则逐步放宽并记录。"""
    by_f = defaultdict(list)
    for c in candidates:
        by_f[folder_fn(c)].append(c)
    folders = sorted(by_f.keys(), key=lambda x: (x is None, str(x)))
    for f in folders:
        by_f[f].sort(key=id_fn)
        rng.shuffle(by_f[f])

    orig_cap = folder_cap(n)
    cap = orig_cap
    relaxed = False

    def try_cap(cap_now):
        order = folders[:]
        rng.shuffle(order)
        picked = []
        used = {f: 0 for f in folders}
        idxs = {f: 0 for f in folders}
        progressed = True
        while len(picked) < n and progressed:
            progressed = False
            for f in order:
                if len(picked) >= n:
                    break
                if used[f] >= cap_now:
                    continue
                i = idxs[f]
                if i < len(by_f[f]):
                    picked.append(by_f[f][i])
                    idxs[f] = i + 1
                    used[f] += 1
                    progressed = True
        return picked, used

    picked, used = try_cap(cap)
    while len(picked) < n and cap < n:
        cap += 1
        relaxed = True
        picked, used = try_cap(cap)

    # 若放宽后仍不够，再无视上限把剩余按稳定顺序补上
    overflow = False
    if len(picked) < n:
        overflow = True
        have = {id_fn(x) for x in picked}
        rest = [c for c in candidates if id_fn(c) not in have]
        rest.sort(key=id_fn)
        rng.shuffle(rest)
        for c in rest:
            picked.append(c)
            if len(picked) >= n:
                break

    return picked, {
        "建议上限": orig_cap,
        "实际上限": cap,
        "放宽": relaxed,
        "无视上限补齐": overflow,
        "抽到": len(picked),
        "目标": n,
        "候选": len(candidates),
        "项目文件夹数": len(folders),
        "各夹条数": {f: used.get(f, 0) for f in folders if used.get(f, 0)},
    }


def load_all():
    lib, paths, label_unc, share_root = load_configs()
    yuan_path = CLIPLIB / "原片表.jsonl"
    sha = sha256_file(yuan_path)
    yuans = list(iter_jsonl(yuan_path))
    by_id = {}
    for y in yuans:
        if y.get("原片ID"):
            by_id[y["原片ID"]] = y
    facts = list(iter_jsonl(CLIPLIB / "事实层.jsonl"))
    coarse = list(iter_jsonl(CLIPLIB / "粗标层.jsonl"))
    bans = list(iter_jsonl(CLIPLIB / "禁用表.jsonl"))
    file_ranges, folders, ban_ids = t06a.load_bans(bans)
    cleanup = load_cleanup_paths()
    water_ids = load_waterstone_ids(facts, coarse)
    data = {
        "lib": lib,
        "paths": paths,
        "label_unc": label_unc,
        "share_root": share_root,
        "yuans": yuans,
        "by_id": by_id,
        "facts": facts,
        "coarse": coarse,
        "bans": bans,
        "file_ranges": file_ranges,
        "folders": folders,
        "ban_ids": ban_ids,
        "cleanup": cleanup,
        "water_ids": water_ids,
        "yuan_sha256": sha,
        "yuan_sha_ok": sha == YUANPIAN_SHA256_EXPECTED,
    }
    return data


def get_yuan(data, rec) -> dict | None:
    yid = rec.get("原片ID") if rec else None
    if yid and yid in data["by_id"]:
        return data["by_id"][yid]
    return None


def build_cut_index(data):
    """每个原片的切点：分时段起止、施工镜头起止、change_time。"""
    cuts = defaultdict(set)
    timelines = defaultdict(list)
    shots = defaultdict(list)
    for c in data["coarse"]:
        yid = c.get("原片ID")
        if not yid:
            continue
        if c.get("范围") != "范围内":
            continue
        st = t06a.as_float(c.get("起秒"))
        en = t06a.as_float(c.get("止秒"))
        kind = c.get("记录种类")
        if st is not None:
            cuts[yid].add(st)
        if en is not None:
            cuts[yid].add(en)
        fields = c.get("原字段") or {}
        ct = t06a.as_float(fields.get("change_time"))
        if ct is not None:
            cuts[yid].add(ct)
        item = {
            "start": st,
            "end": en,
            "粗标编号": c.get("粗标编号"),
            "记录种类": kind,
            "coarse": c,
        }
        if kind == "分时段" and st is not None and en is not None:
            timelines[yid].append(item)
        elif kind == "施工镜头" and st is not None and en is not None:
            shots[yid].append(item)
    for yid in timelines:
        timelines[yid].sort(key=lambda x: (x["start"], x["end"]))
    for yid in shots:
        shots[yid].sort(key=lambda x: (x["start"], x["end"]))
    data["cuts"] = cuts
    data["timelines"] = timelines
    data["shots"] = shots
    return data


def split_window(start: float, end: float, cut_points) -> list[tuple[float, float]]:
    """在 (start, end) 内的切点处断开，返回子区间。"""
    pts = [start, end]
    for p in cut_points:
        if p is None:
            continue
        if start + 1e-6 < p < end - 1e-6:
            pts.append(float(p))
    pts = sorted(set(fmt_sec(p) for p in pts))
    # 恢复精确的端点
    pts[0] = fmt_sec(start)
    pts[-1] = fmt_sec(end)
    segs = []
    for a, b in zip(pts, pts[1:]):
        if b - a >= 0.20:
            segs.append((a, b))
    return segs


def cap_over_4(pieces: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """超过 4 秒的再按 4 秒切开。"""
    out = []
    for a, b in pieces:
        d = b - a
        if d <= 4.0 + 1e-9:
            out.append((a, b))
            continue
        t = a
        while t < b - 1e-9:
            u = min(fmt_sec(t + 4.0), b)
            if u - t >= 0.20:
                out.append((fmt_sec(t), fmt_sec(u)))
            t = u
    return out


def choose_piece(pieces: list[tuple[float, float]], min_len=2.0) -> tuple[float, float] | None:
    """取第一段像样的（优先 >=2 秒，否则最长的一段）。"""
    if not pieces:
        return None
    for a, b in pieces:
        if b - a >= min_len - 1e-9:
            return (fmt_sec(a), fmt_sec(b))
    a, b = max(pieces, key=lambda x: x[1] - x[0])
    return (fmt_sec(a), fmt_sec(b))


def cut_from_window(data, yuan, start, end) -> tuple[float, float, dict]:
    """把 [start,end] 按切点与 4 秒上限切开，取一段可抽帧的子区间。"""
    dur = t06a.as_float(yuan.get("时长")) or end
    start = max(0.0, float(start))
    end = min(float(end), float(dur))
    if end <= start:
        return None, None, {"原因": "窗口无效"}
    yid = yuan.get("原片ID")
    cuts = data["cuts"].get(yid, set())
    pieces = cap_over_4(split_window(start, end, cuts))
    piece = choose_piece(pieces)
    info = {
        "源窗口": [fmt_sec(start), fmt_sec(end)],
        "切点内点数": sum(1 for p in cuts if start < p < end),
        "切开后段数": len(pieces),
        "选用": list(piece) if piece else None,
    }
    if not piece:
        return None, None, info
    a, b = piece
    # 抽 4 帧需要约 3 秒跨度；若长于 4 秒已切开。若长于 3 且不超过 4，保留原长。
    return a, b, info


def cut_from_yuan(data, yuan) -> tuple[float, float, dict]:
    """原片表分层随机：优先用现成分时段，否则从原片开头切。"""
    yid = yuan.get("原片ID")
    dur = t06a.as_float(yuan.get("时长")) or 0.0
    tls = data["timelines"].get(yid) or []
    # 取第一段时长像样的分时段
    for item in tls:
        st, en = item["start"], item["end"]
        if st is None or en is None:
            continue
        if en - st < 0.8:
            continue
        a, b, info = cut_from_window(data, yuan, st, en)
        if a is not None:
            info["来源时段"] = item["粗标编号"]
            info["记录种类"] = "分时段"
            return a, b, info
    a, b, info = cut_from_window(data, yuan, 0.0, dur)
    info["来源时段"] = None
    info["记录种类"] = "原片整段"
    return a, b, info


def frame_times(start: float, end: float, duration: float | None) -> list[float]:
    times = []
    for i in range(4):
        t = start + i * 1.0
        limit = end
        if duration is not None:
            limit = min(limit, duration)
        if t < limit - 1e-3:
            times.append(round(t, 3))
    return times


def anonymous_name(index: int) -> str:
    return f"m{index:04d}.jpg"
