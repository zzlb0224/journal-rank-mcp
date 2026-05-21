# publication-rank

> 查看更新: https://github.com/zzlb0224/journal-rank-mcp

学术期刊等级查询工具，同时支持 **MCP server** 和 **opencode Skill** 两种使用方式。

> ⚡ **推荐**：使用 Skill 模式。无需启动服务进程、无需安装依赖，复制目录即可随处使用（需 **Python ≥ 3.11**）。

---

## MCP 模式（传统）

作为独立 MCP 服务运行，提供 `query_journal`、`list_journals`、`format_citation` 工具。

### 安装

```bash
pip install -e .
```

### 配置

在 MCP 客户端配置中添加：

```json
{
  "mcpServers": {
    "publication-rank": {
      "command": "python",
      "args": ["path/to/src/publication_rank/__main__.py"]
    }
  }
}
```

---

## Skill 模式（推荐 ⭐）

无需服务进程、无需安装依赖。AI 在需要时直接调用查询脚本。

Skill 位于 `.opencode/skills/journal-rank/SKILL.md`。打开本项目后，AI 自动加载 skill，遇到期刊查询时会直接执行：

```
python .opencode/skills/journal-rank/query_journal.py <期刊名称或ISSN>
```

**复制到其他项目**：只需复制 `.opencode/skills/journal-rank/` 整个目录即可 —— 自带数据和脚本，开箱即用。

---

## 数据来源

| 数据源 | 版本 |
|--------|------|
| JCR 影响因子及分区 | 2024 |
| 中科院分区表 | 2025 |
| 北大核心 | 2023 第十版 |
| ABDC 评级 | 2025 |
| CSSCI 来源期刊及扩展版 | 2025-2026 |
| Mega-Journal 巨型期刊 | 2025 |

---

## 数据流水线

原始数据位于 `data/` 目录下各子目录。`data/build_database.py` 负责读取、合并、去重，输出：

| 输出文件 | 说明 |
|----------|------|
| `data/journals.json` | 完整期刊库（以 ISSN 为 key） |
| `data/journals_high_rank.json` | 过滤版：CAS 1-2 区 + JCR Q1-Q2，排除医/材/物/化/生 |
| `data/journals.csv` | 扁平表格 |

### 更新数据

```bash
python data/build_database.py
```

重新生成所有输出。更新后同步 skill 中的拷贝：

```bash
cp data/journals.json .opencode/skills/journal-rank/journals.json
```

### 扩展指南 ①：新增字段（如 SABC 评级、SJR、H-index 等）

1. 将原始 JSON 文件放入 `data/` 下对应子目录（需含 `"source"` 和 `"journals"` 字段）
2. 打开 `data/build_database.py` → 文件头部有 **扩展指南 ①** 的 5 步详细说明
3. 在 `elif` 分支添加新数据源的解析逻辑
4. 在 `JournalRecord.__slots__` 中声明新字段
5. 在 JSON 输出段添加该字段的写出代码

### 扩展指南 ②：调整 `journals_high_rank.json` 筛选条件

编辑 `data/filter_high_rank.py` 顶部的配置块即可：

```python
CAS_ZONES           = {1, 2}          # 保留的中科院分区
JCR_QUARTILES       = {'Q1', 'Q2'}    # 保留的 JCR 分区
EXCLUDE_DISCIPLINES = ['医学','材料']  # 排除的学科关键词
```

改完后运行：

```bash
python data/filter_high_rank.py
```
