import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, '2025中科院分区表完整版（附2023vs2025对比版）.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "中科院分区表完整版",
    "version": "2025 (含2023对比)",
    "journals": []
}

FIELD_MAP = {
    '期刊名称': '_name_cn',
    '刊名': '_name_cn',
    '期刊': '_name_cn',
    '中文刊名': '_name_cn',
    '英文刊名': '_name_en',
    'ISSN': 'issn',
    'ISSN1': 'issn',
    '2025年分区': 'cas_zone_2025',
    '2025分区': 'cas_zone_2025',
    '分区': 'cas_zone_2025',
    '2023年分区': 'cas_zone_2023',
    '2023分区': 'cas_zone_2023',
    '是否Top期刊': 'cas_top',
    'Top期刊': 'cas_top',
    '是否OA': 'cas_open_access',
    'OA': 'cas_open_access',
    '学科': 'cas_discipline',
    '学科名称': 'cas_discipline',
}

for sheet_name in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name)

    cols_clean = [c.strip() if isinstance(c, str) else c for c in df.columns]
    df.columns = cols_clean

    for _, row in df.iterrows():
        entry = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                continue
            std_field = FIELD_MAP.get(col, col)
            entry[std_field] = val
        if entry.get('_name_cn') or entry.get('_name_en'):
            output["journals"].append(entry)

output_path = os.path.join(script_dir, '中科院分区表完整版.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"中科院分区表完整版处理完成，共 {len(output['journals'])} 条记录")
