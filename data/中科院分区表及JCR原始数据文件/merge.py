import csv, os, json, re
from collections import defaultdict

data_dir = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.join(data_dir, '..')

def read_csv(filename):
    path = os.path.join(data_dir, filename)
    if not os.path.exists(path):
        print(f'  [SKIP] not found: {filename}')
        return []
    with open(path, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader)

def split_issn(raw):
    if not raw:
        return None, None
    raw = str(raw).strip()
    if '/' in raw:
        parts = raw.split('/', 1)
        return parts[0].strip(), parts[1].strip()
    if len(raw) == 9 and raw[4] == '-':
        return raw, None
    return raw, None

def norm_name(name):
    if not name:
        return ''
    return re.sub(r'\s+', ' ', str(name).strip().lower())

def clean_entry(entry):
    return {k: v for k, v in entry.items() if v not in (None, '', 'nan')}

print('Reading FQBJCR2025...')
fq_data = read_csv('FQBJCR2025-UTF8.csv')
print(f'  {len(fq_data)} rows')

print('Reading JCR2024...')
jcr_data = read_csv('JCR2024-UTF8.csv')
print(f'  {len(jcr_data)} rows')

print('Reading XR2026...')
xr_data = read_csv('XR2026-UTF8.csv')
print(f'  {len(xr_data)} rows')

print('Reading warn lists...')
warn_data = {}
for yr in ['2025', '2024', '2023', '2021', '2020']:
    warn_data[yr] = read_csv(f'GJQKYJMD{yr}.csv')
    print(f'  {yr}: {len(warn_data[yr])} rows')

print('\nBuilding index...')
issn_idx = defaultdict(list)
name_idx = defaultdict(list)

for r in fq_data:
    issn, eissn = split_issn(r.get('ISSN/EISSN', ''))
    r['_issn'] = issn
    r['_eissn'] = eissn
    key = issn or eissn or ''
    if key:
        issn_idx[key].append(r)
    n = norm_name(r.get('Journal', ''))
    if n:
        name_idx[n].append(r)

for r in jcr_data:
    issn = r.get('ISSN', '').strip() or None
    eissn = r.get('eISSN', '').strip() or None
    r['_issn'] = issn
    r['_eissn'] = eissn
    for key in (issn, eissn):
        if key:
            issn_idx[key].append(r)
    n = norm_name(r.get('Journal', ''))
    if n:
        name_idx[n].append(r)

for r in xr_data:
    issn = r.get('ISSN', '').strip() or None
    eissn = r.get('EISSN', '').strip() or None
    r['_issn'] = issn
    r['_eissn'] = eissn
    for key in (issn, eissn):
        if key:
            issn_idx[key].append(r)
    n = norm_name(r.get('Journal', ''))
    if n:
        name_idx[n].append(r)

print(f'  ISSN index: {len(issn_idx)} keys')
print(f'  Name index: {len(name_idx)} keys')

print('\nMerging records...')
merged = {}
used_names = set()

