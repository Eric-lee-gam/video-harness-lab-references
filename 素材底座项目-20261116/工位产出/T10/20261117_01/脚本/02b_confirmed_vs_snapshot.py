# -*- coding: utf-8 -*-
import json, sqlite3
from pathlib import Path

OUTDIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
LEARN = OUTDIR / r"镜序副本\learning.sqlite3"
EV = OUTDIR / r"镜序副本\identity-evidence.json"
out = OUTDIR / r"_reads\02b_confirmed_vs_snapshot.txt"
lines = []

def w(s=""):
    lines.append(s)
    print(s)

conn = sqlite3.connect("file:" + LEARN.as_posix() + "?mode=ro&immutable=1", uri=True)
cur = conn.cursor()

w("=== approved rules full ===")
approved = []
all_rules = []
for rid, created, status, reviewer, payload, fid in cur.execute(
    "SELECT id, created, status, reviewer, payload, feedback_id FROM rules ORDER BY created"
):
    p = json.loads(payload) if payload else {}
    rec = {"id": rid, "created": created, "status": status, "reviewer": reviewer, "feedback_id": fid, "payload": p}
    all_rules.append(rec)
    if status == "approved":
        approved.append(rec)

w("approved count=%d" % len(approved))
for r in approved:
    p = r["payload"]
    # print compact one line but include all scalar fields
    scalars = {k: v for k, v in p.items() if not isinstance(v, (dict, list))}
    w("APPROVED id=%s reviewer=%s created=%s" % (r["id"], r["reviewer"], r["created"]))
    w("  scalars=" + json.dumps(scalars, ensure_ascii=False, default=str))
    for k, v in p.items():
        if isinstance(v, (dict, list)):
            s = json.dumps(v, ensure_ascii=False, default=str)
            if len(s) > 400:
                s = s[:400] + "..."
            w("  %s=%s" % (k, s))

w("")
w("=== rule ids starting confirmed- ===")
for r in all_rules:
    if r["id"].startswith("confirmed-") or str(r["payload"].get("id", "")).startswith("confirmed-"):
        w("MATCH id=%s status=%s reviewer=%s payload_id=%s" % (
            r["id"], r["status"], r["reviewer"], r["payload"].get("id")))

# also search any string field
w("")
w("=== any confirmed- substring ===")
for r in all_rules:
    raw = r["id"] + " " + json.dumps(r["payload"], ensure_ascii=False)
    if "confirmed-" in raw:
        w("HIT id=%s status=%s keys=%s" % (r["id"], r["status"], list(r["payload"].keys())))

# identity evidence
w("")
w("=== identity-evidence.json type/keys ===")
ev = json.loads(EV.read_text(encoding="utf-8"))
w("type=" + type(ev).__name__)
if isinstance(ev, dict):
    w("keys=" + str(list(ev.keys())))
    ev_list = None
    for k, v in ev.items():
        if isinstance(v, list):
            w("list field %s n=%d" % (k, len(v)))
            ev_list = v
        elif isinstance(v, dict):
            w("dict field %s n=%d subkeys=%s" % (k, len(v), list(v.keys())[:20]))
        else:
            val = str(v)
            w("field %s=%s" % (k, val[:200]))
    items = ev_list if ev_list is not None else []
    if ev_list is None:
        # maybe values of a dict are the items
        items = []
elif isinstance(ev, list):
    items = ev
    w("list n=%d" % len(items))
else:
    items = []

w("evidence items n=%d" % len(items))
if items and isinstance(items[0], dict):
    w("item keys=" + str(list(items[0].keys())))
ids_ev = []
for i, item in enumerate(items):
    if not isinstance(item, dict):
        w("item[%d] type=%s val=%s" % (i, type(item).__name__, str(item)[:200]))
        continue
    eid = item.get("id") or item.get("rule_id") or item.get("evidence_id") or item.get("sample_id")
    src = item.get("source") if isinstance(item.get("source"), dict) else {}
    w("EV[%d] id=%s asset=%s start=%s end=%s keys=%s" % (
        i, eid, item.get("asset_id") or src.get("id") or src.get("asset_id"),
        item.get("start") if "start" in item else src.get("start"),
        item.get("end") if "end" in item else src.get("end"),
        list(item.keys())
    ))
    # extra brief
    scalars = {k: v for k, v in item.items() if not isinstance(v, (dict, list))}
    w("  scalars=" + json.dumps(scalars, ensure_ascii=False, default=str)[:500])
    ids_ev.append(str(eid) if eid is not None else "")

# compare with approved current-user rules
w("")
w("=== compare approved-by-当前用户 vs evidence ===")
cu = [r for r in approved if r["reviewer"] == "当前用户"]
w("approved 当前用户=%d evidence=%d approved total=%d" % (len(cu), len(items), len(approved)))

def asset_key(p):
    src = p.get("source") if isinstance(p.get("source"), dict) else {}
    return (
        str(p.get("asset_id") or src.get("id") or src.get("asset_id") or ""),
        p.get("start") if "start" in p else src.get("start"),
        p.get("end") if "end" in p else src.get("end"),
    )

ev_keys = [asset_key(it) if isinstance(it, dict) else None for it in items]
cu_keys = [asset_key(r["payload"]) for r in cu]
w("unique ev asset-span=%d unique cu asset-span=%d" % (len(set(ev_keys)), len(set(cu_keys))))

# ids
cu_ids = [r["id"] for r in cu]
w("cu ids:")
for x in cu_ids:
    w("  " + x)
w("ev ids:")
for x in ids_ev:
    w("  " + x)

only_cu = [r for r in cu if asset_key(r["payload"]) not in set(ev_keys)]
only_ev = []
for it, k in zip(items, ev_keys):
    if k not in set(cu_keys):
        only_ev.append((k, it))
w("in approved-当前用户 but not evidence: %d" % len(only_cu))
for r in only_cu:
    w("  ONLY_CU id=%s key=%s scalars=%s" % (
        r["id"], asset_key(r["payload"]),
        json.dumps({k:v for k,v in r["payload"].items() if not isinstance(v,(dict,list))}, ensure_ascii=False, default=str)[:400]
    ))
w("in evidence but not approved-当前用户: %d" % len(only_ev))
for k, it in only_ev:
    w("  ONLY_EV key=%s" % (k,))

# maybe evidence maps to payload.id
w("")
w("payload.id / kind / type distribution for approved 当前用户")
for r in cu:
    p = r["payload"]
    w("  rule=%s payload.id=%s kind=%s type=%s label=%s text=%s" % (
        r["id"], p.get("id"), p.get("kind"), p.get("type"), p.get("label"),
        str(p.get("text") or p.get("description") or "")[:60]
    ))

conn.close()
out.write_text("\n".join(lines), encoding="utf-8")
w("WROTE " + str(out) + " nlines=" + str(len(lines)))
