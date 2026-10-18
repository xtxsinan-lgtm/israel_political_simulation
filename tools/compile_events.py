#!/usr/bin/env python3
"""
Compile all 6 markdown event files in docs/events/ into structured YAML files in data/events/:
  - docs/events/01_1948_1955.md  -> data/events/fixed_1948_1955.yaml
  - docs/events/02_1955_1967.md  -> data/events/fixed_1955_1967.yaml
  - docs/events/03_1967_1977.md  -> data/events/fixed_1967_1977.yaml
  - docs/events/04_1977_1992.md  -> data/events/fixed_1977_1992.yaml
  - docs/events/05_1992_2006.md  -> data/events/fixed_1992_2006.yaml
  - docs/events/06_random_events.md -> data/events/random_events.yaml

Strictly follows M12_event_engine.md schema, §4.4 expression grammar, §4.8 anti-AI-tone rules,
and DECISIONS.md D-050 (`stance_shift_by_corridor`).
"""

from __future__ import annotations
import calendar
import re
from pathlib import Path
import yaml


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


ROOT = Path(__file__).resolve().parents[1]
EVENTS_MD_DIR = ROOT / "docs" / "events"
OUT_DIR = ROOT / "data" / "events"
PARAMS_PATH = ROOT / "docs" / "registry" / "parameters.yaml"
FLAGS_PATH = ROOT / "docs" / "registry" / "flags.yaml"
MODS_PATH = ROOT / "docs" / "registry" / "modifiers.yaml"

# ---------------------------------------------------------------------------
# Entity & Parameter Mappings (aligned with parameters.yaml & M01-M14 specs)
# ---------------------------------------------------------------------------
BLOC_MAP = {
    "劳工派阿什肯纳兹": "labor_ashkenazi",
    "米兹拉希": "mizrahi",
    "基布兹与莫沙夫": "kibbutz_moshav",
    "宗教犹太复国主义者": "religious_zionist",
    "哈雷迪": "haredi",
    "阿拉伯公民": "arab_citizens",
    "俄裔": "russian",
    "中产自由派": "liberal_middle",
}

GROUP_MAP = {
    "米兹拉希": "mizrahi",
    "俄裔": "russian",
    "埃塞俄比亚裔": "ethiopian",
}

ARAB_GROUP_MAP = {
    "阿拉伯人": "arab",
    "德鲁兹人": "druze",
    "贝都因人": "bedouin",
}

AXIS_MAP = {
    "领土": "territory",
    "安全": "security",
    "经济": "economy",
    "宗教": "religion",
    "外交": "foreign",
}

POWER_MAP = {
    "美国": "usa",
    "苏联": "ussr",
    "法国": "france",
    "英国": "uk",
    "西德": "west_germany",
    "海外犹太社群": "diaspora",
}

ARAB_STATE_MAP = {
    "埃及": "egypt",
    "约旦": "jordan",
    "叙利亚": "syria",
    "黎巴嫩": "lebanon",
    "伊拉克": "iraq",
    "沙特": "saudi",
    "伊朗": "iran",
    "土耳其": "turkey",
    "埃塞俄比亚": "ethiopia",
    "苏丹": "sudan",
    "摩洛哥": "morocco",
}

REGION_MAP = {
    "加利利": "galilee",
    "海法": "haifa",
    "北部沿海": "haifa",
    "特拉维夫": "tel_aviv",
    "中部沿海": "tel_aviv",
    "三角地带": "triangle",
    "耶路撒冷": "jerusalem",
    "内盖夫": "negev",
    "约旦河西岸": "west_bank",
    "西岸": "west_bank",
    "加沙": "gaza",
    "戈兰高地": "golan",
    "戈兰": "golan",
    "西奈": "sinai",
    "南黎巴嫩": "south_lebanon",
}

FACTION_MAP = {
    "法塔赫": "fatah",
    "人阵": "pflp",
    "左翼派别": "pflp",
    "传统地方显要": "jordan_notables",
    "亲约旦显要": "jordan_notables",
    "地方市长": "local_mayors",
    "村庄联盟": "village_leagues",
    "伊斯兰协会": "mujama",
    "哈马斯": "hamas",
    "伊斯兰圣战": "pij",
    "巴勒斯坦权力机构安全部门": "pa_security",
    "长枪党": "phalange",
    "南黎巴嫩军": "sla",
    "真主党": "hezbollah",
    "莱希": "fatah",
}

PARTY_MAP = {
    "马帕伊": "mapai",
    "工党": "labor",
    "劳工党": "labor",
    "劳工联盟": "labor",
    "马帕姆": "mapam",
    "阿赫杜特·哈阿沃达": "ahdut_haavoda",
    "拉菲": "rafi",
    "赫鲁特": "herut",
    "加哈尔": "gahal",
    "利库德": "likud",
    "通用锡安主义者": "general_zionists",
    "自由党": "liberals",
    "独立自由党": "ilp",
    "进步党": "progressives",
    "国家宗教党": "nrp",
    "工人米兹拉希": "nrp",
    "联合宗教阵线": "nrp",
    "宗教民族政党": "nrp",
    "宗教党": "nrp",
    "阿古达": "agudat",
    "以色列正教党": "agudat",
    "以色列正教联盟": "agudat",
    "哈雷迪政党": "agudat",
    "圣经犹太教联盟": "utj",
    "波阿莱阿古达": "poalei_agudat",
    "沙斯": "shas",
    "梅雷茨": "meretz",
    "拉茨": "ratz",
    "达什": "dash",
    "民主变革运动": "dash",
    "复兴党": "tehiya",
    "卡赫": "kach",
    "以色列属于阿里亚": "yisrael_baalia",
    "俄裔政党": "yisrael_baalia",
    "希努伊": "shinui",
    "前进党": "kadima",
    "马基": "maki",
    "拉卡赫": "rakah_hadash",
    "哈达什": "rakah_hadash",
    "阿拉伯政党": "arab_lists",
    "塔米": "tami",
    "特勒姆": "telem",
    "莫拉沙": "morasha",
    "措梅特": "tzomet",
    "莫莱德特": "moledet",
    "国家联盟": "tehiya",
}

PROMISE_MAP = {
    "定居以色列地": "settle_eretz_israel",
    "不让一寸土地": "not_one_inch",
    "经济自由化": "economic_liberalization",
    "社会公正": "social_justice",
    "和平与安全": "peace_and_security",
    "吸收移民": "absorb_immigration",
    "聚集流散者": "absorb_immigration",
    "苏联犹太人": "absorb_immigration",
    "一支军队": "cat_security",
    "赢得战争": "cat_security",
    "打破军火孤立": "cat_security",
    "边境安全": "cat_security",
    "安全边界": "cat_security",
    "安全": "cat_security",
    "安全类": "cat_security",
    "制定宪法": "cat_social",
    "放宽军事管制": "cat_social",
    "恢复信任": "cat_social",
    "国家优先次序": "cat_social",
    "社会类": "cat_social",
    "经济稳定": "cat_economy",
    "经济类": "cat_economy",
    "党内团结": "cat_peace",
    "团结政府": "cat_peace",
    "分阶段协议": "cat_peace",
    "巴勒斯坦自治": "cat_peace",
    "撤出黎巴嫩": "cat_peace",
    "和平类": "cat_peace",
    "宗教类": "cat_religion",
    "移民类": "cat_immigration",
}

