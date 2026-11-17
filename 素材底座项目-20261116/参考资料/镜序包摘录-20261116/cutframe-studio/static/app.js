'use strict';
// 局域网 HTTP 不提供 randomUUID；getRandomValues 仍可生成安全随机字节。
(function(root){
 const crypto=root.crypto;
 if(typeof crypto?.randomUUID==='function')return;
 if(typeof crypto?.getRandomValues!=='function')return;
 crypto.randomUUID=function(){
  const bytes=crypto.getRandomValues(new Uint8Array(16));
  bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const h=Array.from(bytes,b=>b.toString(16).padStart(2,'0')).join('');
  return `${h.slice(0,8)}-${h.slice(8,12)}-${h.slice(12,16)}-${h.slice(16,20)}-${h.slice(20)}`;
 };
})(globalThis);

const $=id=>document.getElementById(id), token=document.querySelector('meta[name="local-token"]').content;
let page=1,total=0,current=null,meta=null,jobId=null,rangeEnd=null,projectId=null;
const shots=[], imports={};
function el(tag,text,cls){const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function notice(msg,error=false){$('notice').textContent=msg;$('notice').className=error?'error':'';$('notice').style.display='block';clearTimeout(notice.timer);notice.timer=setTimeout(()=>$('notice').style.display='none',error?16000:7000);}
async function api(url,body){const opts=body===undefined?{}:{method:'POST',headers:{'X-Local-Token':token},body:body instanceof FormData?body:JSON.stringify(body)};if(body!==undefined&&!(body instanceof FormData))opts.headers['Content-Type']='application/json';const r=await fetch(url,opts);const d=await r.json();if(!r.ok)throw Error(d.error||r.statusText);return d;}
function action(id,fn){$(id).onclick=async()=>{try{await fn();}catch(e){notice(e.message,true);}};}
async function state(){const s=await api('/api/state');if(!$('root').options.length){for(const [key,r]of Object.entries(s.roots).sort((a,b)=>['xiaoq','baba','chengdu','suzhou'].indexOf(a[0])-['xiaoq','baba','chengdu','suzhou'].indexOf(b[0]))){const o=el('option',r.label);o.value=key;$('root').append(o);}}const old=$('category').value;$('category').replaceChildren(...s.categories.map(c=>el('option',c)));if(s.categories.includes(old))$('category').value=old;$('output').textContent=s.output;if(s.scan.running)$('inventory').textContent=`索引更新中 · 已发现 ${s.scan.count} 个文件`;return s;}
async function load(){const d=await api(`/api/assets?root=${encodeURIComponent($('root').value)}&q=${encodeURIComponent($('search').value)}&page=${page}`);total=d.total;$('page').textContent=`${page} / ${Math.max(1,Math.ceil(total/60))}`;$('inventory').textContent=`${total.toLocaleString()} 个文件 · 每页 60 个`;$('prev').disabled=page<=1;$('next').disabled=page*60>=total;$('assets').replaceChildren();for(const a of d.items){const b=el('button',undefined,'asset'+(current?.id===a.id?' selected':''));b.append(el('span',a.name.split('.').pop().toUpperCase(),'file-icon'),el('strong',a.name),el('small',`${(a.size/1048576).toFixed(1)} MB${a.size===0?' · 零字节':''}`),el('small',a.rel.split('/').slice(0,-1).join(' / ')));b.onclick=()=>select(a).catch(e=>notice(e.message,true));$('assets').append(b);}}
async function select(a){current=null;meta=null;$('player').pause();$('player').removeAttribute('src');$('empty').hidden=false;$('filename').textContent='读取素材信息…';const d=await api('/api/assets/'+a.id);current=d.asset;meta=d.meta;$('filename').textContent=current.name;$('codec').textContent=meta.codec||'未知编码';$('meta').textContent=`${meta.width} × ${meta.height} · ${meta.duration.toFixed(3)} 秒 · ${meta.audio_codec||'无音轨'}${['arib-std-b67','smpte2084'].includes(meta.transfer)?' · HDR':''}`;$('sourcepath').textContent=current.rel;$('empty').hidden=true;$('player').src='/media/'+current.id;$('start').value=0;$('end').value=Math.min(10,meta.duration).toFixed(3);updateRange();await api('/api/events',{action:'view',asset_id:current.id});await load();}
function range(){if(!current||!meta)throw Error('请先选择可读取的视频');const start=Number($('start').value),end=Number($('end').value);if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start||end>meta.duration+.02)throw Error('请检查入点、出点和素材时长');return {asset_id:current.id,start,end};}
function updateRange(){if(!meta)return;const start=Number($('start').value),end=Number($('end').value);$('selection-duration').textContent=`选中 ${Math.max(0,end-start).toFixed(3)} 秒`;$('range-fill').style.marginLeft=`${Math.max(0,start/meta.duration*100)}%`;$('range-fill').style.width=`${Math.max(0,(end-start)/meta.duration*100)}%`;}
async function mark(which){if(!current)throw Error('请先选择视频');$(which).value=$('player').currentTime.toFixed(3);updateRange();await api('/api/events',{action:'mark',asset_id:current.id,start:Number($('start').value),end:Number($('end').value)});}
async function watch(jid,callback){jobId=jid;$('job-panel').hidden=false;while(jobId===jid){const j=await api('/api/jobs/'+jid);$('job-title').textContent=j.kind;$('job-message').textContent=j.message;$('progress').value=j.progress;if(['done','failed','cancelled','interrupted'].includes(j.status)){jobId=null;$('cancel-job').hidden=true;if(j.status==='done'){notice('任务完成');if(callback)await callback(j.result);}else notice(j.message,true);return j;} $('cancel-job').hidden=false;await new Promise(r=>setTimeout(r,1000));}}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{document.querySelectorAll('.view,.tab').forEach(n=>n.classList.remove('active'));$(b.dataset.view).classList.add('active');b.classList.add('active');if(b.dataset.view==='exports')loadExports().catch(e=>notice(e.message,true));if(b.dataset.view==='compose')loadProjects().catch(e=>notice(e.message,true));});
action('refresh',async()=>{await api('/api/scan',{});notice('后台刷新索引，已缓存文件仍可浏览');});
$('root').onchange=()=>{page=1;load().catch(e=>notice(e.message,true));};let timer;$('search').oninput=()=>{clearTimeout(timer);timer=setTimeout(()=>{page=1;load().catch(e=>notice(e.message,true));},300);};
action('prev',async()=>{page--;await load();});action('next',async()=>{page++;await load();});
action('mark-in',()=>mark('start'));action('mark-out',()=>mark('end'));['start','end'].forEach(id=>$(id).oninput=updateRange);
document.onkeydown=e=>{if(/INPUT|TEXTAREA|SELECT/.test(e.target.tagName)||!$('cut').classList.contains('active'))return;if(e.key.toLowerCase()==='i')mark('start').catch(e=>notice(e.message,true));if(e.key.toLowerCase()==='o')mark('end').catch(e=>notice(e.message,true));};
action('play-range',async()=>{const r=range();rangeEnd=r.end;$('player').currentTime=r.start;await $('player').play();});$('player').ontimeupdate=()=>{if(rangeEnd!==null&&$('player').currentTime>=rangeEnd){$('player').pause();rangeEnd=null;}};
$('player').onerror=()=>notice('浏览器无法播放该素材。可以点击「生成兼容预览」，源文件不变。',true);
action('proxy',async()=>{if(!current)throw Error('请先选择视频');const aid=current.id;const r=await api('/api/proxy/'+aid,{});const use=d=>{if(current?.id===aid){$('player').src=d.url;$('codec').textContent='本地兼容预览';}};if(r.url)use(r);else await watch(r.job_id,use);});
$('mode').onchange=()=>{$('mode-hint').textContent=$('mode').value==='copy'?'无损切点受关键帧限制，实际边界可能偏移。失败会停止，不自动转码。':'重新编码以获得更准确的切点；速度较慢，并有重新压缩损失。HDR 将转为 SDR。';};
action('add-category',()=>{$('category-editor').hidden=false;$('category-name').focus();});
action('cancel-category',()=>{$('category-editor').hidden=true;});
action('save-category',async()=>{const name=$('category-name').value.trim();if(!name)throw Error('请输入分类名称');await api('/api/categories',{name});await state();$('category').value=name;$('category-editor').hidden=true;$('category-name').value='';notice('分类已保存，不移动既有片段');});
action('export',async()=>{const d={...range(),mode:$('mode').value,category:$('category').value,tags:$('tags').value.split(/[,，]/).map(s=>s.trim()).filter(Boolean),purpose:$('purpose').value,rating:$('rating').value,reason:$('reason').value};const r=await api('/api/clip',d);await watch(r.job_id,result=>{$('job-message').textContent=result.path+'\n'+result.warning;});});
action('cancel-job',async()=>{if(jobId)await api('/api/jobs/'+jobId+'/cancel',{});});
action('add-shot',async()=>{shots.push({...range(),name:current.name});renderShots();notice('已加入单条成片，可切换到「02 单条成片」排列');});
function renderShots(){$('shots').replaceChildren();shots.forEach((s,i)=>{const card=el('div',undefined,'shot'),head=el('div',undefined,'shot-name');head.append(el('strong',`${String(i+1).padStart(2,'0')}  ${s.name}`));const buttons=el('div',undefined,'shot-actions');for(const [label,fn]of [['↑',()=>{if(i>0)[shots[i-1],shots[i]]=[shots[i],shots[i-1]];}],['↓',()=>{if(i<shots.length-1)[shots[i+1],shots[i]]=[shots[i],shots[i+1]];}],['×',()=>shots.splice(i,1)]]){const b=el('button',label);b.onclick=()=>{fn();renderShots();};buttons.append(b);}head.append(buttons);card.append(head);const times=el('div',undefined,'shot-times');for(const [key,label]of [['start','入点 / 秒'],['end','出点 / 秒']]){const l=el('label',label),input=el('input');input.type='number';input.step='.001';input.min='0';input.value=s[key];input.onchange=()=>{s[key]=Number(input.value);updateFilmDuration();};l.append(input);times.append(l);}card.append(times);$('shots').append(card);});updateFilmDuration();}
function updateFilmDuration(){$('film-duration').textContent=shots.reduce((n,s)=>n+s.end-s.start,0).toFixed(3)+' 秒';}
for(const kind of ['voice','music','subtitle'])$(kind).onchange=async()=>{try{const file=$(kind).files[0];if(!file)return;const form=new FormData();form.append('kind',kind);form.append('file',file);const r=await api('/api/imports',form);imports[kind]=r.id;$(kind+'-info').textContent=r.name+(r.meta?.duration?' · '+r.meta.duration.toFixed(2)+' 秒':'');}catch(e){notice(e.message,true);}};
function project(){return {id:projectId,name:$('project-name').value,shots,imports,settings:{canvas:$('canvas').value,fps:Number($('fps').value),fit:$('fit').value,source_audio:$('source-audio').value,voice_offset:Number($('voice-offset').value),music_start:Number($('music-start').value),music_volume:Number($('music-volume').value)/100,subtitle_offset:Number($('subtitle-offset').value),font_size:Number($('font-size').value),subtitle_bottom:Number($('subtitle-bottom').value)}};}
async function loadProjects(){const d=await api('/api/projects');$('project-list').replaceChildren(el('option','选择工程'));$('project-list').firstChild.value='';for(const p of d.items){const o=el('option',p.name);o.value=p.id;$('project-list').append(o);}}
action('save-project',async()=>{const d=await api('/api/projects',project());projectId=d.id;await loadProjects();$('project-list').value=d.id;notice('工程已保存到本地');});
action('load-project',async()=>{const id=$('project-list').value;if(!id)throw Error('请选择工程');const d=await api('/api/projects/'+id);projectId=d.id;$('project-name').value=d.name;shots.splice(0,shots.length,...d.shots);Object.keys(imports).forEach(k=>delete imports[k]);Object.assign(imports,d.imports);const map={canvas:'canvas',fps:'fps',fit:'fit',source_audio:'source-audio',voice_offset:'voice-offset',music_start:'music-start',music_volume:'music-volume',subtitle_offset:'subtitle-offset',font_size:'font-size',subtitle_bottom:'subtitle-bottom'};for(const [k,id]of Object.entries(map))if(d.settings[k]!==undefined)$(id).value=k==='music_volume'?d.settings[k]*100:d.settings[k];for(const k of ['voice','subtitle','music'])$(k+'-info').textContent=d.import_names?.[k]||'未导入';renderShots();notice('工程已恢复');});
action('render-film',async()=>{if(!shots.length)throw Error('请先添加镜头');const d=await api('/api/render',project());projectId=d.project_id;await watch(d.job_id,result=>{const box=$('film-result');box.replaceChildren(el('h2','完整成片验证'),el('p',result.path,'small'));const v=el('video');v.controls=true;v.src=result.url;box.append(v);box.scrollIntoView({behavior:'smooth'});});});
async function loadExports(){
  const d=await api('/api/clips');$('export-list').replaceChildren();
  for(const c of d.items){
    const m=JSON.parse(c.data),card=el('div',undefined,'export-card');
    card.append(el('strong',c.path),el('p',`${m.mode==='copy'?'无损切割':'精确转码'} · ${m.requested_start}–${m.requested_end} 秒 · ${m.category} · ${m.rating}`,'small'));
    const details=el('details');details.append(el('summary','查看分类、评价与来源追溯'));
    const fields=[['标签',(m.tags||[]).join('、')||'未填写'],['用途 / 对应文案',m.purpose||'未填写'],['人工评价',m.rating||'未评价'],['评价原因',m.reason||'未填写'],['来源素材库',({xiaoq:'拍摄 · 小区',baba:'扒扒 · 分类素材',chengdu:'参考成片 · 成都',suzhou:'参考成片 · 苏州'})[m.root_alias]||m.root_alias],['源文件相对路径',m.relative_path],['请求入出点',`${m.requested_start}–${m.requested_end} 秒`],['输出时长',`${m.output_meta?.duration??'未知'} 秒`],['切点核验状态',m.actual_source_boundaries?JSON.stringify(m.actual_source_boundaries):'未逐帧核验；请求时间不等于已验证的实际源帧边界'],['片段编号',m.clip_id],['来源素材编号',m.asset_id],['源文件大小',`${m.source_size} 字节`],['导出时间',m.created?new Date(m.created).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false})+'（北京时间）':'未记录'],['发布状态',m.publication_status==='published'?'已发布':m.publication_status]];
    for(const [label,value] of fields){const row=el('p');row.append(el('b',label+'：'),document.createTextNode(String(value??'未记录')));details.append(row);}
    const back=el('button','回到原素材及本次选段');
    back.onclick=async()=>{try{
      $('root').value=m.root_alias;$('search').value=m.relative_path.split(/[\\/]/).pop();page=1;
      document.querySelector('[data-view="cut"]').click();
      await select({id:m.asset_id});$('start').value=m.requested_start;$('end').value=m.requested_end;updateRange();
      notice('已定位源素材与本次入出点；可点击「试听选段」核对。');
    }catch(e){notice('无法定位原素材：'+e.message,true);}};
    details.append(back);card.append(details);$('export-list').append(card);
  }
  if(!d.items.length)$('export-list').append(el('p','尚无导出记录','small'));
}
(async()=>{try{const s=await state();await load();const active=s.jobs.find(j=>['queued','running'].includes(j.status));if(active)watch(active.id).catch(e=>notice(e.message,true));}catch(e){notice(e.message,true);}})();
setInterval(()=>state().catch(()=>{}),7000);

