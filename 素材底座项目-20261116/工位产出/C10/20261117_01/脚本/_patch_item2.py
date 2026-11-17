from pathlib import Path
p = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\脚本\c10_item2_sample_facts.py")
t = p.read_text(encoding="utf-8")

old_lookup = '''def lookup_human(key_str):
    # unknown format — try several
    # maybe id or id:start-end or id:n
    if key_str in xq_id or key_str in ts_id:
        # file-level? probably not
        pass
    rec = lookup_index_seg(key_str)
    if rec:
        return ("seg?", rec)
    # id:index
    if ":" in key_str:
        oid, rest = key_str.split(":", 1)
        if rest.isdigit():
            i = int(rest)
            return ("hum", xq_hum.get((oid, i)) or ts_hum.get((oid, i)))
        # start-end
        if "-" in rest and rest.count(":")==0:
            i = rest.find("-")
            st_s, en_s = rest[:i], rest[i+1:]
            try:
                st, en = float(st_s), float(en_s)
            except ValueError:
                st, en = st_s, en_s
            return ("hum", xq_hum.get((oid, st, en)) or ts_hum.get((oid, st, en)))
    return None
'''

new_lookup = '''def lookup_human(key_str):
    # formats: id:人工确认:start-end:index   or id:start-end or id:index
    if ":人工确认:" in key_str:
        oid, rest = key_str.split(":人工确认:", 1)
        parts = rest.split(":")
        idx = int(parts[-1]) if parts and parts[-1].isdigit() else None
        mid = ":".join(parts[:-1]) if idx is not None else rest
        if "-" in mid:
            i = mid.find("-") if not mid.startswith("-") else mid.find("-", 1)
            st_s, en_s = mid[:i], mid[i+1:]
            try:
                st, en = float(st_s), float(en_s)
            except ValueError:
                st, en = st_s, en_s
            rec = xq_hum.get((oid, st, en)) or ts_hum.get((oid, st, en))
            if rec:
                return ("hum", rec)
            if idx is not None:
                rec = xq_hum.get((oid, idx)) or ts_hum.get((oid, idx))
                if rec:
                    return ("hum", rec)
    rec = lookup_index_seg(key_str)
    if rec:
        return ("seg?", rec)
    if ":" in key_str:
        oid, rest = key_str.split(":", 1)
        if rest.isdigit():
            i = int(rest)
            return ("hum", xq_hum.get((oid, i)) or ts_hum.get((oid, i)))
        if "-" in rest and rest.count(":")==0:
            i = rest.find("-")
            st_s, en_s = rest[:i], rest[i+1:]
            try:
                st, en = float(st_s), float(en_s)
            except ValueError:
                st, en = st_s, en_s
            return ("hum", xq_hum.get((oid, st, en)) or ts_hum.get((oid, st, en)))
    return None
'''

if old_lookup not in t:
    raise SystemExit("lookup_human block not found")
t = t.replace(old_lookup, new_lookup, 1)

# skip path-like keys in generic field loops
old_loop = '''        for k, val in seg.items():
            if k in ("preview", "preview_path"):
                continue
'''
new_loop = '''        PATH_KEYS = {"source_path", "path", "preview", "preview_path", "rel"}
        for k, val in seg.items():
            if k in PATH_KEYS:
                continue
'''
if old_loop not in t:
    raise SystemExit("seg loop not found")
t = t.replace(old_loop, new_loop, 1)

old_hum = '''            for k, val in hum.items():
                if val in (None, "", [], {}):
                    continue
'''
new_hum = '''            PATH_KEYS = {"source_path", "path", "preview", "preview_path", "rel"}
            for k, val in hum.items():
                if k in PATH_KEYS:
                    continue
                if val in (None, "", [], {}):
                    continue
'''
if old_hum not in t:
    raise SystemExit("hum loop not found")
t = t.replace(old_hum, new_hum, 1)

p.write_text(t, encoding="utf-8")
print("patched ok")
