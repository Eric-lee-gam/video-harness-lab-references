# -*- coding: utf-8 -*-
"""
句意 → 画面类型 对照表生成脚本（2026-11-14）

输入（只读）：references/analysis/R01..R35/analysis.json 里已有的拉片镜头行
输出（只新建，不覆盖）：
  句意画面对照表.md      人看的汇总
  镜头逐行标注.csv        每个镜头的句意、画面类型，供人工改正

用法：
  python build_table.py --review            只在屏幕输出逐行分类，不写文件
  python build_table.py --out <新文件夹>    生成文件（文件已存在则报错，不覆盖）

分类方式：关键词规则初分 + AI 逐行通读核对后的改正表（没有人工看过）。
"""
import argparse, collections, csv, io, json, os, re, statistics, sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REL = os.path.normpath(os.path.join(_HERE, "..", "..", "analysis"))
BASE = _REL if os.path.isdir(_REL) else r"D:\codex-work\codex-company\video-harness-lab\references\analysis"

# 同一条视频的重复拉片：只保留一份
EXCLUDE = {
    "R13": "与 R12 逐字节相同",
    "R07": "与 R17 音视频流完全相同（封装不同）",
    "R32": "与 R22 音视频流完全相同（封装不同）",
}

# ---------- 句意 ----------
COVER = re.compile(
    r"(旧房翻新$|微陶泥翻新$|旧房改造$|换新家|极简风|^坐标|Materialsunion|即装即租|快速改造|7天翻新"
    r"|^不拆不砸$|奶油风|首创|极简翻新|旧改翻新|^微陶泥$|卫生间瓷砖不拆不砸|^[\u4e00-\u9fff]{2}$)"
)

INTENTS = collections.OrderedDict([
    ("H1", "开头·趋势预测/疑问"),
    ("H2", "开头·行业冲突"),
    ("H3", "开头·亲情故事"),
    ("H4", "开头·人设吸引/喊停留"),
    ("H5", "开头·生活体验"),
    ("H6", "开头·价格范围"),
    ("H7", "开头·团队到来"),
    ("K1", "点名空间/旧房（卫生间、厨房、老房子）"),
    ("S1", "找谁做（人物/团队引入）"),
    ("B1", "工法·不拆不砸/直接覆盖/批刮步骤"),
    ("M1", "材料指认（这款微陶泥/一桶/开桶）"),
    ("T1", "工期/完工即用（3天、7天、当天）"),
    ("C1", "价格数字（万把块、几千块）"),
    ("C2", "省钱（省拆除/垃圾/人工/瓷砖钱）"),
    ("C3", "同行高价对比（其他公司十几万）"),
    ("F1", "效果外观（一体无缝/极简/亮堂/焕然一新）"),
    ("P1", "性能·防水防霉防潮"),
    ("P2", "性能·耐磨/硬度/不开裂"),
    ("P3", "易清洁（没有瓷砖缝/污渍好打理）"),
    ("P4", "耐久（用几十年）"),
    ("P5", "环保/放心住"),
    ("S2", "省心主张（不用搬家/不用操心/一站式）"),
    ("S3", "服务步骤（保护/铲修/涂刷/水电/保洁/全包）"),
    ("S6", "上门量房/报价/出方案"),
    ("E0", "结尾·点赞铺垫/理由（如果你也喜欢…/以后用得上）"),
    ("E1", "结尾·点赞请求（点个小爱心）"),
    ("E2", "结尾·咨询引导（点头像/留言/直接找）"),
    ("X0", "封面卡/闪帧/黑帧（不计入统计）"),
    ("ZZ", "未归类"),
])

