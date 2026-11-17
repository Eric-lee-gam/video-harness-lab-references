# -*- coding: utf-8 -*-
import json
from pathlib import Path
facts = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库\事实层.jsonl")
want = {"F0118","F0034","F0119","F0031","F0123","F0036","F0131","F0035"}
for line in facts.open(encoding="utf-8"):
    r = json.loads(line)
    if r.get("事实编号") in want:
        print("="*60)
        print(r["事实编号"], r.get("来源条目标识"), r.get("确认人"), r.get("主库相对路径"), r.get("起秒"), r.get("止秒"))
        print("限定语:", r.get("限定语原文"))
        c = r.get("内容")
        if isinstance(c, dict):
            for k in ("出镜的是谁","李康的判断","description","person_identity","evidence","confirmed_label"):
                if k in c:
                    print(k, ":", c[k])
