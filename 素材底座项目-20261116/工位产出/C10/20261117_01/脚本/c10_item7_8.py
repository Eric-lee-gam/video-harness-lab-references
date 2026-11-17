# -*- coding: utf-8 -*-
"""C10 items 7 and 8: forbidden sources, secrets, read-only writes, gpt-pilot."""
from __future__ import annotations

import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from c10_common import *

aa_src = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
t10_scripts = T10 / "脚本"
proj = PROJ

# ---------- official vs before/discovery sample ids ----------
def is_before_or_discovery(name: str) -> bool:
    n = name.lower()
    return ".before-" in n or "discovery" in n

official_ids = set()
official_hashes = set()
before_ids = set()
before_hashes = set()
before_only_rows = []

for p in sorted(aa_src.glob("*.json")):
    try:
        obj = load_json(p)
    except Exception as e:
        continue
    rows = obj.get("rows") if isinstance(obj, dict) else (obj if isinstance(obj, list) else [])
    if not isinstance(rows, list):
        continue
    target_ids = before_ids if is_before_or_discovery(p.name) else official_ids
    target_hash = before_hashes if is_before_or_discovery(p.name) else official_hashes
    for r in rows:
        if not isinstance(r, dict):
            continue
        sid = r.get("sample_id")
        h = r.get("clip_sha256") or r.get("source_record_hash")
        if sid:
            target_ids.add(str(sid))
            if is_before_or_discovery(p.name):
                before_only_rows.append({"file": p.name, "sample_id": sid, "status": r.get("status"), "sha": h})
        if h:
            target_hash.add(h)

only_before_ids = before_ids - official_ids
only_before_hashes = before_hashes - official_hashes

# scan outputs' 来源文件 and 来源条目标识 / 样例编号
outputs = [
    LIB / "事实层.jsonl",
    LIB / "评价与采用.jsonl",
    LIB / "禁用表.jsonl",
    LIB / "线索.jsonl",
    LIB / "粗标层.jsonl",
]
bad_source_files = []
leaked_ids = []
leaked_hashes = []
source_file_values = set()

# For coarse, only check 来源文件 and 来源条目标识 to save time; also sha if present
for path in outputs:
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if not line.strip():
                continue
            # cheap filename check
            if ".before-" in line.lower() or "discovery" in line.lower():
                o = json.loads(line)
                src = str(o.get("来源文件") or "")
                source_file_values.add(src)
                if is_before_or_discovery(src) or is_before_or_discovery(Path(src).name):
                    bad_source_files.append({"file": path.name, "line": i, "来源文件": src, "id": o.get("来源条目标识") or o.get("事实编号") or o.get("粗标编号")})
                sid = str(o.get("来源条目标识") or "")
                smp = str(o.get("样例编号") or "")
                blob = json.dumps(o, ensure_ascii=False)
                for bid in only_before_ids:
                    if bid and (sid==bid or smp==bid):
                        leaked_ids.append({"file": path.name, "id": o.get("事实编号") or o.get("粗标编号"), "sample": bid, "来源文件": src})
            # still collect 来源文件 always? expensive to json every line for 65k
            # parse 来源文件 with regex
            m = re.search(r'"来源文件": "([^"]+)"', line)
            if m:
                source_file_values.add(m.group(1))
                if is_before_or_discovery(m.group(1)):
                    o = json.loads(line)
                    bad_source_files.append({"file": path.name, "line": i, "来源文件": m.group(1), "id": o.get("来源条目标识")})

# Also check leftover only_before_ids against fact 样例编号 / 来源条目标识 without relying on line keyword
# Load small files fully; for coarse only if needed
small = []
for name in ["事实层.jsonl", "评价与采用.jsonl", "禁用表.jsonl", "线索.jsonl"]:
    small.extend(load_jsonl(LIB / name))
for o in small:
    sid = str(o.get("来源条目标识") or "")
    smp = str(o.get("样例编号") or "")
    src = str(o.get("来源文件") or "")
    source_file_values.add(src)
    for bid in only_before_ids:
        if bid and bid in (sid, smp) and bid not in official_ids:
            leaked_ids.append({"file": "small", "sample": bid, "来源文件": src, "id": o.get("事实编号")})
    # hashes in content
    blob = json.dumps(o, ensure_ascii=False)
    for h in only_before_hashes:
        if h and h in blob:
            leaked_hashes.append({"id": o.get("事实编号"), "hash": h, "来源文件": src})

