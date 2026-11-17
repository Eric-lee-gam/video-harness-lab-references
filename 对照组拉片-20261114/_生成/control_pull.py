# -*- coding: utf-8 -*-
"""
对照组拉片（2026-11-14）：从共享盘「视频发布」抽 30 条，与 32 条爆款用同一套句意/画面分类比较。

共享盘只读。输出只新建、不覆盖：
  python control_pull.py pick      写 抽样清单.csv
  python control_pull.py pull      每条：切镜检测 + 本机语音转写（写 _生成/cache/Cxx.json）+ 拼图（写 拼图/Cxx.jpg）
  python control_pull.py review [Cxx ...]   屏幕输出逐镜头初分结果和拼图格子对应关系
  python control_pull.py build <新文件夹名>  生成 对照组镜头逐行标注.csv 和 对比数字.md

人工（AI 看拼图）标注文件，都在 _生成/ 下：
  画面标注.csv   编号,逐格画面码（按拼图格子顺序，空格分隔）
  切点修正.csv   编号,动作(加/删),秒
  句意改正.csv   行(如 C01#3),句意码,说明
"""
import collections, csv, io, json, math, os, random, re, statistics, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(HERE)
sys.path.insert(0, os.path.normpath(os.path.join(OUT, "..", "句意画面对照表-20261114", "_生成")))
import build_table as bt  # 复用同一套句意规则和代码表

TMP = r"C:\Users\leega\AppData\Local\Temp\share-video-inventory-20261114"
SAMPLE = os.path.join(TMP, "rhythm_published_200.csv")
SHARE_ROOT = r"\\192.168.110.36\共享本公司"
MODEL = r"C:\Users\leega\.cache\huggingface\hub\models--Systran--faster-whisper-small\snapshots\536b0662742c02347bc0e980a01041f333bce120"
QUOTA = collections.OrderedDict([("陈翰文", 7), ("张艺", 7), ("李康", 5), ("彭书超", 5), ("舒依玲", 3), ("赵金忠", 2), ("刘永添", 1)])
THR, MIN_GAP = 0.20, 0.30
TILE_W, TILE_H, COLS, STEP = 240, 427, 6, 1.5
NOWIN = 0x08000000
LIST = os.path.join(OUT, "抽样清单.csv")
LIST2 = os.path.join(OUT, "抽样清单-补抽.csv")
EXTRA = collections.OrderedDict([("陈翰文", 2), ("张艺", 2), ("李康", 1), ("彭书超", 1)])
HAND = {"舒依玲", "赵金忠", "刘永添"}  # 新人手剪，不是 AI 剪辑
CACHE = os.path.join(HERE, "cache")
SHEETS = os.path.join(OUT, "拼图")


# ---------- 抽样 ----------
def pick():
    by = collections.defaultdict(list)
    for r in csv.DictReader(io.open(SAMPLE, encoding="utf-8-sig")):
        if "历史版本" in r["relpath"] or "勿发布" in r["relpath"] or float(r["dur"]) <= 0:
            continue
        by[r["person"]].append(r)
    rnd = random.Random(20261114)
    rows = []
    for person, n in QUOTA.items():
        rs = sorted(by[person], key=lambda r: r["relpath"])
        rnd.shuffle(rs)
        got, seen = [], set()
        for r in rs:  # 先保证账号不重复
            if len(got) < n and r["account"] not in seen:
                got.append(r)
                seen.add(r["account"])
        for r in rs:
            if len(got) < n and r not in got:
                got.append(r)
        rows += got
    with io.open(LIST, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["编号", "人", "账号文件夹", "相对路径", "大小字节", "时长秒", "修改时间戳"])
        for i, r in enumerate(rows, 1):
            w.writerow([f"C{i:02d}", r["person"], r["account"], r["relpath"], r["size"], r["dur"], r["mtime"]])
            print(f"C{i:02d}", r["person"], r["dur"], r["relpath"])


