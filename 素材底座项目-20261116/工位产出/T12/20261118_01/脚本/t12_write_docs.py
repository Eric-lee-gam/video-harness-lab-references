# -*- coding: utf-8 -*-
"""根据选样和转码统计，写出测试计划、准备阶段回报和问题单。不调用任何外部接口。"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from t12_lib import (
    MAX_COPY_BYTES,
    OUT_ROOT,
    PROJECT_ROOT,
    fmt_hours,
)

PROBLEM_DIR = PROJECT_ROOT / "问题反馈"


def now_sh() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "（Asia/Shanghai）"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def pct(n, d) -> str:
    if not d:
        return "0%"
    return f"{n/d*100:.2f}%"


def write_plan(sel: dict, tr: dict | None):
    final = sel["最终"]
    short = final["短于4秒"]
    up = final["可上传_不少于4秒"]
    if tr:
        size_b = tr["副本总字节"]
        size_gb = size_b / 1024 / 1024 / 1024
        size_line = f"{size_gb:.4f} GB（{size_b:,} 字节）"
        copy_dir = tr["副本目录"]
        copy_n = tr["副本文件数"]
        bitrate = tr.get("码率kbps")
        under = "不超过" if tr.get("是否不超过2.5GB") else "超过了"
        miss = tr.get("可上传>=4秒") or {}
        copy_ok = miss.get("已有副本")
        copy_need = miss.get("应有")
        fail = tr.get("失败") or []
    else:
        size_line = "转码尚未完成，待填"
        copy_dir = str(OUT_ROOT / "副本")
        copy_n = "待填"
        bitrate = "待填"
        under = "待转码完成后确认"
        copy_ok = "待填"
        copy_need = up["条数"]
        fail = []
        size_gb = None

    text = f"""# 测试计划与费用预估（T12 准备阶段，尚未上传）

日期：2026-11-18（Asia/Shanghai）

**本页只是上传前的计划，现在还不能上传。** 必须等李康看过本页和 `上传清单.csv`，明确说「可以传」之后，才能调用任何 Twelve Labs 的上传、建索引、检索或分析接口。准备阶段没有调用这些接口，也没有花钱。

## 1. 准备传什么

| 项 | 数字 |
|---|---|
| 上传清单文件数 | {final['条数']} 个 |
| 清单总时长 | {final['总时长']} |
| 其中可上传（时长 ≥ 4 秒） | {up['条数']} 个，{up['总时长']} |
| 其中短于 4 秒（按官网 Marengo 3.0，单独传不了） | {short['条数']} 个，{fmt_hours(short['总秒'])}；占清单条数 {pct(short['条数'], final['条数'])}，占清单时长 {pct(short['总秒'], final['总秒'])} |
| 转码副本路径 | `{copy_dir}` |
| 已做成的副本数 | {copy_n}（可上传应有副本 {copy_need} 个，已有 {copy_ok} 个） |
| 转码视频目标码率 | {bitrate} kbps（按 2.5 GB 上限留余量反推） |
| 副本总大小 | {size_line} |
| 任务书副本上限 | 2.5 GB，当前{under} |

对应关系见同目录 `编号对应表.csv`。文件名是 `t12_0001.mp4` 这类编号，不含项目名和人名。短于 4 秒的明细见 `短于4秒清单.csv`。本步没有把短片拼成一条，也没有上传。

## 2. 账号后台额度（待李康填写）

李康还没有提供账号后台数字。下表先空着，不以官网套餐数字冒充后台额度。实际以登录后 `Settings > Billing & Plans` 显示的为准。

| 项 | 账号后台数字 | 说明 |
|---|---|---|
| 当前套餐 | （待填） | 新计费下免费档是 $0/月 |
| Managed Intelligence 额度 | （待填） | 免费档官网写累计存储 3 GB |
| 已用存储 | （待填） | 存储按成功处理的上传原文件大小计，缩略图和转写不计入 |
| 剩余存储 | （待填） |  |
| 每月 Workload 额度 | （待填） | 免费档官网只写 Basic、按月刷新，具体数字以后台为准 |
| 已用 Workload | （待填） |  |
| 剩余 Workload | （待填） |  |
| 是否已切到新计费 | （待填） | 现有用户可能仍在旧计费，2027-01-04 起自动迁移；无付费 Jockey 订阅的可以提前选套餐 |