let ttsSelection=null;
const ttsItems=new Map();
const speedPanel=document.createElement('div');speedPanel.id='tts-speed-panel';speedPanel.innerHTML='<label>配音语速（倍）<input id="tts-speed" type="number" min="0.5" max="2" step="0.05" value="1"></label><button id="tts-speed-apply">生成此语速试听</button><p class="small">0.5—2.0倍，默认1倍。生成后试听，再用作工程配音；字幕须按新音频重新生成，分镜须重新核对。原版保留。</p>';$('tts-player').after(speedPanel);
function ttsSpeedDirty(){return ttsSelection&&Math.abs(Number($('tts-speed').value)-(ttsSelection.speed||1))>.000001;}
$('tts-speed').oninput=()=>{$('tts-use').disabled=!ttsSelection||ttsSpeedDirty()||!$('tts-speed').checkValidity();if(ttsSpeedDirty())$('tts-status').textContent='语速尚未应用，播放器仍是上一版本；请点击“生成此语速试听”。';};
action('tts-speed-apply',async()=>{if(jobId)throw Error('请等待当前任务完成');if(!ttsSelection)throw Error('请先生成或选择配音');if(!$('tts-speed').checkValidity())throw Error('语速范围为0.5—2.0倍');const speed=Number($('tts-speed').value);$('tts-speed-apply').disabled=true;try{const r=await api('/api/tts/speed',{voice_id:ttsSelection.id,speed});const j=await watch(r.job_id,async result=>{await loadTts(result.id);});if(j.status!=='done')throw Error(j.message||'变速失败');}finally{$('tts-speed-apply').disabled=false;}});

