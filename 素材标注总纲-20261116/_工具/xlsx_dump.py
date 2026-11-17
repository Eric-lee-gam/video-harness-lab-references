# -*- coding: utf-8 -*-
"""只读解析 xlsx（标准库），输出每张表的行列数和前若干行。用法: xlsx_dump.py 文件 [每表行数] [只看的表名]"""
import re, sys, zipfile
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
      "p": "http://schemas.openxmlformats.org/package/2006/relationships"}
path = sys.argv[1]
nrows = int(sys.argv[2]) if len(sys.argv) > 2 else 6
only = sys.argv[3] if len(sys.argv) > 3 else None
z = zipfile.ZipFile(path)
shared = []
if "xl/sharedStrings.xml" in z.namelist():
    for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
        shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
wb = ET.fromstring(z.read("xl/workbook.xml"))
rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).findall("p:Relationship", NS)}


def col_idx(ref):
    s = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n - 1


for sh in wb.find("m:sheets", NS).findall("m:sheet", NS):
    name = sh.get("name")
    if only and name != only:
        continue
    target = rels[sh.get("{%s}id" % NS["r"])]
    target = target.lstrip("/") if target.startswith("/") else "xl/" + target
    root = ET.fromstring(z.read(target))
    rows = []
    for row in root.iter("{%s}row" % NS["m"]):
        cells = {}
        for c in row.findall("m:c", NS):
            t, v = c.get("t"), c.find("m:v", NS)
            if t == "s" and v is not None:
                val = shared[int(v.text)]
            elif t == "inlineStr":
                val = "".join(x.text or "" for x in c.iter("{%s}t" % NS["m"]))
            else:
                val = v.text if v is not None else ""
            if val != "":
                cells[col_idx(c.get("r"))] = val
        if cells:
            rows.append(cells)
    width = max((max(r) for r in rows), default=-1) + 1
    print(f"\n===== 工作表「{name}」 有内容的行 {len(rows)}，列 {width}")
    for i, r in enumerate(rows[:nrows] if nrows > 0 else rows):
        line = " | ".join(str(r.get(j, "")).replace("\n", "⏎")[:120] for j in range(width))
        print(f"[{i + 1}] {line}")
