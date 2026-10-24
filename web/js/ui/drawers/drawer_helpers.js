/* Shared Chinese labels, formatting helpers, and compact UI widgets for D1–D7 drawers. */
import { el, label, button, fmt } from "../../core/controls.js";

export const PARTY_ZH = {
  likud: "利库德集团",
  labor: "工党联盟",
  dash: "民主变革运动",
  nrp: "国家宗教党",
  agudat: "以色列阿古达",
  poalei_agudat: "阿古达工人党",
  rakah_hadash: "哈达什和平阵线",
  sheli: "舍利左翼和平党",
  flatto_sharon: "弗拉托·沙龙名单",
  ilp: "独立自由党",
  ratz: "公民权利运动",
  arab_lists: "阿拉伯联合名单",
  tehiya: "复兴党",
  shas: "沙斯党",
  shinui: "变革党",
  meretz: "梅雷兹党",
  kach: "卡赫运动",
  tami: "塔米传统党",
  morasha: "莫拉沙宗教党",
  tzomet: "路口党",
  moledet: "祖国党",
  degel_hatorah: "妥拉旗帜党",
  independents: "独立议员",
  liberals: "自由党派系",
  mapam: "统一工人党",
  herut: "赫鲁特运动",
  gahal: "加哈尔集团",
  mapai: "以色列地工人党",
  rafi: "以色列工人名单",
  ahdut_haavoda: "劳动统一党",
  general_zionists: "一般锡安主义党",
  progressives: "进步党",
  utj: "联合妥拉犹太教",
  yisrael_baalia: "以色列阿利亚党",
  kadima: "前进党",
  maki: "以色列共产党",
  shlomtzion: "锡安和平党",
  telem: "国家复兴运动",
  yahad: "团结党",
  ometz: "勇气党",
  plp: "进步和平名单",
  adp: "阿拉伯民主党",
  other_lists: "其他小党名单",
  new_party_a: "新政党甲",
  new_party_b: "新政党乙",
  new_party_c: "新政党丙",
};

export const FACTION_ZH = {
  herut_core: "赫鲁特主流（贝京派）",
  herut_hawks: "以色列地强硬派（科亨派）",
  liberal_wing: "自由党温和派（埃利希派）",
  laam: "拉姆国家派（胡尔维茨派）",
  labor_peres: "工党佩雷斯主流派",
  labor_rabin: "工党拉宾务实派",
  ahdut_haavoda: "劳动统一鹰派",
  labor_doves: "工党鸽派",
};

export const OFFICE_ZH = {
  prime_minister: "内阁总理",
  foreign: "外交部长",
  foreign_minister: "外交部长",
  defense: "国防部长",
  defense_minister: "国防部长",
  finance: "财政部长",
  finance_minister: "财政部长",
  deputy_pm: "副总理",
  agriculture: "农业与定居点部长",
  interior: "内政部长",
  interior_minister: "内政部长",
  police: "警察部长",
  education: "教育文化部长",
  education_minister: "教育文化部长",
  religious_affairs: "宗教事务部长",
  religion_minister: "宗教事务部长",
  industry_trade: "工贸部长",
  housing: "住房与建设部长",
  housing_minister: "住房与建设部长",
  absorption: "移民吸收部长",
  absorption_minister: "移民吸收部长",
  energy: "能源与基建部长",
  communications: "通信部长",
  justice: "司法部长",
  justice_minister: "司法部长",
  transport: "交通部长",
  labor_welfare: "劳工与福利部长",
  chief_of_staff: "国防军总参谋长",
  mossad_chief: "摩萨德局长",
  shin_bet_chief: "辛贝特局长",
  attorney_general: "总检察长",
  supreme_court_president: "最高法院院长",
  boi_governor: "以色列央行行长",
  opposition_leader: "反对党领袖",
  knesset_speaker: "议会议长",
};

export const BLOC_ZH = {
  mizrahi: "米兹拉希选民",
  liberal_middle: "世俗自由派中产",
  religious_zionist: "宗教锡安主义者",
  haredi: "哈雷迪正统派",
  labor_ashkenazi: "劳工阿什肯纳兹",
  kibbutz_moshav: "基布兹与莫沙夫",
  arab_citizens: "阿拉伯与德鲁兹公民",
  russian: "苏联/俄语裔新移民",
};

export const AXIS_ZH = {
  territory: "领土与定居点",
  security: "安全与军事",
  economy: "经济体制",
  religion: "宗教与世俗",
  foreign: "外交与美以关系",
};

export const BUDGET_ZH = {
  defense: { zh: "国防与军费", desc: "影响战备水平、威慑力与外汇消耗" },
  welfare: { zh: "社会福利与津贴", desc: "缓解贫富差距与罢工风险" },
  infrastructure: { zh: "国家基础设施", desc: "拉动长期经济增长与区域发展" },
  education: { zh: "教育与科研", desc: "提升长期增长潜力与世俗中产满意" },
  absorption: { zh: "移民吸收安置", desc: "提升移民吸收容量与新移民住房" },
  dev_towns: { zh: "发展城镇专项", desc: "降低米兹拉希疏离度，拉动内盖夫/加利利" },
  religion: { zh: "宗教机构与经学院", desc: "维持宗教盟党 (NRP/阿古达) 满意度" },
  settlements: { zh: "定居点建设拨款", desc: "推升定居者动量与右翼核心支持，引发美方关切" },
  tax: { zh: "综合税负基准", desc: "税率基准（通过经济政策调节）" },
};

