# -*- coding: utf-8 -*-
import json, sqlite3
from pathlib import Path
from collections import Counter

LEARN = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\镜序副本\learning.sqlite3")
OUT = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01\_reads\02a_learning.txt")
lines = []

def w(s=""):
    lines.append(s)
    print(s)

conn = sqlite3.connect("file:" + LEARN.as_posix() + "?mode=ro&immutable=1", uri=True)
cur = conn.cursor()
w("rules status:")
for row in cur.execute("SELECT status, COUNT(*) FROM rules GROUP BY status"):
    w("  %s=%s" % row)

w("reviewer:")
for row in cur.execute("SELECT reviewer, COUNT(*) FROM rules GROUP BY reviewer"):
    w("  %r=%s" % row)

# dump each rule compact
w("")
w("ALL RULES")
confirmed_ids = []
approved_ids = []
for rid, created, status, reviewer, payload, fid in cur.execute(
    "SELECT id, created, status, reviewer, payload, feedback_id FROM rules ORDER BY created"
):
    p = json.loads(payload) if payload else {}
    raw = json.dumps(p, ensure_ascii=False)
    marker = "confirmed-" in raw or rid.startswith("confirmed-")
    if marker:
        confirmed_ids.append(rid)
    if status in ("approved", "passed", "accepted"):
        approved_ids.append(rid)
    # extract useful fields
    bits = [
        "id=" + rid,
        "status=" + (status or ""),
        "reviewer=" + (reviewer or "-"),
        "action=" + str(p.get("action")),
        "scope=" + str(p.get("scope")),
        "asset=" + str(p.get("asset_id") or ""),
        "start=" + str(p.get("start")),
        "end=" + str(p.get("end")),
    ]
    for k in ("id", "kind", "type", "sample_id", "evidence_id", "label", "description", "text", "reason"):
        if k in p and p[k] not in (None, ""):
            val = str(p[k])
            if len(val) > 80:
                val = val[:80] + "..."
            bits.append("%s=%s" % (k, val))
    extra_keys = [k for k in p.keys() if k not in (
        "action","scope","asset_id","start","end","id","kind","type","sample_id",
        "evidence_id","label","description","text","reason","reason_code","context",
        "project_id","path","rel","root","name"
    )]
    if extra_keys:
        bits.append("extra_keys=" + ",".join(extra_keys))
    if marker:
        bits.append("HAS_CONFIRMED_MARKER")
    w(" | ".join(bits))

w("")
w("confirmed-marker rules: %d" % len(confirmed_ids))
for x in confirmed_ids:
    w("  " + x)
w("approved-like rules: %d" % len(approved_ids))

# payload key union
keys = Counter()
for (payload,) in cur.execute("SELECT payload FROM rules"):
    p = json.loads(payload) if payload else {}
    keys.update(p.keys())
w("payload key union: " + json.dumps(dict(keys), ensure_ascii=False))

# action/scope
w("action: " + json.dumps(dict(Counter(json.loads(p).get("action") for (p,) in cur.execute("SELECT payload FROM rules"))), ensure_ascii=False))
w("scope: " + json.dumps(dict(Counter(json.loads(p).get("scope") for (p,) in cur.execute("SELECT payload FROM rules"))), ensure_ascii=False))

# runs structure
w("")
w("RUNS")
row = cur.execute("SELECT id, payload, result FROM runs").fetchall()
w("n=%d" % len(row))
p0 = json.loads(row[0][1]) if row[0][1] else {}
r0 = json.loads(row[0][2]) if row[0][2] else {}
w("payload0 keys: " + str(list(p0.keys()) if isinstance(p0, dict) else type(p0).__name__))
if isinstance(p0, dict):
    for k,v in p0.items():
        typ = type(v).__name__
        if isinstance(v, list):
            w("  payload.%s list n=%d" % (k, len(v)))
        elif isinstance(v, str) and len(v)>120:
            w("  payload.%s str=%s" % (k, v[:120]))
        else:
            w("  payload.%s %s=%s" % (k, typ, v))
w("result0 type: " + type(r0).__name__)
if isinstance(r0, dict):
    w("result0 keys: " + str(list(r0.keys())))
    for k,v in r0.items():
        if isinstance(v, list):
            w("  result.%s list n=%d" % (k, len(v)))
            if v and isinstance(v[0], dict):
                w("    item keys: " + str(list(v[0].keys())))
        elif isinstance(v, dict):
            w("  result.%s dict keys=%s" % (k, list(v.keys())[:20]))
        elif isinstance(v, str) and len(v)>120:
            w("  result.%s str=%s" % (k, v[:120]))
        else:
            w("  result.%s %s=%s" % (k, type(v).__name__, v))
elif isinstance(r0, list):
    w("result0 list n=%d" % len(r0))
    if r0 and isinstance(r0[0], dict):
        w("  item keys: " + str(list(r0[0].keys())))

# summarize candidate lookup coverage
# find how to get candidate by run_id+candidate_id
cand_key_sets = Counter()
found_lists = Counter()
n_with = 0
n_cands = 0
for rid, payload, result in row:
    try:
        r = json.loads(result) if result else {}
    except Exception:
        r = {}
    lists = []
    if isinstance(r, list):
        lists.append(("root", r))
        found_lists["root"] += 1
    elif isinstance(r, dict):
        for k,v in r.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                lists.append((k,v))
                found_lists[k] += 1
    if lists:
        n_with += 1
        for k,v in lists:
            n_cands += len(v)
            if v and isinstance(v[0], dict):
                cand_key_sets[tuple(sorted(v[0].keys()))] += 1
w("runs with some list in result: %d" % n_with)
w("found list fields: %s" % dict(found_lists))
w("total listed items: %d" % n_cands)
w("candidate key-sets:")
for ks, c in cand_key_sets.most_common(8):
    w("  n=%d keys=%s" % (c, list(ks)))

# feedback vs runs join preview
fb = list(cur.execute("SELECT id, run_id, candidate_id, reviewer, verdict FROM feedback"))
run_ids = {r[0] for r in row}
missing_run = sum(1 for x in fb if x[1] not in run_ids)
w("feedback missing run: %d / %d" % (missing_run, len(fb)))

conn.close()
OUT.write_text("\n".join(lines), encoding="utf-8")
w("WROTE " + str(OUT))