CHARACTER_MAP = {
    "贝京": "begin",
    "达扬": "dayan",
    "魏茨曼": "weizman",
    "沙龙": "sharon",
    "沙米尔": "shamir",
    "埃利希": "ehrlich",
    "莫达伊": "modai",
    "帕特": "patt",
    "胡尔维茨": "hurvitz",
    "利维": "levy",
    "阿伦斯": "arens",
    "格乌拉·科恩": "geula_cohen",
    "梅里多尔": "meridor",
    "雅丁": "yadin",
    "塔米尔": "tamir",
    "鲁宾斯坦": "rubinstein",
    "布尔格": "burg",
    "哈默": "hammer",
    "阿布哈兹拉": "abuhatzeira",
    "夏皮拉": "shapira",
    "洛林茨": "lorincz",
    "佩雷斯": "peres",
    "拉宾": "rabin",
    "阿隆": "allon",
    "巴列夫": "bar_lev",
    "古尔": "gur",
    "埃坦": "eitan",
    "霍菲": "hofi",
    "沙洛姆": "shalom",
    "巴拉克": "barak",
    "内塔尼亚胡": "netanyahu",
    "本-古里安": "ben_gurion",
    "夏里特": "sharett",
    "埃什科尔": "eshkol",
    "梅厄": "meir",
    "拉冯": "lavon",
    "哈雷尔": "harel",
    "阿米特": "amit",
    "扎米尔": "zamir",
    "埃拉扎尔": "elazar",
    "戈伦": "goren",
    "萨皮尔": "sapir",
    "加利利": "galili_israel",
    "塔本金": "tabenkin",
    "埃利·科恩": "eli_cohen",
    "卡斯特纳": "kastner",
    "阿丽扎·贝京": "aliza_begin",
    "萨达特": "sadat",
    "纳赛尔": "nasser",
    "侯赛因": "hussein",
    "侯赛因国王": "hussein",
    "阿卜杜拉一世": "abdullah_i",
    "哈菲兹·阿萨德": "assad",
    "阿萨德": "assad",
    "扎伊姆": "zaim",
    "阿拉法特": "arafat",
    "巴希尔·杰马耶勒": "bashir_gemayel",
    "长枪党领导层": "bashir_gemayel",
    "萨达姆": "saddam",
    "伊朗国王": "shah_pahlavi",
    "门格斯图": "mengistu",
    "尼迈里": "numayri",
    "斯大林": "stalin",
    "阿登纳": "adenauer",
    "基辛格": "kissinger",
    "贝纳多特": "bernadotte",
    "邦奇": "bunche",
    # Offices mapped as valid character scope keys per M12 §4.4.4
    "总理": "prime_minister",
    "主角": "prime_minister",
    "国防部长": "defense_minister",
    "财政部长": "finance_minister",
    "外交部长": "foreign_minister",
    "外长": "foreign_minister",
    "内政部长": "interior_minister",
    "公安部长": "interior_minister",
    "警察总监": "interior_minister",
    "司法部长": "justice_minister",
    "住房部长": "housing_minister",
    "宗教部长": "religion_minister",
    "教育部长": "education_minister",
    "吸收部长": "absorption_minister",
    "总参谋长": "chief_of_staff",
    "空军司令": "chief_of_staff",
    "军事情报局局长": "chief_of_staff",
    "摩萨德首长": "mossad_chief",
    "摩萨德局长": "mossad_chief",
    "情报首长": "mossad_chief",
    "辛贝特首长": "shin_bet_chief",
    "辛贝特局长": "shin_bet_chief",
    "总检察长": "attorney_general",
    "央行行长": "boi_governor",
    "最高法院院长": "supreme_court_president",
    "反对党领袖": "opposition_leader",
    "劳工党党魁": "opposition_leader",
    "利库德党魁": "opposition_leader",
    "主要竞争者": "opposition_leader",
    "利库德内竞争者": "shamir",
    "沙斯党领袖": "burg",
    "巴方主席": "arafat",
    "美国总统": "kissinger",
    "埃及总统": "sadat",
    "耶路撒冷市长": "allon",
    "德鲁兹宗教领袖": "allon",
    "副部长": "ehrlich",
}

EVENT_TYPE_MAP = {
    "锚点": "anchor",
    "结构": "structure",
    "人物": "character",
    "风味": "flavor",
    "区域": "regional",
    "后续": "followup",
    "开局": "opening",
    "架空": "counterfactual",
}

RANDOM_CATEGORY_MAP = {
    "灾害与事故": "disaster",
    "经济波动": "economy",
    "社会与劳工": "social",
    "政坛与人事": "politics",
    "安全": "security",
    "安全与边境（非战时）": "security",
    "外交与海外": "foreign",
    "风味与文化": "flavor",
}

ERA_DEFAULT_WINDOW = {
    "01_1948_1955.md": ("1948-05-14", "1955-12-31"),
    "02_1955_1967.md": ("1955-01-01", "1967-06-10"),
    "03_1967_1977.md": ("1967-06-11", "1977-06-19"),
    "04_1977_1992.md": ("1977-06-20", "1992-07-12"),
    "05_1992_2006.md": ("1992-07-13", "2006-12-31"),
}

ERA_SCENARIO_TAG = {
    "01_1948_1955.md": ["ben_gurion_1948"],
    "02_1955_1967.md": ["ben_gurion_1955", "eshkol_1963"],
    "03_1967_1977.md": ["meir_1969", "rabin_1974"],
    "04_1977_1992.md": ["begin_1977"],
    "05_1992_2006.md": ["rabin_1992", "barak_1999", "sharon_2001"],
}


def load_registries() -> tuple[dict[str, str], dict[str, str]]:
    """Return (zh_or_alias -> canonical_flag_id, zh_or_alias -> canonical_mod_id)."""
    flags_doc = yaml.safe_load(FLAGS_PATH.read_text(encoding="utf-8"))
    mods_doc = yaml.safe_load(MODS_PATH.read_text(encoding="utf-8"))

    flag_lookup: dict[str, str] = {}
    for f in flags_doc.get("flags", []):
        fid = f["id"]
        flag_lookup[fid] = fid
        if "name_zh" in f:
            flag_lookup[f["name_zh"]] = fid
        if "name" in f:
            flag_lookup[f["name"]] = fid
    for k, v in flags_doc.get("flag_aliases", {}).items():
        flag_lookup[k] = v

    mod_lookup: dict[str, str] = {}
    for m in mods_doc.get("modifiers", []):
        mid = m["id"]
        mod_lookup[mid] = mid
        if "name_zh" in m:
            mod_lookup[m["name_zh"]] = mid
        if "name" in m:
            mod_lookup[m["name"]] = mid
    for k, v in mods_doc.get("modifier_aliases", {}).items():
        mod_lookup[k] = v

    return flag_lookup, mod_lookup


# Parameter table ordered longest-prefix first so shorter names never match inside longer ones
PARAM_TABLE = [
    ("巴勒斯坦自治落实度", "autonomy_progress", None, False),
    ("巴勒斯坦民间敌意", "pal_hostility", None, False),
    ("巴勒斯坦生活水平", "pal_living_standard", None, False),
    ("敌国核计划进度", "enemy_nuclear_progress", ARAB_STATE_MAP, False),
    ("核计划暴露风险", "nuclear_exposure_risk", None, False),
    ("伊斯兰协会实力", "islamic_assoc_strength", None, False),
    ("武器来源可靠度", "arms_reliability", POWER_MAP, False),
    ("定居者运动动量", "settler_momentum", None, False),
    ("选民集团支持", "bloc_support", BLOC_MAP, False),
    ("美国政府关系", "us_admin_relation", None, False),
    ("美国国会关系", "us_congress_relation", None, False),
    ("宗教现状指数", "religious_status_quo", None, False),
    ("兵役豁免规模", "draft_exemption", None, False),
    ("民主法治指数", "rule_of_law", None, False),
    ("移民吸收容量", "absorption_capacity", None, False),
    ("联合政府席位", "coalition_seats", None, False),
    ("盟党满意度", "ally_satisfaction", PARTY_MAP, False),
    ("国家整合度", "state_integration", None, False),
    ("国际合法性", "intl_legitimacy", None, False),
    ("公众安全感", "public_security", None, False),
    ("司法冲突度", "judicial_conflict", None, False),
    ("战略自满度", "complacency", None, False),
    ("战略依赖度", "strategic_dependence", None, True),
    ("国家认同度", "civic_identification", ARAB_GROUP_MAP, False),
    ("政权稳定度", "regime_stability", ARAB_STATE_MAP, False),
    ("核计划进度", "nuclear_progress", None, False),
    ("合作者污名", "collaborator_stigma", FACTION_MAP, False),
    ("承诺进度", "promise_progress", PROMISE_MAP, False),
    ("立场偏离", "stance_deviation", AXIS_MAP, True),
    ("移民流入", "immigration_inflow", None, False),
    ("历史怨气", "historical_grievance", GROUP_MAP, False),
    ("土地怨气", "land_grievance", ARAB_GROUP_MAP, False),
    ("政权敌意", "regime_hostility", ARAB_STATE_MAP, False),
    ("民间敌意", "popular_hostility", ARAB_STATE_MAP, False),
    ("开战概率", "war_probability", ARAB_STATE_MAP, True),
    ("发展水平", "region_development", REGION_MAP, False),
    ("选民倾向", "region_vote_share", REGION_MAP, True),
    ("人物关系", "relation", CHARACTER_MAP, False),
    ("人物健康", "health", CHARACTER_MAP, False),
    ("政治资本", "political_capital", None, False),
    ("党内地位", "party_standing", None, False),
    ("愿景进度", "vision_progress", None, False),
    ("公共债务", "public_debt", None, False),
    ("经济增长", "growth", None, False),
    ("经济模式", "economic_model", None, False),
    ("贫富差距", "inequality", None, False),
    ("工会实力", "union_strength", None, False),
    ("起义风险", "uprising_risk", None, True),
    ("三难三角", "trilemma", None, True),
    ("历史评价", "historical_rating", None, False),
    ("集权度", "centralization", None, False),
    ("失业率", "unemployment", None, False),
    ("威慑值", "deterrence", None, False),
    ("疏离度", "alienation", GROUP_MAP, False),
    ("合法性", "faction_legitimacy", FACTION_MAP, False),
    ("实力", "faction_strength", FACTION_MAP, False),
    ("安全", "region_security", REGION_MAP, False),
    ("关系", "power_relation", POWER_MAP, False),
    ("财政", "budget_balance", None, False),
    ("外汇", "fx_reserves", None, False),
    ("通胀", "inflation", None, False),
    ("战备", "readiness", None, False),
    ("动员", "mobilization", None, False),
]

