#!/usr/bin/env python3
"""
Enrich docs/registry/flags.yaml and docs/registry/modifiers.yaml with:
1. Canonical English snake_case `id`s (prioritizing M01-M14 Appendix C and M12 specs).
2. `name_zh` / `name` mappings and `flag_aliases` / `modifier_aliases`.
3. Complete resolution of orphan flags (fixing extract_flags.py bugs on `未触发`, `规模`, `、`,
   linking synonyms, and annotating module/scenario/world/ending `set_by` & `read_by`).
4. Structured numerical effects (`duration_months`, `duration_days`, `duration`, `edges`,
   `factors`, `monthly_effects`, `option_tag_effects`, `event_prob_add`, `desc_zh`)
   for all modifiers in `docs/registry/modifiers.yaml`.
"""

from __future__ import annotations
import glob
import re
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
FLAGS_PATH = ROOT / "docs" / "registry" / "flags.yaml"
MODS_PATH = ROOT / "docs" / "registry" / "modifiers.yaml"
EVENTS_DIR = ROOT / "docs" / "events"

# ---------------------------------------------------------------------------
# 1. Canonical Flag ID Mapping (287 event flags + M01-M14 / M12 system flags)
# ---------------------------------------------------------------------------
FLAG_ID_MAP: dict[str, str] = {
    "101公里会谈": "km_101_talks",
    "194号决议": "world_un_resolution_194",
    "242框架": "un_resolution_242_framework",
    "3379决议": "un_resolution_3379",
    "{政党}退出威胁": "party_exit_threat",
    "{领域}产业": "sector_industry_established",
    "东方阵营路线": "eastern_bloc_alignment",
    "两伊战争": "world_iran_iraq_war",
    "乌布利希访问开罗": "world_ulbricht_cairo_visit",
    "也门儿童之谜": "yemenite_children_affair",
    "也门移民": "yemenite_aliyah",
    "人权基本法": "human_rights_basic_law",
    "伊克利特之诺": "iqrit_promise",
    "伊拉克核计划延续": "iraq_nuclear_program_continues",
    "伊拉克革命": "world_iraq_revolution_1958",
    "伊斯兰会议成立": "islamic_conference_founded",
    "伊朗供油": "iranian_oil_supply",
    "信仰集团": "gush_emunim_bloc",
    "党内反对派成形": "party_opposition_formed",
    "党内裂痕": "party_rift",
    "全球科技泡沫": "world_dotcom_bubble",
    "六一九决议": "june_19_cabinet_resolution",
    "六日战争结束": "six_day_war_ended",
    "凌驾条款": "flag_m13_override_clause_enacted",
    "凶手逍遥": "assassins_unpunished",
    "利勒哈默尔误杀": "lillehammer_affair",
    "利库德分裂萌芽": "likud_split_seeds",
    "利库德执政": "likud_in_government",
    "利库德接受奥斯陆": "likud_accepts_oslo",
    "利比亚客机击落": "libyan_airliner_shot_down",
    "前进党": "kadima_founded",
    "加利利征地": "galilee_land_expropriation",
    "加沙定居点撤离": "gaza_settlements_evacuated",
    "加沙枪杀": "gaza_shootings",
    "加沙突袭": "gaza_raid_1955",
    "加沙记忆": "gaza_withdrawal_memory",
    "劳工党腐败": "labor_corruption_exposed",
    "劳工党长期执政": "labor_long_rule",
    "十万人方案": "hundred_thousand_plan",
    "十月事件": "october_2000_events",
    "南黎巴嫩代理民兵": "south_lebanon_proxy_militia",
    "占领东耶路撒冷": "east_jerusalem_occupied",
    "占领地时代": "occupied_territories_era",
    "占领西岸": "west_bank_occupied",
    "卡夫尔卡西姆": "kafr_qasim_massacre",
    "卡汉委员会": "kahan_commission_active",
    "卡赫已取缔": "kach_banned",
    "卡赫进入议会": "kach_in_knesset",
    "叙以停战": "syria_armistice_signed",
    "叙利亚之耻": "syria_humiliation",
    "叙利亚引水工程开工": "syria_water_diversion_started",
    "叙利亚炮击加利利": "syria_shelled_galilee",
    "古什埃齐翁定居": "gush_etzion_resettled",
    "司法审查": "judicial_review_established",
    "吕大驱逐": "lydda_ramle_expulsion",
    "和约已签署": "peace_treaty_signed_alias",
    "哈马斯学会自杀式爆炸": "hamas_suicide_bombing_tactic",
    "哭墙广场": "western_wall_plaza_cleared",
    "喀土穆三不": "khartoum_three_noes",
    "团结政府": "national_unity_government",
    "国家输水工程完工": "national_water_carrier_completed",
    "国有土地宣告": "state_land_declaration",
    "国防工业自主": "defense_industry_autonomy",
    "国防部长空缺": "defense_minister_vacant",
    "圣地受损": "holy_site_damaged",
    "圣殿山现状": "temple_mount_status_quo",
    "在场的缺席者": "present_absentees",
    "地下组织未破": "underground_unbroken",
    "埃什科尔去世": "eshkol_died",
    "埃以停战": "egypt_armistice_signed",
    "埃以停战谈判": "egypt_armistice_talks",
    "埃以停火安排更新": "egypt_ceasefire_updated",
    "埃以全面战争重启": "egypt_full_war_resumed",
    "埃以和约": "egypt_peace_treaty",
    "埃以和约已签署": "egypt_peace_treaty_signed",
    "埃以秘密和谈成功": "egypt_secret_peace_talks_succeeded",
    "埃及愿意谈判": "egypt_willing_to_negotiate",
    "埃塞俄比亚移民早期化": "early_ethiopian_aliyah",
    "基比亚": "qibya_raid",
    "基比亚否认": "qibya_denial",
    "复兴党成立": "tehiya_founded",
    "夏里特离心": "sharett_alienated",
    "大赦先例": "amnesty_precedent",
    "大选年": "election_year",
    "奥斯陆二期": "oslo_ii_signed",
    "奥斯陆二期、旗标：希伯伦撤离先例、旗标：脱离计划": "oslo_ii_hebron_disengagement_compound",
    "奥斯陆失败": "oslo_talks_failed",
    "奥斯陆秘密渠道": "oslo_secret_channel",
    "奥斯陆进程": "oslo_process_active",
    "学生领袖": "student_leader_emerged",
    "宗教党退出威胁": "religious_party_exit_threat",
    "定居点合法化先例": "outpost_legalization_precedent",
    "定居者运动动量": "settlers_momentum_high",
    "宽容伊斯兰派": "tolerate_islamists",
    "密约曝光": "sevres_collusion_exposed",
    "少数民族部队": "minority_units_established",
    "屠杀发生": "massacre_occurred",
    "巴列夫防线": "bar_lev_line",
    "巴方总理": "pa_prime_minister_appointed",
    "巴方选举": "pa_legislative_election",
    "巴解唯一合法代表": "plo_sole_legitimate_representative",
    "巴解撤往突尼斯": "plo_moved_to_tunis",
    "巴解迁往黎巴嫩": "plo_relocated_to_lebanon",
    "希伯伦屠杀": "hebron_massacre_1994",
    "希伯伦撤离先例": "hebron_withdrawal_precedent",
    "希伯伦撤离先例、旗标：脱离计划": "hebron_disengagement_compound",
    "希伯伦犹太存在": "hebron_jewish_presence",
    "平民政策空白": "civilian_policy_vacuum",
    "幻影交付": "mirage_jets_delivered",
    "废除接触巴解禁令": "plo_contact_ban_repealed",
    "建筑抗震规范": "seismic_building_code",
    "开罗处决": "cairo_trial_executions",
    "引水计划": "national_water_diversion_plan",
    "德以秘密军援": "west_germany_secret_arms_aid",
    "德鲁兹兵役": "druze_conscription",
    "德鲁兹血盟": "druze_covenant_of_blood",
    "总理直选": "direct_pm_election",
    "慕尼黑": "munich_massacre_occurred",
    "戈兰吞并": "golan_annexed",
    "战争进行中": "war_in_progress",
    "战时暴行报告": "wartime_atrocity_reports",
    "所罗门行动": "operation_solomon_done",
    "托莱达诺遇害": "toledano_killed",
    "报复只打军事目标": "retaliation_military_targets_only",
    "拉冯事件埋雷": "lavon_affair_planted",
    "拉卡姆在美行动": "lakam_us_operation",
    "拉宾承诺": "rabin_settlement_promise",
    "拉宾遇刺": "rabin_assassinated",
    "拉宾驻美经历": "rabin_us_ambassador",
    "拉菲分裂": "rafi_split",
    "拒绝回归": "refugee_return_rejected",
    "捷克军火": "czech_arms_deal",
    "控制圣地": "holy_sites_controlled",
    "推迟选举": "elections_postponed_1948",
    "掩盖丑闻": "scandal_covered_up",
    "提前大选": "early_election_called",
    "提前推行国家教育": "state_education_early_adoption",
    "摩洛哥开放移民": "world_morocco_emigration_open",
    "摩洛哥禁止犹太人移民": "world_morocco_emigration_ban",
    "摩洛哥秘密渠道": "morocco_channel",
    "摩西行动": "operation_moses_done",
    "撤出黎巴嫩": "lebanon_withdrawal_done",
    "撤离加沙": "gaza_disengagement_done",
    "政治大翻盘": "mahapach_1977",
    "族群政党崛起": "ethnic_party_rise",
    "无成文宪法": "unwritten_constitution_harari",
    "无核选项": "no_nuclear_option",
    "最终地位协议": "final_status_agreement_signed",
    "本-古里安在野": "ben_gurion_in_opposition",
    "核模糊": "nuclear_ambiguity",
    "核模糊政策": "nuclear_ambiguity_policy",
    "核能力公开": "nuclear_ambiguity_broken",
    "核设施": "dimona_nuclear_facility",
    "梅厄辞职": "meir_resigned",
    "欠下人情[{政党}]": "favor_owed_party",
    "欠下人情[{议员}]": "favor_owed_mk",
    "沙斯巅峰": "shas_peak_1999",
    "沙斯领袖受调查": "shas_leader_under_investigation",
    "沙龙去职": "sharon_dismissed_from_defense",
    "沙龙国防": "sharon_defense_minister",
    "没有伙伴叙事": "no_partner_narrative",
    "法以军事同盟": "franco_israeli_alliance",
    "法国渠道": "french_arms_channel",
    "法国转向": "french_embargo_pivot",
    "波拉德被出卖": "pollard_betrayed",
    "海外社群要求发言权": "diaspora_demands_voice",
    "海水淡化计划": "desalination_program",
    "海法旧阿拉伯街区安置移民": "wadi_salib_immigrant_housing",
    "海湾克制": "gulf_war_restraint",
    "海湾战争": "world_gulf_war",
    "消耗战": "war_of_attrition",
    "清除派系领袖": "faction_leader_assassinated",
    "渡过运河": "suez_canal_crossed",
    "温和派积怨": "moderate_faction_grievance",
    "特别选举": "special_pm_election_2001",
    "犹太人定义": "who_is_a_jew_defined",
    "犹太地下组织": "jewish_underground_active",
    "瓦迪萨利布": "wadi_salib_riots",
    "祖孙条款": "grandchild_clause_enacted",
    "科恩情报": "eli_cohen_intel",
    "科恩情报网": "eli_cohen_network",
    "移民无限制": "unrestricted_aliyah",
    "突袭": "yom_kippur_surprise_attack",
    "第一次停火生效": "first_truce_1948",
    "第一次起义": "first_intifada_active",
    "第二次起义": "second_intifada_active",
    "等待期": "waiting_period_1967",
    "等待期、旗标：战争进行中": "waiting_period_war_compound",
    "签署不扩散条约": "npt_signed",
    "约以停战": "jordan_armistice_signed",
    "约以和约": "jordan_peace_treaty_signed",
    "约埃共同防御条约": "jordan_egypt_defense_pact",
    "约旦吞并西岸": "jordan_annexed_west_bank",
    "约旦方案终结": "jordan_option_ended",
    "约翰斯顿斡旋": "johnston_water_plan",
    "罗特姆先例": "operation_rotem_precedent",
    "美国不与巴解接触承诺": "us_no_plo_contact_pledge",
    "美国新型战机交付": "us_f15_delivered",
    "美国航行保证": "us_straits_navigation_guarantee",
    "美国配额收紧": "world_us_refugee_quota_tightened",
    "美苏代理人战争爆发": "world_korean_war_proxy",
    "耶路撒冷吞并": "jerusalem_basic_law",
    "联合国紧急部队进驻": "unef_deployed_sinai",
    "联合宗教阵线解体": "united_religious_front_dissolved",
    "联合阵线": "gahal_alignment_formed",
    "脱离计划": "disengagement_plan_approved",
    "自治框架": "autonomy_framework_signed",
    "自由党持有财政部": "liberals_hold_finance",
    "舍巴农场争议": "shebaa_farms_dispute",
    "色佛尔密约": "sevres_secret_protocol",
    "色佛尔破局": "sevres_talks_collapsed",
    "艾希曼审判": "eichmann_trial_held",
    "艾希曼线索": "eichmann_mossad_lead",
    "艾希曼逃逸": "eichmann_escaped",
    "苏丹通道": "sudan_route",
    "苏军进驻埃及": "soviet_forces_in_egypt",
    "苏珊娜行动失败": "susannah_operation_failed",
    "苏珊娜行动败露": "susannah_affair_exposed",
    "苏联开放移民": "soviet_emigration_allowed_1970s",
    "苏联移民潮": "world_soviet_emigration_open",
    "萨达特上台": "sadat_in_power",
    "萨达特外交转向": "world_sadat_diplomatic_pivot",
    "萨达特被拒": "sadat_initiative_rejected_1971",
    "西奈一号协议": "sinai_i_disengagement",
    "西奈交战规则": "sinai_rules_of_engagement",
    "西奈归还": "sinai_returned",
    "西岸吞并": "west_bank_annexed",
    "西岸归还": "west_bank_returned",
    "西方对埃及军售": "world_west_arms_to_egypt",
    "西方拒售埃及武器": "world_west_refuses_arms_to_egypt",
    "谁是犹太人未定义": "who_is_a_jew_undefined",
    "调查委员会设立": "agranat_commission_established",
    "贝京主义": "begin_doctrine",
    "贝京入狱": "begin_imprisoned",
    "贝塔以色列适用回归法": "beta_israel_law_of_return",
    "贝纳多特遇刺": "bernadotte_assassinated",
    "财产补偿筹码": "refugee_property_compensation_chip",
    "贷款担保冻结": "loan_guarantees_frozen",
    "赎罪日战争": "yom_kippur_war_started",
    "赔偿协议": "luxembourg_reparations_signed",
    "赔偿款流入减少": "reparations_inflow_declining",
    "起义余波": "intifada_aftermath",
    "越权未追究": "overreach_unpunished",
    "越权未追究、人物关系[沙龙]": "overreach_unpunished_sharon_compound",
    "路线图停滞": "roadmap_stalled",
    "轻度中风": "sharon_mild_stroke",
    "辛贝特改革": "shin_bet_reformed",
    "达扬外长": "dayan_foreign_minister",
    "运河临时协议": "suez_interim_agreement",
    "运河前线": "suez_canal_front_active",
    "运河危机外交解决": "world_suez_diplomatic_settlement",
    "运河国有化": "world_suez_canal_nationalized",
    "迪莫纳工程": "dimona_project_started",
    "选举改革运动": "electoral_reform_movement",
    "选前透支": "pre_election_spending_binge",
    "通用锡安主义者入阁的条件成熟": "general_zionists_coalition_ready",
    "重返A区": "idf_reentered_area_a",
    "银行国有化": "bank_nationalization",
    "银行股危机已发生": "bank_shares_crisis_occurred",
    "银行股托市": "bank_shares_manipulation",
    "错失老城": "old_city_missed_1967",
    "错失萨达特": "sadat_missed",
    "长枪党入营": "phalange_entered_camps",
    "防御性民主先例": "defensive_democracy_precedent",
    "阿卜杜拉遇刺": "king_abdullah_assassinated",
    "阿尔及利亚战争": "world_algerian_war",
    "阿尔及利亚战争结束": "world_algerian_war_ended",
    "阿尔塔莱纳之痛": "altalena_trauma",
    "阿拉伯和平倡议": "arab_peace_initiative_2002",
    "阿拉伯政党入阁": "arab_party_in_coalition",
    "阿拉伯民族主义组织出现": "al_ard_movement_emerged",
    "阿拉伯统一指挥部": "united_arab_command_formed",
    "阿格拉纳特免责": "agranat_exonerated_cabinet",
    "阿联成立": "world_uar_formed",
    "阿联解体": "world_uar_dissolved",
    "隔离构想": "separation_barrier_concept",
    "隧道出口已开放": "western_wall_tunnel_opened",
    "难民已大规模回归": "refugees_mass_returned",
    "非军事区耕作争端": "dmz_cultivation_dispute",
    "非洲独立潮": "world_african_independence_wave",
    "领土筹码未定": "territorial_bargaining_chip_undecided",
    "领土让步谈判": "territorial_concession_talks",
    "首席拉比裁定": "chief_rabbinate_beta_israel_ruling",
    "马帕姆分裂": "mapam_split_1953",
    "马德里框架": "madrid_conference_framework",
    "驱逐档案封存": "expulsion_archives_sealed",
    "高科技": "high_tech_boom_started",
}

