# publication-rank

An MCP (Model Context Protocol) server for querying academic journal rankings.

## Tools

- **query_journal** — Query journal rankings (by ISSN or fuzzy name search)
- **list_journals** — List all journals in the local database
- **format_citation** — Format journal info as readable text

## Data Sources

| Source | Version | Description |
|--------|---------|-------------|
| JCR | 2025 | Impact factor & JCR quartile |
| CAS Zone | 2025 | Chinese Academy of Sciences zone (with 2023 vs 2025 diff) |
| Peking University Core | 2023 10th ed. | PKU core journal list |
| ABDC | 2025 | Australian Business Deans Council list (A\*/A/B/C) |
| CSSCI | 2025-2026 | Chinese Social Sciences Citation Index |
| Mega-Journal | 2025 | Journals publishing >3000 articles/year |

Online fallback sources: Scimago, LetPub.

## Installation

```bash
cd publication_rank
pip install -e .
```

Or with uv:

```bash
uv sync
```

## MCP Configuration

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

Add to `cline_mcp_settings.json`:

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

Add to `~/.continue/config.json`:

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

Add to the IDE's MCP configuration:

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

> **Note:** Replace `D:\\1\\opencode\\publication_rank` with your actual installation path.

## Data Pipeline

Raw data files are in `data/`. To regenerate the database:

```bash
cd data
python to_src_data.py
```

The generated `journals.json` is automatically synced to `src/publication_rank/data/`.
