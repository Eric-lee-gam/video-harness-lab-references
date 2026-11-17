from pathlib import Path
import json, collections, sqlite3

out = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01")
raw = out / "原始副本"
mid = out / "检查中间结果"
lib = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
aa = raw / "镜序" / "action-annotation"
lines = []
def log(s=""):
    lines.append(s)
    print(s)

def loadj(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

# fact layer breakdown
facts = []
with (lib/"事实层.jsonl").open(encoding="utf-8") as f:
    for line in f:
        if line.strip():
            facts.append(json.loads(line))
log(f"facts={len(facts)}")
by_src = collections.Counter(r["来源文件"] for r in facts)
by_cat = collections.Counter(r.get("样例类别") for r in facts)
by_lvl = collections.Counter(r.get("确认级别") for r in facts)
by_scope = collections.Counter(r.get("范围") for r in facts)
by_dir = collections.Counter(r.get("目录") for r in facts)
by_status = collections.Counter(r.get("确认状态") for r in facts)
by_neg = collections.Counter(r.get("是否反例") for r in facts)
n_no_time = sum(1 for r in facts if r.get("无起止秒") or r.get("起秒") in (None, "") or r.get("止秒") in (None, ""))
n_seglvl = sum(1 for r in facts if r.get("确认级别")=="片段级")
n_seglvl_notime = sum(1 for r in facts if r.get("确认级别")=="片段级" and (r.get("起秒") in (None,"") or r.get("止秒") in (None,"") or r.get("无起止秒")))
log("by 来源文件:")
for k,v in by_src.most_common():
    log(f"  {v:4d}  {k}")
log("by 样例类别:")
for k,v in by_cat.most_common():
    log(f"  {v:4d}  {k}")
log(f"级别={dict(by_lvl)} 范围={dict(by_scope)} 目录={dict(by_dir)}")
log(f"状态={dict(by_status)} 反例={dict(by_neg)}")
log(f"无起止秒标记或空={n_no_time} 片段级={n_seglvl} 片段级无起止={n_seglvl_notime}")

# missing required fields
req = ["主库相对路径","原片ID","起秒","止秒","内容","来源文件","来源条目标识","确认人","确认时间"]
for k in req:
    miss = sum(1 for r in facts if k not in r)
    empty = sum(1 for r in facts if r.get(k) in (None, "", []))
    log(f"field {k}: missing_key={miss} empty={empty}")

# bans, clues, evals breakdown
bans=[]; clues=[]; evals=[]
with (lib/"禁用表.jsonl").open(encoding="utf-8") as f:
    bans=[json.loads(l) for l in f if l.strip()]
with (lib/"线索.jsonl").open(encoding="utf-8") as f:
    clues=[json.loads(l) for l in f if l.strip()]
with (lib/"评价与采用.jsonl").open(encoding="utf-8") as f:
    evals=[json.loads(l) for l in f if l.strip()]
log(f"\nbans={len(bans)} clues={len(clues)} evals={len(evals)}")
log("ban sources:")
for b in bans:
    log("  " + json.dumps({k:b.get(k) for k in ["来源文件","来源条目标识","确认人","主库相对路径","内容"] if k in b or True}, ensure_ascii=False)[:500])
    log("  FULL keys "+str(list(b.keys())))
    log("  " + json.dumps(b, ensure_ascii=False)[:1500])

by_ekind = collections.Counter(r.get("类型") or r.get("记录类型") or r.get("样例类别") or str(r.get("来源文件")) for r in evals)
log(f"evals kinds {by_ekind}")
# peek keys
log("eval keys "+str(list(evals[0].keys())))
log("clue keys "+str(list(clues[0].keys())))
log("clue 来源 " + str(collections.Counter(c.get("来源文件") for c in clues)))

# official batch/product/person status counts compact
log("\n==== official batch/product/person status ====")
for p in sorted(aa.glob("*.json")):
    n=p.name
    if ".before-" in n.lower() or "discovery" in n.lower():
        continue
    if not (n.startswith("batch-") or n.startswith("product-") or n.startswith("person-") or n.startswith("P24")):
        continue
    if n in ("person-coverage.json",):
        continue
    obj=loadj(p)
    rows=obj.get("rows") if isinstance(obj, dict) else None
    if rows is None:
        log(f"{n}: no rows, keys={list(obj.keys()) if isinstance(obj,dict) else type(obj)}")
        continue
    st=collections.Counter(r.get("status") for r in rows)
    ids=[r.get("sample_id") for r in rows]
    log(f"{n}: n={len(rows)} status={dict(st)} ids={ids}")

(mid/"03_fact_breakdown.txt").write_text("\n".join(lines), encoding="utf-8")
print("wrote breakdown", len(lines))
