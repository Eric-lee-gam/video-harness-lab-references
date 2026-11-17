'use strict';
// 逐条字幕人工选片；匹配与推荐模型不在本阶段启用。

function subtitlePlaybackPlan(){return board.mode==='subtitle'?SubtitleBoardCore.playbackPlan(board.tasks,shots,sbDuration()):{shots,errors:[],gaps:[]};}
const gapProjectBase=project;project=function(){const p=gapProjectBase();if(p.workflow?.storyboard?.mode==='subtitle')p.workflow.storyboard.gap_policy='continue_previous';return p;};
const subtitleTaskShots=t=>shots.filter(s=>s.task_ids?.includes(t.id));
const subtitleTaskSignature=t=>SubtitleBoardCore.signature(t,shots,sbContext());
const subtitleTaskErrors=t=>SubtitleBoardCore.errors(t,shots);
const subtitleLayout=t=>SubtitleBoardCore.layout(t,shots);
$('sb-build').textContent='按已保存字幕建立／同步任务';$('sb-add-task').hidden=true;
$('sb-workbench').querySelector('.hint').textContent='每条字幕一个任务，一至两个镜头。人工搜索、预览、选入，再确认；字幕停顿延续上一镜头原片；原片不足会提示。';
$('sb-tasks').previousElementSibling.textContent='原文与时间来自第三步；修改字幕后点击同步，已有候选和片段保留供重新核对。';
const timelineHeading=$('sb-timeline').previousElementSibling;
timelineHeading.textContent='镜头按字幕时间排列。源入点在当前任务调整；删除只移出工程。';
timelineHeading.previousElementSibling.textContent='4 已选镜头与来源';
const fallbackLabel=el('label');fallbackLabel.innerHTML='<input id="sb-fallback" type="checkbox">这是一段替代画面（人物讲述／相关空镜）';$('sb-reason').parentElement.after(fallbackLabel);
function subtitleRefresh(){renderShots();sbTasks();sbCandidates();sbChanged();subtitleRefreshPreview();}
// 修改镜头后立即撤下旧画面；不替用户补齐时间缺口。
function subtitleRefreshPreview(){
 wfPause();wf.playRange=null;wf.shotIndex=-1;shotPreview.activeKey=null;
 shotPreview.videos.forEach(v=>v.style.visibility='hidden');
 const t=sbTask();wf.time=t?.start||0;wfCaption();
 if(!t||subtitleTaskErrors(t).length){
  $('wf-caption').textContent='';$('wf-frame').dataset.previewState='empty';
  $('wf-preview-status').textContent= t&&subtitleTaskShots(t).length?'本条镜头未完整覆盖字幕，请重新分配时间或增加镜头后联播。':'本条待选片，请先添加镜头。';return;
 }
 $('wf-preview-status').textContent='已更新本条选片，正在定位首帧；点击配音联播检查。';
 wfSeek(t.start).catch(e=>notice(e.message,true));
}
function subtitleButton(label,fn){const b=el('button',label);b.onclick=async()=>{try{await fn();}catch(e){notice(e.message,true);}};return b;}
function subtitleResetReplace(){sbReplace=null;$('sb-cancel-replace').hidden=true;$('sb-adopt').textContent='采用到当前任务';}
function subtitleSelectTask(t){wfPause();wf.playRange=null;subtitleResetReplace();board.selected=t.id;sbTasks();sbCandidates();wfChanged();subtitleRefreshPreview();}
async function subtitlePlay(t,neighbors){
 const i=board.tasks.indexOf(t),group=neighbors==='previous'?board.tasks.slice(Math.max(0,i-1),i+1):neighbors?board.tasks.slice(Math.max(0,i-1),i+2):[t];
 for(const item of group)if(subtitleTaskErrors(item).length)throw Error('播放范围内仍有未选镜头或时长问题，请先完成这些任务');
 const plan=subtitlePlaybackPlan();for(const gap of plan.gaps)if(gap.error&&gap.start>=group[0].start&&gap.start<group.at(-1).end)throw Error(gap.error);
 await wfSeek(group[0].start);wf.playRange={start:group[0].start,end:group.at(-1).end};await $('wf-play').onclick();
}
const oldTasks=sbTasks;
sbTasks=function(){
 if(board.mode!=='subtitle'){oldTasks();return;}
 const box=$('sb-tasks');box.replaceChildren();
 board.tasks.forEach((t,i)=>{
  // 取消尚未采用镜头的旧双镜预规划；已有镜头与切点不变。
  if(t.planned_shots===2&&!subtitleTaskShots(t).length){t.planned_shots=1;delete t.split;t.accepted=null;}
  const c=el('article',undefined,'sb-task'+(board.selected===t.id?' selected':'')),ss=subtitleTaskShots(t),errs=subtitleTaskErrors(t),good=t.accepted===subtitleTaskSignature(t);
  c.append(subtitleButton(`${i+1} · ${t.start.toFixed(2)}–${t.end.toFixed(2)} 秒 · ${good?'已确认':ss.length?'已选待核对':'待选片'}`,()=>subtitleSelectTask(t)),el('p',t.text));
  if(board.selected===t.id){
   c.append(el('p',`本条 ${(t.end-t.start).toFixed(2)} 秒 · ${ss.length?'已选 '+ss.length+' 个镜头':'尚未选镜头'}`));
   const gap=subtitlePlaybackPlan().gaps.find(g=>g.task_id===t.id);if(gap)c.append(el('p',gap.error||`字幕结束后继续播放上一镜头 ${gap.extra.toFixed(2)} 秒，画面接至 ${gap.end.toFixed(2)} 秒；字幕和配音时间不变。`,gap.error?'wf-pending':'small'));
   const requirement=el('details'),summary=el('summary','画面要求（选填）');
   requirement.append(summary,sbInput('希望画面出现什么',t.need,v=>{t.need=v;t.accepted=null;},'textarea'));c.append(requirement);
   if(ss.length===2||t.planned_shots===2){const l=el('label','两个镜头中间切点／成片秒'),input=el('input');input.type='number';input.step='.01';input.value=Number(t.split).toFixed(3);input.min=t.start+.01;input.max=t.end-.01;input.onchange=()=>{const old=t.split;t.split=Number(input.value);try{if(ss.length)subtitleLayout(t);t.accepted=null;subtitleRefresh();}catch(e){t.split=old;input.value=old;notice(e.message,true);}};l.append(input);c.append(l);}
   ss.forEach((s,j)=>{
    c.append(el('p',`镜头${j+1} ${s.name} · 成片 ${Number(s.timeline_start).toFixed(2)}–${(Number(s.timeline_start)+s.end-s.start).toFixed(2)} 秒 · 源 ${s.start.toFixed(2)}–${s.end.toFixed(2)} 秒`,'small'));
    const l=el('label',`镜头${j+1}源入点／秒`),input=el('input');input.type='number';input.min=0;input.step='.01';input.value=s.start;input.onchange=()=>{const prior=s.start;s.start=Number(input.value);try{subtitleLayout(t);t.accepted=null;subtitleRefresh();}catch(e){s.start=prior;input.value=prior;notice(e.message,true);}};l.append(input);c.append(l);
    c.append(subtitleButton(`预览镜头${j+1}原片`,()=>sbSelect(s)),subtitleButton(`替换镜头${j+1}`,()=>{sbReplace=shots.indexOf(s);$('sb-cancel-replace').hidden=false;$('sb-adopt').textContent=`替换镜头${j+1}`;notice('选择新素材、打点后点击替换；采用前保留旧镜头。');}),subtitleButton(`移除镜头${j+1}`,()=>{wfPause();shots.splice(shots.indexOf(s),1);t.accepted=null;subtitleResetReplace();subtitleRefresh();}));
    if(s.fallback){c.append(el('p','替代画面理由：'+(s.reason||'未填写'),'wf-pending'));c.append(subtitleButton(s.fallback_confirmed?'已允许替代（点击撤回）':'我确认允许这个替代画面',()=>{s.fallback_confirmed=!s.fallback_confirmed;t.accepted=null;subtitleRefresh();}));}
   });
   if(ss.length===1)c.append(subtitleButton('＋添加第二镜头',()=>{subtitleResetReplace();$('sb-adopt').textContent='选入镜头②';notice('在右侧查找第二个镜头，预览并打点后选入。两镜默认均分，可调整切点。');}));
   if(ss.length&&errs.length){
    const covered=ss.reduce((sum,s)=>sum+Math.max(0,Math.min(t.end,s.timeline_start+s.end-s.start)-Math.max(t.start,s.timeline_start)),0),missing=Math.max(0,t.end-t.start-covered);
    c.append(el('p',errs.join('；')+(missing>.001?`；本条尚缺 ${missing.toFixed(2)} 秒画面。可增加镜头，或手动重新分配；不会自动延长。`:''),'wf-pending'),subtitleButton('按本条时间重新分配镜头',()=>{if(ss.length===2&&!(t.split>t.start&&t.split<t.end))t.split=(t.start+t.end)/2;subtitleLayout(t);t.accepted=null;subtitleRefresh();}));
   }
   c.append(subtitleButton('预览本条',()=>subtitlePlay(t,false)),subtitleButton('确认并下一条',()=>{if(board.context!==sbContext())throw Error('字幕或配音已变化，请先同步任务');const e=subtitleTaskErrors(t);if(e.length)throw Error(e.join('；'));t.accepted=subtitleTaskSignature(t);board.confirmed=null;subtitleSelectTask(board.tasks[i+1]||t);notice('本条已确认，原文和配音保持不变。');}));
  }box.append(c);
 });
 if(board.archived?.length)box.append(el('p',`${board.archived.length} 条旧任务已归档保留，不参与当前导出。`,'small'));
};
action('sb-build',()=>{
 if(!wf.cues.length||wf.dirtySubtitle||!imports.subtitle)throw Error('请先保存第三步字幕');
 if(board.mode!=='subtitle'&&shots.length)throw Error('旧工程已有镜头，暂不自动迁移；请保留旧工程并从空镜头工程建立字幕任务');
 const result=SubtitleBoardCore.sync(board.tasks,wf.cues,Number($('subtitle-offset').value),()=>crypto.randomUUID());
 board.archived=board.archived||[];
 for(const t of result.removed){board.archived.push({task:t,shots:structuredClone(subtitleTaskShots(t)),candidates:structuredClone(board.candidates.filter(c=>c.task_id===t.id))});for(let i=shots.length-1;i>=0;i--)if(shots[i].task_ids?.includes(t.id))shots.splice(i,1);}
 board.tasks=result.tasks;board.mode='subtitle';board.version=2;board.enabled=true;board.context=sbContext();board.confirmed=null;
 if(!board.tasks.some(t=>t.id===board.selected))board.selected=board.tasks[0]?.id;subtitleRefresh();notice('已同步字幕原文和时间，已有选片保留；变化的任务需要重新核对时长与画面。');
});
const adoptOld=$('sb-adopt').onclick;
$('sb-adopt').onclick=async()=>{
 if(board.mode!=='subtitle')return adoptOld();
 try{const t=sbTask();if(!t)throw Error('先选择字幕任务');if(board.context!==sbContext())throw Error('请先同步字幕任务');const ss=subtitleTaskShots(t);if(!ss.length&&t.planned_shots===2){t.planned_shots=1;delete t.split;}if(ss.length>=2&&sbReplace===null)throw Error('每条最多两个镜头，请替换或移除');
  const aspect=await api('/api/ai/portrait/'+sbAsset?.id);if(!aspect.allowed)throw Error('仅允许原始9:16竖屏素材，请更换');const r=sbRange();if($('sb-fallback').checked&&!r.reason.trim())throw Error('请填写替代画面的理由');
  const s={...r,available_end:r.end,task_ids:[t.id],fallback:$('sb-fallback').checked,fallback_confirmed:false};if(t.planned_shots===2)s.slot=sbReplace!==null?(shots[sbReplace].slot??ss.indexOf(shots[sbReplace])):[0,1].find(i=>!ss.some((x,j)=>(x.slot??j)===i));const backup=structuredClone(shots),split=t.split;
  try{if(sbReplace!==null){if(!shots[sbReplace]?.task_ids?.includes(t.id))throw Error('替换目标不属于当前任务');shots.splice(sbReplace,1,s);}else{shots.push(s);if(ss.length===1&&t.planned_shots!==2)t.split=(t.start+t.end)/2;}subtitleLayout(t);}catch(e){shots.splice(0,shots.length,...backup);t.split=split;throw e;}
  wfPause();subtitleResetReplace();t.accepted=null;subtitleRefresh();notice('已选入，尚未确认。请配音联播后确认本条。');
 }catch(e){notice(e.message,true);}
};
const issuesOld=sbIssues;
sbIssues=function(){
 if(board.mode!=='subtitle')return issuesOld();const e=subtitlePlaybackPlan().errors;
 if(board.context!==sbContext())e.push('文案、配音或字幕已变化，请同步任务');
 if(!imports.voice||wf.confirmed_voice!==imports.voice)e.push('请先确认配音');if(!imports.subtitle||wf.dirtySubtitle||wf.confirmed_subtitle!==imports.subtitle)e.push('请先保存并确认字幕');
 if(!board.tasks.length)e.push('请先按字幕建立任务');
 for(const t of board.tasks){e.push(...subtitleTaskErrors(t).map(x=>`${t.text}：${x}`));if(t.accepted!==subtitleTaskSignature(t))e.push('尚未逐条确认：'+t.text);}
 if(shots.some(s=>s.task_ids?.length!==1||!board.tasks.some(t=>t.id===s.task_ids[0])))e.push('存在未关联当前字幕的镜头');return [...new Set(e)];
};
const statusOld=sbStatus;
sbStatus=function(){if(board.mode!=='subtitle'){statusOld();if(!board.tasks.length)$('sb-status').textContent='请先保存并确认字幕，再点击“按已保存字幕建立／同步任务”。';return;}const e=sbIssues();$('sb-status').textContent=board.confirmed===sbSignature()?'所有任务已确认，可以继续。':e.length?e.slice(0,6).join('；'):'每条已确认，请连贯预览后确认全部选片。';if(e.length||board.confirmed!==sbSignature())$('render-film').disabled=true;};
const renderOld=renderShots;
renderShots=function(){renderOld();if(board.mode==='subtitle'){document.querySelectorAll('#shots .sb-links,#shots .shot-actions').forEach(n=>n.hidden=true);document.querySelectorAll('#shots .shot-times input').forEach(n=>n.disabled=true);}};
const stepOld=wfStep;wfStep=function(n){wf.playRange=null;return stepOld(n);};