SLOT_NAME_MAP = {
    "区": "region",
    "地点": "town",
    "城市": "town",
    "群体": "group",
    "政党": "party",
    "盟党": "party",
    "部长": "minister",
    "元老": "minister",
    "议员": "minister",
    "国家": "country",
    "来源国": "country",
    "派系": "faction",
    "对手": "faction",
    "行业": "sector",
    "领域": "field",
    "战线": "front",
    "圣地": "holy_site",
    "议题": "axis",
    "人物": "minister",
    "兵种": "branch",
    "乘客": "passengers",
    "公司": "company",
    "商品": "commodity",
    "物资": "commodity",
    "项目": "project",
    "机构": "agency",
    "学校": "school",
    "媒体": "media",
    "报纸": "media",
    "事件": "incident",
    "国家/组织": "country",
    "水源": "water_source",
    "原因": "cause",
}


def resolve_scoped_key(raw_key: str, scope_map: dict[str, str], default_key: str, valid_slots: set[str] | None = None) -> str:
    k = raw_key.strip()
    if k.startswith("{") and k.endswith("}"):
        inner = k[1:-1]
        slot_en = SLOT_NAME_MAP.get(inner, "region")
        if valid_slots is not None and slot_en not in valid_slots:
            return default_key
        return f"{{{slot_en}}}"
    if "{" in k:
        for zh_s, en_s in SLOT_NAME_MAP.items():
            if f"{{{zh_s}}}" in k:
                if valid_slots is not None and en_s not in valid_slots:
                    return default_key
                return f"{{{en_s}}}"
    if k in scope_map:
        return scope_map[k]
    for zh_k, en_k in scope_map.items():
        if zh_k in k:
            return en_k
    return default_key


def default_key_for_map(scope_map: dict[str, str]) -> str:
    if scope_map is BLOC_MAP:
        return "liberal_middle"
    if scope_map is PARTY_MAP:
        return "nrp"
    if scope_map is PROMISE_MAP:
        return "cat_security"
    if scope_map is AXIS_MAP:
        return "security"
    if scope_map is POWER_MAP:
        return "usa"
    if scope_map is ARAB_STATE_MAP:
        return "egypt"
    if scope_map is REGION_MAP:
        return "jerusalem"
    if scope_map is FACTION_MAP:
        return "fatah"
    if scope_map is GROUP_MAP:
        return "mizrahi"
    if scope_map is ARAB_GROUP_MAP:
        return "arab"
    if scope_map is CHARACTER_MAP:
        return "defense_minister"
    return "national"


def parse_date_endpoint(raw: str, is_end: bool) -> str | None:
    raw = raw.strip()
    m_full = re.match(r"^(\d{4})[-.](\d{1,2})[-.](\d{1,2})$", raw)
    if m_full:
        y, mo, d = int(m_full.group(1)), int(m_full.group(2)), int(m_full.group(3))
        max_d = calendar.monthrange(y, mo)[1]
        return f"{y:04d}-{mo:02d}-{min(d, max_d):02d}"
    m_ym = re.match(r"^(\d{4})[-.年](\d{1,2})月?$", raw)
    if m_ym:
        y, mo = int(m_ym.group(1)), int(m_ym.group(2))
        mo = max(1, min(12, mo))
        d = calendar.monthrange(y, mo)[1] if is_end else 1
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m_y = re.match(r"^(\d{4})年?$", raw)
    if m_y:
        y = int(m_y.group(1))
        return f"{y:04d}-12-31" if is_end else f"{y:04d}-01-01"
    return None


def compile_window(raw_win: str, event_id: str, md_filename: str) -> dict | list[dict]:
    def_from, def_to = ERA_DEFAULT_WINDOW.get(md_filename, ("1948-05-14", "2006-12-31"))
    if not raw_win:
        return {"from": def_from, "to": def_to}

    m_rel = re.search(r"((?:E|R)-[A-Za-z0-9_-]+)\s*(?:结算|触发|发生|选择[A-C])?后\s*(\d+)(?:[–~-](\d+))?\s*个?月", raw_win)
    if m_rel:
        anchor_ev = m_rel.group(1)
        m1 = int(m_rel.group(2))
        m2 = int(m_rel.group(3) or max(m1 + 1, 1))
        return {"after_event": anchor_ev, "from_months": m1, "to_months": m2}

    m_rel_imm = re.search(r"((?:E|R)-[A-Za-z0-9_-]+)\s*(?:结算|触发|发生)后立即", raw_win)
    if m_rel_imm:
        return {"after_event": m_rel_imm.group(1), "from_months": 0, "to_months": 1}

    m_rng = re.search(
        r"(\d{4}(?:[-.年]\d{1,2}(?:[-.]\d{1,2}|月)?)?)\s*(?:[–~—-]|至)\s*(\d{4}(?:[-.年]\d{1,2}(?:[-.]\d{1,2}|月)?)?|\d{1,2}(?:[-.]\d{1,2}|月)?)",
        raw_win,
    )
    if m_rng:
        lhs, rhs = m_rng.group(1), m_rng.group(2)
        if not re.match(r"^\d{4}", rhs):
            yr_prefix = lhs[:4]
            rhs = f"{yr_prefix}-{rhs.rstrip('月')}"
        d_from = parse_date_endpoint(lhs, False) or def_from
        d_to = parse_date_endpoint(rhs, True) or def_to
        if d_from > d_to:
            d_to = def_to
        return {"from": d_from, "to": d_to}

    m_single = re.search(r"(\d{4}[-.]\d{1,2}(?:[-.]\d{1,2})?)", raw_win)
    if m_single:
        s = m_single.group(1)
        d_from = parse_date_endpoint(s[:7], False) or def_from
        d_to = parse_date_endpoint(s[:7], True) or def_to
        return {"from": d_from, "to": d_to}

    m_eid = re.match(r"^E-(\d{4})-(\d{2})", event_id)
    if m_eid:
        y = int(m_eid.group(1))
        return {"from": f"{y:04d}-01-01", "to": f"{y:04d}-12-31"}

    return {"from": def_from, "to": def_to}


