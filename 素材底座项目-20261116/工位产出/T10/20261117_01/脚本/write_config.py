# -*- coding: utf-8 -*-
import json
from pathlib import Path

cfg = {
    "version": "T10-20261117_01",
    "共享盘": {
        "主库UNC": "\\\\192.168.110.36\\共享本公司\\史上最完整共享",
        "主库相对路径前缀": "史上最完整共享",
        "标注库UNC": "\\\\192.168.110.36\\obsidian\\素材标注",
        "不用盘符": "Z:"
    },
    "镜序根别名": {
        "xiaoq": {
            "主库相对路径前缀": "史上最完整共享\\拍摄\\小区",
            "范围": "范围内",
            "目录": "小区"
        },
        "baba": {
            "主库相对路径前缀": "史上最完整共享\\扒扒",
            "范围": "范围外",
            "目录": "扒扒"
        },
        "chengdu": {
            "主库相对路径前缀": None,
            "范围": "范围外",
            "目录": "chengdu",
            "说明": "登记表有 104 条，主库对应目录未在本批输入中写明"
        },
        "suzhou": {
            "主库相对路径前缀": None,
            "范围": "范围外",
            "目录": "suzhou",
            "说明": "登记表有 54 条，主库对应目录未在本批输入中写明"
        }
    },
    "第一条线范围目录": ["小区", "测试", "阿明", "搅拌"],
    "范围内主库相对路径前缀": [
        "史上最完整共享\\拍摄\\小区",
        "史上最完整共享\\拍摄\\测试",
        "史上最完整共享\\拍摄\\阿明",
        "史上最完整共享\\拍摄\\搅拌"
    ],
    "出镜人标准叫法": ["阿明", "李总", "小羊", "徐经理", "美女姐姐"],
    "本机路径": {
        "项目文件夹": "D:\\codex-work\\codex-company\\video-harness-lab\\references\\素材底座项目-20261116",
        "规则文件夹": "D:\\codex-work\\codex-company\\video-harness-lab\\references\\素材标注总纲-20261116",
        "镜序完整包": "D:\\CutFrame项目完整整理_20261116",
        "Python": "C:\\Python314\\python.exe"
    },
    "说明": "T10 开工时写入。脚本从这份配置读地址、库名和人名，不把密钥写入产出。主库清单 36-gongxiang.csv 在约定位置未找到。"
}

text = json.dumps(cfg, ensure_ascii=False, indent=2)
for dest in [
    Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库\配置\路径与库名.json"),
    Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\配置\路径与库名.json"),
]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(text, encoding="utf-8")
    print("WROTE", dest)
