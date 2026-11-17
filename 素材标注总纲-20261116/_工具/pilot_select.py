# -*- coding: utf-8 -*-
"""试标 50 段：从小区库按文件夹名分层抽样，每段取连续约 3 秒、4 帧拼图。
只读共享上的原片；图和对应表写到工作区的新文件夹。不打印对应关系。"""
import csv, json, os, random, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.abspath(__file__))
SHARE = "\\\\192.168.110.36\\共享本公司\\"
ROOT = "史上最完整共享\\拍摄\\小区\\"
OUT = r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116\试标50段"
VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".wmv", ".flv", ".webm", ".3gp"}
SKIP = ("汉黄社区", "汉阳4个卫生间", "南湖名都", "新华家园", "嘉贝乐", "2其他", "1新的未分类", "被忽悠了")
STRATA = [  # (名字, 子文件夹名匹配, 抽几条)
    ("人物", r"出[镜境]|人设|口播", 8),
    ("拆除", r"拆|铲", 5),
    ("旧状", r"翻新前|展示前|前期|施工前|开场", 4),
    ("上门", r"上门|量房|量尺|送货|搬", 4),
    ("罩面", r"罩面|滚涂|底漆|打磨", 4),
    ("批刮", r"批刮|第一遍|第二遍|陶泥|陶砂|陶沙", 8),
    ("完工", r"完工|展示|后期", 7),
    ("施工", r"施工|续|中期", 10),
]
random.seed(20261116)

pool = {name: [] for name, _, _ in STRATA}
with open(os.path.join(BASE, "36-gongxiang.csv"), newline="", encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        rel = r["relpath"]
        if not rel.startswith(ROOT) or os.path.splitext(rel)[1].lower() not in VIDEO:
            continue
        segs = rel[len(ROOT):].split("\\")
        if any(k in segs[0] for k in SKIP) or len(segs) < 3:
            continue
        sub = "\\".join(segs[1:-1])  # 只看项目名下面的子文件夹名
        for name, pat, _ in STRATA:
            if re.search(pat, sub):
                pool[name].append(rel)
                break

picked = []
for name, _, n in STRATA:
    lst = pool[name]
    random.shuffle(lst)
    seen_proj = set()
    got = []
    for rel in lst:  # 同一层里尽量每个项目只取一条
        proj = rel[len(ROOT):].split("\\")[0]
        if proj in seen_proj:
            continue
        seen_proj.add(proj)
        got.append(rel)
        if len(got) == n:
            break
    for rel in lst:
        if len(got) == n:
            break
        if rel not in got:
            got.append(rel)
    picked += [(name, rel) for rel in got]
random.shuffle(picked)
print("各层可选条数:", {k: len(v) for k, v in pool.items()})
print("抽到:", len(picked))

os.makedirs(OUT, exist_ok=False)
os.makedirs(os.path.join(OUT, "frames"))
VF = "fps=1,scale=480:854:force_original_aspect_ratio=decrease,pad=480:854:(ow-iw)/2:(oh-ih)/2:color=gray,tile=2x2"


def dur(src):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", src],
                           stdin=subprocess.DEVNULL, capture_output=True, timeout=90)
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return None


def make(job):
    i, (name, rel) = job
    src = SHARE + rel
    d = dur(src)
    if d is None:
        return i, name, rel, None, None, False
    start = 0.0 if d <= 5 else round(random.Random(i).uniform(1.0, d - 4.5), 1)
    dst = os.path.join(OUT, "frames", f"seg_{i:02d}.jpg")
    try:
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-ss", str(start), "-t", "4", "-i", src,
                        "-vf", VF, "-frames:v", "1", "-q:v", "3", dst], stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
    except subprocess.TimeoutExpired:
        pass
    return i, name, rel, d, start, os.path.exists(dst) and os.path.getsize(dst) > 0


with ThreadPoolExecutor(4) as ex:
    rows = list(ex.map(make, enumerate(picked, 1)))
with open(os.path.join(OUT, "_对应表.csv"), "x", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["seg", "抽样层", "原片", "原片时长秒", "起始秒", "结束秒", "出图"])
    for i, name, rel, d, start, ok in rows:
        w.writerow([f"seg_{i:02d}", name, rel, "" if d is None else f"{d:.1f}", "" if start is None else start,
                    "" if start is None else round(min(d, start + 4), 1), int(ok)])
print("出图成功:", sum(1 for r in rows if r[5]), "/", len(rows))
print("时长不足 4 秒的:", sum(1 for r in rows if r[3] is not None and r[3] < 4))
print(OUT)
