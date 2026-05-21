# ══════════════════════════════════════════════════════════════════════════
#  MIT License
#  Free to use, modify, and distribute. Retain this notice.
#
#  📦 build_database.py — 期刊数据流水线
#  ══════════════════════════════════════════════════════════════════════════
#
#  ▪ 职责
#     读取 data/ 下各子目录的原始 JSON 数据 → 按 ISSN/名称去重合并 →
#     输出 journals.json（ISSN 为 key 的完整库）和 journals.csv
#
#  ▪ 输入文件格式要求
#     每个 JSON 文件必须包含 "source"（数据源标识）字段。
#     数据可以是 {"journals": […] } 或 {"sheets": {"sheet名": {"journals": […]}}}
#     两种结构。单个 journal 条目是 flat dict，字段名不限，在下方 elif 分支中解析。
#
#  ▪ 输出文件
#     journals.json    — 以 ISSN 为 key 的完整数据库，兼容 src/ 下的 MCP server
#     journals.csv     — 扁平表格，方便 Excel 查看
#
#  ══════════════════════════════════════════════════════════════════════════
#  🔧 扩展指南 ①：新增字段
#  ──────────────────────────────────────────────────────────────────────────
#  如果你想添加一个新的字段（例如 SABC 评级、SJR、H-index 等）：
#
#  第 1 步 — 放数据
#      把包含新字段的原始 JSON 文件放入 data/ 下对应的子目录。
#
#  第 2 步 — 确保能被加载
#      load_journals() 会自动遍历 data/ 下所有 .json（除了 journals.json）。
#      如果你的文件使用了 {"journals": […] } 或 {"sheets": {"…": {"journals": […]}}}
#      之外的格式，需要修改 load_journals() 来兼容它。
#
#  第 3 步 — 添加解析分支
#      在下方 "Process each entry" 区域添加一个 elif 分支。
#      例如，如果 source == 'SABC'，在其中读取字段并赋值到 JournalRecord。
#
#  第 4 步 — 在 JournalRecord 中声明字段
#      在 class JournalRecord 的 __slots__ 元组中添加字段名。
#      然后在 __init__ 中设默认值：
#        - 布尔值 → False（例如 'sabc_rated': False）
#        - 其他 → ''（空字符串，Python 会在 JSON 输出时自动转为 int/float）
#
#  第 5 步 — 写出到 JSON
#      在 "Build JSON output" 区域添加对应的 if 分支，例如：
#        if rec.sabc_rating:
#            entry["sabc_rating"] = rec.sabc_rating
#
#  ══════════════════════════════════════════════════════════════════════════
#  🔧 扩展指南 ②：调整 journals_high_rank.json 的筛选规则
#  ──────────────────────────────────────────────────────────────────────────
#  journals_high_rank.json 由独立的 filter_high_rank.py 生成。
#
#  要改变筛选条件（比如改为 CAS 1 区 + JCR Q1，或排除更多学科），
#  只需编辑 data/filter_high_rank.py 顶部的配置块：
#
#      CAS_ZONES           = {1}          # ← 改为只保留 1 区
#      JCR_QUARTILES       = {'Q1'}       # ← 改为只保留 Q1
#      EXCLUDE_DISCIPLINES = ['医学','材料'] # ← 改为排除不同学科
#
#  然后运行 python data/filter_high_rank.py 即可。无需修改本文件。
#
# ══════════════════════════════════════════════════════════════════════════

import sys, json, os, re, csv
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

# 当前文件所在目录，所有路径都基于它
data_dir = os.path.dirname(os.path.abspath(__file__))


# ══════════════════════════════════════════════════════════════════════════
#  Helpers — 安全类型转换、名称规范化、ISSN 校验
# ══════════════════════════════════════════════════════════════════════════

def safe_str(v):
    """安全提取字符串：None → ''，'nan' → ''"""
    if v is None:
        return ''
    s = str(v).strip()
    return s if s.lower() != 'nan' else ''

def safe_int(v):
    """安全转 int：接受数字字符串或 float（如 1.0 → 1）"""
    if v is None:
        return None
    try:
        return int(float(str(v).strip()))
    except (ValueError, TypeError):
        return None

def safe_float(v):
    """安全转 float"""
    if v is None:
        return None
    try:
        return float(str(v).strip())
    except (ValueError, TypeError):
        return None

def normalize_name(n):
    """期刊名称规范化：去首尾空格、多空格合并、转小写"""
    return re.sub(r'\s+', ' ', str(n).strip().lower()) if n else ''

def clean_issn(s):
    """
    ISSN 清洗：连字符（含 en-dash/em-dash）→ 移除，
    空格 → 移除，转大写。返回纯 8 位字符串（含末位 X）。
    """
    return s.replace('\u2013', '-').replace('\u2014', '-').replace('-', '').replace(' ', '').replace('\t', '').strip().upper()

