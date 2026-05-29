import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, '2023版第十版北大核心 完整榜单.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "北大核心",
    "version": "2023第十版",
    "journals": []
}

FIELD_MAP = {
    '中文刊名': '_name_cn',
    '刊名': '_name_cn',
    '期刊名称': '_name_cn',
    '排名': '_bdhx_rank',
    '排序号': '_bdhx_rank',
    '序号': '_bdhx_rank',
    '学科门类': 'bdhx_discipline',
    '学科分类': '_bdhx_category',
    '学科': '_bdhx_category',
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
        if not any(k in entry for k in ('_name_cn',)):
            continue
        entry['pkua'] = "北大核心"
        output["journals"].append(entry)

output_path = os.path.join(script_dir, '北大核心.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"北大核心处理完成，共 {len(output['journals'])} 条记录")
