/* Port of game/ui/controllers/drawers/D3_CabinetController.gd, enriched with the full M06
 * Cabinet & Security Chiefs roster (Chinese names, party/faction, PM relation, bio preview),
 * active running actions tracker, and categorized M05 player actions. */
import { el, label, button, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { OFFICE_ZH, PARTY_ZH, FACTION_ZH, ACTION_CAT_ZH, charName, charDef, sectionHeader } from "./drawer_helpers.js";

registerReads([["political_capital", ""]]);

const KEY_OFFICES = [
  "prime_minister", "foreign", "defense", "finance", "agriculture", "interior",
  "education", "religious_affairs", "housing", "absorption", "chief_of_staff", "attorney_general",
];

const CAT_TABS = [
  { id: "all", zh: "全部行动" },
  { id: "parl_favr", zh: "议会与党务", cats: ["parl", "favr"] },
  { id: "pers_opin", zh: "内阁与舆论", cats: ["pers", "opin"] },
  { id: "econ_soc", zh: "经济与社会", cats: ["econ", "soc"] },
  { id: "terr", zh: "领土与定居", cats: ["terr"] },
  { id: "dipl_infl", zh: "外交与外围", cats: ["dipl", "infl"] },
  { id: "mil_occ", zh: "军事与占领", cats: ["mil", "occ"] },
  { id: "cent", zh: "宪政与紧急权", cats: ["cent"] },
];

export class D3CabinetController {
  constructor(ctx) {
    this.ctx = ctx;
    this.ministerProposals = [];
    this.activePolicies = [];
    this.actions = [];
    this.fetchedKey = null;
    this.inFlight = false;
    this.lastView = null;
    this.activeCat = "all";
  }

  mount(parent) {
    this.root = el("div", "drawer-body d3-cabinet");
    this.summary = label("", { size: 13, autowrap: true, cls: "drawer-summary d-compact-summary" });
    this.rosterCard = el("div", "d-card");
    this.bioBar = label("提示：点击任意内阁成员可查看人物生平与派系背景；点击下方行动按钮立即下达政令。", { size: 12, autowrap: true, cls: "d3-bio-bar" });
    this.status = label("", { size: 13, cls: "d3-status" });
    this.catBar = el("div", "d-subtabs");
    this.list = el("div", "d3-action-list");
    this.root.append(this.summary, this.rosterCard, this.bioBar, this.status, this.catBar, this.list);
    parent.appendChild(this.root);
  }

  refresh(view) {
    this.lastView = view;
    this.ministerProposals = [];
    this.activePolicies = [];
    let offices = view.modules.M06.offices || {};
    if (!Object.keys(offices).length) offices = view.offices || {};
    const ids = Object.keys(offices).sort();
    for (let i = 0; i < Math.min(6, ids.length); i++) {
      this.ministerProposals.push({ office: ids[i], holder: String(offices[ids[i]]), discount: 0.30 });
    }
    const pol = this.ctx.data.policies || {};
    const policyIds = Object.keys(pol.by_id || {}).sort();
    for (let i = 0; i < Math.min(76, policyIds.length); i++) this.activePolicies.push(policyIds[i]);

    const pc = view.params.get_val("political_capital", "");
    const m05 = (view.raw.modules && view.raw.modules.M05) || {};
    const usedSlots = Number(m05.weekly_slots_used || 0);
    const maxSlots = Number(m05.weekly_slots_max || 2);
    const running = Array.isArray(m05.active_actions) ? m05.active_actions : [];
    const runStr = running.length
      ? " · 执行中：" + running.map((r) => `${r.id}(余${r.remaining_days}天)`).join("、")
      : "";

    this.summary.textContent = fmt(
      "部长提案 %d（批准可享 30%% 政治资本折扣） · 政策 %d · 当前政治资本 %.0f · 本周行动槽 %d/%d%s",
      this.ministerProposals.length, this.activePolicies.length, pc, usedSlots, maxSlots, runStr,
    );

    this.renderRoster(view, offices);
    this.renderCatTabs();
    this.fetchActions(view);
  }

  renderRoster(view, offices) {
    this.rosterCard.replaceChildren();
    this.rosterCard.appendChild(sectionHeader("本届内阁核心成员与军情司法首脑 (M06)", "点击卡片查看人物档案"));
    const grid = el("div", "d3-minister-grid");
    const relMap = (view.raw.params && view.raw.params.relation) || {};

    for (const offId of KEY_OFFICES) {
      const cid = offices[offId];
      const cdef = charDef(this.ctx, cid);
      const nameZh = charName(this.ctx, cid);
      const partyZh = cdef && cdef.party ? (PARTY_ZH[cdef.party] || cdef.party) : "";
      const facZh = cdef && cdef.faction ? (FACTION_ZH[cdef.faction] || cdef.faction) : "";
      const rel = cid && relMap[cid] !== undefined ? Number(relMap[cid]) : (cdef ? Number(cdef.loyalty ?? 65) : 0);

      const cell = el("div", "d3-minister-card clickable");
      const top = el("div", "d3-min-top");
      const roleSpan = el("span", "d3-min-office");
      roleSpan.textContent = OFFICE_ZH[offId] || offId;
      const relSpan = el("span", "d3-min-rel " + (rel >= 65 ? "tone-good" : (rel <= 40 ? "tone-bad" : "")));
      relSpan.textContent = cid ? (offId === "prime_minister" ? "内阁首脑" : `关系 ${rel.toFixed(0)}`) : "空缺";
      top.append(roleSpan, relSpan);

      const bot = el("div", "d3-min-bot");
      const nameSpan = el("span", "d3-min-name");
      nameSpan.textContent = nameZh;
      const metaSpan = el("span", "d3-min-meta");
      metaSpan.textContent = [partyZh, facZh].filter(Boolean).join(" · ");
      bot.append(nameSpan, metaSpan);

      cell.append(top, bot);
      if (cdef) {
        cell.addEventListener("click", () => {
          this.bioBar.textContent = `【${OFFICE_ZH[offId] || offId} · ${nameZh}】(${[partyZh, facZh].filter(Boolean).join(" / ")}) 野心 ${cdef.ambition ?? "-"}：${cdef.bio_zh || "暂无人物简介"}`;
        });
      }
      grid.appendChild(cell);
    }
    this.rosterCard.appendChild(grid);
  }

  renderCatTabs() {
    this.catBar.replaceChildren();
    for (const tab of CAT_TABS) {
      const b = button(tab.zh, () => {
        this.activeCat = tab.id;
        this.renderCatTabs();
        if (this.lastView) this.renderActions(this.lastView);
      }, { size: 12, cls: "d-subtab" + (this.activeCat === tab.id ? " active" : "") });
      this.catBar.appendChild(b);
    }
  }

  async fetchActions(view) {
    const key = view.snap.state_hash || `${view.clock.day_index}`;
    if (key === this.fetchedKey) {
      this.renderActions(view);
      return;
    }
    if (this.inFlight) { this.pendingRefetch = true; return; }
    this.inFlight = true;
    try {
      const actions = await this.ctx.sim.actions();
      this.fetchedKey = key;
      this.actions = Array.isArray(actions) ? actions : [];
      this.renderActions(view);
    } catch (err) {
      console.warn("[D3] actions() failed", err);
    } finally {
      this.inFlight = false;
      if (this.pendingRefetch) {
        this.pendingRefetch = false;
        if (this.lastView) this.fetchActions(this.lastView);
      }
    }
  }

  renderActions(view) {
    const day = Number(view.clock.day_index || 0);
    this.list.replaceChildren();
    const activeTab = CAT_TABS.find((t) => t.id === this.activeCat);
    const allowedCats = activeTab && activeTab.cats ? new Set(activeTab.cats) : null;

    const filtered = allowedCats
      ? this.actions.filter((a) => allowedCats.has(a.cat))
      : this.actions;

    // Show available actions first so actionable buttons are immediately on top
    const sorted = [...filtered].sort((a, b) => (Number(!!b.available) - Number(!!a.available)));

    for (const a of sorted) {
      const pc = a.cost && a.cost.pc !== undefined && a.cost.pc !== null ? Number(a.cost.pc) : 0;
      const dur = a.dur !== null && a.dur !== undefined ? fmt("%d天", a.dur) : "即时";
      const catZh = ACTION_CAT_ZH[a.cat] || a.cat || "";
      let text = fmt("[%s] %s · 资本 %d · %s", catZh, a.zh || a.id, pc, dur);
      const cd = Number(a.cooldown_until || 0);
      if (cd > day) text += fmt(" (冷却至第%d天)", cd);
      const b = button(text, () => this.executeAction(a), { size: 12, cls: "d3-action" });
      b.title = `${a.zh || a.id} (${a.id})${a.note ? "\n" + a.note : ""}`;
      b.dataset.action = a.id;
      b.disabled = !a.available;
      this.list.appendChild(b);
    }
  }

  async executeAction(a) {
    const res = await this.ctx.engine.submitCommand({ op: "execute_action", action: a.id });
    this.fetchedKey = null;
    this.status.textContent = res && res.ok
      ? fmt("✓ 已下达执行：%s", a.zh || a.id)
      : fmt("✗ 未能执行：%s (%s)", a.zh || a.id, (res && res.result && res.result.error) || "条件未满足");
  }
}
