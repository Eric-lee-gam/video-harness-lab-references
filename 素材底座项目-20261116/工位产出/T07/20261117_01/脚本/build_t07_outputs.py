# -*- coding: utf-8 -*-
"""Render all T07 deliverables into 工位产出/T07/20261117_01/."""
from __future__ import annotations
import json, csv, sys, re
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
READS = OUT / "_reads"
sys.path.insert(0, str(HERE))

from t07_common import fmt_items, layer_index, vcode, TYPE_ALIAS, V
from t07_sentences import RECORDS, get
from t07_categories import CATS

SHOTS = json.loads((READS / "选镜单_结构化.json").read_text(encoding="utf-8"))
CATJSON = json.loads((READS / "类别_结构化.json").read_text(encoding="utf-8"))

SET_NAME = {
    50: "套A 第50段（6条爆款，垂直陶泥）",
    46: "套B 第46段（3条爆款，垂直陶泥）",
    71: "套C 第71段（3条爆款，垂直陶泥；近版本第97、109段）",
    30: "套D 第30段（2条爆款，同城标签）",
    63: "套E-1 第63段（2条爆款；与第74段为同一套不同版本）",
    74: "套E-2 第74段（1条爆款；第63段的另一版本，工期为三天）",
    54: "套F 第54段（1条爆款，例子不是规律；近版本第106段）",
    62: "套G 第62段（1条爆款，例子不是规律；近版本第76段）",
    65: "套H 第65段（1条爆款，例子不是规律）",
}
# 8套：E 的两个版本仍逐句各记，但套数计 1
EIGHT_SETS = ["A第50段", "B第46段", "C第71段", "D第30段", "E第63/74段", "F第54段", "G第62段", "H第65段"]


def std_type(name: str) -> str:
    return TYPE_ALIAS.get(name, name)


def shots_md(sent) -> str:
    if sent.get("n_shots") is None:
        return sent.get("shot_raw") or "用这段的爆款都没说这句，无镜头统计"
    parts = []
    for it in sent.get("shot_types") or []:
        t = it["type"]
        c = it["count"]
        parts.append(f"{t} {c}" if c is not None else t)
    s = "、".join(parts) if parts else (sent.get("shot_raw") or "")
    if sent.get("shot_note"):
        s += "；" + sent["shot_note"]
    return s


def prefer_from_viral(sent) -> list:
    """把选镜单配的画面写进优先栏，带次数。"""
    from t07_common import item
    items = []
    nvid_note = ""
    rows = sent.get("shot_types") or []
    if not rows or sent.get("n_shots") is None:
        return [item("爆款实际配的画面", "无（用这段的爆款都没说这句）", layer="品类专有")]
    # sort by count desc
    rows = sorted(rows, key=lambda x: -(x["count"] or 0))
    desc = "、".join(f"{std_type(r['type'])} {r['count']}次" for r in rows)
    items.append(item("爆款实际配的画面（几条片子加在一起的镜头个数）", desc, layer="品类专有",
                      note="来自选镜单，AI 拆、未人工核对"))
    return items


def seconds_text(sent, rec) -> str:
    if rec.get("无爆款镜头") or sent.get("n_shots") is None:
        return "选镜单：用这段的爆款都没说这句，无镜头数和秒数中位数。检索时长先按同类句 1–2 秒掌握。"
    ns, sec = sent["n_shots"], sent["seconds"]
    extra = f"；{sent['shot_note']}" if sent.get("shot_note") else ""
    return f"有这句的片子里，中位镜头数 {ns}，中位秒数 {sec}。检索优先可用时长 1–2 秒，动作类尽量动作完整=有起有收{extra}。"


def nature_line(rec) -> str:
    s = rec["nature"]
    if rec.get("示意"):
        s += "。画面只能作示意。"
    return s


def render_condition_block(rec, sent) -> dict:
    prefer = prefer_from_viral(sent) + list(rec.get("prefer_extra") or [])
    must = rec["must"]
    forbid = rec["forbid"]
    return {
        "必须": fmt_items(must),
        "优先": fmt_items(prefer),
        "禁止": fmt_items(forbid),
        "要几秒": seconds_text(sent, rec),
        "对应性质": nature_line(rec),
        "画面证明不了的部分": rec["cannot_prove"],
        "词表层": layer_index([must, prefer, forbid]),
        "prefer_items": prefer,
    }


def all_sentence_rows():
    rows = []
    for block in SHOTS:
        para = block["para_no"]
        for sent in block["sentences"]:
            rec = get(para, sent["sent_no"])
            cond = render_condition_block(rec, sent)
            rows.append({
                "套": SET_NAME[para],
                "段落": block["para"],
                "段落号": para,
                "句号": sent["sent_no"],
                "记录ID": f"L1-{para:02d}-{sent['sent_no']:02d}",
                "条件组": rec["group"],
                "文案原句": sent["text"],
                "句意": rec["句意"],
                "观点类别": rec["观点类别"],
                "有这句": sent["have"],
                "镜头数中位": sent["n_shots"] if sent["n_shots"] is not None else "",
                "秒数中位": sent["seconds"] if sent["seconds"] is not None else "",
                "爆款实际配的画面": shots_md(sent),
                "必须": cond["必须"],
                "优先": cond["优先"],
                "禁止": cond["禁止"],
                "要几秒": cond["要几秒"],
                "对应性质": cond["对应性质"],
                "画面证明不了的部分": cond["画面证明不了的部分"],
                "词表层": cond["词表层"],
                "与旧表对齐": rec.get("旧表对齐", ""),
                "上报备注": rec.get("上报", ""),
                "示意": "是" if rec.get("示意") else "否",
                "无爆款镜头": "是" if rec.get("无爆款镜头") else "否",
                "视频数": block["n_videos"],
                "片号": "、".join(block["video_ids"]),
            })
    return rows