for r in fq_data:
    issn = r.get('_issn')
    eissn = r.get('_eissn')
    name_en = r.get('Journal', '').strip()
    name_norm = norm_name(name_en)
    
    cas_zone_raw = r.get('大类分区', '').split('[')[0].strip()
    cas_zone = int(cas_zone_raw) if cas_zone_raw.isdigit() else None
    
    oa_raw = r.get('Open Access', '').strip()
    oa = 1 if oa_raw == '是' else None
    
    entry = {
        'name_en': name_en,
        'issn': issn,
        'eissn': eissn,
    }
    if cas_zone is not None:
        entry['cas_zone'] = cas_zone
    if r.get('Top', '').strip() == '是':
        entry['cas_top'] = 1
    if r.get('大类', '').strip():
        entry['cas_discipline'] = r.get('大类', '').strip()
    if oa is not None:
        entry['oa'] = oa
    if r.get('Web of Science', '').strip():
        entry['wos_index'] = r.get('Web of Science', '').strip()
    if r.get('Review', '').strip():
        entry['review'] = r.get('Review', '').strip()
    if r.get('OA Journal Index（OAJ）', '').strip():
        entry['oaj'] = r.get('OA Journal Index（OAJ）', '').strip()
    if r.get('标注', '').strip():
        entry['fq_label'] = r.get('标注', '').strip()
    if r.get('年份', '').strip():
        entry['fq_year'] = r.get('年份', '').strip()
    # 小类1~6
    for i in range(1, 7):
        sub = r.get(f'小类{i}', '').strip() if f'小类{i}' in r else None
        sub_zone = r.get(f'小类{i}分区', '').strip() if f'小类{i}分区' in r else None
        if sub:
            entry[f'cas_sub{i}'] = sub
        if sub_zone:
            entry[f'cas_sub{i}_zone'] = sub_zone
    
    jcr_raw = None
    for key in (issn, eissn):
        if key and key in issn_idx:
            candidates = [c for c in issn_idx[key] if c.get('IF(2024)')]
            if candidates:
                jcr_raw = candidates[0]
                break
    if not jcr_raw and name_norm in name_idx:
        candidates = [c for c in name_idx[name_norm] if c.get('IF(2024)')]
        if candidates:
            jcr_raw = candidates[0]
    
    if jcr_raw:
        if jcr_raw.get('IF(2024)', '').strip():
            entry['jif'] = jcr_raw.get('IF(2024)', '').strip()
        if jcr_raw.get('IF Quartile(2024)', '').strip():
            entry['jcr_quartile'] = jcr_raw.get('IF Quartile(2024)', '').strip()
        if jcr_raw.get('IF Rank(2024)', '').strip():
            entry['jcr_rank'] = jcr_raw.get('IF Rank(2024)', '').strip()
        if jcr_raw.get('Category', '').strip():
            entry['jcr_category'] = jcr_raw.get('Category', '').strip()
    
    xr_raw = None
    for key in (issn, eissn):
        if key and key in issn_idx:
            candidates = [c for c in issn_idx[key] if c.get('大类新锐分区')]
            if candidates:
                xr_raw = candidates[0]
                break
    if not xr_raw and name_norm in name_idx:
        candidates = [c for c in name_idx[name_norm] if c.get('大类新锐分区')]
        if candidates:
            xr_raw = candidates[0]
    
    if xr_raw:
        name_cn = xr_raw.get('中文刊名', '').strip()
        if name_cn:
            entry['name_cn'] = name_cn
        if xr_raw.get('CN', '').strip():
            entry['cn'] = xr_raw.get('CN', '').strip()
        if xr_raw.get('语种', '').strip():
            entry['lang'] = xr_raw.get('语种', '').strip()
        if xr_raw.get('期刊类型', '').strip():
            entry['journal_type'] = xr_raw.get('期刊类型', '').strip()
        if xr_raw.get('数据库', '').strip():
            entry['xr_db'] = xr_raw.get('数据库', '').strip()
        if xr_raw.get('标注', '').strip():
            entry['xr_label'] = xr_raw.get('标注', '').strip()
        if xr_raw.get('年份', '').strip():
            entry['xr_year'] = xr_raw.get('年份', '').strip()
        if xr_raw.get('预警标记', '').strip():
            entry['xr_warning'] = xr_raw.get('预警标记', '').strip()
        zone_raw = xr_raw.get('大类新锐分区', '').strip()
        if zone_raw:
            entry['xr_zone'] = int(zone_raw.replace('区', '').strip())
        xr_top = xr_raw.get('Top', '').strip()
        if xr_top in ('是', 'Top'):
            entry['xr_top'] = 1
        pub = xr_raw.get('出版机构', '').strip()
        if pub:
            entry['publisher'] = pub
        # 大类2
        if xr_raw.get('大类2英文名', '').strip():
            entry['xr_discipline2_en'] = xr_raw.get('大类2英文名', '').strip()
        if xr_raw.get('大类2中文名', '').strip():
            entry['xr_discipline2_cn'] = xr_raw.get('大类2中文名', '').strip()
        if xr_raw.get('大类2新锐分区', '').strip():
            entry['xr_zone2'] = xr_raw.get('大类2新锐分区', '').strip().replace('区', '').strip()
        if xr_raw.get('大类2Top', '').strip() in ('是', 'Top'):
            entry['xr_top2'] = 1
        # 小类1~6 from XR
        for i in range(1, 7):
            sub_en = xr_raw.get(f'小类{i}英文名', '').strip() if f'小类{i}英文名' in xr_raw else None
            sub_cn = xr_raw.get(f'小类{i}中文名', '').strip() if f'小类{i}中文名' in xr_raw else None
            sub_zone = xr_raw.get(f'小类{i}新锐分区', '').strip() if f'小类{i}新锐分区' in xr_raw else None
            if sub_en:
                entry[f'xr_sub{i}_en'] = sub_en
            if sub_cn:
                entry[f'xr_sub{i}_cn'] = sub_cn
            if sub_zone:
                entry[f'xr_sub{i}_zone'] = sub_zone.replace('区', '').strip()
        # 大类英文名/中文名
        if xr_raw.get('大类英文名', '').strip():
            entry['xr_discipline_en'] = xr_raw.get('大类英文名', '').strip()
        if xr_raw.get('大类中文名', '').strip():
            entry['xr_discipline_cn'] = xr_raw.get('大类中文名', '').strip()
    
    for yr in ['2025', '2024', '2023', '2021', '2020']:
        for wr in warn_data[yr]:
            wname = norm_name(wr.get('Journal', ''))
            if wname == name_norm:
                reason_key = f'预警原因（{yr}）' if yr in ('2024', '2025') else f'预警等级（{yr}）'
                reason = wr.get(reason_key, '').strip()
                entry[f'warn_{yr}'] = reason
    
    entry = clean_entry(entry)
    merged[name_norm] = entry
    used_names.add(name_norm)

