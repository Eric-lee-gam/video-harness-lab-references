# -*- coding: utf-8 -*-
"""只读扫描主库四个目录，自行数视频。不写共享盘。"""
from __future__ import annotations

import os
import time
from collections import Counter
from pathlib import Path

from c01_common import (
    IN_SCOPE_LIBS,
    PASSWORD_NAME_MARK,
    VIDEO_EXTS,
    format_mtime,
    is_apple_double,
    join_unc,
    looks_like_mp4_by_magic,
    now_iso,
    to_posix,
    write_json,
    write_jsonl,
)


def walk_library(root: Path, lib: dict, progress_every: int = 1000):
    if not root.exists() or not root.is_dir():
        raise FileNotFoundError(f"路径不存在: {root}")

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
            yield {"_error": "子目录不可访问", "path": str(current), "库ID": lib["库ID"]}
            continue
        except PermissionError:
            yield {"_error": "没有权限", "path": str(current), "库ID": lib["库ID"]}
            continue
        dirs = []
        for ent in entries:
            try:
                is_dir = ent.is_dir(follow_symlinks=False)
            except OSError:
                yield {"_error": "无法判断类型", "path": ent.path, "库ID": lib["库ID"]}
                continue
            if is_dir:
                dirs.append(ent)
                continue
            name = ent.name
            if PASSWORD_NAME_MARK in name:
                yield {"_skipped": "资料账号密码", "path": ent.path, "name": name, "库ID": lib["库ID"]}
                continue
            try:
                st = ent.stat(follow_symlinks=False)
            except OSError as e:
                yield {"_error": f"无法读取状态:{e}", "path": ent.path, "库ID": lib["库ID"]}
                continue
            rel_from_lib = to_posix(os.path.relpath(ent.path, root))
            share_rel = f"{share_rel_root}/{rel_from_lib}" if rel_from_lib != "." else share_rel_root
            ext = Path(name).suffix.lower()
            apple = is_apple_double(name)
            is_vid = False
            magic = False
            if not apple:
                is_vid = ext in VIDEO_EXTS
                if (not is_vid) and (not ext) and name not in {".DS_Store", "Thumbs.db"}:
                    magic = looks_like_mp4_by_magic(Path(ent.path))
                    is_vid = magic
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
                "是AppleDouble": apple,
                "无扩展名按文件头识别": bool(is_vid and magic),
                "绝对路径": ent.path,
            }
            n += 1
            if n % progress_every == 0:
                dt = time.perf_counter() - t0
                print(f"  [{lib['目录名']}] 已扫 {n} 个文件, 用时 {dt:.1f}s, 当前 {rel_from_lib}", flush=True)
            yield rec
        for ent in sorted(dirs, key=lambda e: e.name):
            stack.append(Path(ent.path))


def scan_four_dirs(share_root: str, out_dir: Path) -> dict:
    t0 = time.perf_counter()
    rows = []
    errors = []
    skipped = []
    by_lib = {}
    ext_counter = Counter()
    other_ext_videos_like = []

    for lib in IN_SCOPE_LIBS:
        root = Path(join_unc(share_root, *lib["相对根路径"].split("/")))
        print(f"扫描 {lib['目录名']} -> {root}", flush=True)
        lib_t0 = time.perf_counter()
        lib_videos = 0
        lib_files = 0
        lib_magic = 0
        lib_apple = 0
        for rec in walk_library(root, lib):
            if rec.get("_error"):
                errors.append(rec)
                continue
            if rec.get("_skipped"):
                skipped.append(rec)
                continue
            rows.append(rec)
            lib_files += 1
            ext_counter[rec["扩展名"] or "(无扩展名)"] += 1
            if rec["是视频"]:
                lib_videos += 1
            if rec.get("无扩展名按文件头识别"):
                lib_magic += 1
            if rec.get("是AppleDouble"):
                lib_apple += 1
            ext = rec["扩展名"]
            if ext and ext not in {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts",
                                   ".wmv", ".mpg", ".mpeg", ".ts", ".flv", ".webm", ".3gp",
                                   ".insv", ".mxf", ".jpg", ".jpeg", ".png", ".heic", ".heif",
                                   ".webp", ".bmp", ".tif", ".tiff", ".gif", ".txt", ".json",
                                   ".csv", ".xml", ".ini", ".db", ".ds_store"}:
                if not rec.get("是AppleDouble"):
                    other_ext_videos_like.append({
                        "共享相对路径": rec["共享相对路径"],
                        "扩展名": ext,
                        "字节数": rec["字节数"],
                    })
        by_lib[lib["库ID"]] = {
            "目录名": lib["目录名"],
            "根路径": str(root),
            "文件数": lib_files,
            "视频数": lib_videos,
            "无扩展名按文件头识别": lib_magic,
            "AppleDouble": lib_apple,
            "用时秒": round(time.perf_counter() - lib_t0, 2),
        }
        print(
            f"  [{lib['目录名']}] 文件 {lib_files}, 视频 {lib_videos}, "
            f"无扩展名视频 {lib_magic}, AppleDouble {lib_apple}, "
            f"用时 {time.perf_counter()-lib_t0:.1f}s",
            flush=True,
        )

    videos = [r for r in rows if r["是视频"]]
    apple = [r for r in rows if r.get("是AppleDouble")]
    magic_videos = [r for r in videos if r.get("无扩展名按文件头识别")]
    scan_path = out_dir / "核对" / "C01扫描清单.jsonl"
    summary_path = out_dir / "统计" / "C01扫描摘要.json"
    write_jsonl(scan_path, rows)
    summary = {
        "时间": now_iso(),
        "共享盘根路径来源": "共同约定.md 主库（只读）",
        "共享盘根路径": share_root,
        "总文件数": len(rows),
        "总视频数": len(videos),
        "AppleDouble": len(apple),
        "无扩展名按文件头识别为视频": len(magic_videos),
        "分库": by_lib,
        "扩展名": dict(ext_counter),
        "扫描异常数": len(errors),
        "跳过资料账号密码数": len(skipped),
        "跳过资料账号密码样例": skipped[:20],
        "扫描异常样例": errors[:20],
        "其他少见扩展名样例": other_ext_videos_like[:50],
        "用时秒": round(time.perf_counter() - t0, 2),
        "清单路径": str(scan_path),
    }
    write_json(summary_path, summary)
    print(f"完成扫描 总文件={len(rows)} 总视频={len(videos)} 用时={summary['用时秒']}s", flush=True)
    return {"rows": rows, "videos": videos, "summary": summary, "errors": errors, "skipped": skipped}
