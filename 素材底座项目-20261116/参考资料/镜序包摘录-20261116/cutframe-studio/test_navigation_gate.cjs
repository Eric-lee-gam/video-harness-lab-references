const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync(__dirname+'/static/subtitle-board.js','utf8').split('// 下一步只导航，不代用户确认；')[1].split('\n').slice(1).join('\n');
function element(){return {children:[],append(...x){this.children.push(...x)},replaceChildren(...x){this.children=x},before(){},setAttribute(){},scrollIntoView(){this.scrolled=true},focus(){this.focused=true}};}
const nodes={};let problems=['请先确认配音'];
const context={el:element,$:id=>nodes[id]??=element(),root:{querySelector:element},wf:{step:4},board:{enabled:true,tasks:[{}],confirmed:null},shots:[{}],sbIssues:()=>problems,sbSignature:()=> 'signature',subtitleButton:(text,fn)=>({text,onclick:fn}),wfRefresh(){},wfStep(n){context.wf.step=n},notice(){}};
vm.createContext(context);vm.runInContext(source,context);
context.wfStep(5);assert.equal(context.wf.step,4);assert.equal(context.board.confirmed,null);assert.equal(nodes['sb-confirm'].disabled,true);
let rows=nodes['sb-next-issues']; // 新节点通过 el 创建，使用函数返回的结构验证缺项路由。
assert.equal(context.sbNavigationIssues()[0].step,2);
problems=['请先保存并确认字幕'];assert.equal(context.sbNavigationIssues()[0].step,3);
problems=['文案、配音或字幕已变化，请同步任务'];assert.equal(context.sbNavigationIssues()[0].step,4);
problems=[];context.sbNavigationRefresh();assert.equal(nodes['sb-confirm'].disabled,false);
context.wfStep(5);assert.equal(context.wf.step,4);assert.equal(context.board.confirmed,null);
context.board.confirmed='signature';context.wfStep(5);assert.equal(context.wf.step,5);
problems=['请先确认配音'];context.wfStep(5);assert.equal(context.wf.step,4);
console.log('导航缺项、路由、未确认拦截、确认后放行及再次失效检查通过；不写入真实工程');