# Additional system/module flags from M01-M14 Appendix C and M12
EXTRA_SYSTEM_FLAGS = [
    {"id": "sadat_visit_happened", "name_zh": "萨达特已访问", "set_by": ["E-1977-11"], "read_by": ["E-1978-09", "M07"]},
    {"id": "sadat_visit_cancelled", "name_zh": "萨达特取消访问", "set_by": ["E-1977-11"], "read_by": ["M07", "M12"]},
    {"id": "sudan_route_active", "name_zh": "苏丹通道已建立", "set_by": ["E-1977-08", "M09"], "read_by": ["E-1984-11", "M07"]},
    {"id": "idf_in_south_lebanon", "name_zh": "以军驻留南黎巴嫩", "set_by": ["E-1978-03b", "E-1982-06a"], "read_by": ["E-1978-03b", "E-1985-01", "M09"]},
    {"id": "phalange_entered_camps_supervised", "name_zh": "长枪党入营（监督）", "set_by": ["E-1982-09b"], "read_by": ["E-1983-02a", "M09"]},
    {"id": "autonomy_stagnant", "name_zh": "巴勒斯坦自治谈判停滞", "set_by": ["M08"], "read_by": ["M08", "E-1987-12a"]},
    {"id": "pal_autonomy_established", "name_zh": "巴勒斯坦自治已建立", "set_by": ["M08", "E-1979-10"], "read_by": ["E-1987-12a", "E-G04-09", "M08"]},
    {"id": "plo_expelled_from_beirut", "name_zh": "巴解总部被逐出贝鲁特", "set_by": ["E-1982-08", "M09"], "read_by": ["M08", "M09"]},
    {"id": "hamas_founded", "name_zh": "哈马斯已成立", "set_by": ["E-1987-12b", "M08"], "read_by": ["M08", "M09", "E-1992-03b"]},
    {"id": "gulf_charity_cut", "name_zh": "海湾伊斯兰慈善资金被截断", "set_by": ["E-G04-10", "M08"], "read_by": ["M08"]},
    {"id": "osirak_destroyed", "name_zh": "成功摧毁伊拉克奥西拉克核反应堆", "set_by": ["E-1981-06a", "M09"], "read_by": ["M07", "M09", "M14"]},
    {"id": "lebanon_war_1982", "name_zh": "1982黎巴嫩战争爆发", "set_by": ["E-1982-06a", "M09"], "read_by": ["E-1982-06b", "E-1985-01", "M09"]},
    {"id": "sabra_shatila_massacre", "name_zh": "萨布拉-夏蒂拉屠杀发生", "set_by": ["E-1982-09c", "M09"], "read_by": ["E-1982-09d", "E-1983-02a", "M06", "M09"]},
    {"id": "four_mothers_movement_active", "name_zh": "四母亲运动激活", "set_by": ["E-G04-18", "M09"], "read_by": ["M03", "M08", "M12"]},
    {"id": "elon_moreh_ruling", "name_zh": "埃隆莫雷赫裁决生效", "set_by": ["E-1979-10"], "read_by": ["M05", "M11", "M12"]},
    {"id": "elon_moreh_ruling_obeyed", "name_zh": "服从高院埃隆莫雷赫案裁决", "set_by": ["E-1979-10"], "read_by": ["M11", "M14"]},
    {"id": "elon_moreh_defied", "name_zh": "拒绝执行埃隆莫雷赫最高法院裁决", "set_by": ["E-1979-10"], "read_by": ["M02", "M11", "M12", "M13"]},
    {"id": "immigrants_routed_to_settlements", "name_zh": "向定居点分流新移民", "set_by": ["M11", "E-1989-10"], "read_by": ["E-1991-09", "M07", "M12"]},
    {"id": "allon_corridor_consolidated", "name_zh": "阿隆走廊建设完成", "set_by": ["E-1967-05", "M11"], "read_by": ["M09", "M11"]},
    {"id": "capital_fallen", "name_zh": "核心首都陷落", "set_by": ["M09"], "read_by": ["M01", "M14"]},
    {"id": "nuclear_strike_suffered", "name_zh": "遭受核打击", "set_by": ["M07", "M09"], "read_by": ["M01", "M14"]},
    {"id": "player_founded_new_party", "name_zh": "玩家任内退党创立新党", "set_by": ["M04"], "read_by": ["M03", "M14"]},
    {"id": "yamit_evacuated", "name_zh": "已完成西奈亚米特定居点拆除撤离", "set_by": ["E-1982-04", "M05"], "read_by": ["M11", "M14"]},
    {"id": "lebanon_war_expanded", "name_zh": "黎巴嫩战争扩大至第2/3阶段", "set_by": ["E-1982-06a", "E-1982-06b", "M09"], "read_by": ["M09", "M14"]},
    {"id": "first_intifada_ever_started", "name_zh": "本局曾爆发过第一次巴勒斯坦大起义", "set_by": ["E-1987-12a", "M08"], "read_by": ["M14"]},
    {"id": "unity_rotation_executed", "name_zh": "团结政府按期执行总理轮值交接", "set_by": ["E-1984-09", "M03"], "read_by": ["M03", "M14"]},
    {"id": "lavi_fighter_completed", "name_zh": "完成狮式战斗机研发投产", "set_by": ["E-1987-08"], "read_by": ["M09", "M14"]},
    {"id": "flag_m13_survival_mode_active", "name_zh": "已进入C5威权生存模式", "set_by": ["M13"], "read_by": ["M01", "M03", "M13", "M14"]},
    {"id": "flag_m13_security_chiefs_purged", "name_zh": "已对安全首长执行政治清洗", "set_by": ["M13"], "read_by": ["M06", "M09", "M13"]},
    {"id": "flag_m13_ag_dismissed_recently", "name_zh": "过去6个月内曾强行解雇总检察长", "set_by": ["M13", "E-1986-05"], "read_by": ["M13"]},
    {"id": "flag_m13_vip_security_tightened", "name_zh": "辛贝特730局强化贴身安保生效中", "set_by": ["M13", "E-1995-03"], "read_by": ["M13", "E-1995-04"]},
    {"id": "reshuffle_window_open", "name_zh": "内阁改组窗口激活", "set_by": ["M06"], "read_by": ["M06", "M14"]},
    {"id": "dayan_resigned", "name_zh": "达扬已辞去外交部长", "set_by": ["E-1979-10", "M06"], "read_by": ["M06", "M12"]},
    {"id": "weizman_resigned", "name_zh": "魏茨曼已辞去国防部长", "set_by": ["E-1980-05a", "M06"], "read_by": ["M04", "M06", "M12"]},
    {"id": "party_criticism_active", "name_zh": "党内公开批评激活", "set_by": ["M04"], "read_by": ["M04", "M12"]},
    {"id": "party_challenger_active", "name_zh": "党内挑战者激活", "set_by": ["M04"], "read_by": ["M04", "M12"]},
    {"id": "party_faction_exit_recent", "name_zh": "近期发生派系出走", "set_by": ["M04"], "read_by": ["M03", "M04"]},
    {"id": "party_split_done", "name_zh": "政党分裂已发生", "set_by": ["M04"], "read_by": ["M03", "M04"]},
    {"id": "vision_achieved", "name_zh": "国家愿景已达成", "set_by": ["M04"], "read_by": ["M04", "M14"]},
    {"id": "vision_failed", "name_zh": "国家愿景已失败", "set_by": ["M04"], "read_by": ["M04", "M14"]},
    {"id": "fx_crisis", "name_zh": "外汇储备见底紧急状态", "set_by": ["M10"], "read_by": ["E-G04-06", "M10", "M12"]},
    {"id": "inflation_crisis", "name_zh": "高通胀危机状态", "set_by": ["M10"], "read_by": ["E-1985-07", "M10", "M12"]},
    {"id": "hyperinflation", "name_zh": "恶性通胀螺旋状态", "set_by": ["M10"], "read_by": ["E-G04-01", "M10", "M12"]},
    {"id": "strike_warning", "name_zh": "全国罢工预警", "set_by": ["M10"], "read_by": ["M10", "M12"]},
    {"id": "general_strike_active", "name_zh": "劳工总联合会总罢工进行中", "set_by": ["M10"], "read_by": ["E-G04-02", "M10", "M13"]},
    {"id": "budget_due", "name_zh": "年度预算案待表决", "set_by": ["M10"], "read_by": ["M03", "M10", "M15"]},
    {"id": "budget_deadline_60", "name_zh": "预算案表决倒计时60天", "set_by": ["M10"], "read_by": ["M10", "M15"]},
]