# also add unmatched JCR records
for r in jcr_data:
    name_en = r.get('Journal', '').strip()
    name_norm = norm_name(name_en)
    if name_norm in used_names:
        continue
    issn = r.get('_issn')
    eissn = r.get('_eissn')
    entry = {
        'name_en': name_en,
        'issn': issn,
        'eissn': eissn,
    }
    if r.get('IF(2024)', '').strip():
        entry['jif'] = r.get('IF(2024)', '').strip()
    if r.get('IF Quartile(2024)', '').strip():
        entry['jcr_quartile'] = r.get('IF Quartile(2024)', '').strip()
    if r.get('IF Rank(2024)', '').strip():
        entry['jcr_rank'] = r.get('IF Rank(2024)', '').strip()
    if r.get('Category', '').strip():
        entry['jcr_category'] = r.get('Category', '').strip()
    entry = clean_entry(entry)
    merged[name_norm] = entry
    used_names.add(name_norm)

# also add unmatched XR records
for r in xr_data:
    name_en = r.get('Journal', '').strip()
    name_norm = norm_name(name_en)
    if name_norm in used_names:
        continue
    issn = r.get('ISSN', '').strip() or None
    eissn = r.get('EISSN', '').strip() or None
    entry = {
        'name_en': name_en,
        'issn': issn,
        'eissn': eissn,
    }
    name_cn = r.get('中文刊名', '').strip()
    if name_cn:
        entry['name_cn'] = name_cn
    pub = r.get('出版机构', '').strip()
    if pub:
        entry['publisher'] = pub
    zone_raw = r.get('大类新锐分区', '').strip()
    if zone_raw:
        entry['xr_zone'] = int(zone_raw.replace('区', '').strip())
    if r.get('CN', '').strip():
        entry['cn'] = r.get('CN', '').strip()
    if r.get('语种', '').strip():
        entry['lang'] = r.get('语种', '').strip()
    if r.get('期刊类型', '').strip():
        entry['journal_type'] = r.get('期刊类型', '').strip()
    if r.get('数据库', '').strip():
        entry['xr_db'] = r.get('数据库', '').strip()
    if r.get('标注', '').strip():
        entry['xr_label'] = r.get('标注', '').strip()
    if r.get('年份', '').strip():
        entry['xr_year'] = r.get('年份', '').strip()
    if r.get('预警标记', '').strip():
        entry['xr_warning'] = r.get('预警标记', '').strip()
    xr_top = r.get('Top', '').strip()
    if xr_top in ('是', 'Top'):
        entry['xr_top'] = 1
    if r.get('大类英文名', '').strip():
        entry['xr_discipline_en'] = r.get('大类英文名', '').strip()
    if r.get('大类中文名', '').strip():
        entry['xr_discipline_cn'] = r.get('大类中文名', '').strip()
    if r.get('大类2英文名', '').strip():
        entry['xr_discipline2_en'] = r.get('大类2英文名', '').strip()
    if r.get('大类2中文名', '').strip():
        entry['xr_discipline2_cn'] = r.get('大类2中文名', '').strip()
    if r.get('大类2新锐分区', '').strip():
        entry['xr_zone2'] = r.get('大类2新锐分区', '').strip().replace('区', '').strip()
    if r.get('大类2Top', '').strip() in ('是', 'Top'):
        entry['xr_top2'] = 1
    for i in range(1, 7):
        sub_en = r.get(f'小类{i}英文名', '').strip() if f'小类{i}英文名' in r else None
        sub_cn = r.get(f'小类{i}中文名', '').strip() if f'小类{i}中文名' in r else None
        sub_zone = r.get(f'小类{i}新锐分区', '').strip() if f'小类{i}新锐分区' in r else None
        if sub_en:
            entry[f'xr_sub{i}_en'] = sub_en
        if sub_cn:
            entry[f'xr_sub{i}_cn'] = sub_cn
        if sub_zone:
            entry[f'xr_sub{i}_zone'] = sub_zone.replace('区', '').strip()
    entry = clean_entry(entry)
    merged[name_norm] = entry

print(f'\nTotal merged records: {len(merged)}')

output = {
    'source': '中科院分区表完整版',
    'version': '2025',
    'count': len(merged),
    'journals': list(merged.values())
}

out_path = os.path.join(out_dir, 'JCR_CAS.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f'Written to: {out_path}')
print('Done!')
