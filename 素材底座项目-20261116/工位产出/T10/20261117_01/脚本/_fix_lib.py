# -*- coding: utf-8 -*-
from pathlib import Path
import ast
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\脚本\t10_lib.py")
t = p.read_text(encoding="utf-8-sig")
t = t.replace(
    'r"\\\\192.168.110.36\\共享本公司\\"',
    '"\\\\\\\\192.168.110.36\\\\共享本公司\\\\"',
)
# The file content as actually stored uses single backslashes in the raw source.
# Do a line-based replace to be safe.
lines = t.splitlines(True)
out = []
for line in lines:
    stripped = line.strip()
    if "192.168.110.36" in line and "共享本公司" in line:
        # rewrite any UNC literal using chr(92)
        if "markers" in "".join(out[-3:]) or stripped.startswith("r\"\\\\") or stripped.startswith('r"\\'):
            pass
        # we'll replace known bad patterns after joining
    out.append(line)
text = "".join(out)
# explicit replacements of the exact bad lines
text = text.replace(
    '        r"\\192.168.110.36\\共享本公司\\",\n',
    '        "\\\\" + "\\\\192.168.110.36\\\\共享本公司\\\\",\n',
)
# hmm this is messy because of how the file actually stores backslashes.
# Let's replace by line number logic.
lines = text.splitlines()
for i, line in enumerate(lines):
    if "192.168.110.36" in line and "共享本公司" in line:
        # Build a safe assignment
        if "SHARED_UNC =" in line and "PREFIXES" not in line:
            lines[i] = 'SHARED_UNC = "\\\\\\\\192.168.110.36\\\\共享本公司"'
        elif 'r"//192.168.110.36/共享本公司/"' in line or "//192.168.110.36/共享本公司/" in line:
            lines[i] = '    "//192.168.110.36/共享本公司/",'
        elif "PREFIXES" not in line:
            # list items
            if line.strip().endswith(","):
                # decide trailing slash or not
                if line.rstrip().endswith('\\",') or line.rstrip().endswith('\\",') or line.rstrip()[-3:] in ('\\",', '\\"'):
                    lines[i] = '    "\\\\\\\\192.168.110.36\\\\共享本公司\\\\",'
                else:
                    # keep as is if already safe, else no trailing slash
                    if line.count("共享本公司") and ("markers" in "\n".join(lines[max(0,i-3):i+1]) or True):
                        # inspect ending
                        print("LINE", i+1, repr(line))
# do a cleaner approach: rewrite the two constant blocks completely via markers
src = "\n".join(lines)
# I'll just rewrite from scratch the beginning constants using unique placeholders
p.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("intermediate written")
for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
    if "192.168" in line or i <= 70 and i >= 18:
        if "192.168" in line or "SHARED" in line or "markers" in line:
            print(f"{i}:{line!r}")
