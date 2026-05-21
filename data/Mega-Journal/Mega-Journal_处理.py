import sys, json, os
import pdfplumber

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, '2025年 Mega-Journal 列表.pdf')

output = {
    "source": "Mega-Journal",
    "version": "2025",
    "count": 0,
    "journals": []
}

with pdfplumber.open(src_file) as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line in ('2025 年 Mega-Journal 列表', '最近 2 年发文数量，任一年份超过 3000 的期刊标记为Mega Journal。', '刊名 大类 分区'):
                continue

            parts = line.rsplit(maxsplit=2)
            if len(parts) == 3:
                journal_name, category, tier = parts
                entry = {
                    "刊名": journal_name,
                    "大类": category,
                    "分区": int(tier)
                }
                output["journals"].append(entry)

output["count"] = len(output["journals"])

output_path = os.path.join(script_dir, 'Mega-Journal.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Mega-Journal处理完成，共 {len(output['journals'])} 条记录")