# ---------- secret words in 片段库 + T10 回报/统计/配置 (not source copies, not before json) ----------
SECRET_RE = re.compile(r"(?i)(?<![\w])(key|token|secret|api_key|access_token|private_key)(?![\w])")
secret_hits = []

def scan_text(label, text, limit=20):
    hits = []
    for i, line in enumerate(text.splitlines(), 1):
        for m in SECRET_RE.finditer(line):
            hits.append({"where": label, "line": i, "word": m.group(1), "context": line.strip()[:300]})
            if len(hits) >= limit:
                return hits
    return hits

# 片段库 jsonl: stream
for path in outputs:
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            for m in SECRET_RE.finditer(line):
                # classify likely field-name false positives
                secret_hits.append({
                    "where": f"片段库/{path.name}",
                    "line": i,
                    "word": m.group(1),
                    "context": line[max(0, m.start()-80):m.end()+80].replace("\n", " ")[:300],
                })
                if len(secret_hits) > 200:
                    break
        if len(secret_hits) > 200:
            break

# config
for p in (LIB / "配置").glob("*.json"):
    secret_hits.extend(scan_text(f"片段库/配置/{p.name}", p.read_text(encoding="utf-8")))

# T10 回报 and 统计 and 配置 (not 标注库副本 / 镜序副本 / scripts maybe yes for gpt-pilot separately)
for p in [T10 / "回报.md"]:
    if p.exists():
        secret_hits.extend(scan_text(f"T10/{p.name}", p.read_text(encoding="utf-8")))
for p in (T10 / "统计").glob("*"):
    if p.is_file() and p.suffix.lower() in {".md", ".json", ".jsonl", ".txt"}:
        # skip huge overlap file? 900k is ok
        try:
            secret_hits.extend(scan_text(f"T10/统计/{p.name}", p.read_text(encoding="utf-8"), limit=30))
        except Exception as e:
            secret_hits.append({"where": f"T10/统计/{p.name}", "error": repr(e)})
cfg = T10 / "配置" / "路径与库名.json"
if cfg.exists():
    secret_hits.extend(scan_text("T10/配置/路径与库名.json", cfg.read_text(encoding="utf-8")))

# classify secret hits: real vs likely identifier
real_secretish = []
benign = []
for h in secret_hits:
    ctx = (h.get("context") or "").lower()
    word = (h.get("word") or "").lower()
    # common benign: JSON key names like "key":, source_record? no; "keyboard" already excluded by word boundary
    # "key" as a json key or dict key in python
    if re.search(r'["\']%s["\']\s*:' % re.escape(word), ctx) or re.search(r"\b%s\s*=" % re.escape(word), ctx):
        benign.append(h)
    elif "source_record" in ctx or "clip_sha" in ctx:
        benign.append(h)
    else:
        # still may be path 'key' as folder? keep for review
        real_secretish.append(h)

