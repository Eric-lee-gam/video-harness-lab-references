# -*- coding: utf-8 -*-
"""T12 Pegasus 1.6 labeling on trial-50 windows only. Stdlib only. Never log the API key."""
from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

SH = timezone(timedelta(hours=8))
BATCH = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T12\20261118_01")
TRIAL_DIR = Path(r"D:\codex-work\codex-company\video-harness-lab\references\素材标注总纲-20261116\试标50段")
INDEX_ID = "6afd3b33371b8643c700ba73"
MODEL = "pegasus1.6"
PROBE_N = 2
ANALYZE_TIMEOUT = 300.0
MIN_WINDOW = 1.0

sys.path.insert(0, str(BATCH / "脚本"))
from t12_api import (  # noqa: E402
    ApiError,
    QuotaError,
    TwelveClient,
    _interesting_headers,
    key_status_label,
    redact_obj,
    redact_text,
)

PROMPT = """请只根据这段视频里当前分析时间范围内的画面，按照下面的「画面类型」定义，选出一个最合适的画面类型代码。
只能从下列代码里选一个，代码和类型名称必须原样使用。看不出来就选 V00（看不清），不要猜。

规则：
1. 只写看得见的。不判断人是谁，不判断材料的品名，不推测这是哪一户。
2. 只能从给出的选项里选。
3. 看不出来就选 V00。有一点线索但不够定下来，也选 V00。
4. 不要根据文件名或来源推测。

一段里前后不一样时：
- 动作变了：按占比多的填。一样多时，按和画面类型对应的那个填。
- 镜头连续地从一处移到另一处（跟拍、横移、摇）：不算换镜头。
- 画面里有几个人各做各的：先定画面类型，再按撑起这个类型的那个人来理解。例如前面的人对镜头讲话、后面的人在干活，类型是人物对镜头。

画面类型（单选）：
- V01 人物对镜头：人是主体，看着镜头说话或示意。人在成品房间里、工地里、室外都算。
- V24 人物在现场（不看镜头）：人在旧房或施工现场里走动、查看、比划，不看镜头，也没有和别人明显互动。
- V02 握手/与客户沟通：人已经在屋里站定：握手、面对面交谈、一起低头看图纸、样板或同一样东西。
- V03 团队上门/搬料搬物：人员进小区、上楼、进门；几个人站在门口或过道往房间里看；搬材料桶、工具、家具；开工前清空住户的物品。只有一个人也算。
- V04 量房/水电/安装：用卷尺或测距仪测量；水电作业；安装洁具、灯具、柜体。
- V05 施工·批刮覆盖：用刮板、批刀、抹子、小铲刀往墙面或地面上加料，包括补缝、补裂。拿着带料的工具站在施工面前也算，不要求每一刻都在抹。
- V06 施工·滚涂：用滚筒或刷子往墙面或地面上涂。
- V07 铲修旧墙/旧顶：往下铲墙皮、旧涂层。
- V08 拆砸/贴砖：砸墙、拆瓷砖、拆洁具、拆橱柜；把拆下来的东西往外搬；贴瓷砖。
- V09 铺保护膜/贴胶带：铺地膜、包家具、贴美纹纸。
- V10 保洁/清扫（施工前后）：施工现场的扫地、吸尘、清垃圾、用布擦地。
- V11 材料桶（取料/搅拌/桶特写）：画面主体是料桶：开桶、倒料、搅拌、从桶里取料、桶的特写。
- V23 施工现场·其他：看得出是施工现场，但不属于上面任何一种。包括：打磨；现场全貌；贴了胶带保护膜或做了一半、没人干活的现场；有人在干活但看不清在干什么；一只手伸进施工现场比划。
- V12 旧房旧态：还没动工的旧房间、旧瓷砖、污渍、破损，画面里没有人。
- V13 成品空间（空镜）：面层已经做完的空间或表面，画面里没有人。摆着家具日用品也算；顶上还吊着线、边角没收口也算。
- V14 旧→新同镜转场：同一段里同一机位从旧状变到新状。
- V15 成品里的人：做完的空间里有人在看、摸、走、生活，不看镜头。
- V16 手摸/手指成品：画面主体是手和做完的表面：摸、敲、指、比划。
- V17 成品日常清洁：入住后拖地、擦洗做完的表面。
- V18 演示·喷水冲洗：往表面喷水、冲水、泼水做演示。
- V19 演示·弯折样板/揭薄层：弯折样板，或揭起一层薄料做演示。
- V20 演示·刮擦/擦污：用硬物刮、用布擦污渍做演示。
- V21 老楼/城市外景：楼栋外观、小区、街道、城市地标，人不是主体。
- V22 其他：看得清，但以上都不是。
- V00 看不清：连是不是施工现场、有没有人都看不出。

两类都像的时候，按下面的顺序定，先对上的算：
1. 有人看着镜头说话或示意，而且是画面主体：人物对镜头。
2. 有人在施工，工具看得清：选对应的施工类（V04 到 V11）。
3. 有人在施工，工具或动作看不清：施工现场·其他。不要按猜的工具去选批刮、滚涂或清扫。
4. 画面主体是一只手和一个表面：表面是做完的选手摸/手指成品，是施工现场选施工现场·其他。
5. 几个人之间有互动：按上表 V02、V03 的写法分。
6. 有人但没有施工、没有互动、不看镜头：做完的空间选成品里的人，旧房或施工现场选人物在现场。
7. 没有人：旧的选旧房旧态，做完的选成品空间，做了一半或贴着保护的选施工现场·其他。

容易混的：
- 批刮 / 铲修：往面上加料是批刮（含补缝补裂），往下铲东西是铲修。
- 批刮 / 滚涂：看工具：刮板、批刀、抹子是批刮，滚筒、刷子是滚涂。
- 批刮 / 材料桶：工具在桶里是材料桶，工具在墙面地面上是批刮。
- 拆砸 / 搬料搬物：搬的是拆下来的废料、旧柜体，算拆砸；搬的是材料、工具、住户的东西，算搬料搬物。
- 保洁清扫 / 成品日常清洁：施工现场的清理是保洁，住进去以后的拖地擦洗是日常清洁。

请只给出一个画面类型代码和对应的类型名称。
"""

