# ══════════════════════════════════════════════════════════════════════════
#  MIT License — https://github.com/zzlb0224/journal-rank-mcp
#  Free to use, modify, and distribute. Retain this notice.
#
#  📦 期刊数据流水线
#  ───────────────────────────────────────────
#  职责：从 data/ 下各子目录的原始 JSON 读入 → 合并去重 → 输出
#        journals.json（ISSN 为 key 的完整库）
#        journals_high_rank.json（CAS 1-2 区 + JCR Q1-Q2 过滤库）
#        journals.csv（扁平表格）
#
#  🔧 如需扩展字段或新增期刊级别：
#     1. 将原始数据文件放入 data/ 下对应子目录
#     2. 在 load_journals() 能加载到的位置（参考现有 JSON 结构，
#        需包含 "source" 和 "journals" 字段）
#     3. 在本文件底部附近的 elif 分支添加该 source 的解析逻辑
#     4. 在 JournalRecord.__slots__ 添加新字段
#     5. 在 JSON 输出段（# ── Build JSON output ── 附近）
#        添加该字段到 entry
#     6. 若需加入过滤条件，在 journals_high_rank.json 的
#        筛选逻辑中添加
# ══════════════════════════════════════════════════════════════════════════

import sys, json, os, re, csv
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

data_dir = os.path.dirname(os.path.abspath(__file__))

# ─── helpers ───────────────────────────────────────────────────────────

def safe_str(v):
    if v is None:
        return ''
    s = str(v).strip()
    return s if s.lower() != 'nan' else ''

def safe_int(v):
    if v is None:
        return None
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return None

def safe_float(v):
    if v is None:
        return None
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None

def normalize_name(n):
    return re.sub(r'\s+', ' ', str(n).strip().lower()) if n else ''

def clean_issn(s):
    return s.replace('\u2013', '-').replace('\u2014', '-').replace('-', '').replace(' ', '').replace('\t', '').strip().upper()

def is_valid_issn(s):
    """ISSN 应为 8 位纯数字或末位 X（排除 JIF 等误入值）"""
    c = clean_issn(s)
    if len(c) != 8:
        return False
    if not c[:-1].isdigit():
        return False
    if c[-1] not in '0123456789Xx':
        return False
    return True

# ─── Conflict tracker ──────────────────────────────────────────────────

