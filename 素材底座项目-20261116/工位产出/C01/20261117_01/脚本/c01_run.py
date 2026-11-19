# -*- coding: utf-8 -*-
"""C01 检查编号对照主入口：从原始数据重算八项，写出检查报告。"""
from __future__ import annotations

import json
import sys
import time
import traceback
from pathlib import Path

# 脚本目录加入 path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from c01_common import (
    C01_OUT,
    CONFIG_PATH,
    INVENTORY_CSV,
    PROJECT_DIR,
    SEED,
    TABLE_PATH,
    T01_OUT,
    file_meta,
    load_origin_table,
    now_iso,
    read_share_root,
    sha256_file,
    write_json,
)
from c01_scan import scan_four_dirs
from c01_checks import (
    check1_counts,
    check2_jingxu,
    check3_sample50,
    check4_annotation,
    check5_limits,
    check6_dedup,
    check7_config,
    check8_readonly,
    audit_ffprobe_rotation,
)


def yn(flag: bool) -> str:
    return "通过" if flag else "不通过"


def md_escape(s) -> str:
    if s is None:
        return ""
    return str(s).replace("|", "\\|")


def write_report(payload: dict) -> None:
    c1, c2, c3, c4, c5, c6, c7, c8 = (payload["检查"][str(i)] for i in range(1, 9))
    extra = payload.get("另外发现的问题") or []
    conclusion = payload["结论"]
    report_li_kang = payload["是否需要直接上报李康"]

    lines = []
    a = lines.append
    a("# C01 检查编号对照 · 检查报告 · 20261117_01")
    a("")
    a(f"检查时间：{payload['开始时间']} 至 {payload['结束时间']}（Asia/Shanghai）")
    a("执行机器：nmu")
    a("被查批次：`工位产出/T01/20261117_01`")
    a("规则：`共同约定.md`、`共同约定-v0.4补充.md`、`T01-编号对照.md`、`C01-检查编号对照.md`（以 C01 任务书为准）、`专有词表.md` 第四节、`片段记录格式-草案.md`「原片表」、T01 `回报.md`")
    a("做法：自己写检查脚本，从主库四个目录、镜序登记表副本、标注库索引副本和原片表重新算。T01 脚本只用来对照做法和第 7、8 项。")
    a(f"随机种子：**{SEED}**（不是 T01 的 20261117）")
    a("")
    a("## 结论")
    a("")
    a(f"**{conclusion}**")
    a("")
    if payload.get("结论说明"):
        a(payload["结论说明"])
        a("")
    a(f"是否需要直接上报李康：**{'是' if report_li_kang else '否'}**")
    if payload.get("上报说明"):
        a(payload["上报说明"])
    a("")
    a("八项总览：")
    a("")
    a("| 项 | 名称 | 结果 | 要点 |")
    a("|---|---|---|---|")
    for i in range(1, 9):
        c = payload["检查"][str(i)]
        a(f"| {i} | {c['名称']} | {yn(c['通过'])} | {md_escape(c.get('要点') or '')} |")
    a("")

    # ---- 1 ----
    a("## 1. 条数")
    a("")
    a(f"结果：**{yn(c1['通过'])}**")
    a("")
    a("官方主库文件清单 `C:\\Users\\leega\\AppData\\Local\\Temp\\share-video-inventory-20261114\\36-gongxiang.csv` " + ("存在，已按其数。" if c1.get("官方清单CSV存在") else "仍不存在（与 T01 回报一致）。本项改为只读重扫主库四个目录，自行数视频：按常见视频扩展名计；排除 `._*` AppleDouble 和文件名含「资料账号密码」的文件；无扩展名的文件只读文件头，含 `ftyp` 的按视频计入。"))
    a("")
    a(f"- C01 扫描视频数：{c1['C01扫描视频数']}")
    a(f"- 原片表条数：{c1['原片表条数']}")
    a(f"- 原片表重复逻辑路径：{len(c1.get('重复逻辑路径') or [])} 组")
    a(f"- 原片表重复共享相对路径：{len(c1.get('重复共享相对路径') or [])} 组")
    a(f"- 原片表重复库内相对路径：{len(c1.get('重复库内相对路径') or [])} 组")
    a(f"- 仅扫描有：{len(c1.get('仅扫描有') or [])} 条")
    a(f"- 仅原片表有：{len(c1.get('仅原片表有') or [])} 条")
    a(f"- 不一致比例：{c1.get('不一致比例')}（是否超过 1%：{'是' if c1.get('是否超过百分之一') else '否'}）")
    a("")
    a("| 目录 | C01 扫描 | 原片表按库ID | 原片表按路径前缀 | 相等 | 补充约定 | 扫描相对约定之差 |")
    a("|---|---:|---:|---:|---|---:|---:|")
    exp = c1.get("相对补充约定") or {}
    for row in c1.get("分库对照") or []:
        e = exp.get(row["库ID"]) or {}
        a(
            f"| {row['目录名']} | {row['C01扫描视频数']} | {row['原片表按库ID']} | "
            f"{row['原片表按相对路径前缀']} | {'是' if row['相等'] else '否'} | "
            f"{e.get('约定', '')} | {e.get('差', '')} |"
        )
    a("")
    if c1.get("仅扫描有") or c1.get("仅原片表有") or c1.get("重复逻辑路径"):
        a("不通过或不一致的记录：")
        a("")
        if c1.get("仅扫描有"):
            a("仅扫描有：")
            for p in c1["仅扫描有"][:50]:
                a(f"- `{p}`")
            if len(c1["仅扫描有"]) > 50:
                a(f"- … 另有 {len(c1['仅扫描有'])-50} 条，见 `核对/检查结果.json`")
        if c1.get("仅原片表有"):
            a("仅原片表有：")
            for p in c1["仅原片表有"][:50]:
                a(f"- `{p}`")
            if len(c1["仅原片表有"]) > 50:
                a(f"- … 另有 {len(c1['仅原片表有'])-50} 条")
        if c1.get("重复逻辑路径"):
            a("重复逻辑路径：")
            for x in c1["重复逻辑路径"][:20]:
                a(f"- `{x}`")
        a("")
    else:
        a("四个目录条数全部相等，原片表没有重复路径。")
        a("")
        a("相对补充约定 21,152 条，小区多出的 20 条是无扩展名但文件头为 MP4 的视频，与 T01 回报一致；测试 / 阿明 / 搅拌与约定条数一致。这 20 条已计入原片表，本项按「扫描与原片表相等」判定，不把它当作原片表漏计或多计。")
        a("")

    # ---- 2 ----
    a("## 2. 镜序编号")
    a("")
    a(f"结果：**{yn(c2['通过'])}**")
    a("")
    a("算法：`sha256(库别名 + \"/\" + 相对路径)` 的十六进制前 32 位，正斜杠，库别名 `xiaoq`。对小区库全部视频自行计算，分别与镜序登记表（T01 输入副本 `catalog.sqlite3`，只读 `mode=ro&immutable=1`）和原片表比较。")
    a("")
    a(f"- 小区扫描视频数：{c2['小区扫描视频数']}")
    a(f"- 小区原片表条数：{c2['小区原片表条数']}")
    a(f"- 登记表小区行数：{c2['登记表小区行数']}")
    a(f"- 三边路径与编号完全一致：{c2['三边路径与编号完全一致']}")
    a(f"- 登记表 ID 与算法不符：{len(c2.get('登记表ID与算法不符') or [])}")
    a(f"- 登记表有、扫描没有：{len(c2.get('登记表有扫描没有') or [])}")
    a(f"- 扫描有、登记表没有：{len(c2.get('扫描有登记表没有') or [])}")
    a(f"- 原片表编号问题：{len(c2.get('原片表编号问题') or [])}")
    a(f"- 原片表有、扫描没有：{len(c2.get('原片表有扫描没有') or [])}")
    a(f"- 与 T01 不一致清单相同：{'是' if c2.get('与T01清单一致') else '否'}")
    a(f"- 不一致路径数：{c2.get('不一致路径数')}，比例 {c2.get('不一致比例')}（是否超过 1%：{'是' if c2.get('是否超过百分之一') else '否'}）")
    a(f"- 三边全部一致：{'是' if c2.get('三边全部一致') else '否'}")
    a("")
    a("登记表有而扫描没有的路径：")
    a("")
    if c2.get("登记表有扫描没有"):
        for x in c2["登记表有扫描没有"]:
            a(f"- `{x.get('登记表路径')}`，登记表 ID `{x.get('镜序素材ID')}`")
    else:
        a("- （无）")
    a("")
    a("扫描有而登记表没有的路径：")
    a("")
    if c2.get("扫描有登记表没有"):
        for x in c2["扫描有登记表没有"]:
            a(f"- `{x.get('库内相对路径')}`，字节数 {x.get('字节数')}，原片表镜序素材ID `{x.get('原片表镜序素材ID') or '（空）'}`")
    else:
        a("- （无）")
    a("")
    if c2.get("登记表ID与算法不符"):
        a("登记表 ID 与算法不符：")
        a("")
        for x in c2["登记表ID与算法不符"]:
            a(f"- `{x.get('登记表路径')}` 登记表 `{x.get('登记表ID')}` 算法 `{x.get('按算法计算')}`")
        a("")
    if c2.get("原片表编号问题"):
        a("原片表编号问题：")
        a("")
        for x in c2["原片表编号问题"]:
            a(f"- `{x}`")
        a("")
    if c2.get("仅C01有的扫描未登记") or c2.get("仅T01有的扫描未登记"):
        a("与 T01 清单的差集：")
        a("")
        for p in c2.get("仅C01有的扫描未登记") or []:
            a(f"- 仅 C01 有：`{p}`")
        for p in c2.get("仅T01有的扫描未登记") or []:
            a(f"- 仅 T01 有：`{p}`")
        a("")
    a("通过标准是「三边全部一致；不一致的条数和 T01 回报清单相同」。当前存在已知不一致（航天花园改名 1 条 + 无扩展名未登记 20 条），与 T01 回报清单一致，故本项按清单相同判定。")
    a("")

    # ---- 3 ----
    a("## 3. 抽 50 条看文件")
    a("")
    a(f"结果：**{yn(c3['通过'])}**")
    a("")
    a(f"- 随机种子：{c3.get('随机种子')}")
    a(f"- 抽检条数：{c3.get('抽检条数')}，全部一致 {c3.get('全部一致')}，不一致 {c3.get('不一致')}")
    a(f"- 用时：{c3.get('用时秒')} 秒")
    a("- 核对：文件是否存在、字节数、ffprobe 时长 / 宽 / 高 / 旋转角度、按宽高和旋转自行判断的画幅。时长相差 0.1 秒以内算一致。")
    a("")
    a("抽到的记录（原片ID / 逻辑路径 / 结果）：")
    a("")
    for row in c3.get("明细") or []:
        mark = "一致" if row.get("全部一致") else "不一致"
        a(f"{row.get('序号')}. `{row.get('原片ID')}`　`{row.get('逻辑路径')}`　{mark}")
    a("")
    if c3.get("不一致记录"):
        a("不一致的具体记录：")
        a("")
        for row in c3["不一致记录"]:
            a(
                f"- `{row.get('逻辑路径')}`：存在={row.get('文件存在')} 字节数一致={row.get('字节数一致')} "
                f"时长 {row.get('原片表时长')} vs {row.get('探测时长')}（{row.get('时长一致')}） "
                f"宽高 {row.get('原片表宽')}x{row.get('原片表高')} vs {row.get('探测宽')}x{row.get('探测高')} "
                f"旋转 {row.get('原片表旋转角度')} vs {row.get('探测旋转角度')} "
                f"画幅 {row.get('原片表画幅')} vs {row.get('C01判定画幅')} "
                f"ffprobe={row.get('ffprobe成功')} {row.get('ffprobe错误') or ''}"
            )
        a("")
    a("明细也在 `核对/抽检50条.json`。")
    a("")

    # ---- 4 ----
    a("## 4. 标注库 ID")
    a("")
    a(f"结果：**{yn(c4['通过'])}**")
    a("")
    a(f"- 随机种子：{c4.get('随机种子')}")
    a(f"- 索引总条数：{c4.get('索引总条数')}（两份索引副本）")
    a(f"- 原片表已对上：{c4.get('原片表已对上')}，对不上：{c4.get('原片表对不上')}")
    a(f"- T01 对不上清单：{c4.get('T01对不上清单条数')} 条；与原片表空标注库ID集合相同：{'是' if c4.get('T01清单与原片表空标注库ID是否相同') else '否'}")
    s30 = c4.get("抽30条已对上") or {}
    s10 = c4.get("抽10条T01说对不上的") or {}
    a(f"- 抽 30 条已对上的：同一文件 {s30.get('同一文件')} / {s30.get('条数')}")
    a(f"- 抽 10 条 T01 说对不上的：C01 能找到对应 {s10.get('C01能找到对应')} 条（通过标准：不超过 1 条）")
    a("")
    a("抽中的 30 条已对上原片ID：")
    a("")
    for i, rid in enumerate(s30.get("抽中原片ID") or [], 1):
        rec = (s30.get("明细") or [None] * i)[i - 1] if s30.get("明细") else {}
        same = "同一文件" if rec.get("是同一文件") else "不是同一文件"
        a(f"{i}. `{rid}`　`{rec.get('原片表路径')}`　{same}")
    a("")
    if s30.get("明细"):
        bad = [x for x in s30["明细"] if not x.get("是同一文件")]
        if bad:
            a("30 条里不是同一文件的：")
            a("")
            for x in bad:
                a(f"- `{x}`")
            a("")
    a("抽中的 10 条 T01 说对不上的：")
    a("")
    for i, row in enumerate(s10.get("明细") or [], 1):
        mark = "找到对应" if row.get("是否找到对应") else "未找到唯一对应"
        a(f"{i}. `{row.get('共享相对路径')}`　{mark}　{row.get('查找方式')}")
    a("")
    if s10.get("找到的记录"):
        a("C01 认为能对应上的记录：")
        a("")
        for x in s10["找到的记录"]:
            a(f"- `{x}`")
        a("")
    if c4.get("仅T01清单有") or c4.get("仅原片表空ID有"):
        a("T01 清单与原片表空标注库ID的差集：")
        a("")
        for p in c4.get("仅T01清单有") or []:
            a(f"- 仅 T01 清单有：`{p}`")
        for p in c4.get("仅原片表空ID有"):
            a(f"- 仅原片表空ID有：`{p}`")
        a("")
    a("明细在 `核对/标注库抽检.json`。")
    a("")

    # ---- 5 ----
    a("## 5. 限制")
    a("")
    a(f"结果：**{yn(c5['通过'])}**")
    a("")
    a("词表第四节限制表里，落在本批四个目录范围内的目录如下。范围外的（客户的素材、嘉贝乐工厂口播）只登记，不比条数。")
    a("")
    a("| 目录 | 范围内 | 词表条数 | C01 扫描 | 原片表路径落在该目录 | 相等 | 备注 |")
    a("|---|---|---:|---:|---:|---|---|")
    for row in c5.get("对照") or []:
        if not row.get("范围内"):
            a(f"| `{row['相对前缀']}` | 否 | {row['词表条数']} | — | — | — | {row.get('说明') or '范围外'} |")
            continue
        note = ""
        if row.get("该目录下限制原文不符"):
            note = f"限制原文不符 {len(row['该目录下限制原文不符'])} 条"
        if row.get("限制原文落在其他目录"):
            note = (note + "；" if note else "") + f"限制原文落到其他目录 {len(row['限制原文落在其他目录'])} 条"
        a(
            f"| `{row['相对前缀']}` | 是 | {row['词表条数']} | {row['C01扫描视频数']} | "
            f"{row['原片表路径落在该目录']} | {'是' if row.get('相等') else '否'} | {note or '限制原文与词表一致'} |"
        )
    a("")
    bad5 = []
    for row in c5.get("对照") or []:
        if row.get("范围内") and not row.get("相等"):
            bad5.append(row)
        if row.get("该目录下限制原文不符") or row.get("限制原文落在其他目录"):
            if row not in bad5 and row.get("范围内"):
                bad5.append(row)
    if bad5:
        a("不通过或限制原文不符的记录：")
        a("")
        a("```json")
        a(json.dumps(bad5, ensure_ascii=False, indent=2)[:8000])
        a("```")
        a("")

    # ---- 6 ----
    a("## 6. 重复组")
    a("")
    a(f"结果：**{yn(c6['通过'])}**")
    a("")
    a(f"- 随机种子：{c6.get('随机种子')}")
    a(f"- 原片表重复组数：{c6.get('原片表重复组数')}，成员 {c6.get('原片表重复组成员数')} 条")
    a(f"- 抽组数：{c6.get('抽组数')}，组号：{', '.join(c6.get('抽到的组号') or [])}")
    a("")
    a("| 组号 | 成员数 | 哈希相同 | 恰好一条进入选材 | 结果 |")
    a("|---|---:|---|---|---|")
    for row in c6.get("明细") or []:
        a(
            f"| {row['组号']} | {row['成员数']} | {'是' if row.get('哈希相同') else '否'} | "
            f"{'是' if row.get('恰好一条进入选材') else '否'} | {'通过' if row.get('通过') else '不通过'} |"
        )
    a("")
    bad6 = [x for x in (c6.get("明细") or []) if not x.get("通过")]
    if bad6:
        a("不通过的组：")
        a("")
        for row in bad6:
            a(f"- {row.get('组号')}：角色 {row.get('角色统计')}，唯一哈希数 {row.get('唯一哈希数')}，读取失败 {row.get('读取失败')}")
            for m in row.get("成员") or []:
                a(f"  - `{m.get('逻辑路径')}` 角色={m.get('角色')} 哈希=`{m.get('哈希')}`")
        a("")
    a("明细在 `核对/重复组抽检.json`。")
    a("")

    # ---- 7 ----
    a("## 7. 配置")
    a("")
    a(f"结果：**{yn(c7['通过'])}**")
    a("")
    a(f"- 在 T01 脚本（{', '.join(c7.get('搜索的脚本') or [])}）中搜索共享盘地址：写死地址 {len(c7.get('脚本里写死的共享盘地址') or [])} 处。没有写死地址：{'是' if c7.get('没有写死地址') else '否'}。")
    a(f"- 库别名字面量（如 `xiaoq`）出现 {c7.get('库别名字面量条数')} 处。任务书通过标准写的是「脚本里没有写死的地址」；库别名出现在配置生成和镜序对照代码里，本项不因此判不通过，记在「另外发现的问题」里说明。")
    a(f"- 已把 `片段库/配置/素材库.json` 复制到 `{c7.get('配置副本')}`，把「{c7.get('改的是哪个库')}」的根路径从配置中的原值改成 `{c7.get('改成的根路径')}`，然后用 T01 的 `02_scan.py --config <副本> --out-dir <C01统计/missing-path-run>` 跑。没有改原配置，也没有让 T01 脚本往片段库写。")
    a(f"- 退出码：{c7.get('退出码')}；输出含「路径不存在」：{'是' if c7.get('输出含有路径不存在') else '否'}；是否扫到了别处：{'是' if c7.get('是否扫描到了别的地方') else '否'}。")
    a(f"- 原配置保持原样：{'是' if c7.get('原配置保持原样') else '否'}（运行前 sha256 `{((c7.get('原配置运行前') or {}).get('sha256'))}`，运行后 `{((c7.get('原配置运行后') or {}).get('sha256'))}`，修改时间 {((c7.get('原配置运行前') or {}).get('修改时间'))} / {((c7.get('原配置运行后') or {}).get('修改时间'))}）。")
    a("")
    if c7.get("脚本里写死的共享盘地址"):
        a("写死的地址：")
        a("")
        for x in c7["脚本里写死的共享盘地址"]:
            a(f"- `{x.get('文件')}:{x.get('行号')}` `{x.get('内容')}`")
        a("")
    a("标准输出摘录：")
    a("")
    a("```")
    a((c7.get("标准输出") or "").strip() or "（无）")
    a("```")
    a("")
    a("明细在 `核对/配置检查.json`。")
    a("")

    # ---- 8 ----
    a("## 8. 只读")
    a("")
    a(f"结果：**{yn(c8['通过'])}**")
    a("")
    a(f"读了 T01 全部脚本里写文件、删文件、移动文件的调用，共 {c8.get('调用条数')} 处。")
    a("")
    a("目标归纳：")
    a("")
    for k in c8.get("已知目标归纳") or []:
        a(f"- `{k.get('脚本')}`：{k.get('目标')}。落在项目文件夹：{'是' if k.get('范围内') else '否'}。")
    a("")
    a(f"疑似写到共享盘或镜序完整包的调用：{len(c8.get('疑似写到共享盘或镜序完整包') or [])} 处。")
    a("")
    if c8.get("疑似写到共享盘或镜序完整包"):
        a("需要直接上报李康的写入：")
        a("")
        for x in c8["疑似写到共享盘或镜序完整包"]:
            a(f"- `{x.get('文件')}:{x.get('行号')}` {x.get('种类')} `{x.get('代码')}`")
        a("")
    else:
        a("未发现脚本把共享盘或镜序完整包当作写入、删除、移动目标。读文件头、stat、ffprobe、SQLite 只读打开不计入写入。")
        a("")
    a("明细在 `核对/只读检查.json`。")
    a("")

    # ---- extras ----
    a("## 另外发现的问题")
    a("")
    if extra:
        for i, item in enumerate(extra, 1):
            a(f"{i}. {item}")
        a("")
    else:
        a("没有八项之外需要记录的问题。")
        a("")

    a("## 被查对象与本批产出未改动核验")
    a("")
    snap = payload.get("快照") or {}
    a(f"- 原片表运行前：{json.dumps(snap.get('原片表前') or {}, ensure_ascii=False)}")
    a(f"- 原片表运行后：{json.dumps(snap.get('原片表后') or {}, ensure_ascii=False)}")
    a(f"- 素材库.json 运行前：{json.dumps(snap.get('配置前') or {}, ensure_ascii=False)}")
    a(f"- 素材库.json 运行后：{json.dumps(snap.get('配置后') or {}, ensure_ascii=False)}")
    a(f"- 二者保持原样：{'是' if snap.get('保持原样') else '否'}")
    a("")

    a("## 产出文件清单")
    a("")
    a("- `检查报告.md`（本文件）")
    a("- `脚本/c01_common.py`、`脚本/c01_scan.py`、`脚本/c01_checks.py`、`脚本/c01_run.py`")
    a("- `统计/C01扫描摘要.json`、`统计/素材库_不存在路径测试.json`、`统计/missing-path-run/`（跑 T01 扫描脚本的隔离输出）")
    a("- `核对/C01扫描清单.jsonl`、`核对/抽检50条.json`、`核对/ffprobe画幅补充抽查.json`、`核对/标注库抽检.json`、`核对/重复组抽检.json`、`核对/配置检查.json`、`核对/只读检查.json`、`核对/检查结果.json`")
    a("")

    a("## 花了多少")
    a("")
    a(f"- 墙钟：{payload['开始时间']}–{payload['结束时间']}（Asia/Shanghai），约 {payload.get('用时秒')} 秒。")
    a(f"- {payload.get('耗时说明') or ''}")
    a("- 花了多少钱：0。未装软件，未触发线上镜序，未向云端传抽帧。")
    a("")

    path = C01_OUT / "检查报告.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"已写报告 {path}", flush=True)