# 任一分句命中即优先
ANY_CLAUSE = [
    ("E1", r"小爱心|小红心|点个赞|大拇指|只要你给这|请帮我点|^免费的小"),
    ("S1", r"都在找|都找|在找|找了.{0,8}团队"),
]
# 按分句顺序，第一个有命中的分句决定句意；分句内按下列顺序匹配
CLAUSE_RULES = [
    ("E2", r"点击头像|哪个位置|评论留下|有需要请直接找|如果您家也需要"),
    ("S6", r"上门|合理报价|出方案"),
    ("E0", r"如果你也喜欢|如果你喜欢|如果您刷到|如果你看到|刷到这条视频|这种(翻新)?(工艺|方式)|^翻新工艺$"
           r"|总有一天会用上|以后一定用得上|找不到|老乡|如果你不相信"),
    ("B1", r"不拆不砸|直接覆盖|直接批刮|直接壁刮|直接劈挂|不用敲|不会再砸|不砸瓷砖|不用瓷砖|老旧瓷砖上"
           r"|原瓷砖|瓷砖直接|先滚涂底漆|腻子墙面|批刮3|皮刮3"),
    ("H3", r"阿姨|做梦都想不到|出去旅游|旅游这几天|趁他们"),
    ("H4", r"女人|都想嫁|改造大王|喜讯|停留|遇到我"),
    ("H5", r"小区火了|邻居说"),
    ("H2", r"失业|卖不出去|当傻子|不会去找装修公司|新房子"),
    ("H7", r"来了一支|最省心省钱|旧房改造团队"),
    ("C3", r"其他装修公司|十几万"),
    ("S3", r"家具地板保护|铲修旧墙|刷上环保材料|卫生都打扫|最后的卫生|都不用你操心|水电|人工材料|全包"),
    ("S2", r"不用搬家|不用操心|不用您动|一站式"),
    ("M1", r"这款|这个微陶泥|金刚陶泥|金刚泥|一桶|出厂|开桶|打开桶|^微陶泥$|微陶泥翻新工艺|做微陶泥|个平方|公斤|注意看"),
    ("P5", r"甲醛|VOC|无异味|环保|放心住"),
    ("T1", r"\d+天|三天|两天|当天|72小时|即可入住|即可使用|就能入住|正常使用"),
    ("C1", r"万把块|几千块|1到2万|几千到两万|不到1万|亲民"),
    ("P3", r"瓷砖缝|污渍|油渍|好打理|好清理|扫地机|日常打扫"),
    ("P1", r"耐水|防霉|防潮|回南天|防水|发霉|发黄|再也没有"),
    ("P2", r"耐磨|耐刮|耐摩擦|硬度|韧性|不开裂|不会开裂|起皮|耐擦|高强|用在地上"),
    ("P4", r"几十年|20年|用上"),
    ("F1", r"一体无缝|无缝一体|极简|高级|温馨风|亮亮堂堂|焕然一新|美观|氛围感|光滑平整|更显大|好看"
           r"|从这样改成|漂亮|踢脚线|打造一个|刮完的墙面地面|做完效果|就能打造"),
    ("C2", r"省|拆除|运垃圾|搬运垃圾|人工费|不用买瓷砖|便宜|费时费力|费用"),
    ("H1", r"再过|你会发现|家家户户|越来越多|为什么现在|过不了多久|都流行|现在翻新一个|太简单|你会看到"),
]
WEAK = [("K1", r"卫生间|厨房|洗手间|老房|你家")]

# ---------- 画面类型 ----------
VISUALS = collections.OrderedDict([
    ("V01", "人物对镜头（讲话/手势）"),
    ("V24", "人物在现场（不看镜头：查看、站、走）"),
    ("V02", "握手/与客户沟通"),
    ("V03", "团队上门/搬料搬物"),
    ("V04", "量房/水电/安装"),
    ("V05", "施工·批刮覆盖（抹刀/刮板）"),
    ("V06", "施工·滚涂"),
    ("V23", "施工现场·其他（工人在场、打磨、基面）"),
    ("V07", "铲修旧墙/旧顶"),
    ("V08", "拆砸/贴砖（传统做法）"),
    ("V09", "铺保护膜/贴胶带"),
    ("V10", "保洁/清扫（施工前后）"),
    ("V11", "材料桶（取料/搅拌/桶特写）"),
    ("V12", "旧房旧态"),
    ("V13", "成品空间（空镜）"),
    ("V14", "旧→新同镜转场"),
    ("V15", "成品里的人（坐、走、小孩、开门）"),
    ("V16", "手摸/手指成品"),
    ("V17", "成品日常清洁（拖地/刮水器/扫地机）"),
    ("V18", "演示·喷水冲洗"),
    ("V19", "演示·弯折样板/揭薄层"),
    ("V20", "演示·刮擦/擦污"),
    ("V21", "老楼/城市外景"),
    ("V22", "其他（模糊画面、细节特写、故事人物等）"),
])

