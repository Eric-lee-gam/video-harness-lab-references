# -*- coding: utf-8 -*-
import json
from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\统计\李康与镜序说法对照.json")
c = json.loads(p.read_text(encoding="utf-8"))
c["人工复核"] = {
    "结论": "自动扫描 4 处里，2 处（武汉理工大学 F0118 vs V1、常青花园四小区 F0119 vs R07）并不相反；博学仕府 F0123 vs V3 为混杂文件夹与阿明正例，兼容；二印小区 F0131 文件夹「是阿明（未逐条看）」与 V2「该段主要人物不是阿明」需要人定，已写问题单。",
    "需上报": ["F0131 vs F0035 / confirmed-V2"]
}
p.write_text(json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8")
print("updated conflict review")
