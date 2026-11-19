# -*- coding: utf-8 -*-
"""78 个素材类别的条件（另附防滑 0 条说明）。"""
from t07_common import (
    item, vcode, COMMON_MUST, COMMON_FORBID,
    ACTION_NOTE_PI, ACTION_NOTE_ROLL, ACTION_NOTE_FETCH,
    WATERPROOF_SRC, ABRASION_OK, ABRASION_BAN,
)

def bm(extra):
    return list(COMMON_MUST) + list(extra)

def bf(extra=None):
    return list(COMMON_FORBID) + list(extra or [])

CATS = {}

def add(name, **kw):
    CATS[name] = kw

# duration default for categories: 没有选镜单中位数时，用爆款单镜中位约 1.3 秒
DEFAULT_SEC = "没有本类专用的爆款中位数；检索时先按 1–2 秒取（爆款单镜中位约 1.3 秒，91% 不超过 2 秒），动作类优先动作完整=有起有收。"

add("价格与预算",
    must=bm([item("画面类型", "按该条原句选语境画面。同类报价/对比句（如其他公司要价高）：可用「其他」（V22）承接，推荐模糊画面叠大字；金额只能示意，须另核；禁止用其他公司的清晰可辨画面；不要用我方成品或我方施工去「证明」别人要价。省拆除费用：批刮和拆砸反例都可以用，可并列；拆砸是反例，不要写成我方正在推荐继续砸砖的工艺。不要伪造价目表或数钱来「证明」金额"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("画面类型", "禁止用其他公司的清晰可辨画面；不要用我方成品或我方施工去「证明」别人要价；拆砸镜头不得写成我方正在推荐继续砸砖的工艺")]),
    cannot_prove="具体价格、预算区间、「便宜」「省了多少」都必须另核报价单、合同或活动规则。画面只能作示意。本类 140 条里 131 条为语境承接，1 条需事实依据，8 条需上下文；需事实依据的那一条仍必须写明示意。",
    duration=DEFAULT_SEC,
    mixed_nature="以观点清单该条的对应性质为准；类默认（索引表）为语境承接。",
    polar=False,
)

add("工期与效率",
    must=bm([item("画面类型", vcode("成品空间") + " 或 " + vcode("成品里的人") + "，表示完成或可使用状态；施工过程只能作辅镜"),
             item("阶段", "完工空房 或 入住使用（主镜）"),
             item("举证等级", "示意")]),
    prefer=[item("空间", "按原句点名的厨房、卫生间或其他空间，不要串空间")],
    forbid=bf([item("阶段", "禁止用旧状或拆除中表达已经完工或即住")]),
    cannot_prove="「三天」「七天」「当天」「快速」等工期数字须另核施工记录、合同工期或产品说明。画面只能作示意。本类 133 条全部是需事实依据。",
    duration=DEFAULT_SEC,
    fact_all=True,
)

add("点赞关注收藏",
    must=bm([item("画面类型", vcode("人物对镜头") + " 为主"),
             item("人数", "至少 1"),
             item("朝向", "看镜头")]),
    prefer=[item("主动作", "挥手、手势或交谈讲解"),
            item("画面类型", "握手沟通可作备选")],
    forbid=bf(),
    cannot_prove="点赞、关注、收藏是行动号召，不需要画面出现爱心图形，也不证明观众会做。",
    duration="第一条线点赞句选镜单中位多在 1.5–2.5 秒；优先人物动作完整。",
)

add("需求条件与兴趣",
    must=bm([item("画面类型", "成品空间、人物或与前后句工艺相关的画面，用来铺垫兴趣/条件，不要独立做成硬卖点")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="「如果你也喜欢」「感兴趣」是呼吁，不要求证明观众的兴趣。短句须结合上下文。",
    duration=DEFAULT_SEC,
)

add("保留基层不拆砸",
    must=bm([item("画面类型", vcode("施工·批刮覆盖")),
             item("主动作", "批刮", note=ACTION_NOTE_PI),
             item("基层", "须同时看见完整旧砖/原基层和新材料"),
             item("阶段", "上料施工中")]),
    prefer=[item("材料类目", "微陶泥（若原句点名）"),
            item("材料依据等级", "人工确认 或 目录标称")],
    forbid=bf([item("画面类型", "拆砸镜头不得写成我方正在推荐继续砸砖的工艺", note="李康 2026-11-17 已定：不拆不砸/不会再砸类，批刮与拆砸反例都可用，可并列")]),
    cannot_prove="不能暗示任何空鼓、渗漏基层都可以直接覆盖。否定拆砸句与拆砸痛点句的画面相反，见肯否定分套。本类另有 5 条需事实依据，那些句子画面只能作示意。",
    duration=DEFAULT_SEC,
    polar="与「传统拆砸与返工」对照：本类以否定拆砸为主。",
)

add("地域与受众",
    must=bm([item("画面类型", "可用老楼/城市外景、人物现场或与后文对象一致的室内；不要把外地地标写成当前账号城市")]),
    prefer=[item("城市", "按账号配置填写；总纲城市字段目前基本空缺，已列入缺口")],
    forbid=bf([item("城市", "不要仅靠字幕或后期大字把素材改成另一个城市的「本地证据」")]),
    cannot_prove="「武汉越来越多人」这类范围断言画面证明不了。城市标签不能靠猜。",
    duration=DEFAULT_SEC,
)

add("无缝同色与踢脚线",
    must=bm([item("画面类型", vcode("成品空间")),
             item("阶段", "完工空房 或 入住使用"),
             item("人数", "0（有人则改用成品里的人）"),
             item("部位", "墙面、地面或墙角与交界；踢脚线原句优先墙角与交界"),
             item("基层", "已成形饰面，尽量看不见旧砖缝")]),
    prefer=[],
    forbid=bf([item("画面类型", "禁止用砖缝清晰的普通瓷砖完成面来配无缝、同色或一体")]),
    cannot_prove="只对可见表面有效。同色到踢脚线的完整收口，总纲部位没有「踢脚线」专名，只能用墙角与交界近似，已列入缺口。本类 4 条需事实依据的句子须写明示意。",
    duration=DEFAULT_SEC,
)

add("人物身份与团队",
    must=bm([item("画面类型", "握手沟通、人物在现场、人物对镜头或团队上门，按原句是「找谁做」还是「团队」来选"),
             item("身份", "只有在依据充分时才填写阿明/李总/小羊/徐经理等；否则未确认")]),
    prefer=[item("身份来源", "人工确认优先；文件夹名已在词表确认次之；人脸程序「像阿明」可作片段库来源，镜序可选择不认")],
    forbid=bf([item("身份", "大模型不许靠脸或衣服认人；普通工人不得冒充负责人；客户方人物只用在该客户自己的片子里")]),
    cannot_prove="「都在找某某」的市场范围证明不了。身份必须另有依据。",
    duration=DEFAULT_SEC,
)

add("开场提问与转折",
    must=bm([item("画面类型", "按钩子类型选：趋势疑问常用批刮或滚涂开头；人设钩子用人物；不要用无关生活空镜硬凑")]),
    prefer=[item("主动作", "施工开场须符合批刮/滚涂口径")],
    forbid=bf(),
    cannot_prove="提问、转折、夸张钩子往往不是可证事实。须保留钩子原文，不要删。",
    duration="第一条线开场单镜中位常见 1.1–1.7 秒；有的开头会用 2–4 个镜头，按该句选镜单为准。",
)

add("材料展示与选品",
    must=bm([item("画面类型", vcode("材料桶") + " 优先，其次正在使用该材料的批刮"),
             item("材料类目", "按原句产品归入词表标准叫法：金刚泥/金刚陶泥/陶泥/陶砂均=微陶泥"),
             item("材料依据等级", "人工确认 或 目录标称；优先包装可见或具名料桶同框"),
             item("主动作", "料桶镜头用倒料取料或搅拌；" + ACTION_NOTE_FETCH)]),
    prefer=[item("部位", "料桶")],
    forbid=bf([item("材料类目", "不得靠颜色猜测；不得用微岩石/水洗石冒充微陶泥；他方品牌包装禁用")]),
    cannot_prove="「就是这款」的品牌指向必须靠已确认材料身份。",
    duration=DEFAULT_SEC,
)

add("环保与无异味",
    must=bm([item("画面类型", "优先可核验的同型号检测资料或已确认产品实物；居家生活、批刮、人物入住只作舒适环境承接"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("画面类型", "不得伪造报告；不得用老人小孩入住暗示无条件环保即住")]),
    cannot_prove="无甲醛、无 VOC、无异味、环保须另核检测报告原文。人物或外观不能证明。本类 2 条需事实依据及全部此类主张，画面只能作示意。",
    duration=DEFAULT_SEC,
)

add("联系与头像",
    must=bm([item("画面类型", vcode("人物对镜头") + " 为主，用于点头像、直接找某某等引导")]),
    prefer=[item("朝向", "看镜头"), item("身份", "具名时须有依据")],
    forbid=bf(),
    cannot_prove="画面不能证明人物正在说这句后配文案，也不能证明头像后面的联系方式有效。",
    duration=DEFAULT_SEC,
)

add("覆盖批刮工艺",
    must=bm([item("画面类型", vcode("施工·批刮覆盖")),
             item("主动作", "批刮", note=ACTION_NOTE_PI),
             item("阶段", "上料施工中"),
             item("动作完整", "有起有收")]),
    prefer=[item("基层", "旧瓷砖且砖缝可见（原句是在瓷砖上覆盖时必须尽量满足）"),
            item("材料类目", "微陶泥，依据到人工确认或目录标称")],
    forbid=bf([item("主动作", "工具在桶里是取料，不算批刮；不要用滚涂或刷涂代替点名批刮的句子")]),
    cannot_prove="批刮过程不能自动证明材料品名或遍数；遍数只来自文件夹名或人工确认。",
    duration=DEFAULT_SEC,
)

add("传统拆砸与返工",
    must=bm([item("画面类型", "必须按肯否定分套，见专门分套表：肯定/痛点用 " + vcode("拆砸/贴砖") + " 或铲修；否定（不拆不砸/不会再砸）则批刮（在旧瓷砖上批刮微陶泥，证明不砸砖）和拆砸反例都可以用，可并列；拆砸的作用是反例，不要写成在推荐继续砸砖的工艺")]),
    prefer=[item("主动作", "拆砸、拆卸或铲除，须看见工具接触与拆除物")],
    forbid=bf([item("画面类型", "否定拆砸的句子里，拆砸镜头不得写成我方正在推荐继续砸砖的工艺", note="李康 2026-11-17 已定：批刮与拆砸反例都可用，可并列")]),
    cannot_prove="「又拆又砸」若是传统痛点，应读得出是旧方法，不能当成我方正在主推的工艺。本类 2 条需事实依据须示意。",
    duration=DEFAULT_SEC,
    polar=True,
)

add("留言地址与需求",
    must=bm([item("画面类型", vcode("人物对镜头") + " 或沟通镜头，承接「留言、留地址、说需求」")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="不要用伪造的评论区截图充当真实留言证据。",
    duration=DEFAULT_SEC,
)

add("耐磨与耐刮",
    must=bm([item("画面类型", vcode("演示·刮擦/擦污")),
             item("主动作", "刮擦敲击，保留接触与擦后表面"),
             item("指定主库编号", "可用 " + ABRASION_OK),
             item("禁用主库编号", ABRASION_BAN + " 禁用"),
             item("材料类目", "微陶泥"),
             item("材料依据等级", "人工确认 或 目录标称"),
             item("举证等级", "示意（即使是获准测试，也不等于无限耐久）")]),
    prefer=[],
    forbid=bf([item("禁用主库编号", ABRASION_BAN),
               item("主动作", "不得用踩踏或奔跑冒充耐磨或防滑认证")]),
    cannot_prove="须另核检测或获准测试记录。本类 3 条需事实依据及所有性能主张，画面只能作示意。",
    duration=DEFAULT_SEC,
    specified=True,
)

add("防潮与防霉",
    must=bm([item("画面类型", "有真实防霉试验记录才作性能证明；否则只用湿区完工表面或 " + vcode("演示·喷水冲洗") + " 作语境承接"),
             item("指定目录", "若做耐水相关演示，优先「" + WATERPROOF_SRC + "」"),
             item("举证等级", "示意")]),
    prefer=[item("材料类目", "微陶泥，依据充分")],
    forbid=bf([item("画面类型", "瞬时泼水、普通干净房间不得写成长期防霉证明")]),
    cannot_prove="长期防霉须另核试验或检测。泼水不独立证明长期防霉。本类主张画面只能作示意。",
    duration=DEFAULT_SEC,
)

add("旧瓷砖与砖缝病害",
    must=bm([item("画面类型", vcode("旧房旧态") + " 为主，须能看见旧砖或砖缝问题"),
             item("阶段", "旧状（未动工）"),
             item("基层", "旧瓷砖且砖缝可见（病害句尤其需要）"),
             item("人数", "0（有人则改人物在现场，但仍须旧状空间是主体）")]),
    prefer=[item("空间", "按原句厨房或卫生间")],
    forbid=bf([item("阶段", "不要用完工无缝饰面或普通未完工墙代替旧砖病害")]),
    cannot_prove="一块旧砖不能证明整户都有同样病害。",
    duration=DEFAULT_SEC,
)

add("短承接词",
    must=bm([item("画面类型", "必须结合原文定位的前后句来选，不能把「然后」「所以」「最主要的是」当成独立工序")]),
    prefer=[],
    forbid=bf([item("画面类型", "不要硬塞无关施工来填这个短句")]),
    cannot_prove="短承接本身通常不是完整的可见信息，对应性质为需上下文。",
    duration="往往短于 1 秒或与前后句同镜；不要为这类词单独堆镜头。",
)

add("量房勘察",
    must=bm([item("画面类型", vcode("量房/水电/安装") + " 或上门、握手沟通"),
             item("主动作", "测量、查看、交谈讲解或走入进门")]),
    prefer=[item("角色", "能同时看见服务人员和客户更好，但关系须有依据")],
    forbid=bf([item("主动作", "不要用批刮冒充量房")]),
    cannot_prove="「免费上门」是政策，须另核活动规则。",
    duration=DEFAULT_SEC,
)
add("客户案例与身份",
    must=bm([item("画面类型", "案例须用已确认授权的客户或项目画面；身份具名须有依据"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("身份", "不得把未授权客户或路人写成案例主人公；客户方人物只用在该客户自己的片子里")]),
    cannot_prove="具体客户身份、住址、改造经历须另核授权和项目记录。本类 53 条全部需事实依据，画面只能作示意。不能确认同户时不得暗示同一户前后。",
    duration=DEFAULT_SEC, fact_all=True,
)

add("风格与完成效果",
    must=bm([item("画面类型", vcode("成品空间") + " 或 " + vcode("成品里的人")),
             item("阶段", "完工空房 或 入住使用")]),
    prefer=[item("部位", "能看清墙地或空间关系")],
    forbid=bf([item("阶段", "不要用旧房或未完工面表达完成效果")]),
    cannot_prove="极简、高级、美观是观感，不是认证。",
    duration=DEFAULT_SEC,
)

add("卫浴与洁具",
    must=bm([item("空间", "卫生间"),
             item("部位", "原句点马桶、浴柜、花洒、淋浴时，部位须是洁具或对应对象，不要用任意漂亮卫生间空镜代替")]),
    prefer=[item("画面类型", "按阶段选旧房旧态、安装中的量房/水电/安装、或成品空间")],
    forbid=bf([item("空间", "不能把厨房或卧室当成卫浴对象")]),
    cannot_prove="不能把任意漂亮卫生间当成无缝或微陶泥材料证明。",
    duration=DEFAULT_SEC,
)

add("方案设计与样品",
    must=bm([item("画面类型", "样品或方案交流：材料桶、样板（部位=样板）、握手沟通或量房；样板不能当成已经做好的墙地面")]),
    prefer=[],
    forbid=bf([item("部位", "样板不得标成墙面或地面完工")]),
    cannot_prove="样品不等于现场已做完的效果。",
    duration=DEFAULT_SEC,
)

add("全包与一站式",
    must=bm([item("画面类型", "团队上门、保护膜、保洁、量房或多项服务现场，用来示意服务完整")]),
    prefer=[item("画面类型", vcode("铺保护膜/贴胶带") + "、" + vcode("团队上门/搬料搬物"))],
    forbid=bf(),
    cannot_prove="「全包」「一站式」的范围须另核服务合同，画面不能证明包含所有项目。",
    duration=DEFAULT_SEC,
)

add("搬家折腾",
    must=bm([item("画面类型", "必须按肯否定分套：否定「不用搬家」用家具保留、分区施工、正常通行；肯定传统折腾用打包搬运、搬离、住酒店相关真实场面")]),
    prefer=[item("画面类型", vcode("铺保护膜/贴胶带") + " 常用于边住边改")],
    forbid=bf([item("主动作", "不要把施工中短暂搬移家具说成整户搬家")]),
    cannot_prove="「全程不用搬家」只对画面可见的住户状态有示意作用。",
    duration=DEFAULT_SEC, polar=True,
)

add("寿命与长期耐用",
    must=bm([item("画面类型", "成品空间或成品里的人，只作使用状态示意"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="「用上二十年/几十年」须另核质保条款或耐久检测。任何成品镜头都不能证明寿命。本类 15 条全部需事实依据，画面只能作示意。",
    duration=DEFAULT_SEC, fact_all=True,
)

add("全屋服务",
    must=bm([item("画面类型", "按原句对象展示对应空间；全屋主张应尽量覆盖不止一个空间，不要只用一个卫生间代替全屋")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="「全屋」范围须看合同和原句上下文。",
    duration=DEFAULT_SEC,
)

add("原砖与翻新基层",
    must=bm([item("画面类型", "必须按原句动词和肯否定选：保留原砖/不用敲=旧砖近景或旧砖上覆盖；基层处理=填缝、清洁、滚涂底漆；贴砖语境=真实铺贴（拆砸/贴砖里的贴砖动作）")]),
    prefer=[item("基层", "旧瓷砖且砖缝可见或旧瓷砖但砖缝看不见，按原句能否看见缝来选")],
    forbid=bf([item("主动作", "不要把覆盖批刮和传统贴砖当成同一种工艺")]),
    cannot_prove="单独一个「瓷砖」词必须回看上下文。本类混了原砖展示、覆盖、贴砖等需求，建议拆开，已上报。",
    duration=DEFAULT_SEC, polar=True, mixed_suggest_split=True,
)

add("局部维修与服务范围",
    must=bm([item("画面类型", "按原句对象做局部：对应部位的旧状、修补或完工，不要用全屋大场景代替局部")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="服务范围以原句和合同为准。",
    duration=DEFAULT_SEC,
)

add("叙述承接与情绪",
    must=bm([item("画面类型", "结合前后段用短讲解、对象细节或生活场景，动作结束后切入下一观点")]),
    prefer=[],
    forbid=bf([item("画面类型", "不把修辞或时间词当成可独立证明的事实，不硬塞无关施工")]),
    cannot_prove="对应性质为需上下文。",
    duration=DEFAULT_SEC,
)

add("安排与到达",
    must=bm([item("画面类型", vcode("团队上门/搬料搬物") + " 或走入进门、车旁到达")]),
    prefer=[item("主动作", "走入进门 或 搬运"), item("空间", "入户门口或小区楼栋外")],
    forbid=bf([item("画面类型", "进门搬东西是团队上门，不要和已在屋里的握手沟通混淆")]),
    cannot_prove="到达画面证明不了预约时间或免费政策。",
    duration=DEFAULT_SEC,
)

add("垃圾清运",
    must=bm([item("画面类型", "搬离废料优先归 " + vcode("拆砸/贴砖") + "（拆下来的废料往外搬）或能明确看出是废料的搬运；新材料进场是团队上门，不要混")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="「省下运垃圾费用」须另核报价。总纲没有独立的垃圾清运画面类型，已列入缺口。",
    duration=DEFAULT_SEC,
)

add("耐污易清洁",
    must=bm([item("画面类型", vcode("成品日常清洁") + " 或去污演示（刮擦/喷水）"),
             item("阶段", "完工空房 或 入住使用"),
             item("主动作", "拖地擦洗、刮擦或喷水冲水")]),
    prefer=[],
    forbid=bf([item("画面类型", "施工现场保洁（V10）不能冒充入住后的日常清洁（V17）"),
               item("画面类型", "不要用砖缝清晰的旧瓷砖配「不用打扫砖缝」")]),
    cannot_prove="一次清洁只能示意好打理。",
    duration=DEFAULT_SEC,
)

add("厨房与橱柜",
    must=bm([item("空间", "厨房"),
             item("部位", "点名橱柜、台面时用台面柜体，不要只用墙面特写代替")]),
    prefer=[item("画面类型", "按阶段选旧态、拆装、成品")],
    forbid=bf([item("空间", "不要用卫生间代替厨房")]),
    cannot_prove="柜体品牌或是否新装须看画面事实，不能凭「厨房」一词推定。",
    duration=DEFAULT_SEC,
)

add("韧性与抗裂",
    must=bm([item("画面类型", vcode("演示·弯折样板/揭薄层")),
             item("主动作", "弯折"),
             item("部位", "样板"),
             item("材料类目", "微陶泥，依据充分"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("部位", "样板不能当成墙地面已经具备同样韧性的证明")]),
    cannot_prove="须另核检测或工艺说明。本类 9 条全部需事实依据，画面只能作示意。",
    duration=DEFAULT_SEC, fact_all=True,
)

add("叙述承接待结合上下文",
    must=bm([item("画面类型", "必须先读原文定位的前后句再选人物、对象和场景；本类片段本身不是完整可见信息")]),
    prefer=[],
    forbid=bf([item("画面类型", "短承接保留独立记录，但不强行当成具体工序")]),
    cannot_prove="对应性质为需上下文。",
    duration=DEFAULT_SEC,
)

add("人物争议与夸张钩子",
    must=bm([item("画面类型", "按钩子选人物对镜头、人物在现场或相应施工；宣传修辞不必从画面证明")]),
    prefer=[],
    forbid=bf([item("身份", "不能把不明人物冒认为特定主体；不要用贬损真实工人的画面")]),
    cannot_prove="「女人都想嫁」「师傅要失业」等是修辞，不是可证事实。不得删钩子、不得改原文。",
    duration=DEFAULT_SEC,
)

add("边住边改与生活",
    must=bm([item("画面类型", "家具保留、分区施工、保护膜、正常通行或真实居家使用"),
             item("画面类型", vcode("铺保护膜/贴胶带") + " 优先用于保护主张")]),
    prefer=[],
    forbid=bf([item("阶段", "不要用清空的毛坯房表达边住边改")]),
    cannot_prove="「边住边改」不能由空房效果证明。本类 1 条需事实依据须示意。",
    duration=DEFAULT_SEC,
)

add("服务态度与客户沟通",
    must=bm([item("画面类型", vcode("握手/与客户沟通")),
             item("主动作", "交谈讲解、握手或查看"),
             item("人数", "优先 2 人以上")]),
    prefer=[],
    forbid=bf([item("角色", "普通工人不冒充负责人；客户关系不能只凭同框推定")]),
    cannot_prove="承诺和客户经历须另核依据。",
    duration=DEFAULT_SEC,
)

add("前后变化",
    must=bm([item("画面类型", "旧态和成品必须成对：须同时准备 " + vcode("旧房旧态") + " 和 " + vcode("成品空间") + "。只有人工确认同户才能说是同一套房子（总纲 D2）。铲修或批刮只能作过程辅镜，不能代替两端"),
             item("阶段", "旧状 → 完工空房或入住使用")]),
    prefer=[item("画面类型", vcode("旧→新同镜转场") + " 可用，同样需要同户确认")],
    forbid=bf([item("同户配对", "不能确认时只能说服务示意，不得暗示同一户")]),
    cannot_prove="本类 4 条需事实依据须示意。旧态和成品必须成对；只有人工确认同户才能说是同一套房子；铲修或批刮不能代替两端。李康 2026-11-17 同意此写法。",
    duration=DEFAULT_SEC,
)

add("改造服务与安装",
    must=bm([item("画面类型", vcode("量房/水电/安装") + " 或对应对象的拆装动作"),
             item("主动作", "安装、拆卸或测量，须与原句对象一致"),
             item("阶段", "安装收口 或 与对象相符的阶段")]),
    prefer=[],
    forbid=bf([item("主动作", "不要仅按「施工」标签选打墙、刷墙来配柜体/洁具安装")]),
    cannot_prove="短镜头无法证明完整工序和结果（参考片拆解口径）。",
    duration=DEFAULT_SEC,
)

add("旧空间痛点",
    must=bm([item("画面类型", vcode("旧房旧态")),
             item("阶段", "旧状"),
             item("空间", "与原句对象一致")]),
    prefer=[],
    forbid=bf([item("阶段", "不要用完工面或普通施工中面代替脏旧痛点")]),
    cannot_prove="一处脏旧不能推广到整户。",
    duration=DEFAULT_SEC,
)

add("预算与人工开支",
    must=bm([item("画面类型", "语境承接即可，可用人物或对比施工；不要伪造工资单或数钱"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="人工费、省好几万须另核报价或结算。画面只能作示意。",
    duration=DEFAULT_SEC,
)

add("水电改造",
    must=bm([item("画面类型", "必须按肯否定分套：肯定改水电用真实检查管线、开槽、布管或接线（" + vcode("量房/水电/安装") + "）；否定「不改水电」展示保留原设施的表面翻新，不得配正在拆管线")]),
    prefer=[],
    forbid=bf([item("画面类型", "不把批刮当水电施工；「不用改」不能配正在拆管线")]),
    cannot_prove="是否真的不用改水电须看现场和合同。",
    duration=DEFAULT_SEC, polar=True,
)

add("传统噪音与扬尘",
    must=bm([item("画面类型", "必须按肯否定分套：传统扬尘配实际拆砸；低扰动配手工批刮、分区围护与日常通行")]),
    prefer=[],
    forbid=bf([item("画面类型", "无灰尘、无噪音等绝对说法不能靠静音视频证明；不额外合成粉尘")]),
    cannot_prove="「全程静音不扰民」无法被无音轨或环境声证明。绝对化主张只能示意。",
    duration=DEFAULT_SEC, polar=True,
)

add("入住与正常使用",
    must=bm([item("画面类型", vcode("成品里的人") + " 或入住使用阶段的成品空间"),
             item("阶段", "入住使用（优先）或完工空房"),
             item("角色", "客户业主、长者或儿童须真实且授权，不得用工人冒充住户"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="入住画面不等于即住合规或环保合格。",
    duration=DEFAULT_SEC,
)

add("案例数量与经验",
    must=bm([item("画面类型", "多个项目或团队现场只能作示意，不得用后期堆砌数字当证据"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="「做了多少家」须另核项目台账。本类 15 条全部需事实依据，画面只能作示意。",
    duration=DEFAULT_SEC, fact_all=True,
)

add("售后与质保",
    must=bm([item("画面类型", "沟通、回访或成品使用只能作服务示意"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="质保年限、售后承诺须另核合同或质保条款。本类 10 条全部需事实依据，画面只能作示意。",
    duration=DEFAULT_SEC, fact_all=True,
)

add("保洁与清洁",
    must=bm([item("画面类型", "施工前后清理用 " + vcode("保洁/清扫") + "；入住后拖地擦洗用 " + vcode("成品日常清洁")),
             item("主动作", "清扫吸尘 或 拖地擦洗")]),
    prefer=[],
    forbid=bf([item("画面类型", "两类清洁不要混用")]),
    cannot_prove="一次清扫不能证明「最后连卫生都做了」的全部过程。",
    duration=DEFAULT_SEC,
)

add("政策与补贴",
    must=bm([item("画面类型", "任何工地或人物镜头都只作话题承接"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("画面类型", "不得伪造红头文件或补贴到账画面来充当政策证据")]),
    cannot_prove="政策资格、补贴金额须另核政策原文和适用条件。本类 17 条全部需事实依据，画面只能作示意。",
    duration=DEFAULT_SEC, fact_all=True,
)
add("使用与效果补充",
    must=bm([item("画面类型", "效果句配完成表面；入住句配真实使用；环保与噪音句仅配过程示意"),
             item("举证等级", "涉及无味、无醛、即住或性能时必须示意")]),
    prefer=[],
    forbid=bf([item("画面类型", "无味、无醛、即住及性能不由外观或人物入镜直接证明")]),
    cannot_prove="性能与即住须另核依据。",
    duration=DEFAULT_SEC,
)

add("客户评价与转介绍",
    must=bm([item("画面类型", "真实沟通或授权出镜的客户评价场面，只作示意"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("身份", "未授权不得写成客户好评")]),
    cannot_prove="好评内容、转介绍数量须另核。本类 15 条全部需事实依据，画面只能作示意。",
    duration=DEFAULT_SEC, fact_all=True,
)

add("补充工序与改造方式",
    must=bm([item("画面类型", "必须按原句工序和肯否定拆开：肯定拆砸=真实拆旧；否定拆砸（不想拆砸换新/不拆不砸）=批刮（保留原砖覆盖）和拆砸反例都可以用，可并列，拆砸是反例、不要写成推荐继续砸砖；美缝=填缝收胶近景；工艺介绍=完整对应动作")]),
    prefer=[],
    forbid=bf([item("主动作", "别把覆盖和美缝当成同一种工艺")]),
    cannot_prove="本类实际混了拆砸态度、美缝、笼统工艺介绍等多种画面需求，建议拆开，已上报。肯定/否定分套见专门表。总纲没有独立「美缝」画面类型，只能用主动作其他或部位墙角与交界近似，已列入缺口。",
    duration=DEFAULT_SEC, polar=True, mixed_suggest_split=True,
)

add("包装与施工用量",
    must=bm([item("画面类型", vcode("材料桶") + " 或能看见包装的产品实物"),
             item("材料依据等级", "优先包装可见")]),
    prefer=[],
    forbid=bf([item("他方品牌包装入镜", "有则不用")]),
    cannot_prove="「能刮多少平方米」须另核产品说明，画面不能证明用量数字。",
    duration=DEFAULT_SEC,
)

add("生意与求助",
    must=bm([item("画面类型", "人物对镜头或沟通，作话术承接")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="求助、做生意的叙事不是工程施工证据。",
    duration=DEFAULT_SEC,
)

add("家具保护",
    must=bm([item("画面类型", vcode("铺保护膜/贴胶带")),
             item("主动作", "铺膜贴胶带"),
             item("阶段", "保护与基层处理")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="看见局部保护不能证明全程所有家具都保护了。",
    duration=DEFAULT_SEC,
)

add("施工人员与工艺细节",
    must=bm([item("画面类型", "以能看清工具、手部和接触面的施工近景为主，按具体动作选批刮/滚涂/其他"),
             item("动作完整", "有起有收")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="细节镜头不能自动推广为整道工序已经完成。",
    duration=DEFAULT_SEC,
)

add("耐压与硬度",
    must=bm([item("画面类型", "获准材料的敲击、承压测试；主动作=刮擦敲击"),
             item("指定主库编号", "可与耐磨同一批获准源 " + ABRASION_OK + " 检索"),
             item("禁用主库编号", ABRASION_BAN + " 禁用"),
             item("举证等级", "示意")]),
    prefer=[item("材料类目", "微陶泥，依据充分")],
    forbid=bf(),
    cannot_prove="敲击只是演示，不等同量化硬度或承压等级报告。画面只能作示意。",
    duration=DEFAULT_SEC, specified=True,
)

add("霉墙与潮湿起皮",
    must=bm([item("画面类型", vcode("旧房旧态")),
             item("阶段", "旧状"),
             item("空间", "按原句，常见卫生间或外墙附近室内")]),
    prefer=[],
    forbid=bf([item("画面类型", "一面普通未完工墙不能代替发霉、起皮的旧状")]),
    cannot_prove="局部霉斑不能证明整面墙或整户潮湿原因。",
    duration=DEFAULT_SEC,
)

add("家具搬移与复位",
    must=bm([item("画面类型", vcode("团队上门/搬料搬物")),
             item("主动作", "搬运 或 收拾整理", note="搬的是住户家具，不是拆下来的废料（废料归拆砸）")]),
    prefer=[],
    forbid=bf([item("画面类型", "不要把整户搬家和施工中短暂搬家具搞混，见搬家折腾的肯否定")]),
    cannot_prove="看见搬一次不能证明已经复位。",
    duration=DEFAULT_SEC,
)

add("墙面服务",
    must=bm([item("部位", "墙面"),
             item("画面类型", "按原句阶段选旧态、批刮、滚涂或成品")]),
    prefer=[],
    forbid=bf([item("部位", "不要用地面镜头代替墙面服务")]),
    cannot_prove="索引表对应性质为直接展示，但本类 4 条观点实际都是需上下文，选镜须读原句。",
    duration=DEFAULT_SEC,
)

add("现场对象与服务补充",
    must=bm([item("画面类型", "依原句配墙面、地面、旧卫浴或量房现场；动作与前后文施工阶段一致")]),
    prefer=[],
    forbid=bf([item("阶段", "脏旧、施工和完工状态不可互相替代")]),
    cannot_prove="完整上下文见原文定位页。",
    duration=DEFAULT_SEC,
)

add("台面水槽与龙头",
    must=bm([item("部位", "台面柜体 或 洁具（水槽龙头按原句）"),
             item("空间", "厨房优先，卫生间台盆按原句"),
             item("画面类型", "安装用 " + vcode("量房/水电/安装") + "；换新完成用成品空间；测量只能作间接备选")]),
    prefer=[],
    forbid=bf([item("主动作", "不能把「测量」标成「台面已换新」的事实证据（参考片拆解）")]),
    cannot_prove="短镜头无法证明完成换新全过程。",
    duration=DEFAULT_SEC,
)

add("门窗阳台吊顶",
    must=bm([item("空间", "按原句阳台或对应房间"),
             item("部位", "门窗 或 顶面")]),
    prefer=[item("画面类型", "安装或成品，按原句阶段")],
    forbid=bf(),
    cannot_prove="不要用墙地饰面冒充门窗或吊顶对象。",
    duration=DEFAULT_SEC,
)

add("家具与电器",
    must=bm([item("画面类型", "按原句展示对应家具或电器的保护、搬移、安装或使用，不要用空房间代替")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="品牌和是否新购须看画面事实和授权。",
    duration=DEFAULT_SEC,
)

add("防水与耐水",
    must=bm([item("画面类型", vcode("演示·喷水冲洗") + "：已确认微陶泥墙地面泼水、水珠流下或冲洗近景"),
             item("指定目录", "优先「" + WATERPROOF_SRC + "」内适配区间"),
             item("材料类目", "微陶泥"),
             item("材料依据等级", "人工确认 或 目录标称"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("画面类型", "不能用泼水证明整个防水系统合格；要区分材料耐水展示与基层防水施工")]),
    cannot_prove="须另核防水施工记录或检测。画面只能作示意。指定目录在扒扒库，属清单写明的例外，不是把扒扒库整体纳入第一条线。",
    duration=DEFAULT_SEC, specified=True,
)

add("开桶即用",
    must=bm([item("画面类型", vcode("材料桶")),
             item("主动作", "倒料取料或搅拌；开桶动作若发生在取料之前，须能看见开盖，不要只用已经在刮的批刮代替「打开桶就可以使用」")]),
    prefer=[item("材料类目", "微陶泥，依据充分")],
    forbid=bf(),
    cannot_prove="「打开就能用」的施工便利是主张，须结合产品说明。本类 4 条性质混杂，其中 1 条需事实依据须示意。总纲动作没有单独的「开桶」，只能用倒料取料近似，已列入缺口。",
    duration=DEFAULT_SEC,
)

add("旧楼外观与室内反差",
    must=bm([item("画面类型", vcode("老楼/城市外景") + " 与室内旧态或成品的对比；若暗示同一栋/同一户，须另核来源，不能靠猜测")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="室外楼栋和室内房间的对应关系必须确认，否则只能分开作示意。",
    duration=DEFAULT_SEC,
)

add("颜色与柜体改色",
    must=bm([item("部位", "台面柜体 或 原句所指对象"),
             item("画面类型", "改色过程或改后成品，须能看出对象是柜体/指定表面")]),
    prefer=[],
    forbid=bf([item("材料类目", "柜体改色未必是微陶泥，按原句和材料依据填，不要默认微陶泥")]),
    cannot_prove="改色前后若称同一套，须同户或同件确认。",
    duration=DEFAULT_SEC,
)

add("地面服务",
    must=bm([item("部位", "地面"),
             item("画面类型", "按原句选旧态、批刮、成品或演示")]),
    prefer=[],
    forbid=bf([item("部位", "不要用墙面镜头代替地面服务")]),
    cannot_prove="须读原句确认是维修、覆盖还是清洁。",
    duration=DEFAULT_SEC,
)

add("厨房油污与脏乱",
    must=bm([item("空间", "厨房"),
             item("画面类型", vcode("旧房旧态")),
             item("阶段", "旧状")]),
    prefer=[],
    forbid=bf([item("阶段", "不要用完工厨房代替油污脏乱旧状")]),
    cannot_prove="局部油污不能推广到整个厨房。",
    duration=DEFAULT_SEC,
)

add("底漆与滚涂",
    must=bm([item("画面类型", vcode("施工·滚涂")),
             item("主动作", "滚涂（必须看见滚筒接触表面滚动，不是刷子）", note=ACTION_NOTE_ROLL),
             item("阶段", "滚筒在旧瓷砖或旧墙面上=保护与基层处理；在已经同色成形的面上=罩面收尾")]),
    prefer=[item("材料类目", "按依据填写；词表：罩面、上罩面、滚涂罩面合并为罩面")],
    forbid=bf([item("主动作", "刷子刷涂应标刷涂，不得写成滚涂")]),
    cannot_prove="滚涂画面不能自动证明用的是底漆还是罩面，要看阶段和依据。",
    duration=DEFAULT_SEC,
)

add("材料性能与选型补充",
    must=bm([item("画面类型", "对应产品实物或有依据的单项性能演示，按后文确定是耐磨、耐水还是其他"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("画面类型", "泛称「性能」不意味着一个测试可以证明所有性能")]),
    cannot_prove="须另核对应检测。",
    duration=DEFAULT_SEC,
)

add("亲自带队与负责",
    must=bm([item("画面类型", "现场人物或团队；若点名具体负责人，身份必须有依据")]),
    prefer=[],
    forbid=bf([item("身份", "不得把普通工人写成「亲自带队」的负责人")]),
    cannot_prove="「亲自」是角色主张，须身份依据。",
    duration=DEFAULT_SEC,
)

add("基层与适用表面",
    must=bm([item("基层", "按原句填写旧瓷砖且砖缝可见 / 旧瓷砖但砖缝看不见 / 水泥或腻子等"),
             item("画面类型", "能看清基层的旧态、基层处理或覆盖界面")]),
    prefer=[],
    forbid=bf(),
    cannot_prove="「什么表面都能做」不能由一块基层推广。",
    duration=DEFAULT_SEC,
)

add("施工厚度与空间",
    must=bm([item("画面类型", vcode("施工·批刮覆盖") + " 近景，尽量看见涂层边缘"),
             item("主动作", "批刮", note=ACTION_NOTE_PI)]),
    prefer=[],
    forbid=bf(),
    cannot_prove="「三到五毫」等厚度数字总纲没有字段可以检索，只能示意，已列入缺口。须另核工艺说明。",
    duration=DEFAULT_SEC,
)

add("找平与填缝",
    must=bm([item("画面类型", "基层处理：可能是批刮补缝、其他施工或部位=墙角与交界/地面"),
             item("阶段", "保护与基层处理"),
             item("主动作", "批刮（补缝补裂也算批刮，总纲：往面上加料是批刮）或看不清时归施工现场·其他，不要猜")]),
    prefer=[],
    forbid=bf([item("主动作", "往下铲东西是铲除，不要和填缝批刮混淆")]),
    cannot_prove="本类只有 1 条观点。美缝收胶与填平砖缝不是同一工序。",
    duration=DEFAULT_SEC,
)

# 防滑：索引表有定义、出现次数 0，不计入验收要求的 78 条，另附。
add("防滑",
    appendix=True,
    must=bm([item("画面类型", "须为有依据的防滑测试或表面纹理近景，不能用耐磨刮擦或行人踩踏代替"),
             item("材料类目", "须有材料身份依据"),
             item("举证等级", "示意")]),
    prefer=[],
    forbid=bf([item("主动作", "不得用踩踏或奔跑冒充防滑认证，不制造危险演示")]),
    cannot_prove="索引表将本类列为需事实依据，但观点清单 2043 条中出现次数合计为 0，没有代表句。部分「耐磨与耐刮」适配说明里附带了防滑提示。本条不计入 78 类对照表正文，只作附录。防滑测试在总纲画面类型里没有专类，已列入缺口。",
    duration=DEFAULT_SEC, fact_all=True,
)


def get_cat(name):
    if name not in CATS:
        raise KeyError(name)
    return CATS[name]