import json
import time
import hashlib
from pathlib import Path
import app as s
s.CONFIG['output']=str(s.STATE/'smoke-outputs')
c=s.app.test_client()
headers={'Host':f'127.0.0.1:{s.PORT}','X-Local-Token':s.TOKEN}
def call(url,body=None):
    r=c.get(url,headers=headers) if body is None else c.post(url,json=body,headers=headers)
    if r.status_code>=400: raise RuntimeError(str(r.json))
    return r.json
def wait(jid):
    limit=time.monotonic()+300
    while time.monotonic()<limit:
        r=call('/api/jobs/'+jid)
        if r['status'] in ('done','failed','cancelled'):
            return r
        time.sleep(.5)
    raise RuntimeError('测试超时')
samples=json.loads((s.STATE.parent/'cutframe-precheck'/'小区-probe.json').read_text('utf-8-sig'))
selected=[]
for label,predicate in [('ProRes',lambda x:any(v.get('codec_name')=='prores' for v in x['Metadata']['streams'])),('HDR',lambda x:any(v.get('color_transfer') in ('arib-std-b67','smpte2084') for v in x['Metadata']['streams']))]:
    r=next(x for x in sorted(samples,key=lambda x:x['Bytes']) if x['Success'] and predicate(x))
    p=Path(r['Path']);rel=p.relative_to(Path(s.CONFIG['roots']['xiaoq']['path'])).as_posix()
    aid=hashlib.sha256(('xiaoq/'+rel).encode()).hexdigest()[:32]
    response=call('/api/proxy/'+aid,{})
    result=wait(response['job_id']) if 'job_id' in response else response
    selected.append(dict(kind=label,asset_id=aid,result=result))
    print(label,json.dumps(result,ensure_ascii=False),flush=True)
samples=json.loads((s.STATE.parent/'cutframe-precheck'/'扒扒-probe.json').read_text('utf-8-sig'))
r=next(x for x in sorted(samples,key=lambda x:x['Bytes']) if x['Success'] and any(v.get('codec_name')=='h264' for v in x['Metadata']['streams']))
p=Path(r['Path']);before=hashlib.sha256(p.read_bytes()).hexdigest();rel=p.relative_to(Path(s.CONFIG['roots']['baba']['path'])).as_posix()
aid=hashlib.sha256(('baba/'+rel).encode()).hexdigest()[:32]
m=call('/api/assets/'+aid)['meta']
response=call('/api/clip',dict(asset_id=aid,start=0,end=min(2,m['duration']),mode='copy',category='未分类'))
result=wait(response['job_id'])
assert before==hashlib.sha256(p.read_bytes()).hexdigest()
selected.append(dict(kind='扒扒无损',asset_id=aid,result=result,source_unchanged=True))
(s.STATE/'variant-smoke-report.json').write_text(json.dumps(selected,ensure_ascii=False,indent=2),'utf-8')
print('检查完成',flush=True)
