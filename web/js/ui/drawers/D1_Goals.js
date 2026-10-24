/* Port of game/ui/controllers/drawers/D1_GoalsController.gd, enriched with the full M04
 * Three-Layer Goal System (Grand Vision milestones, Campaign Promises, Party Corridor axes)
 * and M11/M13 Constitutional & Trilemma monitors. */
import { el, label, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { AXIS_ZH, BLOC_ZH, sectionHeader, metricCard, meterBar } from "./drawer_helpers.js";

registerReads([
  ["vision_progress", ""],
  ["trilemma", ""],
  ["trilemma_jewish", ""],
  ["trilemma_democratic", ""],
  ["trilemma_territory", ""],
  ["party_standing", ""],
  ["party_cohesion", ""],
  ["cynicism", ""],
  ["rule_of_law", ""],
  ["centralization", ""],
  ["coup_risk", ""],
  ["assassination_risk", ""],
]);

const STAGE_DESC = {
  C1: "C1 常规议会民主",
  C2: "C2 行政扩权争议",
  C3: "C3 司法与总检对抗",
  C4: "C4 紧急法令常态化",
  C5: "C5 宪政停摆/危机体制",
};

const MILESTONE_FALLBACK = [
  { id: "m1_cairo", name_zh: "开罗之路：埃以和约", weight: 25 },
  { id: "m2_rooted", name_zh: "和平生根：南疆无战事", weight: 20 },
  { id: "m3_autonomy", name_zh: "巴勒斯坦自治框架推进", weight: 25 },
  { id: "m4_jordan", name_zh: "约旦河东岸战略默契", weight: 15 },
  { id: "m6_eretz", name_zh: "护栏：保住犹太与撒马利亚定居点", weight: 10 },
  { id: "m7_law", name_zh: "护栏：捍卫法治与议会体面", weight: 5 },
];

export class D1GoalsController {
  constructor(ctx) { this.ctx = ctx; }

  mount(parent) {
    this.root = el("div", "drawer-body d1-goals");
    this.summary = label("", { size: 13, autowrap: true, cls: "drawer-summary d-compact-summary" });
    this.body = el("div", "d-grid-body");
    this.root.append(this.summary, this.body);
    parent.appendChild(this.root);
  }

  refresh(view) {
    const g = (p, k = "") => view.params.get_val(p, k);
    const vision = g("vision_progress");
    const nationalVision = vision < 80.0 ? "完整以色列地" : "愿景里程碑";
    const trilemma = fmt("犹太 %.0f / 民主 %.0f / 领土 %.0f", g("trilemma_jewish"), g("trilemma_democratic"), g("trilemma_territory"));
    const m13 = view.modules.M13 || {};
    const stage = String(m13.centralization_stage ?? "C1");
    const tier = Number(m13.protest_tier ?? m13.social_protest_tier ?? 0);
    this.summary.textContent = fmt("%s 进度 %.0f%%（80%% 终局 +8） · 不可能三角 %s · 集权 %s 抗议 %d",
      nationalVision, vision, trilemma, stage, tier);

    this.body.replaceChildren();

    // 1. Top Banner: Layer 3 Grand Vision + Milestones
    const vRaw = view.raw.vision || {};
    const vTitle = vRaw.name_zh || "以色列地上的和平";
    const vBox = el("div", "d-card");
    vBox.appendChild(sectionHeader(`第三层 · 历史大愿景：「${vTitle}」`, `总进度 ${vision.toFixed(0)}%（达 80% 解锁史诗加成）`));
    vBox.appendChild(meterBar(vision, vision >= 80 ? "green" : "blue"));

    const msGrid = el("div", "d-ms-grid");
    const milestones = (Array.isArray(vRaw.milestones) && vRaw.milestones.length) ? vRaw.milestones : MILESTONE_FALLBACK;
    const held = ((view.raw.modules && view.raw.modules.M04 && view.raw.modules.M04.vision_held_months) || {});
    const egyptPeace = !!(view.flags && (view.flags.egypt_peace_treaty_signed || view.flags.camp_david_signed));
    for (const ms of milestones.slice(0, 6)) {
      const mMonths = Number(held[ms.id] || 0);
      const done = (ms.id === "m1_cairo" && (egyptPeace || mMonths >= 1))
        || (ms.id === "m6_eretz" && g("trilemma_territory") >= 55)
        || (ms.id === "m7_law" && g("rule_of_law") >= 50 && g("centralization") <= 28)
        || mMonths >= 6;
      const chip = el("div", "d-ms-chip" + (done ? " done" : ""));
      chip.textContent = `${done ? "✓" : "○"} ${ms.name_zh || ms.id}${mMonths > 0 && !done ? ` (${mMonths}月)` : ""}`;
      msGrid.appendChild(chip);
    }
    vBox.appendChild(msGrid);
    this.body.appendChild(vBox);

    // 2. Two-column body: Left = Promises & Party Corridor; Right = Trilemma & Constitutional Order
    const cols = el("div", "d-two-col");
    const leftCol = el("div", "d-col");
    const rightCol = el("div", "d-col");

    // Left A: Layer 1 Campaign Promises
    const pCard = el("div", "d-card");
    pCard.appendChild(sectionHeader("第一层 · 竞选承诺兑现进度 (M04)", `选民犬儒度 ${g("cynicism").toFixed(0)}`));
    const promises = Array.isArray(view.raw.promises) ? view.raw.promises : [];
    const promMap = (view.raw.params && view.raw.params.promise_progress) || {};
    if (!promises.length) {
      pCard.appendChild(label("当前无活跃竞选承诺", { size: 12, cls: "d-muted" }));
    } else {
      for (const pr of promises) {
        const pk = pr.id || pr.key || "";
        const prog = Math.max(0, Math.min(100, Number(promMap[pk] ?? pr.progress ?? 0)));
        const row = el("div", "d-row-item");
        const top = el("div", "d-row-top");
        const blocs = Object.keys(pr.blocs || {}).map((b) => BLOC_ZH[b] || b).join("、");
        const nameSpan = el("span", "d-row-title");
        nameSpan.textContent = `${pr.name_zh || pk}${blocs ? `（关切：${blocs}）` : ""}`;
        const valSpan = el("span", "d-row-val");
        valSpan.textContent = `${prog.toFixed(0)}%${prog >= 80 ? " ✓已兑现" : (pr.deadline ? ` · 截止 ${pr.deadline}` : "")}`;
        top.append(nameSpan, valSpan);
        row.append(top, meterBar(prog, prog >= 80 ? "green" : (prog >= 40 ? "amber" : "red")));
        pCard.appendChild(row);
      }
    }
    leftCol.appendChild(pCard);

    // Left B: Layer 2 Party Corridor & PM Health
    const cCard = el("div", "d-card");
    const inCorr = !(view.raw.party_state && view.raw.party_state.in_corridor === false);
    cCard.appendChild(sectionHeader("第二层 · 党内立场走廊与执政根基", inCorr ? "✓ 处于党内走廊内" : "⚠ 偏离党内走廊"));
    const leaderId = (view.raw.player && view.raw.player.leader_id) || "begin";
    const health = Number(((view.raw.params && view.raw.params.health) || {})[leaderId] ?? 80);
    const stress = Number(((view.raw.params && view.raw.params.character_stress) || {})[leaderId] ?? 25);
    const kpiRow = el("div", "d-kpi-grid-4");
    kpiRow.append(
      metricCard(this.ctx, { title: "执政威望", value: g("party_standing").toFixed(0), param: "party_standing", tone: g("party_standing") >= 55 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "党内凝聚", value: g("party_cohesion").toFixed(0), param: "party_cohesion", tone: g("party_cohesion") >= 55 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "总理健康", value: health.toFixed(0), sub: "低于35触发辞职", tone: health >= 50 ? "good" : "bad" }),
      metricCard(this.ctx, { title: "执政压力", value: stress.toFixed(0), sub: "战争/高通胀推升", tone: stress <= 55 ? "good" : "warn" }),
    );
    cCard.appendChild(kpiRow);

    const govPos = (view.raw.params && view.raw.params.gov_axis_position) || view.raw.gov_axis_position || {};
    const axWrap = el("div", "d-axis-list");
    for (const ax of ["territory", "security", "economy", "religion", "foreign"]) {
      const pos = Number(govPos[ax] ?? 0);
      const pill = el("div", "d-axis-pill");
      pill.textContent = `${AXIS_ZH[ax] || ax}: ${pos >= 0 ? "+" : ""}${pos.toFixed(0)}`;
      axWrap.appendChild(pill);
    }
    cCard.appendChild(axWrap);
    leftCol.appendChild(cCard);

    // Right A: National Trilemma (M11)
    const tCard = el("div", "d-card");
    tCard.appendChild(sectionHeader("国家不可能三角 (M11 Trilemma)", `综合均衡度 ${g("trilemma").toFixed(0)}`));
    const triItems = [
      { id: "trilemma_jewish", zh: "犹太国家属性", val: g("trilemma_jewish"), desc: "受人口结构、移民吸收与宗教现状影响" },
      { id: "trilemma_democratic", zh: "民主宪政属性", val: g("trilemma_democratic"), desc: "受法治指数、公民平权与去集权化影响" },
      { id: "trilemma_territory", zh: "领土主权控制", val: g("trilemma_territory"), desc: "受西岸/戈兰/西奈主权与定居点规模影响" },
    ];
    for (const it of triItems) {
      const row = el("div", "d-row-item clickable");
      row.title = "点击查看因果拆解";
      row.addEventListener("click", () => this.ctx.bus.emit("tooltip_requested", it.id, ""));
      const top = el("div", "d-row-top");
      const n = el("span", "d-row-title");
      n.textContent = `${it.zh}（${it.desc}）`;
      const v = el("span", "d-row-val");
      v.textContent = it.val.toFixed(0);
      top.append(n, v);
      row.append(top, meterBar(it.val, it.val >= 60 ? "blue" : "amber"));
      tCard.appendChild(row);
    }
    rightCol.appendChild(tCard);

    // Right B: Constitutional & Authoritarian Monitor (M13)
    const mCard = el("div", "d-card");
    mCard.appendChild(sectionHeader("宪政法治与集权风险监控 (M13)", STAGE_DESC[stage] || stage));
    const mGrid = el("div", "d-kpi-grid-4");
    const rol = g("rule_of_law");
    const cent = g("centralization");
    mGrid.append(
      metricCard(this.ctx, { title: "民主法治指数", value: rol.toFixed(0), param: "rule_of_law", sub: "低于50引发宪政危机", tone: rol >= 60 ? "good" : "bad" }),
      metricCard(this.ctx, { title: "行政集权度", value: cent.toFixed(0), param: "centralization", sub: `${STAGE_DESC[stage] || stage}`, tone: cent < 35 ? "good" : "bad" }),
      metricCard(this.ctx, { title: "政变风险", value: `${g("coup_risk").toFixed(0)}%`, param: "coup_risk", sub: `街头抗议 ${tier} 级`, tone: g("coup_risk") < 20 ? "good" : "bad" }),
      metricCard(this.ctx, { title: "极端暗杀风险", value: `${g("assassination_risk").toFixed(0)}%`, param: "assassination_risk", sub: "政治极化推升", tone: g("assassination_risk") < 20 ? "good" : "bad" }),
    );
    mCard.appendChild(mGrid);

    const actors = (m13.raw && m13.raw.resist_actors) || {};
    const actorIds = Object.keys(actors);
    if (actorIds.length) {
      const aRow = el("div", "d-axis-list");
      for (const aid of actorIds) {
        const a = actors[aid] || {};
        const chip = el("div", "d-axis-pill");
        chip.textContent = `${a.zh || aid}: 独立度 ${Number(a.autonomy ?? 80).toFixed(0)}`;
        aRow.appendChild(chip);
      }
      mCard.appendChild(aRow);
    }
    rightCol.appendChild(mCard);

    cols.append(leftCol, rightCol);
    this.body.appendChild(cols);
  }
}
