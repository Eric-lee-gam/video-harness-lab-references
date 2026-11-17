# -*- coding: utf-8 -*-
"""对 5 个“混有别人”的出镜文件夹逐条做本机人脸比对，按秒输出。
只读共享上的原片（ffmpeg 抽帧走管道，不落盘）；结果只写到本机临时文件夹的新子目录。不联网。"""
import csv, os, subprocess, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
import cv2
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
SHARE = "\\\\192.168.110.36\\共享本公司\\"
VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".wmv", ".flv", ".webm", ".3gp"}
REF_PREFIX = "史上最完整共享\\拍摄\\阿明\\口播人设视频\\"
N_REF = 30
MAX_SEC = 60
TH = 0.45
FOLDERS = [
    "史上最完整共享\\拍摄\\小区\\蔡甸小区全屋\\人物出镜\\",
    "史上最完整共享\\拍摄\\展厅\\人物出境\\",
    "史上最完整共享\\拍摄\\小区\\珞珈山花园小区\\人物出镜2\\",
    "史上最完整共享\\拍摄\\小区\\博学仕府（地面液态陶泥）\\人物出镜\\",
    "史上最完整共享\\拍摄\\小区\\汉阳琴台社区\\人物出境\\",
]
YUNET = os.path.join(HERE, "face_detection_yunet_2023mar.onnx")
SFACE = os.path.join(HERE, "sface_full.onnx")
tl = threading.local()


def models():
    if not hasattr(tl, "det"):
        tl.det = cv2.FaceDetectorYN.create(YUNET, "", (320, 320), 0.7, 0.3, 50)
        tl.rec = cv2.FaceRecognizerSF.create(SFACE, "")
    return tl.det, tl.rec


def frames(rel, seconds):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-t", str(seconds), "-i", SHARE + rel,
           "-vf", "fps=1,scale=1280:1280:force_original_aspect_ratio=decrease", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "3", "-"]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=600)
    except subprocess.TimeoutExpired:
        return None
    data, imgs, pos = r.stdout, [], 0
    while True:
        a = data.find(b"\xff\xd8\xff", pos)
        if a < 0:
            break
        b = data.find(b"\xff\xd8\xff", a + 3)
        chunk = data[a:b] if b > 0 else data[a:]
        img = cv2.imdecode(np.frombuffer(chunk, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            imgs.append(img)
        if b < 0:
            break
        pos = b
    return imgs


def feats(img):
    det, rec = models()
    h, w = img.shape[:2]
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    res = []
    if faces is None:
        return res
    for f in faces:
        if f[2] < 40:
            continue
        v = rec.feature(rec.alignCrop(img, f)).flatten().astype(np.float32)
        v /= (np.linalg.norm(v) + 1e-9)
        res.append((float(f[2]), v))
    res.sort(key=lambda x: -x[0])
    return res


todo, ref_files = [], []
with open(os.path.join(BASE, "36-gongxiang.csv"), newline="", encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        rel = r["relpath"]
        if os.path.splitext(rel)[1].lower() not in VIDEO:
            continue
        if rel.startswith(REF_PREFIX):
            ref_files.append(rel)
        elif any(rel.startswith(p) for p in FOLDERS):
            todo.append(rel)
todo.sort()
ref_files.sort()

out_dir = os.path.join(HERE, "batch_" + time.strftime("%H%M%S"))
os.makedirs(out_dir, exist_ok=False)
log = open(os.path.join(out_dir, "log.txt"), "x", encoding="utf-8")


def P(*a):
    s = " ".join(str(x) for x in a)
    log.write(s + "\n")
    log.flush()
    print(s, flush=True)


step = max(1.0, len(ref_files) / N_REF)
picks = sorted({ref_files[int(i * step)] for i in range(N_REF) if int(i * step) < len(ref_files)})
ref = []
for rel in picks:
    for img in (frames(rel, 6) or [])[1:4]:
        fs = feats(img)
        if fs:
            ref.append(fs[0][1])
R = np.stack(ref)
S = R @ R.T
med = np.array([np.median(np.delete(S[i], i)) for i in range(len(R))])
R = R[med >= 0.35]
np.save(os.path.join(out_dir, "ref_ming.npy"), R)
P(f"参考：{len(picks)} 条视频，人脸 {len(ref)} 张，留 {len(R)} 张；待跑 {len(todo)} 条")


def score(v):
    s = np.sort(R @ v)[::-1]
    return float(s[:5].mean())


def work(rel):
    imgs = frames(rel, MAX_SEC)
    if imgs is None:
        return rel, None
    per = []
    for i, img in enumerate(imgs):
        fs = feats(img)
        sc = [score(v) for _, v in fs]
        if sc:
            j = int(np.argmax(sc))
            per.append((i, len(fs), max(sc), j == 0))
        else:
            per.append((i, 0, None, False))
    return rel, per


t0 = time.time()
fc = open(os.path.join(out_dir, "clips.csv"), "x", newline="", encoding="utf-8-sig")
fp = open(os.path.join(out_dir, "persec.csv"), "x", newline="", encoding="utf-8-sig")
wc, wp = csv.writer(fc), csv.writer(fp)
wc.writerow(["relpath", "frames", "frames_with_face", "best_score", "secs_like_ming", "secs_ming_is_largest_face", "max_faces", "result"])
wp.writerow(["relpath", "sec", "faces", "best_score", "best_is_largest_face"])
n = 0
with ThreadPoolExecutor(4) as ex:
    for rel, per in ex.map(work, todo):
        n += 1
        if per is None:
            wc.writerow([rel, 0, 0, "", "", "", 0, "读取超时"])
        else:
            for i, k, s, big in per:
                wp.writerow([rel, i, k, "" if s is None else f"{s:.3f}", int(big)])
            sc = [s for _, _, s, _ in per if s is not None]
            like = [i for i, _, s, _ in per if s is not None and s >= TH]
            main = [i for i, _, s, big in per if s is not None and s >= TH and big]
            best = max(sc, default=None)
            res = "像阿明" if like else ("未确认·有脸但不够像" if sc else ("未确认·没找到脸" if per else "没抽到帧"))
            wc.writerow([rel, len(per), len(sc), "" if best is None else f"{best:.3f}", " ".join(map(str, like)), " ".join(map(str, main)),
                         max((k for _, k, _, _ in per), default=0), res])
        if n % 50 == 0:
            fc.flush()
            fp.flush()
            P(f"{n}/{len(todo)}  用时 {time.time() - t0:.0f} 秒")
fc.close()
fp.close()
P(f"完成 {n} 条，用时 {time.time() - t0:.0f} 秒；结果在 {out_dir}")
log.close()
