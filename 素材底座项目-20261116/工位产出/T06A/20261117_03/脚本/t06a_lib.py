# -*- coding: utf-8 -*-
"""T06A 共用：路径、对照规则、映射。脚本从配置读地址，不写死共享盘以外的根。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

PROJECT_ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
CLIPLIB = PROJECT_ROOT / "片段库"
CONFIG_LIB = CLIPLIB / "配置" / "素材库.json"
CONFIG_PATHS = CLIPLIB / "配置" / "路径与库名.json"
T07_DIR = PROJECT_ROOT / "工位产出" / "T07" / "20261117_02"
T10_DIR = PROJECT_ROOT / "工位产出" / "T10" / "20261117_01"
SPLIT_POLICY = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation\split-policy.json")
YUANPIAN_SHA256_EXPECTED = "3891213ba53acf3dbff89dd594ff195a887ad4639b661c872e4be582a2813da4"

SEED = 20261117
SAMPLE_PER_FIELD = 30
SAMPLE_CAP = 150
BUDGET_CAP = 2000
MIN_COMPARE = 20
USABLE_AGREE_RATIO = 0.80

# 粗标「有效工序」映射到总纲 B1。T10 PROCESS_TO_GANG 未收录的取值在此补全并在回报里说明。
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

# 人确认的工序/动作叫法 → 画面类型代码（用于和粗标比）
HUMAN_PROCESS_TO_V = {
    "批刮摊料": "V05",
    "批刮覆盖": "V05",
    "批刮": "V05",
    "墙面基面上的批刮": "V05",
    "基面批刮": "V05",
    "铺料找平": "V05",
    "微陶泥批刮": "V05",
    "滚涂": "V06",
    "滚涂罩面": "V06",
    "罩面": "V06",
    "上罩面": "V06",
    "滚刷涂布": "V06",
    "搅拌配料": "V11",
    "取料": "V11",
    "纯取料": "V11",
    "材料桶展示": "V11",
    "微陶泥取料": "V11",
    "基层处理": "V23",
    "拆除": "V08",
    "铲除": "V07",
    "覆膜保护": "V09",
    "家具覆膜": "V09",
    "清洁": "V10",
    "抹布擦地面": "V10",
    "灶台清洁": "V10",
    "厨房台面清洁": "V10",
}

V_NAME = {
    "V01": "人物对镜头",
    "V02": "握手/与客户沟通",
    "V03": "团队上门/搬料搬物",
    "V04": "量房/水电/安装",
    "V05": "施工·批刮覆盖",
    "V06": "施工·滚涂",
    "V07": "铲修旧墙/旧顶",
    "V08": "拆砸/贴砖",
    "V09": "铺保护膜/贴胶带",
    "V10": "保洁/清扫",
    "V11": "材料桶",
    "V12": "旧房旧态",
    "V13": "成品空间",
    "V14": "旧→新同镜转场",
    "V15": "成品里的人",
    "V16": "手摸/手指成品",
    "V17": "成品日常清洁",
    "V18": "演示·喷水冲洗",
    "V19": "演示·弯折样板/揭薄层",
    "V20": "演示·刮擦/擦污",
    "V21": "老楼/城市外景",
    "V22": "其他",
    "V23": "施工现场·其他",
    "V24": "人物在现场",
}

# 词表别名（材料）
MATERIAL_ALIAS = {
    "水洗石": "微岩石",
    "金钢陶泥": "微陶泥",
    "金刚陶泥": "微陶泥",
    "金刚泥": "微陶泥",
}

T10_UNMAPPED_PROCESS = ("上罩面", "滚刷涂布", "铺料找平", "未据此确认", "刮刀批刮", "批刀批刮", "备料或展示", "滚涂（基层未明）", "罩面（工序）")

# 第一条线画面清单（T07 20261117_02），镜头数按原文抄入。
SHOT_LIST = [
    {"排序": 1, "画面类型": "施工·批刮覆盖", "代码": "V05", "被多少句话要": 43, "需要镜头数": 33.2},
    {"排序": 2, "画面类型": "成品空间", "代码": "V13", "被多少句话要": 34, "需要镜头数": 23.2},
    {"排序": 3, "画面类型": "人物对镜头", "代码": "V01", "被多少句话要": 17, "需要镜头数": 9.3},
    {"排序": 4, "画面类型": "握手/与客户沟通", "代码": "V02", "被多少句话要": 13, "需要镜头数": 8.5},
    {"排序": 5, "画面类型": "人物在现场", "代码": "V24", "被多少句话要": 17, "需要镜头数": 7.5},
    {"排序": 6, "画面类型": "拆砸/贴砖", "代码": "V08", "被多少句话要": 14, "需要镜头数": 6.3},
    {"排序": 7, "画面类型": "手摸/手指成品", "代码": "V16", "被多少句话要": 11, "需要镜头数": 4.2},
    {"排序": 8, "画面类型": "施工现场·其他", "代码": "V23", "被多少句话要": 6, "需要镜头数": 4.2},
    {"排序": 9, "画面类型": "施工·滚涂", "代码": "V06", "被多少句话要": 6, "需要镜头数": 3.8},
    {"排序": 10, "画面类型": "旧房旧态", "代码": "V12", "被多少句话要": 8, "需要镜头数": 3.8},
    {"排序": 11, "画面类型": "团队上门/搬料搬物", "代码": "V03", "被多少句话要": 8, "需要镜头数": 3.0},
    {"排序": 12, "画面类型": "其他", "代码": "V22", "被多少句话要": 11, "需要镜头数": 2.8},
    {"排序": 13, "画面类型": "材料桶", "代码": "V11", "被多少句话要": 8, "需要镜头数": 2.7},
    {"排序": 14, "画面类型": "成品里的人", "代码": "V15", "被多少句话要": 7, "需要镜头数": 2.7},
    {"排序": 15, "画面类型": "演示·喷水冲洗", "代码": "V18", "被多少句话要": 6, "需要镜头数": 2.7},
    {"排序": 16, "画面类型": "演示·刮擦/擦污", "代码": "V20", "被多少句话要": 6, "需要镜头数": 2.5},
    {"排序": 17, "画面类型": "演示·弯折样板/揭薄层", "代码": "V19", "被多少句话要": 4, "需要镜头数": 2.3},
    {"排序": 18, "画面类型": "量房/水电/安装", "代码": "V04", "被多少句话要": 2, "需要镜头数": 1.3},
    {"排序": 19, "画面类型": "旧→新同镜转场", "代码": "V14", "被多少句话要": 3, "需要镜头数": 1.2},
    {"排序": 20, "画面类型": "成品日常清洁", "代码": "V17", "被多少句话要": 5, "需要镜头数": 1.2},
    {"排序": 21, "画面类型": "保洁/清扫", "代码": "V10", "被多少句话要": 2, "需要镜头数": 0.5},
    {"排序": 22, "画面类型": "铲修旧墙/旧顶", "代码": "V07", "被多少句话要": 1, "需要镜头数": 0.5},
    {"排序": 23, "画面类型": "老楼/城市外景", "代码": "V21", "被多少句话要": 1, "需要镜头数": 0.3},
]


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_jsonl(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def write_jsonl(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm_slash(p) -> str:
    if not p:
        return ""
    return str(p).replace("\\", "/").strip().lower()


def overlap(a0, a1, b0, b1) -> bool:
    if a0 is None or a1 is None or b0 is None or b1 is None:
        return False
    try:
        a0, a1, b0, b1 = float(a0), float(a1), float(b0), float(b1)
    except (TypeError, ValueError):
        return False
    return a0 < b1 and b0 < a1


def has_times(rec) -> bool:
    return rec.get("起秒") is not None and rec.get("止秒") is not None


def as_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_material(name):
    if not name:
        return None
    s = str(name).strip()
    if not s or s in {"未辨明", "未定品名", "未确认", "None", "null"}:
        return None
    return MATERIAL_ALIAS.get(s, s)


def empty_process(val) -> bool:
    if val is None:
        return True
    s = str(val).strip()
    return s == "" or s in {"None", "null", "未据此确认", "待确认", "瓷釉改色或底漆"}


def effective_process(fields: dict):
    """有工序复核且不是空/未据此确认时，以复核为准；否则用工序。"""
    if not isinstance(fields, dict):
        return None
    review = fields.get("工序复核")
    raw = fields.get("工序")
    if not empty_process(review):
        return str(review).strip()
    if not empty_process(raw):
        return str(raw).strip()
    return None


def raw_process(fields: dict):
    if not isinstance(fields, dict):
        return None
    raw = fields.get("工序")
    if empty_process(raw):
        return None
    return str(raw).strip()


def process_to_v(name):
    if not name:
        return None
    return PROCESS_TO_V.get(str(name).strip())


def load_configs():
    lib = load_json(CONFIG_LIB)
    paths = load_json(CONFIG_PATHS)
    label_unc = paths["共享盘"]["标注库UNC"]
    return lib, paths, label_unc


def choose_out_dir() -> Path:
    base = PROJECT_ROOT / "工位产出" / "T06A"
    base.mkdir(parents=True, exist_ok=True)
    for i in range(1, 100):
        d = base / f"20261117_{i:02d}"
        if not d.exists():
            d.mkdir(parents=True)
            return d
        # 已存在且不空则换版本
        if not any(d.iterdir()):
            return d
    raise RuntimeError("无法分配产出目录")


def load_split_policy_dirs():
    data = load_json(SPLIT_POLICY)
    groups = data.get("exposed_directory_groups") or []
    # xiaoq/项目 或 baba/项目 → 用于匹配主库相对路径
    rules = []
    for g in groups:
        g = g.strip().replace("\\", "/")
        if "/" not in g:
            continue
        root, rest = g.split("/", 1)
        if root == "xiaoq":
            prefix = "史上最完整共享/拍摄/小区/" + rest
        elif root == "baba":
            prefix = "史上最完整共享/扒扒/" + rest
        elif root == "ceshi":
            prefix = "史上最完整共享/拍摄/测试/" + rest
        elif root == "aming":
            prefix = "史上最完整共享/拍摄/阿明/" + rest
        elif root == "jiaoban":
            prefix = "史上最完整共享/拍摄/搅拌/" + rest
        else:
            prefix = rest
        rules.append({"group": g, "prefix": norm_slash(prefix), "rest": rest})
    return rules


def path_in_split_policy(main_rel: str, rules) -> bool:
    p = norm_slash(main_rel)
    if not p:
        return False
    # 也允许不带「史上最完整共享/」的写法
    alts = [p]
    if p.startswith("史上最完整共享/"):
        alts.append(p[len("史上最完整共享/"):])
    for rule in rules:
        pref = rule["prefix"]
        rest = norm_slash(rule["rest"])
        for a in alts:
            if a == pref or a.startswith(pref + "/"):
                return True
            # 拍摄/小区/项目...
            if rest and (a == rest or a.startswith(rest + "/") or f"/{rest}/" in a or a.endswith("/" + rest)):
                # 必须是项目目录这一级，避免短名字误伤。要求 rest 出现在小区或扒扒之后。
                if f"/小区/{rest}" in a or a.startswith(f"拍摄/小区/{rest}") or f"/扒扒/{rest}" in a:
                    return True
    return False


def mosaic_path(coarse: dict, label_unc: str) -> str:
    """标注库抽帧拼图路径。分时段/施工镜头用 证据 相对路径；用途片段用 preview。"""
    fields = coarse.get("原字段") or {}
    ev = fields.get("证据") or fields.get("evidence")
    if ev and isinstance(ev, str) and ev.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        ev_norm = ev.replace("/", "\\")
        if ev_norm.startswith("\\\\") or ":" in ev_norm[:3]:
            return ev
        return str(Path(label_unc) / ev_norm)
    preview = fields.get("preview")
    if preview:
        return str(preview)
    return ""


def dedup_ok(yuan: dict) -> bool:
    """重复组里只留「进入选材」；没有重复组的算一条。"""
    d = yuan.get("重复组")
    if not d:
        return True
    if isinstance(d, dict):
        return d.get("角色") == "进入选材"
    return True


def load_bans(rows):
    file_ranges = []  # (norm path, start, end, rule)
    folders = []
    yuan_ids = set()
    for r in rows:
        rel = r.get("主库相对路径") or ""
        if r.get("定位到文件") and has_times(r):
            file_ranges.append({
                "path": norm_slash(rel),
                "start": as_float(r.get("起秒")),
                "end": as_float(r.get("止秒")),
                "规则ID": r.get("规则ID"),
                "原片ID": r.get("原片ID"),
            })
            if r.get("原片ID"):
                yuan_ids.add(r.get("原片ID"))
        elif rel:
            folders.append({
                "path": norm_slash(rel),
                "规则ID": r.get("规则ID"),
            })
    return file_ranges, folders, yuan_ids


def is_banned(main_rel, yuan_id, start, end, file_ranges, folders) -> bool:
    p = norm_slash(main_rel)
    for f in folders:
        pref = f["path"]
        if p == pref or (pref and p.startswith(pref + "/")):
            return True
    for fr in file_ranges:
        if yuan_id and fr.get("原片ID") and yuan_id == fr["原片ID"]:
            if start is None or end is None:
                # 整条原片级别：该文件有已知禁用时段，但任务是片段级计数时再比时间
                # 这里若没有片段时段，不算整条禁用（R09 只禁 2–6 秒）
                continue
            if overlap(start, end, fr["start"], fr["end"]):
                return True
        elif p and p == fr["path"]:
            if start is None or end is None:
                continue
            if overlap(start, end, fr["start"], fr["end"]):
                return True
    return False


def yuan_eligible(yuan: dict) -> bool:
    """竖屏、可用状态正常=可用、重复组只算进入选材。画幅空的不算竖屏。"""
    if not yuan:
        return False
    if yuan.get("画幅") != "竖":
        return False
    if yuan.get("可用状态") != "可用":
        return False
    if not dedup_ok(yuan):
        return False
    return True


def project_folder(yuan: dict) -> str:
    return (yuan or {}).get("项目名") or ""


def label_unc_from_config():
    _, paths, label_unc = load_configs()
    return label_unc