VIS_RULES = [
    ("V22", r"模糊|虚焦|纸币"),
    ("V19", r"弯折|弯曲|弯成"),
    ("V18", r"喷水|喷淋|水流|冲洗|花洒对着|喷出"),
    ("V20", r"纸巾|擦拭.*污|污迹减少|摩擦|刮动|锤头|钥匙|工具尖端|硬物"),
    ("V17", r"拖地|刮水器|刮水工具|扫地机|清洁设备|清洁头"),
    ("V14", r"叠化到|→|遮罩"),
    ("V04", r"量尺|测量|长尺|切槽|水平尺|红绿|定位马桶|马桶后侧"),
    ("V02", r"握手|交流|沟通|交谈|看纸|面对面|比划|展示纸张|同框"),
    ("V03", r"搬|提.{0,4}桶|纸箱|后备箱|尾箱|平板车|货车|楼道|楼梯|上楼|入户|电梯|前行|行走|同行|抬/挪|移动床"),
    ("V01", r"(?<!背)面向镜头|面对镜头|(?<!背)向镜头|(?<!背)对镜头|朝镜头|看镜头|看向镜头|讲解|讲话"),
    ("V07", r"铲|刮除|刮下|剥落|起皮"),
    ("V08", r"拆|砸|碎料|碎砖|碎片|敲|拉倒|持锤|机械设备|地面机器|摆放大块白瓷砖|瓷砖背面"),
    ("V06", r"滚筒|滚涂"),
    ("V09", r"保护膜|贴保护胶带|贴黄色胶带|揭下保护"),
    ("V10", r"扫帚|清扫|吸尘|抹布|擦.{0,8}(桌|柜|台面|抽屉)|清洁者|清洁人员|刷洗|扫旧|装进袋|装入大袋"),
    ("V11", r"桶内|桶口|桶里|桶中|搅拌|舀|取料|取浅色膏体|桶近景|衬桶"),
    ("V05", r"批刮|抹刀|抹板|刮板|刮平|摊|覆盖|覆到|刮涂|铺展|刮到|刮盖|刮料|压平|推平|推进|抹墙|抹地|抹浅|抹白"
            r"|抹面|抹平|抹拱|抹竖|抹台盆|抹料|处理(浅墙|白色|弧形|天花|表面|边角|墙面|斑纹|瓷砖墙|壁面)|黄色工具|黄色大抹"),
    ("V21", r"航拍|居民楼|老小区|旧楼|老楼|住宅楼|楼房街巷|城市建筑|城市大道|河畔|外立面|古建筑"),
    ("V16", r"第一视角|主观|触摸|抚摸|手触|摸浅色|擦摸|前景手掌|前景手指|镜头前手指|手在浅色地面"),
    ("V15", r"沙发上|坐沙发|看电视|儿童|小孩|躺|窗边台面|坐在窗边|开门|跑入|走入有|走入完成|坐粉色|浴缸卫生间"
            r"|立于浅色浴室|持.{0,2}花洒|拿淋浴头|在极简客厅|冰箱前|坐在椅子"),
    ("V24", r"男子|女子|男在|黑衣男|人物|团队|两男|三男|年长"),
    ("V23", r"工人"),
    ("V12", r"旧|老旧|脏污|破旧|发黄|黑黄"),
    ("V13", r"成品|完成|完工|浅色|现代|明亮|暖光|灯带|镜柜|壁龛|空房|连续墙|洗手台"),
]

# ---------- AI 逐行核对后的改正：{"R01#1": (句意码或None, 画面码或None)} ----------
OVERRIDE = {}


# 原拉片把同一个连续镜头拆成了多行：合并到首行（值为要并入的最后一个镜头序号）
MERGE = {"R29#2": 4}


def load_override(path):
    """改正表.csv：行,句意码,画面码,说明（句意码或画面码留空表示不改）"""
    if path and os.path.exists(path):
        with io.open(path, encoding="utf-8-sig", newline="") as f:
            for i, row in enumerate(csv.reader(f)):
                if i == 0 or not row or not row[0].strip():
                    continue
                row = [x.strip() for x in row] + ["", ""]
                if row[1] and row[1] not in INTENTS:
                    raise SystemExit(f"改正表里的句意码不存在: {row}")
                if row[2] and row[2] not in VISUALS:
                    raise SystemExit(f"改正表里的画面码不存在: {row}")
                OVERRIDE[row[0]] = (row[1] or None, row[2] or None)


