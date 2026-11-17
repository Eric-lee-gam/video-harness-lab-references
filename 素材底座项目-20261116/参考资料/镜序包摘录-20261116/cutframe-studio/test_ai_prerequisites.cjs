const vm=require('vm'),fs=require('fs'),assert=require('assert');
const nodes={},handlers={},requests=[];const node=()=>({children:[],append(...x){this.children.push(...x)},before(){},replaceChildren(...x){this.children=x},focus(){this.focused=true},scrollIntoView(){this.scrolled=true}});
const ctx={el:node,$:id=>nodes[id]??=node(),aiPanel:node(),projectId:'',board:{context:'c',tasks:[]},wf:{cues:[{text:'句'}],dirtySubtitle:false},imports:{subtitle:'s'},shots:[],jobId:null,sbContext:()=> 'c',localStorage:{setItem(){},getItem(){return null}},action:(id,fn)=>handlers[id]=fn,subtitleButton:node,wfOpen:async()=>{},wfStep:n=>ctx.step=n,setInterval(){},sbTask:()=>null,api:async(u,r)=>{requests.push(r);return {job_id:'j'}},watch:async()=>({status:'done',result:{items:[],run_id:'r'}})};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/static/ai-batch.js','utf8'),ctx);
(async()=>{
assert.equal(ctx.aiBatchMissing().length,2);await handlers['ai-batch-start']();assert.equal(requests.length,0);
ctx.aiBatchMissing()[0].run();assert.equal(ctx.step,1);assert(nodes['project-name'].focused);
ctx.projectId='p';ctx.wf.dirtySubtitle=true;assert.match(ctx.aiBatchMissing()[0].text,/字幕尚未保存/);ctx.aiBatchMissing()[0].run();assert.equal(ctx.step,3);
ctx.wf.dirtySubtitle=false;nodes['sb-build']={onclick:async()=>{ctx.board.tasks=[{id:'t',text:'句',start:0,end:1}]}};await ctx.aiBatchMissing()[0].run();assert.equal(ctx.aiBatchMissing().length,0);
ctx.board.context='old';await handlers['ai-batch-start']();assert.equal(requests.length,0);assert.match(ctx.aiBatchMissing()[0].button,/同步/);ctx.board.context='c';await handlers['ai-batch-start']();assert.equal(requests.length,1);assert.equal(ctx.shots.length,0);
console.log('缺工程/缺任务/未保存字幕/过期任务拦截、跳转、手动建立后可检索、不自动采用：通过');
})().catch(e=>{console.error(e);process.exitCode=1});
