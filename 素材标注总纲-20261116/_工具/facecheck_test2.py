# -*- coding: utf-8 -*-
"""本机人脸比对小测试（第二版：每条视频每秒抽一帧，最多前 20 秒，取最像的一帧）。
只读共享上的原片（ffmpeg 抽帧走管道，不落盘）；结果只写到本机临时文件夹的新文件。不联网。"""
import csv, glob, os, subprocess, sys, time
import cv2
import numpy as np

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
SHARE = "\\\\192.168.110.36\\共享本公司\\"
VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".mts", ".wmv", ".flv", ".webm", ".3gp"}
REF_PREFIX = "史上最完整共享\\拍摄\\阿明\\口播人设视频\\"
N_REF = 30
LABELS = {"01": {1, 2, 8, 10}, "04": {1, 2, 3, 7, 10, 11}, "06": {2}, "07": {1}}

out = []


def P(*a):
    s = " ".join(str(x) for x in a)
    out.append(s)
    print(s, flush=True)


det = cv2.FaceDetectorYN.create(os.path.join(HERE, "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.7, 0.3, 50)
rec = cv2.FaceRecognizerSF.create(os.path.join(HERE, "sface_full.onnx"), "")


def frames(rel, seconds=20):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-t", str(seconds), "-i", SHARE + rel,
           "-vf", "fps=1,scale=1280:1280:force_original_aspect_ratio=decrease", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "3", "-"]
    try:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, timeout=300)
    except subprocess.TimeoutExpired:
        return []
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


ref_files = []
with open(os.path.join(BASE, "36-gongxiang.csv"), newline="", encoding="utf-8-sig") as fh:
    for r in csv.DictReader(fh):
        rel = r["relpath"]
        if rel.startswith(REF_PREFIX) and os.path.splitext(rel)[1].lower() in VIDEO:
            ref_files.append(rel)
ref_files.sort()
step = max(1.0, len(ref_files) / N_REF)
picks = sorted({ref_files[int(i * step)] for i in range(N_REF) if int(i * step) < len(ref_files)})
ref = []
for rel in picks:
    for img in frames(rel, 6)[1:4]:
        fs = feats(img)
        if fs:
            ref.append(fs[0][1])
R = np.stack(ref)
S = R @ R.T
med = np.array([np.median(np.delete(S[i], i)) for i in range(len(R))])
keep = med >= 0.35
P(f"参考：{len(picks)} 条视频，人脸 {len(ref)} 张，内部相似度中位数 {np.median(med):.2f}，剔除 {int((~keep).sum())} 张，留 {int(keep.sum())} 张")
R = R[keep]


def score(v):
    s = np.sort(R @ v)[::-1]
    return float(s[:5].mean())


sheet_dir = sorted(glob.glob(os.path.join(BASE, "outcam_sheets_*")))[0]
rows = []
for sheet, notming in LABELS.items():
    with open(os.path.join(sheet_dir, sheet, "顺序.txt"), encoding="utf-8") as fh:
        for line in fh:
            k, rel = line.rstrip("\n").split("\t")
            imgs = frames(rel)
            sc = [score(v) for img in imgs for _, v in feats(img)]
            best = max(sc, default=None)
            rows.append((sheet, int(k), int(k) not in notming, len(imgs), len(sc), best))
            P(f"图{sheet} 格{k}  李康:{'阿明' if int(k) not in notming else '不是'}  帧 {len(imgs)}  人脸 {len(sc)}  最高相似 {'无脸' if best is None else f'{best:.2f}'}")

P("\n== 汇总（每条视频取最像的一帧；SFace 官方建议的同一人阈值是 0.36）")
P("提醒：李康的判断是针对拼图上第 2 秒那一帧里打叉的人；整条视频里可能还有别的人出现。")
for name, cond in (("李康标为阿明", True), ("李康标为不是", False)):
    sub = [r for r in rows if r[2] == cond]
    wf = [r[5] for r in sub if r[5] is not None]
    P(f"{name}：{len(sub)} 条，检出人脸 {len(wf)} 条，相似度从低到高：" + " ".join(f"{x:.2f}" for x in sorted(wf)))
for th in (0.36, 0.45, 0.55):
    tp = sum(1 for r in rows if r[2] and r[5] is not None and r[5] >= th)
    fn = sum(1 for r in rows if r[2] and (r[5] is None or r[5] < th))
    fp = sum(1 for r in rows if not r[2] and r[5] is not None and r[5] >= th)
    tn = sum(1 for r in rows if not r[2] and (r[5] is None or r[5] < th))
    P(f"阈值 {th:.2f}：阿明认出 {tp}、阿明没认出 {fn}；不是阿明判对 {tn}、被当成阿明 {fp}")

name = os.path.join(HERE, "facecheck_test2_out_" + time.strftime("%H%M%S") + ".txt")
with open(name, "x", encoding="utf-8") as fh:
    fh.write("\n".join(out))
print(name)
