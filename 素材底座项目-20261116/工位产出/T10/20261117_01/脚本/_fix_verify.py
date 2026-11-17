# -*- coding: utf-8 -*-
from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\脚本\t10_post.py")
t = p.read_text(encoding="utf-8-sig")
old = 'origin_qual = "；".join([x for x in [p.get("evidence"), p.get("reason"), p.get("context"), p.get("product_identity")] if x])'
new = 'origin_qual = "；".join([x if isinstance(x, str) else json.dumps(x, ensure_ascii=False) for x in [p.get("evidence"), p.get("reason"), p.get("context"), p.get("product_identity")] if x])'
if old not in t:
    raise SystemExit("pattern not found")
p.write_text(t.replace(old, new), encoding="utf-8")
print("patched")