def pick2():
    """补抽 6 条 AI 剪辑的（Eric 2026-11-14 说明：舒依玲、赵金忠、刘永添是新人手剪，不属于 AI 对照组）"""
    have = load_list()
    used_rel = {r["相对路径"] for r in have}
    used_acct = {(r["人"], r["账号文件夹"]) for r in have}
    by = collections.defaultdict(list)
    for r in csv.DictReader(io.open(SAMPLE, encoding="utf-8-sig")):
        if "历史版本" in r["relpath"] or "勿发布" in r["relpath"] or float(r["dur"]) <= 0 or r["relpath"] in used_rel:
            continue
        by[r["person"]].append(r)
    rnd = random.Random(2026111402)
    rows = []
    for person, n in EXTRA.items():
        rs = sorted(by[person], key=lambda r: r["relpath"])
        rnd.shuffle(rs)
        got = [r for r in rs if (person, r["account"]) not in used_acct][:n]
        got += [r for r in rs if r not in got][: n - len(got)]
        rows += got
    with io.open(LIST2, "x", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["编号", "人", "账号文件夹", "相对路径", "大小字节", "时长秒", "修改时间戳"])
        for i, r in enumerate(rows, len(have) + 1):
            w.writerow([f"C{i:02d}", r["person"], r["account"], r["relpath"], r["size"], r["dur"], r["mtime"]])
            print(f"C{i:02d}", r["person"], r["dur"], r["relpath"])


def load_list():
    rows = list(csv.DictReader(io.open(LIST, encoding="utf-8-sig")))
    if os.path.exists(LIST2):
        rows += list(csv.DictReader(io.open(LIST2, encoding="utf-8-sig")))
    return rows


# ---------- 检测 / 转写 / 拼图 ----------
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate:format=duration", "-of", "json", path],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
    j = json.loads(r.stdout or "{}")
    s = (j.get("streams") or [{}])[0]
    return float(j.get("format", {}).get("duration") or 0), s.get("width"), s.get("height")


def scene_scores(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-an", "-vf",
                        "scale=180:320,select='gt(scene,0.15)',metadata=print:file=-", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=NOWIN)
    out, t = [], None
    for line in r.stdout.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            t = float(m.group(1))
            continue
        m = re.search(r"scene_score=([\d.]+)", line)
        if m and t is not None:
            out.append((t, float(m.group(1))))
    return out


def auto_cuts(scores, dur):
    cs, last = [], -9
    for t, s in scores:
        if s > THR and t - last >= MIN_GAP and 0.2 < t < dur - 0.2:
            cs.append(round(t, 2))
            last = t
    return cs


def tile_times(cuts, dur):
    pts = [0.0] + cuts + [dur]
    out = []
    for a, b in zip(pts, pts[1:]):
        n = max(1, math.ceil((b - a) / STEP))
        out += [round(a + (k + 0.5) * (b - a) / n, 2) for k in range(n)]
    return out