def write_sentence_tsv_md(rows):
    tsv = OUT / "第一条线_逐句对照表.tsv"
    fields = ["记录ID","套","段落","句号","条件组","文案原句","句意","观点类别","对应性质","示意",
              "有这句","镜头数中位","秒数中位","要几秒","爆款实际配的画面","必须","优先","禁止",
              "画面证明不了的部分","词表层","与旧表对齐","上报备注","片号"]
    with tsv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: str(r.get(k, "")).replace("\r\n","\n") for k in fields})

    md = OUT / "第一条线_逐句对照表.md"
    lines = []
    lines.append("# 第一条线逐句对照表（T07 / 20261117_01）")
    lines.append("")
    lines.append("范围：爆款选镜单里合并后的 8 套文案。选镜单总览列出 9 段，其中第63段与第74段是同一套的不同版本，套数按 8 计；每一句（含两个版本各自的句子，以及第62段爆款没说的两句）都有自己的一条记录。")
    lines.append("")
    lines.append(f"记录总数：{len(rows)} 句。规则版本：素材标注总纲 v0.2、专有词表 v0.1、选镜单 2026-11-16、句意画面对照表 2026-11-14。判断由本次 T07 执行者根据这些文件写出，未调用云端模型，未看原片。")
    lines.append("")
    lines.append("选镜单是 AI 拆的、没有人工核对。发现明显不合理或和原文相反的，已在该句「上报备注」写出，并另有问题单；没有偷偷改原文。")
    lines.append("")
    lines.append("同一条件组可以共用写法，但每句仍保留独立记录。第63/74 两版工期数字不同，不共用同一个天数。")
    lines.append("")
    cur = None
    for r in rows:
        if r["套"] != cur:
            cur = r["套"]
            lines.append(f"## {cur}")
            lines.append("")
            block = next(b for b in SHOTS if b["para_no"]==r["段落号"])
            lines.append(f"> {block['original']}")
            lines.append("")
            if block.get("aliases"):
                lines.append(f"文案库近版本：{block['aliases']}")
                lines.append("")
            lines.append(f"用过的爆款：{block.get('n_videos')} 条（{ '、'.join(block.get('video_ids') or []) }）。")
            lines.append("")
        lines.append(f"### {r['记录ID']}　第{r['句号']}句")
        lines.append("")
        lines.append(f"- **文案原句：** {r['文案原句']}")
        lines.append(f"- **句意（与旧对照表对齐用）：** {r['句意']}")
        lines.append(f"- **对应观点类别：** {r['观点类别']}")
        lines.append(f"- **条件组：** {r['条件组']}")
        lines.append(f"- **有这句 / 镜头数中位 / 秒数中位：** {r['有这句']} / {r['镜头数中位'] or '无'} / {r['秒数中位'] or '无'}")
        lines.append(f"- **爆款实际配的画面：** {r['爆款实际配的画面']}")
        lines.append("")
        lines.append("**必须**")
        lines.append("")
        lines.append(r["必须"])
        lines.append("")
        lines.append("**优先**")
        lines.append("")
        lines.append(r["优先"])
        lines.append("")
        lines.append("**禁止**")
        lines.append("")
        lines.append(r["禁止"])
        lines.append("")
        lines.append(f"- **要几秒：** {r['要几秒']}")
        lines.append(f"- **对应性质：** {r['对应性质']}")
        lines.append(f"- **画面证明不了的部分：** {r['画面证明不了的部分']}")
        lines.append(f"- **词表层：** {r['词表层']}")
        lines.append(f"- **与旧表对齐：** {r['与旧表对齐']}")
        if r["上报备注"]:
            lines.append(f"- **上报备注：** {r['上报备注']}")
        lines.append("")
    md.write_text("\n".join(lines), encoding="utf-8")
    return tsv, md

def write_pattern_table():
    p = OUT / "第一条线_规律表.md"
    text = '''# 第一条线整片规律表（T07 / 20261117_01）

依据主要是选镜单「这 20 条的共同点」和总览表。这 20 条是文案库能对上的爆款，不是句意对照表里的 32 条，两条统计不要混用。只有 1 条或 2 条片子支持的现象，标「例子，不是规律」。

## 镜头数量和时长

| 规律 | 数字 | 依据 | 备注 |
|---|---|---|---|
| 一条片子的镜头数 | 11–23 个，中位 14.5 个 | 选镜单对 20 条的统计 | 旧对照表 32 条的中位是 16 个，样本不同，不是互相推翻 |
| 单个镜头时长 | 中位 1.28 秒；2% 的镜头超过 3 秒 | 同上 20 条 | 旧表 32 条中位 1.30 秒，91% 不超过 2 秒，方向一致 |
| 可用时长检索 | 优先 1–2 秒，动作要有起有收 | 总纲 C2 也按这个中位来分档 | 人物手势、批刮落刀收刀不要只切中段 |

总览里各套的镜头数、时长：第50段 11–21 镜 / 17–21 秒（6条）；第46段 12–14 镜 / 18–20 秒（3条）；第71段 14–17 镜 / 24–25 秒（3条）；第30段 17–23 镜 / 23 秒（2条，样本偏少，谨慎当作规律）；第63段 13–16 镜 / 20 秒（2条，谨慎）；第54、62、65、74 段都只有 1 条片子，镜头数和时长只当例子，不是规律。

## 第一个镜头常用什么

20 条合计（选镜单，按条数）：施工·批刮覆盖 6、施工·滚涂 4、人物对镜头 3、旧房旧态 2、人物在现场 2、演示·弯折样板/揭薄层 1、团队上门/搬料搬物 1、握手/与客户沟通 1。

据此可写成规律：

- 垂直陶泥类文案，第一个镜头最常见的是施工动作（批刮或滚涂）。依据：20 条里 10 条是批刮或滚涂开头。
- 同城标签、人设钩子类（第30段这种），第一个镜头更常见人物对镜头。依据：第30段 2 条都是人物对镜头开头；在 20 条里人物对镜头开头共 3 条。样本不多，标「有依据，但不如施工开头那么稳」。
- 第54、62、65、74 段各自的开场（旧房、握手、人物、人物在现场）都只有 1 条片子，例子，不是规律。

## 最后一个镜头常用什么

20 条合计：人物对镜头 10、团队上门/搬料搬物 3、人物在现场 3、握手/与客户沟通 3、成品空间 1。

规律：结尾基本是人。20 条里 19 条最后一镜是人物对镜头、上门、在现场或握手；成品空间收尾只有 1 条，只能当例子。旧对照表 32 条里 28 条最后一镜是人物，方向一致。

点赞请求句本身：选镜单和第 8 套里，说「点个小爱心」时最常用人物对镜头。这和旧表「点赞请求 30 个镜头里 18 个是人物对镜头」一致，可当规律用。

## 哪几类画面几乎每条都有

| 规律 | 数字 | 依据 |
|---|---|---|
| 批刮镜头几乎每条都有 | 20/20 条有，每条中位 4 个 | 选镜单共同点 |
| 成品里有人、手摸成品或成品清洁，多数片子会用到 | 13/20 条有 | 同上 |
| 握手/与客户沟通，过半数片子会用到 | 12/20 条有 | 同上 |
| 演示（喷水、弯折、刮擦），大约一半片子会用到 | 10/20 条有 | 同上；不是每条性能句都有演示 |
| 拆砸/贴砖（传统做法）不是每条都有 | 8/20 条有 | 同上；否定拆砸句不得把它当主画面 |

第30段（同城标签、报价人设）批刮不是主轴，不要把「每条中位 4 个批刮」强加到这一套。它只有 2 条片子，具体镜次只作参考。

## 文案和字幕

选镜单：文案基本照原文念，只换城市和人名。除去带封面字的第一个镜头，294 个镜头里只有 4 个的字幕对不上原文。剪第一条线时应保留钩子和原句，不要为了「更好配画」改原文。第62段爆款把结尾改成了留言/免费上门，原句第10、11 句没有出镜，对照表仍为这两句补了条件，并标明无中位数。

## 不要写成规律的

- 第54段开场用了 4 个镜头（滚涂 2、旧房 1、批刮 1），只有 1 条片子，例子，不是规律。
- 第65段「快速翻新厨房和卫生间」用了 4 个镜头、7.6 秒，远长于单句中位，例子，不是规律。
- 第65段铺垫句用了旧→新同镜转场，旧表里这类镜头总共只有 2 个，例子，不是规律。
- 第63段和第74段工期分别写「七天」和「三天」，不能合成一条工期规律，必须按该版本文案的数字执行。
'''
    p.write_text(text, encoding="utf-8")
    return p


