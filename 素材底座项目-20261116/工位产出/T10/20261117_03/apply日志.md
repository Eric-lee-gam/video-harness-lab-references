# T10 20261117_03 apply 日志

日期：2026-11-17（Asia/Shanghai）
口径：T06A 有效工序空值（推荐）。未使用问题单字面口径。

## 命令

工作目录未改，直接调用：

```
$env:PYTHONUTF8=1
$env:PYTHONDONTWRITEBYTECODE=1
C:\Python314\python.exe `D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_03\脚本\t10_rewrite_gang_labels.py` --apply
```

脚本由 `工位产出\T10\20261117_02\脚本\t10_rewrite_gang_labels.py` 复制而来，仅把 `OUT` 改为本批目录 `20261117_03`，临时文件名改为 `粗标层.jsonl.t10_20261117_03.tmp`，改写规则未改。默认 dry-run，`--apply` 先备份再写正式库。Apply 使用脚本内 `T06A_EMPTY`（`未据此确认`、`待确认`、`瓷釉改色或底漆` 视为空，回退到工序原值；映射含「刮刀批刮」等 T06A 已补项）。

## 事先核对

- 读过 `20261117_02` 的返工说明、检索说明、回报、干跑对照和脚本，确认默认/apply 都是 T06A 口径。
- 为避免覆盖 02 产出，本批 dry-run 与日志写到 `20261117_03`。
- Apply 前正式 `片段库\粗标层.jsonl`：65,971 行，113,340,513 字节，sha256 `2e6908b03f13e85d37eddf97813ba6c5a56e301dd474e969b46bc59c04d3f06f`。
- `事实层.jsonl` sha256 `6a3deb63c154e52cb55b7529000b3737be1b76e9e330f77ce1160dba1169506f`；`禁用表.jsonl` sha256 `a2c776129a21bac141ef384b17f50a178d92985b45e42ad43158b8d6b6b42894`。本批未改这两份文件。

## 本批 dry-run（不覆盖 02）

T06A 有效工序空值（推荐）：

- 不变 65098
- 新补B1 687
- 多B1收成一个 115
- 单B1被复核改写 60
- 有效工序无映射将去掉B1 11

与已记预期完全一致。问题单字面口径同时算出「去掉B1 1332」，仅作对照，未采用。

## --apply 标准输出

```
backup -> D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_03\输入副本\粗标层.jsonl
APPLIED {'总条数': 65971, '改写条数': 873, '备份': 'D:\codex-work\codex-company\video-harness-lab\references\素材底座项目-20261116\工位产出\T10\20261117_03\输入副本\粗标层.jsonl'}
```

改写条数 873 = 687 + 115 + 60 + 11。

## 备份

- 路径：`工位产出\T10\20261117_03\输入副本\粗标层.jsonl`
- 大小：113,340,513 字节
- 行数：65,971
- sha256：2e6908b03f13e85d37eddf97813ba6c5a56e301dd474e969b46bc59c04d3f06f
- 与 apply 前正式文件一致：是

## 正式库写入后

- 路径：`片段库\粗标层.jsonl`
- 大小：113,360,561 字节
- 行数：65,971（未变）
- sha256：1bf1a10d59d7fb07f0b3a6564b089649895976ef514fd56cdd8285334b1c2d9a
- 临时文件残留：无
- 未改 `事实层.jsonl`、`禁用表.jsonl`，未挂镜序拦截。

详见 `apply验收对照.json`、`干跑与实写对照.md`、`回报.md`。