def make_sheet(cid, path, times, cuts, dest):
    from PIL import Image, ImageDraw, ImageFont
    fdir = os.path.join(TMP, "ctl_frames", cid)
    os.makedirs(fdir, exist_ok=True)
    font = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 22)
    rows = math.ceil(len(times) / COLS)
    sheet = Image.new("RGB", (COLS * TILE_W, rows * TILE_H), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    for k, t in enumerate(times, 1):
        fp = os.path.join(fdir, f"f_{k:03d}.jpg")
        if not os.path.exists(fp):
            subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-n", "-ss", f"{t:.2f}", "-i", path, "-frames:v", "1",
                            "-vf", f"scale={TILE_W}:{TILE_H}", fp], capture_output=True, creationflags=NOWIN)
        x, y = ((k - 1) % COLS) * TILE_W, ((k - 1) // COLS) * TILE_H
        if os.path.exists(fp):
            sheet.paste(Image.open(fp).convert("RGB").resize((TILE_W, TILE_H)), (x, y))
        shot = 1 + sum(1 for c in cuts if c <= t)
        d.rectangle([x, y, x + 118, y + 26], fill=(0, 0, 0))
        d.text((x + 3, y + 1), f"{k} S{shot} {t:.1f}", font=font, fill=(255, 255, 0))
        d.rectangle([x, y, x + TILE_W - 1, y + TILE_H - 1], outline=(255, 0, 0) if shot % 2 else (0, 200, 255), width=3)
    with io.open(dest, "xb") as f:
        sheet.save(f, "JPEG", quality=82)


def pull():
    os.makedirs(CACHE, exist_ok=True)
    os.makedirs(SHEETS, exist_ok=True)
    model = None
    t0 = time.time()
    for r in load_list():
        cid, path = r["编号"], os.path.join(SHARE_ROOT, r["相对路径"])
        cp = os.path.join(CACHE, cid + ".json")
        if not os.path.exists(cp):
            dur, w, h = probe(path)
            scores = scene_scores(path)
            if model is None:
                from faster_whisper import WhisperModel
                model = WhisperModel(MODEL, device="cpu", compute_type="int8")
            segs, info = model.transcribe(path, language="zh", word_timestamps=True, vad_filter=False,
                                          initial_prompt="以下是普通话的句子。")
            segments = [{"start": s.start, "end": s.end, "text": s.text.strip(),
                         "words": [{"s": x.start, "e": x.end, "w": x.word} for x in (s.words or [])]} for s in segs]
            cuts = auto_cuts(scores, dur)
            j = {"id": cid, "relpath": r["相对路径"], "dur": dur, "w": w, "h": h, "scores": scores, "auto_cuts": cuts,
                 "tiles": tile_times(cuts, dur), "segments": segments, "asr_model": "faster-whisper-small cpu int8",
                 "human_listening_verified": False}
            with io.open(cp, "x", encoding="utf-8") as f:
                json.dump(j, f, ensure_ascii=False)
        j = json.load(io.open(cp, encoding="utf-8"))
        sp = os.path.join(SHEETS, cid + ".jpg")
        if not os.path.exists(sp):
            make_sheet(cid, path, j["tiles"], j["auto_cuts"], sp)
        print(cid, f"{j['dur']:.1f}s", "镜头", len(j["auto_cuts"]) + 1, "格子", len(j["tiles"]), f"{time.time()-t0:.0f}s", flush=True)
    print("DONE", flush=True)


# ---------- 标注读取 ----------
def read_csv(name):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return []
    with io.open(p, encoding="utf-8-sig", newline="") as f:
        return [[x.strip() for x in row] for i, row in enumerate(csv.reader(f)) if i > 0 and row and row[0].strip()]


def load_marks():
    vis = {}
    for row in read_csv("画面标注.csv"):
        codes = row[1].split()
        for c in codes:
            if c not in bt.VISUALS:
                raise SystemExit(f"画面标注里的代码不存在: {row[0]} {c}")
        vis[row[0]] = codes
    fix = collections.defaultdict(lambda: {"加": [], "删": []})
    for row in read_csv("切点修正.csv"):
        fix[row[0]][row[1]].append(float(row[2]))
    it = {}
    for row in read_csv("句意改正.csv"):
        if row[1] not in bt.INTENTS:
            raise SystemExit(f"句意改正里的代码不存在: {row}")
        it[row[0]] = row[1]
    return vis, fix, it


def final_cuts(j, fx):
    cuts = [c for c in j["auto_cuts"] if not any(abs(c - d) < 0.15 for d in fx["删"])]
    return sorted(cuts + fx["加"])


def shot_text(j, a, b):
    out = []
    for s in j["segments"]:
        ws = [x["w"] for x in s["words"] if a <= (x["s"] + x["e"]) / 2 < b]
        if ws:
            out.append("".join(ws).strip())
    return "；".join(x for x in out if x)


def rows_for(meta, vis, fix, it):
    cid = meta["编号"]
    j = json.load(io.open(os.path.join(CACHE, cid + ".json"), encoding="utf-8"))
    cuts = final_cuts(j, fix[cid])
    pts = [0.0] + cuts + [j["dur"]]
    codes = vis.get(cid)
    if codes is not None and len(codes) != len(j["tiles"]):
        raise SystemExit(f"{cid} 画面标注有 {len(codes)} 个，拼图有 {len(j['tiles'])} 格")
    rows = []
    for idx, (a, b) in enumerate(zip(pts, pts[1:]), 1):
        key = f"{cid}#{idx}"
        text = shot_text(j, a, b)
        intent = bt.classify_intent(cid, idx, b - a, text) if text else "X0"
        src = "规则"
        if key in it:
            intent, src = it[key], "核对后改"
        tl = [k for k, t in enumerate(j["tiles"], 1) if a <= t < b]
        v = ""
        if codes and tl:
            c = collections.Counter(codes[k - 1] for k in tl)
            best = max(c.values())
            v = next(codes[k - 1] for k in tl if c[codes[k - 1]] == best)
        rows.append(dict(key=key, cid=cid, idx=idx, start=a, end=b, dur=b - a, text=text, intent=intent, visual=v,
                         src=src, tiles=tl, person=meta["人"], account=meta["账号文件夹"], rel=meta["相对路径"],
                         vdur=j["dur"]))
    return rows


def all_rows(only=None):
    vis, fix, it = load_marks()
    rows = []
    for m in load_list():
        if only and m["编号"] not in only:
            continue
        rows += rows_for(m, vis, fix, it)
    return rows


def review(only):
    rows = all_rows(only)
    cur = None
    for r in rows:
        if r["cid"] != cur:
            cur = r["cid"]
            print(f"== {cur} {r['person']} | {r['account']} | {r['vdur']:.1f}s | {os.path.basename(r['rel'])}")
        tl = f"{r['tiles'][0]}-{r['tiles'][-1]}" if r["tiles"] else "无"
        print(f"{r['key']} {r['start']:.1f}-{r['end']:.1f} 格{tl} {r['intent']} {r['visual'] or '--'} {r['src'][0]} | {r['text']}")


# ---------- 文案比对 ----------
def _grams(text):
    s = re.sub(r"[^\u4e00-\u9fff0-9]", "", text or "")
    return {s[i:i + 2] for i in range(len(s) - 1)}


def copy_match():
    """每条片子的机器转写，与文案库 74 条、爆款 32 条转写的相似度（片子的二字组有多少比例出现在对方里）"""
    ana = os.path.normpath(os.path.join(OUT, "..", "analysis"))
    lib = json.load(io.open(os.path.join(ana, "copy-library", "analysis.json"), encoding="utf-8"))["scripts"]
    libg = [(s["id"], s.get("family", ""), _grams(s["text"])) for s in lib]
    refg = []
    for i in range(1, 36):
        rid = f"R{i:02d}"
        if rid in bt.EXCLUDE:
            continue
        p = os.path.join(ana, rid, "asr.json")
        if os.path.exists(p):
            refg.append((rid, "", _grams(json.load(io.open(p, encoding="utf-8")).get("raw_text", ""))))
    out = {}
    for m in load_list():
        j = json.load(io.open(os.path.join(CACHE, m["编号"] + ".json"), encoding="utf-8"))
        text = "".join(s["text"] for s in j["segments"])
        g = _grams(text)

        def best(cands):
            sc = [(len(g & cg) / max(1, len(g)), cid, fam) for cid, fam, cg in cands]
            return max(sc)

        out[m["编号"]] = dict(lib=best(libg), ref=best(refg), text=text, person=m["人"])
    return out


def show_copy():
    cm = copy_match()
    for cid, d in cm.items():
        print(f"{cid} {d['person']} 文案库 {d['lib'][1]} {d['lib'][0]:.2f} {d['lib'][2]} | 爆款 {d['ref'][1]} {d['ref'][0]:.2f} | {d['text'][:40]}")


# ---------- 汇总 ----------
def load_ref():
    """爆款 32 条的逐行标注（上次生成的 CSV）"""
    p = os.path.join(OUT, "..", "句意画面对照表-20261114", "镜头逐行标注.csv")
    rows = []
    for r in csv.DictReader(io.open(p, encoding="utf-8-sig")):
        rows.append(dict(cid=r["参考片"], idx=int(r["镜头序号"]), dur=float(r["时长秒"]), intent=r["句意码"], visual=r["画面码"]))
    return rows


def vname(v):
    return bt.VISUALS[v].split("（")[0]


def iname(i):
    return bt.INTENTS[i].split("（")[0]


PEOPLE = {"V01", "V24", "V02"}


def build(folder):
    rows = all_rows()
    missing = [r["key"] for r in rows if not r["visual"]]
    if missing:
        raise SystemExit(f"还有 {len(missing)} 个镜头没有画面标注，例如 {missing[:5]}")
    out = os.path.join(OUT, folder)
    os.makedirs(out, exist_ok=True)
    with io.open(os.path.join(out, "对照组镜头逐行标注.csv"), "x", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["编号", "人", "账号文件夹", "镜头序号", "开始秒", "结束秒", "时长秒", "口播(机器转写)", "句意码", "句意",
                    "画面码", "画面类型", "句意标注方式", "相对路径"])
        for r in rows:
            w.writerow([r["cid"], r["person"], r["account"], r["idx"], f"{r['start']:.2f}", f"{r['end']:.2f}", f"{r['dur']:.2f}",
                        r["text"], r["intent"], bt.INTENTS[r["intent"]], r["visual"], bt.VISUALS[r["visual"]], r["src"], r["rel"]])
    ref = [r for r in load_ref() if r["intent"] != "X0"]
    ctl = [r for r in rows if r["intent"] != "X0"]
    nref, nctl = len({r["cid"] for r in ref}), len({r["cid"] for r in ctl})
    L = []
    A = L.append
    A(f"爆款 {nref} 条 {len(ref)} 个镜头；对照组 {nctl} 条 {len(ctl)} 个镜头（另有 {len(rows)-len(ctl)} 个无口播镜头不计）。")
    A("")
    A("## 画面类型用量（每条平均用几个镜头 / 占时长比例）")
    A("")
    A("| 画面类型 | 爆款 每条平均 | 对照 每条平均 | 爆款 占镜头数 | 对照 占镜头数 | 爆款 占时长 | 对照 占时长 | 爆款 用到的片 | 对照 用到的片 |")
    A("|---|---|---|---|---|---|---|---|---|")
    tr, tc = sum(r["dur"] for r in ref), sum(r["dur"] for r in ctl)
    for v in bt.VISUALS:
        a = [r for r in ref if r["visual"] == v]
        b = [r for r in ctl if r["visual"] == v]
        if not a and not b:
            continue
        A(f"| {vname(v)} | {len(a)/nref:.1f} | {len(b)/nctl:.1f} | {len(a)/len(ref):.0%} | {len(b)/len(ctl):.0%} | "
          f"{sum(r['dur'] for r in a)/tr:.0%} | {sum(r['dur'] for r in b)/tc:.0%} | "
          f"{len({r['cid'] for r in a})}/{nref} | {len({r['cid'] for r in b})}/{nctl} |")
    A("")
    A("## 句意 → 画面（前三名，括号里是镜头数）")
    A("")
    A("| 句意 | 爆款 镜头数 | 爆款配的画面 | 对照 镜头数 | 对照配的画面 |")
    A("|---|---|---|---|---|")
    for i in bt.INTENTS:
        if i == "X0":
            continue
        a = [r for r in ref if r["intent"] == i]
        b = [r for r in ctl if r["intent"] == i]
        if not a and not b:
            continue
        fa = "；".join(f"{vname(v)}({c})" for v, c in collections.Counter(r["visual"] for r in a).most_common(3))
        fb = "；".join(f"{vname(v)}({c})" for v, c in collections.Counter(r["visual"] for r in b).most_common(3))
        A(f"| {iname(i)} | {len(a)} | {fa} | {len(b)} | {fb} |")
    A("")
    A("## 每条片子的整体情况")
    A("")

    def per_video(rs):
        g = collections.defaultdict(list)
        for r in rs:
            g[r["cid"]].append(r)
        return g

    def summarize(name, rs):
        g = per_video(rs)
        n = len(g)
        kinds = [len({r["visual"] for r in v}) for v in g.values()]
        ppl = [sum(r["dur"] for r in v if r["visual"] in PEOPLE) / sum(r["dur"] for r in v) for v in g.values()]
        first = collections.Counter(sorted(v, key=lambda r: r["idx"])[0]["visual"] for v in g.values())
        last = collections.Counter(sorted(v, key=lambda r: r["idx"])[-1]["visual"] for v in g.values())
        firstd = [sorted(v, key=lambda r: r["idx"])[0]["dur"] for v in g.values()]
        A(f"- **{name}**（{n} 条）：每条用到的画面类型数 中位 {statistics.median(kinds):.0f}（最少 {min(kinds)}，最多 {max(kinds)}）；"
          f"人物镜头（对镜头/在现场/握手沟通）占时长 中位 {statistics.median(ppl):.0%}；第一镜时长中位 {statistics.median(firstd):.2f} 秒。")
        A(f"  - 第一镜：{'；'.join(f'{vname(v)}({c})' for v, c in first.most_common())}")
        A(f"  - 最后一镜：{'；'.join(f'{vname(v)}({c})' for v, c in last.most_common())}")
        for code in ("V05", "V13", "V11", "V12", "V08", "V15", "V16"):
            A(f"  - 有「{vname(code)}」的片子：{sum(1 for v in g.values() if any(r['visual']==code for r in v))}/{n}")
        ints = collections.Counter()
        for v in g.values():
            for i in {r["intent"] for r in v}:
                ints[i] += 1
        A(f"  - 出现各句意的片子数：{'；'.join(f'{iname(i)}({c})' for i, c in ints.most_common())}")

    summarize("爆款", ref)
    summarize("对照组", ctl)
    A("")
    A("## 对照组分人")
    A("")
    A("| 人 | 条数 | 镜头数 | 最多的四类画面 | 人物镜头占时长 |")
    A("|---|---|---|---|---|")
    for person in QUOTA:
        rs = [r for r in ctl if r["person"] == person]
        if not rs:
            continue
        top = "；".join(f"{vname(v)}({c})" for v, c in collections.Counter(r["visual"] for r in rs).most_common(4))
        pp = sum(r["dur"] for r in rs if r["visual"] in PEOPLE) / sum(r["dur"] for r in rs)
        A(f"| {person} | {len({r['cid'] for r in rs})} | {len(rs)} | {top} | {pp:.0%} |")
    with io.open(os.path.join(out, "对比数字.md"), "x", encoding="utf-8") as f:
        f.write("\n".join(L))
    print("\n".join(L))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pick":
        pick()
    elif cmd == "pick2":
        pick2()
    elif cmd == "copy":
        show_copy()
    elif cmd == "pull":
        pull()
    elif cmd == "review":
        review(set(sys.argv[2:]) or None)
    elif cmd == "build":
        build(sys.argv[2])