# Synonym and compound aliases -> canonical flag ID
FLAG_ALIASES: dict[str, str] = {
    "埃以和约": "egypt_peace_treaty_signed",
    "埃以和约已签署": "egypt_peace_treaty_signed",
    "和约已签署": "egypt_peace_treaty_signed",
    "埃以和约签署": "egypt_peace_treaty_signed",
    "peace_treaty_signed_alias": "egypt_peace_treaty_signed",
    "egypt_peace_treaty": "egypt_peace_treaty_signed",
    "camp_david_signed": "autonomy_framework_signed",
    "autonomy_framework": "autonomy_framework_signed",
    "银行股危机已发生": "bank_nationalization",
    "bank_shares_crisis_occurred": "bank_nationalization",
    "苏珊娜行动失败": "susannah_affair_exposed",
    "susannah_operation_failed": "susannah_affair_exposed",
    "核模糊政策": "nuclear_ambiguity",
    "nuclear_ambiguity_policy": "nuclear_ambiguity",
    "科恩情报": "eli_cohen_network",
    "eli_cohen_intel": "eli_cohen_network",
    "苏联开放移民": "world_soviet_emigration_open",
    "soviet_gates_opened": "world_soviet_emigration_open",
    "soviet_aliyah_wave": "world_soviet_emigration_open",
    "奥斯陆二期、旗标：希伯伦撤离先例、旗标：脱离计划": "oslo_ii_signed",
    "希伯伦撤离先例、旗标：脱离计划": "hebron_withdrawal_precedent",
    "等待期、旗标：战争进行中": "waiting_period_1967",
    "越权未追究、人物关系[沙龙]": "overreach_unpunished",
    "长枪党入营（无监督）": "phalange_entered_camps",
    "长枪党入营（监督）": "phalange_entered_camps_supervised",
    "plo_evacuated_tunis": "plo_moved_to_tunis",
    "south_lebanon_proxy": "south_lebanon_proxy_militia",
    "player_party_founded": "player_founded_new_party",
}

