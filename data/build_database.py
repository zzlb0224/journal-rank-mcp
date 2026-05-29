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
#  ▪ 约定字段（标准字段名，由 FIELD_MAP 映射得到）
#     ────────────────────────────────────────────────────────────────
#     字段名              类型      说明
#     ────────────────────────────────────────────────────────────────
#     _name_cn             str       中文刊名
#     _name_en             str       英文刊名
#     issn / eissn        str       ISSN / eISSN（自动校验去重）
#     publisher           str       出版商
#     bdhx_core           bool      北大核心收录
#     bdhx_rank           int       北大核心排序
#     bdhx_discipline     str       北大核心学科门类
#     bdhx_category       str       北大核心学科
#     cas_zone            int       中科院大类分区（→ cas_zone_2025）
#     cas_zone_2023       int       2023年中科院分区
#     cas_top             bool      Top 期刊
#     cas_open_access     bool      Open Access
#     cas_discipline      str       中科院学科分类
#     abdc_rating         str       ABDC 评级
#     cssci_type          str       CSSCI 类型（"来源期刊" / "扩展版"）
#     cssci_discipline    str       CSSCI 学科
#     jif                 float     影响因子
#     jcr_quartile        str       JCR 分区（Q1/Q2/Q3/Q4）
#     jcr_rank            str       JCR 排名（如 "12/420"）
#     jcr_publisher       str       JCR 出版商
#     mega_journal        bool      巨型期刊
#     mega_category       str       巨型期刊大类
#     mega_zone           int       巨型期刊分区
#     abbreviated_name    str       期刊缩写名
#     ────────────────────────────────────────────────────────────────
#     新增字段时在此表追加一行，并在 FIELD_MAP 中添加映射即可。
#
#  ▪ JSON 输出特殊映射
#     JournalRecord 属性           → JSON 字段名
#     ────────────────────────────────────────────────────────────────
#     cas_zone_2025                → cas_zone
#     bdhx_core = True             → pkua = "北大核心"
#     cssci_source / cssci_extended → cssci = "来源期刊" / "扩展版"
#     _name_en / _name_cn            → name（合二为一）
#     ────────────────────────────────────────────────────────────────
#     其余非 _ 开头的属性自动同名输出到 JSON。
#
#  ══════════════════════════════════════════════════════════════════════════
#  🔧 扩展指南 ①：新增字段
#  ──────────────────────────────────────────────────────────────────────────
#  1. 原始 JSON 文件放入 data/ 下（平铺格式）
#  2. 在 FIELD_MAP 中添加字段映射：{'原始字段名': '标准字段名'}
#  3. 若标准字段涉及 JSON 特殊映射，在上述映射表中追加
#
#  🔧 扩展指南 ②：调整 journals_high_rank.json 筛选规则
#  ──────────────────────────────────────────────────────────────────────────
#  编辑 data/filter_high_rank.py 顶部的配置块即可，无需修改本文件。
#
# ══════════════════════════════════════════════════════════════════════════

import sys, json, os, re, csv
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

# 当前文件所在目录，所有路径都基于它
data_dir = os.path.dirname(os.path.abspath(__file__))


# ══════════════════════════════════════════════════════════════════════════
#  Helpers — 安全类型转换、名称规范化、ISSN 校验
# ══════════════════════════════════════════════════════════════════════════


def safe_str(v):
    """安全提取字符串：None → ''，'nan' → ''"""
    if v is None:
        return ""
    s = str(v).strip()
    return s if s.lower() != "nan" else ""


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
    return re.sub(r"\s+", " ", str(n).strip().lower()) if n else ""


