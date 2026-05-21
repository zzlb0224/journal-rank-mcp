import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, '2025中科院分区表.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "中科院分区表",
    "version": "2025",
    "sheets": {}
}

# Sheets that have simple single-header structure
simple_sheets = ['综合', '化学', '生物', '医学', '农林科学', '计算机科学',
                 '工程技术', '材料科学', '环境科学与生态学', '地球科学',
                 '物理与天体物理', '管理']

# Sheets that need skiprows
special_sheets = {
    '巨型期刊': 1,
    'IF＜20': 1,
}

for sheet_name in xls.sheet_names:
    if sheet_name in simple_sheets:
        df = pd.read_excel(xls, sheet_name)
    elif sheet_name in special_sheets:
        df = pd.read_excel(xls, sheet_name, skiprows=special_sheets[sheet_name])
    else:
        continue

    cols_clean = [c.strip() if isinstance(c, str) else c for c in df.columns]
    df.columns = cols_clean

    journals = []
    for _, row in df.iterrows():
        entry = {}
        for col in df.columns:
            val = row[col]
            if pd.isna(val):
                continue
            entry[col] = val
        if entry:
            journals.append(entry)

    output["sheets"][sheet_name] = {
        "count": len(journals),
        "journals": journals
    }

output_path = os.path.join(script_dir, '中科院分区表.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"中科院分区表处理完成，共 {sum(s['count'] for s in output['sheets'].values())} 条记录")
