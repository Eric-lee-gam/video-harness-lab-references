# -*- coding: utf-8 -*-
"""Copy 30 unusable source videos into the project isolation dir. Never move or delete share files."""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116")
SRC_LIST = ROOT / "工位产出" / "T01" / "20261117_03" / "32条时长或画幅缺口清单.json"
DEST_ROOT = ROOT / "工位产出" / "T01" / "20261117_04_隔离"
SCRIPT_DIR = DEST_ROOT / "脚本"
LOG = DEST_ROOT / "隔离过程日志.jsonl"

EXCLUDE_IDS = {"25a4ad80490d5c2b", "2ae8d45b0f4efe92"}
EXCLUDE_PATH_NEEDLES = [
    "南湖一厨一卫/26916_小区场景.MOV",
    "武昌沙湖小区 看房量尺/32303_小区场景.MOV",
]
PASSWORD_NEEDLE = "资料账号密码"
SHARE_PREFIX = Path(r"\\192.168.110.36\共享本公司\史上最完整共享")

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def is_excluded(rec: dict) -> bool:
    if rec.get("原片ID") in EXCLUDE_IDS:
        return True
    logic = rec.get("逻辑路径") or ""
    share = rec.get("共享盘路径") or ""
    rel = rec.get("共享相对路径") or ""
    blob = logic + "\n" + share + "\n" + rel
    for needle in EXCLUDE_PATH_NEEDLES:
        if needle.replace("/", os.sep) in blob.replace("/", os.sep) or needle in blob:
            return True
    return False

def log(obj: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    print(obj.get("event"), obj.get("原片ID") or obj.get("path") or "", obj.get("status") or obj.get("message") or "", flush=True)

def copy_hashed(src: Path, dest: Path) -> dict:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".partial_copy")
    if tmp.exists():
        tmp.unlink()  # only a dest-side temp, never on share
    h = hashlib.sha256()
    written = 0
    t0 = time.perf_counter()
    with src.open("rb") as rf, tmp.open("wb") as wf:
        while True:
            chunk = rf.read(1024 * 1024)
            if not chunk:
                break
            wf.write(chunk)
            h.update(chunk)
            written += len(chunk)
    os.replace(str(tmp), str(dest))  # dest side only
    dest_sha = sha256_file(dest)
    return {
        "bytes_written": written,
        "elapsed_sec": round(time.perf_counter() - t0, 3),
        "stream_sha256": h.hexdigest(),
        "dest_sha256": dest_sha,
    }

def main():
    SCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    data = json.loads(SRC_LIST.read_text(encoding="utf-8"))
    records = data["记录"]
    results = []
    isolated = 0
    failed = 0
    skipped = 0

    # never write this script's source onto the share
    for rec in records:
        item = {
            "原片ID": rec.get("原片ID"),
            "分类": rec.get("分类"),
            "逻辑路径": rec.get("逻辑路径"),
            "共享相对路径": rec.get("共享相对路径"),
            "共享盘路径": rec.get("共享盘路径"),
            "清单字节数": rec.get("字节数"),
            "原因": rec.get("原因"),
        }
        if is_excluded(rec):
            item["status"] = "排除_超时已恢复不清理"
            item["copied"] = False
            skipped += 1
            results.append(item)
            log({"event": "skip_excluded", "原片ID": rec.get("原片ID"), "逻辑路径": rec.get("逻辑路径")})
            continue
        nameblob = (rec.get("逻辑路径") or "") + (rec.get("共享相对路径") or "") + (rec.get("共享盘路径") or "")
        if PASSWORD_NEEDLE in nameblob:
            item["status"] = "跳过_文件名含资料账号密码"
            item["copied"] = False
            skipped += 1
            results.append(item)
            log({"event": "skip_password_name", "原片ID": rec.get("原片ID")})
            continue

        src = Path(rec["共享盘路径"])
        # belt-and-suspenders: refuse if path is not under share prefix
        try:
            src.resolve()  # may fail for UNC? try anyway
        except Exception:
            pass
        src_s = str(src)
        if not src_s.lower().startswith(str(SHARE_PREFIX).lower()):
            item["status"] = "失败_路径不在指定共享盘根下"
            item["copied"] = False
            failed += 1
            results.append(item)
            log({"event": "reject_path", "原片ID": rec.get("原片ID"), "path": src_s})
            continue

        rel = rec["共享相对路径"].replace("/", os.sep)
        dest = DEST_ROOT / rel
        item["目标路径"] = str(dest)

        try:
            if not src.exists():
                item["status"] = "失败_共享盘源文件缺失"
                item["copied"] = False
                item["源仍在共享盘"] = False
                failed += 1
                results.append(item)
                log({"event": "missing", "原片ID": rec.get("原片ID"), "path": src_s})
                continue
            st_before = src.stat()
            item["源拷贝前"] = {"size": st_before.st_size, "mtime": st_before.st_mtime}
            copy_info = copy_hashed(src, dest)
            st_after = src.stat()
            dest_st = dest.stat()
            item["源拷贝后"] = {"size": st_after.st_size, "mtime": st_after.st_mtime, "仍存在": src.exists()}
            item["目标"] = {
                "size": dest_st.st_size,
                "sha256": copy_info["dest_sha256"],
            }
            item["stream_sha256"] = copy_info["stream_sha256"]
            item["elapsed_sec"] = copy_info["elapsed_sec"]
            size_ok = (
                dest_st.st_size == st_before.st_size
                and st_after.st_size == st_before.st_size
                and dest_st.st_size == copy_info["bytes_written"]
            )
            hash_ok = copy_info["stream_sha256"] == copy_info["dest_sha256"]
            # listed size may be 0 or previous measurement
            item["大小与清单一致"] = dest_st.st_size == rec.get("字节数")
            item["大小源与目标一致"] = size_ok
            item["哈希源与目标一致"] = hash_ok
            item["共享盘未删未移"] = src.exists() and st_after.st_size == st_before.st_size
            if size_ok and hash_ok and item["共享盘未删未移"]:
                item["status"] = "成功"
                item["copied"] = True
                isolated += 1
            else:
                item["status"] = "失败_校验不一致"
                item["copied"] = False
                failed += 1
            results.append(item)
            log({
                "event": "copy",
                "原片ID": rec.get("原片ID"),
                "status": item["status"],
                "size": dest_st.st_size,
                "sha256": copy_info["dest_sha256"],
                "elapsed_sec": copy_info["elapsed_sec"],
            })
        except Exception as e:
            # never delete source on failure
            still = None
            try:
                still = src.exists()
            except Exception:
                still = "unknown"
            item["status"] = "失败_拷贝异常"
            item["copied"] = False
            item["error"] = f"{type(e).__name__}: {e}"
            item["共享盘未删未移"] = still
            failed += 1
            results.append(item)
            log({"event": "error", "原片ID": rec.get("原片ID"), "error": item["error"], "share_still": still})
            # cleanup dest partial if any
            tmp = dest.with_name(dest.name + ".partial_copy")
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    summary = {
        "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "时区": "Asia/Shanghai",
        "待隔离": 30,
        "成功": isolated,
        "失败": failed,
        "排除未拷贝的超时恢复": skipped,
        "共享盘删除或移动": 0,
        "说明": "只拷贝到项目目录，不移动、不重命名、不删除共享盘上任何文件。",
    }
    out = {"summary": summary, "records": results}
    (DEST_ROOT / "隔离结果.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)

if __name__ == "__main__":
    main()
