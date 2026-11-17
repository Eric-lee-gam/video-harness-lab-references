# -*- coding: utf-8 -*-
import json
from pathlib import Path
OUT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
c = json.loads((OUT / "统计" / "李康与镜序说法对照.json").read_text(encoding="utf-8"))
print("=== contradictions ===")
print("total", c["条数"], "hard", len(c["硬冲突"]))
for h in c["需注意"]:
    print(json.dumps(h, ensure_ascii=False))
print("\n=== missing 29 sample ===")
m = json.loads((OUT / "统计" / "小区无粗标原片.json").read_text(encoding="utf-8"))
print("n", m["条数"])
for rec in m["清单"][:29]:
    print(rec["镜序素材ID"], rec["rel"])
print("\n=== verify 20 ids ===")
v = json.loads((OUT / "统计" / "随机20条对照.json").read_text(encoding="utf-8"))
print("all_ok", v["全部一字不差"])
for r in v["抽到的20条"]:
    print(r["事实编号"], r["来源条目标识"], r["主库相对路径"], r["起秒"], r["止秒"])