// 候选直接选入：以候选保存的源时间为准，确认前不修改任何镜头。
async function subtitleCandidateDialog(candidate){
 try{const check=await api('/api/ai/portrait/'+candidate.asset_id);if(!check.allowed){notice('此源素材不是9:16竖屏，不能采用。请换一条候选。',true);return;}}catch(e){notice('画幅检查失败，未采用：'+e.message,true);return;}
 const t=sbTask();if(!t||candidate.task_id!==t.id)throw Error('请先选择该候选所属的字幕任务');
 if(board.context!==sbContext())throw Error('请先同步字幕任务');
 const original=JSON.stringify({task:t,shots,context:sbContext(),candidate});
 const dialog=el('dialog');dialog.id='sb-candidate-dialog';dialog.setAttribute('aria-label','确认候选时间与选入位置');
 dialog.append(el('h3','确认候选时间与选入位置'),el('p',`字幕：${t.text}`),el('p',`候选：${candidate.name} · 源 ${candidate.start.toFixed(2)}–${candidate.end.toFixed(2)} 秒`));
 const label=el('label','选入位置'),select=el('select');select.id='sb-candidate-target';
 const ss=subtitleTaskShots(t);ss.forEach((s,i)=>{const o=el('option',`替换镜头${i+1}（现有源 ${s.start.toFixed(2)}–${s.end.toFixed(2)} 秒）`);o.value=String(i);select.append(o);});
 if(ss.length<2){const o=el('option',ss.length?'增加为镜头②（重新分配两镜时长）':'选入镜头①');o.value='append';select.append(o);}label.append(select);dialog.append(label);
 const summary=el('div');summary.id='sb-candidate-plan';dialog.append(summary);let plan=null;
 const confirm=subtitleButton('确认选入（仍需联播验收）',()=>{
  const live=board.candidates.find(c=>c.id===candidate.id);
  if(board.selected!==t.id||JSON.stringify({task:sbTask(),shots,context:sbContext(),candidate:live})!==original)throw Error('任务或候选已变化，请关闭后重新选择');
  if(!plan)throw Error('当前时间分配不可用');
  wfPause();shots.splice(0,shots.length,...plan.shots);Object.assign(t,plan.task);subtitleResetReplace();dialog.close();dialog.remove();subtitleRefresh();notice('已按确认的候选源时间选入，尚未确认本条；请配音联播验收。');
 });confirm.id='sb-candidate-commit';
 const cancel=subtitleButton('取消，不改变镜头',()=>{dialog.close();dialog.remove();});
 dialog.addEventListener('cancel',()=>dialog.remove());dialog.append(confirm,cancel);
 const update=()=>{summary.replaceChildren();try{plan=SubtitleBoardCore.candidatePlan(t,shots,candidate,select.value);const s=plan.shot;summary.append(el('p',`实际取源：${s.start.toFixed(2)}–${s.end.toFixed(2)} 秒`),el('p',`放入成片：${s.timeline_start.toFixed(2)}–${(s.timeline_start+s.end-s.start).toFixed(2)} 秒 · ${(s.end-s.start).toFixed(2)} 秒`));
  plan.shots.filter(s=>s.task_ids?.includes(t.id)).forEach((s,i)=>summary.append(el('p',`镜头${i+1}：${s.name}，源 ${s.start.toFixed(2)}–${s.end.toFixed(2)} 秒，成片 ${s.timeline_start.toFixed(2)}–${(s.timeline_start+s.end-s.start).toFixed(2)} 秒`,'small')));
  if(candidate.fallback)summary.append(el('p','此为替代画面，选入后仍须明确允许替代。','wf-pending'));confirm.disabled=false;
 }catch(e){plan=null;summary.append(el('p',e.message,'wf-pending'));confirm.disabled=true;}};
 select.onchange=update;document.body.append(dialog);update();dialog.showModal();
}
const candidateListBase=sbCandidates;
sbCandidates=function(){candidateListBase();if(board.mode!=='subtitle')return;const visible=board.candidates.filter(c=>c.task_id===board.selected).slice(0,3);$('sb-candidates').querySelectorAll('.sb-candidate').forEach((row,i)=>{const b=subtitleButton('选入本条',()=>subtitleCandidateDialog(visible[i]));b.classList.add('primary');const used=shots.some(s=>s.task_ids?.includes(board.selected)&&s.asset_id===visible[i].asset_id&&Math.abs(s.start-visible[i].start)<.001);row.prepend(el('p',used?'当前状态：已采用，验收状态见任务卡':'当前状态：未采用','hint'));row.append(b);});};
const globalIssues=el('details');globalIssues.id='sb-global-issues';const globalSummary=el('summary'),globalBody=el('div');globalIssues.append(globalSummary,globalBody);$('sb-status').after(globalIssues);
const candidateStatusBase=sbStatus;
sbStatus=function(){
 if(board.mode!=='subtitle'){globalIssues.hidden=true;candidateStatusBase();return;}globalIssues.hidden=false;
 const all=sbIssues(),t=sbTask(),local=t?subtitleTaskErrors(t):['请选择一条字幕'];
 if(board.context!==sbContext())local.unshift('字幕或配音有变化，请同步任务');
 const accepted=t&&t.accepted===subtitleTaskSignature(t);
 $('sb-status').textContent=t?`当前第${board.tasks.indexOf(t)+1}条「${t.text}」：`+(local.length?local.join('；'):accepted?'已确认':'已选镜头，待配音联播并确认'):'请选择一条字幕任务';
 globalSummary.textContent=`全片待处理问题（${all.length}项，含后段间隙）`;globalBody.replaceChildren(...all.map(x=>el('p',x,'small')));if(!all.length)globalBody.append(el('p','无未处理问题；完成连贯预览后确认全部选片。'));
 if(all.length||board.confirmed!==sbSignature())$('render-film').disabled=true;
};


