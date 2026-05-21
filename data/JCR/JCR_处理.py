import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, '2025影响因子.xlsx')

df = pd.read_excel(src_file)

output = {
    "source": "JCR",
    "version": "2025",
    "count": len(df),
    "journals": []
}

for _, row in df.iterrows():
    entry = {}
    for col in df.columns:
        val = row[col]
        if pd.isna(val):
            continue
        if isinstance(val, str):
            val = val.strip()
        entry[col] = val
    if entry:
        output["journals"].append(entry)

output_path = os.path.join(script_dir, 'JCR.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"JCR处理完成，共 {len(output['journals'])} 条记录")
