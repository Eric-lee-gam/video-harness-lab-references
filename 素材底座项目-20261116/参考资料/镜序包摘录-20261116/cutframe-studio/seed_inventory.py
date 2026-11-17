"""从已授权预检报告导入索引，不扫描或修改源文件。"""
import json
import hashlib
from pathlib import Path
from app import connect, CONFIG, STATE

folder = STATE.parent / 'cutframe-precheck'
with connect() as db:
    for alias, filename in [('xiaoq','小区-inventory.json'),('baba','扒扒-inventory.json'),('chengdu','chengdu-inventory.json'),('suzhou','suzhou-inventory.json')]:
        source = folder / filename
        if not source.exists():
            continue
        data = json.loads(source.read_text('utf-8-sig'))
        root = CONFIG['roots'][alias]['path'].rstrip('\\') + '\\'
        records = []
        for f in data:
            if f['Extension'].lower() not in ('.mp4','.mov'):
                continue
            rel = f['FullName'][len(root):].replace('\\','/')
            aid = hashlib.sha256((alias+'/'+rel).encode()).hexdigest()[:32]
            records.append((aid,alias,rel,Path(rel).name,f['Length'],''))
        db.executemany('INSERT OR IGNORE INTO assets(id,root,rel,name,size,stamp) VALUES(?,?,?,?,?,?)',records)
        print(alias,len(records))