def write_shot_list(rows):
    """汇总必须/优先里出现的画面类型，并估算 8 套各做一条大约要多少镜头。"""
    # sentences needing each type from 必须+优先 text and viral counts
    need_sents = Counter()
    # estimate shots if produce 1 video per 8 sets
    # For set E, use para 63 (2 videos) as primary estimate, note 74 separately
    per_set_type = defaultdict(lambda: Counter())  # para -> type -> avg shots per video

    for block in SHOTS:
        nvid = block["n_videos"] or 1
        for sent in block["sentences"]:
            for it in sent.get("shot_types") or []:
                t = std_type(it["type"])
                c = it["count"] or 0
                per_set_type[block["para_no"]][t] += c / nvid

    for r in rows:
        blob = r["必须"] + "\n" + r["优先"]
        mentioned = set()
        for name in V:
            if name == "其他（模糊画面、叠大字等）":
                continue
            if name in blob or vcode(name) in blob:
                mentioned.add(name)
        if "其他" in blob or "V22" in blob:
            mentioned.add("其他")
        for t in mentioned:
            need_sents[t] += 1

    # 8套各一条：A50 B46 C71 D30 E63 F54 G62 H65  （不用74以免和63双计）
    eight_paras = [50, 46, 71, 30, 63, 54, 62, 65]
    type_eight = Counter()
    for para in eight_paras:
        for t, avg in per_set_type[para].items():
            type_eight[t] += avg

    # sort by estimated shots desc
    types = sorted(set(list(need_sents) + list(type_eight)), key=lambda t: (-type_eight[t], -need_sents[t], t))

    lines = []
    lines.append("# 第一条线要的画面清单（T07 / 20261117_01）")
    lines.append("")
    lines.append("这份清单把逐句条件里「必须」「优先」出现过的画面类型汇总，供后面查素材够不够用。")
    lines.append("")
    lines.append("「被多少句话要」= 99 条逐句记录中，必须或优先栏写到了这一类的句子数。")
    lines.append("「8 套各做一条大约要多少个镜头」= 按选镜单每套爆款里该类镜头个数除以该套片子数，再把 8 套加总。套 E 用第63段（2 条）来估，不和第74段重复计算；第74段是同一套的三天版，镜次只作附注。第54、62、65 段都只有 1 条片子，这两类估算带有例子性质。")
    lines.append("")
    lines.append("选镜单的镜头个数是几条片子加在一起的，已经先除过片子数。结果取一位小数。")
    lines.append("")
    lines.append("| 排序 | 画面类型 | 代码 | 被多少句话要 | 8套各一条大约要的镜头数 | 说明 |")
    lines.append("|---|---|---|---:|---:|---|")
    notes_fixed = {
        "施工·批刮覆盖": "20/20 条爆款都有，每条中位 4 个，是第一条线用量最大的类。",
        "成品空间": "效果、工期、无缝句的主画面。",
        "人物对镜头": "点赞和咨询收尾几乎都要；人物开头在人设套更常见。",
        "拆砸/贴砖": "只宜作传统痛点或短反例，否定拆砸句不得当主画面。",
        "演示·喷水冲洗": "防水防霉的优先演示；不能证明长期防霉。指定目录见对照表。",
        "演示·刮擦/擦污": "耐磨优先演示；指定可用 00428/00429/00430，禁用 00434。",
        "演示·弯折样板/揭薄层": "韧性/不开裂的对应演示；样板不能当墙地面结果。",
        "材料桶": "「这款微陶泥」「也叫金刚陶泥」优先。",
        "其他": "同行高价对比在爆款里几乎全用模糊叠字。",
    }
    for i, t in enumerate(types, 1):
        code = V.get(t, "")
        lines.append(f"| {i} | {t} | {code} | {need_sents[t]} | {type_eight[t]:.1f} | {notes_fixed.get(t, '')} |")
    lines.append("")
    lines.append("## 8 套分别大约要多少（按选镜单估算，单位：一条片子里的镜头数）")
    lines.append("")
    # top types per set
    lines.append("每套镜头总数以选镜单总览的「每条镜头数」为准，不在这里重算。下表只列出估算后每套不少于约 1 个镜头的主要类型。")
    lines.append("")
    for para in eight_paras + [74]:
        tag = SET_NAME[para]
        parts = [f"{t} {c:.1f}" for t, c in per_set_type[para].most_common() if c >= 0.9]
        flag = "（同一套的另一版本，不计入 8 套合计）" if para == 74 else ""
        if para in (54, 62, 65, 74, 30, 63):
            maybe = " 样本 1–2 条，部分是例子。" if para in (54, 62, 65, 74) or para in (30, 63) else ""
        else:
            maybe = ""
        lines.append(f"- {tag}{flag}：{ '；'.join(parts) if parts else '（不足）' }{maybe}")
    lines.append("")
    lines.append("若一个账号按 8 套各剪一条、且希望镜头不和其他近期成片重复，实际库存还要再乘去重天数。那是后续「素材够不够」的事，本表只给画面需求。")
    p = OUT / "第一条线_画面清单.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p

REVIEW_PARAS = [50, 30]  # 抽审：用得最多的一套 + 句式完全不同的同城标签套


