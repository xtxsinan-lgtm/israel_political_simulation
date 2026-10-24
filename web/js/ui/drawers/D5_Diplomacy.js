/* Port of game/ui/controllers/drawers/D5_DiplomacyController.gd, enriched with the full M07
 * Superpowers & Western Powers table, Arab & Peripheral States matrix (hostility, stability,
 * war probability, treaty/secret channel/nuclear status), Aliyah immigration breakdown, and
 * diplomatic quick actions. */
import { el, label, button, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { COUNTRY_ZH, sectionHeader, metricCard } from "./drawer_helpers.js";

const ARAB_AND_PERIPHERY = ["egypt", "syria", "jordan", "lebanon", "iraq", "saudi", "iran", "turkey", "ethiopia"];
const POWERS = ["usa", "ussr", "france", "uk", "west_germany", "diaspora"];

const TREATY_ZH = {
  0: "敌对/无条约",
  1: "停火/脱离接触",
  2: "戴维营框架",
  3: "✓ 正式和平条约",
};

const DIPL_ACTIONS = [
  { id: "washington_visit", zh: "正式访问华盛顿", cost: "资本 10" },
  { id: "request_us_aid", zh: "申请美国紧急经援", cost: "资本 8" },
  { id: "strategic_memorandum", zh: "签署美以战略备忘录", cost: "资本 12" },
  { id: "secret_channel", zh: "开辟邻国秘密渠道", cost: "资本 8" },
  { id: "autonomy_proposal", zh: "提出巴勒斯坦自治方案", cost: "资本 12" },
  { id: "un_lobbying", zh: "联合国与欧洲外交游说", cost: "资本 6" },
  { id: "diaspora_tour", zh: "海外犹太社群募捐巡访", cost: "资本 6" },
  { id: "lebanon_christian_alliance", zh: "强化黎巴嫩基督徒同盟", cost: "资本 8" },
];

registerReads([
  ["us_wh_warmth", ""],
  ["us_cong_support", ""],
  ["intl_legitimacy", ""],
  ["strategic_dependence", ""],
  ["immigration_inflow", ""],
  ["absorption_capacity", ""],
]);

export class D5DiplomacyController {
  constructor(ctx) {
    this.ctx = ctx;
    this.targetCountry = "egypt";
  }

  mount(parent) {
    this.root = el("div", "drawer-body d5-diplomacy");
    this.summary = label("", { size: 12, autowrap: true, cls: "drawer-summary d-compact-summary" });
    this.kpiRow = el("div", "d-kpi-grid-6");
    this.status = label("", { size: 12, cls: "d3-status" });
    this.cols = el("div", "d-two-col");
    this.leftCol = el("div", "d-col");
    this.rightCol = el("div", "d-col");
    this.cols.append(this.leftCol, this.rightCol);
    this.root.append(this.summary, this.kpiRow, this.status, this.cols);
    parent.appendChild(this.root);
  }

  refresh(view) {
    const wh = view.params.get_val("us_wh_warmth", "");
    const cong = view.params.get_val("us_cong_support", "");
    const intl = view.params.get_val("intl_legitimacy", "");
    const dep = view.params.get_val("strategic_dependence", "");
    const aliyah = view.params.get_val("immigration_inflow", "");
    const absCap = view.params.get_val("absorption_capacity", "");

    const m07 = (view.raw.modules && view.raw.modules.M07) || {};
    const usPol = m07.us_politics || {};
    const presZh = usPol.president_zh || (view.clock.year < 1981 ? "吉米·卡特 (民主党)" : "罗纳德·里根 (共和党)");

    this.summary.textContent = fmt(
      "白宫 %.0f  国会 %.0f（当前美国总统：%s） · 国际合法性 %.0f · 年化阿利亚移民 %.0f 人/年 · 苏联配额 / 埃塞俄比亚 / 欧美 / 中东（埃及 约旦 叙利亚 黎巴嫩）",
      wh, cong, presZh, intl, aliyah,
    );

    this.kpiRow.replaceChildren();
    this.kpiRow.append(
      metricCard(this.ctx, { title: "美国白宫关系", value: wh.toFixed(0), param: "us_admin_relation", sub: presZh, tone: wh >= 55 ? "good" : (wh <= 35 ? "bad" : "warn") }),
      metricCard(this.ctx, { title: "美国国会支持", value: cong.toFixed(0), param: "us_congress_relation", sub: "军援与否决权护盾", tone: cong >= 60 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "国际合法性", value: intl.toFixed(0), param: "intl_legitimacy", sub: "低于25面临制裁风险", tone: intl >= 50 ? "good" : (intl <= 30 ? "bad" : "warn") }),
      metricCard(this.ctx, { title: "对美战略依赖", value: `${dep.toFixed(0)}%`, param: "strategic_dependence", sub: "军火与经援依赖度" }),
      metricCard(this.ctx, { title: "年阿利亚流入", value: `${(aliyah / 1000).toFixed(1)}千`, param: "immigration_inflow", sub: "全球犹太移民潮", tone: "good" }),
      metricCard(this.ctx, { title: "国内吸收容量", value: absCap.toFixed(0), param: "absorption_capacity", sub: "住房与安置承载力", tone: absCap >= 45 ? "good" : "warn" }),
    );

    this.renderLeftPowersAndActions(view, m07);
    this.renderRightNeighbors(view, m07);
  }

  renderLeftPowersAndActions(view, m07) {
    this.leftCol.replaceChildren();
    const countries = m07.countries || {};
    const powerRel = (view.raw.params && view.raw.params.power_relation) || {};
    const armsRel = (view.raw.params && view.raw.params.arms_reliability) || {};

    const pCard = el("div", "d-card");
    pCard.appendChild(sectionHeader("大国关系、海外侨界与阿利亚来源 (M07)", "影响军购、美援与移民配额"));

    const tbl = el("table", "d-table");
    tbl.innerHTML = "<thead><tr><th>大国 / 主体</th><th>当前关系</th><th>军售可靠度</th><th>战略态势说明</th></tr></thead>";
    const tbody = el("tbody");

    for (const pid of POWERS) {
      const c = countries[pid] || {};
      const rel = pid === "usa"
        ? view.params.get_val("us_wh_warmth", "")
        : Number(powerRel[pid] ?? c.relation ?? 50);
      const arms = armsRel[pid] !== undefined ? `${Number(armsRel[pid]).toFixed(0)}%` : "—";
      let note = "常规外交往来";
      if (pid === "usa") note = `国会支持 ${view.params.get_val("us_cong_support", "").toFixed(0)} · 核心战略盟友`;
      else if (pid === "ussr") note = rel < 25 ? "1967断交状态 · 严控犹太移民配额" : "关系缓和 · 移民配额松动";
      else if (pid === "diaspora") note = "北美与全球犹太社团游说及债券认购";
      else if (pid === "france" || pid === "uk") note = "欧共体经贸与联合国安理会投票方";
      else if (pid === "west_germany") note = "欧洲关键经贸伙伴与情报合作";

      const tr = el("tr");
      tr.innerHTML = `<td class="td-bold">${COUNTRY_ZH[pid] || pid}</td><td class="td-num">${rel.toFixed(0)}</td><td class="td-num">${arms}</td><td>${note}</td>`;
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    pCard.appendChild(tbl);

    // Aliyah breakdown bar
    const imm = m07.immigration_breakdown || {};
    const immLine = el("div", "d-subnote");
    immLine.textContent = `阿利亚移民来源拆解：苏联犹太人 ${Number(imm.ussr_jewish ?? 6500).toFixed(0)}/年 · 欧美自由移民 ${Number(imm.western_free ?? 5500).toFixed(0)}/年 · 埃塞俄比亚 (摩西行动线) ${Number(imm.ethiopia ?? 500).toFixed(0)}/年`;
    pCard.appendChild(immLine);
    this.leftCol.appendChild(pCard);

    // Diplomatic Actions
    const aCard = el("div", "d-card");
    const pc = view.params.get_val("political_capital", "");
    aCard.appendChild(sectionHeader("外交与国际游说行动", `当前政治资本 ${pc.toFixed(0)}`));

    const tgtBar = el("div", "d-target-bar");
    tgtBar.appendChild(label("密道/双边行动目标国：", { size: 11 }));
    const sel = el("select", "d-arg-select");
    for (const cid of ARAB_AND_PERIPHERY) {
      const opt = document.createElement("option");
      opt.value = cid;
      opt.textContent = COUNTRY_ZH[cid] || cid;
      if (cid === this.targetCountry) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", () => { this.targetCountry = sel.value; });
    tgtBar.appendChild(sel);
    aCard.appendChild(tgtBar);

    const actGrid = el("div", "d-act-grid");
    const cdMap = (view.raw.modules && view.raw.modules.M05 && view.raw.modules.M05.action_cooldowns) || {};
    const day = Number(view.clock.day_index || 0);
    for (const act of DIPL_ACTIONS) {
      const cd = Number(cdMap[act.id] || 0);
      const onCd = cd > day;
      const b = button(
        `${act.zh}（${onCd ? `冷却至第${cd}天` : act.cost}）`,
        async () => {
          const args = { country: this.targetCountry, power: "usa" };
          const res = await this.ctx.engine.submitCommand({ op: "execute_action", action: act.id, args });
          this.status.textContent = res && res.ok
            ? `✓ 已下达外交行动：${act.zh}（目标：${COUNTRY_ZH[this.targetCountry] || this.targetCountry}）`
            : `✗ 未能执行：${act.zh}（${(res && res.result && res.result.error) || "条件或政治资本不足"}）`;
        },
        { size: 12, cls: "d-act-btn" },
      );
      b.disabled = onCd;
      actGrid.appendChild(b);
    }
    aCard.appendChild(actGrid);
    this.leftCol.appendChild(aCard);
  }

  renderRightNeighbors(view, m07) {
    this.rightCol.replaceChildren();
    const card = el("div", "d-card");
    card.appendChild(sectionHeader("阿拉伯前线国家与中东外围态势 (M07)", "点击国家可查看政权敌意因果链"));

    const countries = m07.countries || {};
    const regHost = (view.raw.params && view.raw.params.regime_hostility) || {};
    const popHost = (view.raw.params && view.raw.params.popular_hostility) || {};
    const regStab = (view.raw.params && view.raw.params.regime_stability) || {};
    const warProb = (view.raw.params && view.raw.params.war_probability) || {};
    const nucProg = (view.raw.params && view.raw.params.enemy_nuclear_progress) || {};

    const tbl = el("table", "d-table");
    tbl.innerHTML = "<thead><tr><th>国家</th><th>政权敌意</th><th>民间敌意</th><th>政权稳定</th><th>开战概率</th><th>条约 / 密道 / 核情报</th></tr></thead>";
    const tbody = el("tbody");

    for (const cid of ARAB_AND_PERIPHERY) {
      const c = countries[cid] || {};
      const rh = Number(regHost[cid] ?? (c.relation !== undefined ? 100 - c.relation : 60));
      const ph = Number(popHost[cid] ?? rh);
      const st = Number(regStab[cid] ?? c.stability ?? 55);
      const wp = Number(warProb[cid] ?? 10);
      const treaty = Number(c.peace_treaty_state ?? 0);
      const secCh = !!c.secret_channel_open;
      const nuc = Number(nucProg[cid] ?? c.nuclear_progress ?? 0);

      const tags = [TREATY_ZH[treaty] || "无条约"];
      if (secCh) tags.push("密道已通");
      if (cid === "iraq" || nuc >= 15) tags.push(`核进度 ${nuc.toFixed(0)}%`);

      const tr = el("tr", "clickable");
      tr.title = `点击查看「${COUNTRY_ZH[cid] || cid}」敌意因果拆解`;
      tr.addEventListener("click", () => this.ctx.bus.emit("tooltip_requested", "regime_hostility", cid));
      tr.innerHTML = `
        <td class="td-bold">${COUNTRY_ZH[cid] || cid}</td>
        <td class="td-num ${rh >= 70 ? "tone-bad" : (rh <= 35 ? "tone-good" : "")}">${rh.toFixed(0)}</td>
        <td class="td-num">${ph.toFixed(0)}</td>
        <td class="td-num">${st.toFixed(0)}%</td>
        <td class="td-num ${wp >= 35 ? "tone-bad" : ""}">${wp.toFixed(0)}%</td>
        <td>${tags.join(" · ")}</td>
      `;
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    card.appendChild(tbl);
    this.rightCol.appendChild(card);
  }
}
