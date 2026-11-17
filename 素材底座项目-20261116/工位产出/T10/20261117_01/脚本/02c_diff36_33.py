# -*- coding: utf-8 -*-
import json, sqlite3
from pathlib import Path

OUTDIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
LEARN = OUTDIR / r"镜序副本\learning.sqlite3"
EV = OUTDIR / r"镜序副本\identity-evidence.json"

conn = sqlite3.connect("file:" + LEARN.as_posix() + "?mode=ro&immutable=1", uri=True)
cur = conn.cursor()
facts = []
for rid, created, status, reviewer, payload in cur.execute(
    "SELECT id, created, status, reviewer, payload FROM rules WHERE id LIKE 'confirmed-%' ORDER BY id"
):
    p = json.loads(payload) if payload else {}
    facts.append({"id": rid, "created": created, "status": status, "reviewer": reviewer, "payload": p})
print("confirmed-* rules:", len(facts), "status", {s: sum(1 for x in facts if x["status"]==s) for s in set(x["status"] for x in facts)})
print("DB fact ids:")
for f in facts:
    p = f["payload"]
    print(" ", f["id"], "sample=", p.get("sample_id"), "asset=", p.get("asset_id"), "start=", p.get("start"), "end=", p.get("end"), "person=", p.get("person_identity"), "product=", p.get("product_identity"), "action=", p.get("confirmed_action"), "desc=", (p.get("description") or "")[:60])

ev = json.loads(EV.read_text(encoding="utf-8"))
print("\nevidence type", type(ev).__name__)
items = ev
if isinstance(ev, dict):
    print("evidence keys", list(ev.keys()))
    for k,v in ev.items():
        print(" ", k, type(v).__name__, (len(v) if hasattr(v, "__len__") and not isinstance(v, str) else v if not isinstance(v, (dict,)) else "dict"))
    # find list of 33
    items = None
    for k,v in ev.items():
        if isinstance(v, list) and len(v) in (33, 32, 34, 36, 37):
            items = v
            print("using field", k, "n", len(v))
            break
    if items is None:
        # maybe ev itself is {id: obj}
        maybe = [v for v in ev.values() if isinstance(v, dict) and ("asset_id" in v or "source" in v or "sample_id" in v or "id" in v)]
        if maybe:
            items = maybe
            print("using dict values n", len(items))
        else:
            # print shallow structure
            print("CANNOT find list")
            items = []

print("evidence items", len(items))
ev_ids = []
for i, it in enumerate(items or []):
    if isinstance(it, str):
        print(" ev str", it)
        ev_ids.append(it)
        continue
    eid = it.get("id") or it.get("rule_id") or it.get("evidence_id") or it.get("sample_id")
    ev_ids.append(eid)
    src = it.get("source") if isinstance(it.get("source"), dict) else {}
    print(" EV", eid, "asset=", it.get("asset_id") or src.get("id"), "start=", it.get("start", src.get("start")), "end=", it.get("end", src.get("end")), "keys=", list(it.keys())[:15])

db_ids = [f["id"] for f in facts]
# also sample_id
db_sids = [f["payload"].get("sample_id") for f in facts]
print("\nDB ids:", db_ids)
print("EV ids:", ev_ids)
print("in DB not EV (by rule id):", [x for x in db_ids if x not in ev_ids and x.replace("confirmed-","") not in ev_ids])
print("in EV not DB (by rule id):", [x for x in ev_ids if x not in db_ids and ("confirmed-"+str(x)) not in db_ids])
print("in DB not EV (by sample_id):", [s for s in db_sids if s not in ev_ids and ("confirmed-"+str(s) if s else "") not in ev_ids])

# If evidence items are nested
if items and isinstance(items[0], dict):
    print("\nFirst evidence item full scalars:")
    it = items[0]
    print(json.dumps({k:v for k,v in it.items() if not isinstance(v,(dict,list))}, ensure_ascii=False))
conn.close()
