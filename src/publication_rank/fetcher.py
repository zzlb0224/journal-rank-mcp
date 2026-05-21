# MIT License — https://github.com/zzlb0224/journal-rank-mcp
# Free to use, modify, and distribute. Retain this notice.

import re
import httpx
from bs4 import BeautifulSoup
from typing import Any

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

TIMEOUT = httpx.Timeout(15.0)


def _parse_jif(text: str) -> float | None:
    text = text.strip()
    match = re.search(r"(\d+\.\d+)", text)
    return float(match.group(1)) if match else None


async def fetch_from_scimago(name: str) -> dict[str, Any] | None:
    """Fetch journal ranking from scimagojr.com by searching for the journal name."""
    search_url = "https://www.scimagojr.com/journalsearch.php"
    params = {"q": name}

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(search_url, params=params)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            results = soup.select("div.search_results a")
            if not results:
                return None

            journal_link = results[0].get("href", "")
            if not journal_link.startswith("http"):
                journal_link = "https://www.scimagojr.com" + journal_link

            detail_resp = await client.get(journal_link)
            detail_resp.raise_for_status()
            detail_soup = BeautifulSoup(detail_resp.text, "lxml")

            result: dict[str, Any] = {}

            sjr_elem = detail_soup.select_one("div.celltext_rank")
            if sjr_elem:
                text = sjr_elem.get_text(strip=True)
                q_match = re.search(r"(Q[1-4])", text)
                if q_match:
                    result["sjr_quartile"] = q_match.group(1)
                sjr_match = re.search(r"([\d.]+)", text)
                if sjr_match:
                    result["sjr"] = float(sjr_match.group(1))

            h_index_elem = detail_soup.select_one("div.celltext_hindex")
            if h_index_elem:
                h_match = re.search(r"(\d+)", h_index_elem.get_text(strip=True))
                if h_match:
                    result["h_index"] = int(h_match.group(1))

            cat_elems = detail_soup.select("div.cellcontent_category")
            if cat_elems:
                categories = [c.get_text(strip=True) for c in cat_elems]
                result["categories"] = categories

            return result if result else None

    except Exception:
        return None


async def fetch_from_letpub(query: str) -> dict[str, Any] | None:
    """Fetch journal info from letpub (Chinese journal ranking data)."""
    url = "https://www.letpub.com.cn/index.php"
    params = {
        "page": "journalapp",
        "view": "search",
        "searchstr": query,
    }

    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")
            result: dict[str, Any] = {}

            rows = soup.select("table.table tbody tr")
            if not rows:
                return None

            cells = rows[0].select("td")
            for cell in cells:
                text = cell.get_text(strip=True)

                if "中科院" in text or "CAS" in text.upper():
                    zone_match = re.search(r"[一二三四]", text)
                    if zone_match:
                        zone_map = {"一": 1, "二": 2, "三": 3, "四": 4}
                        result["cas_zone"] = zone_map.get(zone_match.group(0))

                if "IF" in text or "影响因子" in text:
                    jif = _parse_jif(text)
                    if jif:
                        result["jif"] = jif

                if "JCR" in text or "Q" in text:
                    q_match = re.search(r"Q[1-4]", text)
                    if q_match:
                        result["jcr_quartile"] = q_match.group(0)

            return result if result else None

    except Exception:
        return None


async def fetch_journal(query: str) -> dict[str, Any] | None:
    """Try multiple sources to fetch journal ranking data."""
    result = await fetch_from_scimago(query)
    if result:
        return result

    result = await fetch_from_letpub(query)
    if result:
        return result

    return None
