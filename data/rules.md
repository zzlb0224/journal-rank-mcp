# 数据规则

## 合并流程

1. `中科院分区表及JCR原始数据文件/merge.py` — 从原始 CSV 合并生成 `data/JCR_CAS.json`
   - 基础：FQBJCR2025-UTF8.csv（中科院分区 + JCR + Top）
   - 匹配：JCR2024-UTF8.csv（ISSN/EISSN→jif/jcr_quartile/jcr_rank/jcr_category）
   - 匹配：XR2026-UTF8.csv（ISSN/EISSN→新锐分区/中文名/出版机构等）
   - 追加：GJQKYJMD*.csv（按期刊名匹配→warn_2020~warn_2025）

2. `data/merge_all.py` — 合并三个 JSON 源生成最终输出
   - 基础：JCR_CAS.json（22696 条）
   - 追加/融合：北大核心.json（3978 条，按 name_cn 匹配）
   - 追加/融合：CSSCI.json（936 条，按 name_cn 匹配）

## 输出文件

| 文件 | 内容 | 记录数 | 部署路径 |
|------|------|--------|----------|
| `journals.json` | 全部数据，所有字段 | 27610 | `src/journal_rank_mcp/data/journals.json` |
| `journals_lite.json` | 全部数据，仅 `fields_lite.md` 中字段 | 27610 | — |
| `journals_high_lite.json` | 高水平期刊，仅 `fields_lite.md` 中字段 | ~1001 | `.opencode/skills/search-scispace/journals_high_lite.json` |

`merge_all.py` 执行完后自动复制到上述部署路径。

## 高水平筛选规则 (`journals_high_lite.json`)

并**列条件**（全部满足）：

1. **jif > 4** — JCR 影响因子大于 4
2. **cas_zone <= 2** — 中科院分区为一区或二区
3. **jcr_quartile in (Q1, Q2)** — JCR 分区为 Q1 或 Q2

排除条件（满足任一即排除）：

1. **预警期刊** — 任何 `warn_` 字段有值（被列入中科院预警名单）
2. **排除学科** — `cas_discipline` 为以下之一：
   - 医学、材料科学、物理与天体物理、化学、生物学
3. **排除出版社** — `publisher` 包含以下关键词（不区分大小写）：
   - MDPI、Frontiers、Hindawi

## 字段命名约定

- 标记字段用 `1`（整数）表示真，假值直接省略字段
- `name_cn` / `name_en` 按数据实际内容决定字段名
- 来源前缀：
  - `cas_` — 中科院分区
  - `jcr_` — JCR 数据
  - `xr_` — 新锐分区（XR2026）
  - `fq_` — FQBJCR 原始标记
  - `warn_` — 预警名单（`warn_年份`）
  - `cssci_` — CSSCI
  - `pkua` — 北大核心