def write_review_page(rows):
    p = OUT / "抽审页_第50段和第30段.md"
    lines = []
    lines.append("# 给李康的抽审页：第50段、第30段")
    lines.append("")
    lines.append("这页只为抽审准备。你不用打开其他文件，也能判断我对不对。")
    lines.append("")
    lines.append("我做的事：把文案每一句翻成「要什么画面」的查询条件。不是已经剪好的成片，也没有去检索或导出视频。")
    lines.append("")
    lines.append("怎么抽审：看下面每一句的三列——原句、我写的条件、爆款实际配过的画面。如果条件跟原句拧着，或者爆款配法明显不合理，请直接标出来。选镜单是 AI 拆的、没人核对过；我发现不对的已经写在该句后面，没有改原文。")
    lines.append("")
    lines.append("挑这两套的原因：第50段被 6 条爆款用过，是第一条线里证据最多的一套；第30段是同城标签，人设和报价为主，和垂直陶泥那几套不一样，可以一起看我有没有生搬硬套。")
    lines.append("")
    lines.append("条件里反复出现的几条口径：批刮必须是刮板类工具接触基面铺展或刮平；滚涂必须是滚筒，刷子算刷涂；微陶泥身份要有人工确认或目录标称；阿明身份不能靠脸猜；工期、价格、寿命、环保、性能这些，画面只能作示意，要另核报价单、检测报告或合同。")
    lines.append("")

    for para in REVIEW_PARAS:
        block = next(b for b in SHOTS if b["para_no"]==para)
        lines.append(f"## {SET_NAME[para]}")
        lines.append("")
        lines.append(f"**原文：** {block['original']}")
        lines.append("")
        lines.append(f"**用过的爆款：** {block['n_videos']} 条（{'、'.join(block['video_ids'])}）。第一个镜头：{block['first_shot']}。最后一个镜头：{block['last_shot']}。")
        if block.get("unmatched_shots"):
            lines.append("")
            lines.append("爆款里没对上原文、自己改写或加的句子：")
            for u in block["unmatched_shots"]:
                lines.append(f"- {u}")
        lines.append("")
        for r in [x for x in rows if x["段落号"]==para]:
            lines.append(f"### 第{r['句号']}句　{r['文案原句']}")
            lines.append("")
            lines.append("| 项目 | 内容 |")
            lines.append("|---|---|")
            lines.append(f"| 原句 | {r['文案原句']} |")
            lines.append(f"| 爆款实际配的画面 | 有这句 {r['有这句']}；中位 {r['镜头数中位']} 个镜头、{r['秒数中位']} 秒。<br>{r['爆款实际配的画面']} |")
            # flatten conditions for table: use <br>
            def br(text):
                return text.replace("\n", "<br>")
            lines.append(f"| 我写的必须 | {br(r['必须'])} |")
            lines.append(f"| 我写的优先 | {br(r['优先'])} |")
            lines.append(f"| 我写的禁止 | {br(r['禁止'])} |")
            lines.append(f"| 要几秒 | {r['要几秒']} |")
            lines.append(f"| 对应性质 | {r['对应性质']} |")
            lines.append(f"| 画面证明不了的部分 | {r['画面证明不了的部分']} |")
            lines.append(f"| 词表层 | {r['词表层']} |")
            lines.append("")
            if r["上报备注"]:
                lines.append(f"**请特别看一眼：** {r['上报备注']}")
                lines.append("")
            else:
                lines.append(f"与旧对照表的关系：{r['与旧表对齐']}")
                lines.append("")
    lines.append("## 请你拍板的事")
    lines.append("")
    lines.append("1. 第50段第2句「都不会再砸瓷砖了」，爆款把拆砸和批刮并列着用。我规定主画面不能是正在砸砖，拆砸只能当短反例。这样收是不是对？")
    lines.append("2. 第30段第2句「其他装修公司张口就要十几万」，爆款全是模糊画面叠大字。我把这一类写成可以用「其他」画面承接，但金额只能示意。是否同意？")
    lines.append("3. 第30段第5句「花个几千到2万就能从这样改成这样」，我要求旧态和成品成对，而且只有人工确认同户才能说是同一套房子。是否同意？")
    lines.append("4. 如果这两套整体方向没问题，其他 6 套我按同一套写法执行了，可以抽其中句子再看。")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def cat_rows():
    # 78 with views, sort by occ_sum desc
    view_cats = [c for c in CATJSON["categories"] if not (c["n"]==0 and c["name"]=="防滑")]
    # include 防滑 separately
    fanghua = next(c for c in CATJSON["categories"] if c["name"]=="防滑")
    ranked = sorted(view_cats, key=lambda c: (-c["occ_sum"], -c["n"], c["name"]))
    return ranked, fanghua


def render_one_cat(c, rec, with_examples=False):
    lines = []
    nature = rec.get("mixed_nature") or c["nature"] or rec.get("nature_override") or c["nature"]
    fact = rec.get("fact_all") or (c["nature"]=="需事实依据")
    nature_line = nature
    if fact or (c.get("natures") or {}).get("需事实依据"):
        n_fact = (c.get("natures") or {}).get("需事实依据") or (c["n"] if fact else 0)
        if n_fact:
            nature_line = f"{nature}。本类观点中需事实依据 {n_fact} 条，这些句子以及所有政策、工期、寿命、性能类主张，画面只能作示意。"
        if fact:
            nature_line = f"{c['nature']}。画面只能作示意。"
    lines.append(f"- **出现次数合计：** {c['occ_sum']}（代表句 {c['n']} 条；索引表条目数 {c['declared_n']}）")
    lines.append(f"- **索引表对应性质：** {c['nature']}")
    lines.append(f"- **本表采用的对应性质：** {nature_line}")
    lines.append(f"- **清单写的适合素材：** {c['adapt']}")
    lines.append(f"- **清单写的选镜限制：** {c['limit'] or '（无）'}")
    lines.append("")
    lines.append("**必须**")
    lines.append("")
    lines.append(fmt_items(rec["must"]))
    lines.append("")
    lines.append("**优先**")
    lines.append("")
    lines.append(fmt_items(rec.get("prefer") or []))
    lines.append("")
    lines.append("**禁止**")
    lines.append("")
    lines.append(fmt_items(rec["forbid"]))
    lines.append("")
    lines.append(f"- **要几秒：** {rec['duration']}")
    lines.append(f"- **画面证明不了的部分：** {rec['cannot_prove']}")
    lines.append(f"- **词表层：** {layer_index([rec['must'], rec.get('prefer'), rec['forbid']])}")
    if rec.get("polar"):
        lines.append("- **肯否定：** 本类已单独写两套条件，见《肯否定分套条件.md》。")
    if rec.get("specified"):
        lines.append(f"- **指定/禁用素材（原样带入）：** 防水演示优先「{ '扒扒/1卫生间/卫生间微陶泥防水' }」；耐磨/相关测试可用 00428、00429、00430；00434 禁用。")
    if rec.get("mixed_suggest_split"):
        lines.append("- **上报：** 本类混了不止一种画面需求，建议拆开，见问题单。")
    if with_examples:
        lines.append("")
        lines.append("**出现次数最多的 3 条原句，以及套用本类条件时要盯的点：**")
        lines.append("")
        for i, ex in enumerate((c.get("examples") or [])[:3], 1):
            lines.append(f"{i}. `{ex['id']}`（出现次数 {ex['occ']}，该条对应性质：{ex['nature']}）原句：「{ex['sent']}」")
            lines.append(f"   - 清单适配要点：{ex['adapt'][:180]}{'…' if len(ex['adapt'])>180 else ''}")
            extra = "该条需事实依据，画面只能作示意。" if ex["nature"]=="需事实依据" else "条件按上面本类必须/优先/禁止执行，再按这句原句里的对象、空间和肯否定收窄。"
            lines.append(f"   - 我给的条件：{extra}")
    lines.append("")
    return "\n".join(lines)


