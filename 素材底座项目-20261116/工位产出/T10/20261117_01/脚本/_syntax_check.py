import ast, pathlib
p = pathlib.Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\脚本\t10_c10_fix.py")
ast.parse(p.read_text(encoding="utf-8-sig"))
print("SYNTAX_OK")
