/* Port of game/ui/controllers/drawers/D7_MilitaryIntelController.gd, enriched with the full M09
 * IDF readiness/deterrence/complacency dashboard, interactive Mobilization Order controls,
 * 4 Strategic Fronts table with ROE toggles, Nuclear & Osirak Intel monitor, and military actions. */
import { el, label, button, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { FRONT_ZH, sectionHeader, metricCard, meterBar } from "./drawer_helpers.js";

const FRONT_STATUS_ZH = {
  PEACE: "停火和平",
  TENSION: "边境摩擦",
  SKIRMISH: "局部交火",
  WAR: "⚠ 全面交战",
};

const ROE_LABELS = ["0 克制防守", "1 常规警戒", "2 越境反击"];

const MOB_PRESETS = [
  { val: 10, zh: "常备值勤 (10%)", desc: "无额外财政与GDP拖累" },
  { val: 30, zh: "局部戒备 (30%)", desc: "轻度拖累GDP (-0.08%/季)" },
  { val: 60, zh: "前线集结 (60%)", desc: "显著消耗财政并压低增长" },
  { val: 90, zh: "全面总动员 (90%)", desc: "战时体制，严重抽干劳动力" },
];

const MIL_ACTIONS = [
  { id: "raise_alert", zh: "全军提高战备等级", cost: "资本 6" },
  { id: "partial_mobilization", zh: "征召部分预备役旅", cost: "资本 8" },
  { id: "retaliatory_raid", zh: "授权越境报复突袭", cost: "资本 10" },
  { id: "limited_incursion", zh: "发动有限地面清剿行动", cost: "资本 15" },
  { id: "preemptive_strike", zh: "空袭摧毁敌国核反应堆", cost: "资本 20" },
  { id: "arms_purchase", zh: "向大国紧急采购主战装备", cost: "资本 10 · 财政 2" },
  { id: "intelligence_review", zh: "阿曼与摩萨德情报复核", cost: "资本 6" },
  { id: "targeted_killing", zh: "特种部队定点清除", cost: "资本 8" },
];

registerReads([
  ["mobilization", ""],
  ["intel_accuracy", ""],
  ["readiness", ""],
  ["deterrence", ""],
  ["public_security", ""],
  ["complacency", ""],
  ["nuclear_progress", ""],
  ["nuclear_exposure_risk", ""],
  ["enemy_nuclear_progress", "iraq"],
]);

export class D7MilitaryIntelController {
  constructor(ctx) {
    this.ctx = ctx;
    this.mobilizationLevel = 0;
    this.frontStatus = {};
    this.nuclearAmbiguity = "opaque";
    this.intelQuality = 0.0;
  }

  mount(parent) {
    this.root = el("div", "drawer-body d7-military");
    this.summary = label("", { size: 12, autowrap: true, cls: "drawer-summary crt-scanline d-compact-summary" });
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
    const mob = view.params.get_val("mobilization", "");
    this.mobilizationLevel = Math.floor(mob + 0.5);
    this.intelQuality = view.params.get_val("intel_accuracy", "");
    const m09 = (view.raw.modules && view.raw.modules.M09) || {};
    const nuc = m09.nuclear || {};
    this.nuclearAmbiguity = String(nuc.posture || "opaque").toLowerCase();

    const fronts = (view.modules.M09 && view.modules.M09.fronts) || m09.fronts || {};
    this.frontStatus = {};
    for (const id of Object.keys(fronts).sort()) {
      const f = fronts[id];
      this.frontStatus[id] = String((f && typeof f === "object" && f.status) || "PEACE");
    }

    const rdy = view.params.get_val("readiness", "");
    const det = view.params.get_val("deterrence", "");
    const sec = view.params.get_val("public_security", "");
    const comp = view.params.get_val("complacency", "");
    const tgtMob = Number(m09.mobilization_target ?? this.mobilizationLevel);

    this.summary.textContent = fmt(
      "动员 %d (目标 %.0f%%)  情报 %.1f  核模糊 %s  战线 %d  ·  战备 %.0f  威慑 %.0f  安全 %.0f",
      this.mobilizationLevel, tgtMob, this.intelQuality, this.nuclearAmbiguity, Object.keys(this.frontStatus).length,
      rdy, det, sec,
    );

    this.kpiRow.replaceChildren();
    this.kpiRow.append(
      metricCard(this.ctx, { title: "国防军战备度", value: rdy.toFixed(0), param: "readiness", sub: "受国防预算与训练影响", tone: rdy >= 65 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "国家战略威慑", value: det.toFixed(0), param: "deterrence", sub: "压制邻国开战企图", tone: det >= 65 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "国内公共安全", value: sec.toFixed(0), param: "public_security", sub: "低于35触发红色警报", tone: sec >= 55 ? "good" : (sec <= 38 ? "bad" : "warn") }),
      metricCard(this.ctx, { title: "轻敌麻痹指数", value: comp.toFixed(0), param: "complacency", sub: "和平期自然滋生，削弱预警", tone: comp >= 45 ? "bad" : "good" }),
      metricCard(this.ctx, { title: "军情准确度", value: `${this.intelQuality.toFixed(1)}%`, param: "intel_accuracy", sub: "摩萨德/阿曼/辛贝特综合", tone: this.intelQuality >= 70 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "预备役动员率", value: `${this.mobilizationLevel}%`, param: "mobilization", sub: `目标档位 ${tgtMob.toFixed(0)}%`, tone: this.mobilizationLevel >= 50 ? "warn" : "" }),
    );

    this.renderFrontsAndMobilization(view, fronts, tgtMob);
    this.renderNuclearAndActions(view, m09);
  }

  renderFrontsAndMobilization(view, fronts, tgtMob) {
    this.leftCol.replaceChildren();

    // 1. 4 Strategic Fronts Table + ROE buttons
    const fCard = el("div", "d-card");
    fCard.appendChild(sectionHeader("四大战略战线态势与交战规则 (M09 Fronts & ROE)", "可切换各战线前线指挥官交战授权"));

    const tbl = el("table", "d-table");
    tbl.innerHTML = "<thead><tr><th>战略方向</th><th>战线状态</th><th>边境摩擦</th><th>交战规则 (ROE) 授权</th></tr></thead>";
    const tbody = el("tbody");

    for (const fid of Object.keys(fronts).sort()) {
      const f = fronts[fid] || {};
      const st = String(f.status || "PEACE");
      const fric = Number(f.border_friction ?? 15);
      const roe = Number(f.roe_level ?? 1);
      const quag = Number(f.quagmire_months || 0);

      const tr = el("tr");
      const tdName = el("td", "td-bold");
      tdName.textContent = FRONT_ZH[fid] || fid;

      const tdSt = el("td");
      const badgeCls = st === "WAR" ? "badge-red" : (st === "PEACE" ? "badge-blue" : "badge-amber");
      tdSt.innerHTML = `<span class="d-badge ${badgeCls}">${FRONT_STATUS_ZH[st] || st}</span>${quag > 0 ? ` 泥潭${quag}月` : ""}`;

      const tdFric = el("td", "td-num");
      tdFric.textContent = `${fric.toFixed(0)}`;

      const tdRoe = el("td");
      const roeBox = el("div", "d7-roe-box");
      for (let lvl = 0; lvl <= 2; lvl++) {
        const b = button(ROE_LABELS[lvl], async () => {
          const res = await this.ctx.engine.submitCommand({ op: "set_roe", front: fid, roe: lvl });
          this.status.textContent = res && res.ok
            ? `✓ 已将「${FRONT_ZH[fid] || fid}」交战规则设为：${ROE_LABELS[lvl]}`
            : `✗ 交战规则调整失败`;
        }, { size: 11, cls: "d4-pol-btn" + (roe === lvl ? " active" : "") });
        roeBox.appendChild(b);
      }
      tdRoe.appendChild(roeBox);

      tr.append(tdName, tdSt, tdFric, tdRoe);
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    fCard.appendChild(tbl);
    this.leftCol.appendChild(fCard);

    // 2. Mobilization Target Controls
    const mCard = el("div", "d-card");
    mCard.appendChild(sectionHeader("国防军预备役动员令等级", `当前动员 ${this.mobilizationLevel}% → 目标 ${tgtMob.toFixed(0)}%`));
    const mGrid = el("div", "d-act-grid");
    for (const p of MOB_PRESETS) {
      const active = Math.abs(tgtMob - p.val) < 5;
      const b = button(`${p.zh} · ${p.desc}`, async () => {
        const res = await this.ctx.engine.submitCommand({ op: "set_mobilization", value: p.val });
        this.status.textContent = res && res.ok
          ? `✓ 已下达预备役动员令：目标动员率 ${p.val}%`
          : `✗ 动员令未能下达`;
      }, { size: 11, cls: "d-act-btn" + (active ? " active" : "") });
      mGrid.appendChild(b);
    }
    mCard.appendChild(mGrid);
    this.leftCol.appendChild(mCard);
  }

  renderNuclearAndActions(view, m09) {
    this.rightCol.replaceChildren();

    // 1. Dimona Nuclear Posture & Enemy Nuclear Intel (Osirak)
    const nCard = el("div", "d-card");
    const nucProg = view.params.get_val("nuclear_progress", "");
    const iraqNuc = view.params.get_val("enemy_nuclear_progress", "iraq");
    const expRisk = view.params.get_val("nuclear_exposure_risk", "");
    nCard.appendChild(sectionHeader("迪莫纳核计划与敌国核武情报 (M09)", `姿态：核模糊 (${this.nuclearAmbiguity.toUpperCase()})`));

    const iraqRow = el("div", "d-row-item");
    const iraqTop = el("div", "d-row-top");
    const iraqTitle = el("span", "d-row-title");
    iraqTitle.textContent = "伊拉克「奥西拉克」核反应堆进度（达 85% 构成生存威胁，需择机执行巴比伦行动）";
    const iraqVal = el("span", "d-row-val");
    iraqVal.textContent = `${iraqNuc.toFixed(0)}%`;
    iraqTop.append(iraqTitle, iraqVal);
    iraqRow.append(iraqTop, meterBar(iraqNuc, iraqNuc >= 70 ? "red" : "amber"));
    nCard.appendChild(iraqRow);

    const subRow = el("div", "d-subnote");
    subRow.textContent = `战略核能力储备：${nucProg.toFixed(0)}% · 核机密泄露风险（瓦努努/拉卡姆）：${expRisk.toFixed(0)}% · 连续和平月数：${Number(m09.peace_months_streak || 0)} 个月`;
    nCard.appendChild(subRow);
    this.rightCol.appendChild(nCard);

    // 2. Military & Intelligence Actions
    const aCard = el("div", "d-card");
    const pc = view.params.get_val("political_capital", "");
    aCard.appendChild(sectionHeader("参谋本部与情报机构行动指令", `当前政治资本 ${pc.toFixed(0)}`));
    const actGrid = el("div", "d-act-grid");
    const cdMap = (view.raw.modules && view.raw.modules.M05 && view.raw.modules.M05.action_cooldowns) || {};
    const day = Number(view.clock.day_index || 0);
    for (const act of MIL_ACTIONS) {
      const cd = Number(cdMap[act.id] || 0);
      const onCd = cd > day;
      const b = button(
        `${act.zh}（${onCd ? `冷却至第${cd}天` : act.cost}）`,
        async () => {
          const res = await this.ctx.engine.submitCommand({ op: "execute_action", action: act.id });
          this.status.textContent = res && res.ok
            ? `✓ 已下达军事/情报指令：${act.zh}`
            : `✗ 暂不可执行：${act.zh}（${(res && res.result && res.result.error) || "前置条件或政治资本不足"}）`;
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
