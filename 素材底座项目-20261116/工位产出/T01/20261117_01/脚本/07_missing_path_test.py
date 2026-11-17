# -*- coding: utf-8 -*-
"""把配置里的根路径换成不存在的路径再跑扫描，必须报“路径不存在”，不去读别处。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import config_path, now_iso, this_output_dir, write_json, load_config


def main():
    out_dir = this_output_dir()
    src = load_config(config_path())
    fake = json.loads(json.dumps(src, ensure_ascii=False))
    fake_root = r"D:\path-does-not-exist-t01-20261117\not-a-real-library"
    fake["共享盘根路径"] = fake_root
    for lib in fake["库"]:
        lib["根路径"] = str(Path(fake_root) / lib["目录名"])
    tmp_cfg = out_dir / "统计" / "素材库_不存在路径测试.json"
    tmp_out = out_dir / "统计" / "missing-path-run"
    tmp_out.mkdir(parents=True, exist_ok=True)
    tmp_cfg.write_text(json.dumps(fake, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    scan = Path(__file__).with_name("02_scan.py")
    proc = subprocess.run(
        [sys.executable, str(scan), "--config", str(tmp_cfg), "--out-dir", str(tmp_out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    has_msg = "路径不存在" in combined
    # 不应该去读别的地方：输出里不应出现真实库扫描进度（已扫 N 个文件）
    scanned_elsewhere = "已扫 " in (proc.stdout or "")
    report = {
        "时间": now_iso(),
        "退出码": proc.returncode,
        "输出含有路径不存在": has_msg,
        "是否扫描到了别的地方": scanned_elsewhere,
        "标准输出": (proc.stdout or "")[-2000:],
        "标准错误": (proc.stderr or "")[-2000:],
        "结论": "通过" if (has_msg and proc.returncode != 0 and not scanned_elsewhere) else "未通过",
    }
    write_json(out_dir / "核对" / "不存在路径测试.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["结论"] != "通过":
        sys.exit(1)


if __name__ == "__main__":
    main()