def clean_issn(s):
    """
    ISSN 清洗：连字符（含 en-dash/em-dash）→ 移除，
    空格 → 移除，转大写。返回纯 8 位字符串（含末位 X）。
    """
    return (
        s.replace("\u2013", "-")
        .replace("\u2014", "-")
        .replace("-", "")
        .replace(" ", "")
        .replace("\t", "")
        .strip()
        .upper()
    )


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
    if c[-1] not in "0123456789Xx":
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

    def record(self, _name_en="", _name_cn="", issn="", source=""):
        """记录一条期刊的名称 → ISSN → 来源映射"""
        nen = normalize_name(_name_en)
        ncn = normalize_name(_name_cn)
        cissn = clean_issn(issn) if issn and is_valid_issn(issn) else ""
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
                rec_issn = clean_issn(rec.get("issn", "") or "")
                rec_eissn = clean_issn(rec.get("eissn", "") or "")
                known = {s for s in (rec_issn, rec_eissn) if s}
                remaining = set(issns_sorted) - known
                if not remaining:
                    continue
            issn_detail = []
            for isxn in issns_sorted:
                srcs = issn_sources[isxn]
                issn_detail.append(f"{isxn} ({', '.join(sorted(srcs))})")
            self.conflicts.append(
                {
                    "type": "同名多ISSN",
                    "name": nm,
                    "issns": issn_detail,
                    "detail": "同一期刊名称在不同数据源中出现多个不同ISSN，可能为不同期刊",
                }
            )

    def write_report(self, path, record_lookup):
        """生成 merge_conflicts.md 报告"""
        self.detect(record_lookup)
        lines = []
        lines.append("# 数据合并冲突报告\n")
        lines.append(
            f"> 生成时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        lines.append(f"> 总冲突数: {len(self.conflicts)}\n")
        lines.append("---\n")

        if not self.conflicts:
            lines.append("未发现冲突。\n")
        else:
            for i, c in enumerate(self.conflicts, 1):
                lines.append(f"## {i}. {c['type']}\n")
                lines.append(f"- **名称**: `{c['name']}`\n")
                lines.append(f"- **ISSN来源**:\n")
                for item in c["issns"]:
                    lines.append(f"  - `{item}`\n")
                lines.append(f"- **说明**: {c['detail']}\n")
                lines.append("\n")

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"冲突报告已生成: {path}")


tracker = ConflictTracker()


# ══════════════════════════════════════════════════════════════════════════
#  load_journals() — 扫描 data/ 下所有 JSON（排除 journals.json）并加载
#
#  原始数据文件已自带标准字段名（由各文件的 field_map 定义转换），
#  本函数仅读取并附加 _source 标签和归一化配置。
#
#  添加新数据源 → 在原始 JSON 文件中定义 field_map 即可，
#  norm_defaults 和 norm_config 为可选配置。
# ══════════════════════════════════════════════════════════════════════════

SOURCE_CONFIG = {}


def load_journals():
    json_files = []
    for root, dirs, files in os.walk(data_dir):
        for f in files:
            if f.endswith(".json") and f != "journals.json":
                json_files.append(os.path.join(root, f))

    all_entries = []
    for jf in sorted(json_files):
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)
        source = data.get("source", "")
        for entry in data.get("journals", []):
            entry["_source"] = source
            all_entries.append(entry)
    return all_entries


all_entries = load_journals()


def _normalize_entry(entry, source):
    """数据字段已是标准名，无需额外归一化"""
    return dict(entry)


def _apply_entry(rec, norm):
    """将标准化字段赋值到 JournalRecord"""
    for field, val in norm.items():
        if field.startswith("_"):
            continue

        # ISSN 校验存储
        if field in ("issn", "eissn"):
            vs = safe_str(val)
            if vs and is_valid_issn(vs):
                cvs = clean_issn(vs)
                cur = clean_issn(getattr(rec, "issn", "") or "")
                cur_e = clean_issn(getattr(rec, "eissn", "") or "")
                if field == "issn" and not getattr(rec, "issn", None):
                    rec.issn = vs
                elif (
                    field == "eissn" and not getattr(rec, "eissn", None) and cvs != cur
                ):
                    rec.eissn = vs
                elif cvs and cvs not in (cur, cur_e):
                    if not getattr(rec, "issn", None):
                        rec.issn = vs
                    elif not getattr(rec, "eissn", None):
                        rec.eissn = vs
            continue

        # 已有值跳过
        existing = getattr(rec, field, None)
        if existing and existing is not False:
            continue

        # 简单赋值
        setattr(rec, field, val)