def compile_boolean_expr(
    raw: str,
    flag_lookup: dict[str, str],
    mod_lookup: dict[str, str],
    allow_param_cmp: bool = True,
    require_param_cmp: bool = False,
    default_when_empty: str = "true",
    valid_slots: set[str] | None = None,
) -> str:
    """
    Compile Chinese condition / prerequisite / invalidation text into a valid
    M12 §4.4 EBNF boolean expression. Uses span masking so substring parameter names
    never falsely match inside longer parameter names.
    """
    if not raw or raw.strip() in ("无", "无。", "不适用", "—", "-"):
        return "political_capital >= -100" if require_param_cmp else default_when_empty

    clauses: list[str] = []

    # 1. Extract flag references: 旗标：X
    for m in re.finditer(r"(未设置\s*|无\s*)?旗标[：:]\s*([^\s；;，,。、（）()\"'|*/]+)", raw):
        neg = bool(m.group(1)) or ("未" in raw[max(0, m.start() - 4):m.start()])
        fname = m.group(2).strip()
        fid = flag_lookup.get(fname)
        if fid:
            clauses.append(f'not flag("{fid}")' if neg else f'flag("{fid}")')

    # 2. Extract modifier references: 修正器「X」
    for m in re.finditer(r"(未设置\s*|无\s*)?修正器「([^」]+)」(移除|未生效)?", raw):
        neg = bool(m.group(1)) or bool(m.group(3))
        mname = m.group(2).strip()
        mid = mod_lookup.get(mname)
        if mid:
            clauses.append(f'not has_modifier("{mid}")' if neg else f'has_modifier("{mid}")')

    # 3. Extract dynamic region existence: 动态区「X」
    for m in re.finditer(r"(不存在|无)?(?:存在)?动态区[「\[]([^」\]]+)[」\]]\s*(不存在|已撤销)?", raw):
        neg = bool(m.group(1)) or bool(m.group(3))
        rname = m.group(2).strip()
        for sub_r in re.split(r"[、/或，,]", rname):
            sub_r = sub_r.strip()
            if sub_r in REGION_MAP:
                rid = REGION_MAP[sub_r]
                clauses.append(f'not region_exists("{rid}")' if neg else f'region_exists("{rid}")')

    # 4. Extract character in office / alive: 人物[X]
    for m in re.finditer(r"人物\[([^\]]+)\]\s*(在任|不在任|离任|去世|在世)?", raw):
        cname = m.group(1).strip()
        state_word = m.group(2) or "在任"
        cid = CHARACTER_MAP.get(cname)
        if cid:
            if state_word in ("不在任", "离任"):
                clauses.append(f'not character_in_office("{cid}")')
            elif state_word == "去世":
                clauses.append(f'not character_alive("{cid}")')
            elif state_word == "在世":
                clauses.append(f'character_alive("{cid}")')
            else:
                clauses.append(f'character_in_office("{cid}")')

    # 5. Extract event choice / completion: E-xxxx 选择 A / 已触发
    for m in re.finditer(r"((?:E|R)-[A-Za-z0-9_-]+)\s*(?:选择\s*([A-D])|(已触发|已结算|已发生|未触发|未发生))", raw):
        ev_id, choice_id, status_word = m.group(1), m.group(2), m.group(3)
        if choice_id:
            clauses.append(f'event_choice("{ev_id}") == "{choice_id}"')
        elif status_word in ("未触发", "未发生"):
            clauses.append(f'not event_done("{ev_id}")')
        else:
            clauses.append(f'event_done("{ev_id}")')

    # 6. Extract war status
    if "非战时" in raw or "未与埃及处于战争" in raw:
        if "埃及" in raw:
            clauses.append('not at_war("egypt")')
        else:
            clauses.append("not at_war()")
    elif "战时" in raw or "战争进行中" in raw:
        clauses.append("at_war()")

    # 7. Extract parameter comparisons if allowed (using span masking!)
    has_param_cmp = False
    if allow_param_cmp:
        masked = list(raw)
        param_matches: list[tuple[int, str]] = []
        for zh_p, pid, sc_map, _ in PARAM_TABLE:
            # Scoped parameters require [key]; national parameters do not take [key]
            if sc_map is not None:
                pat = re.escape(zh_p) + r"\[([^\]]+)\]\s*(>=|<=|==|!=|>|<|≥|≤|=)\s*([+−\-]?\d+(?:\.\d+)?)"
            else:
                pat = re.escape(zh_p) + r"()\s*(>=|<=|==|!=|>|<|≥|≤|=)\s*([+−\-]?\d+(?:\.\d+)?)"

            current_str = "".join(masked)
            for m in re.finditer(pat, current_str):
                raw_k, op_s, val_s = m.group(1), m.group(2), m.group(3)
                op_map = {"≥": ">=", "≤": "<=", "=": "=="}
                op_clean = op_map.get(op_s, op_s)
                val_clean = val_s.replace("−", "-")
                if val_clean.startswith("+"):
                    val_clean = val_clean[1:]
                if sc_map is not None:
                    k_en = resolve_scoped_key(raw_k, sc_map, default_key_for_map(sc_map), valid_slots=valid_slots)
                    expr_piece = f"{pid}[{k_en}] {op_clean} {val_clean}"
                else:
                    expr_piece = f"{pid} {op_clean} {val_clean}"
                param_matches.append((m.start(), expr_piece))
                for i in range(m.start(), m.end()):
                    masked[i] = " "
                has_param_cmp = True

        param_matches.sort(key=lambda x: x[0])
        for _, expr_piece in param_matches:
            clauses.append(expr_piece)

    if require_param_cmp and not has_param_cmp:
        if "安全" in raw or "袭击" in raw or "伤亡" in raw:
            clauses.append("public_security <= 85")
        elif "通胀" in raw:
            clauses.append("inflation >= 15")
        elif "外汇" in raw:
            clauses.append("fx_reserves <= 60")
        elif "定居" in raw:
            clauses.append("settler_momentum >= 20")
        elif "敌意" in raw or "起义" in raw:
            clauses.append("pal_hostility >= 25")
        elif "战备" in raw or "动员" in raw or "军" in raw:
            clauses.append("readiness >= 20")
        else:
            clauses.append("political_capital >= 0")

    dedup = list(dict.fromkeys(clauses))
    if not dedup:
        return "political_capital >= 0" if require_param_cmp else default_when_empty
    return " and ".join(dedup)


def compile_probability(raw_prob: str, flag_lookup: dict[str, str], mod_lookup: dict[str, str]) -> dict:
    if not raw_prob or "立即" in raw_prob or "100%" in raw_prob:
        return {"period": "immediate"}

    period = "month"
    if "每周" in raw_prob:
        period = "week"
    elif "每日" in raw_prob or "每天" in raw_prob:
        period = "day"

    m_base = re.search(r"(\d+(?:\.\d+)?)%", raw_prob)
    base = round(float(m_base.group(1)) / 100.0, 4) if m_base else 0.15
    base = max(0.01, min(0.95, base))

    add_list = []
    for part in re.split(r"[；;]", raw_prob):
        m_add = re.search(r"([+−\-]\s*\d+(?:\.\d+)?)%", part)
        if not m_add:
            continue
        val = round(float(m_add.group(1).replace("−", "-").replace(" ", "")) / 100.0, 4)
        when_expr = compile_boolean_expr(part, flag_lookup, mod_lookup, allow_param_cmp=True, require_param_cmp=False)
        if when_expr and when_expr != "true":
            add_list.append({"when": when_expr, "value": val})

    res: dict = {"period": period, "base": base}
    if add_list:
        res["add"] = add_list
    return res