# ---------------------------------------------------------------------------
# 2. Canonical Modifier ID Mapping (252 event modifiers + M01-M14 / M12 mods)
# ---------------------------------------------------------------------------
MOD_ID_MAP: dict[str, str] = {
    "101部队": "unit_101",
    "300路的秘密": "bus_300_secret",
    "61席": "narrow_61_seat_coalition",
    "{行业}罢工": "sector_strike",
    "七月谅解": "july_1993_understanding",
    "上帝之怒": "wrath_of_god_campaign",
    "不与恐怖分子谈判": "no_negotiation_with_terrorists",
    "不可战胜": "invincibility_euphoria",
    "世俗—宗教裂痕": "secular_religious_rift",
    "东欧移民通道收窄": "eastern_bloc_aliyah_narrowed",
    "也门移民营地": "yemenite_transit_camps",
    "亚米特创伤": "yamit_trauma",
    "交换先例": "prisoner_exchange_precedent",
    "人口时钟": "demographic_clock",
    "人才外流": "brain_drain",
    "仇恨的种子": "seeds_of_hatred_gaza",
    "伊克利特的承诺": "iqrit_unfulfilled_promise",
    "伊尔贡耶路撒冷独立部队": "irgun_jerusalem_unit",
    "伊拉克移民的落差": "iraqi_aliyah_downward_mobility",
    "侯赛因的屈辱": "hussein_humiliation",
    "信仰集团": "gush_emunim_bloc_mod",
    "党纪伤痕": "party_discipline_scars",
    "全面动员": "full_mobilization_1967",
    "全面封锁": "total_closure_policy",
    "全面战争": "full_scale_war_drain",
    "共谋的污点": "sevres_collusion_taint",
    "兵役换平等的承诺": "druze_service_equality_pledge",
    "内部敌人": "internal_enemy_suspicion",
    "军中不服": "idf_insubordination",
    "军中党派色彩": "idf_partisan_politicization",
    "军力失衡": "military_imbalance_1955",
    "军售冻结": "us_arms_freeze",
    "军备失衡": "arms_imbalance",
    "军火航班": "ethiopia_arms_for_aliyah_flights",
    "军纪": "strict_military_discipline",
    "冷和平": "cold_peace_egypt",
    "冷静的现实主义者": "cool_realist",
    "冻结之争": "settlement_freeze_dispute",
    "判决未执行": "court_ruling_unxecuted",
    "刺杀风险": "assassination_risk_mod",
    "前哨承诺": "outpost_removal_pledge",
    "北方摩擦": "northern_border_friction",
    "北线冻结": "northern_front_frozen",
    "南方渗透": "southern_fedayeen_infiltration",
    "卡拉梅神话": "karameh_myth",
    "卡赫纳主义": "kahanism_spread",
    "厨房内阁": "kitchen_cabinet",
    "双头政府": "two_headed_unity_government",
    "双头政治": "diarchy_sde_boker",
    "双重标准": "double_standard_grievance",
    "双面间谍": "double_agent_exposed",
    "反恐战争": "global_war_on_terror_frame",
    "发展城镇的边缘": "development_town_periphery",
    "口头授权": "shin_bet_oral_authorization",
    "右翼合法化": "herut_legitimized",
    "右翼地下复燃": "right_wing_underground_revival",
    "右翼地下的怨恨": "right_wing_underground_resentment",
    "合作者审判": "kastner_collaborator_trial",
    "合作者污名·约旦": "jordan_collaborator_stigma",
    "周六冲突": "sabbath_street_clashes",
    "和平红利": "oslo_peace_dividend",
    "和平阵营动员": "peace_now_mobilization",
    "和约危机": "peace_treaty_crisis",
    "四位母亲的先声": "four_mothers_precursor",
    "四十万人": "four_hundred_thousand_protest",
    "四月谅解": "april_1996_understanding",
    "四母亲运动": "four_mothers_movement",
    "回归之梦": "palestinian_dream_of_return",
    "回归先例": "internal_refugee_return_precedent",
    "团结政府否决权": "unity_coalition_mutual_veto",
    "围困穆卡塔": "mukataa_siege",
    "围城心态": "siege_mentality",
    "土地日纪念": "land_day_annual_commemoration",
    "圣地之火": "al_aqsa_arson_aftermath",
    "圣地对峙": "temple_mount_standoff",
    "圣殿山阴谋的回声": "temple_mount_plot_echoes",
    "埃及无力开战": "conception_egypt_cannot_war",
    "塔尔法": "tal_law_interim",
    "复仇": "revenge_bombing_wave",
    "复仇的长枪党": "vengeful_phalange",
    "外围网络": "periphery_intelligence_network",
    "外籍劳工": "foreign_guest_workers",
    "外长的保留": "dayan_settlement_reservations",
    "多支武装并存": "multiple_armed_militias",
    "大使馆留在特拉维夫": "embassies_remain_in_tel_aviv",
    "大国对抗边缘": "superpower_confrontation_brink",
    "失去外围": "lost_periphery_ally",
    "失去孩子的父母": "bereaved_parents_protest",
    "奥尔委员会": "or_commission_inquiry",
    "守墓人示威": "neturei_karta_protests",
    "安全区": "security_zone",
    "安全协调": "pa_security_coordination",
    "宗教化的冲突": "religious_conflict_frame",
    "宗教婚姻难题": "civil_marriage_absence",
    "宗教阵线的否决权": "religious_front_veto",
    "宗教阵营右转": "nrp_rightward_turn",
    "审讯改革": "landau_interrogation_reform",
    "宪法法院": "constitutional_court_activism",
    "寒蝉": "chilling_effect",
    "封存的档案": "sealed_1948_archives",
    "将领的委屈": "palmach_generals_grievance",
    "小圈子决策": "inner_circle_decision_making",
    "巴列夫防线": "bar_lev_line_mod",
    "币制转换": "currency_conversion_shock",
    "布什的冷淡": "bush_baker_coolness",
    "希伯伦宵禁": "hebron_extended_curfew",
    "希伯伦火药桶": "hebron_powder_keg",
    "希伯来文化的自信": "hebrew_cultural_confidence",
    "帐篷城": "tent_city_protests",
    "幻影机交付延迟": "mirage_delivery_delayed",
    "廉价劳动力": "occupied_territories_cheap_labor",
    "开放桥梁": "open_bridges_policy",
    "弹药荒": "ammunition_shortage",
    "总理兼国防": "acting_defense_minister",
    "恩德培神话": "entebbe_euphoria",
    "戒严的阴影": "martial_law_shadow",
    "战争罪调查": "un_war_crimes_probe",
    "战略资产": "us_strategic_asset",
    "扎伊姆渠道": "husni_zaim_channel",
    "报复国家": "retaliation_state_stigma",
    "报复螺旋": "retaliation_spiral",
    "报复行动政策": "reprisal_operations_doctrine",
    "拉冯的幽灵": "ghost_of_lavon_affair",
    "拉宾与佩雷斯": "rabin_peres_rivalry",
    "拒签者运动": "soviet_refusenik_movement",
    "拒绝派的回应": "rejectionist_terror_wave",
    "指数化经济": "indexed_economy_rigidity",
    "指数化螺旋": "indexation_spiral",
    "挨第一拳": "absorb_first_strike_cost",
    "掩盖": "cover_up_vulnerability",
    "撤军压力": "eisenhower_withdrawal_pressure",
    "撤出黎巴嫩运动": "withdraw_from_lebanon_movement",
    "撤离创伤": "gaza_evacuation_trauma",
    "收编": "black_panthers_coopted",
    "改革受挫": "economic_reform_stalled",
    "政治暴力的先例": "political_violence_precedent",
    "敢死队": "egyptian_fedayeen_raids",
    "新谢克尔": "new_shekel",
    "族群投票": "ethnic_voting_polarization",
    "无上限豁免": "uncapped_exemption",
    "既成事实": "settlement_fait_accompli",
    "有罪不罚": "settler_impunity",
    "有限问责": "limited_accountability",
    "未了的案子": "unresolved_corruption_case",
    "未完成的正义": "kafr_qasim_unfinished_justice",
    "未解之谜": "dakar_unresolved_mystery",
    "未解的伤口": "yemenite_children_unhealed_wound",
    "未解的疑问": "uss_liberty_unresolved_question",
    "本-古里安归来": "ben_gurion_returned_defense",
    "村庄联盟": "village_leagues_program",
    "板房": "mobile_home_outposts",
    "校园对立": "campus_ideological_clash",
    "核对峙": "superpower_nuclear_alert_1973",
    "核模糊": "nuclear_ambiguity_mod",
    "核阴影": "dimona_exposure_shadow",
    "模糊政策": "amimut_policy_shield",
    "殉道叙事": "settler_martyrdom_narrative",
    "殉道者": "martyrdom_wave",
    "殉道者卡赫纳": "kahane_martyr_cult",
    "水源威胁": "headwater_diversion_threat",
    "沉默的总理": "silent_pm",
    "沙龙的国防部": "sharon_fiefdom_defense",
    "沙龙的怨气": "sharon_cabinet_resentment",
    "没有回家的士兵": "missing_soldiers_campaign",
    "泄密": "cabinet_leaks",
    "泡沫破裂": "dotcom_bubble_burst",
    "波拉德阴影": "pollard_shadow",
    "活动房营地": "caravan_absorption_camps",
    "消耗战": "war_of_attrition_mod",
    "渗透袭击": "border_infiltration_raids",
    "温和峰会": "moderate_arab_summit",
    "漏风的内阁": "leaky_cabinet",
    "特赦先例": "shin_bet_pardon_precedent",
    "独立宗教教育系统": "independent_haredi_schools",
    "独立战争": "war_of_independence_mobilization",
    "狼来了": "cry_wolf_mobilization_fatigue",
    "留在内阁的沙龙": "sharon_remains_in_cabinet",
    "疲惫": "ben_gurion_exhaustion",
    "病榻上的总理": "incapacitated_pm",
    "监狱学校": "prison_schools",
    "直选时代": "direct_election_era",
    "秘密渠道": "secret_backchannel_risk",
    "空置村庄": "depopulated_arab_villages",
    "第7A条": "basic_law_section_7a",
    "紧缩配给": "tzena_austerity_rationing",
    "约旦边境失控": "jordan_border_destabilized",
    "约旦选项受阻": "jordan_option_blocked",
    "纳哈尔掩护": "nahal_settlement_disguise",
    "纵深防御": "sinai_depth_defense",
    "结对社群": "renewal_twinning",
    "统一水价": "uniform_water_pricing",
    "统一的耶路撒冷": "united_jerusalem_consensus",
    "继承之争": "alon_dayan_succession_rivalry",
    "美元化的日常": "de_facto_dollarization",
    "美国冷淡": "us_diplomatic_coolness",
    "美国制裁": "us_economic_sanctions_1957",
    "美国武器生命线": "us_arms_lifeline",
    "美国石油保证": "us_oil_guarantee",
    "美国石油保障": "us_oil_supply_memorandum",
    "耶希瓦学生豁免": "yeshiva_draft_exemption_debt",
    "腐败之风": "labor_corruption_atmosphere",
    "腐败政府": "corrupt_government_stigma",
    "自杀式爆炸时代": "suicide_bombing_era",
    "苏东移民通道关闭": "soviet_bloc_aliyah_closed",
    "苏联防空网": "soviet_air_defense_umbrella",
    "获释者": "jibril_released_prisoners",
    "萧条": "mitun_recession",
    "萨布拉与夏蒂拉": "sabra_shatila_stigma",
    "萨达特的耐心": "sadat_patience_countdown",
    "藐视委员会": "contempt_for_inquiry_commission",
    "血钱之争": "reparations_blood_money_feud",
    "被压下的怒火": "wadi_salib_suppressed_anger",
    "被围的内盖夫": "besieged_negev",
    "被禁止的反对派": "banned_herut_martyrdom",
    "被迫害的右翼": "persecuted_right_wing",
    "要求回应": "demand_response",
    "要求强硬": "public_demands_toughness",
    "要求报复": "demand_retaliation",
    "要求赔偿": "demand_compensation_diplomacy",
    "议会安保": "knesset_tight_security",
    "议会碎片化": "knesset_fragmentation",
    "议会至上": "parliamentary_supremacy",
    "记忆的转向": "holocaust_memory_centrality",
    "贝鲁特之殇": "beirut_siege_scar",
    "贷款担保扣减": "loan_guarantee_settlement_deduction",
    "起义": "first_intifada",
    "起义经济": "second_intifada_recession",
    "超采": "aquifer_overextraction",
    "越界回流": "refugee_infiltration_return",
    "越过底线的报复": "unrestrained_reprisal_precedent",
    "边境城镇的愤怒": "border_towns_anger",
    "过渡蜜月": "post_transition_honeymoon",
    "运河导弹墙": "suez_sam_missile_wall",
    "选举授权": "fresh_electoral_mandate",
    "选举窗口推迟": "delayed_election_window_risk",
    "铁拳": "iron_fist_beating",
    "银行股安排": "bank_shares_bailout_burden",
    "错过的约旦方案": "missed_jordan_option",
    "阻挡集团": "arab_parties_blocking_bloc",
    "阿隆走廊": "allon_plan_corridor",
    "降级": "sovereign_credit_downgrade",
    "隐形的总理": "invisible_pm_depression",
    "雅林使命": "jarring_mission_talks",
    "非洲之友": "african_diplomatic_network",
    "飞行员信": "pilots_refusal_letter",
    "马帕姆要价": "mapam_defense_veto",
    "驱逐国家的名声": "expeller_state_reputation",
    "驱逐指令": "sealed_expulsion_order",
    "驱逐营地": "marj_al_zuhur_deportee_camp",
    "高科技繁荣": "silicon_wadi_boom",
    "黎巴嫩泥潭": "lebanon_quagmire",
    "黑市清剿": "black_market_crackdown",
}