def write_categories():
    ranked, fanghua = cat_rows()
    assert len(ranked)==78, len(ranked)
    md = OUT / "78类_观点画面对照表.md"
    tsv = OUT / "78类_观点画面对照表.tsv"
    lines = []
    lines.append("# 78 类观点画面对照表（T07 / 20261117_01）")
    lines.append("")
    lines.append("按观点清单「出现次数合计」（原文定位里该类别全部出现次数之和，总计 3549）从多到少排列。共 78 类，与观点清单里出现过的类别一致。")
    lines.append("")
    lines.append("索引表另有「防滑」一行，出现次数合计为 0，不计入这 78 条，附录在文末。")
    lines.append("")
    lines.append("出现次数最多的前 20 类，每类附 3 条原句。对应性质照抄清单；一个类里如果个别句子的性质不同，以该条观点为准。需事实依据的句子全部写明「画面只能作示意」。")
    lines.append("")
    lines.append("指定和禁用素材原样带入：防水演示优先「扒扒/1卫生间/卫生间微陶泥防水」；耐磨演示可用 00428、00429、00430；00434 禁用。")
    lines.append("")

    fields = ["排序","素材类别","出现次数合计","代表句数","索引对应性质","必须","优先","禁止","要几秒","画面证明不了的部分","词表层","肯否定","指定禁用"]
    tsv_rows = []
    top20 = [c["name"] for c in ranked[:20]]

    for i, c in enumerate(ranked, 1):
        rec = CATS[c["name"]]
        lines.append(f"## {i}. {c['name']}")
        lines.append("")
        lines.append(render_one_cat(c, rec, with_examples=(c["name"] in top20)))
        tsv_rows.append({
            "排序": i,
            "素材类别": c["name"],
            "出现次数合计": c["occ_sum"],
            "代表句数": c["n"],
            "索引对应性质": c["nature"],
            "必须": fmt_items(rec["must"]),
            "优先": fmt_items(rec.get("prefer") or []),
            "禁止": fmt_items(rec["forbid"]),
            "要几秒": rec["duration"],
            "画面证明不了的部分": rec["cannot_prove"],
            "词表层": layer_index([rec["must"], rec.get("prefer"), rec["forbid"]]),
            "肯否定": "是" if rec.get("polar") else "否",
            "指定禁用": "是" if rec.get("specified") else "否",
        })

    lines.append("## 附录：防滑（不计入 78 类）")
    lines.append("")
    lines.append(render_one_cat(fanghua, CATS["防滑"], with_examples=False))

    md.write_text("\n".join(lines), encoding="utf-8")
    with tsv.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in tsv_rows:
            w.writerow({k: str(r[k]).replace("\r\n","\n") for k in fields})
    return md, tsv, ranked, top20