TYPE_NAMES = {
    "V01": "人物对镜头",
    "V24": "人物在现场（不看镜头）",
    "V02": "握手/与客户沟通",
    "V03": "团队上门/搬料搬物",
    "V04": "量房/水电/安装",
    "V05": "施工·批刮覆盖",
    "V06": "施工·滚涂",
    "V07": "铲修旧墙/旧顶",
    "V08": "拆砸/贴砖",
    "V09": "铺保护膜/贴胶带",
    "V10": "保洁/清扫（施工前后）",
    "V11": "材料桶（取料/搅拌/桶特写）",
    "V23": "施工现场·其他",
    "V12": "旧房旧态",
    "V13": "成品空间（空镜）",
    "V14": "旧→新同镜转场",
    "V15": "成品里的人",
    "V16": "手摸/手指成品",
    "V17": "成品日常清洁",
    "V18": "演示·喷水冲洗",
    "V19": "演示·弯折样板/揭薄层",
    "V20": "演示·刮擦/擦污",
    "V21": "老楼/城市外景",
    "V22": "其他",
    "V00": "看不清",
}

CODE_RE = re.compile(r"\b(V(?:00|1[0-9]|2[0-4]|0[1-9]))\b", re.I)


def now_iso() -> str:
    return datetime.now(SH).strftime("%Y-%m-%d %H:%M:%S") + " Asia/Shanghai"


def now_iso8601() -> str:
    return datetime.now(SH).isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"[{now_iso()}] {msg}"
    print(line, flush=True)
    log_path = BATCH / "统计" / "Pegasus控制台.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def norm_path(p: str) -> str:
    return str(p or "").replace("/", "\\").strip().lower()


