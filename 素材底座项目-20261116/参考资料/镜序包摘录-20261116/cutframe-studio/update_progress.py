"""更新一项状态并保留历史。只能据实记录，用户验收必须有明确反馈。"""
import argparse
import json
from pathlib import Path
from datetime import datetime

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('id'); p.add_argument('status',choices=['已完成','进行中','待验收','等待输入','待开始'])
p.add_argument('--evidence',required=True); p.add_argument('--next',required=True)
a=p.parse_args()
path=Path(__file__).resolve().parent.parent/'outputs'/'CutFrame流程图'/'plan.json'
data=json.loads(path.read_text(encoding='utf-8'))
task=next(t for t in data['tasks'] if t['id']==a.id)
now=datetime.now().astimezone().isoformat(timespec='seconds')
data['history'].append(dict(time=now,task=a.id,change=f"{task['status']} → {a.status}",before=dict(task),evidence=a.evidence,next=a.next))
task.update(status=a.status,evidence=a.evidence,next=a.next,updated=now)
data['version']+=1; data['updated']=now
temp=path.with_suffix('.tmp'); temp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(path)
print(f'{a.id} 已更新，版本 {data["version"]}')
import runpy
runpy.run_path(str(path.parent/'render_flow.py'),run_name='__main__')