// 未开始选片时，不展示可直接完成验收的按钮。
const readinessStatusBase=sbStatus;
sbStatus=function(){readinessStatusBase();const ready=board.tasks.length>0&&shots.length>0;$('sb-confirm').disabled=!ready;if(!board.tasks.length)$('sb-status').textContent='下一步：点击“按已保存字幕建立／同步任务”，然后逐条预览和选片。';else if(!shots.length)$('sb-status').textContent='任务已建立。请先为字幕选择镜头，再联播验收；当前没有采用镜头。';};

const rangeTools=el('div',undefined,'button-row');rangeTools.id='sb-preview-range-tools';
const rangeLabel=el('label','播放范围'),rangeSelect=el('select');rangeSelect.id='sb-preview-range';
for(const [value,label] of [['current','仅本条'],['previous','上一条＋本条'],['neighbors','本条及前后条']]){const option=el('option',label);option.value=value;rangeSelect.append(option);}
rangeLabel.append(rangeSelect);rangeTools.append(rangeLabel,subtitleButton('播放所选范围',()=>{const t=sbTask();if(!t)throw Error('请先选择一条字幕');return subtitlePlay(t,rangeSelect.value==='previous'?'previous':rangeSelect.value==='neighbors');}));
$('wf-preview-status').before(rangeTools);
const rangeRefreshBase=wfRefresh;wfRefresh=function(){rangeRefreshBase();rangeTools.hidden=wf.step!==4;};rangeTools.hidden=wf.step!==4;
// 第四步共用预览区：仅移动原有节点，保留打点、采用与来源引用。
const studioPreview=document.querySelector('.wf-preview'),filmPane=el('div');filmPane.id='sb-film-pane';
while(studioPreview.firstChild)filmPane.append(studioPreview.firstChild);
const previewTabs=el('div',undefined,'sb-preview-tabs');previewTabs.id='sb-preview-tabs';
const sourceTab=subtitleButton('候选原片',()=>studioPreviewMode('source')),filmTab=subtitleButton('成片联播',()=>studioPreviewMode('film'));
previewTabs.append(sourceTab,filmTab);studioPreview.append(previewTabs,$('sb-source'),filmPane);
let studioMode='source';
function studioPreviewMode(mode){
 wfPause();$('sb-player').pause();document.querySelectorAll('#sb-candidates video').forEach(v=>v.pause());studioMode=mode;studioUpdate();
}
function studioUpdate(){
 const active=wf.step===4;root.classList.toggle('sb-studio',active);previewTabs.hidden=!active;
 $('sb-source').hidden=!active||studioMode!=='source';filmPane.hidden=active&&studioMode!=='film';
 sourceTab.classList.toggle('primary',studioMode==='source');filmTab.classList.toggle('primary',studioMode==='film');
 const task=sbTask();$('sb-current-caption').textContent=task?`当前字幕：${task.text} · 需要 ${(task.end-task.start).toFixed(2)} 秒画面`:'先在左侧选择一条字幕';
}
const currentCaption=el('p',undefined,'hint');currentCaption.id='sb-current-caption';$('sb-player').after(currentCaption);
const studioSelectBase=sbSelect;sbSelect=async function(a){studioPreviewMode('source');return studioSelectBase(a);};
const studioPlayBase=subtitlePlay;subtitlePlay=async function(t,neighbors){studioPreviewMode('film');return studioPlayBase(t,neighbors);};
const studioStepBase=wfStep;wfStep=function(n){$('sb-player').pause();studioStepBase(n);studioUpdate();};
const studioRefreshBase=wfRefresh;wfRefresh=function(){studioRefreshBase();studioUpdate();};
const studioTools=el('details');studioTools.id='sb-tools';studioTools.append(el('summary','任务同步与全片检查'));
const workbench=$('sb-workbench');studioTools.append($('sb-build').parentElement,$('sb-global-issues'));workbench.prepend(studioTools);
workbench.querySelector(':scope > .hint')?.remove();
const progressSummary=el('p',undefined,'small');progressSummary.id='sb-progress-summary';studioTools.after(progressSummary);
const studioStatusBase=sbStatus;sbStatus=function(){studioStatusBase();progressSummary.textContent=`已确认 ${board.tasks.filter(t=>t.accepted===subtitleTaskSignature(t)).length}/${board.tasks.length} 条 · 选择字幕 → 查找素材 → 预览打点 → 采用 → 确认`;};
studioUpdate();
// 固定时长选段：只移动源片段起点，不把素材不足静默裁短。
function sbFixedLength(){
 const t=sbTask();if(!t)return 0;const ss=subtitleTaskShots(t);
 if(ss.length===0)return t.end-t.start;
 if(sbReplace!==null){const old=shots[sbReplace];if(!old?.task_ids?.includes(t.id))return 0;if(ss.length===1&&t.planned_shots!==2)return t.end-t.start;const slot=old.slot??ss.indexOf(old);return slot===0?t.split-t.start:t.end-t.split;}
 if(ss.length===1)return t.end-(Number.isFinite(t.split)?t.split:(t.start+t.end)/2);
 return 0;
}
function sbFixedUpdate(){
 const duration=sbFixedLength(),start=Number($('sb-in').value),end=start+duration;
 $('sb-out').value=Number.isFinite(end)?end.toFixed(3):'';
 const ready=sbAsset&&sbMeta&&duration>0&&Number.isFinite(start)&&start>=0&&end<=sbMeta.duration+.000001;
 $('sb-fixed-status').textContent=duration>0?`固定时长 ${duration.toFixed(3)} 秒 · 已选 ${duration.toFixed(3)} 秒`+(sbMeta&&end>sbMeta.duration?' · 原片剩余不足，请将开始位置往前移或更换素材':''):'请先选择字幕或明确要替换的镜头';
 for(const id of ['sb-adopt','sb-candidate','sb-audition'])$(id).disabled=!ready;
 $('sb-position').max=Math.max(0,(sbMeta?.duration||0)-duration);$('sb-position').value=Number.isFinite(start)?start:0;$('sb-position').disabled=!sbMeta||sbMeta.duration<duration;
}
$('sb-in').parentElement.firstChild.textContent='片段开始／秒';$('sb-out').parentElement.firstChild.textContent='片段结束／秒（自动）';$('sb-out').readOnly=true;
$('sb-mark-in').textContent='从播放位置开始';$('sb-mark-out').hidden=true;$('sb-audition').textContent='预览选段';$('sb-candidate').textContent='暂存候选';
const fixedStatus=el('p',undefined,'hint');fixedStatus.id='sb-fixed-status';const position=el('input');position.id='sb-position';position.type='range';position.min=0;position.step='.001';position.setAttribute('aria-label','移动固定时长片段');$('sb-in').closest('.form-grid').after(position,fixedStatus);
position.oninput=()=>{$('sb-in').value=Number(position.value).toFixed(3);sbFixedUpdate();};position.onchange=()=>{if(sbMeta)$('sb-player').currentTime=Number(position.value);};
$('sb-in').addEventListener('input',sbFixedUpdate);$('sb-in').addEventListener('change',()=>{if(sbMeta&&Number($('sb-in').value)>=0&&Number($('sb-in').value)<sbMeta.duration)$('sb-player').currentTime=Number($('sb-in').value);});
action('sb-mark-in',()=>{$('sb-in').value=$('sb-player').currentTime.toFixed(3);sbFixedUpdate();});
sbRange=function(){sbFixedUpdate();if(!sbAsset||!sbMeta)throw Error('请先打开原素材');const start=Number($('sb-in').value),length=sbFixedLength(),end=start+length;if(!Number.isFinite(start)||start<0||length<=0||end>sbMeta.duration+.000001)throw Error('素材剩余不足固定时长，请前移开始位置或更换素材');return {asset_id:sbAsset.id,name:sbAsset.name,rel:sbAsset.rel,root:sbAsset.root,path:sbAsset.source_path||sbAsset.rel,start,end,source_duration:sbMeta.duration,reason:$('sb-reason').value};};
const fixedSelectBase=sbSelect;sbSelect=async function(a){$('sb-proxy').hidden=true;await fixedSelectBase(a);sbFixedUpdate();};
const fixedRefreshBase=wfRefresh;wfRefresh=function(){fixedRefreshBase();sbFixedUpdate();};
const reasonDetails=el('details');reasonDetails.append(el('summary','用途／选择理由（选填）'));$('sb-reason').parentElement.before(reasonDetails);reasonDetails.append($('sb-reason').parentElement);
const sourceNote=$('sb-source').lastElementChild,help=el('details');help.append(el('summary','使用说明'));sourceNote.before(help);help.append(sourceNote);
$('sb-proxy').hidden=true;$('sb-player').onerror=()=>{$('sb-proxy').hidden=false;$('sb-source-info').textContent+=' · 当前格式无法直接播放，可生成本地兼容预览';};$('sb-player').addEventListener('loadeddata',()=>{$('sb-proxy').hidden=true;});
sbFixedUpdate();
// 浏览器 timeupdate 有间隔，停止后回到精确选段出点，避免停留在范围之外。
$('sb-player').ontimeupdate=()=>{if(sbStop!==null&&$('sb-player').currentTime>=sbStop){const end=sbStop;sbStop=null;$('sb-player').pause();$('sb-player').currentTime=end;}};