def is_valid_issn(s):
    """
    ISSN 格式校验：8 位，前 7 位数字，末位数字或 X。
    用于排除 JIF 等数值被误当作 ISSN 读入。
    """
    c = clean_issn(s)
    if len(c) != 8:
        return False
    if not c[:-1].isdigit():
        return False
    if c[-1] not in '0123456789Xx':
        return False
    return True


# ══════════════════════════════════════════════════════════════════════════
#  ConflictTracker — 检测同名期刊在不同数据源中 ISSN 不一致的冲突
#  原理：对每条记录记录（名称 → ISSN → 数据源），
#  若同一名称出现多个不同 ISSN，说明不同数据源对该期刊的标识不一致，
#  可能指代不同期刊，在 merge_conflicts.md 中输出供人工排查。
# ══════════════════════════════════════════════════════════════════════════

class ConflictTracker:
    def __init__(self):
        self.name_data = defaultdict(dict)
        self.conflicts = []

    def record(self, name_en='', name_cn='', issn='', source=''):
        """记录一条期刊的名称 → ISSN → 来源映射"""
        nen = normalize_name(name_en)
        ncn = normalize_name(name_cn)
        cissn = clean_issn(issn) if issn and is_valid_issn(issn) else ''
        for nm in (nen, ncn):
            if nm and cissn:
                if cissn not in self.name_data[nm]:
                    self.name_data[nm][cissn] = set()
                self.name_data[nm][cissn].add(source)

    def detect(self, record_lookup):
        """检测所有冲突：同一名称对应 >=2 个不同 ISSN 即为冲突"""
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
        """生成 merge_conflicts.md 报告"""
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


# ══════════════════════════════════════════════════════════════════════════
#  load_journals() — 扫描 data/ 下所有 JSON（排除 journals.json）并加载
#
#  支持两种顶层结构：
#    A. {"source":"xx", "journals": [{...}, ...]}
#       直接遍历 journals 数组，每条加 _source 标签
#    B. {"source":"xx", "sheets": {"sheet名": {"journals": [...]}, ...}}
#       遍历 sheets 下每个子表，每条加 _source 和 _sheet 标签
#
#  如果你用的是其他结构，需要在此函数中扩展兼容。
# ══════════════════════════════════════════════════════════════════════════

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
        # 格式 A: {"journals": [...]}
        if 'journals' in data and isinstance(data['journals'], list):
            for entry in data['journals']:
                entry['_source'] = source
                all_entries.append(entry)
        # 格式 B: {"sheets": {"sheet名": {"journals": [...]}}}
        elif 'sheets' in data and isinstance(data['sheets'], dict):
            for sheet_name, sheet_data in data['sheets'].items():
                if 'journals' in sheet_data:
                    for entry in sheet_data['journals']:
                        entry['_source'] = source
                        entry['_sheet'] = sheet_name
                        all_entries.append(entry)
    return all_entries

all_entries = load_journals()


# ══════════════════════════════════════════════════════════════════════════
#  JournalRecord — 单条期刊的统一数据模型
#
#  使用 __slots__ 限制属性列表，节省内存。
#  所有公开字段（不以 _ 开头）会在 to_dict() 中输出。
#  以 _ 开头的为内部索引键，不输出。
#
#  添加新字段 → 参考扩展指南第 4 步：
#    1. 在 __slots__ 元组中加入字段名
#    2. 在 __init__ 中设置默认值
# ══════════════════════════════════════════════════════════════════════════

class JournalRecord:
    __slots__ = (
        # —— 基本标识 ——
        'name_cn', 'name_en',
        'issn', 'eissn', 'publisher',
        # —— 北大核心 ——
        'bdhx_core', 'bdhx_rank', 'bdhx_discipline', 'bdhx_category',
        # —— 中科院分区 ——
        'cas_zone_2025', 'cas_zone_2023', 'cas_top', 'cas_open_access', 'cas_discipline',
        # —— ABDC 评级 ——
        'abdc_rating', 'abdc_year',
        # —— CSSCI ——
        'cssci_source', 'cssci_extended', 'cssci_discipline',
        # —— JCR ——
        'jif', 'jcr_quartile', 'jcr_rank', 'jcr_publisher',
        # —— Mega-Journal ——
        'mega_journal', 'mega_category', 'mega_zone',
        # —— 期刊缩写 ——
        'abbreviated_name',
        # —— 内部索引（不输出到 JSON） ——
        '_key_issn', '_key_en', '_key_cn',
    )

    def __init__(self):
        for s in self.__slots__:
            # _ 开头为内部字段，默认 None（不输出）
            setattr(self, s, None if s.startswith('_') else (
                # 布尔字段默认 False
                False if s in ('bdhx_core', 'cssci_source', 'cssci_extended',
                               'cas_top', 'cas_open_access', 'mega_journal')
                # 其他字段默认空字符串
                else ''
            ))

    def to_dict(self):
        """只输出非内部字段的 dict"""
        return {s: getattr(self, s) for s in self.__slots__ if not s.startswith('_')}

    @property
    def key(self):
        """用于去重比对的唯一标识：ISSN > 英文名 > 中文名"""
        if self.issn:
            return self.issn
        if self.name_en:
            return normalize_name(self.name_en)
        if self.name_cn:
            return normalize_name(self.name_cn)
        return f"unknown_{id(self)}"


