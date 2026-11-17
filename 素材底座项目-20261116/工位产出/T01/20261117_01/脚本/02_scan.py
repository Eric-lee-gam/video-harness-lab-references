# -*- coding: utf-8 -*-
"""只读扫描配置中的四个素材库根路径，写出扫描清单。根路径不存在时只报“路径不存在”，不去读别处。"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    PASSWORD_NAME_MARK,
    PHOTO_EXTS,
    UNLISTED_LIMIT_WORDS,
    VOCAB_LIMIT_DIRS,
    config_path,
    format_mtime,
    load_config,
    now_iso,
    this_output_dir,
    to_posix,
    write_json,
)


def is_video(name: str, video_exts: set[str]) -> bool:
    return Path(name).suffix.lower() in video_exts

def is_apple_double(name: str) -> bool:
    return name.startswith("._")


def looks_like_mp4_by_magic(path: Path) -> bool:
    """只读文件头，判断无扩展名文件是不是 mp4/mov。"""
    try:
        with path.open("rb") as f:
            head = f.read(32)
    except OSError:
        return False
    return (len(head) >= 8 and head[4:8] == b"ftyp") or (b"ftyp" in head[:16])



def walk_library(root: Path, lib: dict, video_exts: set[str], progress_every: int = 500):
    """Yield file records. Raises FileNotFoundError if root does not exist."""
    if not root.exists():
        raise FileNotFoundError("路径不存在")
    if not root.is_dir():
        raise FileNotFoundError("路径不存在")

    share_rel_root = to_posix(lib["相对根路径"])
    n = 0
    t0 = time.perf_counter()
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                entries = list(it)
        except FileNotFoundError:
            # 扫描过程中某个子目录突然不可见，记下来但不改去别处
            yield {"_error": "子目录不可访问", "path": str(current)}
            continue
        except PermissionError:
            yield {"_error": "没有权限", "path": str(current)}
            continue
        # dirs first later
        dirs = []
        for ent in entries:
            try:
                is_dir = ent.is_dir(follow_symlinks=False)
            except OSError:
                yield {"_error": "无法判断类型", "path": ent.path}
                continue
            if is_dir:
                dirs.append(ent)
                continue
            name = ent.name
            if PASSWORD_NAME_MARK in name:
                yield {
                    "_skipped": "资料账号密码",
                    "path": ent.path,
                    "name": name,
                }
                continue
            try:
                st = ent.stat(follow_symlinks=False)
            except OSError as e:
                yield {"_error": f"无法读取状态:{e}", "path": ent.path}
                continue
            rel_from_lib = to_posix(os.path.relpath(ent.path, root))
            share_rel = f"{share_rel_root}/{rel_from_lib}" if rel_from_lib != "." else share_rel_root
            ext = Path(name).suffix.lower()
            if is_apple_double(name):
                rec = {
                    "库ID": lib["库ID"],
                    "目录名": lib["目录名"],
                    "库内相对路径": rel_from_lib,
                    "共享相对路径": share_rel,
                    "文件名": name,
                    "扩展名": ext,
                    "字节数": st.st_size,
                    "修改时间": format_mtime(st.st_mtime),
                    "修改时间戳": st.st_mtime,
                    "是视频": False,
                    "是照片": False,
                    "是AppleDouble": True,
                }
            else:
                is_vid = ext in video_exts
                if (not is_vid) and (not ext) and name not in {".DS_Store", "Thumbs.db"}:
                    is_vid = looks_like_mp4_by_magic(Path(ent.path))
                rec = {
                    "库ID": lib["库ID"],
                    "目录名": lib["目录名"],
                    "库内相对路径": rel_from_lib,
                    "共享相对路径": share_rel,
                    "文件名": name,
                    "扩展名": ext,
                    "字节数": st.st_size,
                    "修改时间": format_mtime(st.st_mtime),
                    "修改时间戳": st.st_mtime,
                    "是视频": is_vid,
                    "是照片": ext in PHOTO_EXTS,
                    "无扩展名按文件头识别": bool(is_vid and not ext),
                }
            n += 1
            if n % progress_every == 0:
                dt = time.perf_counter() - t0
                print(f"  [{lib['目录名']}] 已扫 {n} 个文件, 用时 {dt:.1f}s, 当前 {rel_from_lib}", flush=True)
            yield rec
        # 稳定顺序
        for ent in sorted(dirs, key=lambda e: e.name):
            stack.append(Path(ent.path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    parser.add_argument("--out-dir", default=str(this_output_dir()))
    args = parser.parse_args()

    cfg = load_config(Path(args.config))
    out_dir = Path(args.out_dir)
    video_exts = set(x.lower() for x in cfg.get("视频扩展名", []))
    scan_path = out_dir / "输入副本" / "扫描清单.jsonl"
    summary_path = out_dir / "统计" / "扫描摘要.json"
    err_path = out_dir / "核对" / "扫描异常.jsonl"

    print(f"开始扫描 {now_iso()}", flush=True)
    t0 = time.perf_counter()
    rows = []
    errors = []
    skipped = []
    by_lib = {}
    ext_counter = Counter()
    unlisted = []

    for lib in cfg["库"]:
        root = Path(lib["根路径"])
        print(f"扫描 {lib['目录名']} ...", flush=True)
        lib_t0 = time.perf_counter()
        lib_videos = 0
        lib_files = 0
        try:
            for rec in walk_library(root, lib, video_exts):
                if rec.get("_error"):
                    errors.append({"库ID": lib["库ID"], **rec})
                    continue
                if rec.get("_skipped"):
                    skipped.append({"库ID": lib["库ID"], **rec})
                    continue
                rows.append(rec)
                lib_files += 1
                ext_counter[rec["扩展名"] or "(无扩展名)"] += 1
                if rec["是视频"]:
                    lib_videos += 1
                    # 未收录限制字样（只看目录路径，不含文件名以免误伤）
                    dir_part = rec["共享相对路径"].rsplit("/", 1)[0]
                    hit_vocab = False
                    for item in VOCAB_LIMIT_DIRS:
                        if dir_part == item["相对前缀"] or dir_part.startswith(item["相对前缀"] + "/"):
                            hit_vocab = True
                            break
                    if not hit_vocab:
                        for w in UNLISTED_LIMIT_WORDS:
                            if w in dir_part:
                                unlisted.append({
                                    "共享相对路径": rec["共享相对路径"],
                                    "字样": w,
                                    "目录": dir_part,
                                })
                                break
        except FileNotFoundError:
            print(f"路径不存在: 库={lib['目录名']}", flush=True)
            write_json(summary_path, {
                "结果": "路径不存在",
                "库ID": lib["库ID"],
                "目录名": lib["目录名"],
                "配置键": "根路径",
            })
            print("路径不存在")
            sys.exit(2)

        by_lib[lib["库ID"]] = {
            "目录名": lib["目录名"],
            "文件数": lib_files,
            "视频数": lib_videos,
            "用时秒": round(time.perf_counter() - lib_t0, 2),
        }
        print(f"  [{lib['目录名']}] 文件 {lib_files}, 视频 {lib_videos}, 用时 {time.perf_counter()-lib_t0:.1f}s", flush=True)

    # 去重 unlisted 目录级
    seen_dirs = set()
    unlisted_unique = []
    for item in unlisted:
        key = (item["目录"], item["字样"])
        if key in seen_dirs:
            continue
        seen_dirs.add(key)
        unlisted_unique.append(item)

    scan_path.parent.mkdir(parents=True, exist_ok=True)
    with scan_path.open("w", encoding="utf-8", newline="\n") as f:
        for rec in rows:
            # 不把内部时间戳以外的额外大字段再加了
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    if errors:
        err_path.parent.mkdir(parents=True, exist_ok=True)
        with err_path.open("w", encoding="utf-8", newline="\n") as f:
            for rec in errors:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    videos = [r for r in rows if r["是视频"]]
    apple = [r for r in rows if r.get("是AppleDouble")]
    magic_videos = [r for r in videos if r.get("无扩展名按文件头识别")]
    summary = {
        "AppleDouble已排除不出镜片表": len(apple),
        "无扩展名按文件头识别为视频": len(magic_videos),
        "开始时间": None,
        "结束时间": now_iso(),
        "用时秒": round(time.perf_counter() - t0, 2),
        "配置文件": str(Path(args.config)),
        "总文件数": len(rows),
        "总视频数": len(videos),
        "分库": by_lib,
        "扩展名": dict(ext_counter),
        "扫描异常数": len(errors),
        "跳过资料账号密码数": len(skipped),
        "跳过资料账号密码样例": skipped[:20],
        "未收录限制目录": unlisted_unique,
        "未收录限制涉及视频数": len(unlisted),
        "清单路径": str(scan_path),
    }
    write_json(summary_path, summary)
    print(f"完成扫描 总文件={len(rows)} 总视频={len(videos)} 用时={summary['用时秒']}s")
    print(f"清单: {scan_path}")
    print(f"摘要: {summary_path}")
    if unlisted_unique:
        print(f"发现未收录限制目录 {len(unlisted_unique)} 个，见摘要。")


if __name__ == "__main__":
    main()