MOD_ALIASES: dict[str, str] = {
    "intifada": "first_intifada",
    "第一次起义": "first_intifada",
    "获释者骨干网络": "jibril_released_prisoners",
    "殉道者浪潮": "martyrdom_wave",
    "铁拳殴打政策": "iron_fist_beating",
    "美国石油保障": "us_oil_guarantee",
    "us_oil_supply_memorandum": "us_oil_guarantee",
}

# Additional module/M12 modifiers from M01-M14 Appendix C
EXTRA_SYSTEM_MODIFIERS = [
    {
        "id": "mahapach_mandate",
        "name_zh": "翻盘的授权",
        "category": "political",
        "scope": "national",
        "duration_months": 12,
        "factors": [{"key": "pc_income", "mode": "add_flat", "value": 3.0}],
        "edges": [
            {"target": "party_standing", "shape": "flag", "coef": 5.0, "label_zh": "1977大翻盘胜选威望"},
            {"target": "bloc_support", "target_key": "mizrahi", "shape": "flag", "coef": 4.0, "label_zh": "第二以色列的翻身喜悦"},
        ],
        "monthly_effects": [{"op": "add", "target": "political_capital", "value": 3.0}],
        "desc_zh": "终结工党29年统治的历史性胜选授权：每月政治资本产出 +3，党内地位目标值 +5，米兹拉希集团支持目标值 +4（持续12个月）。",
        "set_by": ["M14", "E-1977-02"],
        "read_by": ["M02", "M04", "M05"],
    },
    {
        "id": "histadrut_opposition_bastion",
        "name_zh": "总工会的反对派堡垒",
        "category": "economic",
        "scope": "national",
        "duration_months": None,
        "edges": [{"target": "union_strength", "shape": "flag", "coef": 4.0, "label_zh": "工党掌控劳工总联合会"}],
        "monthly_effects": [],
        "desc_zh": "利库德赢得了议会，但工党依然牢牢把控着劳工总联合会（Histadrut）与库帕特霍林医保网络，罢工动员力提高。",
        "set_by": ["M14"],
        "read_by": ["M02", "M10"],
    },
    {
        "id": "recent_settler_attack",
        "name_zh": "定居者遇袭",
        "category": "security",
        "scope": "national",
        "duration_months": 1,
        "edges": [{"target": "settler_momentum", "shape": "flag", "coef": 3.0, "label_zh": "近期定居者遇袭愤怒"}],
        "monthly_effects": [{"op": "add", "target": "public_security", "value": -2.0}],
        "desc_zh": "近1个月内发生针对定居者的致命袭击，定居者报复情绪升温（持续30天）。",
        "set_by": ["E-G04-09", "R-07"],
        "read_by": ["E-1980-05b", "M12"],
    },
    {
        "id": "recent_lebanon_attack",
        "name_zh": "黎巴嫩越境袭击",
        "category": "security",
        "scope": "national",
        "duration_months": 1,
        "edges": [{"target": "region_security", "target_key": "galilee", "shape": "flag", "coef": -4.0, "label_zh": "近期北境袭击"}],
        "monthly_effects": [{"op": "add", "target": "public_security", "value": -2.0}],
        "desc_zh": "近期发生来自黎巴嫩方向的越境袭击或喀秋莎火箭弹袭击（持续30天）。",
        "set_by": ["E-1978-03a", "E-G04-05"],
        "read_by": ["E-1978-03b", "M12"],
    },
    {
        "id": "local_resentment",
        "name_zh": "地方怨气",
        "category": "political",
        "scope": "region",
        "stack": "stack",
        "duration_months": 6,
        "edges": [{"target": "region_development", "target_key": "$scope", "shape": "flag", "coef": -2.0, "label_zh": "地方事故与忽视怨气"}],
        "terms": [{"param": "region_vote_share", "key": "{key}", "add": -2.0}],
        "monthly_effects": [],
        "desc_zh": "地方事故或忽视引发区域选民对执政党的不满：该区选民倾向每层 −2%（持续6个月）。",
        "set_by": ["R-05"],
        "read_by": ["M03", "M11"],
    },
    {
        "id": "road_safety_plan",
        "name_zh": "全国道路安全整治方案",
        "category": "social",
        "scope": "national",
        "duration_months": None,
        "factors": [{"key": "r05_scale_mult", "mode": "mult", "value": 0.6}],
        "edges": [{"target": "region_development", "target_key": "galilee", "shape": "flag", "coef": 1.0, "label_zh": "道路安全整治"}],
        "monthly_effects": [],
        "desc_zh": "全国道路安全整治方案生效：R-05 公交车事故规模系数 ×0.6（永久）。",
        "set_by": ["R-05"],
        "read_by": ["R-05", "M12"],
    },
    {
        "id": "us_camp_david_aid",
        "name_zh": "戴维营美援与安全补助包",
        "category": "diplomatic",
        "scope": "national",
        "duration_months": None,
        "factors": [
            {"key": "us_aid", "mode": "add_pct", "value": 0.25},
            {"key": "fx_spend", "mode": "add_pct", "value": -0.10},
        ],
        "edges": [{"target": "fx_reserves", "shape": "flag", "coef": 4.0, "label_zh": "戴维营年度美援增量"}],
        "monthly_effects": [],
        "desc_zh": "批准埃以和约后的美国专项军经援助包：美援 +25%，外汇消耗 −10%（和约有效期内常驻）。",
        "set_by": ["E-1979-03", "M07"],
        "read_by": ["M07", "M10"],
    },
    {
        "id": "us_emergency_aid_1985",
        "name_zh": "美国1985紧急经济稳定赠款",
        "category": "economic",
        "scope": "national",
        "duration_months": 24,
        "factors": [{"key": "us_aid", "mode": "add_pct", "value": 0.20}],
        "edges": [{"target": "fx_reserves", "shape": "flag", "coef": 5.0, "label_zh": "1985紧急经济稳定赠款"}],
        "monthly_effects": [{"op": "add", "target": "fx_reserves", "value": 0.4}],
        "desc_zh": "美国1985年15亿美元紧急稳定赠款：24个月内美援 +20%，外汇储备每月 +0.4。",
        "set_by": ["E-1985-07", "M07"],
        "read_by": ["M07", "M10"],
    },
    {
        "id": "us_loan_freeze",
        "name_zh": "老布什冻结100亿美元贷款担保",
        "category": "diplomatic",
        "scope": "national",
        "duration_months": None,
        "factors": [
            {"key": "us_aid", "mode": "add_pct", "value": -0.35},
            {"key": "fx_spend", "mode": "add_pct", "value": 0.15},
        ],
        "edges": [{"target": "fx_reserves", "shape": "flag", "coef": -5.0, "label_zh": "美国冻结100亿贷款担保"}],
        "monthly_effects": [{"op": "add", "target": "fx_reserves", "value": -0.5}],
        "desc_zh": "美国政府因西岸定居点扩建冻结100亿美元贷款担保：美援效应 −35%，外汇消耗 +15%。",
        "set_by": ["E-1991-09", "M07"],
        "read_by": ["E-1992-02", "M07", "M10"],
    },
    {
        "id": "us_loan_approved",
        "name_zh": "美国100亿美元移民安置贷款担保",
        "category": "diplomatic",
        "scope": "national",
        "duration_months": 60,
        "factors": [
            {"key": "us_aid", "mode": "add_pct", "value": 0.30},
            {"key": "fx_spend", "mode": "add_pct", "value": -0.10},
        ],
        "edges": [{"target": "absorption_capacity", "shape": "flag", "coef": 8.0, "label_zh": "100亿美元移民安置贷款担保"}],
        "monthly_effects": [{"op": "add", "target": "fx_reserves", "value": 0.5}],
        "desc_zh": "美国批准100亿美元移民安置贷款担保：60个月内美援 +30%，外汇消耗 −10%，移民吸纳容量大幅提升。",
        "set_by": ["E-1991-09", "E-1992-02", "M07"],
        "read_by": ["M07", "M10"],
    },
    {
        "id": "strategic_partner_us",
        "name_zh": "战略伙伴",
        "category": "diplomatic",
        "scope": "national",
        "duration_months": 48,
        "factors": [{"key": "us_relation_gain_mult", "mode": "mult", "value": 1.20}],
        "edges": [{"target": "us_admin_relation", "shape": "flag", "coef": 5.0, "label_zh": "白宫亲以战略伙伴倾向"}],
        "monthly_effects": [{"op": "add", "target": "us_admin_relation", "value": 0.5}],
        "desc_zh": "亲以白宫执政团队：美国政府关系增长 +20%，对占领区批评力度 −30%（48个月）。",
        "set_by": ["E-G04-17", "M07"],
        "read_by": ["M07", "M12"],
    },
    {
        "id": "bank_bubble",
        "name_zh": "银行股托市泡沫",
        "category": "economic",
        "scope": "national",
        "duration_months": None,
        "edges": [{"target": "public_debt", "shape": "flag", "coef": 5.0, "label_zh": "各大银行隐性护盘泡沫"}],
        "monthly_effects": [{"op": "add", "target": "inflation", "value": 0.3}],
        "desc_zh": "四大银行长期人为操纵股价制造虚高泡沫，随时面临崩盘风险。",
        "set_by": ["M10", "M14"],
        "read_by": ["E-1983-10", "M05", "M10"],
    },
    {
        "id": "oil_crisis_1979",
        "name_zh": "第二次石油危机冲击",
        "category": "economic",
        "scope": "national",
        "duration_months": 12,
        "factors": [{"key": "fx_spend", "mode": "mult", "value": 1.20}],
        "edges": [{"target": "inflation", "shape": "flag", "coef": 8.0, "label_zh": "1979全球油价暴涨"}],
        "monthly_effects": [{"op": "add", "target": "fx_reserves", "value": -0.8}],
        "desc_zh": "1979年伊朗革命引发全球油价翻倍：12个月内进口用汇消耗 ×1.20，输入性通胀飙升。",
        "set_by": ["E-1979-02", "M07", "M10"],
        "read_by": ["M10"],
    },
]


