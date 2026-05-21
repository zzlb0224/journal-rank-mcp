import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, 'ABDC-JQL-2025-v1-260326.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "ABDC",
    "version": "2025",
    "sheets": {}
}

# Each sheet has different header row offsets
sheet_config = {
    '2025 JQL': {'skiprows': 6, 'header_row': 6, 'col_names': ['Journal Title', 'Publisher', 'ISSN', 'ISSNOnline', 'Year Inception', 'FoR', '2025 rating']},
    '2022 JQL': {'skiprows': 7, 'header_row': 7, 'col_names': ['Journal Title', 'Publisher', 'ISSN', 'ISSN Online', 'Year Inception', 'FoR', '2022 rating']},
    '2019 JQL': {'skiprows': 7, 'header_row': 7, 'col_names': ['Journal Title', 'Publisher', 'ISSN', 'ISSN Online', 'Year Inception', 'Field of Research', '2019 Rating']},
    '2016 JQL': {'skiprows': 6, 'header_row': 6, 'col_names': ['Journal Title', 'Publisher', 'ISSN', 'ISSN Online', 'Year Inception', 'Field of Research', '2016 rating']},
    '2013 JQL': {'skiprows': 0, 'header_row': 0, 'col_names': ['Journal Name', 'ISSN', 'ISSN Online', 'Start year', 'www', 'ABDC FoR code', 'ABDC List 2013']},
    '2010 JQL': {'skiprows': 0, 'header_row': 0, 'col_names': ['Journal Name', 'ISSN', 'ISSN Online', 'Start year', 'www', 'ABDC FoR code', 'ABDC Ranking']},
}

for sheet_name in xls.sheet_names:
    if sheet_name not in sheet_config:
        continue

    cfg = sheet_config[sheet_name]
    if cfg['skiprows'] > 0:
        df = pd.read_excel(xls, sheet_name, skiprows=cfg['skiprows'])
    else:
        df = pd.read_excel(xls, sheet_name)

    # Drop the unnamed index column if it's all NaN
    unnamed_cols = [c for c in df.columns if 'Unnamed' in str(c)]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    # Assign column names
    actual_cols = list(df.columns)
    if len(actual_cols) == len(cfg['col_names']):
        df.columns = cfg['col_names']
    else:
        df.columns = actual_cols

    journals = []
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
            journals.append(entry)

    output["sheets"][sheet_name] = {
        "count": len(journals),
        "journals": journals
    }

output_path = os.path.join(script_dir, 'ABDC.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"ABDC处理完成，共 {sum(s['count'] for s in output['sheets'].values())} 条记录")
