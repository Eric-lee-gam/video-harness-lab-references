from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果\02_structures.txt")
text = p.read_text(encoding="utf-8")
parts = text.split("====")
# print official counts (part 6) but maybe truncate first-rule dumps
part6 = parts[6]
# keep lines that don't start with "  first" or are not huge json dumps... actually I want counts
for line in part6.splitlines():
    if line.startswith("  first") or line.startswith("  first rule") or line.startswith("  row keys"):
        # shorten
        print(line[:300])
        continue
    if len(line) > 500 and line.strip().startswith("{") or "first rule" in line:
        print(line[:300] + "...")
        continue
    print(line)