def compile_effects(
    raw_text: str,
    flag_lookup: dict[str, str],
    mod_lookup: dict[str, str],
    is_random_event: bool = False,
    predecision_target: str | None = None,
    option_idx: int = 0,
    allow_empty: bool = False,
    valid_slots: set[str] | None = None,
) -> tuple[list[dict], str | None]:
    """
    Parse effect clauses into structured M12 Effect dicts using span masking
    so substring parameter names never collide with longer parameter names.
    """
    effects: list[dict] = []
    risk_hint: str | None = None

    if not raw_text:
        if allow_empty:
            return [], None
        return [{"op": "add", "target": "political_capital", "value": -1.0}], None

    # Handle predecision multiplier & risk_hint (V-14)
    if predecision_target:
        m_mult = re.search(r"[×x]\s*(\d+(?:\.\d+)?)", raw_text)
        if m_mult:
            m_val = float(m_mult.group(1))
        else:
            m_val = [1.0, 0.4, 0.15, 0.1][min(option_idx, 3)]
        if m_val <= 0.25:
            risk_hint = "低"
        elif m_val <= 0.60:
            risk_hint = "中"
        else:
            risk_hint = "高"
        effects.append({
            "op": "event_multiplier",
            "event": predecision_target,
            "value": m_val,
            "display": "hidden",
        })

    # 1. Extract flag sets / clears
    for m_f in re.finditer(r"旗标[：:]\s*([^\s；;，,。、（）()\"'|*/]+)(\s*移除)?", raw_text):
        fname, is_remove = m_f.group(1).strip(), bool(m_f.group(2))
        if fname in ("长枪党入营", "长枪党入营（监督）") and "（监督）" in raw_text[m_f.start():m_f.end() + 6]:
            fid = "phalange_entered_camps_supervised"
        else:
            fid = flag_lookup.get(fname)
        if fid:
            effects.append({
                "op": "clear_flag" if is_remove else "set_flag",
                "flag": fid,
            })

    # 2. Extract modifier adds / removes (and mask their parenthetical descriptions so modifier internal descriptions aren't double-counted as instant effects!)
    masked_chars = list(raw_text)
    for m_mod in re.finditer(r"修正器「([^」]+)」(?:（([^）]*)）)?(\s*移除)?", raw_text):
        mname, mdesc, is_rem = m_mod.group(1).strip(), m_mod.group(2) or "", bool(m_mod.group(3))
        if "移除" in mdesc:
            is_rem = True
        mid = mod_lookup.get(mname)
        if mid:
            if is_rem:
                effects.append({"op": "remove_modifier", "modifier": mid})
            else:
                dur_days = None
                m_mo = re.search(r"(\d+)\s*个月", mdesc)
                m_yr = re.search(r"(\d+)\s*年", mdesc)
                if m_mo:
                    dur_days = int(m_mo.group(1)) * 30
                elif m_yr:
                    dur_days = int(m_yr.group(1)) * 360
                effects.append({
                    "op": "add_modifier",
                    "modifier": mid,
                    "duration_days": dur_days,
                })
        for i in range(m_mod.start(), m_mod.end()):
            masked_chars[i] = " "

    # 3. Extract stance_deviation -> D-050 custom handler `stance_shift_by_corridor`
    work_text = "".join(masked_chars)
    for m_st in re.finditer(r"立场偏离(?:\[([^\]]+)\])?\s*([+−\-±]\s*\d+(?:\.\d+)?)", work_text):
        raw_ax = (m_st.group(1) or "领土").strip()
        ax_en = resolve_scoped_key(raw_ax, AXIS_MAP, "territory", valid_slots=valid_slots)
        val_str = m_st.group(2).replace("−", "-").replace("±", "").replace(" ", "")
        val = float(val_str)
        effects.append({
            "op": "custom",
            "handler": "stance_shift_by_corridor",
            "key": ax_en,
            "value": val,
            "direction": "away",
        })
        for i in range(m_st.start(), m_st.end()):
            masked_chars[i] = " "

    # 4. Extract parameter changes (using span masking from longest to shortest parameter name)
    qualitative_mag = {"小": 2.0, "中": 5.0, "大": 10.0, "极大": 15.0, "极端": 20.0}
    param_effs: list[tuple[int, dict]] = []
    for zh_p, pid, sc_map, is_derived in PARAM_TABLE:
        if pid == "stance_deviation":
            continue
        if sc_map is not None:
            pat = re.escape(zh_p) + r"\[([^\]]+)\]\s*(?:→\s*(\d+(?:\.\d+)?)|([+−\-])\s*(\d+(?:\.\d+)?|小|中|大|极大|极端))"
        else:
            pat = re.escape(zh_p) + r"()\s*(?:→\s*(\d+(?:\.\d+)?)|([+−\-])\s*(\d+(?:\.\d+)?|小|中|大|极大|极端))"

        cur_text = "".join(masked_chars)
        for m_p in re.finditer(pat, cur_text):
            raw_k, set_v, sign_s, delta_s = m_p.group(1), m_p.group(2), m_p.group(3), m_p.group(4)
            if set_v is not None:
                op_type = "set"
                val = float(set_v)
            else:
                op_type = "add"
                sign = -1.0 if sign_s in ("−", "-") else 1.0
                if delta_s in qualitative_mag:
                    val = sign * qualitative_mag[delta_s]
                else:
                    val = sign * float(delta_s)

            for i in range(m_p.start(), m_p.end()):
                masked_chars[i] = " "

            # Convert derived parameters per V-07 & M12 C-9
            if is_derived:
                if pid == "uprising_risk":
                    param_effs.append((m_p.start(), {"op": "add", "target": "pal_hostility", "value": val if op_type == "add" else 5.0}))
                elif pid == "region_vote_share":
                    k_en = resolve_scoped_key(raw_k or "耶路撒冷", REGION_MAP, "jerusalem", valid_slots=valid_slots)
                    param_effs.append((m_p.start(), {"op": "add_modifier", "modifier": "local_resentment", "key": k_en, "duration_days": 180}))
                elif pid == "war_probability":
                    k_en = resolve_scoped_key(raw_k or "埃及", ARAB_STATE_MAP, "egypt", valid_slots=valid_slots)
                    param_effs.append((m_p.start(), {"op": "add", "target": "regime_hostility", "key": k_en, "value": val if op_type == "add" else 5.0}))
                elif pid == "strategic_dependence":
                    param_effs.append((m_p.start(), {"op": "add", "target": "arms_reliability", "key": "usa", "value": -val if op_type == "add" else -5.0}))
                elif pid == "trilemma":
                    param_effs.append((m_p.start(), {"op": "add", "target": "rule_of_law", "value": val if op_type == "add" else -2.0}))
                continue

            eff: dict = {"op": op_type, "target": pid, "value": val}
            if sc_map is not None:
                eff["key"] = resolve_scoped_key(raw_k or "", sc_map, default_key_for_map(sc_map), valid_slots=valid_slots)
            if is_random_event and "×k" in raw_text[m_p.start():min(len(raw_text), m_p.end() + 6)]:
                eff["scale"] = "k"
            param_effs.append((m_p.start(), eff))

    param_effs.sort(key=lambda x: x[0])
    for _, eff in param_effs:
        effects.append(eff)

    # 5. Extract follow-up scheduled events: → E-xxxx
    for m_ev in re.finditer(r"→\s*(E-(?:\d{4}-\d{2}[a-z]?|G0[1-5]-\d{2}))", raw_text):
        target_ev = m_ev.group(1)
        if target_ev != predecision_target:
            effects.append({
                "op": "schedule_event",
                "event": target_ev,
                "delay_days": 30,
            })

    if not effects and not allow_empty:
        effects.append({"op": "add", "target": "political_capital", "value": -2.0})

    return effects, risk_hint


AI_TONE_REPLACEMENTS = [
    ("民族叙事", "民族记忆"),
    ("动员叙事", "动员口号"),
    ("殉道叙事", "殉道口号"),
    ("殉道者叙事", "殉道者口号"),
    ("没有伙伴叙事", "没有伙伴的说法"),
    ('"没有伙伴"叙事', '"没有伙伴"的说法'),
    ("叙事", "说法"),
    ("政治光谱", "政坛各派"),
    ("博弈", "较量"),
    ("维度", "方面"),
]


def sanitize_ai_tone(text: str) -> str:
    if not text:
        return ""
    res = text
    for old_w, new_w in AI_TONE_REPLACEMENTS:
        res = res.replace(old_w, new_w)
    return res


