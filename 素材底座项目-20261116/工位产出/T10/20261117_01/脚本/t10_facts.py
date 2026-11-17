# -*- coding: utf-8 -*-
"""Convert confirmed facts into 事实层.jsonl. Dedup jingxu confirmed-* vs source JSON."""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import t10_lib as L

NEG_HINTS = ("反例", "不是", "禁止", "不能用", "不要用", "不适用", "非微陶泥", "不是微陶泥", "不是阿明", "排除")


def is_neg(text) -> bool:
    if text is None:
        return False
    if isinstance(text, (list, dict)):
        text = json.dumps(text, ensure_ascii=False)
    s = str(text)
    return any(h in s for h in NEG_HINTS)


def collect_qualifiers(*parts):
    chunks = []
    for p in parts:
        if p is None or p is False:
            continue
        if p is True:
            continue
        if isinstance(p, (list, dict)):
            s = json.dumps(p, ensure_ascii=False)
        else:
            s = str(p).strip()
        if s and s not in chunks:
            chunks.append(s)
    return "；".join(chunks) if chunks else None


def src_loc(source, catalog, ann):
    source = source or {}
    return L.locate(
        asset_id=source.get("id") or source.get("asset_id"),
        path=source.get("path"),
        root=source.get("root"),
        rel=source.get("rel"),
        catalog=catalog,
        ann=ann,
    )


def load_batches():
    rows_by_file = {}
    for name in (
        [f"batch-0{i}.json" for i in range(1, 5)]
        + [f"product-0{i}.json" for i in range(1, 9)]
        + ["person-01.json", "person-02.json", "person-03.json", "person-04.json", "person-05.json", "person-07.json", "P24-boundary-proposal.json"]
    ):
        data = json.loads((L.ANN / name).read_text(encoding="utf-8"))
        rows_by_file[name] = data.get("rows") or []
    return rows_by_file


def convert_action_and_samples(catalog, ann, already_sample_ids):
    """Action batches + unconfirmed-excluded products already in confirmed-* skipped.
    Action samples and P24-A/B are added. Products/persons already in confirmed-* are not duplicated.
    """
    out = []
    notes = []
    files = load_batches()
    # action batches
    for name in [f"batch-0{i}.json" for i in range(1, 5)]:
        for row in files[name]:
            sid = row.get("sample_id")
            status = row.get("status") or ""
            if status == "用户已确认":
                cstatus = "已确认"
            elif "未定案" in status or "倾向" in status:
                cstatus = "暂定"
            else:
                cstatus = "未确认"
                notes.append({"file": name, "id": sid, "skip": status})
                continue
            source = row.get("source") or {}
            loc = src_loc(source, catalog, ann)
            start, end = source.get("start"), source.get("end")
            qual = collect_qualifiers(
                row.get("label_scope"),
                row.get("quality_note"),
                row.get("confirmation_evidence"),
                row.get("review_evidence"),
                row.get("product_identity"),
                ("apply_to_directory=false 不套用到目录" if row.get("apply_to_directory") is False else None),
            )
            confirmer = row.get("confirmed_by") or row.get("reviewed_by")
            confirmed_at = row.get("confirmed_at") or row.get("reviewed_at")
            label = row.get("confirmed_label") or row.get("user_judgment")
            out.append(L.fact_record(
                loc=loc, start=start, end=end, content=row,
                source_file="local/action-annotation/" + name,
                source_id=sid, confirmer=confirmer, confirmed_at=confirmed_at,
                level="片段级", qualifiers=qual,
                is_negative=is_neg(label) or (label == "反例"),
                confirm_status=cstatus,
                extra={"样例类别": "施工动作", "样例标签": label, "样例大类": row.get("category")},
            ))
    # P24 derived segments always
    for row in files["P24-boundary-proposal.json"]:
        sid = row.get("sample_id")
        source = row.get("source") or {}
        loc = src_loc(source, catalog, ann)
        out.append(L.fact_record(
            loc=loc, start=source.get("start"), end=source.get("end"), content=row,
            source_file="local/action-annotation/P24-boundary-proposal.json",
            source_id=sid,
            confirmer=row.get("confirmed_by"),
            confirmed_at=row.get("confirmed_at"),
            level="片段级",
            qualifiers=collect_qualifiers(row.get("label_scope"), row.get("quality_note"), row.get("confirmation_evidence"), "来自同一P24，不增加独立来源数量"),
            is_negative=is_neg(row.get("confirmed_label")),
            confirm_status="已确认",
            extra={"样例类别": "两动作分段", "样例标签": row.get("confirmed_label")},
        ))
    # product/person files: record counts, only add if sample_id not already in confirmed-*
    for name, rows in files.items():
        if not (name.startswith("product-") or name.startswith("person-")):
            continue
        for row in rows:
            sid = row.get("sample_id")
            status = str(row.get("status") or "")
            confirmed = ("确认" in status and "待人工确认" not in status and "暂不展示" not in status) or name == "person-07.json"
            if sid in already_sample_ids:
                continue
            if not confirmed:
                notes.append({"file": name, "id": sid, "skip": status or "未确认"})
                continue
            source = row.get("source") or {}
            loc = src_loc(source, catalog, ann)
            out.append(L.fact_record(
                loc=loc, start=source.get("start"), end=source.get("end"), content=row,
                source_file="local/action-annotation/" + name,
                source_id=sid,
                confirmer=row.get("confirmed_by"),
                confirmed_at=row.get("confirmed_at"),
                level="片段级",
                qualifiers=collect_qualifiers(
                    row.get("label_scope"), row.get("label_note"), row.get("quality_note"),
                    row.get("confirmation_evidence"), row.get("product_identity"),
                    ("apply_to_directory=false 不套用到目录" if row.get("apply_to_directory") is False else None),
                ),
                is_negative=is_neg(row.get("confirmed_label") or row.get("person_identity")),
                confirm_status="已确认",
                extra={"样例类别": "产品" if name.startswith("product-") else "人物", "样例标签": row.get("confirmed_label")},
            ))
    return out, notes, files


