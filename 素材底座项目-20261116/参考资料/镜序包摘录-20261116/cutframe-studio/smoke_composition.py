"""技术测试，不使用正式配音；测试视频不得当作业务成片。"""
import io
import json
import time
import hashlib
import subprocess
from pathlib import Path
import app as studio
from composition import parse_srt

studio.CONFIG['output']=str(studio.STATE/'smoke-outputs')
client=studio.app.test_client()
headers={'Host':f'127.0.0.1:{studio.PORT}','X-Local-Token':studio.TOKEN}
def call(url,data=None):
    r=client.get(url,headers=headers) if data is None else client.post(url,json=data,headers=headers)
    if r.status_code>=400: raise RuntimeError(str(r.json))
    return r.json
def wait(jid):
    end=time.monotonic()+240
    while time.monotonic()<end:
        r=call('/api/jobs/'+jid)
        if r['status'] in ('done','failed','cancelled'):
            if r['status']!='done': raise RuntimeError(json.dumps(r,ensure_ascii=False))
            return r['result']
        time.sleep(.5)
    raise RuntimeError('媒体测试超时')
work=studio.STATE/'technical-inputs';work.mkdir(exist_ok=True)
for name,duration,freq in [('voice-test',3,440),('music-test',8,220)]:
    p=work/(name+'.wav')
    if not p.exists():
        subprocess.run([studio.CONFIG['ffmpeg'],'-v','error','-n','-f','lavfi','-i',f'sine=frequency={freq}:duration={duration}','-ar','48000','-ac','2',str(p)],check=True,creationflags=studio.FLAGS)
srt='1\n00:00:00,100 --> 00:00:01,500\n本地技术验证\n\n2\n00:00:02,000 --> 00:00:03,700\n不是正式业务成片\n'
(work/'test.srt').write_text(srt,'utf-8')
imported={}
for kind,p in [('voice',work/'voice-test.wav'),('music',work/'music-test.wav'),('subtitle',work/'test.srt')]:
    with p.open('rb') as f:
        r=client.post('/api/imports',data={'kind':kind,'file':(io.BytesIO(f.read()),p.name)},headers=headers)
        assert r.status_code==200,r.json
        imported[kind]=r.json['id']
asset=studio.one("SELECT * FROM assets WHERE name='16199_小区场景.mp4' AND root='xiaoq'")
data=dict(name='技术测试非业务成片',shots=[dict(asset_id=asset['id'],name=asset['name'],start=.3,end=2.3),dict(asset_id=asset['id'],name=asset['name'],start=3,end=5)],
          imports=imported,settings=dict(canvas='1080x1920',fps=30,fit='contain',source_audio='mute',voice_offset=0,music_start=0,music_volume=.12,subtitle_offset=0,font_size=52,subtitle_bottom=180))
saved=call('/api/projects',data)
loaded=call('/api/projects/'+saved['id'])
assert loaded['shots']==data['shots'] and loaded['imports']==data['imports']
data['id']=saved['id']
bad=json.loads(json.dumps(data));bad['settings']['voice_offset']=5
assert client.post('/api/render',json=bad,headers=headers).status_code==400
result=wait(call('/api/render',data)['job_id'])
samples=json.loads((studio.STATE.parent/'cutframe-precheck'/'小区-probe.json').read_text('utf-8-sig'))
candidate=next(r for r in sorted(samples,key=lambda r:r['Bytes']) if r['Success'] and any(s.get('codec_name')=='hevc' for s in r['Metadata']['streams']))
p=Path(candidate['Path']);rel=p.relative_to(Path(studio.CONFIG['roots']['xiaoq']['path'])).as_posix()
aid=hashlib.sha256(('xiaoq/'+rel).encode()).hexdigest()[:32]
proxy=call('/api/proxy/'+aid,{})
if 'job_id' in proxy: proxy=wait(proxy['job_id'])
report=dict(project_restore='passed',voice_overrun_rejected='passed',composition=result,hevc_proxy=proxy,notice='测试音轨为合成正弦波，未验证正式配音与业务成片质量')
(studio.STATE/'composition-smoke-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
