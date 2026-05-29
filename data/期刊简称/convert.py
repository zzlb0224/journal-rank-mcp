"""
MIT License
Copyright (c) 2025 周智

将 2025年4月最新期刊缩写名称.txt 转换为平铺 JSON 格式，
供 data/build_database.py 直接加载。
"""

import json
import os

txt_path = os.path.join(os.path.dirname(__file__), '2025年4月最新期刊缩写名称.txt')
json_path = os.path.join(os.path.dirname(__file__), '期刊缩写.json')

entries = []
with open(txt_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or '\t' not in line:
            continue
        full, abbr = line.split('\t', 1)
        entries.append({
            '_name_en': full.strip(),
            'abbreviated_name': abbr.strip(),
        })

output = {
    'source': '期刊简称',
    'version': '2025-04',
    'journals': entries,
}

with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'已转换 {len(entries)} 条期刊缩写 → {json_path}')