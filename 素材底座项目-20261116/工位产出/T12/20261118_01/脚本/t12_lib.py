# -*- coding: utf-8 -*-
"""T12 共用：路径、原片表、排除规则、转正滤镜。不调用任何外部接口。"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

PROJECT_ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
RULES_ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116")
SHARE_ROOT = Path(r"\\192.168.110.36\共享本公司\史上最完整共享")
OUT_ROOT = PROJECT_ROOT / "工位产出" / "T12" / "20261118_01"

SEED = 20261118
TARGET_MIN_SEC = 2.5 * 3600
TARGET_MAX_SEC = 3.5 * 3600
TARGET_AIM_SEC = 3.15 * 3600
MAX_COPY_BYTES = int(2.5 * 1024 * 1024 * 1024)
SHORT_LIMIT_SEC = 4.0

# T07 20261117_02 画面清单（20261117_05 未另存该清单，类型与 02 一致）
T07_PICTURE_TYPES = [
    ("V05", "施工·批刮覆盖"),
    ("V13", "成品空间"),
    ("V01", "人物对镜头"),
    ("V02", "握手/与客户沟通"),
    ("V24", "人物在现场"),
    ("V08", "拆砸/贴砖"),
    ("V16", "手摸/手指成品"),
    ("V23", "施工现场·其他"),
    ("V06", "施工·滚涂"),
    ("V12", "旧房旧态"),
    ("V03", "团队上门/搬料搬物"),
    ("V22", "其他"),
    ("V11", "材料桶"),
    ("V15", "成品里的人"),
    ("V18", "演示·喷水冲洗"),
    ("V20", "演示·刮擦/擦污"),
    ("V19", "演示·弯折样板/揭薄层"),
    ("V04", "量房/水电/安装"),
    ("V14", "旧→新同镜转场"),
    ("V17", "成品日常清洁"),
    ("V10", "保洁/清扫"),
    ("V07", "铲修旧墙/旧顶"),
    ("V21", "老楼/城市外景"),
]

# 粗标层里能直接对上画面类型的 B1 标签（其余类粗标层没有对应画面类型标签）
B1_TAG_TO_CODE = {
    "B1 画面类型=V05 施工·批刮覆盖": "V05",
    "B1 画面类型=V06 施工·滚涂": "V06",
    "B1 画面类型=V11 材料桶（取料/搅拌/桶特写）": "V11",
    "B1 画面类型=V23 施工现场·其他": "V23",
}


def norm_path(p) -> str:
    if not p:
        return ""
    s = str(p).replace("/", "\\")
    s = s.replace("@shared\\", "史上最完整共享\\")
    if s.startswith("\\") and not s.startswith("\\\\"):
        s = s.lstrip("\\")
    if s.lower().startswith("拍摄\\"):
        s = "史上最完整共享\\" + s
    while "\\\\" in s and not s.startswith("\\\\"):
        s = s.replace("\\\\", "\\")
    return s


def norm_key(p) -> str:
    return norm_path(p).lower()


def master_relpath(rec: dict) -> str:
    """统一写成 史上最完整共享\\拍摄\\..."""
    if rec.get("共享相对路径"):
        rel = rec["共享相对路径"].replace("/", "\\")
        if rel.lower().startswith("史上最完整共享\\"):
            return rel
        return "史上最完整共享\\" + rel
    if rec.get("逻辑路径"):
        return norm_path(rec["逻辑路径"])
    return rec.get("主库相对路径") or ""


def share_path(rec: dict) -> Path:
    rel = rec.get("共享相对路径") or ""
    rel = rel.replace("/", "\\")
    if rel.lower().startswith("史上最完整共享\\"):
        rel = rel[len("史上最完整共享\\"):]
    return SHARE_ROOT / rel


def is_under_xiaoqu_or_test(rec: dict) -> bool:
    rel = (rec.get("共享相对路径") or "").replace("\\", "/")
    return rel.startswith("拍摄/小区/") or rel.startswith("拍摄/测试/") or rel.startswith("拍摄/小区\\") or rel.startswith("拍摄/测试\\")


def top_dir(rec: dict) -> str:
    rel = (rec.get("共享相对路径") or "").replace("\\", "/")
    parts = rel.split("/")
    if len(parts) >= 2 and parts[0] == "拍摄":
        return parts[1]
    return ""


def looks_like_file_path(p: str) -> bool:
    if not p:
        return False
    name = norm_path(p).split("\\")[-1]
    return "." in name


def rotation_vf(angle) -> str:
    """与 T02 t02_lib.rotation_vf 一致：配合 ffmpeg -noautorotate。"""
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
    rad = float(angle) * 3.141592653589793 / 180.0
    return f"rotate={rad}:c=0x808080"


def scale_vf_720p() -> str:
    """转正后短边缩放到 720，保持比例，偶数边。不补边。"""
    return (
        "scale="
        "w='if(gte(iw\\,ih)\\,min(1280\\,iw)\\,min(720\\,if(gte(ih\\,720)\\,720\\,iw)))':"
        "h='if(gte(ih\\,iw)\\,min(1280\\,if(gte(iw\\,720)\\,trunc(ih*720/iw/2)*2\\,ih))\\,min(720\\,ih))':"
        "force_original_aspect_ratio=decrease:"
        "force_divisible_by=2"
    )


def scale_vf_720p_simple() -> str:
    """竖屏以宽=720 为 720p；横屏以高=720。已排除横屏，主要走竖屏分支。"""
    return (
        "scale="
        "if(gte(ih\\,iw)\\,720\\,trunc(iw*720/ih/2)*2):"
        "if(gte(ih\\,iw)\\,trunc(ih*720/iw/2)*2\\,720)"
    )


def transcode_vf(angle) -> str:
    parts = []
    rot = rotation_vf(angle)
    if rot:
        parts.append(rot)
    parts.append(scale_vf_720p_simple())
    parts.append("setsar=1")
    parts.append("format=yuv420p")
    return ",".join(parts)


# --------------- 外传风险与排除 ---------------

RISK_PATH_RULES = [
    (re.compile(r"嘉贝乐"), "目录或文件名含嘉贝乐，不该外传"),
    (re.compile(r"美女人设"), "目录含美女人设（含禁用人物出镜素材），不该外传"),
    (re.compile(r"阿姨不要用"), "目录带限制字样「阿姨不要用」"),
    (re.compile(r"用不太上的"), "目录带限制字样「用不太上的」"),
    (re.compile(r"业主露脸"), "目录含业主露脸（客户的脸，需打码），不该外传"),
    (re.compile(r"需要打码"), "目录带限制字样「需要打码」"),
    (re.compile(r"[（(]打码[）)]"), "目录带限制字样「打码」"),
    (re.compile(r"\\客户_|/客户_|_客户_|客户_"), "文件名含客户标识，可能含客户的脸，不该外传"),
]


def path_risk_reasons(master_rel: str, rec: dict | None = None) -> list[str]:
    reasons = []
    text = norm_path(master_rel)
    for pat, why in RISK_PATH_RULES:
        if pat.search(text):
            reasons.append(why)
    if rec:
        limit = (rec.get("目录限制原文") or "").strip()
        if limit:
            msg = f"原片表目录限制原文为「{limit}」"
            if msg not in reasons and not any(limit in r for r in reasons):
                reasons.append(msg)
        status = rec.get("可用状态")
        if status == "需打码后可用":
            reasons.append("可用状态为需打码后可用（客户的脸/需打码），不该外传")
    return reasons


def load_jsonl(path: Path):
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_yuanpian() -> tuple[dict, dict]:
    by_id = {}
    by_path = {}
    for rec in load_jsonl(PROJECT_ROOT / "片段库" / "原片表.jsonl"):
        by_id[rec["原片ID"]] = rec
        rel = master_relpath(rec)
        if rel:
            by_path[norm_key(rel)] = rec
        if rec.get("共享相对路径"):
            by_path[norm_key(rec["共享相对路径"])] = rec
        if rec.get("逻辑路径"):
            by_path[norm_key(rec["逻辑路径"])] = rec
    return by_id, by_path


def resolve_yuan(by_id: dict, by_path: dict, yuan_id=None, path=None):
    if yuan_id and yuan_id in by_id:
        return by_id[yuan_id]
    if path:
        k = norm_key(path)
        if k in by_path:
            return by_path[k]
        # try adding / stripping prefix
        if not k.startswith("史上最完整共享\\"):
            k2 = norm_key("史上最完整共享\\" + norm_path(path))
            if k2 in by_path:
                return by_path[k2]
    return None


# 这两条超时后已读出，本应因横屏被排除，不当作 T01 清理对象
TIMEOUT_RECOVERED_IDS = {"25a4ad80490d5c2b", "2ae8d45b0f4efe92"}


def load_unusable_30() -> tuple[set, set, list]:
    """20 条 moov 缺失 + 10 条蔡甸小文件。不含 2 条已恢复的超时横屏。"""
    iso_path = PROJECT_ROOT / "工位产出" / "T01" / "20261117_04_隔离" / "隔离结果.json"
    data = json.loads(iso_path.read_text(encoding="utf-8"))
    ids, paths, recs = set(), set(), []
    for r in data["records"]:
        cat = r.get("分类") or ""
        oid = str(r.get("原片ID") or "")
        if oid in TIMEOUT_RECOVERED_IDS:
            continue
        if cat not in ("moov缺失", "蔡甸小文件"):
            continue
        if oid:
            ids.add(oid)
            if oid.startswith("N") and len(oid) == 17:
                ids.add(oid[1:])
            elif len(oid) == 16:
                ids.add("N" + oid)
        if r.get("共享相对路径"):
            paths.add(norm_key("史上最完整共享\\" + r["共享相对路径"].replace("/", "\\")))
        if r.get("逻辑路径"):
            paths.add(norm_key(r["逻辑路径"]))
        recs.append(r)
    if len(recs) != 30:
        raise RuntimeError(f"隔离结果里 moov缺失+蔡甸小文件 应为 30 条，实际 {len(recs)}")
    return ids, paths, recs


def load_ban_rules() -> list[dict]:
    return load_jsonl(PROJECT_ROOT / "片段库" / "禁用表.jsonl")


def ban_reasons(rec: dict, master_rel: str, ban_rules: list[dict]) -> list[str]:
    reasons = []
    rel_k = norm_key(master_rel)
    oid = rec.get("原片ID")
    for b in ban_rules:
        bpath = norm_path(b.get("主库相对路径") or "")
        if not bpath:
            continue
        bk = norm_key(bpath)
        level = b.get("确认级别") or b.get("类型") or ""
        folder_level = ("文件夹" in str(level)) or (b.get("原片ID") in (None, ""))
        if folder_level:
            prefix = bk if bk.endswith("\\") else bk + "\\"
            if rel_k == bk or rel_k.startswith(prefix):
                reasons.append(f"命中禁用表（{b.get('规则ID') or b.get('类型')}）：{bpath}")
        else:
            if (b.get("原片ID") and oid and b["原片ID"] == oid) or rel_k == bk:
                reasons.append(f"命中禁用表（{b.get('规则ID') or b.get('类型')}）：{bpath}")
    return reasons


def exclude_reasons(rec: dict, unusable_ids: set, unusable_paths: set, ban_rules: list[dict]) -> list[str]:
    """硬排除（选材规则）+ 外传风险。返回原因列表，空表示可入选。"""
    reasons = []
    master = master_relpath(rec)
    oid = rec.get("原片ID")
    if oid in unusable_ids or norm_key(master) in unusable_paths:
        reasons.append("T01已确认不能用（20条moov缺失或10条蔡甸3–8KB）")
    status = rec.get("可用状态")
    if status != "可用":
        reasons.append(f"可用状态不正常：{status}")
    aspect = rec.get("画幅")
    if aspect != "竖":
        reasons.append(f"画幅不是竖（当前：{aspect!r}）")
    dup = rec.get("重复组") or {}
    if isinstance(dup, dict) and dup.get("角色") == "组内副本":
        reasons.append(f"重复组副本（组号{dup.get('组号')}）")
    if rec.get("时长") in (None, ""):
        reasons.append("原片表无时长")
    reasons.extend(ban_reasons(rec, master, ban_rules))
    reasons.extend(path_risk_reasons(master, rec))
    # 去重保持顺序
    seen = set()
    out = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def dur_of(rec: dict) -> float:
    try:
        return float(rec.get("时长") or 0)
    except (TypeError, ValueError):
        return 0.0


def fmt_hms(sec: float) -> str:
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - h * 3600 - m * 60
    return f"{h}:{m:02d}:{s:05.2f}"


def fmt_hours(sec: float) -> str:
    return f"{sec/3600:.4f} 小时（{fmt_hms(sec)}，{sec:.3f} 秒）"
