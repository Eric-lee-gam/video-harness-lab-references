# -*- coding: utf-8 -*-
import json
from pathlib import Path
from collections import Counter, defaultdict

OUTDIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_01")
ANN = Path(r"D:\CutFrame项目完整整理_20261116\local\action-annotation")
LABEL = OUTDIR / "标注库副本"
dest = OUTDIR / r"_reads\02f_jsonl_batches.txt"
lines=[]

def w(s=""):
    lines.append(s)

# remaining batch products/persons already partly printed; write complete compact
w("=== ALL BATCHES ===")
for name in (["batch-01.json","batch-02.json","batch-03.json","batch-04.json"]
             + [f"product-0{i}.json" for i in range(1,9)]
             + ["person-01.json","person-02.json","person-03.json","person-04.json","person-05.json","person-07.json",
                "P24-boundary-proposal.json"]):
    data = json.loads((ANN/name).read_text(encoding="utf-8"))
    rows = data.get("rows") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        w("%s NO rows keys=%s" % (name, list(data.keys()) if isinstance(data, dict) else type(data)))
        continue
    st = Counter(str(r.get("status")) for r in rows)
    lab = Counter(str(r.get("confirmed_label") or r.get("label") or "") for r in rows)
    ids = [r.get("sample_id") or r.get("id") for r in rows]
    w("%s n=%d status=%s labels=%s ids=%s" % (name, len(rows), dict(st), dict(lab), ids))

# JSONL compact, write first-record types only to keep short
def one_jsonl(path, tag):
    path=Path(path)
    n=0
    keys=Counter()
    list_info=defaultdict(lambda: {"n":0,"sum":0,"item_keys":Counter()})
    first=None
    path_field_examples={}
    lib_or_dir=Counter()
    with path.open(encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line:
                continue
            o=json.loads(line)
            n+=1
            if not isinstance(o, dict):
                continue
            keys.update(o.keys())
            if first is None:
                first=o
            for k,v in o.items():
                if isinstance(v, list):
                    list_info[k]["n"] += 1
                    list_info[k]["sum"] += len(v)
                    if v and isinstance(v[0], dict):
                        list_info[k]["item_keys"].update(v[0].keys())
            if n<=3:
                for fk,v in o.items():
                    if isinstance(v,str) and ("\\" in v or "/" in v) and fk not in path_field_examples:
                        path_field_examples[fk]=v
    w("")
    w("=== %s n=%d ===" % (tag, n))
    w("keys=" + json.dumps(dict(keys), ensure_ascii=False))
    for k,info in list_info.items():
        avg = info["sum"]/info["n"] if info["n"] else 0
        w("list %s filled=%d sum=%d avg=%.2f item_keys=%s" % (k, info["n"], info["sum"], avg, list(info["item_keys"].keys())))
    w("path_examples=" + json.dumps(path_field_examples, ensure_ascii=False))
    # first record short
    if first:
        short={}
        for k,v in first.items():
            if isinstance(v, list):
                short[k]="LIST n=%d" % len(v)
            elif isinstance(v, dict):
                short[k]="DICT " + json.dumps(v, ensure_ascii=False, default=str)[:200]
            elif isinstance(v, str) and len(v)>120:
                short[k]=v[:120]+"..."
            else:
                short[k]=v
        w("first=" + json.dumps(short, ensure_ascii=False, default=str))
        # if has segments, print first segment
        for k,v in first.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                w("first.%s[0]=" % k + json.dumps(v[0], ensure_ascii=False, default=str)[:600])
    return n

one_jsonl(LABEL/r"小区全库\数据\AI剪辑检索索引.jsonl", "小区索引")
one_jsonl(LABEL/r"测试阿明搅拌\数据\AI剪辑检索索引.jsonl", "测试阿明搅拌索引")
one_jsonl(LABEL/r"微陶泥施工\施工镜头.jsonl", "施工镜头")
one_jsonl(LABEL/r"小区全库\数据\按用途检索.jsonl", "按用途检索")
one_jsonl(LABEL/r"小区全库\数据\本轮看片精标.jsonl", "本轮看片精标")
one_jsonl(LABEL/r"小区全库\数据\机器片段复核.jsonl", "机器片段复核")
one_jsonl(LABEL/r"小区全库\数据\目视纠正.jsonl", "目视纠正")

dest.write_text("\n".join(lines), encoding="utf-8")
print("WROTE", dest, "lines", len(lines), "bytes", dest.stat().st_size)