def convert_confirmed_rules(catalog, ann):
    conn = L.ro_sqlite(L.LEARN)
    cur = conn.cursor()
    out = []
    sample_ids = set()
    for rid, created, status, reviewer, payload in cur.execute(
        "SELECT id, created, status, reviewer, payload FROM rules WHERE id LIKE 'confirmed-%' ORDER BY id"
    ):
        p = json.loads(payload) if payload else {}
        sid = p.get("sample_id") or rid.replace("confirmed-", "")
        sample_ids.add(sid)
        loc = L.locate(asset_id=p.get("asset_id"), catalog=catalog, ann=ann)
        qual = collect_qualifiers(
            p.get("evidence"),
            p.get("reason"),
            p.get("context"),
            p.get("product_identity"),
            ("apply_to_directory=false 不套用到目录" if p.get("apply_to_directory") is False else None),
        )
        out.append(L.fact_record(
            loc=loc, start=p.get("start"), end=p.get("end"), content=p,
            source_file="local/cutframe/ai/learning.sqlite3#rules",
            source_id=rid,
            confirmer=p.get("confirmed_by") or reviewer or "当前用户",
            confirmed_at=p.get("confirmed_at") or created,
            level="片段级",
            qualifiers=qual,
            is_negative=is_neg(p.get("description") or p.get("person_identity") or p.get("product_identity") or p.get("confirmed_action") or p.get("evidence")),
            confirm_status="已确认" if status == "approved" else status,
            extra={"样例类别": "逐段事实", "样例编号": sid},
        ))
    conn.close()
    return out, sample_ids


