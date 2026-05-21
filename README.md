# publication-rank

Academic journal ranking query tool — supports both **MCP server** and **opencode Skill** modes.

> ⚡ **Recommendation**: Use the Skill mode. It requires no server process, no dependency installation, and works anywhere you copy the project.

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
    "publication-rank": {
      "command": "python",
      "args": ["path/to/src/publication_rank/__main__.py"]
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

All raw data lives in `data/`. The pipeline `data/to_src_data.py` reads, merges, deduplicates, and outputs:

| Output | Description |
|--------|-------------|
| `data/journals.json` | Full journal database (ISSN-keyed) |
| `data/journals_high_rank.json` | Filtered: CAS 1-2 + JCR Q1-Q2, excludes 医/材/物/化/生 |
| `data/journals.csv` | Flat table of all records |

### Updating Data

```bash
python data/to_src_data.py
```

This regenerates all outputs from the raw files under `data/`.  
After updating, sync the skill's copy:

```bash
cp data/journals.json .opencode/skills/journal-rank/journals.json
```

### Extending (new fields, new journal ratings)

1. Place your raw JSON file in `data/` (must have `"source"` + `"journals"` fields)
2. Open `data/to_src_data.py` — the header has a checklist
3. Add an `elif` branch for the new source
4. Add fields to `JournalRecord.__slots__` if needed
5. Add field to JSON output section
