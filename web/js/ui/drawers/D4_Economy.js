/* Port of game/ui/controllers/drawers/D4_EconomyController.gd, implementing the full
 * M15_ui_presentation.md §9.2 D4_POLICY_BUDGET specification:
 *  - 页签0 [政策与矛盾因果网]: 5 Core Policy Levers (direct multi-tier buttons) +
 *    7 Deep Social Contradictions & Historical Debts (hover/click to draw Democracy 4 causal net) +
 *    3-column Chinese CausalGraphCanvas.
 *  - 页签1 [财政与年度预算案]: 6 Macro Indicators + strike_risk + absorption_capacity +
 *    Fiscal Ledger breakdown + 8 Annual Budget Sliders (0..100, % share, marginal impact preview,
 *    discrete tier buttons + slider) + budget_cycle status & [向议会提交年度预算案表决]. */
import { el, label, button, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { CausalGraphCanvas } from "./CausalGraphCanvas.js";
import { BUDGET_ZH, paramZh, sectionHeader, metricCard, rangeSlider } from "./drawer_helpers.js";

export const SLIDERS = ["defense", "welfare", "infrastructure", "education", "religion", "settlements", "absorption", "tax"];
const REAL_BUDGET_KEYS = ["defense", "absorption", "religion", "dev_towns", "education", "welfare", "infrastructure", "settlements"];

const FIVE_CORE_LEVERS = [
  { id: "settlement_policy", zh: "定居点扩张政策", tags: ["-2 全面冻结", "-1 仅加厚现有", "0 阿隆框架", "+1 全面扩张", "+2 德罗布莱斯计划"] },
  { id: "fx_regime", zh: "经济与外汇体制", tags: ["-1 全面外汇管制", "0 有管理浮动", "+1 自由浮动(埃利希改革)"] },
  { id: "exemption_coverage", zh: "宗教现状(兵役豁免)", tags: ["-1 收紧须服役", "0 维持年度上限", "+1 取消人数上限", "+2 全面豁免"] },
  { id: "arab_local_budget", zh: "阿拉伯公民拨款", tags: ["-1 低于犹太城镇一半", "0 现行(约六成)", "+1 缩小差距(八成)", "+2 平权等额拨款"] },
  { id: "emergency_regs_use", zh: "安全与紧急状态条例", tags: ["-1 最低克制", "0 现行常规审查", "+1 扩大(以条例代立法)"] },
];

const BUDGET_MARGINAL_PREVIEW = {
  defense: "边际效应：战备与威慑 ▲ | 外汇消耗与财政赤字 ▲",
  absorption: "边际效应：移民吸收容量 ▲ | 俄裔/埃塞移民支持 ▲",
  religion: "边际效应：宗教党(NRP/阿古达)满意度 ▲▲ | 世俗中产支持 ▼",
  dev_towns: "边际效应：米兹拉希疏离度 ▼ | 内盖夫/加利利发展 ▲",
  education: "边际效应：长期GDP增长 ▲ | 世俗中产与劳工支持 ▲",
  welfare: "边际效应：贫富差距与罢工风险 ▼ | 财政支出压力 ▲",
  infrastructure: "边际效应：GDP增长与区域发展 ▲ | 吸收容量 ▲",
  settlements: "边际效应：定居者动量与右翼满意 ▲▲ | 美国白宫关系 ▼",
};

registerReads([
  ["budget_balance", ""],
  ["public_debt", ""],
  ["fx_reserves", ""],
  ["inflation", ""],
  ["growth", ""],
  ["unemployment", ""],
  ["strike_risk", ""],
  ["absorption_capacity", ""],
  ["religious_status_quo", ""],
  ["draft_exemption", ""],
  ["alienation", "mizrahi"],
  ["historical_grievance", "mizrahi"],
  ["civic_identification", "arab"],
  ["land_grievance", "arab"],
  ["pal_hostility", ""],
  ["uprising_risk", ""],
  ["trilemma", ""],
  ["settler_momentum", ""],
  ["economic_model", ""],
  ["inequality", ""],
  ["union_strength", ""],
  ["rule_of_law", ""],
  ["public_security", ""],
  ["political_capital", ""],
  ...REAL_BUDGET_KEYS.map((k) => ["budget_slider", k]),
]);

export class D4EconomyController {
  constructor(ctx) {
    this.ctx = ctx;
    this.shares = {};
    this.activeTab = 0; // 0: 政策杠杆与七大社会矛盾网, 1: 宏观经济与财政预算案
    this.graph = new CausalGraphCanvas(ctx, () => this._updateGraphHeader());
    this.lastView = null;
  }

  mount(parent) {
    this.root = el("div", "drawer-body d4-economy");

    // Top bar: Sub-tabs [页签0: 政策杠杆与社会矛盾因果网] [页签1: 宏观经济与年度财政预算案] + summary
    const topBar = el("div", "d4-tab-bar");
    this.tabBtn0 = button("页签0：五大政策杠杆与七大社会矛盾因果网", () => this.switchTab(0), { size: 12, cls: "d-subtab active" });
    this.tabBtn1 = button("页签1：宏观经济指标与八大年度财政预算案", () => this.switchTab(1), { size: 12, cls: "d-subtab" });
    this.status = label("", { size: 12, cls: "d3-status" });
    topBar.append(this.tabBtn0, this.tabBtn1, this.status);

    this.summary = label("", { size: 12, autowrap: true, cls: "drawer-summary d-compact-summary" });

    // Tab 0 Container: 5 Core Levers + 7 Contradictions + CausalGraphCanvas
    this.tab0Wrap = el("div", "d-grid-body");
    this.leversCard = el("div", "d-card");
    this.contradictionsCard = el("div", "d-card");
    this.graphCard = el("div", "d-card d4-graph-card");
    this.graphHdr = sectionHeader("Democracy 4 式加权因果网络 (M02 Causal Net)", "悬停或点击上方任一矛盾/指标即可绘制因果连线");
    const holder = el("div", "d4-graph");
    this.graph.mount(holder);
    this.graphCard.append(this.graphHdr, holder);
    this.tab0Wrap.append(this.leversCard, this.contradictionsCard, this.graphCard);

    // Tab 1 Container: 8 Macro KPIs + Fiscal Waterfall + 8 Budget Sliders + Budget Cycle Submission
    this.tab1Wrap = el("div", "d-grid-body");
    this.tab1Wrap.style.display = "none";
    this.macroCard = el("div", "d-card");
    this.budgetCard = el("div", "d-card");
    this.cycleCard = el("div", "d-card");
    this.tab1Wrap.append(this.macroCard, this.budgetCard, this.cycleCard);

    this.root.append(topBar, this.summary, this.tab0Wrap, this.tab1Wrap);
    parent.appendChild(this.root);
  }

  switchTab(idx) {
    this.activeTab = idx;
    this.tabBtn0.classList.toggle("active", idx === 0);
    this.tabBtn1.classList.toggle("active", idx === 1);
    this.tab0Wrap.style.display = idx === 0 ? "" : "none";
    this.tab1Wrap.style.display = idx === 1 ? "" : "none";
    if (this.lastView) this.refresh(this.lastView);
  }

  selectFocus(nodeId, key = "", openTooltip = true) {
    this.graph.focusNode(nodeId);
    this._updateGraphHeader();
    if (openTooltip) this.ctx.bus.emit("tooltip_requested", nodeId, key);
  }

  _updateGraphHeader() {
    if (!this.graphHdr) return;
    const fZh = paramZh(this.ctx, this.graph.focusId);
    const sub = this.graphHdr.querySelector(".d-sec-sub");
    if (sub) sub.textContent = `当前聚焦：【${fZh} (${this.graph.focusId})】 · 点击图上任意圆圈可顺藤摸瓜切换焦点`;
  }

  refresh(view) {
    this.lastView = view;
    this.graph.setView(view);
    const store = (view.raw.params || {}).budget_slider || {};
    for (const key of SLIDERS) {
      const present = store && typeof store === "object" && store[key] !== undefined && store[key] !== null;
      this.shares[key] = present ? view.param("budget_slider", key) : 12.5;
    }
    if (!this.graph.focusId) this.graph.focusNode("inflation");

    const m10 = (view.raw.modules && view.raw.modules.M10) || {};
    const bc = m10.budget_cycle || {};
    const ledger = m10.last_fiscal_ledger || {};
    const day = Number(view.clock.day_index || 0);
    const dueDay = Number(bc.deadline_day || 90);
    const leftDays = Math.max(0, dueDay - (day % 365));

    this.summary.textContent = fmt(
      "宏观与政策总览：通胀 %.1f%% · 外汇 %.0f · 一次性收支 %.2f（税收 %.1f + 美援 %.1f − 滑块支出 %.1f − 债务利息 %.1f） · 预算截止倒计时 %d 天",
      view.params.get_val("inflation", ""),
      view.params.get_val("fx_reserves", ""),
      view.params.get_val("budget_balance", ""),
      Number(ledger.tax_revenue ?? 7.8),
      Number(ledger.us_aid_grant ?? 0.6),
      Number(ledger.slider_expenditure ?? 8.7),
      Number(ledger.debt_service ?? 1.0),
      leftDays,
    );

    this.renderFiveCoreLevers(view);
    this.renderSevenContradictions(view);
    this._updateGraphHeader();
    this.graph.draw();

    this.renderMacroSection(view, ledger);
    this.renderBudgetSlidersSection(view, store);
    this.renderBudgetCycleSection(view, bc, leftDays);
  }

  renderFiveCoreLevers(view) {
    this.leversCard.replaceChildren();
    const pc = view.params.get_val("political_capital", "");
    this.leversCard.appendChild(sectionHeader(
      "■ 五大核心政策杠杆 (Policy Levers - 点击目标档位消耗政治资本调整)",
      `当前政治资本：${pc.toFixed(0)}`,
    ));

    const polDefs = (this.ctx.data.policies && this.ctx.data.policies.by_id) || {};
    const polState = view.policies || {};
    const day = Number(view.clock.day_index || 0);
    const list = el("div", "d4-lever-table");

    for (const item of FIVE_CORE_LEVERS) {
      const pdef = polDefs[item.id] || {};
      const pst = polState[item.id] || {};
      const tiers = Array.isArray(pdef.tiers) ? pdef.tiers : [];
      const curIdx = Number(pst.tier_idx ?? 0);
      const costPc = Number(pdef.pc ?? 8);
      const cdDay = Number(pst.cooldown_until_day || 0);
      const onCd = cdDay > day;

      const row = el("div", "d4-lever-row");
      const nameBox = el("div", "d4-lever-label");
      const titleSpan = el("span", "d4-pol-name");
      titleSpan.textContent = `• ${item.zh}`;
      const metaSpan = el("span", "d4-pol-tier");
      metaSpan.textContent = onCd ? `冷却至第${cdDay}天` : `耗资本 ${costPc}`;
      nameBox.append(titleSpan, metaSpan);

      const tierBar = el("div", "d4-tier-bar");
      tiers.forEach((t, idx) => {
        const isCur = idx === curIdx;
        const labelTxt = item.tags[idx] || t.zh || `档位${idx}`;
        const btn = button(
          `${isCur ? "● " : ""}${labelTxt}`,
          async () => {
            if (isCur) return;
            const res = await this.ctx.engine.submitCommand({ op: "adjust_policy", policy: item.id, tier: idx });
            this.status.textContent = res && res.ok
              ? `✓ 已将「${item.zh}」调至：${labelTxt}`
              : `✗ 无法调档：${(res && res.result && res.result.error) || "政治资本不足或冷却中"}`;
          },
          { size: 11, cls: "d4-tier-btn" + (isCur ? " active" : "") },
        );
        btn.disabled = !isCur && (onCd || pc < costPc);
        btn.title = `${pdef.zh || item.zh} → ${t.zh || labelTxt}（消耗 ${costPc} 政治资本）`;
        tierBar.appendChild(btn);
      });

      row.append(nameBox, tierBar);
      list.appendChild(row);
    }
    this.leversCard.appendChild(list);
  }

  renderSevenContradictions(view) {
    this.contradictionsCard.replaceChildren();
    this.contradictionsCard.appendChild(sectionHeader(
      "■ 七大深层社会矛盾与历史债务 (Contradictions & Historical Debts)",
      "点击或悬停任一矛盾节点，下方即时绘制红绿加权因果连线",
    ));

    const g = (p, k = "") => view.params.get_val(p, k);
    const rows = [
      {
        tag: "矛盾1 · 世俗与宗教",
        nodes: [
          { param: "religious_status_quo", key: "", zh: "宗教现状倾斜", val: `${g("religious_status_quo") >= 0 ? "+" : ""}${g("religious_status_quo").toFixed(0)}` },
          { param: "draft_exemption", key: "", zh: "★历史债务：兵役豁免规模", val: `${g("draft_exemption").toFixed(0)}`, debt: true },
        ],
      },
      {
        tag: "矛盾2 · 族群与移民",
        nodes: [
          { param: "alienation", key: "mizrahi", zh: "米兹拉希疏离度", val: `${g("alienation", "mizrahi").toFixed(0)}` },
          { param: "historical_grievance", key: "mizrahi", zh: "★历史债务：族群历史怨气", val: `${g("historical_grievance", "mizrahi").toFixed(0)}`, debt: true },
        ],
      },
      {
        tag: "矛盾3 · 阿拉伯公民",
        nodes: [
          { param: "civic_identification", key: "arab", zh: "国家认同度", val: `${g("civic_identification", "arab").toFixed(0)}` },
          { param: "land_grievance", key: "arab", zh: "★历史债务：土地征用怨气", val: `${g("land_grievance", "arab").toFixed(0)}`, debt: true },
        ],
      },
      {
        tag: "矛盾4 · 巴以与占领",
        nodes: [
          { param: "pal_hostility", key: "", zh: "巴方民间敌意", val: `${g("pal_hostility").toFixed(0)}` },
          { param: "uprising_risk", key: "", zh: "起义风险指数", val: `${g("uprising_risk").toFixed(0)}` },
        ],
      },
      {
        tag: "矛盾5 · 领土与定居",
        nodes: [
          { param: "trilemma", key: "", zh: "三难三角均衡度", val: `${g("trilemma").toFixed(0)}` },
          { param: "settler_momentum", key: "", zh: "定居者运动动量", val: `${g("settler_momentum").toFixed(0)}` },
        ],
      },
      {
        tag: "矛盾6 · 经济与劳资",
        nodes: [
          { param: "economic_model", key: "", zh: "经济体制坐标", val: `${g("economic_model") >= 0 ? "+" : ""}${g("economic_model").toFixed(0)}` },
          { param: "inequality", key: "", zh: "贫富差距", val: `${g("inequality").toFixed(0)}` },
          { param: "union_strength", key: "", zh: "总工会实力", val: `${g("union_strength").toFixed(0)}` },
        ],
      },
      {
        tag: "矛盾7 · 安全与法治",
        nodes: [
          { param: "rule_of_law", key: "", zh: "民主法治指数", val: `${g("rule_of_law").toFixed(0)}` },
          { param: "public_security", key: "", zh: "公众安全感", val: `${g("public_security").toFixed(0)}` },
          { param: "inflation", key: "", zh: "通货膨胀率", val: `${g("inflation").toFixed(1)}%` },
        ],
      },
    ];

    const grid = el("div", "d4-contra-grid");
    for (const r of rows) {
      const box = el("div", "d4-contra-row");
      const tagEl = el("span", "d4-contra-tag");
      tagEl.textContent = r.tag;
      box.appendChild(tagEl);

      const pills = el("div", "d4-contra-pills");
      for (const n of r.nodes) {
        const isFocus = this.graph.focusId === n.param;
        const pill = el("button", "btn d4-contra-pill" + (isFocus ? " active" : "") + (n.debt ? " debt" : ""));
        pill.type = "button";
        pill.textContent = `${n.zh}: ${n.val}`;
        pill.title = "点击查看因果拆解并在下方绘制因果网";
        pill.addEventListener("mouseenter", () => {
          if (this.graph.focusId !== n.param) {
            this.graph.focusNode(n.param);
            this._updateGraphHeader();
          }
        });
        pill.addEventListener("click", () => this.selectFocus(n.param, n.key, true));
        pills.appendChild(pill);
      }
      box.appendChild(pills);
      grid.appendChild(box);
    }
    this.contradictionsCard.appendChild(grid);
  }

  renderMacroSection(view, ledger) {
    this.macroCard.replaceChildren();
    const g = (p) => view.params.get_val(p, "");
    const inf = g("inflation");
    const fx = g("fx_reserves");
    const bb = g("budget_balance");
    const debt = g("public_debt");
    const gro = g("growth");
    const unemp = g("unemployment");
    const strike = g("strike_risk");
    const abs = g("absorption_capacity");

    this.macroCard.appendChild(sectionHeader(
      "■ 宏观经济六大核心指标与社会承载力 (M10 Macro Indicators)",
      "点击任意指标卡可跳转至页签0查看其因果传导网",
    ));

    const kpiGrid = el("div", "d-kpi-grid-8");
    const items = [
      { id: "budget_balance", title: "财政收支", value: `${bb >= 0 ? "+" : ""}${bb.toFixed(1)}`, sub: bb <= -6 ? "⚠ 赤字失控" : "占GDP比重", tone: bb >= -2.5 ? "good" : (bb <= -6 ? "bad" : "warn") },
      { id: "public_debt", title: "公共债务", value: `${debt.toFixed(0)}%`, sub: "占GDP存量", tone: debt >= 130 ? "bad" : "warn" },
      { id: "fx_reserves", title: "外汇储备", value: fx.toFixed(0), sub: fx <= 20 ? "⚠ 违约危机" : "进口护垫", tone: fx <= 20 ? "bad" : (fx >= 40 ? "good" : "warn") },
      { id: "inflation", title: "通货膨胀", value: `${inf.toFixed(1)}%`, sub: inf >= 80 ? "⚠ 恶性通胀" : "年化涨幅", tone: inf >= 80 ? "bad" : (inf >= 45 ? "warn" : "good") },
      { id: "growth", title: "经济增长", value: `${gro.toFixed(1)}%`, sub: "实际GDP增速", tone: gro >= 2.5 ? "good" : (gro < 0 ? "bad" : "") },
      { id: "unemployment", title: "城镇失业率", value: `${unemp.toFixed(1)}%`, sub: "全国失业占比", tone: unemp <= 5 ? "good" : (unemp >= 8 ? "bad" : "warn") },
      { id: "strike_risk", title: "罢工风险", value: `${strike.toFixed(0)}%`, sub: "总工会动员度", tone: strike >= 65 ? "bad" : "good" },
      { id: "absorption_capacity", title: "吸收容量", value: abs.toFixed(0), sub: "移民安置承载", tone: abs >= 50 ? "good" : "warn" },
    ];

    for (const it of items) {
      kpiGrid.appendChild(metricCard(this.ctx, {
        title: it.title,
        value: it.value,
        sub: it.sub,
        tone: it.tone,
        onClick: () => {
          this.selectFocus(it.id, "", true);
          this.switchTab(0);
        },
      }));
    }
    this.macroCard.appendChild(kpiGrid);

    // Victoria 3 style fiscal waterfall breakdown bar
    const tax = Number(ledger.tax_revenue ?? 7.83);
    const aid = Number(ledger.us_aid_grant ?? 0.60);
    const exp = Number(ledger.slider_expenditure ?? 8.71);
    const dSrv = Number(ledger.debt_service ?? 0.96);
    const tanzi = Number(ledger.tanzi_erosion ?? 0.70);
    const wf = el("div", "d4-waterfall");
    wf.innerHTML = `
      <span class="tone-good"><b>总收入 +${(tax + aid).toFixed(2)}</b>（国内税收 +${tax.toFixed(2)} · 美国经援 +${aid.toFixed(2)}）</span>
      <span> vs </span>
      <span class="tone-bad"><b>总支出 −${(exp + dSrv + tanzi).toFixed(2)}</b>（八大预算项 −${exp.toFixed(2)} · 债务利息 −${dSrv.toFixed(2)} · 坦齐通胀侵蚀 −${tanzi.toFixed(2)}）</span>
      <span> ➔ <b>月度净结余 ${bb >= 0 ? "+" : ""}${bb.toFixed(2)}</b></span>
    `;
    this.macroCard.appendChild(wf);
  }

  renderBudgetSlidersSection(view, store) {
    this.budgetCard.replaceChildren();
    const totalPoints = REAL_BUDGET_KEYS.reduce((s, k) => s + Number(store[k] ?? 50), 0) || 1;
    this.budgetCard.appendChild(sectionHeader(
      "■ 八大年度国家预算滑块 (Annual Budget Sliders - 拖动滑块或点选档位)",
      "实时显示占总预算比例与对盟党/宏观指标的边际效应",
    ));

    const list = el("div", "d4-slider-list");
    const TIER_PRESETS = [
      { v: 25, zh: "紧缩" },
      { v: 40, zh: "偏低" },
      { v: 55, zh: "常规" },
      { v: 70, zh: "倾斜" },
      { v: 85, zh: "重点" },
    ];

    for (const key of REAL_BUDGET_KEYS) {
      const val = Number(store[key] ?? view.param("budget_slider", key) ?? 50);
      const pct = (val / totalPoints) * 100;
      const meta = BUDGET_ZH[key] || { zh: key, desc: "" };
      const previewTxt = BUDGET_MARGINAL_PREVIEW[key] || meta.desc;

      const row = el("div", "d4-slider-card");
      const top = el("div", "d4-slider-top");
      const nameSpan = el("span", "d4-slider-name");
      nameSpan.textContent = `${meta.zh}`;
      const valSpan = el("span", "d4-slider-val");
      valSpan.textContent = `档位 ${val.toFixed(0)}/100 · 占预算 ${pct.toFixed(1)}%`;
      top.append(nameSpan, valSpan);

      const sub = el("div", "d4-slider-preview");
      sub.textContent = previewTxt;

      const ctrlRow = el("div", "d4-slider-ctrls");
      const input = rangeSlider(0, 100, val, 5, async (newVal) => {
        await this._applyBudgetSlider(key, meta.zh, newVal);
      });
      ctrlRow.appendChild(input);

      const tierBtns = el("div", "d4-slider-tiers");
      for (const tp of TIER_PRESETS) {
        const active = Math.abs(val - tp.v) <= 5;
        const b = button(tp.zh, () => this._applyBudgetSlider(key, meta.zh, tp.v), {
          size: 10,
          cls: "d4-mini-tier" + (active ? " active" : ""),
        });
        b.title = `将「${meta.zh}」设为 ${tp.v}（${previewTxt}）`;
        tierBtns.appendChild(b);
      }
      ctrlRow.appendChild(tierBtns);

      row.append(top, sub, ctrlRow);
      list.appendChild(row);
    }
    this.budgetCard.appendChild(list);
  }

  async _applyBudgetSlider(key, zh, newVal) {
    const res = await this.ctx.engine.submitCommand({ op: "set_budget_slider", slider: key, value: newVal });
    this.status.textContent = res && res.ok
      ? `✓ 已将「${zh}」预算拨款调至 ${newVal.toFixed(0)}`
      : `✗ 预算调整未生效`;
  }

  renderBudgetCycleSection(view, bc, leftDays) {
    this.cycleCard.replaceChildren();
    const st = String(bc.status || "PASSED");
    const stZh = st === "PASSED" ? "✓ 已通过 (PASSED)" : (st === "DUE" ? "⚠ 待呈议会表决 (DUE)" : "❗ 逾期危机 (OVERDUE)");
    this.cycleCard.appendChild(sectionHeader(
      `■ 年度预算周期状态：${stZh}`,
      `距离预算案截止日剩余：${leftDays} 天（财年 ${bc.fiscal_year || view.clock.year}）`,
    ));

    const actRow = el("div", "d-act-grid-4");
    const econActs = [
      { id: "submit_budget", zh: "📜 向议会提交年度预算案表决", primary: true },
      { id: "package_deal", zh: "🤝 与总工会签一揽子稳物价协议" },
      { id: "emergency_cut", zh: "✂ 紧急削减政府开支" },
      { id: "stabilization_plan", zh: "🛡 启动全面经济稳定计划" },
    ];
    for (const a of econActs) {
      const b = button(a.zh, async () => {
        const res = await this.ctx.engine.submitCommand({ op: "execute_action", action: a.id });
        this.status.textContent = res && res.ok
          ? `✓ 已下达执行：${a.zh}`
          : `✗ 暂不可执行：${a.zh}（${(res && res.result && res.result.error) || "未到预算期或政治资本不足"}）`;
      }, { size: 12, cls: "d-act-btn" + (a.primary ? " active" : "") });
      actRow.appendChild(b);
    }
    this.cycleCard.appendChild(actRow);
  }
}
