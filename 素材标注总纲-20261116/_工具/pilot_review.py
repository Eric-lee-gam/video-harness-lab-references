# -*- coding: utf-8 -*-
"""试标 50 段：合并云端标注、校验选项、跑一致性规则、出统计和审核网页。
只读写工作区的 试标50段 文件夹，全部新建文件。"""
import collections, csv, glob, html, json, os, sys

sys.dont_write_bytecode = True
D = r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116\试标50段"
C = collections.Counter

TYPES = {"V01": "人物对镜头", "V24": "人物在现场（不看镜头）", "V02": "握手/与客户沟通", "V03": "团队上门/搬料搬物",
         "V04": "量房/水电/安装", "V05": "施工·批刮覆盖", "V06": "施工·滚涂", "V07": "铲修旧墙/旧顶",
         "V08": "拆砸/贴砖（传统做法）", "V09": "铺保护膜/贴胶带", "V10": "保洁/清扫（施工前后）",
         "V11": "材料桶（取料/搅拌/桶特写）", "V23": "施工现场·其他", "V12": "旧房旧态", "V13": "成品空间（空镜）",
         "V14": "旧→新同镜转场", "V15": "成品里的人", "V16": "手摸/手指成品", "V17": "成品日常清洁",
         "V18": "演示·喷水冲洗", "V19": "演示·弯折样板/揭薄层", "V20": "演示·刮擦/擦污", "V21": "老楼/城市外景", "V22": "其他"}
OPT = {
    "空间": "卫生间 / 厨房 / 客厅餐厅 / 卧室 / 阳台 / 楼梯过道 / 入户门口 / 小区楼栋外 / 城市街景或地标 / 展厅 / 车旁或仓库 / 样板台 / 看不清",
    "阶段": "旧状（未动工） / 拆除铲除中 / 保护与基层处理 / 上料施工中 / 罩面收尾 / 完工空房 / 入住使用 / 非现场（演示、口播、外景） / 看不清",
    "人数": "0 / 1 / 2 / 3以上",
    "朝向": "对镜头 / 侧面或背面 / 看不见脸 / 无人",
    "主动作": "批刮 / 滚涂 / 刷涂 / 搅拌 / 倒料取料 / 打磨 / 铲除 / 拆砸 / 贴砖 / 铺膜贴胶带 / 安装 / 测量 / 清扫吸尘 / 握手 / 交谈讲解 / 指向示意 / 走入进门 / 搬运 / 挥手 / 转身 / 开门推门 / 手摸 / 拖地擦洗 / 喷水冲水 / 弯折 / 刮擦敲击 / 无动作 / 其他 / 看不清",
    "多画面": "是 / 否",
    "把握": "确定 / 不确定",
}
OPT = {k: [x.strip() for x in v.split("/")] for k, v in OPT.items()}

