
const $=id=>document.getElementById(id),videos=[];
function node(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
fetch('/api/projects/fdfe11a3fdf7462e970c9717cae45d75').then(r=>{if(!r.ok)throw Error('工程读取失败');return r.json();}).then(p=>{
 const board=p.workflow.storyboard;let count=0;const absent=[],counts={newcards:0,cards:0,duplicates:0,rejected:0};
 const same=(a,b)=>Boolean(a.asset_id&&a.asset_id===b.asset_id)||Boolean(a.path&&b.path&&a.path.replaceAll('\\','/').toLowerCase()===b.path.replaceAll('\\','/').toLowerCase());
 const taskNumber=id=>board.tasks.findIndex(t=>t.id===id)+1;
 const usedDuplicates=[];
 p.shots.forEach((s,i)=>p.shots.slice(0,i).forEach(other=>{if(same(s,other))usedDuplicates.push('已采用第'+other.task_ids.map(taskNumber).join('/')+'、'+s.task_ids.map(taskNumber).join('/')+'条同源：'+s.name+'（保留原采用决定，待复核是否接受重复场景）');}));
 $('audit').textContent='同源核查：'+usedDuplicates.join('；')+'。不同文件仍可能拍到相同场景，此检查不能保证视觉完全不重复。';
 board.tasks.slice(4).forEach((t,j)=>{
  const index=j+5,cs=board.candidates.filter(c=>c.task_id===t.id);
  if(!p.shots.some(s=>s.task_ids?.includes(t.id))&&!cs.some(c=>c.rating!=='不合适'&&!p.shots.some(s=>same(c,s)&&!s.task_ids?.includes(t.id)))){absent.push('第'+index+'条「'+t.text+'」');}
  cs.forEach((c,k)=>{
   count++;const label=index+'-'+String.fromCharCode(65+k),card=node('article');card.id='candidate-'+label;
   card.append(node('span',c.fallback?'替代画面 · 待你确认':'内容相关 · 待验收','badge'+(c.fallback?' fallback':'')),node('h2',label+' ｜ '+t.text),node('p','字幕 '+t.start.toFixed(2)+'–'+t.end.toFixed(2)+'秒；选段 '+c.start.toFixed(2)+'–'+c.end.toFixed(2)+'秒','small'));
   const v=node('video');v.controls=true;v.muted=true;v.playsInline=true;v.preload='metadata';v.src='/media/'+c.asset_id+'#t='+c.start+','+c.end;videos.push(v);
   const adopted=p.shots.some(s=>s.task_ids?.includes(t.id)&&s.asset_id===c.asset_id&&Math.abs(s.start-c.start)<.001);const decision=adopted?'已采用 · 待联播验收':c.rating==='不合适'?'已拒绝 · 不采用':'待你决定 · 未采用';card.append(node('p',decision,'badge'));
   const conflicts=p.shots.filter(s=>same(c,s)&&!s.task_ids?.includes(t.id));
   const target=c.rating==='不合适'?'rejected':!adopted&&conflicts.length?'duplicates':c.review_batch==='补找第三轮'?'newcards':'cards';counts[target]++;
   if(conflicts.length)card.append(node('p','同源提醒：与已采用第'+[...new Set(conflicts.flatMap(s=>s.task_ids.map(taskNumber)))].join('、')+'条使用同一源文件。取段不同也可能重复场景。','error'));
   const repeated=board.tasks.slice(4).flatMap((other,j)=>board.candidates.filter(x=>x.task_id===other.id).map((x,k)=>({x,label:(j+5)+'-'+String.fromCharCode(65+k)}))).filter(o=>o.x!==c&&same(c,o.x));
   if(repeated.length)card.append(node('p','同源候选：'+repeated.map(o=>o.label+(o.x.rating==='不合适'?'（已拒绝）':'')).join('、'),'small'));
   if(target==='rejected')v.preload='none';const status=node('p','未播放','small');let bounded=false,frame=null;
   function pauseOthers(){videos.forEach(x=>{if(x!==v)x.pause();});}
   function stopAtEnd(){if(bounded&&v.currentTime>=c.end){v.pause();bounded=false;status.textContent='选段已播放结束 · 等待你决定';}if(bounded&&!v.paused)frame=requestAnimationFrame(stopAtEnd);}
   v.onplay=()=>{pauseOthers();};v.onerror=()=>{status.className='error';status.textContent='原片无法播放，请回工作台生成本地兼容预览；不要据此判断素材内容';};
   const play=node('button','播放选段 '+label);play.onclick=async()=>{pauseOthers();cancelAnimationFrame(frame);bounded=true;v.currentTime=c.start;try{await v.play();status.textContent='播放中 · '+label;stopAtEnd();}catch(e){status.textContent='无法播放：'+e.message;}};
   card.append(v,play,status,node('p',t.note||'','hint'),node('p',c.reason||'','small'),node('p',c.name+'｜'+c.rel,'small'));$(target).append(card);
  });
 });
 $('state').textContent='已加载 '+count+' 段：本轮新增 '+counts.newcards+' 段，旧候选及已采用 '+counts.cards+' 段，重复待处理 '+counts.duplicates+' 段，已拒绝 '+counts.rejected+' 段（默认折叠）。请回复编号，例如“6-B采用，10-B允许替代，14-A采用”。采用和拒绝状态见各卡片；此页不会修改工程。';
 $('missing').textContent='仍缺准确候选：'+absent.join('、')+'。这些条目未用无关画面填充。';
}).catch(e=>{$('state').className='error';$('state').textContent=e.message;});