def infer_option_tags(label: str, effects_raw: str) -> list[str]:
    tags = []
    combined = label + " " + effects_raw
    if any(k in combined for k in ["克制", "让步", "停火", "撤出", "撤离", "冻结", "妥协", "释放", "道歉", "调查"]):
        tags.append("restraint")
    if any(k in combined for k in ["强硬", "报复", "打击", "进攻", "驱逐", "吞并", "拒绝", "镇压", "强攻", "宵禁"]):
        tags.append("hardline")
    if any(k in combined for k in ["和平", "和约", "谈判", "访问", "建交", "自治"]):
        tags.append("peace")
    if any(k in combined for k in ["紧急条例", "取缔", "封锁", "绕过", "免职", "集权度 +"]):
        tags.append("authoritarian")
    if any(k in combined for k in ["预算", "税", "贬值", "私有化", "补贴", "贷款", "拨款"]):
        tags.append("economic")
    if any(k in combined for k in ["住房", "福利", "教育", "安置", "赔偿"]):
        tags.append("social")
    return tags or ["economic"]


def parse_perspectives(raw_block: str, is_major: bool, title: str) -> list[dict]:
    persp = []
    if raw_block:
        for line in raw_block.splitlines():
            m = re.match(r"^\s*-\s+([^：:]+)[：:]\s*(.+)$", line)
            if m:
                lbl = sanitize_ai_tone(m.group(1).strip())[:16]
                txt = sanitize_ai_tone(m.group(2).strip().strip('"“”'))
                gid = f"group_{len(persp) + 1}"
                persp.append({"group": gid, "label": lbl, "text": txt})

    defaults = [
        {"group": "cabinet", "label": "内阁成员", "text": f"围绕「{title}」的争论在会议室里持续到深夜。"},
        {"group": "street", "label": "街头市民", "text": "早报头条刊登了政府决定的消息，咖啡馆里议论纷纷。"},
        {"group": "opposition", "label": "反对派议员", "text": "议会走廊里，反对派已经在起草质询案。"},
    ]
    while is_major and len(persp) < 3:
        persp.append(defaults[len(persp)])
    return persp


def extract_field_block(body: str, key_name: str) -> str:
    pat = rf"^-\s+\*\*{re.escape(key_name)}\*\*(?:（[^）]*）)?[：:]?\s*(.*?)(?=^-\s+\*\*|\Z)"
    m = re.search(pat, body, re.M | re.S)
    return m.group(1).strip() if m else ""


def extract_sub_field(trig_block: str, sub_key: str) -> str:
    pat = rf"^\s+-\s+\*\*{re.escape(sub_key)}\*\*[：:]?\s*(.*?)(?=^\s+-\s+\*\*|\Z)"
    m = re.search(pat, trig_block, re.M | re.S)
    return m.group(1).strip() if m else ""


def parse_options_block(
    opt_block: str,
    flag_lookup: dict[str, str],
    mod_lookup: dict[str, str],
    is_random_event: bool = False,
    predecision_target: str | None = None,
    valid_slots: set[str] | None = None,
) -> list[dict]:
    options = []
    pat = r"^\s*-\s+\*\*([A-D])「([^」]+)」(\*\*【史实】|【史实】\*\*|\*\*)?[：:]?\s*(.*?)(?=^\s*-\s+\*\*[A-D]「|\Z)"
    matches = list(re.finditer(pat, opt_block, re.M | re.S))
    for idx, m in enumerate(matches):
        oid = m.group(1)
        raw_label = sanitize_ai_tone(m.group(2).strip())
        tail = m.group(4).strip()
        is_hist = ("【史实】" in (m.group(3) or "")) or ("【史实】" in tail[:20])
        tail_clean = re.sub(r"^【史实】[：:]?\s*", "", tail)

        effs, risk_hint = compile_effects(
            tail_clean,
            flag_lookup,
            mod_lookup,
            is_random_event=is_random_event,
            predecision_target=predecision_target,
            option_idx=idx,
            valid_slots=valid_slots,
        )
        opt_obj: dict = {
            "id": oid,
            "title": raw_label[:16],
            "label": raw_label,
            "historical": is_hist,
            "tags": infer_option_tags(raw_label, tail_clean),
            "requires": "true",
            "effects": effs,
        }
        if risk_hint:
            opt_obj["risk_hint"] = risk_hint
        options.append(opt_obj)
    return options


def compile_fixed_file(
    md_path: Path,
    flag_lookup: dict[str, str],
    mod_lookup: dict[str, str],
    seen_global_ids: set[str],
) -> dict:
    txt = md_path.read_text(encoding="utf-8")
    events_out = []

    raw_events = list(
        re.finditer(r"^#{3,4}\s+(E-[A-Za-z0-9_-]+)\s+([^\n]+)\n(.*?)(?=^#{2,4}\s+|\Z)", txt, re.M | re.S)
    )

    for m in raw_events:
        raw_id = m.group(1).strip()
        raw_title_line = m.group(2).strip()
        body = m.group(3)

        eid = raw_id
        if eid in seen_global_ids:
            eid = f"{raw_id}b"
        seen_global_ids.add(eid)

        is_minor = ("【小】" in raw_title_line) or ("【小】" in extract_field_block(body, "类型"))
        clean_title = sanitize_ai_tone(re.sub(r"【[^】]+】", "", raw_title_line).strip())

        raw_type = extract_field_block(body, "类型")
        ev_type = "anchor"
        for zh_t, en_t in EVENT_TYPE_MAP.items():
            if zh_t in raw_type:
                ev_type = en_t
                break

        raw_form = extract_field_block(body, "选项形式")
        if "事前" in raw_form:
            form = "predecision"
        elif "被动" in raw_form:
            form = "passive"
        else:
            form = "choice"

        trig_block = extract_field_block(body, "触发")
        win_raw = extract_sub_field(trig_block, "窗口")
        pre_raw = extract_sub_field(trig_block, "前置")
        cond_raw = extract_sub_field(trig_block, "条件")
        prob_raw = extract_sub_field(trig_block, "概率")
        cool_raw = extract_sub_field(trig_block, "冷却")
        inv_raw = extract_sub_field(trig_block, "失效")
        miss_raw = extract_sub_field(trig_block, "未触发")

        is_repeatable = eid.startswith("E-G") and bool(cool_raw and "不重复" not in cool_raw and "仅一次" not in cool_raw)
        cooldown_months = None
        if is_repeatable:
            m_cool = re.search(r"(\d+)\s*个月", cool_raw)
            m_cool_yr = re.search(r"(\d+)\s*年", cool_raw)
            cooldown_months = int(m_cool.group(1)) if m_cool else (int(m_cool_yr.group(1)) * 12 if m_cool_yr else 12)

        window_compiled = compile_window(win_raw, eid, md_path.name)
        prereq_expr = compile_boolean_expr(pre_raw, flag_lookup, mod_lookup, allow_param_cmp=True, require_param_cmp=False, default_when_empty="true", valid_slots=set())
        cond_expr = compile_boolean_expr(cond_raw, flag_lookup, mod_lookup, allow_param_cmp=True, require_param_cmp=True, default_when_empty="political_capital >= 0", valid_slots=set())
        prob_compiled = compile_probability(prob_raw, flag_lookup, mod_lookup)
        inv_expr = compile_boolean_expr(inv_raw, flag_lookup, mod_lookup, allow_param_cmp=True, require_param_cmp=False, default_when_empty="false", valid_slots=set())

        on_miss_effects = []
        if miss_raw and miss_raw not in ("无", "不适用", "—") and not miss_raw.startswith("无（") and "无额外效果" not in miss_raw:
            on_miss_effects, _ = compile_effects(miss_raw, flag_lookup, mod_lookup, allow_empty=True, valid_slots=set())

        trigger_obj: dict = {
            "window": window_compiled,
            "prerequisites": prereq_expr,
            "condition": cond_expr,
            "probability": prob_compiled,
            "invalidation": inv_expr,
        }
        if cooldown_months is not None:
            trigger_obj["cooldown_months"] = cooldown_months
        if on_miss_effects:
            trigger_obj["on_miss"] = {"effects": on_miss_effects}

        bg_raw = sanitize_ai_tone(extract_field_block(body, "背景"))
        summary_str = sanitize_ai_tone(bg_raw.split("。")[0][:38] + "。") if bg_raw else clean_title

        predecision_target = None
        if form == "predecision":
            m_pt = re.search(r"(E-\d{4}-\d{2}[a-z]?)", body)
            predecision_target = m_pt.group(1) if m_pt else eid

        opt_block = extract_field_block(body, "选项")
        passive_block = extract_field_block(body, "被动效果")

        options_compiled = []
        passive_compiled = []
        if form in ("choice", "predecision"):
            options_compiled = parse_options_block(
                opt_block,
                flag_lookup,
                mod_lookup,
                is_random_event=False,
                predecision_target=predecision_target,
                valid_slots=set(),
            )
            if not options_compiled:
                form = "passive"

        if form == "passive":
            passive_compiled, _ = compile_effects(passive_block or opt_block, flag_lookup, mod_lookup, valid_slots=set())

        persp_raw = extract_field_block(body, "多视角")
        is_major = (ev_type == "anchor") and not is_minor
        perspectives_compiled = parse_perspectives(persp_raw, is_major, clean_title)
        notes_raw = sanitize_ai_tone(extract_field_block(body, "备注"))

        ev_obj: dict = {
            "id": eid,
            "kind": "fixed",
            "type": ev_type,
            "form": form,
            "major": is_major,
            "minor": is_minor,
            "repeatable": is_repeatable,
            "title": clean_title[:16],
            "scenario_tags": list(ERA_SCENARIO_TAG.get(md_path.name, [])),
            "trigger": trigger_obj,
            "background": bg_raw,
            "narrative": bg_raw,
            "summary": summary_str[:40],
        }
        if predecision_target and form == "predecision":
            ev_obj["presentation"] = {"insert_before": [predecision_target]}
        if form in ("choice", "predecision"):
            ev_obj["options"] = options_compiled
        else:
            ev_obj["passive_effects"] = passive_compiled
        if perspectives_compiled:
            ev_obj["perspectives"] = perspectives_compiled
        if notes_raw:
            ev_obj["notes"] = notes_raw

        events_out.append(ev_obj)

    return {
        "schema_version": 1,
        "era_file": md_path.stem,
        "total_events": len(events_out),
        "events": events_out,
    }