rows, bad = [], []
for p in sorted(glob.glob(os.path.join(D, "标注_云端_part*.jsonl"))):
    for n, line in enumerate(open(p, encoding="utf-8-sig"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception as e:
            bad.append(f"{os.path.basename(p)} 第{n}行不是合法 JSON: {e}")
            continue
        r["人数"] = str(r.get("人数", ""))
        rows.append(r)
rows.sort(key=lambda r: r.get("seg", ""))
print("合并行数:", len(rows), "；不同段数:", len({r.get("seg") for r in rows}))

for r in rows:
    code = r.get("画面类型代码")
    if code not in TYPES:
        bad.append(f"{r.get('seg')} 画面类型代码不在选项里: {code}")
    elif r.get("画面类型") != TYPES[code]:
        bad.append(f"{r.get('seg')} 类型文字和代码对不上: {code} / {r.get('画面类型')}")
    for k, opts in OPT.items():
        if r.get(k) not in opts:
            bad.append(f"{r.get('seg')} {k} 不在选项里: {r.get(k)}")
print("选项不合规:", len(bad))
for b in bad:
    print("  ", b)

# 一致性规则
viol = []
for r in rows:
    c, n, st = r.get("画面类型代码"), r.get("人数"), r.get("阶段")
    if c == "V05" and (r.get("主动作") != "批刮" or st != "上料施工中"):
        viol.append((r["seg"], "批刮覆盖：主动作应是批刮、阶段应是上料施工中", f"主动作={r.get('主动作')} 阶段={st}"))
    if c == "V13" and (n != "0" or st not in ("完工空房", "入住使用")):
        viol.append((r["seg"], "成品空间：人数应是 0、阶段应是完工空房或入住使用", f"人数={n} 阶段={st}"))
    if c == "V15" and (n == "0" or st not in ("完工空房", "入住使用")):
        viol.append((r["seg"], "成品里的人：人数至少 1、阶段应是完工空房或入住使用", f"人数={n} 阶段={st}"))
    if c == "V01" and (n == "0" or r.get("朝向") != "对镜头"):
        viol.append((r["seg"], "人物对镜头：人数至少 1、朝向应是对镜头", f"人数={n} 朝向={r.get('朝向')}"))
    if n == "0" and r.get("朝向") != "无人":
        viol.append((r["seg"], "人数是 0 时朝向应是无人", f"朝向={r.get('朝向')}"))
print("一致性规则不通过:", len(viol))
for v in viol:
    print("  ", v)

N = len(rows)
print("\n== 统计")
print("把握:", dict(C(r.get("把握") for r in rows)))
print("多画面:", dict(C(r.get("多画面") for r in rows)))
for k in ("空间", "阶段", "主动作"):
    c = C(r.get(k) for r in rows)
    print(f"{k} 选了看不清 {c.get('看不清', 0)}、其他 {c.get('其他', 0)}；分布:", dict(c.most_common()))
print("画面类型分布:", {f"{k} {TYPES.get(k, '')}": v for k, v in C(r.get("画面类型代码") for r in rows).most_common()})

# 抽样层（文件夹名线索） x 画面类型，只作参考，不是标准答案
layer = {}
for r in csv.DictReader(open(os.path.join(D, "_对应表.csv"), encoding="utf-8-sig")):
    layer[r["seg"]] = r["抽样层"]
cross = collections.defaultdict(C)
for r in rows:
    cross[layer.get(r["seg"], "?")][r.get("画面类型代码")] += 1
print("\n== 文件夹名线索 → 模型选的画面类型（文件夹名只是线索，不是标准答案）")
for k, c in cross.items():
    print(f"  {k}：" + "，".join(f"{TYPES.get(t, t)} {n}" for t, n in c.most_common()))

with open(os.path.join(D, "标注_云端.jsonl"), "x", encoding="utf-8") as fh:
    for r in rows:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
with open(os.path.join(D, "机器检查结果.json"), "x", encoding="utf-8") as fh:
    json.dump({"选项不合规": bad, "一致性规则不通过": [list(v) for v in viol]}, fh, ensure_ascii=False, indent=1)

# 审核网页
vmap = collections.defaultdict(list)
for seg, rule, got in viol:
    vmap[seg].append(f"{rule}（实际：{got}）")
data = [{**r, "规则提示": vmap.get(r["seg"], [])} for r in rows]
PAGE = r"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>试标 50 段审核页</title>
<style>
body{font-family:"Microsoft YaHei",sans-serif;margin:0;background:#f4f4f2;color:#222}
header{position:sticky;top:0;background:#fff;border-bottom:1px solid #ccc;padding:10px 20px;z-index:5}
header b{font-size:18px} #prog{margin-left:16px;color:#555}
button{font-size:15px;padding:6px 14px;margin-left:8px;cursor:pointer}
.intro{margin:14px 20px;padding:12px 16px;background:#fff;border:1px solid #ddd;line-height:1.7}
.card{display:flex;gap:18px;margin:14px 20px;padding:14px;background:#fff;border:1px solid #ddd}
.card.done{border-left:6px solid #3a8f4a} .card.bad{border-left:6px solid #c0392b}
.card img{width:400px;height:auto;border:1px solid #bbb;cursor:zoom-in;flex:none}
.info{flex:1;min-width:0} h3{margin:0 0 8px}
table{border-collapse:collapse;margin-bottom:8px} td{padding:3px 10px 3px 0;vertical-align:top}
td.k{color:#666;white-space:nowrap} .type{font-size:18px;font-weight:bold}
.warn{color:#b9770e;margin:4px 0} .unsure{color:#c0392b}
.rv{margin-top:8px;padding-top:8px;border-top:1px dashed #bbb;line-height:2.1}
select,input[type=text]{font-size:15px;padding:3px} input[type=text]{width:420px}
label{margin-right:14px;cursor:pointer}
</style></head><body>
<header><b>试标 50 段审核页</b><span id="prog"></span>
<button onclick="exportResult()">导出审核结果</button><button onclick="showPending()">只看没审的</button><button onclick="showAll()">全部显示</button></header>
<div class="intro">
每张图是同一段视频连续约 3 秒的 4 帧，顺序是左上、右上、左下、右下。点图可以放大。<br>
<b>怎么审：</b>先看“画面类型”对不对，点“对”或“错”。点“错”的话，从下拉里选出正确的类型，再选一个原因。其余几项（空间、阶段、人数、朝向、主动作）如果有错，勾出来就行。<br>
你的选择会自动存在这个浏览器里，中途关掉再打开不会丢。全部审完后点右上角“导出审核结果”，会下载一个文件 <b>审核结果.json</b>，把它发给我或放回这个文件夹即可。<br>
<b>通过的原因：</b>T1 典型（一眼就是这类）、T2 边界（算这类但勉强）、T3 优质（典型而且画面好，可当范例）。<br>
<b>不通过的原因：</b>F1 类型判错、F2 一段里有两种画面、F3 起止秒不对、F4 抽帧看不出、F5 定义说不清、F6 没有合适选项、F7 模型猜了看不见的东西、F8 漏了水印字幕或打码、F9 类型对但画面不能用。
</div>
<div id="list"></div>
<script>
const DATA = __DATA__;
const TYPES = __TYPES__;
const KEY = "pilot50_review_v1";
let st = JSON.parse(localStorage.getItem(KEY) || "{}");
const PASS = [["T1","T1 典型"],["T2","T2 边界"],["T3","T3 优质"]];
const FAIL = [["F1","F1 类型判错"],["F2","F2 一段里有两种画面"],["F3","F3 起止秒不对"],["F4","F4 抽帧看不出"],["F5","F5 定义说不清"],["F6","F6 没有合适选项"],["F7","F7 模型猜了看不见的"],["F8","F8 漏了水印字幕或打码"],["F9","F9 类型对但画面不能用"]];
const OTHER = ["空间","阶段","人数","朝向","主动作"];
function save(){localStorage.setItem(KEY, JSON.stringify(st)); prog();}
function prog(){const n=DATA.filter(d=>st[d.seg]&&st[d.seg].verdict).length; document.getElementById("prog").textContent="已审 "+n+" / "+DATA.length;}
function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));}
function opts(list, cur){return '<option value="">请选择</option>'+list.map(o=>'<option value="'+o[0]+'"'+(cur===o[0]?" selected":"")+'>'+esc(o[1])+'</option>').join("");}
function render(){
  const box=document.getElementById("list"); box.innerHTML="";
  DATA.forEach(d=>{
    const s=st[d.seg]||{}; const div=document.createElement("div");
    div.className="card"+(s.verdict==="对"?" done":s.verdict==="错"?" bad":""); div.id=d.seg;
    const typeOpts=Object.keys(TYPES).map(k=>[k,k+" "+TYPES[k]]).concat([["看不清","看不清，定不了"]]);
    div.innerHTML='<a href="frames/'+d.seg+'.jpg" target="_blank"><img loading="lazy" src="frames/'+d.seg+'.jpg"></a><div class="info">'+
      '<h3>'+d.seg+'</h3><table>'+
      '<tr><td class="k">画面类型</td><td class="type">'+esc(d["画面类型代码"])+' '+esc(d["画面类型"])+'</td></tr>'+
      '<tr><td class="k">空间</td><td>'+esc(d["空间"])+'</td></tr><tr><td class="k">阶段</td><td>'+esc(d["阶段"])+'</td></tr>'+
      '<tr><td class="k">人数 / 朝向</td><td>'+esc(d["人数"])+' / '+esc(d["朝向"])+'</td></tr>'+
      '<tr><td class="k">主动作</td><td>'+esc(d["主动作"])+'</td></tr><tr><td class="k">多画面</td><td>'+esc(d["多画面"])+'</td></tr>'+
      '<tr><td class="k">模型看见了什么</td><td>'+esc(d["看见了什么"])+'</td></tr>'+
      '<tr><td class="k">模型的把握</td><td class="'+(d["把握"]==="不确定"?"unsure":"")+'">'+esc(d["把握"])+'</td></tr></table>'+
      d["规则提示"].map(w=>'<div class="warn">自相矛盾：'+esc(w)+'</div>').join("")+
      '<div class="rv"><b>画面类型：</b>'+
      '<label><input type="radio" name="v_'+d.seg+'" value="对"'+(s.verdict==="对"?" checked":"")+'> 对</label>'+
      '<label><input type="radio" name="v_'+d.seg+'" value="错"'+(s.verdict==="错"?" checked":"")+'> 错</label>'+
      '<span class="fix" style="'+(s.verdict==="错"?"":"display:none")+'">应该是 <select data-f="fix">'+opts(typeOpts,s.fix)+'</select></span><br>'+
      '<b>原因：</b><select data-f="reason">'+opts(s.verdict==="错"?FAIL:s.verdict==="对"?PASS:PASS.concat(FAIL),s.reason)+'</select><br>'+
      '<b>其余项有错的：</b>'+OTHER.map(o=>'<label><input type="checkbox" data-o="'+o+'"'+((s.other||[]).includes(o)?" checked":"")+'> '+o+'</label>').join("")+'<br>'+
      '<b>备注：</b><input type="text" data-f="note" value="'+esc(s.note||"")+'" placeholder="可不填。比如正确的空间、为什么不能用"></div></div>';
    div.querySelectorAll('input[type=radio]').forEach(r=>r.onchange=()=>{st[d.seg]=Object.assign(st[d.seg]||{}, {verdict:r.value, reason:""}); if(r.value==="对") delete st[d.seg].fix; save(); render(); location.hash=d.seg;});
    div.querySelectorAll('select,input[type=text]').forEach(e=>e.onchange=()=>{st[d.seg]=Object.assign(st[d.seg]||{}, {[e.dataset.f]:e.value}); save();});
    div.querySelectorAll('input[type=checkbox]').forEach(c=>c.onchange=()=>{const cur=new Set((st[d.seg]||{}).other||[]); c.checked?cur.add(c.dataset.o):cur.delete(c.dataset.o); st[d.seg]=Object.assign(st[d.seg]||{}, {other:[...cur]}); save();});
    box.appendChild(div);
  });
  prog();
}
function showPending(){document.querySelectorAll(".card").forEach(c=>{c.style.display=(st[c.id]&&st[c.id].verdict)?"none":"flex";});}
function showAll(){document.querySelectorAll(".card").forEach(c=>c.style.display="flex");}
function exportResult(){
  const out=DATA.map(d=>Object.assign({seg:d.seg, 机器画面类型:d["画面类型代码"]}, st[d.seg]||{verdict:""}));
  const blob=new Blob([JSON.stringify({规则版本:"总纲v0.1/任务说明v0.1", 导出时间:new Date().toLocaleString(), 结果:out}, null, 1)], {type:"application/json"});
  const a=document.createElement("a"); a.href=URL.createObjectURL(blob); a.download="审核结果.json"; a.click();
}
render();
</script></body></html>"""
page = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("__TYPES__", json.dumps(TYPES, ensure_ascii=False))
with open(os.path.join(D, "审核页.html"), "x", encoding="utf-8") as fh:
    fh.write(page)
print("\n已生成:", os.path.join(D, "审核页.html"))
