# MIT License
# Free to use, modify, and distribute. Retain this notice.

import json, re, unicodedata
from pathlib import Path
from difflib import SequenceMatcher
from typing import Any

DATA_DIR = Path(__file__).parent / "data"
JOURNALS_FILE = DATA_DIR / "journals.json"
CACHE_FILE = DATA_DIR / "cache.json"

_journals_cache: dict[str, Any] | None = None
_cache_data: dict[str, Any] | None = None


def _load_journals(*, force: bool = False) -> dict[str, Any]:
    global _journals_cache
    if _journals_cache is not None and not force:
        return _journals_cache
    if JOURNALS_FILE.exists():
        _journals_cache = json.loads(JOURNALS_FILE.read_text(encoding="utf-8"))
    else:
        _journals_cache = {}
    return _journals_cache


def _load_cache(*, force: bool = False) -> dict[str, Any]:
    global _cache_data
    if _cache_data is not None and not force:
        return _cache_data
    if CACHE_FILE.exists():
        _cache_data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    else:
        _cache_data = {}
    return _cache_data


def _save_cache(entry: dict) -> None:
    global _cache_data
    cache = _load_cache()
    cache[entry["issn"]] = entry
    _cache_data = cache
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _similarity(a: str, b: str) -> float:
    a, b = a.lower().strip(), b.lower().strip()
    return SequenceMatcher(None, a, b).ratio()


def _normalize(name: str) -> str:
    s = unicodedata.normalize('NFKD', name.lower())
    s = s.replace('&', 'and').replace('/', ' ').replace('\\', ' ')
    s = re.sub(r'[\u2013\u2014]', '-', s)
    s = s.replace('-', ' ').replace(':', '').replace(',', '').replace('.', '')
    s = s.replace("'", '').replace('"', '').replace('(', '').replace(')', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def search_journal(query: str) -> list[dict]:
    journals = _load_journals()
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
            score = max(_similarity(query_clean, name), max((_similarity(query_clean, a) for a in aliases), default=0))
            if query_clean in name or any(query_clean in a for a in aliases):
                score = max(score, 0.8)

        if score >= 0.4:
            results.append((score, entry | {"issn": issn}))

    results.sort(key=lambda x: -x[0])

    cache = _load_cache()
    for issn, entry in cache.items():
        if all(r[1].get("issn") != issn for r in results):
            if query_clean == _normalize(entry.get("name", "")):
                results.insert(0, (1.0, entry | {"issn": issn}))

    return [r[1] for r in results[:10]]


def lookup_issn(issn: str) -> dict | None:
    journals = _load_journals()
    clean = issn.replace("-", "")
    for key, entry in journals.items():
        if key.replace("-", "") == clean:
            return entry | {"issn": key}
    cache = _load_cache()
    for key, entry in cache.items():
        if key.replace("-", "") == clean:
            return entry | {"issn": key}
    return None


def add_journal(issn: str, data: dict) -> None:
    _save_cache({"issn": issn, **data})