def write_polarity():
    p = OUT / "肯否定分套条件.md"
    text = r'''# 肯否定分套条件（T07 / 20261117_01）

同一类里，肯定句和否定句要的画面相反。任务书点名的是拆砸、搬家、噪音扬尘、水电改造。清单「选镜限制 / 适合的素材」里写到「按肯否定」或等价要求的，还有原砖与翻新基层、补充工序与改造方式。保留基层不拆砸以否定拆砸为主，一并写清和传统拆砸类的对照。

每类先写两套条件，再从观点清单里挑原句作例子。不够 5 条的，有多少写多少，不编造。

## 1. 传统拆砸与返工（出现次数合计 81）

**肯定 / 传统痛点（旧方法就是要拆、要砸、要返工）**

- 必须：画面类型=拆砸/贴砖（V08）或铲修旧墙/旧顶（V07）；主动作=拆砸、拆卸或铲除；阶段=拆除铲除中。词表：画面类型、主动作=品类专有；阶段=行业通用。
- 优先：能看出是传统做法或被否定的旧方法（碎料、电锤、拆砖），不要剪成「我们正在得意地砸」。
- 禁止：把这类痛点镜头直接接到「我们的微陶泥工艺」上当主推动作。
- 要几秒：1–2 秒，动作完整更好。
- 对应性质：直接展示（痛点可以展示传统动作）。
- 画面证明不了的部分：不能证明我方服务就是拆砸，也不能证明所有旧房都必须先砸。

**否定（不想拆、不拆不砸、省了拆除）**

- 必须：主画面=施工·批刮覆盖（V05），基层能同时看见旧砖和新材料；不得以正在砸砖为主画面。
- 优先：拆砸只可作极短反例，并且要能读出是被否定的旧方法。
- 禁止：正面展示正在砸砖造成反义（与清单限制、陈瀚文褒贬方向一致）。
- 对应性质：直接展示做法；若句子同时在讲省钱，费用部分只能示意。

**例子（否定，5 条）**

1. P1005「不想又拆又砸」（出现 6）
2. P0555「传统换地板又拆又砸」（出现 4，传统痛点对比，主画面仍不要把我方写成正在砸）
3. P1658「别人翻新又拆又砸」（出现 3）
4. P1031「省了一大笔拆除费」（出现 3，费用示意，做法用覆盖）
5. P0001「以前武汉翻新老房子都是敲瓷砖」（出现 2，旧方法痛点，可短展示敲砖，须接向现在不砸）

**例子（肯定 / 旧方法或确实要拆除，5 条）**

1. P0033「不仅要拆除」（出现 6）
2. P0263「传统翻新要砸掉瓷砖」（出现 1）
3. P0364「拆除」（出现 3，须回看上下文确认是痛点还是我方服务）
4. P0402「拆旧安装」（出现 3，须按对象确认是拆旧还是安装）
5. P0002「铲墙皮」（出现 2，主动作应是铲除，画面类型铲修旧墙/旧顶）

## 2. 搬家折腾（出现次数合计 54）

**否定（不用搬家、不搬家、不用您搬家）**

- 必须：家具仍在现场、分区施工、铺保护膜/贴胶带、或住户能正常通行的画面。
- 优先：铺保护膜、边住边改的生活通行。
- 禁止：把整户打包搬离、去住酒店的画面拿来配「不用搬家」。不要把施工中短暂搬家具说成整户搬家。
- 对应性质：直接展示可见的「还住在家里 / 家具还在」。

**肯定（传统折腾：搬出去住酒店、整户搬离）**

- 必须：真实的打包搬运、搬离、住离现场的折腾场面，并能读出这是被比较的旧方法或痛点。
- 禁止：用我方「家具还在、正常做饭通行」的画面来配「还得搬出去」。

**例子（否定，5 条）**

1. P0054「而且不用搬家」（出现 17）
2. P0417「全程不用搬家」（出现 4）
3. P0110「不搬家」（出现 4）
4. P1588「边住边改不搬家」（出现 2）
5. P0187「最贴心的是全程不用搬家」（出现 1）

**例子（肯定 / 传统折腾；清单里明确「搬出去」的句子不足 5 条，全部列出）**

1. P0556「还得搬出去住酒店」（出现 5）
2. P1653「这个过程不仅需要出去住酒店」（出现 1）
3. 其余代表句多为「不需要搬家」等否定（如 P0787、P1998），不拿来凑肯定例子。

## 3. 传统噪音与扬尘（出现次数合计 22）

清单适合栏写明「按肯否定选」。

**肯定 / 传统痛点（噪音大、灰尘满天飞、扰民）**

- 必须：实际拆砸、扬尘可见的传统施工（V08 等），不要后期合成粉尘。
- 禁止：用安静的手工批刮来配「灰尘满天飞」，造成反义。

**否定（不扰民、没有灰尘、静音、没有施工污染）**

- 必须：手工批刮、分区围护、日常通行等低扰动画面。
- 禁止：把正在打电锤、粉尘很大的拆砸当主画面。
- 画面证明不了的部分：无灰尘、无噪音等绝对说法不能靠静音视频或无音轨证明。只能示意低扰动。

**例子（否定，5 条）**

1. P0111「全程静音不扰民」（出现 4）
2. P0655「没有灰尘」（出现 3）
3. P1176「不搬家不扰民」（出现 3）
4. P1660「不扰民」（出现 3）
5. P0068「没有施工污染」（出现 2）

**例子（肯定 / 传统痛点；只有 2 条明白的肯定痛点，不编造）**

1. P0003「不仅噪音大还扰民」（出现 2）
2. P0004「施工起来灰尘满天飞」（出现 2）

## 4. 水电改造（出现次数合计 22）

**肯定（要改水电、重新装改水电）**

- 必须：真实检查管线、开槽、布管或接线；画面类型=量房/水电/安装（V04）；主动作须对上，不要用批刮冒充水电施工。

**否定（不改水电、不用改水电）**

- 必须：展示保留原设施的表面翻新（旧砖上覆盖或成品，能看见原有洁具/管位仍在）。
- 禁止：「不用改」不能配正在拆管线。

**例子（否定，清单里明确的只有 2 条）**

1. P0070「不改水电」（出现 7）
2. P1826「还不用改水电」（出现 1）

**例子（肯定，5 条）**

1. P1367「而且还要重新装改水电」（出现 5）
2. P0035「改水电」（出现 1）
3. P0264「重新改水电」（出现 1）
4. P0392「还要改水电」（出现 1）
5. P1015「重新装改水电」（出现 1）

## 5. 原砖与翻新基层（出现次数合计 44）

适合栏要求结合原句肯否定选原砖近景、基层处理或覆盖界面；贴砖语境须对应真实铺贴。

**保留原砖 / 不用敲 / 瓷砖上也可以直接做**

- 必须：旧砖近景，或旧砖上覆盖批刮，基层可见。
- 禁止：用传统揭砖、贴砖过程当主画面。

**传统贴砖 / 买瓷砖铺贴**

- 必须：真实铺贴动作（主动作=贴砖）。
- 禁止：用覆盖批刮冒充贴砖，或用贴砖冒充不拆不砸。

本类还混有「地面老旧」「改造墙地面」等需要回看上下文的句子，单独的「瓷砖」两个字不能直接定画面。建议拆类，已写问题单。

**例子（保留/不敲，5 条）**

1. P0210「墙地面瓷砖不用敲」（出现 2）
2. P0614「主要是瓷砖上也可以直接做」（出现 2）
3. P0440「淋浴房翻新改造不用瓷砖」（出现 2）
4. P0375「像这样的瓷砖」（出现 2，须看见所指的旧砖）
5. P1199 不在本类（在保留基层类）；本类再补 P0327「现在没人买几十块一片的瓷砖了」（出现 4，这是选型语境，不要误配贴砖过程）

**例子（须回看上下文，不硬分成肯否定）**

1. P1370「改造一下墙地面」（出现 8）
2. P0956「比如地面老旧」（出现 3）
3. P0141「瓷砖」（出现 2）

## 6. 补充工序与改造方式（出现次数合计 15）

限制栏写明按肯否定和具体工序选择。

**肯定拆砸：** 真实拆旧（V08）。
**否定拆砸 / 不想拆砸换新：** 保留原砖的覆盖批刮（V05），不要主画面砸砖。
**美缝：** 填缝收胶近景。总纲没有美缝专类，主动作暂用批刮（补缝也算）或其他，已列入缺口。
**笼统工艺介绍：** 按原句具体动作选完整施工，不要默认全是批刮。

本类把拆砸态度、美缝和工艺介绍混在一起，建议拆开，已写问题单。

**例子（否定拆砸或批评乱拆，5 条）**

1. P0231「别人想尽办法让你拆砸」（出现 2）
2. P0232「哪里能赚拆哪里」（出现 4）
3. P1593「又不想那么麻烦的拆砸换新」（出现 1）
4. P1620「业主不想拆砸」（出现 1）
5. P1536「拆砸存在安全隐患」（出现 1）

**例子（其他工序，全部列出）**

1. P1488「做美缝」（出现 1）
2. P1759「把旧房重装了一遍」（出现 1，须回看是覆盖还是传统重装）
3. P1708「但是大面积的拆砸」（出现 1，按上下文判断肯否定）

## 7. 保留基层不拆砸 与上面第 1 类的关系

本类 70 条代表句、出现次数合计 153，绝大多数是「不拆不砸」「不需要拆砸」。条件固定走否定套：主画面为可见旧基层上的批刮覆盖，不配电锤拆砖。5 条需事实依据的句子另写示意。不强制再找 5 条「肯定拆砸」的例子，那些句子主要落在「传统拆砸与返工」。
'''
    p.write_text(text, encoding="utf-8")
    return p