// 下一步只导航，不代用户确认；把真实缺项和处理入口放在导航旁。
const sbGatePanel=el('section',undefined,'hint');sbGatePanel.id='sb-next-check';sbGatePanel.setAttribute('aria-live','polite');
const sbGateList=el('div');sbGateList.id='sb-next-issues';
sbGatePanel.append(el('strong','进入配乐前检查'),sbGateList);
root.querySelector('.wf-navigation').before(sbGatePanel);
$('wf-next').before($('sb-confirm'));
$('sb-confirm').textContent='已联播检查，确认全片选片';
function sbNavigationIssues(){
 const issues=sbIssues().map(text=>({text,step:/确认配音/.test(text)?2:/确认字幕/.test(text)?3:4}));
 if(board.confirmed!==sbSignature())issues.push({text:'尚未确认全片选片：逐条确认和播放到片尾不会自动完成此项',step:4,confirm:true});
 return issues;
}
function sbNavigationRefresh(){
 const active=wf.step===4;sbGatePanel.hidden=!active;$('sb-confirm').hidden=!active;
 if(!active)return;
 const issues=board.enabled?sbNavigationIssues():[];
 sbGateList.replaceChildren();
 for(const issue of issues){
  const row=el('div',undefined,'button-row');row.append(el('span',issue.text));
  row.append(subtitleButton(issue.confirm?'定位全片确认':issue.step===2?'去第二步确认配音':issue.step===3?'去第三步核对字幕':'查看选片问题',()=>{
   if(issue.step!==4){wfStep(issue.step);$(issue.step===2?'wf-confirm-voice':'wf-confirm-subtitles').scrollIntoView({block:'center'});return;}
   const target=issue.confirm?$('sb-confirm'):$('sb-global-issues');
   if(!issue.confirm){for(let p=target;p;p=p.parentElement)if(p.tagName==='DETAILS')p.open=true;}
   target.scrollIntoView({block:'center'});target.focus();
  }));sbGateList.append(row);
 }
 if(!issues.length)sbGateList.append(el('p','检查通过，可以点击下一步进入配乐。'));
 $('sb-confirm').disabled=!board.tasks.length||!shots.length||sbIssues().length>0;
}
const sbNavigationRefreshBase=wfRefresh;wfRefresh=function(){sbNavigationRefreshBase();sbNavigationRefresh();};
const sbNavigationStepBase=wfStep;wfStep=function(n){
 if(n>4&&board.enabled&&sbNavigationIssues().length){
  sbNavigationStepBase(4);sbNavigationRefresh();sbGatePanel.scrollIntoView({block:'center'});
  notice(`还有 ${sbNavigationIssues().length} 项待处理，详见“进入配乐前检查”及对应处理按钮。`,true);return;
 }
 return sbNavigationStepBase(n);
};
sbNavigationRefresh();