def load_jobs() -> list[dict]:
    idmap = list(csv.DictReader((BATCH / "编号对应表.csv").open(encoding="utf-8-sig")))
    by_path = {norm_path(r["主库相对路径"]): r for r in idmap}
    concat_rows = list(csv.DictReader((BATCH / "拼接清单_重编码.csv").open(encoding="utf-8-sig")))
    concat_by_copy = {r["副本文件名"]: r for r in concat_rows}
    last = {}
    for line in (BATCH / "统计" / "上传进度.jsonl").open(encoding="utf-8"):
        if not line.strip():
            continue
        ev = json.loads(line)
        name = ev.get("local_name")
        if name:
            last[name] = ev
    removed = list(csv.DictReader((BATCH / "拿掉清单.csv").open(encoding="utf-8-sig")))
    removed_paths = {norm_path(r["主库相对路径"]): r for r in removed}
    audit_raw = json.loads((TRIAL_DIR / "审核结果_李康_20261116.json").read_text(encoding="utf-8"))
    audit = {r["seg"]: r for r in audit_raw["结果"]}
    trial = list(csv.DictReader((TRIAL_DIR / "_对应表.csv").open(encoding="utf-8-sig")))
    jobs = []
    for t in trial:
        seg = t["seg"]
        path = t["原片"]
        start = float(t["起始秒"])
        end = float(t["结束秒"])
        a = audit[seg]
        gold = a.get("fix") if a.get("verdict") == "错" else a.get("机器画面类型")
        rec = by_path.get(norm_path(path))
        job = {
            "seg": seg,
            "原片": path,
            "原起始秒": start,
            "原结束秒": end,
            "审定画面类型": gold,
            "审核verdict": a.get("verdict"),
        }
        if rec is None:
            rm = removed_paths.get(norm_path(path)) or {}
            job.update({"状态": "跳过_未上传", "跳过原因": rm.get("拿掉原因") or "未在上传清单中"})
            jobs.append(job)
            continue
        copy = rec["文件名"]
        short = rec.get("是否短于4秒") in {"是", "1", "true", "True", "Y"}
        job["副本文件名"] = copy
        job["原片ID"] = rec["原片ID"]
        if short or copy in concat_by_copy:
            cr = concat_by_copy.get(copy)
            if not cr:
                job.update({"状态": "跳过_短片无合成", "跳过原因": "短于4秒但没有合成记录"})
                jobs.append(job)
                continue
            cname = cr["合成文件名"]
            c0 = float(cr["合成内起始秒"])
            c1 = float(cr["合成内结束秒"])
            a0 = max(c0, c0 + start)
            a1 = min(c1, c0 + end)
            ev = last.get(cname) or {}
            job.update({
                "上传文件名": cname,
                "分析起始秒": a0,
                "分析结束秒": a1,
                "asset_id": ev.get("asset_id"),
                "upload_status": ev.get("status"),
            })
        else:
            ev = last.get(copy) or {}
            job.update({
                "上传文件名": copy,
                "分析起始秒": start,
                "分析结束秒": end,
                "asset_id": ev.get("asset_id"),
                "upload_status": ev.get("status"),
            })
        dur = float(job.get("分析结束秒") or 0) - float(job.get("分析起始秒") or 0)
        if ev.get("status") != "index_ready" or not ev.get("asset_id"):
            job.update({"状态": "跳过_资产未就绪", "跳过原因": f"upload_status={ev.get('status')}"})
        elif dur < MIN_WINDOW:
            job.update({"状态": "跳过_窗口不足1秒", "跳过原因": f"window={dur}"})
        else:
            job["状态"] = "待分析"
        jobs.append(job)
    return jobs


def last_success(progress_path: Path) -> set[str]:
    done = set()
    if not progress_path.is_file():
        return done
    for line in progress_path.open(encoding="utf-8"):
        if not line.strip():
            continue
        ev = json.loads(line)
        if ev.get("status") == "ok" and ev.get("seg"):
            done.add(ev["seg"])
    return done


def append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def parse_prediction(body) -> tuple[str | None, str | None, object]:
    data = body
    if isinstance(body, dict) and "data" in body:
        data = body.get("data")
    parsed = data
    if isinstance(data, str):
        text = data.strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = data
    code = name = None
    if isinstance(parsed, dict):
        code = parsed.get("画面类型代码") or parsed.get("code") or parsed.get("label")
        name = parsed.get("画面类型") or parsed.get("name") or parsed.get("type")
        if isinstance(code, str):
            code = code.strip().upper()
    if not code and isinstance(data, str):
        m = CODE_RE.search(data)
        if m:
            code = m.group(1).upper()
    if code and not re.fullmatch(r"V\d{2}", code):
        m = CODE_RE.search(str(code))
        code = m.group(1).upper() if m else None
    if code and not name:
        name = TYPE_NAMES.get(code)
    return code, name, parsed