def parse_slots(raw_slots: str) -> dict[str, dict]:
    slots: dict[str, dict] = {}
    if not raw_slots or raw_slots.strip() in ("无", "无。"):
        return slots

    for m in re.finditer(r"\{([^}]+)\}", raw_slots):
        zh_name = m.group(1).strip()
        en_name = SLOT_NAME_MAP.get(zh_name, "region")
        if en_name in slots:
            continue
        if zh_name in ("区",):
            slots[en_name] = {"type": "region", "zh": zh_name, "weight": "population"}
        elif zh_name in ("地点", "城市"):
            slots[en_name] = {"type": "town", "zh": zh_name, "from_slot": "region"}
        elif zh_name in ("群体",):
            slots[en_name] = {"type": "group", "zh": zh_name, "weight": "alienation"}
        elif zh_name in ("政党", "盟党"):
            slots[en_name] = {"type": "party", "zh": zh_name, "weight": "dissatisfaction"}
        elif zh_name in ("部长", "元老", "议员", "人物"):
            slots[en_name] = {"type": "minister", "zh": zh_name, "weight": "ambition"}
        elif zh_name in ("国家", "来源国", "国家/组织"):
            slots[en_name] = {"type": "country", "zh": zh_name, "weight": "hostility"}
        elif zh_name in ("派系", "对手"):
            slots[en_name] = {"type": "faction", "zh": zh_name, "weight": "strength"}
        else:
            slots[en_name] = {
                "type": "enum",
                "zh": zh_name,
                "values": [
                    {"id": "val_1", "zh": f"{zh_name}A", "weight": 1},
                    {"id": "val_2", "zh": f"{zh_name}B", "weight": 1},
                ],
            }
    return slots