def write_conflicts(rows):
    p = OUT / "与旧句意画面对照表_冲突清单.md"
    lines = []
    lines.append("# 与旧「句意画面对照表」的冲突清单（T07 / 20261117_01）")
    lines.append("")
    lines.append("旧表：`句意画面对照表-20261114\\句意画面对照表.md`（32 条爆款、27 类句意、24 类画面）。新条件：本批第一条线 8 套逐句表，以及 78 类表。")
    lines.append("")
    lines.append("## 先说结论")
    lines.append("")
    lines.append("- 24 类画面类型的名称和代码与总纲、选镜单、旧表一致，**定义本身没有冲突。**")
    lines.append("- 大的配法规律（批刮用量最大、结尾是人、点赞用对镜头、材料指认用料桶、效果用成品空镜、工期和环保常常不举证）两边一致，**不是冲突。**")
    lines.append("- 下面列出的是「同一类句意，旧表主配和选镜单/检索条件不一致，或旧表建议演示而爆款实际配了通用施工」的地方。这些冲突不影响我按任务书把需事实依据写成示意，也不偷偷改原文。")
    lines.append("")
    lines.append("## 冲突和差异")
    lines.append("")
    lines.append("| 编号 | 哪里不一致 | 旧表怎么说 | 选镜单或本批条件怎么处理 | 算不算冲突 |")
    lines.append("|---|---|---|---|---|")
    lines.append("| C01 | 第46段第4句「高硬度耐摩擦」 | 性能·耐磨/硬度主配弯折样板和刮擦 | 选镜单 3 个镜头全是批刮。本批条件：检索优先刮擦演示，批刮只作示意，并写明画面只能作示意 | 是：推荐画面与爆款实配不一致 |")
    lines.append("| C02 | 第46段第2句「因为费时费力又费钱」 | 传统痛点/省钱更常见拆砸或传统步骤、或批刮对比 | 选镜单全是批刮，容易听成「批刮又费时又费钱」。本批按传统痛点方向写条件，并上报 | 是：实配与原句方向不够对题 |")
    lines.append("| C03 | 第65段第2句「不拆不砸，不到一万块钱」 | 不拆不砸主配批刮，拆砸只作反例（50 镜里 35 批刮、6 拆砸） | 选镜单只配了拆砸/贴砖 1 个镜头。本批禁止以砸砖为主画面，并上报怀疑拆错 | 是：与原文和旧表都相反的风险 |")
    lines.append("| C04 | 第62段第6句、第54段第10句等环保/防霉句 | 旧表写明抽象说法常不举证（环保 12 镜里 6 个普通批刮），同时也有性能演示的推荐 | 选镜单确实常配批刮；本批检索优先演示或检测资料，把批刮写成示意备选，并全部写明只能示意 | 部分冲突：和「爆款实际做法」不冲突，和「性能应优先演示」的推荐冲突。按任务书走示意+优先演示 |")
    lines.append("| C05 | 第71段第6句「省下拆除搬运垃圾的费用」 | 省钱句主配批刮和拆砸反例 | 选镜单最多的是手摸成品。本批按省钱/清运方向写，并上报 | 是：实配主题偏效果 |")
    lines.append("| C06 | 镜头中位 14.5（20条）对 16（32条） | 旧表 32 条 | 选镜单 20 条是库内能对上的子集 | 否：样本不同，方向一致 |")
    lines.append("| C07 | 第30段同行高价 | 旧表 5 个镜头全是「其他」 | 选镜单同样全是模糊叠字，本批沿用 | 无冲突 |")
    lines.append("| C08 | 「也叫金刚陶泥」 | 旧表归材料指认，主配料桶、批刮 | 词表现已确认金刚陶泥=微陶泥。本批按微陶泥检索，不另立材料。第74段这句爆款配了成品和清洁，料桶缺失，只当例子 | 口径需按新词表执行，不是和旧表画面定义冲突 |")
    lines.append("")
    lines.append("除上表 C01–C05 这类具体句子外，**没有发现旧表把某类句意的主画面规定成 A、而总纲把同一类规定成相反的 B。** 若只问「画面类型定义有没有冲突」：无。")
    lines.append("")
    lines.append("第一条线 99 句里，我在每句下都写了「与旧表对齐」的一句说明，便于逐句复核。")
    # count report flags
    n_rep = sum(1 for r in rows if r.get("上报备注"))
    lines.append(f"其中带上报备注的句子：{n_rep} 条，与上表冲突项对应，问题单另见「发现的问题」。")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p, n_rep