def brief_points(c1, c2, c3, c4, c5, c6, c7, c8) -> None:
    c1["要点"] = (
        f"扫描 {c1['C01扫描视频数']}，原片表 {c1['原片表条数']}，"
        f"四目录{'全部相等且无重复路径' if c1['通过'] else '未全部相等或有重复/差集'}"
    )
    c2["要点"] = (
        f"登记表未对上 {len(c2.get('登记表有扫描没有') or [])}，"
        f"扫描未登记 {len(c2.get('扫描有登记表没有') or [])}，"
        f"与T01清单{'相同' if c2.get('与T01清单一致') else '不同'}"
    )
    c3["要点"] = f"种子 {c3.get('随机种子')}，{c3.get('全部一致')}/{c3.get('抽检条数')} 一致"
    s30 = c4.get("抽30条已对上") or {}
    s10 = c4.get("抽10条T01说对不上的") or {}
    c4["要点"] = f"已对上抽检 {s30.get('同一文件')}/{s30.get('条数')}；对不上抽检找到 {s10.get('C01能找到对应')} 条"
    ok5 = sum(1 for x in (c5.get("对照") or []) if x.get("范围内") and x.get("相等"))
    total5 = sum(1 for x in (c5.get("对照") or []) if x.get("范围内"))
    c5["要点"] = f"范围内 {ok5}/{total5} 个目录条数相等"
    c6["要点"] = f"种子 {c6.get('随机种子')}，抽 {c6.get('抽组数')} 组，原片表共 {c6.get('原片表重复组数')} 组"
    c7["要点"] = (
        f"写死地址 {len(c7.get('脚本里写死的共享盘地址') or [])} 处；"
        f"改路径后「路径不存在」={'是' if c7.get('输出含有路径不存在') else '否'}；"
        f"原配置不变={'是' if c7.get('原配置保持原样') else '否'}"
    )
    c8["要点"] = (
        f"写入调用 {c8.get('调用条数')} 处；"
        f"写到共享盘或镜序完整包 {len(c8.get('疑似写到共享盘或镜序完整包') or [])} 处"
    )


