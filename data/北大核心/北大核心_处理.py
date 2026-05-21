import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, '2023版第十版北大核心 完整榜单.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "北大核心",
    "version": "2023第十版",
    "sheets": {}
}

for sheet_name in xls.sheet_names:
    df = pd.read_excel(xls, sheet_name)
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
        if any(k in entry for k in ('中文刊名', '刊名')):
            journals.append(entry)

    key = sheet_name.replace(" ", "_")
    output["sheets"][sheet_name] = {
        "count": len(journals),
        "journals": journals
    }

output_path = os.path.join(script_dir, '北大核心.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"北大核心处理完成，共 {sum(s['count'] for s in output['sheets'].values())} 条记录")
