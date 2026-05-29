---
name: journal-rank
description: |
  查询学术期刊的等级信息，支持模糊匹配期刊名称或 ISSN。
  涵盖中科院分区、JCR分区、影响因子、ABDC评级、北大核心、CSSCI等信息。
allowed-tools:
  - Bash
  - Read
metadata:
  source: 项目内建
---

# journal-rank

查询学术期刊的等级信息（中科院分区、JCR分区、影响因子等），支持**期刊名称模糊搜索**和**ISSN 精确搜索**。

## 数据来源

- **中科院分区表**（2025版，含2023对比）
- **JCR**（2024 影响因子及分区）
- **ABDC**（Australian Business Deans Council 评级）
- **北大核心**、**CSSCI**
- **Mega-Journal 大刊名单**

数据文件：`journals.json`（与本 SKILL.md 同目录）
查询脚本：`query_journal.py`（与本 SKILL.md 同目录）

## 查询方法

支持期刊名称（中英文）或 ISSN 两种搜索方式：

```bash
# 按期刊名称模糊搜索
python .opencode/skills/journal-rank/query_journal.py "Nature"

# 按 ISSN 精确搜索
python .opencode/skills/journal-rank/query_journal.py "0028-0836"
```

返回 JSON 数组，每条记录包含以下字段：

| 字段 | 说明 |
|------|------|
| `name` | 期刊英文名 |
| `issn` | ISSN |
| `aliases` | 中文名等别名 |
| `jif` | 影响因子 (JIF 2024) |
| `jcr_quartile` | JCR 分区 (Q1/Q2/Q3/Q4) |
| `jcr_rank` | JCR 排名 (如 "12/420") |
| `cas_zone` | 中科院大类分区 (1/2/3/4) |
| `cas_zone_2023` | 2023 年中科院分区 |
| `cas_top` | 是否 Top 期刊 |
| `cas_open_access` | 是否 OA |
| `cas_discipline` | 中科院学科分类 |
| `high` | 高水平标记 (true/false) — SCI/SSCI + IF>4 + 排除医/材/物/化/生 |
| `abdc_rating` | ABDC 评级 (A*/A/B/C) |
| `cssci` | CSSCI 收录 ("来源期刊" / "扩展版") |
| `pkua` | 北大核心收录 |
| `publisher` | 出版商 |

## 更新数据

运行 `data/build_database.py` 重新生成 `data/journals.json`，然后覆盖到本目录：

```
cp data/journals.json .opencode/skills/journal-rank/journals.json
```

## 注意事项

- 支持中英文期刊名称和 ISSN 模糊搜索
- 返回匹配度最高的前 10 条结果
- 无匹配时返回空数组 `[]`

---

**查看更新**: https://github.com/zzlb0224/journal-rank-mcp  

