import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, '2025中科院分区表完整版（附2023vs2025对比版）.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "中科院分区表完整版",
    "version": "2025 (含2023对比)",
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
        if entry:
            journals.append(entry)

    output["sheets"][sheet_name] = {
        "count": len(journals),
        "journals": journals
    }

output_path = os.path.join(script_dir, '中科院分区表完整版.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"中科院分区表完整版处理完成，共 {sum(s['count'] for s in output['sheets'].values())} 条记录")