def convert_trial50(catalog, ann):
    trial = json.loads((L.RULES / "试标50段" / "审核结果_李康_20261116.json").read_text(encoding="utf-8"))
    results = {r["seg"]: r for r in trial.get("结果") or []}
    out = []
    with (L.RULES / "试标50段" / "_对应表.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        seg = row["seg"]
        rev = results.get(seg) or {}
        src_path = row.get("原片") or ""
        # csv path starts with 史上最完整共享\...
        loc = L.locate(path=src_path, catalog=catalog, ann=ann)
        start = float(row["起始秒"]) if row.get("起始秒") not in (None, "") else None
        end = float(row["结束秒"]) if row.get("结束秒") not in (None, "") else None
        content = {"对应表": row, "审核结果": rev, "规则版本": trial.get("规则版本"), "导出时间": trial.get("导出时间")}
        out.append(L.fact_record(
            loc=loc, start=start, end=end, content=content,
            source_file="试标50段/审核结果_李康_20261116.json+_对应表.csv",
            source_id=seg,
            confirmer="李康",
            confirmed_at=trial.get("导出时间"),
            level="片段级",
            qualifiers=collect_qualifiers(rev.get("note"), rev.get("reason")),
            is_negative=(str(rev.get("verdict") or "") in ("错", "不对", "否")),
            confirm_status="已确认",
            extra={"样例类别": "试标50段", "审核结论": rev.get("verdict"), "机器画面类型": rev.get("机器画面类型")},
        ))
    return out


def parse_duizhao():
    """Parse 对照表.md folder table and appendix per-clip tables."""
    text = (L.RULES / "出镜文件夹确认图" / "对照表.md").read_text(encoding="utf-8")
    folders = []
    clips = []
    for line in text.splitlines():
        if line.startswith("| sheet_") and "拍摄" in line:
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            # 图, 文件夹, 视频数, 抽到帧数, 出镜的是谁
            if len(parts) >= 5:
                folders.append({
                    "图": parts[0].strip(),
                    "文件夹": parts[1].strip().strip("`"),
                    "视频数": parts[2].strip(),
                    "抽到帧数": parts[3].strip(),
                    "出镜的是谁": parts[4].strip(),
                })
    # appendix tables: after headings like ### sheet_xx
    current_sheet = None
    current_folder = None
    in_table = False
    header_seen = False
    folder_by_sheet = {f["图"]: f["文件夹"] for f in folders}
    for line in text.splitlines():
        m = re.match(r"^###\s+(sheet_\d+\.jpg)", line)
        if m:
            current_sheet = m.group(1)
            current_folder = folder_by_sheet.get(current_sheet)
            in_table = False
            header_seen = False
            continue
        if current_sheet and line.startswith("| 格 "):
            in_table = True
            header_seen = True
            continue
        if current_sheet and in_table and re.match(r"^\|\s*---", line):
            continue
        if current_sheet and in_table and line.startswith("|"):
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) >= 3 and parts[0] and parts[0] != "格":
                clips.append({
                    "图": current_sheet,
                    "文件夹": current_folder,
                    "格": parts[0],
                    "原片": parts[1],
                    "李康的判断": parts[2],
                })
            continue
        if current_sheet and in_table and line.strip() == "":
            in_table = False
    return folders, clips


def convert_duizhao(catalog, ann):
    folders, clips = parse_duizhao()
    out = []
    for f in folders:
        folder = f["文件夹"]
        # folder is like 拍摄\小区\...
        rel = folder
        if not rel.startswith("史上最完整共享"):
            rel = "史上最完整共享" + L.BS + folder
        loc = L.locate(path=rel, catalog=catalog, ann=ann)
        # folder-level: even if locate uses a path that isn't a file, keep folder path
        if not loc.get("主库相对路径"):
            loc["主库相对路径"] = rel
            loc["范围"] = L.range_flag(rel)
            loc["目录"] = L.which_dir(rel)
            loc["定位到文件"] = False
            loc["定位依据"] = ["文件夹路径"]
        else:
            # overwrite to folder path, not a single file
            loc["主库相对路径"] = rel
            loc["范围"] = L.range_flag(rel)
            loc["目录"] = L.which_dir(rel)
        text = f["出镜的是谁"]
        out.append(L.fact_record(
            loc=loc, start=None, end=None, content=f,
            source_file="出镜文件夹确认图/对照表.md",
            source_id=f["图"] + ":" + folder,
            confirmer="李康",
            confirmed_at="2026-11-16",
            level="文件夹级",
            qualifiers=text,
            is_negative=is_neg(text),
            confirm_status="已确认",
            extra={"样例类别": "李康按文件夹确认", "注意": "每个文件夹只看了12帧，不能保证里面每一条都是"},
        ))
    for c in clips:
        folder = c.get("文件夹") or ""
        name = c.get("原片") or ""
        path = None
        if folder and name:
            # name may be just filename
            path = "史上最完整共享" + L.BS + folder + L.BS + name
        loc = L.locate(path=path, catalog=catalog, ann=ann)
        start = end = None
        # special known seconds in 17881
        judgment = c.get("李康的判断") or ""
        extra_segs = []
        if "17881" in name and "前 5 秒" in judgment:
            # two identity segments mentioned; keep one record with qualifier, plus split records
            extra_segs = [
                (0, 5, "前 5 秒画面主体是紫衣人（不是阿明）"),
                (6, None, "白衣人约第 6 秒起入镜（是阿明）"),
            ]
        if extra_segs:
            for st, en, note in extra_segs:
                out.append(L.fact_record(
                    loc=loc, start=st, end=en, content={**c, "分段说明": note},
                    source_file="出镜文件夹确认图/对照表.md#明细",
                    source_id="%s:%s:%s-%s" % (c["图"], name, st, en),
                    confirmer="李康",
                    confirmed_at="2026-11-16",
                    level="片段级",
                    qualifiers=collect_qualifiers(judgment, note, "身份要按秒段记，不能整条记"),
                    is_negative=is_neg(note),
                    confirm_status="已确认",
                    extra={"样例类别": "李康按文件夹确认-逐格"},
                ))
        else:
            out.append(L.fact_record(
                loc=loc, start=None, end=None, content=c,
                source_file="出镜文件夹确认图/对照表.md#明细",
                source_id="%s:%s:%s" % (c["图"], c.get("格"), name),
                confirmer="李康",
                confirmed_at="2026-11-16",
                level="片段级" if name else "文件夹级",
                qualifiers=judgment,
                is_negative=is_neg(judgment),
                confirm_status="已确认",
                extra={"样例类别": "李康按文件夹确认-逐格", "注意": "逐格判断针对抽到的第2秒帧，未给整段起止秒则不填写起止"},
            ))
    return out, folders, clips