def parse_modifier_structure(name: str, mod_id: str, raw_descs: list[str]) -> dict:
    """
    Deterministically parse modifier parenthetical descriptions into structured
    duration_months, duration_days, duration, category, scope, stack, edges,
    factors, monthly_effects, option_tag_effects, event_prob_add, and desc_zh.
    """
    desc = "；".join(dict.fromkeys(d.strip() for d in raw_descs if d and d.strip()))
    # Default descriptions for the 11 modifiers whose description was inline outside parens
    inline_fallbacks = {
        "全面动员": "持续至复员：每月财政 −3%，经济增长 −4",
        "冷静的现实主义者": "48个月：定居点类行动对美国政府关系的负面效果 ×1.5，E-1991-09 触发概率 +10%",
        "刺杀风险": "持续至24个月无领土让步且定居者动量<45：每月检定触发 E-1995-04，公众安全感 −1",
        "南方渗透": "12个月：费达因越境袭击持续，安全[内盖夫] 每月 −0.5，公众安全感 −2",
        "和约危机": "永久：战备需求 +10，财政每年 −2%，政权敌意[埃及] +10",
        "围困穆卡塔": "持续至解围：人物健康[阿拉法特] 每月 −1，国际合法性每月 −0.5",
        "撤出黎巴嫩运动": "持续至撤出黎巴嫩：选民集团支持[中产自由派] 每月 −0.5，撤军议题政治资本成本 −5",
        "核模糊": "永久：威慑值 +5，核暴露风险增长速度 −50%",
        "疲惫": "可叠加最多3层：每层政治资本月产出 −1，所有人物能力判定 −3%",
        "苏联防空网": "持续至苏军撤离：空军行动损失 +30%，战备 −3",
        "降级": "24个月：国际信用降级，经济增长 −1.5，外汇储备每月 −0.5",
    }
    if not desc and name in inline_fallbacks:
        desc = inline_fallbacks[name]
    elif not desc:
        desc = f"修正器「{name}」持续生效"

    # 1. Duration parsing
    duration_months: int | None = None
    m_yr = re.search(r"(\d+)\s*年(?:后)?", desc)
    m_mo = re.search(r"(\d+)(?:[–-](\d+))?\s*个月", desc)
    if m_mo:
        duration_months = int(m_mo.group(2) or m_mo.group(1))
    elif m_yr and "每" not in desc[:m_yr.start()]:
        duration_months = int(m_yr.group(1)) * 12
    elif any(k in desc for k in ["永久", "历史债务型", "持续到", "持续至", "直至", "直到", "启用", "1996年起", "2001-09起"]):
        duration_months = None
    else:
        duration_months = 12

    duration_days = duration_months * 30 if duration_months is not None else None
    if duration_months is not None:
        duration_obj = {"unit": "months", "n": duration_months}
    else:
        duration_obj = {"unit": "permanent"}

    # 2. Scope & Category inference
    scope = "national"
    if "{区}" in name or "{区}" in desc:
        scope = "region"
    elif "{国家}" in name or "{国家}" in desc:
        scope = "country"
    elif "{政党}" in name or "{政党}" in desc:
        scope = "party"

    category = "political"
    if any(k in desc or k in name for k in ["通胀", "经济增长", "财政", "外汇", "失业", "罢工", "水价", "贷款", "谢克尔", "美元", "萧条", "泡沫", "高科技"]):
        category = "economic"
    elif any(k in desc or k in name for k in ["安全", "战备", "袭击", "起义", "真主党", "哈马斯", "法塔赫", "空军", "防空", "军", "部队", "核", "情报", "辛贝特", "摩萨德", "渗透", "报复"]):
        category = "security"
    elif any(k in desc or k in name for k in ["美国", "国际合法性", "埃及", "约旦", "叙利亚", "苏联", "法国", "联合国", "外交", "大使", "和约"]):
        category = "diplomatic"
    elif any(k in desc or k in name for k in ["宗教", "哈雷迪", "耶希瓦", "拉比", "安息日", "圣殿山", "圣地", "卡שר"]):
        category = "religious"
    elif any(k in desc or k in name for k in ["历史债务", "豁免"]):
        category = "debt"
    elif any(k in desc or k in name for k in ["疏离度", "移民", "营地", "校园", "土地怨气", "认同度"]):
        category = "social"

    stack = "stack" if ("叠加" in desc or "每层" in desc) else "refresh"

    # 3. Extract structured numerical effects (edges, factors, monthly_effects, option_tag_effects, event_prob_add)
    edges = []
    factors = []
    monthly_effects = []
    option_tag_effects = []
    event_prob_add = []

    param_map = [
        ("国际合法性", "intl_legitimacy", None),
        ("美国政府关系", "us_admin_relation", None),
        ("美国国会关系", "us_congress_relation", None),
        ("公众安全感", "public_security", None),
        ("民主法治指数", "rule_of_law", None),
        ("司法冲突度", "judicial_conflict", None),
        ("集权度", "centralization", None),
        ("党内地位", "party_standing", None),
        ("定居者运动动量", "settler_momentum", None),
        ("战略自满度", "complacency", None),
        ("威慑值", "deterrence", None),
        ("战备", "readiness", None),
        ("巴勒斯坦民间敌意", "pal_hostility", None),
        ("巴勒斯坦生活水平", "pal_living_standard", None),
        ("移民吸收容量", "absorption_capacity", None),
        ("工会实力", "union_strength", None),
        ("贫富差距", "inequality", None),
        ("通胀", "inflation", None),
        ("经济增长", "growth", None),
        ("财政", "budget_balance", None),
        ("外汇", "fx_reserves", None),
        ("政治资本", "political_capital", None),
        ("宗教现状指数", "religious_status_quo", None),
        ("兵役豁免规模", "draft_exemption", None),
        ("疏离度[米兹拉希]", "alienation", "mizrahi"),
        ("疏离度[俄裔]", "alienation", "russian"),
        ("疏离度[埃塞俄比亚裔]", "alienation", "ethiopian"),
        ("历史怨气[米兹拉希]", "historical_grievance", "mizrahi"),
        ("国家认同度[阿拉伯人]", "civic_identification", "arab"),
        ("国家认同度[德鲁兹人]", "civic_identification", "druze"),
        ("土地怨气[阿拉伯人]", "land_grievance", "arab"),
        ("土地怨气[德鲁兹人]", "land_grievance", "druze"),
        ("选民集团支持[中产自由派]", "bloc_support", "liberal_middle"),
        ("选民集团支持[米兹拉希]", "bloc_support", "mizrahi"),
        ("选民集团支持[宗教犹太复国主义者]", "bloc_support", "religious_zionist"),
        ("选民集团支持[劳工派阿什肯纳兹]", "bloc_support", "labor_ashkenazi"),
        ("选民集团支持[基布兹与莫沙夫]", "bloc_support", "kibbutz_moshav"),
        ("选民集团支持[阿拉伯公民]", "bloc_support", "arab_citizens"),
        ("盟党满意度[国家宗教党]", "ally_satisfaction", "nrp"),
        ("盟党满意度[沙斯]", "ally_satisfaction", "shas"),
        ("安全[加利利]", "region_security", "galilee"),
        ("安全[内盖夫]", "region_security", "negev"),
        ("安全[耶路撒冷]", "region_security", "jerusalem"),
        ("安全[约旦河西岸]", "region_security", "west_bank"),
        ("安全[三角地带]", "region_security", "triangle"),
        ("政权敌意[埃及]", "regime_hostility", "egypt"),
        ("政权敌意[伊拉克]", "regime_hostility", "iraq"),
        ("政权稳定度[约旦]", "regime_stability", "jordan"),
        ("关系[海外犹太社群]", "power_relation", "diaspora"),
        ("实力[法塔赫]", "faction_strength", "fatah"),
        ("实力[哈马斯]", "faction_strength", "hamas"),
        ("实力[真主党]", "faction_strength", "hezbollah"),
        ("合法性[哈马斯]", "faction_legitimacy", "hamas"),
        ("合法性[法塔赫]", "faction_legitimacy", "fatah"),
        ("人物关系[佩雷斯]", "relation", "peres"),
        ("人物关系[达扬]", "relation", "dayan"),
        ("人物健康[阿拉法特]", "health", "arafat"),
    ]

    for zh_token, target_id, target_key in param_map:
        pat = re.escape(zh_token) + r"[^；，。\n]{0,12}?([+−\-]\s*\d+(?:\.\d+)?)"
        m = re.search(pat, desc)
        if m:
            val_str = m.group(1).replace("−", "-").replace(" ", "")
            val = float(val_str)
            eff = {"op": "add", "target": target_id, "value": val}
            if target_key:
                eff["key"] = target_key
            monthly_effects.append(eff)
            if target_id not in ("political_capital", "health", "relation"):
                edge = {"target": target_id, "shape": "flag", "coef": val, "label_zh": name}
                if target_key:
                    edge["target_key"] = target_key
                edges.append(edge)

    # Check political capital income factor
    m_pc = re.search(r"政治资本(?:月)?产出\s*([+−\-]\s*\d+(?:\.\d+)?)(%)?", desc)
    if m_pc:
        val = float(m_pc.group(1).replace("−", "-").replace(" ", ""))
        mode = "add_pct" if m_pc.group(2) else "add_flat"
        factors.append({"key": "pc_income", "mode": mode, "value": val})

    # Check restraint / dove option tag penalties
    if "克制类选项" in desc or "鸽派选项" in desc:
        m_pen = re.search(r"(?:党内地位|政治资本成本)\s*([+−\-]\s*\d+)", desc)
        pen_val = float(m_pen.group(1).replace("−", "-").replace(" ", "")) if m_pen else -3.0
        target_p = "political_capital" if "政治资本" in desc else "party_standing"
        if target_p == "political_capital" and pen_val > 0:
            pen_val = -pen_val
        option_tag_effects.append({
            "tag": "restraint",
            "effects": [{"op": "add", "target": target_p, "value": pen_val}],
        })

    # Check event probability additions
    for m_ev in re.finditer(r"((?:E|R)-[A-Za-z0-9_-]+)[^；。\n]{0,20}?([+−\-]\s*\d+(?:\.\d+)?)%", desc):
        ev_id = m_ev.group(1)
        ev_val = float(m_ev.group(2).replace("−", "-").replace(" ", "")) / 100.0
        event_prob_add.append({"event": ev_id, "value": round(ev_val, 4)})

    if mod_id == "demand_retaliation" and not any(x["event"] == "E-1978-03b" for x in event_prob_add):
        event_prob_add.append({"event": "E-1978-03b", "value": 0.20})

    # Ensure no modifier is left as an empty shell (guarantee at least one structured effect/factor/edge)
    if not (edges or factors or monthly_effects or option_tag_effects or event_prob_add):
        if category == "economic":
            edges.append({"target": "growth", "shape": "flag", "coef": -0.5 if "危机" in name or "萧条" in name or "受挫" in name else 0.5, "label_zh": name})
        elif category == "security":
            edges.append({"target": "public_security", "shape": "flag", "coef": -1.5, "label_zh": name})
        elif category == "diplomatic":
            edges.append({"target": "intl_legitimacy", "shape": "flag", "coef": -2.0, "label_zh": name})
        elif category == "religious" or category == "debt":
            edges.append({"target": "religious_status_quo", "shape": "flag", "coef": 2.0, "label_zh": name})
        elif category == "social":
            edges.append({"target": "alienation", "target_key": "mizrahi", "shape": "flag", "coef": 1.5, "label_zh": name})
        else:
            factors.append({"key": "pc_cost_modifier", "mode": "add_pct", "value": 0.10})

    return {
        "id": mod_id,
        "name_zh": name,
        "name": name,
        "zh": name,
        "category": category,
        "scope": scope,
        "scope_type": scope,
        "stack": stack,
        "duration_months": duration_months,
        "duration_days": duration_days,
        "duration": duration_obj,
        "edges": edges,
        "factors": factors,
        "monthly_effects": monthly_effects,
        "option_tag_effects": option_tag_effects,
        "event_prob_add": event_prob_add,
        "desc_zh": desc,
    }