# ---------- gpt-pilot in T10 scripts and report ----------
gpt_hits = []
search_roots = [t10_scripts, T10]
for root in [t10_scripts]:
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in {".py", ".md", ".txt", ".json", ".jsonl", ".ps1", ".bat"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if "gpt-pilot" in text.lower():
            for i, line in enumerate(text.splitlines(), 1):
                if "gpt-pilot" in line.lower():
                    gpt_hits.append({"file": str(p.relative_to(T10)), "line": i, "text": line.strip()[:400]})

# also 回报
rep = (T10 / "回报.md").read_text(encoding="utf-8")
# mention of not opening is OK; reading it is not
# we'll list all mentions

# ---------- item 8: AST writes ----------
WRITE_FUNCS = {
    "write_text", "write_bytes", "touch", "unlink", "rename", "replace", "mkdir",
    "rmdir", "open", "remove", "rmtree", "move", "copy", "copy2", "copyfile", "copytree",
    "makedirs", "mkdirs", "dump", "dumps_to",
}

def const_str(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append("{}")
        return "".join(parts)
    return None

def join_path_expr(node):
    """Best-effort reconstruct Path / string concatenations."""
    s = const_str(node)
    if s is not None:
        return s
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = join_path_expr(node.left), join_path_expr(node.right)
        if a is not None and b is not None:
            return a + b
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):  # Path / x in 3.11? actually operator is not Div for Path
        pass
    if isinstance(node, ast.Call):
        # Path("x") or Path(x)
        if isinstance(node.func, ast.Name) and node.func.id == "Path" and node.args:
            return join_path_expr(node.args[0])
        if isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath" and node.args:
            base = join_path_expr(node.func.value)
            rest = [join_path_expr(a) for a in node.args]
            if base is not None and all(x is not None for x in rest):
                return str(Path(base, *rest))
    if isinstance(node, ast.Attribute):
        # something.parent / name
        return None
    # Path / "foo"
    if isinstance(node, ast.BinOp) and node.__class__.__name__ and isinstance(node.op, ast.Div):
        a, b = join_path_expr(node.left), join_path_expr(node.right)
        if a is not None and b is not None:
            return str(Path(a) / b)
    return None

# Python 3.14 uses ast.Div for / 
# Also BitOr? no

writes = []
for p in sorted(t10_scripts.glob("*.py")):
    text = p.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        writes.append({"file": p.name, "error": f"syntax {e}"})
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            name = None
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if not name:
                continue
            # open(..., mode)
            if name == "open":
                mode = "r"
                if len(node.args) >= 2:
                    m = const_str(node.args[1])
                    if m:
                        mode = m
                for kw in node.keywords:
                    if kw.arg == "mode":
                        m = const_str(kw.value)
                        if m:
                            mode = m
                if any(ch in mode for ch in "wax+"):
                    target = join_path_expr(node.args[0]) if node.args else None
                    writes.append({"file": p.name, "line": node.lineno, "op": f"open({mode})", "target": target, "raw": ast.unparse(node)[:240]})
            elif name in {"write_text", "write_bytes", "touch", "mkdir", "makedirs"}:
                # Path.write_text: func.value is the path
                if isinstance(func, ast.Attribute):
                    target = join_path_expr(func.value)
                else:
                    target = join_path_expr(node.args[0]) if node.args else None
                writes.append({"file": p.name, "line": node.lineno, "op": name, "target": target, "raw": ast.unparse(node)[:240]})
            elif name in {"unlink", "remove", "rmdir", "rmtree", "replace", "rename", "move", "copy", "copy2", "copyfile", "copytree"}:
                # shutil.copy(src, dst) — dst is second arg
                if name in {"copy", "copy2", "copyfile", "copytree", "move", "rename", "replace"} and len(node.args) >= 2:
                    src = join_path_expr(node.args[0])
                    dst = join_path_expr(node.args[1])
                    writes.append({"file": p.name, "line": node.lineno, "op": name, "target": dst, "src": src, "raw": ast.unparse(node)[:240]})
                elif isinstance(func, ast.Attribute):
                    target = join_path_expr(func.value) or (join_path_expr(node.args[0]) if node.args else None)
                    writes.append({"file": p.name, "line": node.lineno, "op": name, "target": target, "raw": ast.unparse(node)[:240]})
            elif name in {"dump"} and node.args:
                # json.dump(obj, f) — file handle, skip unless Path
                pass

# classify write targets
PROJECT_PREFIXES = [
    str(proj).lower(),
    r"d:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116".lower(),
]
SHARE_MARKERS = [r"\\192.168.110.36\共享本公司", r"\\192.168.110.36\obsidian", "史上最完整共享"]
JX_MARKERS = [r"d:\cutframe项目完整整理_20261116"]

bad_writes = []
ok_writes = []
unknown_writes = []
for w in writes:
    t = (w.get("target") or "") 
    tl = t.lower() if t else ""
    raw = (w.get("raw") or "").lower()
    src = (w.get("src") or "")
    dest_is_project = any(tl.startswith(pfx) or pfx in tl for pfx in PROJECT_PREFIXES) if tl else False
    # variables like OUT / LIB / DEST commonly in project
    dest_is_share = any(m.lower() in tl or m.lower() in raw for m in ["\\\\192.168.110.36\\共享", "\\\\192.168.110.36\\obsidian"]) and not dest_is_project
    dest_is_jx = any(m in tl or m in raw for m in ["cutframe项目完整整理_20261116"]) and "工位产出" not in tl and "素材底座项目-20261116" not in tl
    # copy FROM share TO project is OK; we care about destination
    entry = {**w, "dest_is_project": dest_is_project, "dest_is_share": dest_is_share, "dest_is_jx": dest_is_jx}
    if dest_is_share or dest_is_jx:
        bad_writes.append(entry)
    elif dest_is_project or (not t and ("out" in raw or "lib" in raw or "dest" in raw or "产出" in raw or "片段库" in raw)):
        ok_writes.append(entry)
    elif not t:
        unknown_writes.append(entry)
    else:
        # absolute path elsewhere?
        if re.match(r"^[a-zA-Z]:\\", t) or t.startswith("\\\\"):
            if str(proj).lower() in tl:
                ok_writes.append(entry)
            else:
                # could still be project via variable; mark unknown if looks like relative under OUT
                unknown_writes.append(entry)
        else:
            unknown_writes.append(entry)

# heuristic: inspect unknown raw for obviously project-only vars
still_unknown = []
for w in unknown_writes:
    raw = w.get("raw") or ""
    if any(s in raw for s in ["OUT", "LIB", "DEST", "产出", "片段库", "PROJ", "RAW.copy" , "here", "out_dir", "batch", "T10", "mid", "STAT", "CFG"]):
        w["note"] = "表达式看起来落在产出/片段库"
        ok_writes.append(w)
    else:
        still_unknown.append(w)

item7_pass = (not bad_source_files and not leaked_ids and not leaked_hashes and not gpt_hits
              and not any("gpt-pilot" in (h.get("text") or "").lower() and "没有打开" not in (h.get("text") or "") and "未打开" not in (h.get("text") or "") and "不" not in (h.get("text") or "") for h in gpt_hits))
# gpt_hits in scripts would fail even if report says 没有打开 — need to check if scripts actually open it
gpt_read = [h for h in gpt_hits if any(k in (h.get("text") or "").lower() for k in ["open(", "read_text", "rglob", "path(", "listdir", "iterdir", "walk("])]
# mentions only
gpt_mentions = gpt_hits

# For item 7 pass standard: 都没有 — no before/discovery content, no gpt-pilot read, no key/token/secret in output
# I'll treat field-name-only hits as not failing if no secret values
has_real_secrets = False
for h in real_secretish:
    ctx = h.get("context") or ""
    # value-looking: key = "xxxx" long token
    if re.search(r'(key|token|secret)["\']?\s*[:=]\s*["\'][^"\']{8,}', ctx, re.I):
        has_real_secrets = True

item7 = {
    "item": 7,
    "official_sample_ids": len(official_ids),
    "before_discovery_sample_ids": len(before_ids),
    "only_in_before_discovery_ids_n": len(only_before_ids),
    "only_in_before_discovery_ids_sample": sorted(only_before_ids)[:40],
    "bad_source_files": bad_source_files,
    "leaked_ids": leaked_ids,
    "leaked_hashes": leaked_hashes[:20],
    "source_files_seen": sorted(source_file_values),
    "gpt_pilot_mentions": gpt_mentions,
    "gpt_pilot_read_evidence": gpt_read,
    "secret_hits_total": len(secret_hits),
    "secret_hits_benign_n": len(benign),
    "secret_hits_review_n": len(real_secretish),
    "secret_hits_review": real_secretish[:40],
    "has_real_secret_values": has_real_secrets,
}
item7["pass"] = (not bad_source_files and not leaked_ids and not leaked_hashes
                 and not gpt_read and not has_real_secrets)

item8 = {
    "item": 8,
    "writes_n": len(writes),
    "ok_writes_n": len(ok_writes),
    "bad_writes": bad_writes,
    "unknown_writes": still_unknown,
    "ok_writes_sample": ok_writes[:15],
    "pass": not bad_writes and not still_unknown,
    "wrote_share_or_jx": bool(bad_writes),
    "read_gpt_pilot": bool(gpt_read),
}
# if unknown writes remain, don't auto-fail if we can say all resolved later — I'll inspect print

dump_json(MID / "item7_forbidden.json", item7)
dump_json(MID / "item8_readonly.json", item8)
print("ITEM7 pass", item7["pass"], "bad_src", len(bad_source_files), "leaked_ids", len(leaked_ids), "leaked_hash", len(leaked_hashes), "gpt_mentions", len(gpt_mentions), "gpt_read", len(gpt_read), "secrets review", len(real_secretish), "real values", has_real_secrets)
print("source files:")
for s in sorted(source_file_values):
    print(" ", s)
print("only-before ids", sorted(only_before_ids)[:30], "n", len(only_before_ids))
print("gpt hits:")
for h in gpt_mentions:
    print(" ", h)
print("secret review first 15:")
for h in real_secretish[:15]:
    print(" ", h.get("where"), h.get("word"), h.get("context","")[:180])
print("ITEM8 pass", item8["pass"], "bad", len(bad_writes), "unknown", len(still_unknown), "ok", len(ok_writes))
if bad_writes:
    print("BAD WRITES", json.dumps(bad_writes, ensure_ascii=False)[:2000])
if still_unknown:
    print("UNKNOWN WRITES n", len(still_unknown))
    for w in still_unknown[:25]:
        print(" ", w.get("file"), w.get("line"), w.get("op"), "target=", w.get("target"), "raw=", (w.get("raw") or "")[:200])
