from pathlib import Path
import json, sys
sys.path.insert(0, r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\C10\20261117_01\脚本")
from c10_common import *

facts = {r["事实编号"]: r for r in load_jsonl(LIB/"事实层.jsonl")}
for fid in ["F0400","F0297","F0407"]:
    r=facts[fid]
    print("="*60, fid)
    print("来源", r.get("来源文件"), r.get("来源条目标识"))
    print("path", r.get("主库相对路径"), "起止", r.get("起秒"), r.get("止秒"))
    print("标注库ID", r.get("标注库ID"))
    print("内容 keys", list(r.get("内容").keys()) if isinstance(r.get("内容"), dict) else type(r.get("内容")))
    print(json.dumps(r.get("内容"), ensure_ascii=False)[:1500])

# look up raw human and segs
ann = RAW/"标注库"
# F0297
oid="830be1fc59c6e92e"
for p in [ann/"小区全库"/"数据"/"AI剪辑检索索引.jsonl", ann/"测试阿明搅拌"/"数据"/"AI剪辑检索索引.jsonl"]:
    for o in iter_jsonl(p):
        if o.get("id")==oid:
            print("\nFOUND human parent in", p)
            print("source_path", o.get("source_path"))
            print("人工确认片段", json.dumps(o.get("人工确认片段"), ensure_ascii=False)[:2000])
            break

for oid in ["0e2a0645ab8bf3c1","4908c015db00fc77"]:
    for p in [ann/"小区全库"/"数据"/"AI剪辑检索索引.jsonl", ann/"测试阿明搅拌"/"数据"/"AI剪辑检索索引.jsonl"]:
        for o in iter_jsonl(p):
            if o.get("id")==oid:
                print("\nFOUND seg parent", oid, "in", p.name)
                print("source_path", o.get("source_path"))
                print("segs", json.dumps(o.get("indexed_segments"), ensure_ascii=False)[:1500])
                break