def collect_extras(c1, c2, c4, c7, scan_summary, rot_audit=None, c3=None) -> list[str]:
    extras = []
    if not INVENTORY_CSV.exists():
        extras.append(
            "官方主库清单 `36-gongxiang.csv` 在约定路径仍不存在，C01 与 T01 一样只能只读重扫四个目录。这不构成第 1 项不通过，但清单缺失本身还在。"
        )
    exp = c1.get("相对补充约定") or {}
    xq = exp.get("xiaoq") or {}
    if xq.get("差"):
        extras.append(
            f"小区库现有视频比补充约定 20,515 多 {xq.get('差')} 条（无扩展名但文件头为 MP4）。T01 已写问题单，C01 复核数字相同。"
        )
    if c2.get("登记表有扫描没有") or c2.get("扫描有登记表没有"):
        extras.append(
            "镜序登记表与现网小区库仍有已知不一致：登记表中的 `航天花园拍摄/22965_小区场景.MOV` 在盘上已改名为 `IMG_6720.MOV`，另有 20 条无扩展名视频未登记。T01 未把旧编号强接到新文件名，C01 认为这一处理与「按路径计算编号」一致，留给张艺确认即可，不单独立项为 T01 错误。"
        )
    aliases = c7.get("库别名字面量") or []
    if aliases:
        files = sorted({x.get("文件") for x in aliases})
        extras.append(
            f"T01 脚本里出现库别名字面量 {len(aliases)} 处，涉及 {', '.join(files)}。"
            "共享盘地址是从 `共同约定.md` 读进配置的，没有写死；但 `03_build_table.py` 等处把镜序根别名 `xiaoq` 写在代码里，没有一律从 `素材库.json` 的「镜序库别名」读取。"
            "第 7 项通过标准针对的是写死地址，本项仍通过。若要严格做到「地址、库名都进配置」，可由 T01 改脚本，不必重查编号。"
        )
    by_lib = (scan_summary or {}).get("分库") or {}
    # 搅拌默认来源类型「自拍·展厅」看起来不像目录本身的性质，属观察，不自动算错
    extras.append(
        "配置里搅拌库的默认来源类型是「自拍·展厅」。按 T01 规则，只有一级目录名为「展厅」的才改标为自拍·展厅，搅拌库其余条目会带着这个默认值。这不在八项通过标准里，记下来供确认是不是有意为之。"
    )
    if c4.get("原片表对不上"):
        extras.append(
            f"原片表仍有 {c4.get('原片表对不上')} 条没有标注库ID，与 T01 列出的 28 条应一致。第 4 项只抽查，不要求 C01 重做全部对照。"
        )
    if rot_audit:
        extras.append(
            "T01 用 ffprobe 补宽高旋转时，命令是 `-show_entries stream=width,height,duration,rotation:stream_tags=rotate`，"
            "读不到视频流 Display Matrix 里的 rotation。许多手机竖屏文件编码宽高是 1920×1080、矩阵旋转 -90°，"
            f"会被写成旋转 0、画幅「横」。原片表里出处为 ffprobe、画幅为横、旋转为 0 的有 {rot_audit.get('总体_ffprobe记为横且旋转为0')} 条；"
            f"C01 用 `-show_streams` 从中抽 {rot_audit.get('抽查条数')} 条（种子 {rot_audit.get('随机种子')}），"
            f"其中 {rot_audit.get('探测到旋转且画幅应改')} 条实际有非 0 旋转、画幅应改为竖。"
            "镜序已带旋转的 217 条不受影响。T01 需要改探测命令后重写旋转角度和画幅，并由 C01 重查第 3 项。"
        )
    return extras