# ══════════════════════════════════════════════════════════════════════════
#  三路索引 & get_or_create — 按 ISSN / 英文名 / 中文名去重
#
#  index_issn  : 清洗后的 8 位 ISSN → JournalRecord
#  index_en    : 规范化英文名 → JournalRecord
#  index_cn    : 规范化中文名 → JournalRecord
#
#  get_or_create() 逻辑：
#    1. 用传入的 issn/name_en/name_cn 分别查三路索引
#    2. 如果找到多个候选且指向不同对象 → 合并（_merge_records）
#    3. 如果没找到 → 新建 JournalRecord
#    4. 把新的键注册到索引中
# ══════════════════════════════════════════════════════════════════════════

index_issn = {}
index_en = {}
index_cn = {}

def get_or_create(issn='', name_en='', name_cn=''):
    cissn = clean_issn(issn) if issn and is_valid_issn(issn) else ''
    nen = normalize_name(name_en)
    ncn = normalize_name(name_cn)

    # 收集所有匹配到的候选对象
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
        # 多个候选 → 合并到第一个，其余的数据合并进来
        rec = candidates.pop()
        for other in candidates:
            _merge_records(rec, other)
            # 更新索引指针
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
        # 全新记录
        rec = JournalRecord()

    # 注册新键
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


# ══════════════════════════════════════════════════════════════════════════
#  _merge_records — 将 source 中的非空字段合并到 target
#
#  合并规则：
#    - 字段在 target 中为空 → 取 source 的值
#    - 双方都非空的字符串 → 取较长者
#    - ISSN/eISSN → 尽量保留两个不同的 ISSN
# ══════════════════════════════════════════════════════════════════════════

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

    # 合并 issn/eissn：若不同则尽量填充两个字段
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


# ══════════════════════════════════════════════════════════════════════════
#  处理每条原始记录
#  ── 按 source 分发到对应的解析分支 ──
#
#  每个 elif 分支：
#    1. 从 entry 中读取原始字段（字段名参考原始 JSON 文件）
#    2. 调用 get_or_create() 获取或创建 JournalRecord
#    3. 将值赋到 JournalRecord 的对应属性
#    4. 调用 tracker.record() 记录名称→ISSN 映射
#
#  添加新数据源 → 参考扩展指南第 3 步：
#    在此处追加一个 elif source == '你的数据源名': 分支。
# ══════════════════════════════════════════════════════════════════════════

for entry in all_entries:
    source = entry.get('_source', '')
    sheet = entry.get('_sheet', '')

    # ── 北大核心：只有中文刊名和学科分类 ──────────────────────────
    if source == '北大核心':
        name_cn = safe_str(entry.get('中文刊名', ''))
        rec = get_or_create(name_cn=name_cn)
        rec.name_cn = name_cn or rec.name_cn
        rec.bdhx_core = True
        rec.bdhx_rank = safe_int(entry.get('排序'))
        rec.bdhx_discipline = safe_str(entry.get('学科门类', ''))
        rec.bdhx_category = safe_str(entry.get('学科', ''))
        tracker.record(name_cn=name_cn, source=source)

    # ── CSSCI：来源期刊 / 扩展版 ──────────────────────────────────
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

    # ── 中科院分区表（精简版）：带 ISSN、分区、大类学科、IF ────────
    #     大类字段（如"医学""材料科学"）是最细粒度学科分类
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
        # 学科分类：优先取"大类"字段（如"医学"），无大类则用 sheet 名
        discipline = safe_str(entry.get('大类', '')) or safe_str(sheet)
        if discipline and not rec.cas_discipline:
            rec.cas_discipline = discipline
        jif = safe_float(entry.get('2024IF'))
        if jif and not rec.jif:
            rec.jif = jif
        tracker.record(name_en=name_en, name_cn=name_cn, issn=issn, source=source)

    # ── 中科院分区表完整版：2025/2023 分区对比、Top/Open Access 标识 ─
    #     注意：完整版不含学科分类，学科信息从精简版合并获得
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

    # ── ABDC：澳大利亚商学院评级，含 ISSN、评级、出版商 ────────────
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
        # 自动检测 rating 字段（字段名可能叫 Rating / ABDC List / Ranking）
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

    # ── JCR：影响因子、JCR 分区、排名、出版商 ──────────────────────
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

    # ── Mega-Journal：发文量 >3000 的巨型期刊 ─────────────────────
    elif source == 'Mega-Journal':
        name_en = safe_str(entry.get('刊名', ''))
        rec = get_or_create(name_en=name_en)
        rec.name_en = name_en or rec.name_en
        rec.mega_journal = True
        rec.mega_category = safe_str(entry.get('大类', ''))
        rec.mega_zone = safe_int(entry.get('分区'))
        tracker.record(name_en=name_en, source=source)