def convert_ann_human(catalog, ann):
    out = []
    # indexed_segments = 精标
    index_files = [
        (L.LABEL / "小区全库" / "数据" / "AI剪辑检索索引.jsonl", "小区全库/数据/AI剪辑检索索引.jsonl"),
        (L.LABEL / "测试阿明搅拌" / "数据" / "AI剪辑检索索引.jsonl", "测试阿明搅拌/数据/AI剪辑检索索引.jsonl"),
    ]
    seen_jingbiao = set()
    for fp, rel in index_files:
        for lineno, o in L.iter_jsonl(fp):
            loc = L.locate(path=o.get("source_path"), ann_id=o.get("id"), catalog=catalog, ann=ann)
            for j, seg in enumerate(o.get("indexed_segments") or []):
                key = (o.get("id"), seg.get("start"), seg.get("end"), seg.get("category"), seg.get("action"))
                seen_jingbiao.add(key)
                out.append(L.fact_record(
                    loc=loc, start=seg.get("start"), end=seg.get("end"),
                    content={"原片字段摘录": {"id": o.get("id"), "source_path": o.get("source_path")}, "片段": seg},
                    source_file=rel + "#indexed_segments",
                    source_id="%s:%s-%s:%s" % (o.get("id"), seg.get("start"), seg.get("end"), j),
                    confirmer=None,
                    confirmed_at=None,
                    level="片段级",
                    qualifiers=collect_qualifiers(seg.get("basis"), seg.get("limits"), seg.get("privacy")),
                    is_negative=is_neg(seg.get("action") or seg.get("basis")),
                    confirm_status="人工核对",
                    extra={"样例类别": "标注库精标indexed_segments", "确认人说明": "来源为标注库精标/核验片段，确认人字段原文未单列，依据写在 basis"},
                ))
            for j, seg in enumerate(o.get("人工确认片段") or []):
                out.append(L.fact_record(
                    loc=loc, start=seg.get("start"), end=seg.get("end"),
                    content={"原片id": o.get("id"), "source_path": o.get("source_path"), "人工确认片段": seg},
                    source_file=rel + "#人工确认片段",
                    source_id="%s:人工确认:%s-%s:%s" % (o.get("id"), seg.get("start"), seg.get("end"), j),
                    confirmer=seg.get("source") or "人工确认",
                    confirmed_at=None,
                    level="片段级",
                    qualifiers=collect_qualifiers(seg.get("选镜限制"), seg.get("source")),
                    is_negative=is_neg(seg),
                    confirm_status="已确认",
                    extra={"样例类别": "标注库人工确认片段"},
                ))
    # 本轮看片精标, skip exact overlaps with indexed
    jingbiao_path = L.LABEL / "小区全库" / "数据" / "本轮看片精标.jsonl"
    for lineno, o in L.iter_jsonl(jingbiao_path):
        key = (None, o.get("start"), o.get("end"), o.get("category"), o.get("action"))
        # also id-based
        loc = L.locate(path=o.get("path"), catalog=catalog, ann=ann)
        # mark overlap later; always include but tag if same interval appears
        out.append(L.fact_record(
            loc=loc, start=o.get("start"), end=o.get("end"), content=o,
            source_file="小区全库/数据/本轮看片精标.jsonl",
            source_id=o.get("id"),
            confirmer=None,
            confirmed_at=None,
            level="片段级",
            qualifiers=collect_qualifiers(o.get("basis"), o.get("limits")),
            is_negative=False,
            confirm_status="人工核对",
            extra={"样例类别": "本轮看片精标", "确认人说明": "标注库人工看片精标，确认人字段原文未单列"},
        ))
    # 目视纠正: whole-video description, no seconds
    corr = L.LABEL / "小区全库" / "数据" / "目视纠正.jsonl"
    for lineno, o in L.iter_jsonl(corr):
        loc = L.locate(ann_id=o.get("id"), catalog=catalog, ann=ann)
        out.append(L.fact_record(
            loc=loc, start=None, end=None, content=o,
            source_file="小区全库/数据/目视纠正.jsonl",
            source_id=o.get("id"),
            confirmer=None,
            confirmed_at=None,
            level="文件夹级" if False else "片段级",
            qualifiers=collect_qualifiers(o.get("basis"), "目视纠正无起止秒，按整条原片记录"),
            is_negative=False,
            confirm_status="人工核对",
            extra={"样例类别": "目视纠正", "确认人说明": "标注库目视纠正，确认人字段原文未单列", "无起止秒": True},
        ))
    return out


