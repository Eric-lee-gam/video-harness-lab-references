# -*- coding: utf-8 -*-
"""把用户发回的标注截图和已生成的拼图逐张比对，找出是哪一张。只读本机文件。"""
import glob, os, sys
import cv2
import numpy as np

sys.dont_write_bytecode = True
user_img = sys.argv[1]
dirs = sys.argv[2:]


def load(p):
    img = cv2.imdecode(np.fromfile(p, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None
    return cv2.resize(img, (96, 128), interpolation=cv2.INTER_AREA).astype(np.float32)


def corr(a, b):
    a = a - a.mean()
    b = b - b.mean()
    return float((a * b).sum() / (np.sqrt((a * a).sum() * (b * b).sum()) + 1e-9))


u = load(user_img)
res = []
for d in dirs:
    for p in glob.glob(os.path.join(d, "*.jpg")):
        s = load(p)
        if s is not None:
            res.append((corr(u, s), p))
res.sort(reverse=True)
for c, p in res[:5]:
    print(f"{c:.3f}\t{p}")