# ══════════════════════════════════════════════════════════════════════════
#  加载期刊缩写映射
#  缩写来自 data/期刊简称/ 下的文本文件（tab 分隔：全称 → 缩写）
# ══════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════
#  构建输出去重列表
#
#  经过前面的处理，三路索引中可能多个 key 指向同一个 JournalRecord。
#  第一步：收集所有唯一对象
#  第二步：按规范化名称分组（同名期刊可能因 ISBN 不同被多次创建）
#  第三步：合并同名组内的多个对象
# ══════════════════════════════════════════════════════════════════════════

seen = set()
unique_records = []
for rec in list(index_issn.values()) + list(index_en.values()) + list(index_cn.values()):
    if id(rec) not in seen:
        seen.add(id(rec))
        unique_records.append(rec)

# 确保每个 record 都有内部 key
for rec in unique_records:
    if not rec._key_en and rec.name_en:
        rec._key_en = normalize_name(rec.name_en)
    if not rec._key_cn and rec.name_cn:
        rec._key_cn = normalize_name(rec.name_cn)

# 按名称分组，合并同名记录
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


# ══════════════════════════════════════════════════════════════════════════
#  输出 ①：journals.csv — 扁平表格（UTF-8 BOM 编码，Excel 友好）
#
#  每一行对应一个期刊，字段为 JournalRecord 的所有公开属性。
#  布尔值输出 Y/空，None 输出空字符串。
# ══════════════════════════════════════════════════════════════════════════

csv_records = []
name_to_record = {}
for rec in unique_records:
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


# ══════════════════════════════════════════════════════════════════════════
#  输出 ②：journals.json — ISSN 为 key 的完整数据库
#
#  格式：{"ISSN": {name, issn, jif, jcr_quartile, cas_zone, …}}
#  兼容 src/publication_rank/database.py 的查询逻辑。
#
#  添加新字段到此输出 → 参考扩展指南第 5 步。
#  在此处追加 if rec.xxx: entry["xxx"] = rec.xxx 即可。
# ══════════════════════════════════════════════════════════════════════════

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

    # ── JCR 字段 ──
    if rec.jif:
        entry["jif"] = rec.jif
    if rec.jcr_quartile:
        entry["jcr_quartile"] = rec.jcr_quartile
    if rec.jcr_rank:
        entry["jcr_rank"] = rec.jcr_rank

    # ── 中科院字段 ──
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

    # ── ABDC ──
    if rec.abdc_rating:
        entry["abdc_rating"] = rec.abdc_rating

    # ── CSSCI ──
    if rec.cssci_source:
        entry["cssci"] = "来源期刊"
    elif rec.cssci_extended:
        entry["cssci"] = "扩展版"

    # ── 北大核心 ──
    if rec.bdhx_core:
        entry["pkua"] = "北大核心"
        if rec.bdhx_rank:
            entry["bdhx_rank"] = rec.bdhx_rank
        if rec.bdhx_category:
            entry["bdhx_category"] = rec.bdhx_category

    # ── Mega-Journal ──
    if rec.mega_journal:
        entry["mega_journal"] = True
        if rec.mega_zone:
            entry["mega_zone"] = rec.mega_zone

    json_dict[issn_key] = entry

json_path = os.path.join(data_dir, 'journals.json')
with open(json_path, 'w', encoding='utf-8') as f:
    json.dump(json_dict, f, ensure_ascii=False, indent=None, separators=(',', ':'))

# 同步到 MCP server 的数据目录
mcp_data_dir = os.path.join(data_dir, '..', 'src', 'publication_rank', 'data')
mcp_data_dir = os.path.normpath(mcp_data_dir)
os.makedirs(mcp_data_dir, exist_ok=True)
mcp_json_path = os.path.join(mcp_data_dir, 'journals.json')
with open(mcp_json_path, 'w', encoding='utf-8') as f:
    json.dump(json_dict, f, ensure_ascii=False, indent=None, separators=(',', ':'))

report_path = os.path.join(data_dir, 'merge_conflicts.md')
tracker.write_report(report_path, name_to_record)

print(f"journals.json + journals.csv 已生成，共 {len(csv_records)} 条记录")