# -*- coding: utf-8 -*-
"""
三组对比：爆款 32 条 / AI 剪辑（陈翰文、张艺、李康、彭书超）/ 新人手剪（舒依玲、赵金忠、刘永添）

  python compare_groups.py            只在屏幕输出
  python compare_groups.py --write    另外新建 对照组镜头逐行标注.csv 和 对比数字.md（已存在则报错，不覆盖）
"""
import collections, csv, io, os, statistics, sys

sys.dont_write_bytecode = True
import control_pull as cp

bt = cp.bt
PEOPLE = {"V01", "V24", "V02"}
BUILD = {"V05", "V06", "V23", "V07", "V08", "V11", "V04", "V09", "V10", "V03"}
DONE = {"V13", "V14", "V15", "V16", "V17"}
DEMO = {"V18", "V19", "V20"}
LIB_THR = 0.5


def vname(v):
    return bt.VISUALS[v].split("（")[0]


def iname(i):
    return bt.INTENTS[i].split("（")[0]


def pct(a, b):
    return f"{a / b:.0%}" if b else "-"


def main(write):
    rows = cp.all_rows()
    missing = [r["key"] for r in rows if not r["visual"]]
    if missing:
        raise SystemExit(f"还有 {len(missing)} 个镜头没有画面标注，例如 {missing[:5]}")
    cm = cp.copy_match()
    ref = [r for r in cp.load_ref() if r["intent"] != "X0"]
    ai = [r for r in rows if r["intent"] != "X0" and r["person"] not in cp.HAND]
    hand = [r for r in rows if r["intent"] != "X0" and r["person"] in cp.HAND]
    groups = [("爆款", ref), ("AI剪辑", ai), ("新人手剪", hand)]
    L = []
    A = L.append

    def vids(rs):
        g = collections.defaultdict(list)
        for r in rs:
            g[r["cid"]].append(r)
        for v in g.values():
            v.sort(key=lambda r: r["idx"])
        return g

    A("# 对比数字（脚本生成，2026-11-14）")
    A("")
    A("| 组 | 条数 | 用于统计的镜头数 | 每条镜头数中位 | 单镜时长中位秒 |")
    A("|---|---|---|---|---|")
    for name, rs in groups:
        g = vids(rs)
        A(f"| {name} | {len(g)} | {len(rs)} | {statistics.median(len(v) for v in g.values()):.1f} | {statistics.median(r['dur'] for r in rs):.2f} |")
    A("")

    # 1. 文案来源
    A("## 一、文案来源")
    A("")
    A(f"相似度 = 这条片子机器转写里的二字组，有多少比例出现在对方文案里。{LIB_THR} 以上算同一条文案。")
    A("")
    A("| 编号 | 人 | 最像的文案库条目 | 相似度 | 最像的爆款 | 相似度 | 爆款里没有的句型占时长 | 开头（机器转写） |")
    A("|---|---|---|---|---|---|---|---|")
    zz_by = {}
    for m in cp.load_list():
        cid = m["编号"]
        rs = [r for r in rows if r["cid"] == cid and r["intent"] != "X0"]
        tot = sum(r["dur"] for r in rs)
        zz = sum(r["dur"] for r in rs if r["intent"] == "ZZ")
        zz_by[cid] = zz / tot if tot else 0
        d = cm[cid]
        A(f"| {cid} | {m['人']} | {d['lib'][1]} | {d['lib'][0]:.2f} | {d['ref'][1]} | {d['ref'][0]:.2f} | {zz_by[cid]:.0%} | {d['text'][:22]} |")
    A("")
    for name, test in (("AI剪辑", lambda p: p not in cp.HAND), ("新人手剪", lambda p: p in cp.HAND)):
        ids = [m["编号"] for m in cp.load_list() if test(m["人"])]
        nlib = sum(1 for c in ids if cm[c]["lib"][0] >= LIB_THR)
        nzz = sum(1 for c in ids if zz_by[c] >= 0.4)
        A(f"- {name} {len(ids)} 条：文案来自文案库 {nlib} 条，不是文案库的 {len(ids)-nlib} 条；其中“爆款里没有的句型”占时长四成以上的 {nzz} 条。")
    A("")

    # 2. 画面大类
    A("## 二、画面大类占时长")
    A("")
    A("| 组 | 人物（对镜头/在现场/握手沟通） | 其中 人物对镜头 | 施工过程 | 其中 批刮覆盖 | 成品 | 旧房旧态 | 演示（喷水/弯折/刮擦） | 外景及其他 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for name, rs in groups:
        t = sum(r["dur"] for r in rs)

        def s(codes):
            return pct(sum(r["dur"] for r in rs if r["visual"] in codes), t)

        A(f"| {name} | {s(PEOPLE)} | {s({'V01'})} | {s(BUILD)} | {s({'V05'})} | {s(DONE)} | {s({'V12'})} | {s(DEMO)} | {s({'V21', 'V22'})} |")
    A("")

    # 3. 画面类型明细
    A("## 三、画面类型明细（每条平均几个镜头 / 占时长 / 用到的片子）")
    A("")
    A("| 画面类型 | 爆款 每条 | AI 每条 | 手剪 每条 | 爆款 占时长 | AI 占时长 | 手剪 占时长 | 爆款 片数 | AI 片数 | 手剪 片数 |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for v in bt.VISUALS:
        cells1, cells2, cells3 = [], [], []
        any_ = False
        for name, rs in groups:
            g = vids(rs)
            a = [r for r in rs if r["visual"] == v]
            any_ = any_ or bool(a)
            cells1.append(f"{len(a)/len(g):.1f}")
            cells2.append(pct(sum(r["dur"] for r in a), sum(r["dur"] for r in rs)))
            cells3.append(f"{len({r['cid'] for r in a})}/{len(g)}")
        if any_:
            A(f"| {vname(v)} | " + " | ".join(cells1 + cells2 + cells3) + " |")
    A("")

    # 4. 句意配画面是否符合爆款习惯
    A("## 四、每句话配的画面，是否落在爆款常用的画面里")
    A("")
    A("对爆款里出现 10 个镜头以上的句意，取爆款最常配的前 3 类画面。下面是各组镜头落在这前 3 类里的比例（爆款自己的比例是上限参考）。")
    A("")
    top3 = {}
    for i in bt.INTENTS:
        a = [r for r in ref if r["intent"] == i]
        if len(a) >= 10 and i not in ("X0", "ZZ"):
            top3[i] = [v for v, _ in collections.Counter(r["visual"] for r in a).most_common(3)]
    A("| 组 | 可比镜头数 | 落在爆款前 3 类 |")
    A("|---|---|---|")
    for name, rs in groups:
        c = [r for r in rs if r["intent"] in top3]
        A(f"| {name} | {len(c)} | {pct(sum(1 for r in c if r['visual'] in top3[r['intent']]), len(c))} |")
    A("")
    A("| 句意 | 爆款前 3 类画面 | 爆款 命中 | AI 镜头数 | AI 命中 | AI 实际配的画面 | 手剪 镜头数 | 手剪 命中 | 手剪 实际配的画面 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for i, tv in top3.items():
        cells = []
        for name, rs in groups:
            c = [r for r in rs if r["intent"] == i]
            hit = pct(sum(1 for r in c if r["visual"] in tv), len(c))
            fb = "；".join(f"{vname(v)}({k})" for v, k in collections.Counter(r["visual"] for r in c).most_common(3))
            cells.append((len(c), hit, fb))
        A(f"| {iname(i)} | {'、'.join(vname(v) for v in tv)} | {cells[0][1]} | {cells[1][0]} | {cells[1][1]} | {cells[1][2]} | {cells[2][0]} | {cells[2][1]} | {cells[2][2]} |")
    A("")

    # 5. 句意出现率
    A("## 五、各句意出现在多少条片子里")
    A("")
    A("| 句意 | 爆款 | AI剪辑 | 新人手剪 |")
    A("|---|---|---|---|")
    for i in bt.INTENTS:
        if i == "X0":
            continue
        cells = []
        any_ = False
        for name, rs in groups:
            g = vids(rs)
            n = sum(1 for v in g.values() if any(r["intent"] == i for r in v))
            any_ = any_ or n > 0
            cells.append(f"{n}/{len(g)}（{pct(n, len(g))}）")
        if any_:
            A(f"| {'爆款里没有的句型' if i == 'ZZ' else iname(i)} | " + " | ".join(cells) + " |")
    A("")

    # 6. 开头结尾、整体
    A("## 六、开头、结尾和整体")
    A("")
    for name, rs in groups:
        g = vids(rs)
        n = len(g)
        kinds = [len({r["visual"] for r in v}) for v in g.values()]
        ppl = [sum(r["dur"] for r in v if r["visual"] in PEOPLE) / sum(r["dur"] for r in v) for v in g.values()]
        first = collections.Counter(v[0]["visual"] for v in g.values())
        last = collections.Counter(v[-1]["visual"] for v in g.values())
        fi = collections.Counter(v[0]["intent"] for v in g.values())
        firstd = [v[0]["dur"] for v in g.values()]
        lastd = [v[-1]["dur"] for v in g.values()]
        A(f"- **{name}**（{n} 条）")
        A(f"  - 每条用到的画面类型数：中位 {statistics.median(kinds):.0f}（最少 {min(kinds)}，最多 {max(kinds)}）")
        A(f"  - 人物镜头占时长：中位 {statistics.median(ppl):.0%}；超过一半时长是人物的片子 {sum(1 for x in ppl if x > 0.5)}/{n}")
        A(f"  - 第一镜时长中位 {statistics.median(firstd):.2f} 秒；画面：{'；'.join(f'{vname(v)}({c})' for v, c in first.most_common())}")
        A(f"  - 开头句意：{'；'.join(f'{iname(i) if i != chr(90)*2 else chr(29190)+chr(27454)+chr(37324)+chr(27809)+chr(26377)+chr(30340)+chr(21477)+chr(22411)}({c})' for i, c in fi.most_common())}")
        A(f"  - 最后一镜时长中位 {statistics.median(lastd):.2f} 秒；画面：{'；'.join(f'{vname(v)}({c})' for v, c in last.most_common())}")
        for code in ("V05", "V13", "V11", "V12", "V08"):
            A(f"  - 有「{vname(code)}」的片子：{sum(1 for v in g.values() if any(r['visual'] == code for r in v))}/{n}")
    A("")

    # 7. 分人
    A("## 七、分人")
    A("")
    A("| 人 | 组 | 条数 | 镜头数 | 人物占时长 | 施工占时长 | 成品占时长 | 落在爆款前 3 类 | 最多的四类画面 |")
    A("|---|---|---|---|---|---|---|---|---|")
    for person in list(cp.QUOTA):
        rs = [r for r in rows if r["intent"] != "X0" and r["person"] == person]
        if not rs:
            continue
        t = sum(r["dur"] for r in rs)
        c = [r for r in rs if r["intent"] in top3]
        top = "；".join(f"{vname(v)}({k})" for v, k in collections.Counter(r["visual"] for r in rs).most_common(4))
        A(f"| {person} | {'新人手剪' if person in cp.HAND else 'AI剪辑'} | {len({r['cid'] for r in rs})} | {len(rs)} | "
          f"{pct(sum(r['dur'] for r in rs if r['visual'] in PEOPLE), t)} | {pct(sum(r['dur'] for r in rs if r['visual'] in BUILD), t)} | "
          f"{pct(sum(r['dur'] for r in rs if r['visual'] in DONE), t)} | {pct(sum(1 for r in c if r['visual'] in top3[r['intent']]), len(c))} | {top} |")
    text = "\n".join(L)
    print(text)
    if write:
        with io.open(os.path.join(cp.OUT, "对照组镜头逐行标注.csv"), "x", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["编号", "组", "人", "账号文件夹", "镜头序号", "开始秒", "结束秒", "时长秒", "口播(机器转写)", "句意码", "句意",
                        "画面码", "画面类型", "句意标注方式", "相对路径"])
            for r in rows:
                w.writerow([r["cid"], "新人手剪" if r["person"] in cp.HAND else "AI剪辑", r["person"], r["account"], r["idx"],
                            f"{r['start']:.2f}", f"{r['end']:.2f}", f"{r['dur']:.2f}", r["text"], r["intent"], bt.INTENTS[r["intent"]],
                            r["visual"], bt.VISUALS[r["visual"]], r["src"], r["rel"]])
        with io.open(os.path.join(cp.OUT, "对比数字.md"), "x", encoding="utf-8") as f:
            f.write(text)
        print("WRITTEN")


if __name__ == "__main__":
    main("--write" in sys.argv)
