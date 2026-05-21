# MIT License
# Free to use, modify, and distribute. Retain this notice.

"""
📊 filter_high_rank.py — 从 journals.json 筛选高水平期刊

读取 build_database.py 生成的 journals.json，按以下条件筛选：
  1. 中科院分区在指定区间内（默认 1-2 区）
  2. JCR 分区在指定区间内（默认 Q1-Q2）
  3. 排除特定学科（默认 医学/材料/物理/化学/生物）

输出 journals_high_rank.json，用于快速查询高等级期刊。
"""

# ══════════════════════════════════════════════════════════════════════════
#  🔧 配置区 — 修改这里即可调整筛选规则
#
#  你可以：
#  - 修改 CAS_ZONES：比如 {1} 只保留 1 区，{1,2,3} 放宽到 1-3 区
#  - 修改 JCR_QUARTILES：比如 {'Q1'} 只保留 Q1
#  - 修改 EXCLUDE_DISCIPLINES：添加或移除要排除的学科关键词
#    关键词是子串匹配，比如 '医学' 会匹配 '医学'、'临床医学' 等
#    空列表 [] 表示不排除任何学科
#
#  改完后运行：python data/filter_high_rank.py
# ══════════════════════════════════════════════════════════════════════════

# 保留的中科院分区列表
#   1 = 1 区（最高），2 = 2 区，3 = 3 区，4 = 4 区
#   例如 {1, 2} 表示保留 1 区和 2 区
CAS_ZONES = {1, 2}

# 保留的 JCR 分区列表
#   Q1 = 前 25%，Q2 = 25%-50%，Q3 = 50%-75%，Q4 = 75%-100%
#   例如 {'Q1', 'Q2'} 表示保留前 50%
JCR_QUARTILES = {'Q1', 'Q2'}

# 排除的学科关键词（子串匹配，大小写不敏感）
#   期刊的 cas_discipline 字段中只要包含任一关键词即被排除
#   例如 '医学' 会排除 cas_discipline='医学' 或 '临床医学' 的期刊
EXCLUDE_DISCIPLINES = ['医学', '材料', '物理', '化学', '生物']


# ══════════════════════════════════════════════════════════════════════════
#  筛选逻辑（通常无需修改以下代码）
# ══════════════════════════════════════════════════════════════════════════

import json, os, sys

data_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(data_dir, 'journals.json')
dst_path = os.path.join(data_dir, 'journals_high_rank.json')

# 检查输入文件是否存在
if not os.path.exists(src_path):
    print(f"错误: 未找到 {src_path}", file=sys.stderr)
    print("请先运行 python data/build_database.py 生成基础数据库。", file=sys.stderr)
    sys.exit(1)

# 读取完整期刊库
with open(src_path, 'r', encoding='utf-8') as f:
    journals = json.load(f)


def discipline_excluded(discipline):
    """
    判断学科是否应被排除。

    子串匹配规则：
      - '医学' 匹配 '医学', '临床医学', '基础医学' 等
      - '材料' 匹配 '材料科学', '材料', '新材料' 等
      - '物理' 匹配 '物理与天体物理', '物理学' 等
      - '化学' 匹配 '化学', '物理化学' 等
      - '生物' 匹配 '生物学', '生物化学' 等

    不区分大小写，忽略学科名中的空格。
    """
    if not discipline:
        return False
    d = discipline.lower().replace(' ', '')
    for kw in EXCLUDE_DISCIPLINES:
        if kw in d:
            return True
    return False


# 逐条筛选
filtered = {}
for issn_key, entry in journals.items():
    # 检查中科院分区
    cas_zone = entry.get('cas_zone', 0) or 0
    if cas_zone not in CAS_ZONES:
        continue

    # 检查 JCR 分区
    jcr_q = entry.get('jcr_quartile', '')
    if jcr_q not in JCR_QUARTILES:
        continue

    # 检查学科是否在排除列表中
    if discipline_excluded(entry.get('cas_discipline', '')):
        continue

    # 通过所有筛选，保留
    filtered[issn_key] = entry

# 输出结果
with open(dst_path, 'w', encoding='utf-8') as f:
    json.dump(filtered, f, ensure_ascii=False, indent=None, separators=(',', ':'))

zone_desc = f"CAS {sorted(CAS_ZONES)} 区"
jcr_desc = f"JCR {sorted(JCR_QUARTILES)}"
exclude_desc = f"排除 {EXCLUDE_DISCIPLINES}"
print(f"journals_high_rank.json 已生成（{zone_desc} + {jcr_desc}，{exclude_desc}），共 {len(filtered)} 条记录")