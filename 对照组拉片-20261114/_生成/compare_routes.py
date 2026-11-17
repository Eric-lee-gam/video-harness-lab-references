# -*- coding: utf-8 -*-
"""
2026-11-16 补充：用完整文案库重新比对文案来源，并按制作路线分人汇总。只读输入。

  python compare_routes.py            只在屏幕输出
  python compare_routes.py --write    另外新建 按路线对比数字.md（已存在则报错，不覆盖）

文案库：C:\\Users\\leega\\Downloads\\赋能计划文案最新(2).docx
  它分四节：打同城标签文案 / 垂直陶泥文案 / 新文案 / 施工流程文案。
  陶泥文案(2).docx 的 74 段全部原样包含在它的后几节里，所以只用这一份、按节归属。
  文档里说“标黄是有对标视频”，这里把带标黄的段落记为“有对标”。

路线（Eric 2026-11-16 说明）：
  陈翰文  Obsidian 标签 + AI 自己找
  彭书超  自然语言安排任务（与 Eric 相同）
  张艺    人工标注 + AI 给三个候选、人工选（来自 11/11–11/14 对话记录）
  李康    自然语言安排任务（李康 2026-11-16 确认）
  舒依玲、赵金忠、刘永添  新人手剪
"""
import collections, io, json, os, re, statistics, sys, zipfile
from xml.etree import ElementTree as ET

sys.dont_write_bytecode = True
import control_pull as cp

bt = cp.bt
LIB = r"C:\Users\leega\Downloads\赋能计划文案最新(2).docx"
LIB_SUB = r"C:\Users\leega\Downloads\陶泥文案(2).docx"
ROUTE = collections.OrderedDict([("陈翰文", "Obsidian标签+AI找"), ("张艺", "人工三选一"), ("李康", "自然语言"), ("彭书超", "自然语言"),
                                 ("舒依玲", "新人手剪"), ("赵金忠", "新人手剪"), ("刘永添", "新人手剪")])
THR = 0.5
PEOPLE = {"V01", "V24", "V02"}
BUILD = {"V05", "V06", "V23", "V07", "V08", "V11", "V04", "V09", "V10", "V03"}
DONE = {"V13", "V14", "V15", "V16", "V17"}
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SECTION_HEADS = {"打同城标签文案": "同城标签", "垂直陶泥文案": "垂直陶泥", "新文案": "新文案", "施工流程文案": "施工流程"}
SECTIONS = ["同城标签", "垂直陶泥", "新文案", "施工流程"]
NONE = "库里没有"


def simp(text):
    """繁体转简体（Windows 自带 LCMapStringEx，逐字转换）。"""
    import ctypes
    if not text:
        return ""
    buf = ctypes.create_unicode_buffer(len(text) + 1)
    n = ctypes.windll.kernel32.LCMapStringEx("zh-CN", 0x02000000, text, len(text), buf, len(text) + 1, None, None, 0)
    return buf.value if n else text


def grams(text):
    s = re.sub(r"[^\u4e00-\u9fff0-9]", "", simp(text or ""))
    return {s[i:i + 2] for i in range(len(s) - 1)}


def paragraphs(path):
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    for para in root.iter(W + "p"):
        t, hl = "", False
        for r in para.iter(W + "r"):
            s = "".join(x.text or "" for x in r.iter(W + "t"))
            if not s:
                continue
            t += s
            rp = r.find(W + "rPr")
            if rp is not None:
                a = rp.find(W + "highlight")
                if a is not None and a.get(W + "val") not in (None, "none"):
                    hl = True
        t = t.strip()
        if t:
            yield t, hl


def load_sections(path):
    """返回 [(段落序号, 节, 是否带标黄, 文本, 二字组)]，只留 40 字以上的段落。"""
    out, sec, idx = [], "同城标签", 0
    for t, hl in paragraphs(path):
        if t in SECTION_HEADS:
            sec = SECTION_HEADS[t]
            continue
        idx += 1
        if len(t) >= 40:
            out.append((idx, sec, hl, t, grams(t)))
    return out


def attribute(g, lib):
    """返回 (相似度, 节或“库里没有”, 是否有对标, 段落序号)"""
    sc = [(len(g & cg) / max(1, len(g)), sec, hl, i) for i, sec, hl, t, cg in lib]
    s, sec, hl, i = max(sc, key=lambda x: x[0])
    if s < THR:
        return s, NONE, False, -1
    return s, sec, hl, i


def pct(a, b):
    return f"{a / b:.0%}" if b else "-"