# ══════════════════════════════════════════════════════════════════════════
#  JournalRecord — 期刊数据容器
#
#  属性由 _apply_entry 按标准化字段动态设置。
#  以 _ 开头的属性为内部使用（不输出到最终 JSON）。
#  key 属性用于去重比对：ISSN > 英文名 > 中文名。
# ══════════════════════════════════════════════════════════════════════════


class JournalRecord:
    def __init__(self):
        self._key_issn = None
        self._key_en = None
        self._key_cn = None

    @property
    def key(self):
        if getattr(self, "issn", None):
            return self.issn
        if getattr(self, "_name_en", None):
            return normalize_name(self._name_en)
        if getattr(self, "_name_cn", None):
            return normalize_name(self._name_cn)
        return f"unknown_{id(self)}"

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}


# ══════════════════════════════════════════════════════════════════════════
#  三路索引 & get_or_create — 按 ISSN / 英文名 / 中文名去重
#
#  index_issn  : 清洗后的 8 位 ISSN → JournalRecord
#  index_en    : 规范化英文名 → JournalRecord
#  index_cn    : 规范化中文名 → JournalRecord
#
#  get_or_create() 逻辑：
#    1. 用传入的 issn/_name_en/_name_cn 分别查三路索引
#    2. 如果找到多个候选且指向不同对象 → 合并（_merge_records）
#    3. 如果没找到 → 新建 JournalRecord
#    4. 把新的键注册到索引中
# ══════════════════════════════════════════════════════════════════════════

index_issn = {}
index_en = {}
index_cn = {}


def get_or_create(issn="", _name_en="", _name_cn=""):
    cissn = clean_issn(issn) if issn and is_valid_issn(issn) else ""
    nen = normalize_name(_name_en)
    ncn = normalize_name(_name_cn)

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
    """将 source 中的非空字段合并到 target"""
    for attr, sv in source.__dict__.items():
        if attr.startswith("_"):
            continue
        tv = getattr(target, attr, None)
        if sv and not tv:
            setattr(target, attr, sv)
        elif sv and isinstance(sv, str) and isinstance(tv, str) and len(sv) > len(tv):
            setattr(target, attr, sv)

    # ISSN 合并
    t_issn = clean_issn(getattr(target, "issn", "") or "")
    t_eissn = clean_issn(getattr(target, "eissn", "") or "")
    s_issn = clean_issn(getattr(source, "issn", "") or "")
    s_eissn = clean_issn(getattr(source, "eissn", "") or "")
    for src in {s for s in (s_issn, s_eissn) if s} - {t_issn, t_eissn}:
        if not getattr(target, "issn", None):
            target.issn = src
        elif not getattr(target, "eissn", None):
            target.eissn = src


# ══════════════════════════════════════════════════════════════════════════
#  统一处理每条记录
#
#  load_journals() 已将字段名映射为标准字段（_name_cn、issn、cas_zone 等），
#  此处统一 apply 到 JournalRecord，追踪冲突。
#
#  添加新数据源 → 参考扩展指南第 3 步：
#    在文件头的 FIELD_MAP 中添加映射即可，无需修改此处。
# ══════════════════════════════════════════════════════════════════════════

for entry in all_entries:
    source = entry.get("_source", "")
    norm = _normalize_entry(entry, source)

    _name_cn = safe_str(norm.get("_name_cn", ""))
    _name_en = safe_str(norm.get("_name_en", ""))
    issn = safe_str(norm.get("issn", ""))

    rec = get_or_create(_name_cn=_name_cn, _name_en=_name_en, issn=issn)
    if _name_cn:
        rec._name_cn = _name_cn
    if _name_en:
        rec._name_en = _name_en

    _apply_entry(rec, norm)
    tracker.record(_name_en=_name_en, _name_cn=_name_cn, issn=issn, source=source)


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
for rec in (
    list(index_issn.values()) + list(index_en.values()) + list(index_cn.values())
):
    if id(rec) not in seen:
        seen.add(id(rec))
        unique_records.append(rec)

