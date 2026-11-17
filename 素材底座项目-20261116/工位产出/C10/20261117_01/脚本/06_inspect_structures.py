from pathlib import Path
import json, collections, itertools

out = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01")
raw = out / "原始副本"
mid = out / "检查中间结果"
lib = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\片段库")
lines = []
def log(s=""):
    lines.append(s)

def load_json(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))

def json_len_or_keys(obj, name):
    if isinstance(obj, list):
        log(f"{name}: list len={len(obj)}")
        if obj:
            log(f"  item keys: {list(obj[0].keys()) if isinstance(obj[0], dict) else type(obj[0])}")
        return
    if isinstance(obj, dict):
        log(f"{name}: dict keys={list(obj.keys())}")
        for k,v in obj.items():
            if isinstance(v, list):
                log(f"  {k}: list len={len(v)}")
                if v and isinstance(v[0], dict):
                    log(f"    first keys: {list(v[0].keys())}")
            elif isinstance(v, dict):
                log(f"  {k}: dict keys={list(v.keys())[:30]}")
            else:
                s = repr(v)
                if len(s)>200: s=s[:200]+"..."
                log(f"  {k}: {s}")
        return
    log(f"{name}: {type(obj)}")

# coverage
for name in ["sample-coverage.json", "person-coverage.json"]:
    p = raw / "镜序" / "action-annotation" / name
    log(f"\n==== {name} ====")
    json_len_or_keys(load_json(p), name)
    log(json.dumps(load_json(p), ensure_ascii=False, indent=2)[:4000])

# batch/product/person official files (not before/discovery)
aa = raw / "镜序" / "action-annotation"
official = []
for p in sorted(aa.glob("*.json")):
    n = p.name.lower()
    if ".before-" in n or "discovery" in n:
        continue
    official.append(p)

log("\n==== official json counts (no before/discovery) ====")
for p in official:
    obj = load_json(p)
    # count rows if present
    n_rows = None
    status_counts = collections.Counter()
    if isinstance(obj, dict) and "rows" in obj:
        rows = obj["rows"]
        n_rows = len(rows)
        for r in rows:
            st = r.get("status") or r.get("confirmed_label") or r.get("label")
            if isinstance(r, dict):
                status_counts[str(r.get("status"))] += 1
        log(f"{p.name}: rows={n_rows} top_keys={list(obj.keys())} status={dict(status_counts)}")
        if rows:
            log(f"  row keys: {list(rows[0].keys())}")
    elif isinstance(obj, dict) and "rules" in obj:
        log(f"{p.name}: rules={len(obj['rules'])} top_keys={list(obj.keys())}")
        if obj["rules"]:
            log(f"  rule keys: {list(obj['rules'][0].keys()) if isinstance(obj['rules'][0], dict) else type(obj['rules'][0])}")
            log("  first rule " + json.dumps(obj["rules"][0], ensure_ascii=False)[:800])
    elif isinstance(obj, list):
        log(f"{p.name}: list={len(obj)}")
        if obj and isinstance(obj[0], dict):
            log(f"  item keys: {list(obj[0].keys())}")
    else:
        json_len_or_keys(obj, p.name)

# identity evidence
p = raw / "镜序" / "identity-evidence.json"
obj = load_json(p)
log("\n==== identity-evidence.json ====")
json_len_or_keys(obj, "identity-evidence")
if isinstance(obj, list):
    ids = [x.get("id") or x.get("rule_id") or x.get("sample_id") for x in obj if isinstance(x, dict)]
    log(f"  n={len(obj)} sample ids {ids[:40]}")
    log("  first " + json.dumps(obj[0], ensure_ascii=False)[:1500])
elif isinstance(obj, dict):
    # maybe items/evidence
    log(json.dumps({k: (len(v) if isinstance(v, list) else type(v).__name__) for k,v in obj.items()}, ensure_ascii=False))

# peek fact layer
log("\n==== 片段库 outputs schema ====")
def peek_jsonl(path, n=3):
    recs = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i>=n: break
            recs.append(json.loads(line))
    # also count and key freq
    keys = collections.Counter()
    total = 0
    missing_fields = collections.Counter()
    with path.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            o = json.loads(line)
            for k in o:
                keys[k]+=1
    log(f"{path.name}: total={total} keys(count)={dict(keys)}")
    for i,r in enumerate(recs):
        log(f"  SAMPLE {i}: " + json.dumps(r, ensure_ascii=False)[:2000])
    return total

for name in ["事实层.jsonl", "评价与采用.jsonl", "禁用表.jsonl", "线索.jsonl"]:
    peek_jsonl(lib / name, 2)

# coarse: only first records + count later in dedicated script, just peek keys from first 5 and last 1
log("\n==== 粗标层 peek ====")
coarse = lib / "粗标层.jsonl"
keys = collections.Counter()
n=0
samples=[]
with coarse.open(encoding="utf-8") as f:
    for line in f:
        if not line.strip():
            continue
        o=json.loads(line)
        n+=1
        for k in o: keys[k]+=1
        if n<=3:
            samples.append(o)
        if n>=3:
            # don't full scan now, just 3 samples? we need total later
            break
log(f"粗标层 first-3 keys union shown; will count later")
for i,r in enumerate(samples):
    log(f"  SAMPLE {i} keys={list(r.keys())}")
    log("  " + json.dumps(r, ensure_ascii=False)[:2000])

# configs
for p in [lib/"配置"/"路径与库名.json", lib/"配置"/"素材库.json"]:
    log(f"\n==== {p} ====")
    log(p.read_text(encoding="utf-8"))

(mid/"02_structures.txt").write_text("\n".join(lines), encoding="utf-8")
print("wrote", mid/"02_structures.txt", "lines", len(lines))
