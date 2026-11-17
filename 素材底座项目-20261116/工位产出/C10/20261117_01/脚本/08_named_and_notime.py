from pathlib import Path
import json, sqlite3, re, collections

raw = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\原始副本")
lib = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
mid = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\检查中间结果")
aa = raw / "镜序" / "action-annotation"
lines=[]
def log(s=""):
    lines.append(s)

def loadj(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

# load facts, bans
facts=[]; bans=[]
with (lib/"事实层.jsonl").open(encoding="utf-8") as f:
    facts=[json.loads(l) for l in f if l.strip()]
with (lib/"禁用表.jsonl").open(encoding="utf-8") as f:
    bans=[json.loads(l) for l in f if l.strip()]

def rec_text(r):
    return json.dumps(r, ensure_ascii=False)

# named searches in facts+bans
needles = [
    "二印小区厨卫",
    "主要人物不是阿明",
    "不是阿明",
    "水洗石",
    "这是水洗石",
    "不是微陶泥",
    "本片段不是微陶泥",
    "P24",
    "P17",
    "汉阳月印府",
    "美女人设",
    "离职",
    "不能使用",
]
log("==== named hits in 事实层/禁用表 ====")
for needle in needles:
    fhits=[r for r in facts if needle in rec_text(r)]
    bhits=[r for r in bans if needle in rec_text(r)]
    log(f"\nNEEDLE {needle!r}: facts={len(fhits)} bans={len(bhits)}")
    for r in fhits[:8]:
        log(f"  FACT {r.get('事实编号')} src={r.get('来源文件')} id={r.get('来源条目标识')} sid={r.get('样例编号')} path={r.get('主库相对路径')} {r.get('起秒')}-{r.get('止秒')} 反例={r.get('是否反例')}")
        # excerpt evidence/限定语
        log(f"    限定语={str(r.get('限定语原文'))[:300]}")
    for r in bhits[:5]:
        log(f"  BAN {r.get('规则ID')} {r.get('主库相对路径')} 原文={str(r.get('禁用原文'))[:200]}")

# search originals: sqlite payloads, official json
log("\n==== named hits in originals (official json + sqlite confirmed) ====")
# sqlite
uri = "file:" + (raw/"镜序"/"learning.sqlite3").as_posix() + "?mode=ro&immutable=1"
conn=sqlite3.connect(uri, uri=True)
conn.row_factory=sqlite3.Row
for row in conn.execute("SELECT id, status, reviewer, payload FROM rules WHERE id LIKE 'confirmed-%'"):
    if any(n in (row["payload"] or "") for n in ["水洗石","不是微陶泥","二印","P17","P24","美女人设","不是阿明"]):
        pay=json.loads(row["payload"])
        log(f"  RULE {row['id']} keys_hit text/evidence/product: text={pay.get('text')} ev={str(pay.get('evidence'))[:200]} prod={pay.get('product_identity')} ctx={str(pay.get('context'))[:200]} path_asset={pay.get('asset_id')} {pay.get('start')}-{pay.get('end')}")
conn.close()

# official json search
for p in sorted(aa.glob("*.json")):
    n=p.name.lower()
    if ".before-" in n or "discovery" in n:
        continue
    txt=p.read_text(encoding="utf-8")
    hits=[nd for nd in ["水洗石","不是微陶泥","二印小区","P24-A","美女人设","离职了"] if nd in txt]
    if hits:
        log(f"  FILE {p.name} hits={hits}")

# 片段级 no time details
log("\n==== 片段级无起止秒 by 来源 ====")
no=[]
for r in facts:
    if r.get("确认级别")=="片段级":
        no_time = r.get("起秒") in (None,"") or r.get("止秒") in (None,"") or r.get("无起止秒") is True
        if no_time:
            no.append(r)
log(f"count={len(no)}")
c=collections.Counter((r["来源文件"], r.get("样例类别"), bool(r.get("无起止秒")), r.get("起秒") in (None,""), r.get("止秒") in (None,"")) for r in no)
for k,v in c.most_common():
    log(f"  {v}: src={k[0]} cat={k[1]} flag无起止秒={k[2]} 起空={k[3]} 止空={k[4]}")
# samples
for r in no[:5]:
    log(f"  ex {r['事实编号']} {r['来源条目标识']} 起={r.get('起秒')!r} 止={r.get('止秒')!r} 无={r.get('无起止秒')} path={r.get('主库相对路径')}")

# 对照表 / 人物身份确认办法 length
for name in [raw/"规则"/"人物身份确认办法.md", raw/"规则"/"出镜文件夹确认图"/"对照表.md"]:
    log(f"\n==== FILE {name} ({name.stat().st_size} bytes) ====")
    text=name.read_text(encoding="utf-8")
    log(f"lines={len(text.splitlines())}")
    # write separately full later; here structure cues
    if "对照表" in name.name or "对照表" in str(name):
        # count table rows / sheet / folder headings
        log("headings:")
        for i,L in enumerate(text.splitlines(),1):
            if L.startswith("#") or L.startswith("| 图") or "sheet_" in L or L.startswith("##"):
                log(f"  L{i}: {L[:200]}")

(mid/"04_named_and_notime.txt").write_text("\n".join(lines), encoding="utf-8")
print("wrote", len(lines), "lines")
