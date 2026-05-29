import json, os, re
from collections import defaultdict, Counter

data_dir = os.path.dirname(os.path.abspath(__file__))

def load(name):
    with open(os.path.join(data_dir, name), encoding='utf-8') as f:
        d = json.load(f)
    return d if isinstance(d, list) else d.get('journals', [])

def norm(s):
    if not s:
        return ''
    return re.sub(r'\s+', ' ', str(s).strip().lower())

print('Loading...')
jcr = load('JCR_CAS.json')
bdhx = load('北大核心.json')
cssci = load('CSSCI.json')
print(f'  JCR_CAS: {len(jcr)}')
print(f'  北大核心: {len(bdhx)}')
print(f'  CSSCI: {len(cssci)}')

print('\nBuilding index...')
by_name_en = {}
by_name_cn = {}
by_issn = {}
for r in jcr:
    ne = norm(r.get('name_en', ''))
    if ne:
        by_name_en[ne] = r
    nc = norm(r.get('name_cn', ''))
    if nc:
        by_name_cn[nc] = r
    for k in ('issn', 'eissn'):
        v = r.get(k)
        if v:
            by_issn[v] = r

used = set(by_name_en.keys())
merged = {ne: dict(r) for ne, r in by_name_en.items()}

print('Merging 北大核心...')
matched_bd = 0
for r in bdhx:
    nc = norm(r.get('name_cn', ''))
    if not nc:
        continue
    target = by_name_cn.get(nc) or by_name_en.get(nc)
    if target:
        for k, v in r.items():
            if k != 'name_cn' and v not in (None, ''):
                target[k] = v
        matched_bd += 1
    else:
        key = nc
        while key in merged:
            key += '_'
        merged[key] = dict(r)
        used.add(key)
print(f'  matched: {matched_bd}, new: {len(bdhx) - matched_bd}')

print('Merging CSSCI...')
matched_cs = 0
for r in cssci:
    nc = norm(r.get('name_cn', ''))
    if not nc:
        continue
    target = by_name_cn.get(nc) or by_name_en.get(nc)
    if target:
        for k, v in r.items():
            if k != 'name_cn' and v not in (None, ''):
                target[k] = v
        matched_cs += 1
    else:
        key = nc
        while key in merged:
            key += '_'
        merged[key] = dict(r)
        used.add(key)
print(f'  matched: {matched_cs}, new: {len(cssci) - matched_cs}')

all_journals = list(merged.values())
print(f'\nTotal after merge: {len(all_journals)}')

# Collect all field names
field_counter = Counter()
for r in all_journals:
    for k in r:
        field_counter[k] += 1
all_fields = sorted(field_counter.keys())

# Output 1: journals.json (pure array)
out_full = os.path.join(data_dir, 'journals.json')
with open(out_full, 'w', encoding='utf-8') as f:
    json.dump(all_journals, f, ensure_ascii=False, indent=2)
print(f'\nWritten: {out_full} ({len(all_journals)} records)')

# Output 2: journals_lite.json (fields from fields_lite.md)
def parse_lite_fields():
    path = os.path.join(data_dir, 'fields_lite.md')
    fields = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'\|\s*`(\w+)`', line)
            if m:
                fields.append(m.group(1))
    return fields

lite_fields = parse_lite_fields()
print(f'\nLite fields ({len(lite_fields)}): {lite_fields}')

def pick(r, fields):
    return {k: r[k] for k in fields if k in r}

lite = [pick(r, lite_fields) for r in all_journals if any(k in r for k in lite_fields)]
out_lite = os.path.join(data_dir, 'journals_lite.json')
with open(out_lite, 'w', encoding='utf-8') as f:
    json.dump(lite, f, ensure_ascii=False, indent=2)
print(f'Written: {out_lite} ({len(lite)} records)')

# Output 3: journals_high_lite.json
def parse_jif(s):
    try:
        return float(s.replace('<', '').replace('>', '').strip())
    except:
        return 0

