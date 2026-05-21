# publication-rank

MCP (Model Context Protocol) 服务，用于查询学术期刊等级信息。

## 功能

- **query_journal** — 查询期刊等级（ISSN 精准查询 / 期刊名称模糊搜索）
- **list_journals** — 列出本地数据库中的所有期刊
- **format_citation** — 格式化期刊信息为文本

## 数据来源

| 数据源 | 版本 | 说明 |
|--------|------|------|
| JCR | 2025 | 影响因子、JCR 分区 |
| 中科院分区表 | 2025 | 中科院分区（含 2023 vs 2025 对比） |
| 北大核心 | 2023 第十版 | 北大核心收录 |
| ABDC | 2025 | 澳大利亚商学院期刊列表 (A\*/A/B/C) |
| CSSCI | 2025-2026 | 南大核心来源期刊及扩展版 |
| Mega-Journal | 2025 | 发文量 > 3000 的巨型期刊 |

部分数据支持网络补充查询（Scimago、LetPub）。

## 安装

```bash
cd publication_rank
pip install -e .
```

或使用 uv：

```bash
uv sync
```

## MCP 配置

### opencode

```json
{
  "mcp": {
    "publication-rank": {
      "type": "local",
      "command": ["python", "D:\\1\\opencode\\publication_rank\\src\\publication_rank\\__main__.py"],
      "enabled": true
    }
  }
}
```

### Claude Desktop

```json
{
  "mcpServers": {
    "publication-rank": {
      "command": "python",
      "args": ["D:\\1\\opencode\\publication_rank\\src\\publication_rank\\__main__.py"]
    }
  }
}
```

### Cline / Roo Code

在 `cline_mcp_settings.json` 中添加：

```json
{
  "mcpServers": {
    "publication-rank": {
      "command": "python",
      "args": ["D:\\1\\opencode\\publication_rank\\src\\publication_rank\\__main__.py"]
    }
  }
}
```

### Continue.dev

在 `~/.continue/config.json` 中添加：

```json
{
  "experimental": {
    "mcpServers": {
      "publication-rank": {
        "command": "python",
        "args": ["D:\\1\\opencode\\publication_rank\\src\\publication_rank\\__main__.py"]
      }
    }
  }
}
```

### Windsurf / Cursor

在对应 IDE 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "publication-rank": {
      "command": "python",
      "args": ["D:\\1\\opencode\\publication_rank\\src\\publication_rank\\__main__.py"]
    }
  }
}
```

> 注意：将路径中的 `D:\\1\\opencode\\publication_rank` 替换为实际安装路径。

## 工具

### query_journal

```
参数:
  query    (必填) 期刊名称或 ISSN
  use_web  (可选) 从网络获取补充数据，默认 false
```

### list_journals

列出所有期刊（无参数）。

### format_citation

将期刊等级信息格式化为可读文本。

## 数据更新

数据文件位于 `data/` 目录，运行以下命令重新生成：

```bash
cd data
python to_src_data.py
```

生成的 `journals.json` 自动同步到 `src/publication_rank/data/`。
