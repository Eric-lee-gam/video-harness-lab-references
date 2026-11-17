# -*- coding: utf-8 -*-
from pathlib import Path
import re

gang = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116\素材标注总纲.md")
text = gang.read_text(encoding="utf-8")
# print headings and option-like lines, keep shorter
for i, line in enumerate(text.splitlines(), 1):
    s=line.strip()
    if s.startswith("#") or s.startswith("|") and ("字段" in s or "标签" in s or "选项" in s or "代码" in s or "编号" in s):
        print(f"{i}:{line}")
    elif re.match(r"^#+ ", line) or re.match(r"^[A-Z]\d", s) or re.match(r"^[-*] \*\*", s):
        print(f"{i}:{line}")
print("---- GANG LINES", len(text.splitlines()), "chars", len(text))
# also print first 80 lines
print("\n===== FIRST 120 LINES =====")
for i, line in enumerate(text.splitlines()[:120], 1):
    print(f"{i}:{line}")
