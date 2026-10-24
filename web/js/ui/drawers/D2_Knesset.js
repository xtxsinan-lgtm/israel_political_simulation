/* Port of game/ui/controllers/drawers/D2_KnessetController.gd: semicircle seat chart +
 * full Knesset party table (Chinese names, seats, poll_seats, ally_satisfaction, favors),
 * 8 voter bloc support cards, and parliamentary/coalition quick actions. */
import { el, canvas, label, button, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { PARTY_ZH, FACTION_ZH, BLOC_ZH, sectionHeader, metricCard, meterBar } from "./drawer_helpers.js";

const RED = "#B8292E";
const BLUE = "#0038B8";
const AMBER = "#C88A1E";

const BLOCS = ["mizrahi", "liberal_middle", "religious_zionist", "haredi", "labor_ashkenazi", "kibbutz_moshav", "arab_citizens", "russian"];
const PARTY_FACTIONS = [
  { id: "herut_core", zh: "赫鲁特主流（贝京派）", leader: "梅纳赫姆·贝京", defaultW: 38, note: "民族安全与大以色列核心" },
  { id: "liberal_wing", zh: "自由党温和派（埃利希派）", leader: "辛哈·埃利希", defaultW: 32, note: "主张自由市场与世俗温和" },
  { id: "laam", zh: "拉姆国家派（胡尔维茨派）", leader: "伊加尔·胡尔维茨", defaultW: 18, note: "主张财政紧缩与国家统合" },
  { id: "herut_hawks", zh: "以色列地强硬派（科亨派）", leader: "格乌拉·科亨", defaultW: 12, note: "拒绝领土让步，不满意易分裂出走" },
];
const PARL_ACTIONS = [
  { id: "coalition_whip", zh: "强调联合党纪", cost: "盟党满意 -2" },
  { id: "concede_demand", zh: "满足盟党政策诉求", cost: "政治资本 6" },
  { id: "delay_demand", zh: "拖延盟党诉求", cost: "欠盟党人情 1" },
  { id: "coalition_invite", zh: "邀请温和党入阁", cost: "政治资本 15" },
  { id: "knesset_speech", zh: "议会大辩论演说", cost: "政治资本 6" },
  { id: "free_vote", zh: "允许良心自由投票", cost: "政治资本 4" },
  { id: "opposition_talks", zh: "与反对党领袖密谈", cost: "政治资本 8" },
  { id: "call_early_election", zh: "解散议会提前大选", cost: "政治资本 25" },
];

registerReads([
  ["coalition_seats", ""],
  ["poll_lead", ""],
  ["months_to_election", ""],
  ["govt_fatigue", ""],
  ...BLOCS.map((b) => ["bloc_support", b]),
]);

function roundHalfUp(v) { return Math.floor(Number(v) + 0.5); }

export class D2KnessetController {
  constructor(ctx) {
    this.ctx = ctx;
    this.partySeats = {};
    this.coalitionLoyalty = {};
    this.partyPolls = {};
    this.seatDots = 0;
    this.dotColors = [];
  }

  mount(parent) {
    this.root = el("div", "drawer-body d2-knesset");
    const topWrap = el("div", "d2-top-wrap");
    [this.canvas, this.g] = canvas(420, 175);
    this.canvas.classList.add("d2-seat-chart");
    const rightTop = el("div", "d2-top-info");
    this.kpiBar = el("div", "d-kpi-grid-4");
    this.legend = el("div", "d2-legend");
    this.status = label("", { size: 12, cls: "d3-status" });
    rightTop.append(this.kpiBar, this.legend, this.status);
    topWrap.append(this.canvas, rightTop);

    this.cols = el("div", "d-two-col");
    this.partyCol = el("div", "d-col");
    this.blocCol = el("div", "d-col");
    this.cols.append(this.partyCol, this.blocCol);

    this.root.append(topWrap, this.cols);
    parent.appendChild(this.root);
  }

  refresh(view) {
    this.partySeats = {};
    this.coalitionLoyalty = {};
    this.partyPolls = {};
    const seats = view.modules.M03.knesset_seats || view.parliament.knesset_seats || {};
    const pollSeats = (view.raw.params && view.raw.params.poll_seats) || {};
    const allySat = (view.raw.params && view.raw.params.ally_satisfaction) || {};
    const favorParty = (view.raw.params && view.raw.params.favor_party) || {};
    const ids = Object.keys(seats).sort();
    this.seatDots = 0;
    for (const id of ids) {
      const count = roundHalfUp(seats[id]);
      this.partySeats[id] = count;
      this.partyPolls[id] = pollSeats[id] !== undefined ? roundHalfUp(pollSeats[id]) : count;
      this.seatDots += count;
      this.coalitionLoyalty[id] = Number(allySat[id] ?? view.params.get_val("ally_satisfaction", id) ?? 65);
    }
    if (this.seatDots <= 0) this.seatDots = 120;

    const gov = (view.raw.parliament && view.raw.parliament.government) || null;
    const pmParty = (gov && gov.pm_party) || (view.raw.player && view.raw.player.party_id) || "likud";
    const coalitionSet = new Set(gov ? [...(gov.members || []), ...(gov.support || [])] : []);
    this.hasGov = coalitionSet.size > 0;
    const bySeats = (a, b) => (this.partySeats[b] - this.partySeats[a]) || (a < b ? -1 : 1);
    const parties = ids.filter((id) => this.partySeats[id] > 0);
    this.coalition = parties.filter((id) => coalitionSet.has(id)).sort(bySeats);
    this.opposition = parties.filter((id) => !coalitionSet.has(id)).sort(bySeats);
    this.dotColors = [];
    if (this.hasGov) {
      for (const id of this.coalition) {
        const c = id === pmParty ? RED : AMBER;
        for (let k = 0; k < this.partySeats[id]; k++) this.dotColors.push(c);
      }
      for (const id of this.opposition) {
        for (let k = 0; k < this.partySeats[id]; k++) this.dotColors.push(BLUE);
      }
    }
    this.draw();
    this.renderTopInfo(view);
    this.renderPartyTable(view, pmParty, coalitionSet, favorParty);
    this.renderBlocAndActions(view);
  }

  seatTotal() { return this.seatDots; }

  draw() {
    const g = this.g;
    const W = 420, H = 175, cx = 210, cy = 152;
    g.clearRect(0, 0, W, H);
    const total = Math.max(this.seatDots, 1);
    const shown = Math.min(total, 120);
    for (let i = 0; i < shown; i++) {
      const t = i / Math.max(shown - 1, 1);
      const angle = Math.PI * (1.0 - t);
      const radius = 84.0 + (i % 4) * 14.0;
      const x = cx + Math.cos(angle) * radius;
      const y = cy - Math.sin(angle) * radius;
      g.fillStyle = this.hasGov ? (this.dotColors[i] || BLUE) : (i < 61 ? RED : BLUE);
      g.beginPath();
      g.arc(x, y, 3.6, 0, Math.PI * 2);
      g.fill();
    }
    // 61-seat majority line (vertical center mark) & base line
    g.strokeStyle = RED;
    g.lineWidth = 1.5;
    g.beginPath();
    g.moveTo(45, cy + 8);
    g.lineTo(W - 45, cy + 8);
    g.stroke();

    g.fillStyle = "#1E1C1A";
    g.font = "bold 13px sans-serif";
    g.textAlign = "center";
    const coalSeats = this.coalition ? this.coalition.reduce((s, id) => s + this.partySeats[id], 0) : 61;
    g.fillText(`${coalSeats} / 120 席`, cx, cy - 22);
    g.font = "11px sans-serif";
    g.fillStyle = "#736B61";
    g.fillText("过半数线 61 席", cx, cy - 6);
  }

  renderTopInfo(view) {
    this.kpiBar.replaceChildren();
    const coalSeats = view.params.get_val("coalition_seats", "");
    const lead = view.params.get_val("poll_lead", "");
    const mElec = view.params.get_val("months_to_election", "");
    const fat = view.params.get_val("govt_fatigue", "");
    this.kpiBar.append(
      metricCard(this.ctx, { title: "执政联盟席位", value: `${coalSeats.toFixed(0)} 席`, param: "coalition_seats", sub: coalSeats >= 61 ? "✓ 议会过半数" : "⚠ 少数派政府危机", tone: coalSeats >= 61 ? "good" : "bad" }),
      metricCard(this.ctx, { title: "大选民调领先", value: `${lead >= 0 ? "+" : ""}${lead.toFixed(1)}`, param: "poll_lead", sub: "对最大反对党净胜", tone: lead >= 0 ? "good" : "warn" }),
      metricCard(this.ctx, { title: "距法定大选", value: `${mElec.toFixed(0)} 个月`, param: "months_to_election", sub: "满期自动触发大选" }),
      metricCard(this.ctx, { title: "执政疲劳度", value: fat.toFixed(0), param: "govt_fatigue", sub: "长期执政自然累积", tone: fat < 40 ? "good" : "warn" }),
    );

    this.legend.replaceChildren();
    if (!this.hasGov) return;
    const row = (color, title, list) => {
      const sum = list.reduce((s, id) => s + this.partySeats[id], 0);
      const line = el("div", "d2-legend-row");
      const sw = el("span", "d2-swatch");
      sw.style.background = color;
      const names = list.map((id) => `${PARTY_ZH[id] || id} (${this.partySeats[id]})`).join(" · ");
      line.append(sw, label(fmt("%s %d 席：", title, sum), { size: 13, cls: "d2-legend-title" }),
        label(names, { size: 12, autowrap: true }));
      this.legend.appendChild(line);
    };
    row(RED, "执政联盟", this.coalition);
    row(BLUE, "反对派阵营", this.opposition);
  }

  renderPartyTable(view, pmParty, coalitionSet, favorParty) {
    this.partyCol.replaceChildren();
    const card = el("div", "d-card");
    card.appendChild(sectionHeader("第 9 届以色列议会 (Knesset) 政党席位与盟党态度", "点击政党可查满意度因果"));

    const tbl = el("table", "d-table");
    const thead = el("thead");
    thead.innerHTML = "<tr><th>政党名称</th><th>地位</th><th>当前席位</th><th>民调预测</th><th>盟党满意度 / 人情</th></tr>";
    tbl.appendChild(thead);
    const tbody = el("tbody");

    const allParties = [...this.coalition, ...this.opposition];
    for (const pid of allParties) {
      const tr = el("tr", coalitionSet.has(pid) ? "row-coalition" : "row-opposition");
      const isPm = pid === pmParty;
      const isAlly = coalitionSet.has(pid) && !isPm;
      const seats = this.partySeats[pid] || 0;
      const poll = this.partyPolls[pid] ?? seats;
      const diff = poll - seats;
      const diffStr = diff === 0 ? "±0" : (diff > 0 ? `+${diff}` : `${diff}`);
      const sat = this.coalitionLoyalty[pid] || 0;
      const fav = Number(favorParty[pid] || 0);

      const tdName = el("td", "td-bold");
      tdName.textContent = PARTY_ZH[pid] || pid;
      const tdRole = el("td");
      tdRole.innerHTML = isPm
        ? `<span class="d-badge badge-red">执政主党</span>`
        : (isAlly ? `<span class="d-badge badge-amber">执政盟党</span>` : `<span class="d-badge badge-blue">反对党</span>`);
      const tdSeats = el("td", "td-num");
      tdSeats.textContent = `${seats} 席`;
      const tdPoll = el("td", "td-num");
      tdPoll.textContent = `${poll} 席 (${diffStr})`;
      const tdSat = el("td");
      if (isPm) {
        tdSat.textContent = "本党（无需安抚）";
      } else if (isAlly) {
        tdSat.classList.add("clickable");
        tdSat.title = "点击查看该盟党满意度因果拆解";
        tdSat.addEventListener("click", () => this.ctx.bus.emit("tooltip_requested", "ally_satisfaction", pid));
        const favStr = fav !== 0 ? ` · 人情 ${fav > 0 ? "+" + fav : fav}` : "";
        tdSat.textContent = `${sat.toFixed(0)} / 100${sat < 35 ? " ⚠退阁风险" : ""}${favStr}`;
      } else {
        tdSat.textContent = `潜在合作度 ${sat.toFixed(0)}`;
      }
      tr.append(tdName, tdRole, tdSeats, tdPoll, tdSat);
      tbody.appendChild(tr);
    }
    tbl.appendChild(tbody);
    card.appendChild(tbl);
    this.partyCol.appendChild(card);
  }

  renderBlocAndActions(view) {
    this.blocCol.replaceChildren();

    // 0. Ruling Party Internal Factions (M04)
    const fCard = el("div", "d-card");
    const coh = view.params.get_val("party_cohesion", "");
    fCard.appendChild(sectionHeader("执政党（利库德集团）党内四大派系态势 (M04)", `党内凝聚力 ${coh ? coh.toFixed(0) : "58"}`));
    const fMood = (view.raw.params && view.raw.params.faction_mood) || (view.raw.party_state && view.raw.party_state.faction_mood_init) || {};
    const fWeight = (view.raw.params && view.raw.params.faction_weight) || {};
    const fTbl = el("table", "d-table");
    fTbl.innerHTML = "<thead><tr><th>党内派系名称</th><th>派系领袖</th><th>党内权重</th><th>派系满意度</th><th>核心立场</th></tr></thead>";
    const fBody = el("tbody");
    for (const pf of PARTY_FACTIONS) {
      const mood = Number(fMood[pf.id] ?? 55);
      const w = Number(fWeight[pf.id] ?? pf.defaultW);
      const tr = el("tr");
      tr.innerHTML = `
        <td class="td-bold">${pf.zh}</td>
        <td>${pf.leader}</td>
        <td class="td-num">${w.toFixed(0)}%</td>
        <td class="td-num ${mood >= 55 ? "tone-good" : (mood <= 35 ? "tone-bad" : "tone-warn")}">${mood.toFixed(0)} / 100</td>
        <td>${pf.note}</td>
      `;
      fBody.appendChild(tr);
    }
    fTbl.appendChild(fBody);
    fCard.appendChild(fTbl);
    this.blocCol.appendChild(fCard);

    // 1. 8 Voter Blocs
    const bCard = el("div", "d-card");
    bCard.appendChild(sectionHeader("八大选民集团支持度 (M02/M04)", "点击任意选民群体查看支持率涨跌原因"));
    const bGrid = el("div", "d-kpi-grid-4");
    for (const b of BLOCS) {
      const val = view.params.get_val("bloc_support", b);
      bGrid.appendChild(metricCard(this.ctx, {
        title: BLOC_ZH[b] || b,
        value: `${val.toFixed(0)}%`,
        param: "bloc_support",
        key: b,
        tone: val >= 55 ? "good" : (val <= 35 ? "bad" : ""),
      }));
    }
    bCard.appendChild(bGrid);
    this.blocCol.appendChild(bCard);

    // 2. Quick Parliamentary Actions
    const aCard = el("div", "d-card");
    const pc = view.params.get_val("political_capital", "");
    aCard.appendChild(sectionHeader("议会与联盟快捷操作", `当前政治资本 ${pc.toFixed(0)}`));
    const actGrid = el("div", "d-act-grid");
    const cdMap = (view.raw.modules && view.raw.modules.M05 && view.raw.modules.M05.action_cooldowns) || {};
    const day = Number(view.clock.day_index || 0);
    for (const act of PARL_ACTIONS) {
      const cd = Number(cdMap[act.id] || 0);
      const onCd = cd > day;
      const btn = button(
        `${act.zh}（${onCd ? `冷却至第${cd}天` : act.cost}）`,
        async () => {
          const res = await this.ctx.engine.submitCommand({ op: "execute_action", action: act.id });
          this.status.textContent = res && res.ok
            ? `✓ 已执行：${act.zh}`
            : `✗ 无法执行：${act.zh}（${(res && res.result && res.result.error) || "条件或政治资本不足"}）`;
        },
        { size: 12, cls: "d-act-btn" },
      );
      btn.disabled = onCd;
      actGrid.appendChild(btn);
    }
    aCard.appendChild(actGrid);
    this.blocCol.appendChild(aCard);
  }
}
