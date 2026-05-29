# publication-rank

> 查看更新: https://github.com/zzlb0224/journal-rank-mcp

Academic journal ranking query tool — supports both **MCP server** and **opencode Skill** modes.

> ⚡ **Recommendation**: Use the Skill mode. It requires no server process, no dependency installation, and works anywhere you copy the project (requires **Python ≥ 3.11**).

---

## MCP Mode (traditional)

Runs as a standalone MCP server, providing `query_journal`, `list_journals`, `format_citation` tools.

### Installation

```bash
pip install -e .
```

### Configuration

Add to your MCP client config:

```json
{
  "mcpServers": {
    "journal-rank-mcp": {
      "command": "python",
      "args": ["path/to/src/journal_rank_mcp/__main__.py"]
    }
  }
}
```

---

## Skill Mode (recommended ⭐)

No server, no dependencies. The AI calls the query script directly when needed.

The skill is located at `.opencode/skills/journal-rank/SKILL.md`. Once this project is opened in opencode, the AI automatically loads the skill and can answer journal rank queries by running:

```
python .opencode/skills/journal-rank/query_journal.py <name or ISSN>
```

**Copy to another project**: just copy the `.opencode/skills/journal-rank/` folder — it's fully self-contained with its own data and script.

---

## Data Sources

| Source | Version |
|--------|---------|
| JCR Impact Factor & Quartile | 2024 |
| CAS Zone (Chinese Academy of Sciences) | 2025 |
| Peking University Core | 2023 10th ed. |
| ABDC (Australian Business Deans Council) | 2025 |
| CSSCI (Chinese Social Sciences Citation Index) | 2025-2026 |
| Mega-Journal List | 2025 |

---

## Data Pipeline

All raw data lives in `data/`. The pipeline `data/build_database.py` reads, merges, deduplicates, and outputs:

| Output | Description |
|--------|-------------|
| `data/journals.json` | Full journal database (ISSN-keyed) |
| `data/journals_high_rank.json` | Filtered: CAS 1-2 + JCR Q1-Q2, excludes 医/材/物/化/生 |
| `data/journals.csv` | Flat table of all records |

### Updating Data

```bash
python data/build_database.py
```

This regenerates all outputs from the raw files under `data/`.  
After updating, sync the skill's copy:

```bash
cp data/journals.json .opencode/skills/journal-rank/journals.json
```

### Extending ①: Add new fields (e.g. SABC rating, SJR, H-index)

1. Place your raw JSON file in `data/` (flat format)
2. Define `field_map` in the JSON file to map raw field names to standard names
3. Optional: `norm_defaults` for fixed values, `norm_config` for type conversion rules
4. Document new standard fields in `build_database.py`'s convention table

### Extending ②: Adjust `journals_high_rank.json` filter rules

Edit the config block at the top of `data/filter_high_rank.py`:

```python
CAS_ZONES           = {1, 2}          # CAS zones to keep
JCR_QUARTILES       = {'Q1', 'Q2'}    # JCR quartiles to keep
EXCLUDE_DISCIPLINES = ['医学','材料']  # Disciplines to exclude
```

Then run:

```bash
python data/filter_high_rank.py
```

Then run:

```bash
python data/filter_high_rank.py
```
