from pathlib import Path

# The previous script output was huge. Let's just extract key sections from what we need
# and write a compact listing.

src = Path(r"C:\Users\leega\agent-tools\12a247ea-c242-4fec-a3e9-1721e8c14e77.txt")
text = src.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()
print("total lines", len(lines))
print("first 80:")
for L in lines[:80]:
    print(L)
print("\n======= lines with json/md/csv/sqlite in action-annotation or cutframe/ai =======")
# reprint by re-running compact logic