export const COUNTRY_ZH = {
  usa: "美国",
  ussr: "苏联",
  france: "法国",
  uk: "英国",
  west_germany: "西德",
  diaspora: "海外犹太社群",
  egypt: "埃及",
  jordan: "约旦",
  syria: "叙利亚",
  lebanon: "黎巴嫩",
  iraq: "伊拉克",
  saudi: "沙特阿拉伯",
  iran: "伊朗",
  turkey: "土耳其",
  ethiopia: "埃塞俄比亚",
  sudan: "苏丹",
  morocco: "摩洛哥",
};

export const FRONT_ZH = {
  egypt: "南线 · 西奈与埃以边境",
  syria: "北线 · 戈兰高地与叙利亚",
  jordan: "东线 · 约旦河谷防线",
  lebanon: "北疆 · 南黎巴嫩战线",
  sinai: "西奈前线",
  golan: "戈兰高地",
  west_bank: "约旦河西岸",
  south_lebanon: "南黎巴嫩安全区",
};

export const PAL_FACTION_ZH = {
  fatah: "法塔赫 (PLO主流)",
  pflp: "人阵/民阵 (左翼激进)",
  jordan_notables: "亲约旦传统显要",
  local_mayors: "西岸民选市长派",
  village_leagues: "乡村联盟 (亲以合作)",
  mujama: "穆贾马 (伊斯兰慈善网)",
  hamas: "哈马斯 (伊斯兰抵抗运动)",
  pij: "巴勒斯坦杰哈德",
  pa_security: "自治安全机构",
};

export const ACTION_CAT_ZH = {
  all: "全部行动",
  parl: "议会/党务",
  pers: "内阁/人事",
  econ: "经济/财政",
  soc: "社会/族群",
  terr: "领土/定居",
  dipl: "外交/国际",
  mil: "军事/情报",
  occ: "占领区治理",
  opin: "舆论/动员",
  favr: "人情交易",
  cent: "宪政/集权",
};

export function paramZh(ctx, id) {
  if (!id) return "";
  const clean = String(id).startsWith("param:") ? String(id).slice(6) : String(id);
  const byId = (ctx && ctx.data && ctx.data.parameters && ctx.data.parameters.by_id) || {};
  if (byId[clean] && byId[clean].zh) return byId[clean].zh;
  const polById = (ctx && ctx.data && ctx.data.policies && ctx.data.policies.by_id) || {};
  if (polById[clean] && polById[clean].zh) return polById[clean].zh;
  if (BUDGET_ZH[clean]) return BUDGET_ZH[clean].zh;
  if (PARTY_ZH[clean]) return PARTY_ZH[clean];
  if (BLOC_ZH[clean]) return BLOC_ZH[clean];
  return clean;
}

export function charName(ctx, id) {
  if (!id) return "空缺";
  const byId = (ctx && ctx.data && ctx.data.characters && ctx.data.characters.by_id) || {};
  return (byId[id] && byId[id].name_zh) || id;
}

export function charDef(ctx, id) {
  if (!id) return null;
  const byId = (ctx && ctx.data && ctx.data.characters && ctx.data.characters.by_id) || {};
  return byId[id] || null;
}

export function sectionHeader(titleText, rightText = "") {
  const row = el("div", "d-sec-hdr");
  const t = el("span", "d-sec-title");
  t.textContent = titleText;
  row.appendChild(t);
  if (rightText) {
    const r = el("span", "d-sec-sub");
    r.textContent = rightText;
    row.appendChild(r);
  }
  return row;
}

export function metricCard(ctx, { title, value, sub = "", param = "", key = "", tone = "", onClick = null }) {
  const card = el("div", "d-metric-card" + (tone ? ` tone-${tone}` : "") + ((param || onClick) ? " clickable" : ""));
  const top = el("div", "d-metric-top");
  const nameEl = el("span", "d-metric-name");
  nameEl.textContent = title;
  const valEl = el("span", "d-metric-val");
  valEl.textContent = value;
  top.append(nameEl, valEl);
  card.appendChild(top);
  if (sub) {
    const subEl = el("div", "d-metric-sub");
    subEl.textContent = sub;
    card.appendChild(subEl);
  }
  if (param || onClick) {
    card.title = param ? `点击查看「${title}」因果拆解` : title;
    card.addEventListener("click", () => {
      if (onClick) onClick();
      if (param && ctx && ctx.bus) ctx.bus.emit("tooltip_requested", param, key || "");
    });
  }
  return card;
}

export function meterBar(pct, tone = "blue") {
  const wrap = el("div", "d-meter");
  const fill = el("div", `d-meter-fill tone-${tone}`);
  fill.style.width = `${Math.max(0, Math.min(100, Number(pct) || 0)).toFixed(1)}%`;
  wrap.appendChild(fill);
  return wrap;
}

export function rangeSlider(min, max, val, step = 1, onChange = null) {
  const input = el("input", "hslider");
  input.type = "range";
  input.min = String(min);
  input.max = String(max);
  input.step = String(step);
  input.value = String(val);
  if (onChange) {
    input.addEventListener("change", () => onChange(Number(input.value)));
  }
  return input;
}

