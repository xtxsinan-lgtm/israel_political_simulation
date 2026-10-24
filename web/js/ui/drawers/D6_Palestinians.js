/* Port of game/ui/controllers/drawers/D6_PalestiniansController.gd, enriched with the full M08
 * West Bank & Gaza macro indicators, 9 Palestinian factions table (Chinese names, active status,
 * legitimacy share bar, strength, moderation), Arab citizens integration monitor, and
 * occupation governance actions. */
import { el, label, button, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { FuzzyBand } from "../../core/FuzzyBand.js";
import { PAL_FACTION_ZH, sectionHeader, metricCard, meterBar } from "./drawer_helpers.js";

export const FACTIONS = ["fatah", "pflp", "jordan_notables", "local_mayors", "village_leagues", "mujama", "hamas", "pij", "pa_security"];

const PHASE_ZH = {
  calm: "平静期 (零星抗议)",
  unrest: "骚乱升级 (石块与罢市)",
  intifada: "⚠ 全面大起义 (Intifada)",
};

const CAMP_ZH = {
  nationalist: "民族主义 (PLO系)",
  leftist: "激进左翼",
  traditional: "亲约旦传统派",
  municipal: "本土民选派",
  cooperative: "亲以合作派",
  islamist_social: "伊斯兰慈善网",
  islamist_militant: "伊斯兰武装抵抗",
  authority: "自治安全机构",
};

const OCC_ACTIONS = [
  { id: "economic_package_occ", zh: "占领区经济贷款与工业区", cost: "资本 8 · 财政 1" },
  { id: "support_moderates", zh: "扶持西岸温和派与显要", cost: "资本 8" },
  { id: "release_prisoners", zh: "释放部分在押人员(善意)", cost: "资本 10" },
  { id: "covert_support_faction", zh: "秘密资助派系(分而治之)", cost: "资本 6" },
  { id: "admin_detention_wave", zh: "大规模行政拘留行动", cost: "资本 8" },
  { id: "dismiss_mayors", zh: "解职亲巴解民选市长", cost: "资本 10" },
  { id: "close_universities", zh: "关闭比尔宰特等巴方大学", cost: "资本 6" },
  { id: "found_settlement", zh: "批准新建约旦河西岸定居点", cost: "资本 12 · 财政 2" },
];

registerReads([
  ["uprising_risk", ""],
  ["pal_hostility", ""],
  ["pal_living_standard", ""],
  ["autonomy_progress", ""],
  ["collaborator_stigma", ""],
  ["settler_momentum", ""],
  ["civic_identification", "arab"],
  ["land_grievance", "arab"],
  ...FACTIONS.map((f) => ["faction_legitimacy", f]),
  ...FACTIONS.map((f) => ["faction_strength", f]),
  ...FACTIONS.map((f) => ["faction_moderation", f]),
]);

export class D6PalestiniansController {
  constructor(ctx) {
    this.ctx = ctx;
    this.palLegitimacy = {};
    this.intifadaPhase = "calm";
    this.targetFaction = "village_leagues";
  }

  mount(parent) {
    this.root = el("div", "drawer-body d6-palestinians");
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
    let total = 0.0;
    for (const f of FACTIONS) {
      const share = view.params.get_val("faction_legitimacy", f);
      this.palLegitimacy[f] = share;
      total += share;
    }
    if (total <= 0.0) {
      const even = 100.0 / FACTIONS.length;
      for (const f of FACTIONS) this.palLegitimacy[f] = even;
    } else if (Math.abs(total - 100.0) > 0.001) {
      const scale = 100.0 / total;
      for (const f of FACTIONS) this.palLegitimacy[f] = this.palLegitimacy[f] * scale;
    }

    const upRisk = view.params.get_val("uprising_risk", "");
    const band = FuzzyBand.bandIndex(upRisk);
    this.intifadaPhase = band >= 3 ? "intifada" : (band >= 2 ? "unrest" : "calm");
    const riskDesc = FuzzyBand.describeBand(band, "uprising_risk");

    this.summary.textContent = fmt(
      "阶段 %s (%s) · 起义风险 %s · mujama %s · hamas %s",
      this.intifadaPhase,
      PHASE_ZH[this.intifadaPhase] || this.intifadaPhase,
      riskDesc,
      FuzzyBand.describe(this.palLegitimacy.mujama, "faction_legitimacy"),
      FuzzyBand.describe(this.palLegitimacy.hamas, "faction_legitimacy"),
    );

    const host = view.params.get_val("pal_hostility", "");
    const liv = view.params.get_val("pal_living_standard", "");
    const auto = view.params.get_val("autonomy_progress", "");
    const stig = view.params.get_val("collaborator_stigma", "");
    const setPop = Number(((view.raw.params && view.raw.params.settler_population) || {}).west_bank ?? 5000);

    this.kpiRow.replaceChildren();
    this.kpiRow.append(
      metricCard(this.ctx, { title: "起义风险评估", value: riskDesc, param: "uprising_risk", sub: PHASE_ZH[this.intifadaPhase], tone: band >= 3 ? "bad" : (band >= 2 ? "warn" : "good") }),
      metricCard(this.ctx, { title: "巴方民间敌意", value: host.toFixed(0), param: "pal_hostility", sub: "搜查/征地/伤亡推升", tone: host >= 65 ? "bad" : "warn" }),
      metricCard(this.ctx, { title: "占领区生活水平", value: liv.toFixed(0), param: "pal_living_standard", sub: "劳工许可与经援拉动", tone: liv >= 45 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "自治谈判进度", value: `${auto.toFixed(0)}%`, param: "autonomy_progress", sub: "戴维营自治轨道", tone: auto >= 25 ? "good" : "" }),
      metricCard(this.ctx, { title: "合作者污名度", value: stig.toFixed(0), param: "collaborator_stigma", sub: "压低乡村联盟合法性", tone: stig >= 50 ? "warn" : "good" }),
      metricCard(this.ctx, { title: "西岸定居者人口", value: `${(setPop / 1000).toFixed(1)}千人`, param: "settler_momentum", sub: `动量 ${view.params.get_val("settler_momentum", "").toFixed(0)}` }),
    );

    this.renderFactionsTable(view);
    this.renderGovernanceAndArabCitizens(view);
  }

  legitimacySum() {
    return FACTIONS.reduce((s, f) => s + Number(this.palLegitimacy[f] || 0), 0);
  }

  renderFactionsTable(view) {
    this.leftCol.replaceChildren();
    const card = el("div", "d-card");
    card.appendChild(sectionHeader("巴勒斯坦九大政治派系谱系与民意占比 (M08)", "总合法性归一为 100%"));

    const m08 = (view.raw.modules && view.raw.modules.M08) || {};
    const activeMap = m08.faction_active || {};
    const pfList = (this.ctx.data.palestine_factions && this.ctx.data.palestine_factions.factions) || [];
    const pfById = {};
    for (const item of pfList) pfById[item.id] = item;

    const tbl = el("table", "d-table");
    tbl.innerHTML = "<thead><tr><th>派系名称</th><th>状态</th><th>民间合法性占比</th><th>实力评估</th><th>温和度</th></tr></thead>";
    const tbody = el("tbody");

    for (const fid of FACTIONS) {
      const def = pfById[fid] || {};
      const isAct = activeMap[fid] !== undefined ? !!activeMap[fid] : !!def.active_at_1977;
      const legShare = Number(this.palLegitimacy[fid] || 0);
      const strVal = view.params.get_val("faction_strength", fid) || Number((def.init_values && def.init_values.strength) || 20);
      const modVal = view.params.get_val("faction_moderation", fid) || Number((def.init_values && def.init_values.moderation) || 30);

      const tr = el("tr", isAct ? "" : "row-muted");
      const tdName = el("td", "td-bold");
      tdName.textContent = PAL_FACTION_ZH[fid] || def.name_zh || fid;
      tdName.title = CAMP_ZH[def.camp] || "";

      const tdState = el("td");
      tdState.innerHTML = isAct
        ? `<span class="d-badge badge-red">活跃</span>`
        : `<span class="d-badge">未激活</span>`;

      const tdLeg = el("td");
      tdLeg.textContent = `${legShare.toFixed(1)}% (${FuzzyBand.describe(legShare, "faction_legitimacy")})`;
      tdLeg.appendChild(meterBar(legShare * 2, fid === "fatah" || fid === "hamas" ? "red" : "blue"));

      const tdStr = el("td", "td-num");
      tdStr.textContent = FuzzyBand.describe(strVal, "faction_strength");

      const tdMod = el("td", "td-num");
      tdMod.textContent = modVal.toFixed(0);

      tr.append(tdName, tdState, tdLeg, tdStr, tdMod);
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    card.appendChild(tbl);
    this.leftCol.appendChild(card);
  }

  renderGovernanceAndArabCitizens(view) {
    this.rightCol.replaceChildren();

    // 1. Green-line Arab & Druze Citizens status
    const cCard = el("div", "d-card");
    cCard.appendChild(sectionHeader("绿线内阿拉伯与德鲁兹公民态势 (M02/M11)", "影响民主属性与加利利/三角区稳定"));
    const civic = view.params.get_val("civic_identification", "arab");
    const landG = view.params.get_val("land_grievance", "arab");
    const cGrid = el("div", "d-kpi-grid-2");
    cGrid.append(
      metricCard(this.ctx, { title: "阿拉伯公民国家认同度", value: civic.toFixed(0), param: "civic_identification", key: "arab", sub: "平权拨款与去军管拉动", tone: civic >= 45 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "土地征用历史怨气", value: landG.toFixed(0), param: "land_grievance", key: "arab", sub: "1976土地日记忆与征地推升", tone: landG >= 55 ? "bad" : "warn" }),
    );
    cCard.appendChild(cGrid);
    this.rightCol.appendChild(cCard);

    // 2. Occupation Governance Toolbox
    const aCard = el("div", "d-card");
    const pc = view.params.get_val("political_capital", "");
    aCard.appendChild(sectionHeader("约旦河西岸与加沙治理工具箱", `当前政治资本 ${pc.toFixed(0)} · 注意短期铁腕与长期反噬`));

    const tgtBar = el("div", "d-target-bar");
    tgtBar.appendChild(label("专项扶持/针对派系：", { size: 11 }));
    const sel = el("select", "d-arg-select");
    for (const fid of FACTIONS) {
      const opt = document.createElement("option");
      opt.value = fid;
      opt.textContent = PAL_FACTION_ZH[fid] || fid;
      if (fid === this.targetFaction) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.addEventListener("change", () => { this.targetFaction = sel.value; });
    tgtBar.appendChild(sel);
    aCard.appendChild(tgtBar);

    const actGrid = el("div", "d-act-grid");
    const cdMap = (view.raw.modules && view.raw.modules.M05 && view.raw.modules.M05.action_cooldowns) || {};
    const day = Number(view.clock.day_index || 0);
    for (const act of OCC_ACTIONS) {
      const cd = Number(cdMap[act.id] || 0);
      const onCd = cd > day;
      const b = button(
        `${act.zh}（${onCd ? `冷却至第${cd}天` : act.cost}）`,
        async () => {
          const args = { faction: this.targetFaction, region: "west_bank" };
          const res = await this.ctx.engine.submitCommand({ op: "execute_action", action: act.id, args });
          this.status.textContent = res && res.ok
            ? `✓ 已下达占领区治理指令：${act.zh}`
            : `✗ 暂不可执行：${act.zh}（${(res && res.result && res.result.error) || "条件或政治资本不足"}）`;
        },
        { size: 12, cls: "d-act-btn" },
      );
      b.disabled = onCd;
      actGrid.appendChild(b);
    }
    aCard.appendChild(actGrid);
    this.rightCol.appendChild(aCard);
  }
}