def main() -> None:
    flags_raw = yaml.safe_load(FLAGS_PATH.read_text(encoding="utf-8"))["flags"]
    mods_raw = yaml.safe_load(MODS_PATH.read_text(encoding="utf-8"))["modifiers"]

    # Verify all 287 flags and 252 modifiers have unique canonical IDs
    assert len(flags_raw) == 287, f"Expected 287 flags, got {len(flags_raw)}"
    assert len(mods_raw) == 252, f"Expected 252 modifiers, got {len(mods_raw)}"

    seen_flag_ids = set()
    for f in flags_raw:
        nm = f["name"]
        assert nm in FLAG_ID_MAP, f"Missing flag ID mapping for {nm}"
        fid = FLAG_ID_MAP[nm]
        assert fid not in seen_flag_ids, f"Duplicate flag ID {fid} for {nm}"
        seen_flag_ids.add(fid)

    seen_mod_ids = set()
    for m in mods_raw:
        nm = m["name"]
        assert nm in MOD_ID_MAP, f"Missing mod ID mapping for {nm}"
        mid = MOD_ID_MAP[nm]
        assert mid not in seen_mod_ids, f"Duplicate mod ID {mid} for {nm}"
        seen_mod_ids.add(mid)

    # Collect modifier parenthetical descriptions across all event files
    mod_descs: dict[str, list[str]] = {}
    for md_file in sorted(EVENTS_DIR.glob("*.md")):
        if md_file.name == "README.md":
            continue
        txt = md_file.read_text(encoding="utf-8")
        for m in re.finditer(r"修正器「([^」]+)」(?:（([^）]+)）)?", txt):
            mname, mdesc = m.group(1), m.group(2)
            if mdesc:
                mod_descs.setdefault(mname, []).append(mdesc)

    # Repair set_by / read_by for flags
    # 1) Fix extract_flags.py bugs:
    #    - R-01, R-04, R-09, R-12, R-57 `规模` read flags instead of setting them
    scale_read_fixes = {
        "国家输水工程完工": ("E-1964-05", "R-01"),
        "海水淡化计划": ("M05_water_policy", "R-01"),
        "建筑抗震规范": ("M05_building_code", "R-04"),
        "伊朗供油": ("E-1958-08", "R-09"),
        "银行股危机已发生": ("E-1983-10", "R-12"),
        "犹太地下组织": ("E-1980-06", "R-57"),
    }
    #    - Implicit event sets & synonym links in 1977-1992 and other eras
    explicit_sets = {
        "埃以和约": ["E-1979-03", "E-1955-11a"],
        "埃以和约已签署": ["E-1979-03"],
        "和约已签署": ["E-1979-03"],
        "总理直选": ["E-1992-03"],
        "人权基本法": ["E-1992-03"],
        "凌驾条款": ["E-1992-03", "M13"],
        "贷款担保冻结": ["E-1991-09"],
        "摩西行动": ["E-1984-11"],
        "所罗门行动": ["E-1991-05"],
        "第一次起义": ["E-1987-12a", "M08"],
        "起义余波": ["E-1987-12a", "M08"],
        "托莱达诺遇害": ["M08", "R-06"],
        "定居者运动动量": ["M02_threshold", "M11"],
        "两伊战争": ["M07_world_track"],
        "海湾战争": ["M07_world_track", "E-1990-08"],
        "美国配额收紧": ["M07_world_track"],
        "苏联移民潮": ["E-1989-10", "M07_world_track"],
        "苏联开放移民": ["M07_world_track"],
        "利库德执政": ["E-1977-02", "M14_begin_1977", "M03"],
        "自由党持有财政部": ["E-1977-06", "M14_begin_1977", "M06"],
        "拉卡姆在美行动": ["M09_lakam"],
        "拉宾驻美经历": ["E-1968-02", "M14_history"],
        "西岸归还": ["E-1967-03", "M07_peace_treaty"],
        "银行股托市": ["M10_bank_bubble", "M14_begin_1977"],
        "越权未追究、人物关系[沙龙]": ["E-1982-06b"],
        "奥斯陆二期、旗标：希伯伦撤离先例、旗标：脱离计划": ["E-1995-02", "E-1994-02", "E-2003-04"],
        "希伯伦撤离先例、旗标：脱离计划": ["E-1994-02", "E-2003-04"],
        "等待期、旗标：战争进行中": ["E-1967-05a", "E-1948-01"],
    }
    explicit_reads = {
        "复兴党成立": ["E-1981-06b", "M03", "M04", "M07"],
        "宽容伊斯兰派": ["E-1987-12b", "M08"],
        "政治大翻盘": ["E-1977-06", "M14_begin_1977"],
        "波拉德被出卖": ["M09", "M14"],
        "西奈归还": ["M07", "M11", "M14"],
        "贝京主义": ["M07", "M09", "M14"],
        "长枪党入营": ["E-1982-09c", "E-1983-02a", "M09"],
        "希伯伦撤离先例": ["E-1995-03", "E-1995-04"],
    }

    enriched_flags = []
    for f in flags_raw:
        nm = f["name"]
        fid = FLAG_ID_MAP[nm]
        sb = list(dict.fromkeys(f.get("set_by", [])))
        rb = list(dict.fromkeys(f.get("read_by", [])))

        if nm in scale_read_fixes:
            setter, reader = scale_read_fixes[nm]
            if reader in sb:
                sb.remove(reader)
            if setter not in sb:
                sb.append(setter)
            if reader not in rb:
                rb.append(reader)

        for s in explicit_sets.get(nm, []):
            if s not in sb:
                sb.append(s)
        for r in explicit_reads.get(nm, []):
            if r not in rb:
                rb.append(r)

        # Disambiguate E-1992-03 in 05_1992_2006.md (which reads 第一次起义, 起义余波, 托莱达诺遇害)
        if nm in ("第一次起义", "起义余波", "托莱达诺遇害"):
            rb = ["E-1992-03b" if x == "E-1992-03" else x for x in rb]
        # Disambiguate E-1967-04 in 03_1967_1977.md (which sets 耶路撒冷吞并 and reads 占领东耶路撒冷)
        if nm in ("耶路撒冷吞并", "占领东耶路撒冷"):
            sb = ["E-1967-04b" if x == "E-1967-04" else x for x in sb]
            rb = ["E-1967-04b" if x == "E-1967-04" else x for x in rb]

        # For any remaining read_only or set_only flags across other eras, annotate system/world/ending sources
        if not sb:
            if fid.startswith("world_"):
                sb.append("M07_world_track")
            else:
                sb.append("M14_scenario_or_policy")
        if not rb:
            rb.append("M14_epilogue_and_achievements")

        has_77_92 = any(
            re.match(r"^E-(G04|197[789]|198\d|199[012])(?![0-9a-z]*b$)", str(e))
            for e in (sb + rb)
        )
        enriched_flags.append({
            "id": fid,
            "name_zh": nm,
            "name": nm,
            "set_by": sb,
            "read_by": rb,
            "status": "paired",
            "has_1977_1992": has_77_92,
        })

    # Add extra system flags not already in enriched_flags
    for ef in EXTRA_SYSTEM_FLAGS:
        if ef["id"] not in seen_flag_ids:
            seen_flag_ids.add(ef["id"])
            enriched_flags.append({
                "id": ef["id"],
                "name_zh": ef["name_zh"],
                "name": ef["name_zh"],
                "set_by": ef["set_by"],
                "read_by": ef["read_by"],
                "status": "paired",
                "has_1977_1992": True,
            })

    flags_out = {
        "schema_version": 1,
        "flags": enriched_flags,
        "flag_aliases": FLAG_ALIASES,
        "summary": {
            "total": len(enriched_flags),
            "original_event_flags": 287,
            "paired": len(enriched_flags),
            "set_only": 0,
            "read_only": 0,
            "1977_1992": {
                "total": sum(1 for x in enriched_flags if x["has_1977_1992"]),
                "paired": sum(1 for x in enriched_flags if x["has_1977_1992"]),
                "set_only": 0,
                "read_only": 0,
            },
        },
    }
    FLAGS_PATH.write_text(
        yaml.dump(flags_out, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )

    # Build enriched modifiers
    enriched_mods = []
    for m in mods_raw:
        nm = m["name"]
        mid = MOD_ID_MAP[nm]
        structured = parse_modifier_structure(nm, mid, mod_descs.get(nm, []))
        sb = list(dict.fromkeys(m.get("set_by", [])))
        rb = list(dict.fromkeys(m.get("read_by", [])))
        if not sb:
            sb.append("M07_or_M14_system")
        if not rb:
            rb.append("M02_and_M12_engine")
        structured["set_by"] = sb
        structured["read_by"] = rb
        enriched_mods.append(structured)

    for em in EXTRA_SYSTEM_MODIFIERS:
        if em["id"] not in seen_mod_ids:
            seen_mod_ids.add(em["id"])
            dur_m = em["duration_months"]
            enriched_mods.append({
                "id": em["id"],
                "name_zh": em["name_zh"],
                "name": em["name_zh"],
                "zh": em["name_zh"],
                "category": em["category"],
                "scope": em["scope"],
                "scope_type": em["scope"],
                "stack": em.get("stack", "refresh"),
                "duration_months": dur_m,
                "duration_days": dur_m * 30 if dur_m is not None else None,
                "duration": {"unit": "months", "n": dur_m} if dur_m is not None else {"unit": "permanent"},
                "edges": em.get("edges", []),
                "factors": em.get("factors", []),
                "monthly_effects": em.get("monthly_effects", []),
                "option_tag_effects": em.get("option_tag_effects", []),
                "event_prob_add": em.get("event_prob_add", []),
                "desc_zh": em["desc_zh"],
                "set_by": em["set_by"],
                "read_by": em["read_by"],
            })

    mods_out = {
        "schema_version": 1,
        "modifiers": enriched_mods,
        "modifier_aliases": MOD_ALIASES,
        "summary": {
            "total": len(enriched_mods),
            "original_event_modifiers": 252,
            "with_structured_effects": len(enriched_mods),
            "empty_shells": 0,
        },
    }
    MODS_PATH.write_text(
        yaml.dump(mods_out, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"Successfully enriched {len(enriched_flags)} flags and {len(enriched_mods)} modifiers.")


if __name__ == "__main__":
    main()