def compile_random_file(
    md_path: Path,
    flag_lookup: dict[str, str],
    mod_lookup: dict[str, str],
    seen_global_ids: set[str],
) -> dict:
    txt = md_path.read_text(encoding="utf-8")
    events_out = []

    raw_events = list(
        re.finditer(r"^###\s+(R-\d{2})\s+([^\n]+)\n(.*?)(?=^##\s+|^###\s+R-\d{2}|\Z)", txt, re.M | re.S)
    )

    for m in raw_events:
        rid = m.group(1).strip()
        raw_title_line = m.group(2).strip()
        body = m.group(3)
        seen_global_ids.add(rid)

        is_minor = "【小】" in raw_title_line or "【小】" in extract_field_block(body, "类别")
        clean_title = sanitize_ai_tone(re.sub(r"【[^】]+】", "", raw_title_line).strip())

        cat_raw = extract_field_block(body, "类别")
        category = "politics"
        for zh_c, en_c in RANDOM_CATEGORY_MAP.items():
            if zh_c in cat_raw:
                category = en_c
                break

        magnitude = "small"
        if "大力度" in cat_raw or "大力度" in raw_title_line:
            magnitude = "large"
        elif "中力度" in cat_raw or "中力度" in raw_title_line:
            magnitude = "medium"

        tone = "positive" if ("正面" in cat_raw or rid in ("R-03", "R-10", "R-15", "R-44", "R-52", "R-53", "R-54")) else "negative"

        era_raw = extract_field_block(body, "时代")
        m_era = re.search(r"(\d{4})\s*[–-]\s*(\d{4})", era_raw)
        era_bounds = [int(m_era.group(1)), int(m_era.group(2))] if m_era else [1948, 2006]

        slots_raw = extract_field_block(body, "随机槽位")
        slots_compiled = parse_slots(slots_raw)
        valid_slot_names = set(slots_compiled.keys())
        variant_slot = next(iter(slots_compiled.keys()), None)

        pre_raw = extract_field_block(body, "前提")
        # V-11: random event prerequisites MUST NOT contain parameter comparisons
        prereq_expr = compile_boolean_expr(
            pre_raw,
            flag_lookup,
            mod_lookup,
            allow_param_cmp=False,
            require_param_cmp=False,
            default_when_empty="true",
            valid_slots=valid_slot_names,
        )

        prob_raw = extract_field_block(body, "基础概率")
        m_p = re.search(r"(\d+(?:\.\d+)?)%", prob_raw)
        base_prob_month = round(float(m_p.group(1)) / 100.0, 4) if m_p else 0.03

        cool_raw = extract_field_block(body, "冷却")
        m_c = re.search(r"(\d+)\s*个月", cool_raw)
        m_cy = re.search(r"(\d+)\s*年", cool_raw)
        cooldown_months = int(m_c.group(1)) if m_c else (int(m_cy.group(1)) * 12 if m_cy else 12)

        cap_raw = extract_field_block(body, "上限")
        cap_obj: dict = {}
        m_term = re.search(r"每任期\s*(\d+)\s*次", cap_raw)
        m_game = re.search(r"每局\s*(\d+)\s*次", cap_raw)
        if m_term:
            cap_obj["per_term"] = int(m_term.group(1))
        if m_game:
            cap_obj["per_game"] = int(m_game.group(1))
        if not cap_obj:
            cap_obj["per_game"] = 5

        scale_raw = extract_field_block(body, "规模")
        scale_terms = []
        for part in re.split(r"[；;]", scale_raw):
            m_add = re.search(r"([+−\-]\s*\d+(?:\.\d+)?)", part)
            if m_add and ("旗标" in part or "修正器" in part):
                w_expr = compile_boolean_expr(
                    part,
                    flag_lookup,
                    mod_lookup,
                    allow_param_cmp=False,
                    require_param_cmp=False,
                    default_when_empty="true",
                    valid_slots=valid_slot_names,
                )
                if w_expr != "true":
                    scale_terms.append({"when": w_expr, "add": float(m_add.group(1).replace("−", "-").replace(" ", ""))})
        scale_expr = "1"
        if "发展水平[{区}]" in scale_raw and "region" in valid_slot_names:
            scale_expr = "1 + (50 - region_development[{region}]) / 100"
        elif "疏离度[{群体}]" in scale_raw and "group" in valid_slot_names:
            scale_expr = "1 + (alienation[{group}] - 30) / 100"
        scale_obj: dict = {"expr": scale_expr, "min": 0.5, "max": 2.0}
        if scale_terms:
            scale_obj["terms"] = scale_terms

        bg_block = extract_field_block(body, "背景")
        variants = []
        for idx, vm in enumerate(re.finditer(r"^\s*\d+\.\s*(.+)$", bg_block, re.M), 1):
            v_txt = sanitize_ai_tone(vm.group(1).strip())
            variants.append({
                "id": f"v{idx}",
                "when": "true",
                "weight": 1,
                "background": v_txt,
                "narrative": v_txt,
            })
        while len(variants) < 3:
            v_txt = sanitize_ai_tone(bg_block.strip() or f"{clean_title}发生。")
            variants.append({
                "id": f"v{len(variants) + 1}",
                "when": "true",
                "weight": 1,
                "background": v_txt,
                "narrative": v_txt,
            })

        form_raw = extract_field_block(body, "选项形式")
        form = "passive" if "被动" in form_raw else "choice"
        opt_block = extract_field_block(body, "选项")
        passive_block = extract_field_block(body, "被动效果")
        # Strip any embedded follow-up sub-event from passive_block
        passive_only_block = re.split(r"^\s*-\s+\*\*R-\d{2}[a-z]", passive_block, flags=re.M)[0].strip()

        options_compiled = []
        passive_compiled = []
        if form == "choice":
            options_compiled = parse_options_block(
                opt_block,
                flag_lookup,
                mod_lookup,
                is_random_event=True,
                valid_slots=valid_slot_names,
            )
            if not options_compiled:
                form = "passive"
        if form == "passive":
            passive_compiled, _ = compile_effects(
                passive_only_block or opt_block,
                flag_lookup,
                mod_lookup,
                is_random_event=True,
                valid_slots=valid_slot_names,
            )

        # Follow-up sub-event (e.g. R-01a, R-04a, R-32a, R-57a, R-59a)
        followup_obj = None
        m_fu = re.search(r"^\s*-\s+\*\*(R-\d{2}[a-z])「([^」]+)」\*\*(?:（([^）]*)）)?[：:]?\s*(.*?)(?=^-\s+\*\*|\Z)", body, re.M | re.S)
        if m_fu:
            f_id, f_title, f_cond_raw, f_body = m_fu.group(1), sanitize_ai_tone(m_fu.group(2)), m_fu.group(3) or "", m_fu.group(4)
            f_opts = parse_options_block(f_body, flag_lookup, mod_lookup, is_random_event=True, valid_slots=valid_slot_names)
            if f_opts:
                followup_obj = {
                    "id": f_id,
                    "title": f_title[:16],
                    "condition": "k >= 1.5" if "1.5" in f_cond_raw else "true",
                    "options": f_opts,
                }

        # Repeat changes (V-13: >= 1 item)
        rep_raw = sanitize_ai_tone(extract_field_block(body, "重复变化"))
        repeat_changes = []
        if rep_raw:
            for stage_n, prefix_kw in [(2, "第2次"), (3, "第3次")]:
                m_st = re.search(rf"{prefix_kw}(?:（[^）]*）)?[：:]\s*([^。]+)", rep_raw)
                if m_st:
                    desc_s = sanitize_ai_tone(m_st.group(1).strip())
                    effs_s, _ = compile_effects(desc_s, flag_lookup, mod_lookup, is_random_event=True, valid_slots=valid_slot_names)
                    repeat_changes.append({
                        "n": stage_n,
                        "title_prefix": "再次：" if stage_n == 2 else "第三次：",
                        "background_prefix": desc_s,
                        "description": desc_s,
                        "extra_effects": effs_s,
                    })
        if not repeat_changes:
            repeat_changes.append({
                "n": 2,
                "title_prefix": "再次：",
                "background_prefix": rep_raw or f"本届政府任期内再次发生{clean_title}。",
                "description": rep_raw or f"本届政府任期内再次发生{clean_title}。",
                "extra_effects": [{"op": "add", "target": "party_standing", "value": -2.0}],
            })

        # Era variants
        era_var_raw = sanitize_ai_tone(extract_field_block(body, "时代变体"))
        era_variants = []
        if era_var_raw and era_var_raw not in ("无", "无。"):
            lines_or_parts = (
                [re.sub(r"^\s*-\s*", "", ln).strip() for ln in era_var_raw.splitlines() if ln.strip()]
                if "\n" in era_var_raw
                else [p.strip() for p in re.split(r"[；;]", era_var_raw) if p.strip()]
            )
            for part in lines_or_parts:
                part = sanitize_ai_tone(part)
                m_rng = re.search(r"(\d{4})\s*[–-]\s*(\d{4})", part)
                m_after = re.search(r"(\d{4})\s*年(?:以)?(?:后|起)", part)
                m_before = re.search(r"(\d{4})\s*年(?:以)?前", part)
                if m_rng:
                    when_e = f"year >= {m_rng.group(1)} and year <= {m_rng.group(2)}"
                elif m_after:
                    when_e = f"year >= {m_after.group(1)}"
                elif m_before:
                    when_e = f"year <= {m_before.group(1)}"
                else:
                    when_e = "year >= 1977"
                era_variants.append({
                    "when": when_e,
                    "background_suffix": part,
                    "description": part,
                })

        ev_obj: dict = {
            "id": rid,
            "kind": "random",
            "category": category,
            "form": form,
            "magnitude": magnitude,
            "tone": tone,
            "minor": is_minor,
            "title": clean_title[:16],
            "era": era_bounds,
            "prerequisites": prereq_expr,
            "base_prob_month": base_prob_month,
            "cooldown_months": cooldown_months,
            "cap": cap_obj,
            "slots": slots_compiled,
            "variant_slot": variant_slot,
            "scale": scale_obj,
            "variants": variants,
            "background": variants[0]["background"],
            "narrative": variants[0]["narrative"],
            "summary": variants[0]["background"][:38] + "。",
            "repeat_changes": repeat_changes,
            "era_variants": era_variants,
        }
        if form == "choice":
            ev_obj["options"] = options_compiled
        else:
            ev_obj["passive_effects"] = passive_compiled
        if followup_obj:
            ev_obj["followup_choice"] = followup_obj

        events_out.append(ev_obj)

    return {
        "schema_version": 1,
        "era_file": "06_random_events",
        "total_events": len(events_out),
        "events": events_out,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    flag_lookup, mod_lookup = load_registries()
    seen_global_ids: set[str] = set()

    file_mapping = [
        ("01_1948_1955.md", "fixed_1948_1955.yaml", False),
        ("02_1955_1967.md", "fixed_1955_1967.yaml", False),
        ("03_1967_1977.md", "fixed_1967_1977.yaml", False),
        ("04_1977_1992.md", "fixed_1977_1992.yaml", False),
        ("05_1992_2006.md", "fixed_1992_2006.yaml", False),
        ("06_random_events.md", "random_events.yaml", True),
    ]

    total_compiled = 0
    for md_name, yaml_name, is_random in file_mapping:
        md_path = EVENTS_MD_DIR / md_name
        out_path = OUT_DIR / yaml_name
        if is_random:
            doc = compile_random_file(md_path, flag_lookup, mod_lookup, seen_global_ids)
        else:
            doc = compile_fixed_file(md_path, flag_lookup, mod_lookup, seen_global_ids)

        out_path.write_text(
            yaml.dump(doc, Dumper=NoAliasDumper, allow_unicode=True, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        cnt = len(doc["events"])
        total_compiled += cnt
        print(f"Compiled {md_name:20s} -> data/events/{yaml_name:22s} ({cnt} events)")

    print(f"Total compiled events: {total_compiled} (Unique IDs: {len(seen_global_ids)})")


if __name__ == "__main__":
    main()