EXCLUDE_DISCIPLINES = {'医学', '材料科学', '物理与天体物理', '化学', '生物学'}
EXCLUDE_PUBLISHERS = {'mdpi', 'frontiers', 'hindawi'}

def is_high(r):
    # exclude warned
    if any(k.startswith('warn_') for k in r):
        return False
    # exclude disciplines
    if r.get('cas_discipline', '') in EXCLUDE_DISCIPLINES:
        return False
    # exclude publishers
    pub = (r.get('publisher') or '').lower()
    if any(ep in pub for ep in EXCLUDE_PUBLISHERS):
        return False
    # jif > 4 AND cas_zone <= 2 AND jcr_quartile in Q1/Q2
    if not (parse_jif(r.get('jif', '')) > 4):
        return False
    z = r.get('cas_zone')
    if z is None or int(str(z)) > 2:
        return False
    if r.get('jcr_quartile', '') not in ('Q1', 'Q2'):
        return False
    return True

high = [pick(r, lite_fields) for r in all_journals if is_high(r)]
out_high = os.path.join(data_dir, 'journals_high_lite.json')
with open(out_high, 'w', encoding='utf-8') as f:
    json.dump(high, f, ensure_ascii=False, indent=2)
print(f'Written: {out_high} ({len(high)} records)')

# Output 4: fields.md
lines = ['# 可用字段\n']
lines.append('| 字段 | 出现次数 | 来源 | 说明 |')
lines.append('|------|---------|------|------|')

desc = {
    'name_en': '期刊英文名',
    'name_cn': '期刊中文名',
    'issn': 'ISSN',
    'eissn': 'EISSN',
    'cn': '国内统一刊号',
    'lang': '语种',
    'journal_type': '期刊类型',
    'publisher': '出版机构',
    'review': '审稿周期/类型',
    'oaj': 'OA期刊索引 (OAJ)',
    'wos_index': 'Web of Science 索引 (SCIE/SSCI/AHCI/ESCI)',
    'fq_label': 'FQBJCR标注',
    'fq_year': 'FQBJCR年份',
    'cas_zone': '中科院分区 (1-4)',
    'cas_top': '中科院Top期刊 (1)',
    'cas_discipline': '中科院大类学科',
    'cas_sub1': '中科院小类1',
    'cas_sub1_zone': '中科院小类1分区',
    'cas_sub2': '中科院小类2',
    'cas_sub2_zone': '中科院小类2分区',
    'cas_sub3': '中科院小类3',
    'cas_sub3_zone': '中科院小类3分区',
    'cas_sub4': '中科院小类4',
    'cas_sub4_zone': '中科院小类4分区',
    'cas_sub5': '中科院小类5',
    'cas_sub5_zone': '中科院小类5分区',
    'cas_sub6': '中科院小类6',
    'cas_sub6_zone': '中科院小类6分区',
    'jif': 'JCR影响因子',
    'jcr_quartile': 'JCR分区 (Q1-Q4)',
    'jcr_rank': 'JCR排名 (e.g. 1/326)',
    'jcr_category': 'JCR学科分类',
    'oa': '开放获取 (1)',
    'xr_zone': '新锐分区 (1-4)',
    'xr_top': '新锐Top期刊 (1)',
    'xr_zone2': '新锐大类2分区',
    'xr_top2': '新锐大类2Top (1)',
    'xr_year': '新锐年份',
    'xr_warning': '新锐预警标记',
    'xr_db': '新锐数据库',
    'xr_label': '新锐标注',
    'xr_discipline_en': '新锐大类英文名',
    'xr_discipline_cn': '新锐大类中文名',
    'xr_discipline2_en': '新锐大类2英文名',
    'xr_discipline2_cn': '新锐大类2中文名',
    'xr_sub1_en': '新锐小类1英文名',
    'xr_sub1_cn': '新锐小类1中文名',
    'xr_sub1_zone': '新锐小类1分区',
    'xr_sub2_en': '新锐小类2英文名',
    'xr_sub2_cn': '新锐小类2中文名',
    'xr_sub2_zone': '新锐小类2分区',
    'xr_sub3_en': '新锐小类3英文名',
    'xr_sub3_cn': '新锐小类3中文名',
    'xr_sub3_zone': '新锐小类3分区',
    'xr_sub4_en': '新锐小类4英文名',
    'xr_sub4_cn': '新锐小类4中文名',
    'xr_sub4_zone': '新锐小类4分区',
    'xr_sub5_en': '新锐小类5英文名',
    'xr_sub5_cn': '新锐小类5中文名',
    'xr_sub5_zone': '新锐小类5分区',
    'xr_sub6_en': '新锐小类6英文名',
    'xr_sub6_cn': '新锐小类6中文名',
    'xr_sub6_zone': '新锐小类6分区',
    'warnings': '预警信息 [{year, reason}]',
    'pkua': '北大核心 (1)',
    'cssci_source': 'CSSCI来源期刊 (1)',
    'cssci_extended': 'CSSCI扩展版 (1)',
    'warn_2020': '2020年预警等级',
    'warn_2021': '2021年预警等级',
    'warn_2023': '2023年预警等级',
    'warn_2024': '2024年预警原因',
    'warn_2025': '2025年预警原因',
}