# 确保每个 record 都有内部 key
for rec in unique_records:
    if not rec._key_en and getattr(rec, "_name_en", None):
        rec._key_en = normalize_name(rec._name_en)
    if not rec._key_cn and getattr(rec, "_name_cn", None):
        rec._key_cn = normalize_name(rec._name_cn)

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

    d = rec.to_dict()
    csv_records.append(d)
    if rec._key_en:
        name_to_record[rec._key_en] = d
    if rec._key_cn:
        name_to_record[rec._key_cn] = d

csv_path = os.path.join(data_dir, "journals.csv")
if csv_records:
    fields = list(csv_records[0].keys())
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for d in csv_records:
            row = {}
            for k in fields:
                v = d.get(k)
                if isinstance(v, bool):
                    v = "Y" if v else ""
                elif v is None:
                    v = ""
                row[k] = v
            w.writerow(row)


#  ══════════════════════════════════════════════════════════════════════════
#  输出 ②：journals.json — ISSN 为 key 的完整数据库
#
#  格式：{"ISSN": {name, issn, jif, jcr_quartile, cas_zone, …}}
#  非 _ 开头的属性自动输出。
# ══════════════════════════════════════════════════════════════════════════


def _build_json_entry(rec):
    entry = {
        "name": (rec._name_en if getattr(rec, "_name_en", None) else "")
        or (rec._name_cn if getattr(rec, "_name_cn", None) else "")
        or "",
        "issn": getattr(rec, "issn", "") or "",
    }

    # aliases
    nc = getattr(rec, "_name_cn", None)
    ne = getattr(rec, "_name_en", None)
    if nc and ne and nc.lower() != ne.lower():
        entry["aliases"] = [nc]

    # 动态输出：其余非 _ 开头属性
    for attr, val in rec.__dict__.items():
        if attr.startswith("_"):
            continue
        if val:
            entry[attr] = val

    return entry


json_dict = {}
for rec in unique_records:
    issn_key = getattr(rec, "issn", None) or (
        rec._key_en or rec._key_cn or f"unk_{id(rec)}"
    )
    json_dict[issn_key] = _build_json_entry(rec)

json_path = os.path.join(data_dir, "journals.json")
with open(json_path, "w", encoding="utf-8") as f:
    json.dump(json_dict, f, ensure_ascii=False, indent=None, separators=(",", ":"))

# 同步到 MCP server 的数据目录
mcp_data_dir = os.path.join(data_dir, "..", "src", "journal_rank_mcp", "data")
mcp_data_dir = os.path.normpath(mcp_data_dir)
os.makedirs(mcp_data_dir, exist_ok=True)
mcp_json_path = os.path.join(mcp_data_dir, "journals.json")
with open(mcp_json_path, "w", encoding="utf-8") as f:
    json.dump(json_dict, f, ensure_ascii=False, indent=None, separators=(",", ":"))

# 同步到 skill 目录
skill_dir = os.path.join(data_dir, "..", ".opencode", "skills", "journal-rank")
skill_dir = os.path.normpath(skill_dir)
os.makedirs(skill_dir, exist_ok=True)
skill_json_path = os.path.join(skill_dir, "journals.json")
with open(skill_json_path, "w", encoding="utf-8") as f:
    json.dump(json_dict, f, ensure_ascii=False, indent=None, separators=(",", ":"))

report_path = os.path.join(data_dir, "merge_conflicts.md")
tracker.write_report(report_path, name_to_record)

print(f"journals.json + journals.csv 已生成，共 {len(csv_records)} 条记录")