def main(write):
    lib = load_sections(LIB)
    sub = [grams(t) for t, _ in paragraphs(LIB_SUB) if len(t) >= 40]
    inside = sum(1 for g in sub if max(len(g & cg) / max(1, len(g)) for _, _, _, _, cg in lib) >= 0.8)
    L = []
    A = L.append
    A("# 按路线对比数字（脚本生成，2026-11-16）")
    A("")
    A("文案相似度 = 片子机器转写（繁体先转简体）里的二字组，有多少比例出现在文案库的某一段里。0.5 以上算来自这一段。")
    A("")
    A(f"- 文案库：{os.path.basename(LIB)}，40 字以上的段落 {len(lib)} 段："
      + "，".join(f"{k} {sum(1 for x in lib if x[1] == k)} 段（带标黄 {sum(1 for x in lib if x[1] == k and x[2])} 段）" for k in SECTIONS))
    A(f"- {os.path.basename(LIB_SUB)} 的 {len(sub)} 段里有 {inside} 段原样出现在上面这份文档里，所以不单独比对。")
    A("- 文档里写“标黄是有对标视频”，下面的“有对标”指匹配到的那一段带标黄。")
    A("")

    # 爆款
    ana = os.path.normpath(os.path.join(cp.OUT, "..", "analysis"))
    A("## 一、32 条爆款的文案在不在库里")
    A("")
    A("| 片号 | 最高相似度 | 归属 | 库里第几段 | 有对标 | 开头（机器转写，已转简体） |")
    A("|---|---|---|---|---|---|")
    ref_src = collections.Counter()
    ref_para = collections.Counter()
    for i in range(1, 36):
        rid = f"R{i:02d}"
        if rid in bt.EXCLUDE:
            continue
        text = json.load(io.open(os.path.join(ana, rid, "asr.json"), encoding="utf-8")).get("raw_text", "")
        s, sec, hl, pi = attribute(grams(text), lib)
        ref_src[sec] += 1
        if pi >= 0:
            ref_para[pi] += 1
        head = re.sub(r"[\s|]", "", simp(text))[:20]
        A(f"| {rid} | {s:.2f} | {sec} | {pi if pi >= 0 else '-'} | {'是' if hl else ''} | {head} |")
    A("")
    A("爆款合计：" + "；".join(f"{k} {ref_src.get(k, 0)} 条" for k in SECTIONS + [NONE]))
    A(f"爆款用到的库内段落共 {len(ref_para)} 段：" + "、".join(f"第{k}段×{v}" for k, v in sorted(ref_para.items())))
    A("")

    # 对照
    rows = cp.all_rows()
    A("## 二、36 条抽样片子的文案在不在库里")
    A("")
    A("| 编号 | 人 | 路线 | 最高相似度 | 归属 | 库里第几段 | 有对标 | 这一段有爆款用过 | 爆款里没有的句型占时长 | 开头（机器转写） |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    src_by, zz_by, hl_by, proven_by = {}, {}, {}, {}
    for m in cp.load_list():
        cid = m["编号"]
        j = json.load(io.open(os.path.join(cp.CACHE, cid + ".json"), encoding="utf-8"))
        text = "".join(s["text"] for s in j["segments"])
        s, sec, hl, pi = attribute(grams(text), lib)
        src_by[cid], hl_by[cid], proven_by[cid] = sec, hl, pi in ref_para
        rs = [r for r in rows if r["cid"] == cid and r["intent"] != "X0"]
        tot = sum(r["dur"] for r in rs)
        zz_by[cid] = sum(r["dur"] for r in rs if r["intent"] == "ZZ") / tot if tot else 0
        A(f"| {cid} | {m['人']} | {ROUTE[m['人']]} | {s:.2f} | {sec} | {pi if pi >= 0 else '-'} | {'是' if hl else ''} | "
          f"{'是' if proven_by[cid] else ''} | {zz_by[cid]:.0%} | {re.sub(r'[\s|]', '', text)[:20]} |")
    A("")

    # 分人
    ref = [r for r in cp.load_ref() if r["intent"] != "X0"]
    top3 = {}
    for i in bt.INTENTS:
        a = [r for r in ref if r["intent"] == i]
        if len(a) >= 10 and i not in ("X0", "ZZ"):
            top3[i] = [v for v, _ in collections.Counter(r["visual"] for r in a).most_common(3)]

    def vids(rs):
        g = collections.defaultdict(list)
        for r in rs:
            g[r["cid"]].append(r)
        for v in g.values():
            v.sort(key=lambda r: r["idx"])
        return g

    def line(label, route, rs):
        g = vids(rs)
        n = len(g)
        t = sum(r["dur"] for r in rs)
        c = [r for r in rs if r["intent"] in top3]

        def has_i(code):
            return sum(1 for v in g.values() if any(r["intent"] == code for r in v))

        def has_v(code):
            return sum(1 for v in g.values() if any(r["visual"] == code for r in v))

        first = [v[0] for v in g.values()]
        return (f"| {label} | {route} | {n} | {statistics.median(len(v) for v in g.values()):.1f} | "
                f"{statistics.median(len({r['visual'] for r in v}) for v in g.values()):.0f} | "
                f"{pct(sum(r['dur'] for r in rs if r['visual'] in PEOPLE), t)} | {pct(sum(r['dur'] for r in rs if r['visual'] in BUILD), t)} | "
                f"{pct(sum(r['dur'] for r in rs if r['visual'] in DONE), t)} | {pct(sum(r['dur'] for r in rs if r['visual'] == 'V12'), t)} | "
                f"{has_v('V05')}/{n} | {has_v('V02')}/{n} | {sum(1 for r in first if r['visual'] == 'V01')}/{n} | "
                f"{pct(sum(1 for r in c if r['visual'] in top3[r['intent']]), len(c))} | "
                f"{has_i('F1')}/{n} | {has_i('E1')}/{n} | {has_i('E2')}/{n} |")

    HEAD = ("| 组 | 路线 | 条数 | 每条镜头数中位 | 每条画面类型数中位 | 人物占时长 | 施工占时长 | 成品占时长 | 旧态占时长 | 有批刮镜头 | 有握手沟通镜头 | "
            "第一镜是人物对镜头 | 配画面落在爆款前 3 类 | 有效果句 | 有点赞请求 | 有咨询引导 |")
    SEP = "|" + "---|" * 16
    used = [r for r in rows if r["intent"] != "X0"]

    A("## 三、分人、分路线（全部抽样）")
    A("")
    A(HEAD)
    A(SEP)
    A(line("爆款", "-", ref))
    for person, route in ROUTE.items():
        rs = [r for r in used if r["person"] == person]
        if rs:
            A(line(person, route, rs))
    A(line("李康+彭书超", "自然语言合计", [r for r in used if r["person"] in ("李康", "彭书超")]))
    A(line("四人合计", "全部 AI 参与", [r for r in used if r["person"] not in cp.HAND]))
    A(line("三人合计", "新人手剪", [r for r in used if r["person"] in cp.HAND]))
    A("")

    A("## 四、只看文案来自库里的片子（把文案这个变量拿掉，只比选镜）")
    A("")
    A(HEAD)
    A(SEP)
    ref_in = {f"R{i:02d}" for i in range(1, 36)}
    A(line("爆款", "-", ref))
    for person, route in ROUTE.items():
        if person in cp.HAND:
            continue
        rs = [r for r in used if r["person"] == person and src_by[r["cid"]] != NONE]
        if rs:
            A(line(person, route, rs))
    rs = [r for r in used if r["person"] not in cp.HAND and src_by[r["cid"]] != NONE]
    A(line("四人合计·库内文案", "全部 AI 参与", rs))
    rs = [r for r in used if r["person"] not in cp.HAND and src_by[r["cid"]] == NONE]
    A(line("四人合计·库外文案", "全部 AI 参与", rs))
    A("")

    A("## 五、文案来源汇总")
    A("")
    A("| 人（路线） | 条数 | 同城标签 | 垂直陶泥 | 新文案 | 施工流程 | 库里没有 | 库内文案里有对标的 | 库内文案里与某条爆款同一段的 | 说教句占三成以上 |")
    A("|---|---|---|---|---|---|---|---|---|---|")

    def src_line(label, ids):
        cc = collections.Counter(src_by[k] for k in ids)
        none_ids = [k for k in ids if src_by[k] == NONE]
        inn = [k for k in ids if src_by[k] != NONE]
        return (f"| {label} | {len(ids)} | " + " | ".join(str(cc.get(k, 0)) for k in SECTIONS)
                + f" | {len(none_ids)}{'（' + '、'.join(none_ids) + '）' if none_ids else ''} | {sum(1 for k in inn if hl_by[k])}/{len(inn)} | "
                  f"{sum(1 for k in inn if proven_by[k])}/{len(inn)} | {'、'.join(k for k in ids if zz_by[k] >= 0.3) or '无'} |")

    allm = cp.load_list()
    for person, route in ROUTE.items():
        A(src_line(f"{person}（{route}）", [m["编号"] for m in allm if m["人"] == person]))
    A(src_line("四人合计（全部 AI 参与）", [m["编号"] for m in allm if m["人"] not in cp.HAND]))
    A(src_line("三人合计（新人手剪）", [m["编号"] for m in allm if m["人"] in cp.HAND]))
    text = "\n".join(L)
    print(text)
    if write:
        with io.open(os.path.join(cp.OUT, "按路线对比数字.md"), "x", encoding="utf-8") as f:
            f.write(text)
        print("WRITTEN")


if __name__ == "__main__":
    main("--write" in sys.argv)
