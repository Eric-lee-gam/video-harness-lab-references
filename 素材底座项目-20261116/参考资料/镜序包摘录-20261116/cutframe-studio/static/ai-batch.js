// 全片候选队列只准备素材，不采用、不评价。串行提交保证跨字幕历史排重。
const aiBatchBox=el('section',undefined,'hint');aiBatchBox.id='ai-batch';
aiBatchBox.innerHTML='<strong>全片候选准备</strong><div class="button-row"><button id="ai-batch-start" class="primary">为全部字幕查找候选</button><button id="ai-batch-resume">继续未完成项</button><button id="ai-batch-stop">停止（当前条完成后）</button></div><p id="ai-batch-status"></p><progress id="ai-batch-progress" max="1" value="0" style="width:100%"></progress><details><summary>逐条进度与结果</summary><div id="ai-batch-items"></div></details>';
aiPanel.before(aiBatchBox);
// 前置条件持续显示，避免只有消失的报错、用户无处处理。
const aiBatchPrerequisites=el('div');aiBatchPrerequisites.id='ai-batch-prerequisites';aiBatchBox.append(aiBatchPrerequisites);
function aiBatchMissing(){
 const missing=[];
 if(!projectId)missing.push({text:'工程尚未保存，候选结果需要关联工程。',button:'去填写并保存工程',run:()=>{wfStep(1);$('project-name').focus();}});
 if(typeof wf!=='undefined'&&(!wf.cues.length||wf.dirtySubtitle||!imports.subtitle))missing.push({text:'第三步字幕尚未保存，暂不能建立选片任务。',button:'去保存字幕',run:()=>wfStep(3)});
 else if(!board.tasks.length||board.context!==sbContext())missing.push({text:!board.tasks.length?'尚未从已保存字幕建立选片任务。':'字幕任务与当前内容不同，需要同步。',button:!board.tasks.length?'按已保存字幕建立任务':'同步当前字幕任务',run:async()=>{await $('sb-build').onclick();aiBatchRender();}});
 return missing;
}
function aiBatchShowPrerequisites(){
 const missing=aiBatchMissing();aiBatchPrerequisites.hidden=!missing.length;
 aiBatchPrerequisites.replaceChildren(...missing.map(item=>{const row=el('div',undefined,'button-row');const b=el('button',item.button);b.onclick=item.run;row.append(el('span',item.text),b);return row;}));
 return missing;
}
let aiBatchRunning=false,aiBatchStop=false,aiBatch=null,aiBatchProject='';
function aiBatchKey(){return 'cutframe-candidates-batch:'+projectId;}
function aiBatchSave(){localStorage.setItem(aiBatchKey(),JSON.stringify(aiBatch));aiBatchRender();}
function aiBatchContext(){return JSON.stringify({context:sbContext(),tasks:board.tasks.map(t=>({id:t.id,text:t.text,start:t.start,end:t.end,need:t.need||''}))});}
function aiBatchRender(){
 aiBatchShowPrerequisites();
 const rows=aiBatch?.items||[],done=rows.filter(x=>x.status==='done').length;
 $('ai-batch-status').textContent=rows.length?`已完成 ${done}/${rows.length} 条 · ${aiBatchRunning?'正在检索'+(aiBatchStop?'，当前条完成后停止':''):done===rows.length?'全部准备完成，可逐条筛选':'已暂停，可继续未完成项'}。找到不足10条会如实显示，不自动采用。`:'点一次，为每条字幕各准备最多10条新候选；原有镜头和历史候选保留。';
 $('ai-batch-progress').max=rows.length||1;$('ai-batch-progress').value=done;
 $('ai-batch-start').disabled=aiBatchRunning||!!(rows.length&&done<rows.length&&aiBatch.context===aiBatchContext());$('ai-batch-resume').disabled=aiBatchRunning||!rows.length||done===rows.length;$('ai-batch-stop').disabled=!aiBatchRunning;
 for(const id of ['ai-search','ai-next','ai-reject-next'])$(id).disabled=aiBatchRunning;
 $('ai-batch-items').replaceChildren(...rows.map((x,i)=>{const p=el('div',undefined,'button-row');p.append(el('span',`${i+1}. ${x.text} · ${{waiting:'等待',running:'检索中',done:`找到${x.count||0}条`,failed:'失败',cancelled:'已停止',interrupted:'已中断'}[x.status]||x.status}${x.error?' · '+x.error:''}`));if(x.status==='done')p.append(subtitleButton('查看本条候选',async()=>{const t=board.tasks.find(t=>t.id===x.task_id);if(!t)throw Error('字幕任务已变化');subtitleSelectTask(t);await aiHistory(x.run_id);}));return p;}));
}
async function aiBatchRun(){
 if(aiBatchRunning||jobId)throw Error('请等待当前任务完成');
 if(aiBatch.context!==aiBatchContext())throw Error('字幕、配音或画面要求已变化，旧队列不再适用；请先重新建立队列');
 aiBatchRunning=true;aiBatchStop=false;aiBatchRender();
 try{
  for(const item of aiBatch.items){
   if(item.status==='done')continue;
   if(aiBatchStop)break;
   if(aiBatch.context!==aiBatchContext())throw Error('内容已变化，队列已停止，已完成结果仍保留');
   try{
    item.status='running';item.error='';aiBatchSave();
    if(!item.job_id){item.request.exclude_assets=[...new Set([...item.request.exclude_assets,...shots.map(s=>s.asset_id)])];const result=await api('/api/ai/discover',item.request);item.job_id=result.job_id;aiBatchSave();}
    const j=await watch(item.job_id);
    if(!j)throw Error('任务状态暂不可用，请继续重试');
    if(j.status==='done'){item.status='done';item.count=j.result.items.length;item.run_id=j.result.run_id;if(j.result.provider==='gpt'&&j.result.stop_reason){item.error=j.result.stop_reason;if(j.result.budget_hit)aiBatchStop=true;}}
    else {item.status=j.status;item.error=j.message;item.job_id=null;}
    aiBatchSave();
    if(sbTask()?.id===item.task_id&&item.status==='done')await aiHistory(item.run_id);
    if(j.status==='cancelled'||j.status==='interrupted'){aiBatchStop=true;break;}
   }catch(e){item.status='failed';item.error=e.message;aiBatchSave();aiBatchStop=true;break;}
  }
 }finally{aiBatchRunning=false;aiBatchSave();}
}
action('ai-batch-start',async()=>{
 if(aiBatchShowPrerequisites().length){aiBatchPrerequisites.scrollIntoView?.({block:'center',behavior:'smooth'});return;}
 aiBatch={context:aiBatchContext(),created:new Date().toISOString(),items:board.tasks.map((t,i)=>({task_id:t.id,text:t.text,status:'waiting',request:{text:t.text,context:board.tasks.slice(Math.max(0,i-1),i+2).map(x=>x.text).join('，'),need:t.need||'',scope:$('ai-scope').value,board_context:board.context,duration:t.end-t.start,project_id:projectId,task_id:t.id,exclude_assets:[...new Set(shots.map(s=>s.asset_id))],use_experience:$('ai-experience').checked,reviewer:String($('ai-reviewer').value||'').trim(),source_mode:$('ai-source-mode').value||'new'}}))};aiBatchSave();await aiBatchRun();
});
action('ai-batch-resume',aiBatchRun);action('ai-batch-stop',()=>{aiBatchStop=true;aiBatchRender();});
const aiBatchOpenBase=wfOpen;wfOpen=async function(d){if(aiBatchRunning)throw Error('请先停止全片候选队列，再切换工程');return aiBatchOpenBase(d);};
setInterval(()=>{if(aiBatchProject!==projectId&&!aiBatchRunning){aiBatchProject=projectId;try{aiBatch=JSON.parse(localStorage.getItem(aiBatchKey())||'null');}catch{aiBatch=null;}aiBatchRender();}},700);
aiBatchRender();

let aiBatchGateState='';setInterval(()=>{const key=JSON.stringify([projectId,board.tasks.length,board.context,sbContext(),typeof wf!=='undefined'?wf.dirtySubtitle:null,typeof imports!=='undefined'?imports.subtitle:null]);if(key!==aiBatchGateState){aiBatchGateState=key;aiBatchShowPrerequisites();}},700);