**够不够：现在不能下结论。** 要等上面的后台数字填上，再和本页第 1 节的文件数、时长、副本 GB 对一下。

## 3. 官网现行信息（2026-11-18 查到的，和任务书 11 月 17 日记载不完全一样）

查阅页：

- https://www.twelvelabs.io/pricing
- https://www.twelvelabs.io/list-price
- https://docs.twelvelabs.io/docs/get-started/plans-and-billing/plans-allowances-and-overage
- https://docs.twelvelabs.io/docs/get-started/plans-and-billing/migrate-to-new-billing
- https://docs.twelvelabs.io/docs/concepts/models/marengo/marengo-3-0

现行要点（2026-11-18）：

- 免费档：$0/月。Managed Intelligence 累计存储 **3 GB**。到达上限后，免费档和 Plus **不能超支**，上传会被挡住。Pro 可在后台打开超支，默认关闭。
- 新计费下，Marengo 3.0 建索引包含在 Managed Intelligence 里，**不再按任务书里的「建索引每分钟 0.042 美元」那套旧标价来估**。旧标价不要当现行收费。
- Marengo Search（`POST /search`）计入 Workload 额度，列表价 **$4 / 1,000 queries**。
- Pegasus 分析现行列表价约为每视频小时 **$1.75**。任务书写的是 Pegasus 1.5 和另一套分钟价；官网现为 **Pegasus 1.6**。第 9 步「额度够才做」在本计划里标明：免费额度不够就不做。
- 旧免费档还有「每月 10 小时索引、每索引最多 100 个视频」的说法；新计费以套餐额度（3 GB 存储 + 每月 Workload）为准。迁移说明也写了：新计费用套餐额度，不再用那几条旧免费档上限。实际以账号后台为准。
- 存储怎么计量：按成功处理的资源原文件大小（GB）。平台按每天峰值存储再在账期内取平均。生成的缩略图、转写不计入。
- Workload 包括：Analyze、Segment、Embed、Marengo Search、Jockey Responses。Jockey Search 若资源已进 Knowledge Store，包含在 Managed Intelligence 里，不另计 Workload。

## 4. 单个视频限制（开工时已按官网核验）

以 Marengo 3.0 文档为准（https://docs.twelvelabs.io/docs/concepts/models/marengo/marengo-3-0）：

- 时长：4 秒到 4 小时
- 大小：不超过 4 GB
- 分辨率：360×360 到 5184×2160
- 画幅比：1:1 到 1:2.4（或反过来），示例包含 16:9 和 **9:16 竖屏**
- 格式：FFmpeg 支持的格式（副本已转成 720p H.264 MP4，并按原片表旋转/Display Matrix 转正）

这和任务书 11 月 17 日记载一致。另外，上传方式自己还有限制（本阶段只做副本、不上传，写在这里供第 4 步参考）：本地直接上传视频/音频上限 200 MB，分片上传可达 10 GB，公开 URL 可达 4 GB。按本批码率，单条副本远小于 200 MB。

清单里短于 4 秒的，单独传会被 Marengo 3.0 拒绝，见下一节建议。

## 5. 2.5 GB 副本上限怎么对齐 3 GB 免费存储

- 任务书要求副本总大小不超过 2.5 GB，是为了低于免费档 3 GB 存储，并留约 0.5 GB 给已有资源或计量误差。
- 官网说存储按**上传的原文件大小**计，不是按源 MOV 计。我们准备上传的是转码后的副本，所以应对齐副本总大小，而不是共享盘原片大小。
- 转码时按不超过 2.2 GB 反推了视频码率，目标是实际副本落在 2.5 GB 以内。
- 若后台显示已经用掉一部分存储，3 GB 减已用可能小于 2.5 GB，那时要少传，不能硬传满 2.5 GB。

## 6. 短于 4 秒怎么处理（只提建议，本步没有拼接，也没有上传）