def acquire_lock(lock_path: Path) -> None:
    if lock_path.is_file():
        try:
            info = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            info = {}
        pid = info.get("pid")
        if pid:
            try:
                os.kill(int(pid), 0)
                raise SystemExit(f"已有 Pegasus 进程在跑（PID {pid}），不启动第二个。")
            except OSError:
                pass
            except SystemExit:
                raise
    payload = {"pid": os.getpid(), "started": now_iso8601(), "script": "t12_pegasus.py"}
    lock_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def release_lock(lock_path: Path) -> None:
    try:
        if lock_path.is_file():
            info = json.loads(lock_path.read_text(encoding="utf-8"))
            if info.get("pid") == os.getpid():
                lock_path.unlink()
    except OSError:
        pass


def write_tables(jobs: list[dict], results: list[dict]) -> None:
    by_seg = {r["seg"]: r for r in results}
    rows = []
    for job in jobs:
        ev = by_seg.get(job["seg"], {})
        gold = job.get("审定画面类型") or ""
        pred = ev.get("预测代码") or ""
        status = ev.get("status") or job.get("状态")
        agree = ""
        if ev.get("status") == "ok" and gold and pred:
            agree = "是" if gold == pred else "否"
        rows.append({
            "段号": job["seg"],
            "上传文件名": job.get("上传文件名") or ev.get("上传文件名") or "",
            "分析起始秒": job.get("分析起始秒", ev.get("分析起始秒", "")),
            "分析结束秒": job.get("分析结束秒", ev.get("分析结束秒", "")),
            "审定画面类型": gold,
            "Pegasus画面类型": pred,
            "Pegasus类型名": ev.get("预测名称") or "",
            "是否一致": agree,
            "状态": status,
            "跳过原因": job.get("跳过原因") or ev.get("error") or "",
            "input_tokens": (ev.get("usage") or {}).get("input_tokens", ""),
            "output_tokens": (ev.get("usage") or {}).get("output_tokens", ""),
        })
    path = BATCH / "Pegasus对照表.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def summarize(jobs: list[dict], results: list[dict]) -> dict:
    by_seg = {r["seg"]: r for r in results if r.get("status") == "ok"}
    skipped = [j for j in jobs if str(j.get("状态", "")).startswith("跳过")]
    ok = [r for r in results if r.get("status") == "ok"]
    failed = [r for r in results if r.get("status") == "failed"]
    quota = [r for r in results if r.get("status") == "quota_stop"]
    compared = [r for r in ok if r.get("审定画面类型") and r.get("预测代码")]
    agree = [r for r in compared if r["审定画面类型"] == r["预测代码"]]
    disagree = [r for r in compared if r["审定画面类型"] != r["预测代码"]]
    seconds = 0.0
    for r in ok:
        try:
            seconds += float(r["分析结束秒"]) - float(r["分析起始秒"])
        except (TypeError, ValueError, KeyError):
            pass
    tokens_in = sum((r.get("usage") or {}).get("input_tokens") or 0 for r in ok)
    tokens_out = sum((r.get("usage") or {}).get("output_tokens") or 0 for r in ok)
    return {
        "更新时间": now_iso(),
        "模型": MODEL,
        "index_id": INDEX_ID,
        "计划段数": 50,
        "可分析段数": sum(1 for j in jobs if j.get("状态") == "待分析" or j["seg"] in by_seg),
        "跳过未上传": len(skipped),
        "跳过明细": [{"seg": j["seg"], "原因": j.get("跳过原因")} for j in skipped],
        "成功": len(ok),
        "失败": len(failed),
        "额度停止": bool(quota),
        "已比较": len(compared),
        "一致": len(agree),
        "不一致": len(disagree),
        "不一致段": [{"seg": r["seg"], "审定": r.get("审定画面类型"), "预测": r.get("预测代码")} for r in disagree],
        "成功分析窗口秒": round(seconds, 3),
        "成功分析窗口小时": round(seconds / 3600.0, 6),
        "input_tokens合计": tokens_in,
        "output_tokens合计": tokens_out,
    }


