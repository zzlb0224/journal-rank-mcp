# MIT License
# Free to use, modify, and distribute. Retain this notice.

"""
🔍 query_journal.py — 期刊模糊查询工具

通过期刊名称或 ISSN 模糊搜索，返回匹配度最高的前 10 条结果。

用法：
    python query_journal.py "Nature"
    python query_journal.py "管理世界"
    python query_journal.py "0028-0836"

输出：
    JSON 数组，每条包含期刊的全部等级信息（JCR 分区、中科院分区、影响因子等）。
    无匹配时返回空数组 []。

数据来源：
    同目录下的 journals.json（由 data/build_database.py 生成）。
"""

import json, sys, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path

DATA_DIR = Path(__file__).parent
JOURNALS_FILE = DATA_DIR / "journals.json"


def _normalize(name: str) -> str:
    """
    名称规范化，用于提高模糊匹配的准确率。

    处理步骤：
      1. NFKD Unicode 正规化（分解复合字符，如 é → e + ́）
      2. & → and，/ → 空格，\\ → 空格
      3. 短破折号 → ASCII 连字符 → 空格
      4. 移除标点符号（: , . ' " ( )）
      5. 多空格合并，去首尾空格

    这样 "J. Am. Chem. Soc." 和 "Journal of the American Chemical Society"
    在规范化后会更接近，提高匹配分数。
    """
    s = unicodedata.normalize('NFKD', name.lower())
    s = s.replace('&', 'and').replace('/', ' ').replace('\\', ' ')
    s = re.sub(r'[\u2013\u2014]', '-', s)
    s = s.replace('-', ' ').replace(':', '').replace(',', '').replace('.', '')
    s = s.replace("'", '').replace('"', '').replace('(', '').replace(')', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def _similarity(a: str, b: str) -> float:
    """
    计算两个字符串的相似度（0.0 ~ 1.0）。

    使用 difflib.SequenceMatcher 的 ratio() 方法，
    基于最长公共子序列（LCS）计算相似度。
    1.0 = 完全相同，0.0 = 完全不同。
    """
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def search_journal(query: str) -> list[dict]:
    """
    在所有期刊中按名称或 ISSN 模糊搜索。

    得分规则：
      - ISSN 完全匹配（去连字符后 8 位一致）→ 1.0
      - 规范化名称完全一致 → 1.0
      - 查询词是规范化名称的子串 → 0.8
      - 否则用 SequenceMatcher 计算相似度
      - 低于 0.4 的不返回

    返回按得分降序排列的前 10 条结果。
    """
    journals = json.loads(JOURNALS_FILE.read_text(encoding='utf-8'))
    query_clean = _normalize(query)
    results = []

    for issn, entry in journals.items():
        score = 0
        name = _normalize(entry.get("name", ""))
        aliases = [_normalize(a) for a in entry.get("aliases", [])]

        # ISSN 精确匹配
        if issn.replace("-", "") == query.replace("-", ""):
            score = 1.0
        # 名称精确匹配
        elif query_clean == name or query_clean in aliases:
            score = 1.0
        else:
            # 模糊相似度计算
            score = max(
                _similarity(query_clean, name),
                max((_similarity(query_clean, a) for a in aliases), default=0)
            )
            # 子串匹配加成
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