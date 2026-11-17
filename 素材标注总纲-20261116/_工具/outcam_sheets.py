# -*- coding: utf-8 -*-
"""没写是谁的出镜文件夹：每个抽 12 帧拼图。只读共享上的原片；
单帧写到本机临时文件夹的新子目录，拼图和对照表写到工作区的新文件夹。"""
import collections, csv, os, re, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

sys.dont_write_bytecode = True
BASE = os.path.dirname(os.path.abspath(__file__))
SHARE = "\\\\192.168.110.36\\共享本公司\\"
ROOT = "史上最完整共享\\"
OUT_WS = r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116\出镜文件夹确认图"
VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".wmv", ".flv", ".webm", ".3gp"}
PERSON = re.compile(r"出[镜境]|人设|口播")
NAMED = re.compile(r"明|李总|小羊|小阳|徐经理|美女|胡总|胡杰|刘凯|昊哥|谷总|鲍总|刘姐")
N = 12
VF = "scale=360:640:force_original_aspect_ratio=decrease,pad=360:640:(ow-iw)/2:(oh-ih)/2:color=gray"

folders = collections.defaultdict(list)
with open(os.path.join(BASE, "36-gongxiang.csv"), newline="", encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        rel = r["relpath"]
        if not rel.startswith(ROOT) or os.path.splitext(rel)[1].lower() not in VIDEO:
            continue
        segs = rel[len(ROOT):].split("\\")[:-1]
        if segs[0] != "拍摄":
            continue
        for i, s in enumerate(segs):
            if PERSON.search(s):
                folders["\\".join(segs[: i + 1])].append(rel)
                break
todo = sorted(((p, v) for p, v in folders.items() if not NAMED.search(p)), key=lambda x: -len(x[1]))

out_tmp = os.path.join(BASE, "outcam_sheets_" + time.strftime("%H%M%S"))
os.makedirs(out_tmp, exist_ok=False)
os.makedirs(OUT_WS, exist_ok=False)


def grab(src, dst, ss):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-ss", str(ss), "-i", src,
           "-frames:v", "1", "-vf", VF, "-q:v", "4", dst]
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=90)
    except subprocess.TimeoutExpired:
        return False
    return os.path.exists(dst) and os.path.getsize(dst) > 0


def one(job):
    rel, dst = job
    src = SHARE + rel
    return grab(src, dst, 2) or grab(src, dst, 0.3)


rows = []
for idx, (path, vids) in enumerate(todo, 1):
    vids = sorted(vids)
    step = max(1.0, len(vids) / N)
    picks = []
    for i in range(N):
        j = int(i * step)
        if j < len(vids) and vids[j] not in picks:
            picks.append(vids[j])
    d = os.path.join(out_tmp, f"{idx:02d}")
    raw = os.path.join(d, "raw")
    os.makedirs(raw)
    jobs = [(rel, os.path.join(raw, f"{k:02d}.jpg")) for k, rel in enumerate(picks, 1)]
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, jobs))
    ok = [(rel, dst) for (rel, dst), good in zip(jobs, res) if good]
    with open(os.path.join(d, "顺序.txt"), "x", encoding="utf-8") as fh:
        for k, (rel, dst) in enumerate(ok, 1):
            os.replace(dst, os.path.join(d, f"{k:02d}.jpg"))
            fh.write(f"{k:02d}\t{rel}\n")
    sheet = os.path.join(OUT_WS, f"sheet_{idx:02d}.jpg")
    if ok:
        nrows = (len(ok) + 3) // 4
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-n", "-framerate", "1", "-start_number", "1",
                        "-i", os.path.join(d, "%02d.jpg"), "-vf", f"tile=4x{nrows}", "-frames:v", "1", "-q:v", "4", sheet],
                       stdin=subprocess.DEVNULL, capture_output=True, timeout=120)
    made = os.path.exists(sheet)
    rows.append((idx, path, len(vids), len(ok), made))
    print(f"{idx:02d} 帧 {len(ok)}/{len(picks)} 拼图 {'有' if made else '无'}  {path}", flush=True)

with open(os.path.join(OUT_WS, "对照表.md"), "x", encoding="utf-8") as fh:
    fh.write("# 出镜文件夹确认图对照表\n\n")
    fh.write("每张拼图 12 帧，取自该文件夹里均匀挑出的 12 条视频的第 2 秒。顺序从左到右、从上到下。\n")
    fh.write("图由脚本生成，AI 没有看过图的内容。“出镜的是谁”一栏等李康看图后填。\n\n")
    fh.write("| 图 | 文件夹 | 视频数 | 抽到帧数 | 出镜的是谁 |\n|---|---|---|---|---|\n")
    for idx, path, n, k, made in rows:
        fh.write(f"| sheet_{idx:02d}.jpg | `{path}` | {n} | {k} | 待确认 |\n")
print("完成", len(rows), "个文件夹；拼图", sum(1 for r in rows if r[4]), "张；", OUT_WS)