短于 4 秒共 {short['条数']} 条，占清单条数 {pct(short['条数'], final['条数'])}，占清单时长 {pct(short['总秒'], final['总秒'])}，时长合计只有约 {short['总秒']:.1f} 秒，对总样本量影响很小。其中可能含试标 50 段所在的整段短视频：若整段原片本身不足 4 秒，不拼就无法进索引，第 9 步也测不到这些段。

建议（请李康定）：

1. **默认建议：把短于 4 秒的几条按同类或就近拼成一条（或几条）≥ 4 秒的 MP4 再传**，另存拼接对照表，检索对秒时再拆回原编号。这样试标短片还能测到，也不怎么占存储。
2. 备选：不传这些短片。实现简单，但试标里整段不足 4 秒的会缺测。
3. 不建议为这不到两分钟的素材单独付费。

在李康说「可以传」之前，不拼接上传文件，不上传。

## 7. 额度不够时的备选（都不自行执行）

在后台数字填上之后，如果不够，按这个顺序请李康选，**不要自行付费，也不要自行改套餐**：

1. **少传**：优先保留事实层和试标 50 段所在视频，再按 T07 可找到的类（V05/V06/V11/V23）各留一部分；先去掉后补的类候选。按副本 GB 裁到剩余存储以下。
2. **拼短片**：按第 6 节把短于 4 秒的拼起来，只减少文件数，几乎不减存储。
3. **付费**：只有李康决定后才考虑。新计费列表价仅供对照，不是下单依据：存储超支（仅 Pro 可开）约 $0.065/GB/月；Marengo Search $4/1,000 次；Pegasus 1.6 分析约 $1.75/视频小时。免费档和 Plus 不能超支。若后台仍是旧计费，标价可能不同，以后台为准。

第 9 步 Pegasus 打标签测试：**额度够才做**。免费额度不够就不做，报告里写「没做，原因是额度」。不要为第 9 步自行开通付费。

## 8. 本阶段明确没有做的事

- 没有调用 Twelve Labs 的上传、建索引、检索、分析接口
- 没有把密钥写入任何文件或回报（也没有读取或打印 `TWELVELABS_API_KEY`）
- 没有改共享盘或原片
- 没有开始 T03，没有联系任何人

