from pathlib import Path
import re
scripts = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\脚本")
pat = re.compile(r"(write_text|write_bytes|open\(|mkdir\(|makedirs\(|shutil\.(copy|copy2|copytree|move|rmtree)|os\.(remove|unlink|rename|replace|mkdir)|Path\([^)]+\)\.(write|unlink|rename)|dump\()", re.I)
for p in sorted(scripts.glob("*.py")):
    text = p.read_text(encoding="utf-8")
    hits=[]
    for i,line in enumerate(text.splitlines(),1):
        if pat.search(line) and not line.strip().startswith("#"):
            hits.append((i, line.strip()[:220]))
    if hits:
        print("="*60, p.name)
        for i,l in hits:
            print(f"  {i}: {l}")