# If a field has no description, the desc.get will return '' - that's fine
for f in all_fields:
    src = []
    jcr_cas_fields = {'name_en','issn','eissn','cas_zone','cas_top','cas_discipline','wos_index','jif','jcr_quartile','jcr_rank','xr_zone','xr_top','publisher','oa','warnings',
        'review','oaj','fq_label','fq_year',
        'cas_sub1','cas_sub1_zone','cas_sub2','cas_sub2_zone','cas_sub3','cas_sub3_zone',
        'cas_sub4','cas_sub4_zone','cas_sub5','cas_sub5_zone','cas_sub6','cas_sub6_zone',
        'jcr_category','name_cn','cn','lang','journal_type',
        'xr_year','xr_warning','xr_db','xr_label',
        'xr_discipline_en','xr_discipline_cn','xr_zone2','xr_top2',
        'xr_discipline2_en','xr_discipline2_cn',
        'xr_sub1_en','xr_sub1_cn','xr_sub1_zone',
        'xr_sub2_en','xr_sub2_cn','xr_sub2_zone',
        'xr_sub3_en','xr_sub3_cn','xr_sub3_zone',
        'xr_sub4_en','xr_sub4_cn','xr_sub4_zone',
        'xr_sub5_en','xr_sub5_cn','xr_sub5_zone',
        'xr_sub6_en','xr_sub6_cn','xr_sub6_zone',
        'warn_2020','warn_2021','warn_2023','warn_2024','warn_2025'}
    if f in jcr_cas_fields:
        src.append('JCR_CAS')
    if f in ('name_cn', 'pkua'):
        src.append('北大核心')
    if f in ('name_cn', 'cssci_source', 'cssci_extended'):
        src.append('CSSCI')
    lines.append('| `{}` | {} | {} | {} |'.format(f, field_counter[f], ' / '.join(src), desc.get(f, '')))

md_path = os.path.join(data_dir, 'fields.md')
with open(md_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines))
print(f'Written: {md_path}')

# Copy to target dirs
import shutil
mcp_dst = os.path.join(data_dir, '..', 'src', 'journal_rank_mcp', 'journals.json')
shutil.copy2(out_full, mcp_dst)
print(f'Copied to: {mcp_dst}')

scispace_dst = os.path.join(data_dir, '..', '.opencode', 'skills', 'search-scispace', 'journals_high_lite.json')
shutil.copy2(out_high, scispace_dst)
print(f'Copied to: {scispace_dst}')

skill_dst = os.path.join(data_dir, '..', '.opencode', 'skills', 'journal-rank', 'journals.json')
shutil.copy2(out_full, skill_dst)
print(f'Copied to: {skill_dst}')

print('\nDone!')
