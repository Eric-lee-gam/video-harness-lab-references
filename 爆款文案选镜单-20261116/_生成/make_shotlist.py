# -*- coding: utf-8 -*-
"""
爆款文案选镜单：文案库里被爆款用过的段落，逐句列出爆款实际配的画面、镜头数和时长。只读输入。

  python make_shotlist.py            只在屏幕输出
  python make_shotlist.py --write    另外新建 ..\\爆款文案选镜单.md 和 ..\\选镜单逐镜头对齐.csv（已存在则报错，不覆盖）

输入：
  文案库      C:\\Users\\leega\\Downloads\\赋能计划文案最新(2).docx
  爆款逐镜头  ..\\..\\句意画面对照表-20261114\\镜头逐行标注.csv（字幕、句意、画面类型）
做法：
  1. 每条爆款的字幕拼起来，和文案库每一段比二字组重合，0.5 以上算用了这一段。
  2. 文案按标点拆成句，每个镜头按字幕对到最像的一句上（优先顺着往下找）。
  3. 每句汇总：几条爆款里有这句、每条用几个镜头、多长、配了哪些画面。
"""
import collections, csv, io, os, re, statistics, sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
REFS = os.path.dirname(OUT)
sys.path.insert(0, os.path.join(REFS, "对照组拉片-20261114", "_生成"))
import compare_routes as cr

SHOTS = os.path.join(REFS, "句意画面对照表-20261114", "镜头逐行标注.csv")
THR = 0.5
PEOPLE = {"V01", "V24", "V02"}


DIGITS = str.maketrans("0123456789", "〇一二三四五六七八九")


def grams(text):
    """二字组；数字先换成汉字，避免“3天”和“三天”对不上。"""
    return cr.grams((text or "").translate(DIGITS).replace("〇", "0"))


def short(name):
    if name.startswith("其他"):
        return "其他（模糊画面、叠大字等）"
    return re.sub(r"[（(].*$", "", name).strip()


def load_shots():
    vids = collections.OrderedDict()
    for r in csv.DictReader(io.open(SHOTS, encoding="utf-8-sig")):
        vids.setdefault(r["参考片"], []).append({
            "idx": int(r["镜头序号"]), "dur": float(r["时长秒"]), "text": r["字幕/口播"], "intent": r["句意码"],
            "intent_name": short(r["句意"]), "visual": r["画面码"], "visual_name": short(r["画面类型"])})
    return vids


def clauses(text):
    parts = [p for p in re.split(r"[。，！？；：,.!?;:\s]+", text) if p]
    parts = [p for p in parts if not re.fullmatch(r"文案\d+|\d+", p)]
    out, buf = [], ""
    for p in parts:
        buf += p
        if len(buf) >= 5:
            out.append(buf)
            buf = ""
        else:
            buf += "，"
    if buf:
        if out:
            out[-1] += "，" + buf.rstrip("，")
        else:
            out.append(buf.rstrip("，"))
    return out


def align(shots, cl):
    """每个镜头对到一句上（对不上为 -1），并给出这个镜头里顺带说完的其它句。
    返回 [(主句序号, [顺带句序号…])]"""
    cg = [grams(c) for c in cl]
    res, prev = [], 0
    for s in shots:
        g = grams(s["text"])
        if not g:
            res.append((-1, []))
            continue
        a = [len(g & c) / len(g) for c in cg]                      # 镜头字幕有多少落在这句里
        b = [len(g & c) / len(c) if len(c) >= 3 else 0 for c in cg]  # 这句有多少被镜头字幕说到
        sc = [max(x, y) for x, y in zip(a, b)]
        win = [j for j in range(len(cl)) if prev - 1 <= j <= prev + 3]
        bj = max(win, key=lambda j: (round(sc[j], 3), -abs(j - prev), -j))
        if sc[bj] < 0.25:
            gj = max(range(len(cl)), key=lambda j: sc[j])
            bj = gj if sc[gj] >= 0.6 else -1
        also = [j for j in range(len(cl)) if bj >= 0 and j != bj and abs(j - bj) <= 2 and b[j] >= 0.6]
        res.append((bj, also))
        if bj >= 0:
            prev = max([bj] + also)
    return res


