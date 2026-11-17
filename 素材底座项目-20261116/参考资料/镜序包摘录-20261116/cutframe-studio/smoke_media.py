"""真实素材只读端到端检查。验证视频保存在工作区，不进入交付目录。"""
import json
import hashlib
import time
from pathlib import Path
import app as studio
from media import probe

studio.CONFIG['output']=str(studio.STATE/'smoke-outputs')
client=studio.app.test_client()
headers={'Host':f'127.0.0.1:{studio.PORT}','X-Local-Token':studio.TOKEN}
samples=json.loads((studio.STATE.parent/'cutframe-precheck'/'小区-probe.json').read_text('utf-8-sig'))
samples.sort(key=lambda r:r['Bytes'])
sample=next(r for r in samples if r['Success'] and r['Bytes']<50000000 and any(s.get('codec_name')=='h264' for s in r['Metadata']['streams']))
path=Path(sample['Path'])
rel=path.relative_to(Path(studio.CONFIG['roots']['xiaoq']['path'])).as_posix()
aid=hashlib.sha256(('xiaoq/'+rel).encode()).hexdigest()[:32]
before=hashlib.sha256(path.read_bytes()).hexdigest()
report={'source':str(path),'before_sha256':before,'checks':[]}
def call(url,data=None,extra=None):
    r=client.get(url,headers={**headers,**(extra or {})}) if data is None else client.post(url,json=data,headers=headers)
    if r.status_code>=400: raise RuntimeError(str(r.json))
    return r
detail=call('/api/assets/'+aid).json
r=call('/media/'+aid,extra={'Range':'bytes=0-1023'})
assert r.status_code==206 and len(r.data)==1024
r.close()
report['checks'].append('中文UNC HTTP Range 206')
for mode in ['copy','encode']:
    j=call('/api/clip',dict(asset_id=aid,start=.3,end=min(detail['meta']['duration'],2.3),mode=mode,category='未分类')).json
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        state=call('/api/jobs/'+j['job_id']).json
        if state['status'] in ('done','failed','cancelled'): break
        time.sleep(.3)
    if state['status']!='done': raise RuntimeError(json.dumps(state,ensure_ascii=False))
    report['checks'].append({'mode':mode,'result':state['result']})
    # 完整解码测试片段，不产生新视频。
    studio.subprocess.run([studio.CONFIG['ffmpeg'],'-v','error','-i',state['result']['path'],'-f','null','-'],check=True,capture_output=True,timeout=60,creationflags=studio.FLAGS)
after=hashlib.sha256(path.read_bytes()).hexdigest()
assert before==after
report['after_sha256']=after
(studio.STATE/'smoke-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