def split_clauses(text):
    text = re.sub(r"（[\d.]+）", "", text or "")
    out = []
    for c in re.split(r"[／；]", text):
        c = re.sub(r"^(首帧|随后)[：:]?", "", c.strip()).strip()
        if c:
            out.append(c)
    return out


def classify_intent(rid, idx, dur, text):
    if "未见" in (text or ""):
        return "X0"
    cl = split_clauses(text)
    if idx <= 2 and dur < 0.3:
        return "X0"
    if idx == 1:
        cl = [c for c in cl if not COVER.search(c)]
        if not cl:
            return "X0"
    for code, pat in ANY_CLAUSE:
        if any(re.search(pat, c) for c in cl):
            return code
    for c in cl:
        for code, pat in CLAUSE_RULES:
            if re.search(pat, c):
                return code
    for c in cl:
        for code, pat in WEAK:
            if re.search(pat, c):
                return code
    return "ZZ"


def classify_visual(obs):
    for code, pat in VIS_RULES:
        if re.search(pat, obs or ""):
            return code
    return "V22"


def load_rows():
    rows = []
    for i in range(1, 36):
        rid = f"R{i:02d}"
        if rid in EXCLUDE:
            continue
        d = json.load(io.open(os.path.join(BASE, rid, "analysis.json"), encoding="utf-8"))
        shots = d.get("shots", [])
        skip_until = 0
        for s in shots:
            vt = s.get("visible_text")
            if isinstance(vt, list):
                vt = "；".join(str(x) for x in vt)
            vt = vt or ""
            st, en = float(s["start"]), float(s["end"])
            idx = int(s.get("index"))
            key = f"{rid}#{idx}"
            if idx <= skip_until:
                continue
            if key in MERGE:
                skip_until = MERGE[key]
                en = max(float(x["end"]) for x in shots if idx <= int(x.get("index")) <= skip_until)
            it = classify_intent(rid, idx, 9.0 if key in MERGE else en - st, vt)
            vs = classify_visual(s.get("observation"))
            src = "规则"
            if key in OVERRIDE:
                a, b = OVERRIDE[key]
                if a:
                    it = a
                if b:
                    vs = b
                src = "核对后改"
            rows.append(dict(key=key, rid=rid, idx=idx, n=len(shots), start=st, end=en, dur=en - st,
                             text=vt, obs=s.get("observation") or "", purpose=s.get("purpose") or "",
                             intent=it, visual=vs, src=src, source_name=d.get("source_name"),
                             vdur=float(d.get("duration") or 0)))
    return rows


def review(rows, counts_only=False):
    for r in rows:
        if counts_only and r["intent"] != "ZZ" and r["src"] != "核对后改":
            continue
        print(f"{r['key']}|{r['intent']}|{r['visual']}|{r['src'][0]}|{r['text'][:26]}|{r['obs'][:34]}")
    c1 = collections.Counter(r["intent"] for r in rows)
    c2 = collections.Counter(r["visual"] for r in rows)
    print("---")
    print(" ".join(f"{k}:{v}" for k, v in sorted(c1.items())))
    print(" ".join(f"{k}:{v}" for k, v in sorted(c2.items())))
    bad = [k for k in OVERRIDE if k not in {r["key"] for r in rows}]
    if bad:
        print("改正表里有不存在的行:", bad)


def med(xs):
    return statistics.median(xs) if xs else 0


def fmt_t(x):
    return f"{x:.1f}"


