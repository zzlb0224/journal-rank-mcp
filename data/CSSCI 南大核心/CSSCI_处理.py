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
    "sheets": {}
}

sheet_labels = ['来源期刊', '扩展版来源期刊']

for idx, sheet_name in enumerate(xls.sheet_names):
    df = pd.read_excel(xls, sheet_name, header=None)

    label = sheet_labels[idx] if idx < len(sheet_labels) else sheet_name

    # Sheet1 has title at row 0, headers at row 1, data at row 2+
    # Sheet2 has headers at row 0, data at row 1+
    start_row = 2 if idx == 0 else 1

    journals = []
    for i in range(start_row, len(df)):
        row = df.iloc[i]
        seq = row.iloc[0]
        journal_name = row.iloc[1]
        discipline = row.iloc[2]
        if pd.isna(journal_name):
            continue
        seq_val = None
        if not pd.isna(seq):
            try:
                seq_val = int(str(seq).strip())
            except (ValueError, TypeError):
                seq_val = str(seq).strip()
        entry = {
            "序号": seq_val,
            "期刊名称": str(journal_name).strip() if isinstance(journal_name, str) else journal_name,
            "学科名称": str(discipline).strip() if isinstance(discipline, str) else discipline
        }
        journals.append(entry)

    output["sheets"][label] = {
        "count": len(journals),
        "journals": journals
    }

output_path = os.path.join(script_dir, 'CSSCI.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"CSSCI处理完成，共 {sum(s['count'] for s in output['sheets'].values())} 条记录")