def main() -> int:
    stats_dir = BATCH / "统计"
    stats_dir.mkdir(parents=True, exist_ok=True)
    lock_path = stats_dir / "Pegasus进程.lock"
    progress_path = stats_dir / "Pegasus进度.jsonl"
    state_path = stats_dir / "Pegasus状态.json"
    result_path = BATCH / "Pegasus分析结果.jsonl"

    dry = "--dry-run" in sys.argv
    probe_only = "--probe-only" in sys.argv

    log("======= Pegasus 1.6 打标签测试 =======")
    log(f"密钥: {key_status_label()}")
    if key_status_label() != "已设置" and not dry:
        log("还没有读到密钥，停止。")
        return 2

    jobs = load_jobs()
    pending_all = [j for j in jobs if j.get("状态") == "待分析"]
    pending_all.sort(key=lambda j: (float(j["分析结束秒"]) - float(j["分析起始秒"]), j["seg"]))
    done = last_success(progress_path)
    pending = [j for j in pending_all if j["seg"] not in done]
    skipped = [j for j in jobs if str(j.get("状态", "")).startswith("跳过")]
    log(f"试标 50 段：可分析 {len(pending_all)}，已成功 {len(done)}，待跑 {len(pending)}，跳过 {len(skipped)}")
    for j in skipped:
        log(f"  跳过 {j['seg']}：{j.get('跳过原因')}")
    total_sec = sum(float(j["分析结束秒"]) - float(j["分析起始秒"]) for j in pending)
    log(f"待跑窗口合计 {total_sec:.3f} 秒（{total_sec/3600:.6f} 小时），短窗口优先")
    if dry:
        for j in pending[:10]:
            log(f"  DRY {j['seg']} {j['上传文件名']} {j['分析起始秒']:.3f}-{j['分析结束秒']:.3f}")
        log("dry-run 结束，未调用分析接口。")
        return 0

    acquire_lock(lock_path)
    client = None
    quota_stopped = False
    results: list[dict] = []
    if result_path.is_file():
        for line in result_path.open(encoding="utf-8"):
            if line.strip():
                ev = json.loads(line)
                if ev.get("status") == "ok":
                    results.append(ev)
    started = now_iso()
    try:
        client = TwelveClient(timeout=ANALYZE_TIMEOUT)
        log(f"代理: {client._proxy_label or '未检测到，将直连（上次直连曾 403）'}")
        # schedule: first-time probe then continue
        queue = list(pending)
        if probe_only:
            queue = queue[:PROBE_N]
            log(f"仅探路 {len(queue)} 条")
        elif done:
            log("检测到可续跑进度，跳过已成功条目，不再重复分析。")
        else:
            log(f"先探路 {min(PROBE_N, len(queue))} 条短窗口，成功后再继续其余。")

        ran = 0
        probe_ok = 0
        for job in queue:
            if (not done) and (not probe_only) and ran == PROBE_N and probe_ok < PROBE_N:
                log("探路未全部成功，停止扩大，不继续后续条目。")
                break
            if (not done) and (not probe_only) and ran == PROBE_N and probe_ok == PROBE_N:
                log("探路成功，按计划继续其余试标段（只分析对应秒数）。")

            phase = "probe" if (not done and ran < PROBE_N) else "run"
            append_jsonl(progress_path, {
                "ts": now_iso8601(),
                "seg": job["seg"],
                "status": "started",
                "phase": phase,
                "上传文件名": job["上传文件名"],
                "分析起始秒": job["分析起始秒"],
                "分析结束秒": job["分析结束秒"],
                "asset_id": job["asset_id"],
            })
            payload = {
                "model_name": MODEL,
                "video": {"type": "asset_id", "asset_id": job["asset_id"]},
                "prompt": PROMPT,
                "temperature": 0,
                "stream": False,
                "max_tokens": 512,
                "start_time": float(job["分析起始秒"]),
                "end_time": float(job["分析结束秒"]),
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "画面类型代码": {"type": "string"},
                            "画面类型": {"type": "string"},
                        },
                        "required": ["画面类型代码", "画面类型"],
                    },
                },
            }
            log(f"开始 {job['seg']} {job['上传文件名']} {job['分析起始秒']:.3f}-{job['分析结束秒']:.3f} phase={phase}")
            ev = {
                "ts": now_iso8601(),
                "seg": job["seg"],
                "上传文件名": job["上传文件名"],
                "副本文件名": job.get("副本文件名"),
                "分析起始秒": job["分析起始秒"],
                "分析结束秒": job["分析结束秒"],
                "asset_id": job["asset_id"],
                "审定画面类型": job["审定画面类型"],
                "model": MODEL,
                "index_id": INDEX_ID,
                "phase": phase,
            }
            try:
                status, body, hdrs = client.post_json("/analyze", payload, timeout=ANALYZE_TIMEOUT)
                interesting = _interesting_headers(hdrs)
                body_safe = redact_obj(body)
                code, name, parsed = parse_prediction(body)
                usage = {}
                if isinstance(body, dict):
                    usage = body.get("usage") or {}
                    ev["finish_reason"] = body.get("finish_reason")
                    ev["generation_id"] = body.get("id")
                ev["http_status"] = status
                ev["usage"] = usage
                ev["headers"] = interesting
                ev["raw_data"] = body_safe if not isinstance(body_safe, dict) else {
                    k: body_safe.get(k) for k in ("id", "event_type", "data", "finish_reason", "usage", "error")
                    if k in body_safe
                }
                if not code:
                    ev["status"] = "failed"
                    ev["error"] = "无法从响应解析画面类型代码"
                    log(f"失败 {job['seg']}：无法解析画面类型")
                    append_jsonl(progress_path, ev)
                    append_jsonl(result_path, ev)
                    results.append(ev)
                    ran += 1
                    if phase == "probe":
                        log("探路失败，不扩大。")
                        break
                    continue
                ev["预测代码"] = code
                ev["预测名称"] = name
                ev["status"] = "ok"
                ev["是否一致"] = "是" if code == job["审定画面类型"] else "否"
                append_jsonl(progress_path, ev)
                append_jsonl(result_path, ev)
                results.append(ev)
                ran += 1
                if phase == "probe":
                    probe_ok += 1
                log(f"完成 {job['seg']} 预测={code} 审定={job['审定画面类型']} 一致={ev['是否一致']} tokens={usage}")
            except QuotaError as e:
                ev.update({
                    "status": "quota_stop",
                    "http_status": e.status,
                    "error_code": e.code,
                    "error": redact_text(e.user_message),
                })
                append_jsonl(progress_path, ev)
                append_jsonl(result_path, ev)
                results.append(ev)
                quota_stopped = True
                log(f"额度不足或需付费，立即停止。status={e.status} code={e.code} message={redact_text(e.user_message)}")
                break
            except ApiError as e:
                ev.update({
                    "status": "failed",
                    "http_status": e.status,
                    "error_code": e.code,
                    "error": redact_text(e.user_message),
                })
                append_jsonl(progress_path, ev)
                append_jsonl(result_path, ev)
                results.append(ev)
                ran += 1
                log(f"失败 {job['seg']}：HTTP {e.status} code={e.code} {redact_text(e.user_message)}")
                if phase == "probe":
                    log("探路失败，不扩大。")
                    break
                # non-quota failure: continue to next, do not retry-spam this item
                continue

        # reload all ok results for tables
        all_ok: list[dict] = []
        if result_path.is_file():
            seen = {}
            for line in result_path.open(encoding="utf-8"):
                if not line.strip():
                    continue
                ev = json.loads(line)
                seen[ev["seg"]] = ev
            all_ok = list(seen.values())
        write_tables(jobs, all_ok)
        summary = summarize(jobs, all_ok)
        summary["本轮开始"] = started
        summary["本轮结束"] = now_iso()
        summary["本轮新跑条数"] = ran
        summary["额度停止"] = quota_stopped or summary["额度停止"]
        write_json(state_path, summary)
        log(f"汇总：成功={summary['成功']} 失败={summary['失败']} 一致={summary['一致']} 不一致={summary['不一致']} 额度停止={summary['额度停止']}")
        log(f"成功窗口 {summary['成功分析窗口秒']} 秒；对照表已写 Pegasus对照表.csv")
        return 3 if quota_stopped else 0
    finally:
        release_lock(lock_path)
        log("锁已释放。")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        log(f"未捕获错误: {type(e).__name__}: {redact_text(str(e))}")
        raise