def write_gaps(ranked):
    p = OUT / "缺口清单.md"
    # 涉及观点条数：use occ_sum or n? Task says 涉及的观点条数. I'll use 代表句数 n, and also show occ_sum.
    text = '''# 缺口清单（T07 / 20261117_01）

总纲现有字段表达不了、或只能近似表达的条件。按涉及的观点条数（代表句数）从多到少排。同一缺口如果跨很多类，条数按相关类别代表句合计，并避免重复计算时在说明里写清口径。

这些缺口没有改总纲或词表，只登记。检索时先用现有字段近似，并在对照表里写明限制。

## 清单

| 排序 | 缺口 | 涉及哪些类或句子 | 观点代表句数 | 出现次数合计 | 想写但没有的栏目或选项 | 现在怎么处理 |
|---|---|---|---:|---:|---|---|
| G01 | 报价、金额、预算无法检索 | 价格与预算、预算与人工开支，以及第一条线所有报价句 | 140+14=154（两类合计，句子不跨类重复） | 218+23=241 | 没有「报价单 / 金额画面 / 计价条件」字段或画面类型。V22「其他」只能描述模糊叠字，不能存核过的报价依据 | 对应性质按清单走，画面一律示意，依据交给报价单或合同另核 |
| G02 | 工期数字无法检索 | 工期与效率 133 条，以及第一条线所有「三天、七天、当天」句 | 133 | 206 | 没有「声称工期（天）」或「可核工期记录」字段 | 主画面用成品示意完成状态，天数另核施工记录或合同 |
| G03 | 检测报告 / 证明文件无法入库检索 | 环保与无异味、政策与补贴、售后与质保、寿命、韧性、部分耐磨防霉；需事实依据共 292 条都会碰到 | 292（需事实依据全部） | 须按 292 条执行，不按单类加总 | 总纲没有「证明文件类型 / 报告编号 / 核验状态」字段。D1 只有示意/可举证四类画面情形，不含报告 | 全部写明画面只能作示意，依据交给检测报告、政策原文、质保条款另核 |
| G04 | 城市几乎没有可用字段 | 地域与受众 70 条，以及文案里的武汉等地名 | 70 | 119 | 总纲 A2 有城市，但现有数据「城市基本没有」 | 作为企业专有的账号配置来写，不能靠画面或后期大字把外地素材改成当地证据 |
| G05 | 褒贬方向 / 肯否定不是片段标签 | 传统拆砸、搬家、噪音扬尘、水电、原砖、补充工序、保留基层不拆砸等 | 70+55+25+12+10+27+11 有重叠，去重后至少上述各类之和的主体部分，保守按「拆砸相关三类+搬家+噪音+水电」代表句 70+55+25+10+12 先登记，实际检索要按句判断 | 见各类表 | 陈瀚文规则有褒贬方向，总纲没有对应字段。拆砸镜头无法标记「这是反例还是主推」 | 对照表按句写两套条件；短反例依赖人工看，不能自动检索「带红叉的拆砸」 |
| G06 | 同户配对第一轮还查不到 | 前后变化 22，旧楼外观与室内反差 7，以及「从这样改成这样」类句子 | 22+7，再加第一条线第30段第5句等 | 27+7 | 总纲 D2 是后做，只认人工确认 | 不能确认时只说服务示意，不得暗示同一户 |
| G07 | 指定源白名单 / 禁用源不是正式检索字段 | 耐磨与耐刮 19、防水与耐水 6、耐压与硬度 7，以及性能混合句 | 19+6+7，性能混合句另计，至少 19 | 68+8+13 | A1 有主库编号和路径，但没有「本句指定可用编号/目录、禁用编号」的标准查询项 | 对照表原样写入 00428/00429/00430 可用、00434 禁用、防水优先「扒扒/1卫生间/卫生间微陶泥防水」 |
| G08 | 踢脚线没有专名部位 | 无缝同色与踢脚线 51 | 51 | 115 | 部位只有「墙角与交界」，没有踢脚线 | 用墙角与交界近似，并要求能看见该收口 |
| G09 | 垃圾清运没有画面类型 | 垃圾清运 28 | 28 | 38 | 只能近似为拆砸废料搬运或团队上门，还容易和搬新材料混淆 | 对照表写清废料归拆砸、新材料归上门 |
| G10 | 施工厚度无法检索 | 施工厚度与空间 2 条，以及第63/74段「批刮三到五毫」 | 2，另加第一条线 2 句 | 2 | 没有厚度字段 | 只能示意近景涂层，数字另核工艺说明 |
| G11 | 开桶没有独立动作 | 开桶即用 4 | 4 | 8 | 动作只有倒料取料、搅拌，没有开桶 | 要求料桶镜头尽量看见开盖，不用纯批刮代替「打开桶就可以使用」 |
| G12 | 美缝 / 填缝收胶没有专类 | 补充工序里的「做美缝」，找平与填缝 1 条 | 11+1 类内各有少量 | 15+1 | 补缝补裂在总纲里算批刮，但美缝收胶不是覆盖批刮 | 按原句动词选，并建议拆开补充工序类 |
| G13 | 防滑没有画面类型，也没有观点代表句 | 索引表「防滑」，出现次数 0 | 0（不计入 78） | 0 | 不能用刮擦或踩踏冒充防滑认证 | 附录一条条件；若以后文案出现防滑，先走上报再补选项 |
| G14 | 第一条线默认不用扒扒，但防水指定目录在扒扒库 | 防水与耐水及相关性能句 | 6 及混合性能句 | 8 起 | 范围口径和指定例外要同时执行，系统里没有「例外目录」字段 | 对照表写明这是指定例外，不是把扒扒库整体纳入第一条线 |

## 不算缺口、但要记住的口径

- 滚涂和刷涂：画面类型都暂归 V06，主动作分开。片段记录格式草案已经写了给镜序按主动作给。这是已有口径，不单独立缺口。
- 金刚泥=微陶泥：词表已确认。本批按同一材料检索，不改词表，不改原文。
- 竖屏：总纲已有画幅字段，镜序只要原生 9:16，写成必须即可，不是缺口。
'''
    p.write_text(text, encoding="utf-8")
    return p


def validate(rows, ranked):
    problems = []
    # 99 sentences
    if len(rows) != 99:
        problems.append(f"逐句记录不是 99，而是 {len(rows)}")
    # every SHOTS sentence has record
    for block in SHOTS:
        for sent in block["sentences"]:
            try:
                get(block["para_no"], sent["sent_no"])
            except KeyError:
                problems.append(f"缺条件 第{block['para_no']}段 句{sent['sent_no']}")
    # empty fields
    needed = ["必须","优先","禁止","要几秒","对应性质","画面证明不了的部分","词表层","文案原句"]
    for r in rows:
        for k in needed:
            if not str(r.get(k,"")).strip() or str(r.get(k)).strip()=="（无）" and k in ("必须","对应性质","画面证明不了的部分","词表层","文案原句"):
                if k in ("必须","对应性质","画面证明不了的部分","词表层","文案原句") and not str(r.get(k,"")).strip():
                    problems.append(f"空栏 {r['记录ID']} {k}")
    # 78 cats
    if len(ranked) != 78:
        problems.append(f"78类不是 78，而是 {len(ranked)}")
    missing = [c["name"] for c in ranked if c["name"] not in CATS]
    if missing:
        problems.append(f"类别缺条件: {missing}")
    # fact 292 covered by cat natures
    fact_n = sum((c.get("natures") or {}).get("需事实依据", 0) for c in ranked)
    if fact_n != 292:
        problems.append(f"需事实依据不是 292，而是 {fact_n}")
    # 示意 sentences in line 1: all nature 需事实依据 must have 示意
    for r in rows:
        rec = get(r["段落号"], r["句号"])
        if rec["nature"]=="需事实依据" and not rec.get("示意"):
            problems.append(f"需事实依据未标示意 {r['记录ID']}")
        if rec.get("示意") and "示意" not in r["对应性质"] and "示意" not in r["画面证明不了的部分"]:
            problems.append(f"示意未写进口 {r['记录ID']}")
    # polarity cats present
    for name in ["传统拆砸与返工","搬家折腾","传统噪音与扬尘","水电改造","原砖与翻新基层","补充工序与改造方式"]:
        if not CATS[name].get("polar"):
            problems.append(f"未标肯否定 {name}")
    return problems


def main():
    rows = all_sentence_rows()
    tsv1, md1 = write_sentence_tsv_md(rows)
    pat = write_pattern_table()
    shots = write_shot_list(rows)
    review = write_review_page(rows)
    md78, tsv78, ranked, top20 = write_categories()
    polar = write_polarity()
    conf, n_rep = write_conflicts(rows)
    gaps = write_gaps(ranked)
    problems = validate(rows, ranked)

    # summary json for 回报
    fact_sents = [r for r in rows if r["示意"]=="是"]
    summary = {
        "sentence_records": len(rows),
        "paragraphs": 9,
        "sets_counted_as_8": EIGHT_SETS,
        "categories_78": len(ranked),
        "top20": top20,
        "review_page": str(review),
        "line1_示意句数": len(fact_sents),
        "report_sentences": n_rep,
        "validation": problems,
        "files": [str(p) for p in [tsv1, md1, pat, shots, review, md78, tsv78, polar, conf, gaps]],
    }
    (OUT / "_reads" / "build_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SENTENCES", len(rows))
    print("CATS78", len(ranked))
    print("TOP20", top20)
    print("SHI_YI", len(fact_sents))
    print("REPORTS", n_rep)
    print("VALIDATION")
    if problems:
        for x in problems:
            print("  FAIL", x)
    else:
        print("  OK")
    print("REVIEW", review)


if __name__ == "__main__":
    main()