等李康看过 `上传清单.csv` 和本页，并明确说「可以传」之后，再做任务书第 4 步。
"""
    path = OUT_ROOT / "测试计划与费用预估.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_report(sel: dict, tr: dict | None, dropped_rows: list[dict], snap_cmp: dict | None):
    final = sel["最终"]
    short = final["短于4秒"]
    up = final["可上传_不少于4秒"]
    rules = sel["规则路径确认"]
    unique_dropped = {}
    for r in dropped_rows:
        unique_dropped[r["原片ID"]] = r
    # 原因归类
    jbl = mei = heng = other = 0
    for r in unique_dropped.values():
        why = r.get("拿掉原因") or ""
        if "嘉贝乐" in why:
            jbl += 1
        elif "美女人设" in why or "禁用表" in why:
            mei += 1
        elif "画幅" in why or "横" in why:
            heng += 1
        else:
            other += 1

    if tr:
        trans_txt = (
            f"可上传应有副本 {tr['可上传>=4秒']['应有']}，已有 {tr['可上传>=4秒']['已有副本']}；"
            f"副本总大小 {tr['副本总大小']}，不超过 2.5 GB：{tr['是否不超过2.5GB']}；"
            f"失败 {len(tr.get('失败') or [])}。"
        )
        spent_time = f"转码墙钟约 {tr.get('用时秒', 0)/60:.1f} 分钟（见统计/转码结果.json）"
        copy_ok = tr["是否不超过2.5GB"] and tr["可上传>=4秒"]["已有副本"] == tr["可上传>=4秒"]["应有"] and not tr.get("失败")
    else:
        trans_txt = "转码尚未完成或中断后未收工。"
        spent_time = "转码未完成，墙钟待补"
        copy_ok = False

    share_ok = None
    if snap_cmp is not None:
        share_ok = snap_cmp.get("改动条数") == 0

    lines = []
    lines.append("# T12 准备阶段回报（20261118_01）")
    lines.append("")
    lines.append(f"日期：{now_sh()}")
    lines.append("")
    lines.append("本批只做任务书第 1、2 步和第 3 步草稿。没有上传，没有建索引，没有检索或分析，没有花任何钱。")
    lines.append("")
    lines.append("## 1. 做了什么")
    lines.append("")
    lines.append(f"- 规则路径已确认：试标 50 段在 `{rules['试标50段_对应表']}`（存在：{rules['试标50段存在']}）；审核结果和看图说明 v0.2 也在同一 `试标50段` 目录。T07 最新对照表用 `工位产出\\T07\\20261117_05\\第一条线_逐句对照表.md` 与 `.tsv`。画面清单一览采用 `工位产出\\T07\\20261117_02\\第一条线_画面清单.md`（05 批次未另存该清单，类型与 02 一致）。")
    lines.append(f"- 第 1 步挑样本：上传清单 {final['条数']} 条，总时长 {final['总时长']}，落在 2.5–3.5 小时窗口内。随机种子 20261118。")
    lines.append(f"- 必选：事实层范围内落到具体文件的视频 {sel['事实层']['范围内落到文件并可对上原片表的视频数']} 个、试标 50 段所在视频 {sel['试标50段']['所在视频数']} 个；对上原片表后、排除并拿掉外传风险，必选实际入选 {sel['必选入选后']['条数']} 个、{sel['必选入选后']['总时长']}。文件夹级事实 {sel['事实层']['文件夹级事实条数_不展开整夹']} 条不按整夹展开。")
    lines.append(f"- 被拿掉（必选里发现不该外传或硬排除）{sel['必选被拿掉']} 行，去重后 {len(unique_dropped)} 个视频，详见同目录 `拿掉清单.csv` 和问题单。其中嘉贝乐 {jbl}、美女人设/禁用人物 {mei}、横屏 {heng}、其他 {other}。")
    lines.append(f"- 补充：T07 画面清单里，粗标层能找到候选的只有 V05、V06、V11、V23 四类，共取 {sel['补充_按T07类']} 条。其余 19 类粗标层没有对应 B1 画面类型标签，无法按类抽。粗标层完全没有标签的合格视频为 0，所以没有从「无标签项目文件夹」抽到条。没有再用其他目录硬补（时长已落到目标附近）。")
    lines.append(f"- 第 2 步：清单里 {final['条数']} 个源文件在共享盘上只读检查，当时全部能访问。用 ffmpeg 转成 720p H.264 MP4，按 T01 原片表旋转角度（来自 Display Matrix）转正，文件名改为 `t12_XXXX.mp4`。{trans_txt}")
    lines.append("- 第 3 步：写了 `测试计划与费用预估.md`。免费额度以账号后台为准，本页把后台数字留空待填。没有宣称可以上传。")
    lines.append("- 没用 pandas/openpyxl，没装新软件或 Python 包，没读、没打印、没写入 `TWELVELABS_API_KEY`，没改共享盘和原片，没打开 CutFrame `local\\gpt-pilot\\`，没触发镜序扫描/检索/生成，没改总纲/词表/选镜单，没联系人，没开始 T03。")
    lines.append("")
    lines.append("## 2. 验收自查")
    lines.append("")
    ok_win = "达到" if final["是否落在2.5到3.5小时"] else "没达到"
    lines.append(f"- 上传清单每行有主库相对路径、时长、为什么选它，总时长在 2.5–3.5 小时：{ok_win}。实际 {final['条数']} 条，{final['总时长']}。")
    if tr:
        lines.append(f"- 每个可上传视频有一个副本：{'达到' if tr['可上传>=4秒']['已有副本']==tr['可上传>=4秒']['应有'] else '没达到'}。应有 {tr['可上传>=4秒']['应有']}，已有 {tr['可上传>=4秒']['已有副本']}，缺 {tr['可上传>=4秒']['缺副本']}。")
        lines.append(f"- 副本总大小不超过 2.5 GB：{'达到' if tr['是否不超过2.5GB'] else '没达到'}。实际 {tr['副本总大小']}。")
    else:
        lines.append("- 每个可上传视频有一个副本：没达到（转码未收工）。")
        lines.append("- 副本总大小不超过 2.5 GB：未验证（转码未收工）。")
    lines.append(f"- 短于 4 秒有清单和占比：达到。`短于4秒清单.csv` {short['条数']} 条，占条数 {pct(short['条数'], final['条数'])}，占时长 {pct(short['总秒'], final['总秒'])}。本步未擅自拼接。")
    lines.append("- 测试计划已写，后台额度留空待填，并写明必须等李康说「可以传」才能上传：达到。没有调用任何上传接口。")
    lines.append("- 共享盘和原片没有任何改动：{}".format(
        "达到。转码前后只读快照大小和 mtime 变化 0 条。" if share_ok else
        ("没达到或待核。对比见 统计/共享盘快照对比.json。" if snap_cmp is not None else "转码未收工，转码前快照已写，转码后对比待补。")
    ))
    lines.append(f"- 样本中不该外传的内容已从清单拿掉并写明：达到。去重 {len(unique_dropped)} 个视频，见 `拿掉清单.csv` 和问题单。清单残留排除项 0。")
    lines.append("- 所有产出、脚本、日志里不应出现密钥：本阶段没有读取密钥。收工前未用密钥字符串检索（没有调用接口，脚本也不打印环境变量）。")
    lines.append("- 实际花的钱：0。")
    lines.append("")
    lines.append("## 3. 没做的和为什么")
    lines.append("")
    lines.append("- 第 4 步及之后（上传、建索引、检索、和事实层对答案、盲评、Pegasus 打标签、删除说明）全部没做。原因：任务授权只到上传前准备；必须等李康看过清单和计划并说「可以传」。")
    lines.append("- 没有把短于 4 秒的视频拼成一条。原因：任务要求只在第 3 步计划里建议，本步不得擅自拼接上传文件。")
    lines.append("- 没有填写账号后台额度。原因：李康还没提供后台数字，不以官网套餐数字冒充。")
    lines.append("- T07 画面清单中 19 类没有按类抽样。原因：粗标层没有这些类的 B1 画面类型标签，不能假装找到了候选。")
    lines.append("- 「各项目文件夹随机取一些粗标层没有标签的」取到 0 条。原因：在排除后的 `拍摄\\小区` 和 `拍摄\\测试` 里，没有「粗标层完全没有记录」的合格视频。")
    lines.append("- 事实层 27 条文件夹级记录没有把整个文件夹的视频都纳入必选。原因：它们不是「片段所在的视频」，展开会把整夹（含限制目录）全部送去外传。")
    lines.append("")
    lines.append("## 4. 发现的问题")
    lines.append("")
    lines.append("- `问题反馈\\20261118_T12_样本中拿掉的外传风险与横屏.md`：必选里拿掉的嘉贝乐、美女人设和横屏（含试标 2 条）。")
    lines.append("")
    lines.append("## 5. 产出文件清单")
    lines.append("")
    lines.append("- `上传清单.csv`")
    lines.append("- `短于4秒清单.csv`")
    lines.append("- `拿掉清单.csv`")
    lines.append("- `编号对应表.csv`")
    lines.append("- `副本\\t12_XXXX.mp4`")
    lines.append("- `测试计划与费用预估.md`")
    lines.append("- `准备阶段回报.md`（本文件）")
    lines.append("- `统计\\选样统计.json`")
    lines.append("- `统计\\转码进度.jsonl`、`统计\\转码结果.json`、`统计\\转码控制台.log`（若已跑转码）")
    lines.append("- `统计\\共享盘只读快照_转码前.json`、`统计\\共享盘只读快照_转码后.json`、`统计\\共享盘快照对比.json`（若已收工）")
    lines.append("- `脚本\\t12_lib.py`、`t12_select.py`、`t12_transcode.py`、`t12_write_docs.py`")
    lines.append("")
    lines.append("## 6. 花了多少")
    lines.append("")
    lines.append(f"- 选样：脚本一次读片段库和清单，约数秒到十几秒。")
    lines.append(f"- 最慢的一步：从共享盘只读转码。{spent_time}")
    lines.append("- 需要人的地方：李康看上传清单和本计划，填写账号后台额度，决定短于 4 秒是否拼接，明确说是否「可以传」。付费与否只能由他决定。")
    lines.append("- 花了多少钱：0。")
    path = OUT_ROOT / "准备阶段回报.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_problem(dropped_rows: list[dict]):
    PROBLEM_DIR.mkdir(parents=True, exist_ok=True)
    unique = {}
    for r in dropped_rows:
        unique.setdefault(r["原片ID"], r)
    lines = []
    lines.append("# 问题：T12 样本中拿掉的外传风险与横屏")
    lines.append("")
    lines.append("日期：2026-11-18（Asia/Shanghai）")
    lines.append("任务：T12 准备阶段 / 20261118_01")
    lines.append("")
    lines.append("按任务书「样本里发现不该外传的内容要从清单拿掉并上报」，以及排除横屏、禁用表、可用状态不正常、重复组副本、T01 已确认不能用的 30 条。")
    lines.append("本单只记录**必选范围**（事实层范围内落到文件的视频、试标 50 段所在视频）里被拿掉的条目。补充抽样一开始就把这类路径排除在外。")
    lines.append("共享盘原文件没有删除、没有改动。")
    lines.append("")
    lines.append(f"拿掉清单行数 {len(dropped_rows)}（同一视频若既在事实层又在试标，会写两行），去重视频 {len(unique)} 个。明细在 `工位产出\\T12\\20261118_01\\拿掉清单.csv`。")
    lines.append("")
    lines.append("分类（按去重视频，一条只归一类）：")
    jbl = [r for r in unique.values() if "嘉贝乐" in (r.get("拿掉原因") or "")]
    mei = [r for r in unique.values() if "嘉贝乐" not in (r.get("拿掉原因") or "") and ("美女人设" in (r.get("拿掉原因") or "") or "禁用表" in (r.get("拿掉原因") or ""))]
    heng = [r for r in unique.values() if "画幅" in (r.get("拿掉原因") or "")]
    lines.append(f"- 嘉贝乐（不该外传）：{len(jbl)} 个")
    lines.append(f"- 美女人设 / 禁用人物出镜：{len(mei)} 个")
    lines.append(f"- 原片表画幅为横：{len(heng)} 个（其中 2 个同时也是试标 50 段所在视频：`珞珈山花园小区\\施工视频\\续1\\26054_小区场景.MOV`、`武汉理工大学\\滚底漆\\32487_小区场景.MOV`）。T02 曾把部分横倒竖拍转正，本批仍按原片表「横屏排除」执行，没有改原片表，也没有例外放行。）")
    lines.append("")
    lines.append("T01 已确认不能用的 30 条（20 条 moov 缺失 + 10 条蔡甸 3–8KB）已作为排除条件；这 30 条没有进入上传清单。原先超时、后来读出的 2 条横屏没有当作清理对象，它们若出现也会因横屏被排除。")
    lines.append("")
    lines.append("请李康知悉：这批被拿掉的视频不会传到 Twelve Labs。若他认为其中某条其实可以外传，应在说「可以传」之前书面指定，准备阶段不会自行加回。")
    path = PROBLEM_DIR / "20261118_T12_样本中拿掉的外传风险与横屏.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main():
    sel = load_json(OUT_ROOT / "统计" / "选样统计.json")
    tr_path = OUT_ROOT / "统计" / "转码结果.json"
    tr = load_json(tr_path) if tr_path.exists() else None
    snap_path = OUT_ROOT / "统计" / "共享盘快照对比.json"
    snap = load_json(snap_path) if snap_path.exists() else None
    dropped_path = OUT_ROOT / "拿掉清单.csv"
    with dropped_path.open(encoding="utf-8-sig", newline="") as f:
        dropped_rows = list(csv.DictReader(f))
    p1 = write_plan(sel, tr)
    p2 = write_report(sel, tr, dropped_rows, snap)
    p3 = write_problem(dropped_rows)
    print("wrote", p1, flush=True)
    print("wrote", p2, flush=True)
    print("wrote", p3, flush=True)
    if tr is None:
        print("转码结果尚未落地，计划和回报里转码数字仍标未完成。", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