class ConflictTracker:
    def __init__(self):
        self.name_data = defaultdict(dict)
        self.conflicts = []

    def record(self, name_en='', name_cn='', issn='', source=''):
        nen = normalize_name(name_en)
        ncn = normalize_name(name_cn)
        cissn = clean_issn(issn) if issn and is_valid_issn(issn) else ''
        for nm in (nen, ncn):
            if nm and cissn:
                if cissn not in self.name_data[nm]:
                    self.name_data[nm][cissn] = set()
                self.name_data[nm][cissn].add(source)

    def detect(self, record_lookup):
        self.conflicts.clear()
        for nm, issn_sources in self.name_data.items():
            if len(issn_sources) < 2:
                continue
            issns_sorted = sorted(issn_sources.keys())
            rec = record_lookup.get(nm)
            if rec:
                rec_issn = clean_issn(rec.get('issn', '') or '')
                rec_eissn = clean_issn(rec.get('eissn', '') or '')
                known = {s for s in (rec_issn, rec_eissn) if s}
                remaining = set(issns_sorted) - known
                if not remaining:
                    continue
            issn_detail = []
            for isxn in issns_sorted:
                srcs = issn_sources[isxn]
                issn_detail.append(f"{isxn} ({', '.join(sorted(srcs))})")
            self.conflicts.append({
                "type": "同名多ISSN",
                "name": nm,
                "issns": issn_detail,
                "detail": "同一期刊名称在不同数据源中出现多个不同ISSN，可能为不同期刊"
            })

    def write_report(self, path, record_lookup):
        self.detect(record_lookup)
        lines = []
        lines.append("# 数据合并冲突报告\n")
        lines.append(f"> 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        lines.append(f"> 总冲突数: {len(self.conflicts)}\n")
        lines.append("---\n")

        if not self.conflicts:
            lines.append("未发现冲突。\n")
        else:
            for i, c in enumerate(self.conflicts, 1):
                lines.append(f"## {i}. {c['type']}\n")
                lines.append(f"- **名称**: `{c['name']}`\n")
                lines.append(f"- **ISSN来源**:\n")
                for item in c['issns']:
                    lines.append(f"  - `{item}`\n")
                lines.append(f"- **说明**: {c['detail']}\n")
                lines.append("\n")

        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        print(f"冲突报告已生成: {path}")

tracker = ConflictTracker()

# ─── Collect all entries with source tag ───────────────────────────────

def load_journals():
    json_files = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith('.json') and f != 'journals.json':
                json_files.append(os.path.join(root, f))

    all_entries = []
    for jf in sorted(json_files):
        with open(jf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        source = data.get('source', '')
        if 'journals' in data and isinstance(data['journals'], list):
            for entry in data['journals']:
                entry['_source'] = source
                all_entries.append(entry)
        elif 'sheets' in data and isinstance(data['sheets'], dict):
            for sheet_name, sheet_data in data['sheets'].items():
                if 'journals' in sheet_data:
                    for entry in sheet_data['journals']:
                        entry['_source'] = source
                        entry['_sheet'] = sheet_name
                        all_entries.append(entry)
    return all_entries

all_entries = load_journals()

# ─── Unified journal index ─────────────────────────────────────────────

class JournalRecord:
    __slots__ = (
        'name_cn', 'name_en',
        'issn', 'eissn', 'publisher',
        'bdhx_core', 'bdhx_rank', 'bdhx_discipline', 'bdhx_category',
        'cas_zone_2025', 'cas_zone_2023', 'cas_top', 'cas_open_access', 'cas_discipline',
        'abdc_rating', 'abdc_year',
        'cssci_source', 'cssci_extended', 'cssci_discipline',
        'jif', 'jcr_quartile', 'jcr_rank', 'jcr_publisher',
        'mega_journal', 'mega_category', 'mega_zone',
        'abbreviated_name',
        '_key_issn', '_key_en', '_key_cn',
    )

    def __init__(self):
        for s in self.__slots__:
            setattr(self, s, None if s.startswith('_') else (
                False if s in ('bdhx_core', 'cssci_source', 'cssci_extended', 'cas_top', 'cas_open_access', 'mega_journal')
                else ''
            ))

    def to_dict(self):
        return {s: getattr(self, s) for s in self.__slots__ if not s.startswith('_')}

    @property
    def key(self):
        if self.issn:
            return self.issn
        if self.name_en:
            return normalize_name(self.name_en)
        if self.name_cn:
            return normalize_name(self.name_cn)
        return f"unknown_{id(self)}"


index_issn = {}
index_en = {}
index_cn = {}

def get_or_create(issn='', name_en='', name_cn=''):
    cissn = clean_issn(issn) if issn and is_valid_issn(issn) else ''
    nen = normalize_name(name_en)
    ncn = normalize_name(name_cn)

    candidates = set()
    if cissn and cissn in index_issn:
        candidates.add(index_issn[cissn])
    if nen and nen in index_en:
        candidates.add(index_en[nen])
    if ncn and ncn in index_cn:
        candidates.add(index_cn[ncn])

    if len(candidates) == 1:
        rec = candidates.pop()
    elif len(candidates) > 1:
        rec = candidates.pop()
        for other in candidates:
            _merge_records(rec, other)
            for key, val in list(index_issn.items()):
                if val is other:
                    index_issn[key] = rec
            for key, val in list(index_en.items()):
                if val is other:
                    index_en[key] = rec
            for key, val in list(index_cn.items()):
                if val is other:
                    index_cn[key] = rec
    else:
        rec = JournalRecord()

    if cissn and cissn not in index_issn:
        index_issn[cissn] = rec
        rec._key_issn = cissn
    if nen and nen not in index_en:
        index_en[nen] = rec
        rec._key_en = nen
    if ncn and ncn not in index_cn:
        index_cn[ncn] = rec
        rec._key_cn = ncn

    return rec


def _merge_records(target, source):
    for s in JournalRecord.__slots__:
        if s.startswith('_'):
            continue
        tv = getattr(target, s)
        sv = getattr(source, s)
        if not sv:
            continue
        if not tv:
            setattr(target, s, sv)
            continue
        if isinstance(tv, str) and len(sv) > len(tv):
            setattr(target, s, sv)

    # Merge issn/eissn: if different, try to populate both fields
    t_issn = clean_issn(target.issn or '')
    t_eissn = clean_issn(target.eissn or '')
    s_issn = clean_issn(source.issn or '')
    s_eissn = clean_issn(source.eissn or '')
    all_source = {s for s in (s_issn, s_eissn) if s}
    all_target = {t_issn, t_eissn}

    for src in all_source:
        if src not in all_target:
            if not target.issn:
                target.issn = src
            elif not target.eissn:
                target.eissn = src
            elif src != clean_issn(target.issn or '') and src != clean_issn(target.eissn or ''):
                target.eissn = src

# ─── Process each entry ────────────────────────────────────────────────

for entry in all_entries:
    source = entry.get('_source', '')
    sheet = entry.get('_sheet', '')

    if source == '北大核心':
        name_cn = safe_str(entry.get('中文刊名', ''))
        rec = get_or_create(name_cn=name_cn)
        rec.name_cn = name_cn or rec.name_cn
        rec.bdhx_core = True
        rec.bdhx_rank = safe_int(entry.get('排序'))
        rec.bdhx_discipline = safe_str(entry.get('学科门类', ''))
        rec.bdhx_category = safe_str(entry.get('学科', ''))
        tracker.record(name_cn=name_cn, source=source)

    elif source == 'CSSCI':
        name_cn = safe_str(entry.get('期刊名称', ''))
        rec = get_or_create(name_cn=name_cn)
        rec.name_cn = name_cn or rec.name_cn
        rec.cssci_discipline = safe_str(entry.get('学科名称', ''))
        if '扩展版' in sheet:
            rec.cssci_extended = True
        else:
            rec.cssci_source = True
        tracker.record(name_cn=name_cn, source=source)

    elif source == '中科院分区表':
        name_cn = safe_str(entry.get('刊名', '')) or safe_str(entry.get('期刊', '')) or safe_str(entry.get('期刊名', ''))
        name_en = safe_str(entry.get('刊名', ''))
        issn = safe_str(entry.get('ISSN', ''))
        rec = get_or_create(name_cn=name_cn, name_en=name_en, issn=issn)
        rec.name_cn = name_cn or rec.name_cn
        if issn and is_valid_issn(issn):
            if not rec.issn:
                rec.issn = issn
            elif clean_issn(issn) != clean_issn(rec.issn or '') and not rec.eissn:
                rec.eissn = issn
        zone = safe_int(entry.get('分区'))
        if zone and not rec.cas_zone_2025:
            rec.cas_zone_2025 = zone
        discipline = safe_str(entry.get('大类', '')) or safe_str(sheet)
        if discipline and not rec.cas_discipline:
            rec.cas_discipline = discipline
        jif = safe_float(entry.get('2024IF'))
        if jif and not rec.jif:
            rec.jif = jif
        tracker.record(name_en=name_en, name_cn=name_cn, issn=issn, source=source)

    elif source == '中科院分区表完整版':
        name_cn = safe_str(entry.get('期刊名称', ''))
        rec = get_or_create(name_cn=name_cn)
        rec.name_cn = name_cn or rec.name_cn
        zone_2025 = safe_int(entry.get('2025分区'))
        if zone_2025:
            rec.cas_zone_2025 = zone_2025
        zone_2023 = safe_int(entry.get('2023分区'))
        if zone_2023:
            rec.cas_zone_2023 = zone_2023
        top = safe_str(entry.get('Top', ''))
        if top.upper() == 'Y':
            rec.cas_top = True
        oa = safe_str(entry.get('Open Access', ''))
        if oa.upper() == 'Y':
            rec.cas_open_access = True
        tracker.record(name_cn=name_cn, source=source)

    elif source == 'ABDC':
        name_en = safe_str(entry.get('Journal Title', '')) or safe_str(entry.get('Journal Name', ''))
        issn = safe_str(entry.get('ISSN', ''))
        issn_online = safe_str(entry.get('ISSNOnline', '')) or safe_str(entry.get('ISSN Online', ''))
        rec = get_or_create(name_en=name_en, issn=issn or issn_online)
        rec.name_en = name_en or rec.name_en
        if issn and is_valid_issn(issn):
            if not rec.issn:
                rec.issn = issn
            elif clean_issn(issn) != clean_issn(rec.issn or '') and not rec.eissn:
                rec.eissn = issn
        if issn_online and is_valid_issn(issn_online):
            if not rec.eissn:
                rec.eissn = issn_online
        for key in entry:
            kl = key.lower()
            if 'rating' in kl or 'abdc list' in kl or 'ranking' in kl:
                rating = safe_str(entry[key])
                if rating and not rec.abdc_rating:
                    rec.abdc_rating = rating
        publisher = safe_str(entry.get('Publisher', ''))
        if publisher:
            rec.publisher = publisher
        tracker.record(name_en=name_en, issn=issn or issn_online, source=source)

    elif source == 'JCR':
        name_en = safe_str(entry.get('Journal Name', ''))
        issn = safe_str(entry.get('ISSN', ''))
        eissn = safe_str(entry.get('eISSN', ''))
        rec = get_or_create(name_en=name_en, issn=issn or eissn)
        rec.name_en = name_en or rec.name_en
        if issn:
            rec.issn = issn
        if eissn:
            rec.eissn = eissn
        jif = safe_float(entry.get('JIF 2024'))
        if jif:
            rec.jif = jif
        quartile = safe_str(entry.get('JIF Quartile', ''))
        if quartile:
            rec.jcr_quartile = quartile
        jcr_rank = safe_str(entry.get('JIF Rank', ''))
        if jcr_rank:
            rec.jcr_rank = jcr_rank
        publisher = safe_str(entry.get('Publisher', ''))
        if publisher:
            rec.jcr_publisher = publisher
        tracker.record(name_en=name_en, issn=issn or eissn, source=source)

    elif source == 'Mega-Journal':
        name_en = safe_str(entry.get('刊名', ''))
        rec = get_or_create(name_en=name_en)
        rec.name_en = name_en or rec.name_en
        rec.mega_journal = True
        rec.mega_category = safe_str(entry.get('大类', ''))
        rec.mega_zone = safe_int(entry.get('分区'))
        tracker.record(name_en=name_en, source=source)

# ─── Load abbreviations ─────────────────────────────────────────────────

def load_abbreviations():
    abbr_file = os.path.join(data_dir, '期刊简称', '2025年4月最新期刊缩写名称.txt')
    mapping = {}
    if os.path.exists(abbr_file):
        with open(abbr_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or '\t' not in line:
                    continue
                full, abbr = line.split('\t', 1)
                key = normalize_name(full.strip())
                if key:
                    mapping[key] = abbr.strip()
    print(f"已加载 {len(mapping)} 条期刊缩写")
    return mapping

abbrev_map = load_abbreviations()

# ─── Build output ──────────────────────────────────────────────────────

seen = set()
unique_records = []
for rec in list(index_issn.values()) + list(index_en.values()) + list(index_cn.values()):
    if id(rec) not in seen:
        seen.add(id(rec))
        unique_records.append(rec)

for rec in unique_records:
    if not rec._key_en and rec.name_en:
        rec._key_en = normalize_name(rec.name_en)
    if not rec._key_cn and rec.name_cn:
        rec._key_cn = normalize_name(rec.name_cn)

name_groups = defaultdict(list)
for rec in unique_records:
    nk = rec._key_en or rec._key_cn
    if nk:
        name_groups[nk].append(rec)

merged_ids = set()
final_records = []
for rec in unique_records:
    nk = rec._key_en or rec._key_cn
    if nk:
        group = name_groups.get(nk, [rec])
        primary = group[0]
        if id(primary) not in merged_ids:
            for other in group[1:]:
                _merge_records(primary, other)
                merged_ids.add(id(other))
            merged_ids.add(id(primary))
            final_records.append(primary)
    elif id(rec) not in merged_ids:
        merged_ids.add(id(rec))
        final_records.append(rec)
unique_records = final_records

# ── Build CSV output (unified flat format) ──────────────────────────────

csv_records = []
name_to_record = {}
for rec in unique_records:
    # Look up abbreviation
    for name_key in (rec._key_en, rec._key_cn):
        if name_key and name_key in abbrev_map:
            rec.abbreviated_name = abbrev_map[name_key]
            break

    d = rec.to_dict()
    csv_records.append(d)
    if rec._key_en:
        name_to_record[rec._key_en] = d
    if rec._key_cn:
        name_to_record[rec._key_cn] = d

csv_path = os.path.join(data_dir, 'journals.csv')
if csv_records:
    fields = list(csv_records[0].keys())
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for d in csv_records:
            row = {}
            for k in fields:
                v = d.get(k)
                if isinstance(v, bool):
                    v = 'Y' if v else ''
                elif v is None:
                    v = ''
                row[k] = v
            w.writerow(row)

# ── Build JSON output (ISSN-keyed dict, compatible with database.py) ────

json_dict = {}
for rec in unique_records:
    issn_key = rec.issn if rec.issn else (rec._key_en or rec._key_cn or f"unk_{id(rec)}")
    entry = {
        "name": rec.name_en or rec.name_cn or "",
        "issn": rec.issn or "",
    }
    if rec.abbreviated_name:
        entry["abbreviated_name"] = rec.abbreviated_name
    aliases = []
    if rec.name_cn and rec.name_en and rec.name_cn.lower() != rec.name_en.lower():
        aliases.append(rec.name_cn)
    if aliases:
        entry["aliases"] = aliases
    if rec.eissn:
        entry["eissn"] = rec.eissn
    if rec.publisher:
        entry["publisher"] = rec.publisher
    if rec.jif:
        entry["jif"] = rec.jif
    if rec.jcr_quartile:
        entry["jcr_quartile"] = rec.jcr_quartile
    if rec.jcr_rank:
        entry["jcr_rank"] = rec.jcr_rank
    if rec.cas_zone_2025:
        entry["cas_zone"] = rec.cas_zone_2025
    if rec.cas_zone_2023:
        entry["cas_zone_2023"] = rec.cas_zone_2023
    if rec.cas_top:
        entry["cas_top"] = True
    if rec.cas_open_access:
        entry["cas_open_access"] = True
    if rec.cas_discipline:
        entry["cas_discipline"] = rec.cas_discipline
    if rec.abdc_rating:
        entry["abdc_rating"] = rec.abdc_rating
    if rec.cssci_source:
        entry["cssci"] = "来源期刊"
    elif rec.cssci_extended:
        entry["cssci"] = "扩展版"
    if rec.bdhx_core:
        entry["pkua"] = "北大核心"
        if rec.bdhx_rank:
            entry["bdhx_rank"] = rec.bdhx_rank
        if rec.bdhx_category:
            entry["bdhx_category"] = rec.bdhx_category
    if rec.mega_journal:
        entry["mega_journal"] = True
        if rec.mega_zone:
            entry["mega_zone"] = rec.mega_zone

    json_dict[issn_key] = entry

json_path = os.path.join(data_dir, 'journals.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(json_dict, f, ensure_ascii=False, indent=None, separators=(',', ':'))

# Copy to MCP server data dir
mcp_data_dir = os.path.join(data_dir, '..', 'src', 'publication_rank', 'data')
mcp_data_dir = os.path.normpath(mcp_data_dir)
os.makedirs(mcp_data_dir, exist_ok=True)
mcp_json_path = os.path.join(mcp_data_dir, 'journals.json')
with open(mcp_json_path, 'w', encoding='utf-8') as f:
    json.dump(json_dict, f, ensure_ascii=False, indent=None, separators=(',', ':'))

# ── Filtered JSON: CAS 1-2 and JCR Q1-Q2, excluding specific disciplines ──

def discipline_excluded(discipline):
    exclude_keywords = ['医学', '材料', '物理', '化学', '生物']
    if not discipline:
        return False
    d = discipline.lower().replace(' ', '')
    for kw in exclude_keywords:
        if kw in d:
            return True
    return False

filtered_dict = {}
for issn_key, entry in json_dict.items():
    cas_zone = entry.get('cas_zone', 0) or 0
    if cas_zone not in (1, 2):
        continue
    jcr_q = entry.get('jcr_quartile', '')
    if jcr_q not in ('Q1', 'Q2'):
        continue
    if discipline_excluded(entry.get('cas_discipline', '')):
        continue
    filtered_dict[issn_key] = entry

filtered_path = os.path.join(data_dir, 'journals_high_rank.json')
with open(filtered_path, 'w', encoding='utf-8') as f:
    json.dump(filtered_dict, f, ensure_ascii=False, indent=None, separators=(',', ':'))

report_path = os.path.join(data_dir, 'merge_conflicts.md')
tracker.write_report(report_path, name_to_record)

print(f"journals.json + journals.csv 已生成，共 {len(csv_records)} 条记录")
print(f"journals_high_rank.json 已生成（CAS 1-2 + JCR Q1-Q2，排除指定学科），共 {len(filtered_dict)} 条记录")