def run():
    print("loading catalog and indexes...")
    catalog = L.load_catalog()
    ann = L.load_ann_indexes()
    print("catalog", len(catalog[0]), "ann", len(ann[0]))

    facts = []
    confirmed, sample_ids = convert_confirmed_rules(catalog, ann)
    facts.extend(confirmed)
    print("confirmed-*", len(confirmed), "sample_ids", len(sample_ids))

    samples, skip_notes, _files = convert_action_and_samples(catalog, ann, sample_ids)
    facts.extend(samples)
    print("action/P24/extra samples", len(samples), "skipped", skip_notes)

    trial = convert_trial50(catalog, ann)
    facts.extend(trial)
    print("trial50", len(trial))

    duizhao, folders, clips = convert_duizhao(catalog, ann)
    facts.extend(duizhao)
    print("duizhao folders", len(folders), "clips", len(clips), "records", len(duizhao))

    human = convert_ann_human(catalog, ann)
    facts.extend(human)
    print("ann human", len(human))

    # assign fact_uid
    for i, rec in enumerate(facts, 1):
        rec["事实编号"] = "F%04d" % i

    dest = L.CLIPLIB / "事实层.jsonl"
    L.write_jsonl(dest, facts)
    # also copy to output
    L.write_jsonl(L.OUT / "片段库副本" / "事实层.jsonl", facts)

    unresolved = [r for r in facts if not r.get("定位到文件")]
    meta = {
        "事实层条数": len(facts),
        "逐段事实confirmed-*": len(confirmed),
        "动作及P24等样例": len(samples),
        "跳过未确认样例": skip_notes,
        "试标50段": len(trial),
        "对照表文件夹": len(folders),
        "对照表逐格": len(clips),
        "对照表记录": len(duizhao),
        "标注库人工": len(human),
        "定位不到": [
            {"事实编号": r["事实编号"], "来源文件": r["来源文件"], "来源条目标识": r["来源条目标识"], "主库相对路径": r.get("主库相对路径")}
            for r in unresolved
        ],
        "范围内": sum(1 for r in facts if r.get("范围") == "范围内"),
        "范围外": sum(1 for r in facts if r.get("范围") == "范围外"),
        "文件夹级": sum(1 for r in facts if r.get("确认级别") == "文件夹级"),
        "片段级": sum(1 for r in facts if r.get("确认级别") == "片段级"),
    }
    L.write_json(L.OUT / "统计" / "事实层汇总.json", meta)
    print("WROTE", dest, "n", len(facts), "unresolved", len(unresolved))
    return facts, meta


if __name__ == "__main__":
    run()