def main(write):
    lib = cr.load_sections(cr.LIB)
    vids = load_shots()
    use = collections.defaultdict(list)
    score = {}
    for vid, shots in vids.items():
        body = [s for s in shots if s["intent"] != "X0"]
        g = grams("".join(s["text"] for s in body))
        sc = sorted(((len(g & grams(t)) / max(1, len(g)), i) for i, _, _, t, _ in lib), reverse=True)
        score[vid] = sc[:2]
        if sc[0][0] >= THR:
            use[sc[0][1]].append(vid)
    para = {i: (sec, hl, t) for i, sec, hl, t, _ in lib}

    def twin(i, k):
        a, b = grams(para[i][2]), grams(para[k][2])
        return min(len(a & b) / len(a), len(a & b) / len(b)) >= 0.7

    # 同一段的不同版本算一套
    fam = {i: i for i in use}
    for i in use:
        for k in use:
            if i < k and twin(i, k):
                fam[k] = fam[i]
    n_fam = len(set(fam.values()))
    used_vids = [v for vs in use.values() for v in vs]
    bodies_all = [[s for s in vids[v] if s["intent"] != "X0"] for v in used_vids]
    nv = len(used_vids)

    def cnt_txt(c):
        return "、".join(f"{k} {v}" for k, v in c.most_common())

    L, rows_out = [], []
    A = L.append
    A("# 爆款文案选镜单（脚本生成，2026-11-16）")
    A("")
    A("文案库里被爆款用过的段落，逐句列出爆款实际配了什么画面。由 AI 完成，没有人工核对。")
    A("")
    A(f"- 32 条爆款里，{nv} 条的字幕能对上文案库的某一段，集中在 {len(use)} 段上"
      + (f"（其中有同一段的不同版本，合并后是 {n_fam} 套文案）" if n_fam != len(use) else "")
      + f"；其余 {len(vids) - nv} 条的文案不在库里，这份单子不覆盖。")
    A("- 文案库：`C:\\Users\\leega\\Downloads\\赋能计划文案最新(2).docx`，“第几段”是去掉小标题后从头数的段落序号。")
    A("- “有这句”= 用这段文案的几条爆款里，有几条说了这一句。“镜头数”“秒数”是有这句的片子里的中位数。")
    A("- “配的画面”后面的数字是镜头个数，几条片子加在一起。")
    A("- 只有 1 条爆款用过的段落，只能当一个例子看。")
    A("- 画面类型的定义见 `..\\句意画面对照表-20261114\\句意画面对照表.md`。表里没有的文案，按那份表的句意去查。")
    A("")
    A(f"## 这 {nv} 条的共同点")
    A("")
    ns = [len(b) for b in bodies_all]
    per = [s["dur"] for b in bodies_all for s in b]
    A(f"- 每条 {min(ns)}–{max(ns)} 个镜头，中位 {statistics.median(ns):g} 个；单个镜头中位 {statistics.median(per):.2f} 秒，"
      f"{sum(1 for d in per if d > 3) / len(per):.0%} 的镜头超过 3 秒。")
    A(f"- 第一个镜头：{cnt_txt(collections.Counter(b[0]['visual_name'] for b in bodies_all))}。")
    A(f"- 最后一个镜头：{cnt_txt(collections.Counter(b[-1]['visual_name'] for b in bodies_all))}。")
    pg = [sum(1 for s in b if s["visual"] == "V05") for b in bodies_all]
    A(f"- 批刮镜头：{sum(1 for x in pg if x)}/{nv} 条有，每条中位 {statistics.median(pg):g} 个。")
    for label, codes in (("握手/与客户沟通", {"V02"}), ("演示（喷水、弯折、刮擦）", {"V18", "V19", "V20"}),
                         ("成品里有人、手摸成品或成品清洁", {"V15", "V16", "V17"}), ("拆砸/贴砖（传统做法）", {"V08"})):
        A(f"- {label}：{sum(1 for b in bodies_all if any(s['visual'] in codes for s in b))}/{nv} 条有。")
    extra_n = 0
    for i in use:
        cl0 = clauses(re.sub(r"^文案\d+：", "", para[i][2]))
        for v in use[i]:
            body = [s for s in vids[v] if s["intent"] != "X0"]
            extra_n += sum(1 for s, (j, _) in zip(body[1:], align(body, cl0)[1:]) if j < 0)
    A(f"- 文案基本照原文念，只换城市和人名：除去带封面字的第一个镜头，{sum(ns) - nv} 个镜头里只有 {extra_n} 个的字幕对不上原文。")
    A("")
    A("## 总览")
    A("")
    A("| 段落 | 所在节 | 开头 | 用过的爆款 | 每条镜头数 | 每条时长（秒） | 每镜头中位（秒） |")
    A("|---|---|---|---|---|---|---|")
    order = sorted(use, key=lambda i: (-len(use[i]), i))
    for i in order:
        sec, hl, t = para[i]
        bodies = [[s for s in vids[v] if s["intent"] != "X0"] for v in use[i]]
        ns = [len(b) for b in bodies]
        ds = [sum(s["dur"] for s in b) for b in bodies]
        per = [s["dur"] for b in bodies for s in b]
        head = re.sub(r"^文案\d+：", "", t)[:16]
        A(f"| 第{i}段 | {sec} | {head}… | {len(use[i])} 条（{'、'.join(use[i])}） | "
          f"{min(ns)}–{max(ns)}" + f" | {min(ds):.0f}–{max(ds):.0f} | {statistics.median(per):.2f} |")
    A("")

    for i in order:
        sec, hl, t = para[i]
        t = re.sub(r"^文案\d+：", "", t)
        cl = clauses(t)
        n = len(use[i])
        A(f"## 第{i}段（{sec}，{n} 条爆款用过：{'、'.join(use[i])}）")
        A("")
        A("> " + t)
        A("")
        gi = grams(t)
        twins = [k for k, _, _, tk, _ in lib if k != i and min(len(gi & grams(tk)) / len(gi), len(gi & grams(tk)) / len(grams(tk))) >= 0.7]
        if twins:
            A(f"文案库里和它几乎相同的段落：{'、'.join(f'第{k}段' for k in twins)}（同一段的不同版本，算作同一段）。")
            A("")
        per_clause = collections.defaultdict(lambda: collections.defaultdict(list))
        riders = collections.defaultdict(lambda: collections.defaultdict(set))
        extra, firsts, lasts = [], [], []
        for v in use[i]:
            body = [s for s in vids[v] if s["intent"] != "X0"]
            al = align(body, cl)
            firsts.append(body[0]["visual_name"])
            lasts.append(body[-1]["visual_name"])
            for s, (j, also) in zip(body, al):
                rows_out.append([f"第{i}段", v, s["idx"], f"{s['dur']:.2f}", s["text"], (j + 1) if j >= 0 else "", cl[j] if j >= 0 else "",
                                 "、".join(str(k + 1) for k in also), s["intent_name"], s["visual_name"]])
                if j < 0:
                    extra.append((v, s))
                else:
                    per_clause[j][v].append(s)
                    for k in also:
                        riders[k][v].add(j)
        A("| 句 | 文案原句 | 有这句 | 镜头数 | 秒数 | 配的画面 |")
        A("|---|---|---|---|---|---|")
        for j, c in enumerate(cl):
            pv = per_clause.get(j, {})
            rd = {v: ks for v, ks in riders.get(j, {}).items() if v not in pv}
            have = len(pv) + len(rd)
            note = ""
            if rd:
                ks = sorted({k for s in rd.values() for k in s})
                note = f"{len(rd)} 条是和第 {'、'.join(str(k + 1) for k in ks)} 句在同一个镜头里说完"
            if not pv:
                A(f"| {j + 1} | {c} | {have}/{n} | - | - | {note or '用这段的爆款都没说这句'} |")
                continue
            cnt = collections.Counter(s["visual_name"] for ss in pv.values() for s in ss)
            A(f"| {j + 1} | {c} | {have}/{n} | {statistics.median(len(ss) for ss in pv.values()):g} | "
              f"{statistics.median(sum(s['dur'] for s in ss) for ss in pv.values()):.1f} | "
              f"{'、'.join(f'{k} {v}' for k, v in cnt.most_common())}{'；另有 ' + note if note else ''} |")
        A("")
        A(f"- 第一个镜头：{'、'.join(f'{k} {v}' for k, v in collections.Counter(firsts).most_common())}")
        A(f"- 最后一个镜头：{'、'.join(f'{k} {v}' for k, v in collections.Counter(lasts).most_common())}")
        if extra:
            A("- 没对上原文的镜头（片子自己改写或加的句子）：")
            for v, s in extra:
                A(f"  - {v} 第{s['idx']}镜「{s['text']}」→ {s['visual_name']}")
        A("")

    A("## 附：每条爆款最像的两段（核对用）")
    A("")
    A("| 片号 | 最像 | 相似度 | 第二像 | 相似度 |")
    A("|---|---|---|---|---|")
    for vid, sc in score.items():
        A(f"| {vid} | 第{sc[0][1]}段 | {sc[0][0]:.2f} | 第{sc[1][1]}段 | {sc[1][0]:.2f} |")
    text = "\n".join(L)
    print(text)
    if write:
        with io.open(os.path.join(OUT, "爆款文案选镜单.md"), "x", encoding="utf-8") as f:
            f.write(text)
        with io.open(os.path.join(OUT, "选镜单逐镜头对齐.csv"), "x", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["段落", "爆款片号", "镜头序号", "时长秒", "字幕", "对到第几句", "文案原句", "同镜头里顺带说完的句", "句意", "画面类型"])
            w.writerows(rows_out)
        print("WRITTEN")


if __name__ == "__main__":
    main("--write" in sys.argv)
