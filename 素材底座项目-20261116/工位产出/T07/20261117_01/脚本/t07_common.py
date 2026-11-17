# -*- coding: utf-8 -*-
"""T07 shared helpers: format conditions, 词表层, 总纲字段名."""
from __future__ import annotations

# 总纲 v0.2 画面类型代码
V = {
    "人物对镜头": "V01",
    "人物在现场": "V24",
    "握手/与客户沟通": "V02",
    "团队上门/搬料搬物": "V03",
    "量房/水电/安装": "V04",
    "施工·批刮覆盖": "V05",
    "施工·滚涂": "V06",
    "施工现场·其他": "V23",
    "铲修旧墙/旧顶": "V07",
    "拆砸/贴砖": "V08",
    "铺保护膜/贴胶带": "V09",
    "保洁/清扫": "V10",
    "材料桶": "V11",
    "旧房旧态": "V12",
    "成品空间": "V13",
    "旧→新同镜转场": "V14",
    "成品里的人": "V15",
    "手摸/手指成品": "V16",
    "成品日常清洁": "V17",
    "演示·喷水冲洗": "V18",
    "演示·弯折样板/揭薄层": "V19",
    "演示·刮擦/擦污": "V20",
    "老楼/城市外景": "V21",
    "其他": "V22",
    "其他（模糊画面、叠大字等）": "V22",
}

# 统一别名（选镜单写法 -> 总纲标准名）
TYPE_ALIAS = {
    "拆砸/贴砖（传统做法）": "拆砸/贴砖",
    "成品空间（空镜）": "成品空间",
    "保洁/清扫（施工前后）": "保洁/清扫",
    "材料桶（取料/搅拌/桶特写）": "材料桶",
}

LAYER_INDUSTRY = "行业通用"
LAYER_CAT = "品类专有"
LAYER_CO = "企业专有"
LAYER_TODO = "待定"

# 字段默认词表层
FIELD_LAYER = {
    "画幅": LAYER_CO,  # 镜序只用竖屏，是本企业制作规范
    "可用状态": LAYER_CO,
    "他方品牌包装入镜": LAYER_CO,
    "画面类型": LAYER_CAT,
    "主动作": LAYER_CAT,
    "材料类目": LAYER_CO,  # 微陶泥等为本企业产品名
    "材料依据等级": LAYER_CO,
    "身份": LAYER_CO,
    "身份来源": LAYER_CO,
    "基层": LAYER_CAT,
    "批刮的遍数": LAYER_CAT,
    "空间": LAYER_INDUSTRY,
    "部位": LAYER_INDUSTRY,
    "阶段": LAYER_INDUSTRY,
    "人数": LAYER_INDUSTRY,
    "朝向": LAYER_INDUSTRY,
    "角色": LAYER_INDUSTRY,
    "景别": LAYER_INDUSTRY,
    "可用时长": LAYER_INDUSTRY,
    "动作完整": LAYER_INDUSTRY,
    "举证等级": LAYER_CAT,
    "指定目录": LAYER_CO,
    "指定主库编号": LAYER_CO,
    "禁用主库编号": LAYER_CO,
    "城市": LAYER_CO,  # 账号配置，总纲城市字段基本空缺
    "转场镜头": LAYER_INDUSTRY,
    "视角": LAYER_INDUSTRY,
}


def vcode(name: str) -> str:
    name = TYPE_ALIAS.get(name, name)
    code = V.get(name)
    return f"{name}（{code}）" if code else name


def item(field, value, layer=None, note=""):
    return {
        "field": field,
        "value": value,
        "layer": layer or FIELD_LAYER.get(field, LAYER_TODO),
        "note": note,
    }


def fmt_items(items) -> str:
    if not items:
        return "（无）"
    lines = []
    for it in items:
        note = f"；{it['note']}" if it.get("note") else ""
        lines.append(f"- {it['field']}：{it['value']}（词表：{it['layer']}{note}）")
    return "\n".join(lines)


def layer_index(items_lists) -> str:
    """Dedup field+layer for the 词表层 column."""
    seen = []
    for items in items_lists:
        for it in items or []:
            key = (it["field"], it["layer"])
            if key not in seen:
                seen.append(key)
    if not seen:
        return "（无）"
    return "；".join(f"{f}={ly}" for f, ly in seen)


COMMON_MUST = [
    item("画幅", "竖", note="镜序只用原生 9:16，总纲 C1"),
    item("可用状态", "可用", note="总纲 A3；需打码的先打码再进入选材"),
    item("他方品牌包装入镜", "无", note="总纲 C3；含嘉贝乐产品包装的片段不用"),
]

COMMON_FORBID = [
    item("他方品牌包装入镜", "有则禁用"),
    item("材料类目", "第一条线微陶泥工艺句不得使用微岩石/水洗石素材", note="已定口径；水洗石是微岩石别名"),
    item("来源", "除对照表写明的指定目录外，本批第一条线不把扒扒库当默认检索范围", note="共同约定 v0.4；指定防水演示除外"),
]


ACTION_NOTE_PI = "批刮口径与镜序一致：抹刀或刮板接触施工基面铺展或刮平材料。工具在桶里算取料，不算批刮。取料、蘸料分开记。"
ACTION_NOTE_ROLL = "滚涂必须看见滚筒接触表面滚动。刷子刷涂不是滚涂，主动作应标刷涂；画面类型暂归施工·滚涂（V06），给镜序时按主动作给。"
ACTION_NOTE_FETCH = "取料：从桶、托板或另一工具取得或转移材料。滚筒蘸料单独记为蘸料，不当作纯取料。"

WATERPROOF_SRC = "扒扒/1卫生间/卫生间微陶泥防水"
ABRASION_OK = "00428、00429、00430"
ABRASION_BAN = "00434"