async function loadTts(selected){
 const data=await api('/api/tts');ttsItems.clear();$('tts-history').replaceChildren(el('option','选择试听记录'));$('tts-history').firstChild.value='';
 for(const item of data.items){ttsItems.set(item.id,item);const o=el('option',item.name+' · '+item.duration.toFixed(2)+' 秒');o.value=item.id;$('tts-history').append(o);}
 if(selected&&ttsItems.has(selected)){$('tts-history').value=selected;selectTts(selected);}
}
function selectTts(id){ttsSelection=ttsItems.get(id)||null;$('tts-use').disabled=!ttsSelection;$('tts-player').pause();if(ttsSelection){$('tts-speed').value=ttsSelection.speed||1;$('tts-player').playbackRate=1;$('tts-player').src=ttsSelection.url;$('tts-player').hidden=false;$('tts-text').value=ttsSelection.text;$('tts-status').textContent='请完整试听，确认后用作本工程配音。';}else{$('tts-player').removeAttribute('src');$('tts-player').hidden=true;}}
$('tts-history').onchange=()=>selectTts($('tts-history').value);
action('tts-generate',async()=>{
 if(jobId)throw Error('请先等待当前任务结束');
 $('tts-generate').disabled=true;$('tts-status').textContent='准备生成…';
 try{const result=await api('/api/tts',{text:$('tts-text').value,name:$('project-name').value||'武汉翻新'});const job=await watch(result.job_id,async r=>{await loadTts(r.id);});if(job.status!=='done')$('tts-status').textContent=job.message;}
 catch(e){$('tts-status').textContent=e.message;throw e;}finally{$('tts-generate').disabled=false;}
});
action('tts-use',()=>{if(!ttsSelection)throw Error('请先选择配音');if(ttsSpeedDirty()||!$('tts-speed').checkValidity())throw Error('请先生成当前语速的试听版本');const changed=imports.voice!==ttsSelection.id;imports.voice=ttsSelection.id;if(changed)delete imports.subtitle;$('voice-info').textContent=ttsSelection.name+' · '+ttsSelection.duration.toFixed(2)+' 秒';$('tts-status').textContent='已用作本工程配音，请保存工程。';notice('已采用试听音频，成片使用同一语速。请按新配音生成字幕并核对分镜');});
loadTts().catch(e=>notice(e.message,true));
