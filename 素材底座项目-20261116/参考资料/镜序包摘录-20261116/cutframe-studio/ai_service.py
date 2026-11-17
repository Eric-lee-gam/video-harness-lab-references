"""单条字幕的本地AI候选、人工反馈与审核经验；不会自动采用镜头。"""
import json,uuid,subprocess,time,hashlib
from pathlib import Path
from flask import request,jsonify,send_file,Response
from ai_store import connect,now,latest_feedback
from ai_discovery import history_exclusions,query_key
import verified_people
from gpt_provider import load_rules,budget_status
from ai_knowledge import snapshot,validate_draft

def register(app,env):
    state=env['STATE'];base=env['BASE'];home=base.parent
    storage=state/'ai';storage.mkdir(exist_ok=True)
    dbpath=storage/'learning.sqlite3'
    with connect(dbpath):pass
    model=home/'local/ai-models/chinese-clip'
    python=home/'local/qwen-env/Scripts/python.exe'
    rules_path=base/'gpt-retrieval-rules.json'
    ledger=storage/'gpt-costs.sqlite3'
    @app.get('/api/ai/portrait/<aid>')
    def portrait_check(aid):
        from media import probe,is_portrait_916
        a=env['get_asset'](aid);m=probe(env['CONFIG']['ffprobe'],env['asset_path'](a))
        return jsonify(allowed=is_portrait_916(m),meta=m)
    def pointer():
        p=storage/'active-index.json'
        return json.loads(p.read_text('utf-8')) if p.exists() else None
    def raw_roots():return {k:v for k,v in env.get('CONFIG',{}).get('roots',{}).items() if v.get('role')=='raw'}
    def catalog(scope='all'):
        roots=raw_roots()
        if scope!='all':
            if scope not in roots:raise ValueError('只能在已授权原始素材库检索')
            roots={scope:roots[scope]}
        if not roots:return []
        return env['many']('SELECT id,root,rel,name FROM assets WHERE available=1 AND root IN ('+','.join('?' for _ in roots)+') ORDER BY root,rel',list(roots))
    def run_row(rid):
        with connect(dbpath) as db:r=db.execute('SELECT * FROM runs WHERE id=?',(rid,)).fetchone()
        if not r:raise ValueError('候选批次不存在')
        return dict(r)
    def run_worker(jid,data):
        work=state/'jobs'/jid
        data['model_path']=str(model.resolve())
        req=work/'ai-request.json';req.write_text(json.dumps(data,ensure_ascii=False),'utf-8')
        with (work/'ai.log').open('w',encoding='utf-8') as log:
            worker_file='gpt_worker.py' if data.get('provider')=='gpt' else 'ai_worker.py'
            p=subprocess.Popen([str(python),'-X','utf8',str(base/worker_file),str(req.resolve())],stdout=log,stderr=log,creationflags=0x08000000)
            env['PROCESSES'][jid]=p;started=time.monotonic()
            try:
                while p.poll() is None:
                    if env['one']('SELECT status FROM jobs WHERE id=?',(jid,))['status']=='cancelled' or time.monotonic()-started>3600:
                        p.terminate();p.wait(timeout=20);raise ValueError('AI任务已取消或超时，旧索引和素材未改动')
                    progress=work/'progress.json'
                    if progress.exists():
                        try:
                            d=json.loads(progress.read_text('utf-8'));env['update_job'](jid,progress=d.get('progress',90*d['done']/max(1,d['total'])),message=d.get('message',f"建立本地视觉索引 {d['done']}/{d['total']}"))
                        except (ValueError,OSError):pass
                    time.sleep(.5)
                if p.returncode:raise ValueError('本地AI处理失败：'+(work/'ai.log').read_text('utf-8',errors='replace')[-600:])
            finally:
                env['PROCESSES'].pop(jid,None)
                if p.poll() is None:p.terminate()
        if env['one']('SELECT status FROM jobs WHERE id=?',(jid,))['status']=='cancelled':raise ValueError('已取消')
        return json.loads((work/'result.json').read_text('utf-8'))
    def require_model():
        if not python.exists() or not (model/'pytorch_model.bin').exists():raise ValueError('本地视觉模型尚未安装完整')
    @app.get('/api/ai/status')
    def ai_status():
        with connect(dbpath) as db:
            counts={key:db.execute('SELECT count(*) FROM '+key).fetchone()[0] for key in ['runs','feedback','rules']}
        rule=load_rules(rules_path)
        return jsonify(index=pointer(),counts=counts,catalog_total=len(catalog()),roots={k:v['label'] for k,v in raw_roots().items()},mode='GPT分段检查与固定时长复核',model=rule['model'],training='未训练；候选需人工确认',local_only=False,rule_version=rule['version'],rule_hash=rule['hash'],budget=budget_status(ledger,rule))
    @app.get('/api/ai/retrieval-rules')
    def retrieval_rules():
        return jsonify(load_rules(rules_path))
    @app.post('/api/ai/discover')
    def ai_discover():
        rule=load_rules(rules_path)
        budget=budget_status(ledger,rule)
        if budget['pending']:raise ValueError('GPT有未核账或进行中的请求，已阻止新任务；先核对费用，不重复调用')
        if budget['remaining_usd']<rule['limits']['request_reserve_usd']:raise ValueError('GPT预算不足，未启动检索；不会自动提高额度')
        if not python.exists():raise ValueError('GPT工作进程运行环境不存在')
        d=request.get_json() or {};text=str(d.get('text','')).strip();duration=float(d.get('duration',0))
        if not text or len(text)>500 or not .03<=duration<=60:raise ValueError('请提供有效字幕及片段时长')
        project=str(d.get('project_id') or '');task=str(d.get('task_id') or '')
        if not project or project=='unsaved' or not task:raise ValueError('请保存工程并选择字幕任务')
        scope=str(d.get('scope','all'));assets=catalog(scope)
        annotations=home/'local/action-annotation'
        banned=verified_people.blocked_sources(annotations)
        assets=[a for a in assets if a['id'] not in banned]
        if len(str(d.get('context','')))>1500:raise ValueError('上下文过长')
        source_mode=d.get('source_mode','new')
        if source_mode not in ('new','confirmed'):raise ValueError('候选来源无效')
        payload=dict(text=text,need=str(d.get('need',''))[:500],context=str(d.get('context','')),duration=duration,scope=scope,project_id=project,task_id=task,board_context=str(d.get('board_context','')),use_experience=bool(d.get('use_experience',True)),reviewer=str(d.get('reviewer','')).strip()[:80],source_mode=source_mode)
        payload['rule_hash']=rule['hash'];payload['provider']='gpt'
        with connect(dbpath) as db:
            knowledge=snapshot(db,project,payload['reviewer'],payload['use_experience'])
            payload['knowledge_hash']=knowledge['hash']
            payload['query_key']=query_key(payload)+':'+rule['hash']+':'+knowledge['hash']+':'+source_mode
            prior=history_exclusions(db.execute('SELECT payload,result FROM runs'),project,task,payload['query_key']);rules=[]
            if payload['use_experience']:
                for row in db.execute("SELECT * FROM rules WHERE status='approved'"):
                    p=json.loads(row['payload'])
                    if p['scope']=='project' and p['project_id']!=project:continue
                    rules.append(dict(id=row['id'],**p))
        excludes=set(d.get('exclude_assets',[]))|prior['seen']
        # 不把已展示的小测样例重新包装成正式新候选。
        import importlib.util
        helper=home/'outputs/continuous-retrieval/history_exclusions.py'
        if helper.exists() and source_mode=='new':
            spec=importlib.util.spec_from_file_location('gpt_history_exclusions',helper);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
            historical=mod.exclusions(home,include_experiments=True)
            excludes.update(historical[0] if isinstance(historical,tuple) else historical)
        saved=env['one']('SELECT data FROM projects WHERE id=?',(project,))
        if not saved or not saved.get('data'):raise ValueError('工程不存在，请先保存')
        excludes.update(s['asset_id'] for s in json.loads(saved['data']).get('shots',[]))
        active=pointer();hashes=set(prior['hashes'])
        if active:
            ip=state/'jobs'/active['job_id']/'index.json'
            if ip.exists():hashes.update(r['phash'] for r in json.loads(ip.read_text('utf-8'))['frames'] if r['asset_id'] in excludes)
        payload.update(mode='discover',round=prior['round'],exclude_assets=sorted(excludes),rules=[r['id'] for r in rules],catalog_total=len(assets))
        rid=uuid.uuid4().hex
        def worker(jid):
            cursors={}
            with connect(dbpath) as db:
                for row in db.execute('SELECT payload,result FROM runs ORDER BY created'):
                    p=json.loads(row['payload'])
                    if p.get('project_id')==project and p.get('task_id')==task and p.get('query_key')==payload['query_key']:
                        cursors.update(json.loads(row['result']).get('scan_cursors',{}))
            result=run_worker(jid,dict(payload,run_id=rid,catalog=assets,home=str(home.resolve()),gpt_rules=rule,knowledge=knowledge,ledger=str(ledger.resolve()),scan_cursors=cursors,roots={k:v['path'] for k,v in raw_roots().items()},ffmpeg=env['CONFIG']['ffmpeg'],ffprobe=env['CONFIG']['ffprobe'],examined_before=sorted(prior['examined']),exclude_hashes=sorted(hashes),rules=rules))
            result.update(run_id=rid,task_id=task,duration=duration)
            # 工作进程也排重；入库前再校验硬约束，避免旧素材被错误展示为新一轮。
            items=result['items'];ids=[x['asset_id'] for x in items]
            if len(ids)>10 or len(set(ids))!=len(ids) or set(ids)&excludes:raise ValueError('候选轮次排重校验失败，结果未发布')
            if any(abs(x['end']-x['start']-duration)>.001 or x['start']<0 or x['end']>x['duration']+.001 for x in items):raise ValueError('候选固定时长校验失败，结果未发布')
            with connect(dbpath) as db:db.execute('INSERT INTO runs VALUES(?,?,?,?)',(rid,now(),json.dumps(payload,ensure_ascii=False),json.dumps(result,ensure_ascii=False)))
            return result
        return jsonify(job_id=env['submit']('寻找本条新10个素材',worker))
    @app.post('/api/ai/index')
    def ai_index():
        require_model();d=request.get_json() or {}
        ids=d.get('asset_ids')
        if ids is None:
            manifest=storage/'sample-manifest.json'
            if not manifest.exists():raise ValueError('尚未准备小样本清单')
            ids=json.loads(manifest.read_text('utf-8'))['asset_ids']
        if not isinstance(ids,list) or not 1<=len(ids)<=100:raise ValueError('单次小样本索引需1至100个素材')
        def worker(jid):
            assets=[]
            for aid in dict.fromkeys(ids):
                a=env['get_asset'](aid)
                if env['CONFIG']['roots'][a['root']].get('role')!='raw':raise ValueError('本阶段仅索引原始素材库')
                m=env['metadata'](a)
                if m['duration']>0:assets.append(dict(id=aid,name=a['name'],root=a['root'],rel=a['rel'],duration=m['duration'],path=str(env['asset_path'](a).resolve())))
            old=pointer()
            result=run_worker(jid,dict(mode='index',assets=assets,ffmpeg=env['CONFIG']['ffmpeg'],reuse_index=str((state/'jobs'/old['job_id']/'index.json').resolve()) if old else None))
            active=dict(job_id=jid,created=now(),**result)
            temp=storage/'active-index.tmp';temp.write_text(json.dumps(active,ensure_ascii=False),'utf-8');temp.replace(storage/'active-index.json')
            return active
        return jsonify(job_id=env['submit']('AI小样本视觉索引',worker))
    @app.post('/api/ai/search')
    def ai_search():
        require_model();d=request.get_json() or {};active=pointer()
        if not active:raise ValueError('请先建立小样本视觉索引')
        text=str(d.get('text','')).strip();duration=float(d.get('duration',0))
        if not text or len(text)>500 or not .03<=duration<=60:raise ValueError('请提供字幕和有效固定时长')
        if len(str(d.get('context','')))>1500:raise ValueError('上下文过长')
        project=str(d.get('project_id') or 'unsaved');task=str(d.get('task_id') or '')
        if not task:raise ValueError('请先选择字幕任务')
        rid=uuid.uuid4().hex
        with connect(dbpath) as db:
            rules=[]
            if d.get('use_experience',True):
                for r in db.execute("SELECT * FROM rules WHERE status='approved'"):
                    p=json.loads(r['payload'])
                    if p['scope']=='project' and p['project_id']!=project:continue
                    rules.append(dict(id=r['id'],**p))
        payload=dict(need=str(d.get('need',''))[:500],board_context=str(d.get('board_context','')),text=text,context=str(d.get('context','')),duration=duration,project_id=project,task_id=task,exclude_assets=list(dict.fromkeys(d.get('exclude_assets',[]))),use_experience=bool(d.get('use_experience',True)),index_job=active['job_id'],rules=[r['id'] for r in rules])
        def worker(jid):
            result=run_worker(jid,dict(payload,mode='search',run_id=rid,index_path=str((state/'jobs'/active['job_id']/'index.json').resolve()),rules=rules))
            result['run_id']=rid;result['task_id']=task;result['duration']=duration
            with connect(dbpath) as db:db.execute('INSERT INTO runs VALUES(?,?,?,?)',(rid,now(),json.dumps(payload,ensure_ascii=False),json.dumps(result,ensure_ascii=False)))
            return result
        return jsonify(job_id=env['submit']('本条AI候选检索',worker))
    @app.get('/api/ai/runs')
    def ai_runs():
        project=request.args.get('project_id','unsaved');task=request.args.get('task_id','')
        with connect(dbpath) as db:
            out=[]
            for row in db.execute('SELECT * FROM runs ORDER BY rowid DESC'):
                p=json.loads(row['payload'])
                if p['project_id']==project and p['task_id']==task:
                    out.append(dict(id=row['id'],created=row['created'],payload=p,result=json.loads(row['result']),feedback=latest_feedback(db,row['id'])))
                    if len(out)>=100:break
        return jsonify(items=out)
    @app.get('/api/ai/thumb/<rid>/<cid>')
    def ai_thumb(rid,cid):
        result=json.loads(run_row(rid)['result']);c=next((x for x in result['items'] if x['id']==cid),None)
        if not c:raise ValueError('候选不存在')
        return send_file(c['image'],conditional=True)
    @app.post('/api/ai/feedback')
    def ai_feedback():
        d=request.get_json() or {};row=run_row(d.get('run_id'));result=json.loads(row['result']);cid=d.get('candidate_id')
        if cid!='all' and not any(c['id']==cid for c in result['items']):raise ValueError('候选不属于该批次')
        verdict=d.get('verdict');code=str(d.get('reason_code',''));reviewer=str(d.get('reviewer','')).strip();reason=str(d.get('reason','')).strip()
        if verdict not in ('suitable','unsuitable','unreviewed'):raise ValueError('无效评价')
        if not reviewer or len(reviewer)>80 or len(reason)>2000:raise ValueError('请填写评价人，说明不超过2000字')
        ids=[c['id'] for c in result['items']] if cid=='all' else [cid]
        saved=[]
        with connect(dbpath) as db:
            for candidate in ids:
                fid=uuid.uuid4().hex;db.execute('INSERT INTO feedback VALUES(?,?,?,?,?,?,?,?)',(fid,now(),row['id'],candidate,reviewer,verdict,code,reason));saved.append(fid)
        return jsonify(ids=saved,message='已保存原始反馈；未自动训练、未自动启用规则')
    @app.post('/api/ai/adoption')
    def ai_adoption():
        d=request.get_json() or {};row=run_row(d.get('run_id'));p=json.loads(row['payload'])
        if not any(c['id']==d.get('candidate_id') for c in json.loads(row['result'])['items']):raise ValueError('候选不属于该批次')
        if d.get('action') not in ('adopted','removed','adjusted'):raise ValueError('采用事件无效')
        if d.get('project_id')!=p['project_id'] or d.get('task_id')!=p['task_id']:raise ValueError('工程或字幕任务不一致')
        with connect(dbpath) as db:db.execute('INSERT INTO adoptions VALUES(?,?,?,?,?,?,?,?)',(uuid.uuid4().hex,now(),p['project_id'],p['task_id'],row['id'],d['candidate_id'],d['action'],json.dumps(d.get('shot',{}),ensure_ascii=False)))
        return jsonify(ok=True)
    @app.post('/api/ai/rules/propose')
    def ai_propose():
        d=request.get_json() or {}
        with connect(dbpath) as db:
            f=db.execute('SELECT * FROM feedback WHERE id=?',(d.get('feedback_id'),)).fetchone()
            if not f or f['verdict']=='unreviewed':raise ValueError('需要一条明确评价才能生成经验草稿')
            existing=db.execute("SELECT * FROM rules WHERE feedback_id=? AND status IN ('pending','approved')",(f['id'],)).fetchone()
            if existing:return jsonify(id=existing['id'],payload=json.loads(existing['payload']),status=existing['status'])
            row=run_row(f['run_id']);p=json.loads(row['payload']);c=next(x for x in json.loads(row['result'])['items'] if x['id']==f['candidate_id'])
            # 默认本工程；产品、模糊、重复等自由理由不自动推广成全局规则。
            payload=dict(text=p['text'],context=p['context'],asset_id=c['asset_id'],start=c['start'],end=c['end'],scope='project',project_id=p['project_id'],action='prefer' if f['verdict']=='suitable' else 'avoid',reason=f['reason'],reason_code=f['reason_code'],description='相似字幕优先推荐该源片段' if f['verdict']=='suitable' else '相似字幕排除该源片段')
            rid=uuid.uuid4().hex;db.execute('INSERT INTO rules VALUES(?,?,?,?,?,?)',(rid,now(),f['id'],'pending','',json.dumps(payload,ensure_ascii=False)))
        return jsonify(id=rid,payload=payload,status='pending')
    @app.get('/api/ai/rules')
    def ai_rules():
        with connect(dbpath) as db:rows=[dict(r) for r in db.execute('SELECT * FROM rules ORDER BY rowid DESC')]
        for r in rows:r['payload']=json.loads(r['payload'])
        return jsonify(items=rows)
    @app.post('/api/ai/knowledge/propose')
    def knowledge_propose():
        d=request.get_json() or {};payload=validate_draft(d,str(d.get('project_id','')))
        rid=uuid.uuid4().hex
        with connect(dbpath) as db:
            if d.get('source_rule_id'):
                reference=db.execute('SELECT id,feedback_id FROM rules WHERE id=?',(d['source_rule_id'],)).fetchone()
                if not reference:raise ValueError('经验来源记录不存在')
                payload['source_rule_id']=reference['id'];payload['source_feedback_id']=reference['feedback_id']
            db.execute('INSERT INTO rules VALUES(?,?,?,?,?,?)',(rid,now(),str(d.get('feedback_id','')),'pending','',json.dumps(payload,ensure_ascii=False)))
        return jsonify(id=rid,status='pending',message='已保存草稿；审核后才进入检索')
    @app.post('/api/ai/rules/review')
    def ai_review():
        d=request.get_json() or {};reviewer=str(d.get('reviewer','')).strip();status=d.get('status');scope=d.get('scope','project')
        if not reviewer or status not in ('approved','rejected','disabled') or scope not in ('project','similar'):raise ValueError('请提供审核人、状态和适用范围')
        with connect(dbpath) as db:
            r=db.execute('SELECT * FROM rules WHERE id=?',(d.get('id'),)).fetchone()
            if not r:raise ValueError('经验不存在')
            payload=json.loads(r['payload'])
            if scope=='similar' and payload['reason_code']=='duplicate':raise ValueError('与本片重复的经验只能用于本工程')
            payload['scope']=scope
            db.execute('UPDATE rules SET status=?,reviewer=?,payload=? WHERE id=?',(status,reviewer,json.dumps(payload,ensure_ascii=False),r['id']))
            db.execute('INSERT INTO rule_events VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,now(),r['id'],status,reviewer,r['payload'],json.dumps(payload,ensure_ascii=False)))
        return jsonify(ok=True)
    @app.get('/api/ai/export')
    def ai_export():
        with connect(dbpath) as db:
            rows=[]
            for table in ['runs','feedback','rules','rule_events','adoptions']:
                for row in db.execute('SELECT * FROM '+table):rows.append(json.dumps(dict(record_type=table,**dict(row)),ensure_ascii=False))
        return Response('\n'.join(rows)+'\n',mimetype='application/x-ndjson',headers={'Content-Disposition':'attachment; filename="cutframe-feedback.jsonl"'})
