import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, 'CSSCI 2025-26')
src_file = os.path.join(src_dir, '中文社会科学引文索引（CSSCI）来源期刊及扩展版目录（2025-2026）.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "CSSCI",
    "version": "2025-2026",
    "journals": []
}

sheet_labels = ['来源期刊', '扩展版来源期刊']

for idx, sheet_name in enumerate(xls.sheet_names):
    df = pd.read_excel(xls, sheet_name, header=None)

    label = sheet_labels[idx] if idx < len(sheet_labels) else sheet_name
    cssci_type = "来源期刊" if "来源" in label and "扩展" not in label else "扩展版"

    start_row = 2 if idx == 0 else 1

    for i in range(start_row, len(df)):
        row = df.iloc[i]
        journal_name = row.iloc[1]
        discipline = row.iloc[2]
        if pd.isna(journal_name):
            continue
        entry = {
            "_name_cn": str(journal_name).strip() if isinstance(journal_name, str) else journal_name,
            "cssci_discipline": str(discipline).strip() if isinstance(discipline, str) else discipline,
            "cssci": cssci_type
        }
        output["journals"].append(entry)

output_path = os.path.join(script_dir, 'CSSCI.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"CSSCI处理完成，共 {len(output['journals'])} 条记录")
