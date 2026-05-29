import sys, json, os
import pandas as pd

sys.stdout.reconfigure(encoding='utf-8')

script_dir = os.path.dirname(os.path.abspath(__file__))
src_file = os.path.join(script_dir, 'ABDC-JQL-2025-v1-260326.xlsx')

xls = pd.ExcelFile(src_file)

output = {
    "source": "ABDC",
    "version": "2025",
    "journals": []
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

RATING_FIELDS = {
    '2025 JQL': '2025 rating',
    '2022 JQL': '2022 rating',
    '2019 JQL': '2019 Rating',
    '2016 JQL': '2016 rating',
    '2013 JQL': 'ABDC List 2013',
    '2010 JQL': 'ABDC Ranking',
}

for sheet_name in xls.sheet_names:
    if sheet_name not in sheet_config:
        continue

    cfg = sheet_config[sheet_name]
    if cfg['skiprows'] > 0:
        df = pd.read_excel(xls, sheet_name, skiprows=cfg['skiprows'])
    else:
        df = pd.read_excel(xls, sheet_name)

    unnamed_cols = [c for c in df.columns if 'Unnamed' in str(c)]
    if unnamed_cols:
        df = df.drop(columns=unnamed_cols)

    actual_cols = list(df.columns)
    if len(actual_cols) == len(cfg['col_names']):
        df.columns = cfg['col_names']
    else:
        df.columns = actual_cols

    rating_col = RATING_FIELDS[sheet_name]
    for _, row in df.iterrows():
        entry = {}
        name_en = row.get('Journal Title') or row.get('Journal Name')
        if pd.isna(name_en) or not str(name_en).strip():
            continue
        entry['_name_en'] = str(name_en).strip()

        publisher = row.get('Publisher')
        if pd.notna(publisher):
            entry['publisher'] = str(publisher).strip()

        issn = row.get('ISSN')
        if pd.notna(issn):
            entry['issn'] = str(issn).strip()

        issn_online = row.get('ISSNOnline') or row.get('ISSN Online')
        if pd.notna(issn_online):
            entry['eissn'] = str(issn_online).strip()

        rating = row.get(rating_col)
        if pd.notna(rating):
            entry['abdc_rating'] = str(rating).strip()

        if entry:
            output["journals"].append(entry)

output_path = os.path.join(script_dir, 'ABDC.json')
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"ABDC处理完成，共 {len(output['journals'])} 条记录")