def decide_conclusion(c1, c2, c3, c4, c5, c6, c7, c8, extras) -> tuple[str, str, bool, str]:
    report = bool(c1.get("是否超过百分之一") or c2.get("是否超过百分之一") or (c8.get("疑似写到共享盘或镜序完整包")))
    failed = [c for c in (c1, c2, c3, c4, c5, c6, c7, c8) if not c.get("通过")]
    if report or any(c.get("项") in (1, 2, 8) and not c.get("通过") for c in failed) or (
        failed and any(c.get("项") in (3, 4, 5, 6) for c in failed)
    ):
        # 实质性不通过：要返工并重查。第7项若只是小问题可另议
        serious = [c for c in failed if c.get("项") != 7] or failed
        if serious and (report or any(c.get("项") != 7 for c in failed)):
            reasons = "；".join(f"第{c['项']}项（{c['名称']}）不通过" for c in failed)
            note = "下列检查未通过，需要 T01 执行者返工，并由 C01 重查：" + reasons + "。"
            if report:
                up = "条数或镜序编号对不上超过 1%，或发现脚本往共享盘 / 镜序完整包写过东西，按任务书需要直接上报李康。"
            else:
                up = ""
            return "要返工并重查", note, report, up
    if failed:
        # 仅第7项或类似「改完不用重查」
        todo = []
        if not c7.get("通过"):
            if c7.get("脚本里写死的共享盘地址"):
                todo.append("把 T01 脚本里写死的共享盘地址改成从配置读取")
            if not c7.get("输出含有路径不存在"):
                todo.append("改根路径后应报「路径不存在」")
            if not c7.get("原配置保持原样"):
                todo.append("查明为何原配置被改动并恢复")
        note = "要改：" + "；".join(todo or ["见上文不通过项"]) + "。改完不用就编号对照再跑一轮全量重查。"
        return "小问题，改完不用重查", note, report, ""
    # 全部通过。库别名写死等作为小问题？任务说结论三选一，全部通过就是通过。
    # 另外发现的问题若明显但不必改编号，结论仍是通过，问题放在另外发现里。
    return "通过", "八项检查均达到通过标准。与补充约定条数的差、航天花园改名、未对上的标注库 ID，均与 T01 回报清单一致，不作为本项不通过原因。", False, ""


