# -*- coding: utf-8 -*-
"""根据共同约定生成 片段库/配置/素材库.json。共享盘地址只写入配置，不写死在本脚本。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (
    config_path,
    fragment_dir,
    join_unc,
    now_iso,
    project_dir,
    read_share_root,
    this_output_dir,
    write_json,
)


def build_config(share_root: str) -> dict:
    libs = [
        {
            "库ID": "xiaoq",
            "目录名": "小区",
            "相对根路径": "拍摄/小区",
            "根路径": join_unc(share_root, "拍摄", "小区"),
            "镜序库别名": "xiaoq",
            "标注库名": "小区全库",
            "来源类型": "自拍·小区项目",
        },
        {
            "库ID": "ceshi",
            "目录名": "测试",
            "相对根路径": "拍摄/测试",
            "根路径": join_unc(share_root, "拍摄", "测试"),
            "镜序库别名": "",
            "标注库名": "测试阿明搅拌",
            "来源类型": "自拍·测试演示",
        },
        {
            "库ID": "aming",
            "目录名": "阿明",
            "相对根路径": "拍摄/阿明",
            "根路径": join_unc(share_root, "拍摄", "阿明"),
            "镜序库别名": "",
            "标注库名": "测试阿明搅拌",
            "来源类型": "自拍·人物口播",
        },
        {
            "库ID": "jiaoban",
            "目录名": "搅拌",
            "相对根路径": "拍摄/搅拌",
            "根路径": join_unc(share_root, "拍摄", "搅拌"),
            "镜序库别名": "",
            "标注库名": "测试阿明搅拌",
            "来源类型": "自拍·展厅",
        },
    ]
    return {
        "版本": "T01-20261117_01",
        "生成时间": now_iso(),
        "共享盘根路径": share_root,
        "逻辑路径前缀": "@shared",
        "库": libs,
        "视频扩展名": [".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".wmv", ".mpg", ".mpeg", ".ts", ".flv", ".webm", ".3gp", ".insv", ".mxf"],
        "说明": "根路径只出现在本配置中。后续脚本必须从这里读取，不得写死共享盘地址。一级目录名为“展厅”的原片，来源类型按自拍·展厅填写。",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(config_path()))
    args = parser.parse_args()
    share_root = read_share_root()
    cfg = build_config(share_root)
    out = Path(args.config)
    write_json(out, cfg)
    # 产出目录留一份副本
    write_json(this_output_dir() / "统计" / "素材库.json", cfg)
    print(f"已写入 {out}")
    print(f"库条数: {len(cfg['库'])}")
    for lib in cfg["库"]:
        print(f"  {lib['目录名']}: 根路径已写入配置, 镜序库别名={lib['镜序库别名'] or '（空）'}, 标注库名={lib['标注库名']}, 来源类型={lib['来源类型']}")
    # 自检：四个目录
    names = [x["目录名"] for x in cfg["库"]]
    if names != ["小区", "测试", "阿明", "搅拌"]:
        raise SystemExit(f"配置目录名不符合预期: {names}")


if __name__ == "__main__":
    main()
