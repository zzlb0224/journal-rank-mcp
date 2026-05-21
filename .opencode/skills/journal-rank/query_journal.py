# MIT License — https://github.com/zzlb0224/journal-rank-mcp
# Free to use, modify, and distribute. Retain this notice.

import json, sys, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path

DATA_DIR = Path(__file__).parent
JOURNALS_FILE = DATA_DIR / "journals.json"


def _normalize(name: str) -> str:
    s = unicodedata.normalize('NFKD', name.lower())
    s = s.replace('&', 'and').replace('/', ' ').replace('\\', ' ')
    s = re.sub(r'[\u2013\u2014]', '-', s)
    s = s.replace('-', ' ').replace(':', '').replace(',', '').replace('.', '')
    s = s.replace("'", '').replace('"', '').replace('(', '').replace(')', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def search_journal(query: str) -> list[dict]:
    journals = json.loads(JOURNALS_FILE.read_text(encoding='utf-8'))
    query_clean = _normalize(query)
    results = []

    for issn, entry in journals.items():
        score = 0
        name = _normalize(entry.get("name", ""))
        aliases = [_normalize(a) for a in entry.get("aliases", [])]

        if query_clean == name or query_clean in aliases:
            score = 1.0
        elif issn.replace("-", "") == query.replace("-", ""):
            score = 1.0
        else:
            score = max(_similarity(query_clean, name),
                        max((_similarity(query_clean, a) for a in aliases), default=0))
            if query_clean in name or any(query_clean in a for a in aliases):
                score = max(score, 0.8)

        if score >= 0.4:
            results.append((score, {"issn": issn, **entry}))

    results.sort(key=lambda x: -x[0])
    return [r[1] for r in results[:10]]


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python query_journal.py <期刊名称或ISSN>")
        sys.exit(1)

    query = sys.argv[1]
    results = search_journal(query)

    if not results:
        print(json.dumps([], ensure_ascii=False))
        sys.exit(0)

    print(json.dumps(results, ensure_ascii=False, indent=2))
