/* Port of game/ui/controllers/drawers/D3_CabinetController.gd.
 * Summary "部长提案 %d（批准可享 30%% 政治资本折扣）\n政策 %d" (min(6, #offices), min(76, #policies)).
 * Intent fix: execute_action is wired to a list of the player actions from sim.actions(); each
 * button submits {"op":"execute_action","action":id}; unavailable actions are disabled. */
import { label, button, fmt } from "../../core/controls.js";

export class D3CabinetController {
  constructor(ctx) {
    this.ctx = ctx;
    this.ministerProposals = [];
    this.activePolicies = [];
    this.actions = [];
    this.fetchedKey = null;
    this.inFlight = false;
    this.lastView = null;
  }

  mount(parent) {
    this.root = document.createElement("div");
    this.root.className = "drawer-body d3-cabinet";
    this.summary = label("", { size: 16, autowrap: true, cls: "drawer-summary" });
    this.status = label("", { size: 13, cls: "d3-status" });
    this.list = document.createElement("div");
    this.list.className = "d3-action-list";
    this.root.append(this.summary, this.status, this.list);
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
    this.summary.textContent = fmt("部长提案 %d（批准可享 30%% 政治资本折扣）\n政策 %d",
      this.ministerProposals.length, this.activePolicies.length);
    this.fetchActions(view);
  }

  async fetchActions(view) {
    const key = view.snap.state_hash || `${view.clock.day_index}`;
    if (key === this.fetchedKey) return;
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
    for (const a of this.actions) {
      const pc = a.cost && a.cost.pc !== undefined && a.cost.pc !== null ? Number(a.cost.pc) : 0;
      const dur = a.dur !== null && a.dur !== undefined ? fmt("%d天", a.dur) : "即时";
      let text = fmt("%s  政治资本 %d  %s", a.zh || a.id, pc, dur);
      const cd = Number(a.cooldown_until || 0);
      if (cd > day) text += fmt("  冷却至第%d天", cd);
      const b = button(text, () => this.executeAction(a), { size: 13, cls: "d3-action" });
      b.title = `${a.id} · ${a.cat || ""}${a.note ? " · " + a.note : ""}`;
      b.dataset.action = a.id;
      b.disabled = !a.available;
      this.list.appendChild(b);
    }
  }

  async executeAction(a) {
    const res = await this.ctx.engine.submitCommand({ op: "execute_action", action: a.id });
    this.status.textContent = res && res.ok
      ? fmt("已提交：%s", a.zh || a.id)
      : fmt("未执行：%s  %s", a.zh || a.id, (res && res.result && res.result.error) || "");
  }
}