def build(rows, out, summary):
    os.makedirs(out, exist_ok=True)
    used = [r for r in rows if r["intent"] != "X0"]
    vids = sorted({r["rid"] for r in rows})
    nv = len(vids)

    # CSV
    with io.open(os.path.join(out, "镜头逐行标注.csv"), "x", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["参考片", "镜头序号", "开始秒", "结束秒", "时长秒", "字幕/口播", "画面描述(原拉片)",
                    "句意码", "句意", "画面码", "画面类型", "标注方式", "原文件"])
        for r in rows:
            w.writerow([r["rid"], r["idx"], f"{r['start']:.2f}", f"{r['end']:.2f}", f"{r['dur']:.2f}", r["text"],
                        r["obs"], r["intent"], INTENTS[r["intent"]], r["visual"], VISUALS[r["visual"]], r["src"],
                        r["source_name"]])

    L = []
    A = L.append
    durs = [r["dur"] for r in used]
    per_video = collections.Counter(r["rid"] for r in used)
    n_over = sum(1 for r in rows if r["src"] == "核对后改")
    n_zz = sum(1 for r in used if r["intent"] == "ZZ")

    def top_vis(rs, k=4):
        c = collections.Counter(r["visual"] for r in rs)
        return c.most_common(k), len(rs)

    A("# 句意 → 画面类型 对照表（来自 32 条爆款参考片的现有拉片）")
    A("")
    A("生成日期：2026-11-14。数据来源是 `references/analysis/R01–R35` 里 10 月 1 日已完成的拉片，没有重新拉片，也没有改动任何原文件。")
    A("")
    A("## 先看结论")
    A("")
    A(summary)
    A("")
    A("## 数据口径与限制")
    A("")
    A(f"- 模板库 35 个文件，按音视频流比对后独立内容是 **{nv} 条**。除了已知的 R12/R13，R07 与 R17、R22 与 R32 也是同一条视频（封装不同），各保留一份。")
    A(f"- 32 条共 {len(rows)} 个镜头行，去掉封面卡、闪帧、黑尾帧后用于统计的是 **{len(used)} 行**。")
    A(f"- 分类方式：关键词规则初分，再由 AI 逐行通读核对并改正 {n_over} 行，仍未归类 {n_zz} 行。**没有人工看过这些分类。** 逐行结果在同目录 `镜头逐行标注.csv`，改正记录在 `_生成/改正表.csv`。")
    A("- 原拉片是 0.5 秒抽帧加机器语音转写，没有人连续看过全片。镜头边界是约值，很短的镜头可能漏掉。")
    A("- 画面类型是按原拉片的文字描述归类的，AI 只看了 1 张抽帧图（R17 约 4 秒处），没有逐个核对画面。")
    A("- 镜头在句子中间切换时，一个镜头只归到它开始时正在说的那一句。")
    A("- 这些片子是 Eric 认定的高播放量视频，没有平台原始数据，也没有数据差的对照组。本表说明的是“爆款实际怎么配画面”，不能证明“这样配所以爆”。")
    A("")
    A("## 一、节奏")
    A("")
    A(f"- 每条视频镜头数：最少 {min(per_video.values())}，中位 {med(list(per_video.values())):.0f}，最多 {max(per_video.values())}。")
    sd = sorted(durs)
    A(f"- 单个镜头时长：中位 {med(durs):.2f} 秒；10% 的镜头短于 {sd[int(len(sd)*0.1)]:.2f} 秒，90% 短于 {sd[int(len(sd)*0.9)]:.2f} 秒；最长 {sd[-1]:.2f} 秒。")
    A(f"- 不超过 1 秒的镜头占 {sum(1 for x in durs if x <= 1.0)/len(durs):.0%}，不超过 2 秒的占 {sum(1 for x in durs if x <= 2.0)/len(durs):.0%}。")
    A("")
    A("## 二、句意 → 画面类型")
    A("")
    A("“镜头数”是这类句意在 32 条片子里一共配了多少个镜头，“片数”是出现在多少条片子里。“爆款实际配的画面”按次数从多到少列出，括号里是次数。")
    A("")
    A("| 句意 | 镜头数 | 片数 | 单镜中位秒 | 爆款实际配的画面 | 例子（片号 时间 字幕 → 画面） |")
    A("|---|---|---|---|---|---|")
    for code, name in INTENTS.items():
        rs = [r for r in used if r["intent"] == code]
        if not rs or code == "X0":
            continue
        tv, n = top_vis(rs, 5)
        vis_txt = "；".join(f"{VISUALS[v].split('（')[0]}({c})" for v, c in tv)
        ex = []
        seen_v = set()
        for v, _ in tv[:2]:
            for r in rs:
                if r["visual"] == v and r["rid"] not in seen_v:
                    ex.append(f"{r['rid']} {fmt_t(r['start'])}–{fmt_t(r['end'])}「{r['text'].split('；')[-1][:16]}」→{r['obs'][:22]}")
                    seen_v.add(r["rid"])
                    break
        A(f"| {name} | {n} | {len({r['rid'] for r in rs})} | {med([r['dur'] for r in rs]):.2f} | {vis_txt} | {'<br>'.join(ex)} |")
    A("")
    A("## 三、画面类型用量（素材池要备什么、备多少的依据）")
    A("")
    A("“每条平均”是 32 条爆款里平均每条用几个这类镜头。按一个账号一天一条估算，每天每类需要的镜头数就是这个数。")
    A("")
    A("| 画面类型 | 镜头数 | 占比 | 每条平均 | 用到的片数 | 主要服务的句意 |")
    A("|---|---|---|---|---|---|")
    cv = collections.Counter(r["visual"] for r in used)
    for v, c in cv.most_common():
        rs = [r for r in used if r["visual"] == v]
        ci = collections.Counter(r["intent"] for r in rs).most_common(4)
        it_txt = "；".join(f"{INTENTS[i].split('（')[0]}({k})" for i, k in ci)
        A(f"| {VISUALS[v]} | {c} | {c/len(used):.0%} | {c/nv:.1f} | {len({r['rid'] for r in rs})} | {it_txt} |")
    A("")
    A("## 四、开头第一个镜头和最后一个镜头")
    A("")
    first, last = [], []
    for rid in vids:
        rs = [r for r in used if r["rid"] == rid]
        if rs:
            first.append(rs[0])
            last.append(rs[-1])
    A("| 位置 | 画面类型分布（条数） | 时长中位秒 |")
    A("|---|---|---|")
    for nm, rs in (("开头第一镜", first), ("结尾最后一镜", last)):
        c = collections.Counter(r["visual"] for r in rs).most_common()
        A(f"| {nm} | {'；'.join(f'{VISUALS[v].split(chr(65288))[0]}({k})' for v, k in c)} | {med([r['dur'] for r in rs]):.2f} |")
    A("")
    c = collections.Counter(r["intent"] for r in first).most_common()
    A("开头句意分布：" + "；".join(f"{INTENTS[i]}({k})" for i, k in c) + "。")
    A("")
    A("## 五、画面类型定义")
    A("")
    A("给素材打标时用同一套名字，才能和上面的表对上。")
    A("")
    A("| 代码 | 画面类型 |")
    A("|---|---|")
    for v, name in VISUALS.items():
        A(f"| {v} | {name} |")
    A("")
    A("## 六、被排除的重复拉片")
    A("")
    for k, v in EXCLUDE.items():
        A(f"- {k}：{v}")
    A("")
    A("## 七、怎么改、怎么重新生成")
    A("")
    A("- 觉得某个镜头分错了：在 `_生成/改正表.csv` 里加一行（行号写成 `R01#5` 这种形式，句意码或画面码填要改成的代码，不改的留空）。")
    A("- 重新生成：运行 `python _生成/build_table.py --out <一个新文件夹>`。脚本不会覆盖已有文件，所以每次要给一个新的输出位置。")
    A("- “先看结论”一节是 2026-11-14 按当时的数字手写的（`_生成/结论.md`），改正较多后要重新核对那一节。")
    A("")
    with io.open(os.path.join(out, "句意画面对照表.md"), "x", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("written", out, "rows", len(rows), "used", len(used), "override", n_over, "ZZ", n_zz)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--review", action="store_true", help="屏幕输出全部逐行分类")
    ap.add_argument("--counts", action="store_true", help="只输出人工改正行、未归类行和计数")
    ap.add_argument("--out", help="输出到一个新文件夹（已存在则报错）")
    ap.add_argument("--override", default=os.path.join(here, "改正表.csv"))
    ap.add_argument("--summary", default=os.path.join(here, "结论.md"), help="手写的结论段落，插入到表格前")
    a = ap.parse_args()
    load_override(a.override)
    rows = load_rows()
    if a.out:
        summary = io.open(a.summary, encoding="utf-8").read().strip() if os.path.exists(a.summary) else "（未提供结论段落）"
        build(rows, a.out, summary)
    else:
        review(rows, counts_only=a.counts and not a.review)