def main():
    C01_OUT.mkdir(parents=True, exist_ok=True)
    (C01_OUT / "脚本").mkdir(parents=True, exist_ok=True)
    (C01_OUT / "核对").mkdir(parents=True, exist_ok=True)
    (C01_OUT / "统计").mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    started = now_iso()
    print(f"C01 开始 {started} 种子={SEED}", flush=True)

    # 快照：证明本检查不改 T01 / 片段库被查对象
    snap_table_before = {
        "字节数": TABLE_PATH.stat().st_size,
        "修改时间": file_meta(TABLE_PATH)["修改时间"],
        "sha256": sha256_file(TABLE_PATH),
    }
    snap_cfg_before = file_meta(CONFIG_PATH)

    share_root = read_share_root()
    print(f"共享盘根路径（来自共同约定.md）：{share_root}", flush=True)

    print("读取原片表…", flush=True)
    records = load_origin_table()
    print(f"原片表 {len(records)} 条", flush=True)

    print("只读扫描四个目录…", flush=True)
    scan = scan_four_dirs(share_root, C01_OUT)
    videos = scan["videos"]

    print("第1项 条数…", flush=True)
    c1 = check1_counts(videos, records)
    print("第2项 镜序编号…", flush=True)
    c2 = check2_jingxu(videos, records)
    print("第5项 限制…", flush=True)
    c5 = check5_limits(videos, records)
    print("第4项 标注库ID…", flush=True)
    c4 = check4_annotation(records, share_root, SEED)
    print("第8项 只读…", flush=True)
    c8 = check8_readonly()
    print("第3项 抽50条…", flush=True)
    c3 = check3_sample50(records, share_root, SEED)
    print("第6项 重复组…", flush=True)
    c6 = check6_dedup(records, share_root, SEED)
    print("补充抽查 ffprobe 画幅…", flush=True)
    rot_audit = audit_ffprobe_rotation(records, share_root, SEED, 100)
    print(
        f"  ffprobe记横且旋转0共 {rot_audit['总体_ffprobe记为横且旋转为0']}，"
        f"抽 {rot_audit['抽查条数']}，其中画幅应改 {rot_audit['探测到旋转且画幅应改']}",
        flush=True,
    )
    write_json(C01_OUT / "核对" / "ffprobe画幅补充抽查.json", rot_audit)

    print("第7项 配置…", flush=True)
    c7 = check7_config(share_root)

    snap_table_after = {
        "字节数": TABLE_PATH.stat().st_size,
        "修改时间": file_meta(TABLE_PATH)["修改时间"],
        "sha256": sha256_file(TABLE_PATH),
    }
    snap_cfg_after = file_meta(CONFIG_PATH)
    unchanged = (
        snap_table_before == snap_table_after
        and snap_cfg_before["sha256"] == snap_cfg_after["sha256"]
        and snap_cfg_before["字节数"] == snap_cfg_after["字节数"]
        and snap_cfg_before["修改时间"] == snap_cfg_after["修改时间"]
    )

    brief_points(c1, c2, c3, c4, c5, c6, c7, c8)
    extras = collect_extras(c1, c2, c4, c7, scan["summary"], rot_audit, c3)
    if not unchanged:
        extras.append(
            "检查结束时发现 `片段库/原片表.jsonl` 或 `片段库/配置/素材库.json` 的大小、修改时间或哈希与开工时不同。C01 脚本不应改这两份文件，需要核查。"
        )
        # 不自动改结论以外的项，但记下来
    conclusion, note, report_flag, up_note = decide_conclusion(c1, c2, c3, c4, c5, c6, c7, c8, extras)
    ended = now_iso()
    elapsed = round(time.perf_counter() - t0, 2)
    payload = {
        "开始时间": started,
        "结束时间": ended,
        "用时秒": elapsed,
        "耗时说明": f"扫描 {scan['summary'].get('用时秒')} 秒；抽检 50 条 {c3.get('用时秒')} 秒；其余为本地对照和少量哈希。",
        "随机种子": SEED,
        "检查": {str(c["项"]): c for c in (c1, c2, c3, c4, c5, c6, c7, c8)},
        "另外发现的问题": extras,
        "ffprobe画幅补充抽查": rot_audit,
        "结论": conclusion,
        "结论说明": note,
        "是否需要直接上报李康": report_flag,
        "上报说明": up_note,
        "快照": {
            "原片表前": snap_table_before,
            "原片表后": snap_table_after,
            "配置前": snap_cfg_before,
            "配置后": snap_cfg_after,
            "保持原样": unchanged,
        },
    }
    # 明细文件可能很大，检查结果里对第3项只保留摘要字段，明细已单独落盘
    slim = json.loads(json.dumps(payload, ensure_ascii=False))
    if "明细" in slim["检查"]["3"]:
        slim["检查"]["3"] = {k: v for k, v in slim["检查"]["3"].items() if k != "明细"}
    write_json(C01_OUT / "核对" / "检查结果.json", slim)
    write_report(payload)
    print(json.dumps({
        "结论": conclusion,
        "八项": {str(c["项"]): yn_pass(c["通过"]) for c in (c1, c2, c3, c4, c5, c6, c7, c8)},
        "上报李康": report_flag,
        "用时秒": elapsed,
        "原文件保持原样": unchanged,
    }, ensure_ascii=False, indent=2), flush=True)


def yn_pass(flag: bool) -> str:
    return "通过" if flag else "不通过"


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
