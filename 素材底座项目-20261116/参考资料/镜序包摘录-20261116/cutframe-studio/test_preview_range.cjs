const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/static/workflow.js','utf8');
const finish=source.slice(source.indexOf('async function wfFinishRange'),source.indexOf("action('wf-play',"));
const playback=source.slice(source.indexOf("action('wf-play',"),source.indexOf("$('wf-seek').oninput"));
(async()=>{
 for(const end of [.78,1.84,5.2,6.9]){
  let handler,tick;const nodes={'wf-voice':{paused:false,currentTime:end+.03},'voice-offset':{value:0},'wf-play':{},'wf-preview-status':{}};
  const rendered=[];const wf={time:0,playing:false,shotIndex:0,playRange:{start:0,end}};
  const ctx={wf,imports:{voice:'test'},board:{mode:'subtitle'},$:id=>nodes[id],performance:{now:()=>0},action:(_,fn)=>handler=fn,wfResources:async()=>{},wfDuration:()=>25.38,wfPause:()=>{wf.playing=false;nodes['wf-voice'].paused=true;},wfCaption:()=>{},wfVisual:async seek=>{rendered.push(wf.time);if(seek)nodes['wf-voice'].currentTime=wf.time;},requestAnimationFrame:fn=>{tick=fn;return 1;}};
  vm.createContext(ctx);vm.runInContext(finish+playback,ctx);await handler();await tick();
  assert.equal(wf.playing,false);assert.equal(wf.playRange,null);assert.equal(wf.time,end-.000001);assert.ok(rendered.every(t=>t<end));assert.equal(nodes['wf-voice'].currentTime,wf.time);
 }
 console.log('四个真实字幕终点：越界时钟被截住，未渲染下一条，声音暂停并回定位通过');
})().catch(e=>{console.error(e);process.exitCode=1;});
