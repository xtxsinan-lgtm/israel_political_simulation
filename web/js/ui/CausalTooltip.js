/* Port of game/ui/components/CausalTooltipManager.gd (LockableTooltipPanel at (980,80),
 * 300 wide; VBox: body Label + SparklineDrawer 220x48).
 *
 * Wired (no caller in Godot): opens on bus "tooltip_requested"(paramId, key). Line 1 is
 * "%s = %.2f" (or "%s  %s" with FuzzyBand for fuzzy params), then up to 5 contributions from
 * sim.explain(): "%s %+0.2f" (or ↑/↓/— for fuzzy). Sparkline = sim.history(param, key, 30)
 * (fuzzy -> band centres), dashed warn line at 35 for public_security.
 * Locking goes through UIManager.tooltipStack (max 3) so Esc pops the newest lock; locked
 * cards show "锁定 %d/3  %s" and stay; the unlocked card closes on mouse leave, on a click
 * elsewhere, or when another one opens. Locked cards re-explain once per sim day. */
import { el, rect, label, panel, vbox, hbox, fmt } from "../core/controls.js";
import { FuzzyBand } from "../core/FuzzyBand.js";
import { SparklineDrawer } from "./components/SparklineDrawer.js";

export class CausalTooltipManager {
  constructor(ctx) {
    this.ctx = ctx;
    this.cards = []; // [{id, param, key, root, body, spark, locked, seq}]
    this.seq = 0;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(vbox("causal-tooltips"), 980, 80, 1280, null);
    layer.appendChild(this.root);
    const { bus } = this.ctx;
    bus.connect("tooltip_requested", (param, key) => this.explainNode(param, key || ""));
    bus.connect("tooltip_lock_toggled", (id, locked) => { if (!locked) this._onUnlocked(id); });
    bus.connect("sim_day_advanced", () => this._refreshLocked());
    document.addEventListener("pointerdown", (ev) => {
      const open = this.cards.find((c) => !c.locked);
      if (open && !open.root.contains(ev.target)) this._close(open);
    }, true);
  }

  static tooltipId(param, key) { return key ? `${param}[${key}]` : param; }

  get locked() { return this.cards.filter((c) => c.locked).map((c) => c.id); }

  /** explain_node(state, id) */
  async explainNode(param, key = "") {
    if (!param) return null;
    const id = CausalTooltipManager.tooltipId(param, key);
    const existing = this.cards.find((c) => c.id === id);
    for (const c of this.cards.filter((c) => !c.locked && c.id !== id)) this._close(c);
    const card = existing || this._makeCard(id, param, key);
    return this._fill(card);
  }

  _makeCard(id, param, key) {
    const root = panel("causal-tooltip");
    const head = hbox("causal-tooltip-head");
    const lockLine = label("", { cls: "causal-tooltip-lockline expand-fill" });
    const lockBtn = el("button", "btn causal-tooltip-btn", "锁定");
    lockBtn.type = "button";
    const closeBtn = el("button", "btn causal-tooltip-btn", "×");
    closeBtn.type = "button";
    closeBtn.title = "关闭";
    head.append(lockLine, lockBtn, closeBtn);
    const body = label("…", { autowrap: true, cls: "causal-tooltip-body" });
    const spark = new SparklineDrawer(220, 48);
    root.append(head, body, spark.node);
    const card = { id, param, key, root, body, lockLine, lockBtn, spark, locked: false, seq: 0, entered: false, busy: false };
    lockBtn.addEventListener("click", () => (card.locked ? this._unlock(card) : this.lockTooltip(card)));
    closeBtn.addEventListener("click", () => (card.locked ? this._unlock(card) : this._close(card)));
    root.addEventListener("mouseenter", () => { card.entered = true; });
    root.addEventListener("mouseleave", () => { if (!card.locked && card.entered) this._close(card); });
    this.cards.push(card);
    this.root.appendChild(root);
    this._layout();
    return card;
  }

  async _fill(card) {
    const { sim, engine } = this.ctx;
    const seq = ++this.seq;
    card.seq = seq;
    card.busy = true;
    const fuzzy = FuzzyBand.isFuzzy(card.param);
    const [explained, history] = await Promise.all([
      sim.explain(card.param, card.key || null).catch((err) => { console.warn("[CausalTooltip] explain failed", err); return {}; }),
      sim.history(card.param, card.key || null, 30).catch(() => null),
    ]);
    card.busy = false;
    if (card.seq !== seq || !this.cards.includes(card)) return explained;
    const view = engine.view();
    let current = explained && typeof explained.current === "number" ? explained.current : null;
    if (current === null) current = view ? view.param(card.param, card.key) : 0;
    const lines = [];
    if (fuzzy) lines.push(fmt("%s  %s", card.id, FuzzyBand.describe(current, card.param)));
    else lines.push(fmt("%s = %.2f", card.id, current));
    const top = Array.isArray(explained && explained.top_contributors) ? explained.top_contributors
      : (Array.isArray(explained && explained.top_contributions) ? explained.top_contributions : []);
    for (const row of top.slice(0, 5)) {
      const src = this._sourceLabel(row || {});
      const delta = Number((row && (row.value ?? row.delta_per_tick)) || 0);
      if (fuzzy) lines.push(fmt("%s %s", src, delta > 0 ? "↑" : delta < 0 ? "↓" : "—"));
      else lines.push(fmt("%s %+0.2f", src, delta));
    }
    card.body.textContent = lines.join("\n");
    card.spark.setSeries(this._series(history, card, view, fuzzy), card.param === "public_security" ? 35.0 : -1.0);
    return explained;
  }

  /** source_label_zh | source_id: "param:x" / "lever:x" -> parameters.json zh name if any. */
  _sourceLabel(row) {
    const raw = String(row.source_label_zh || row.source || row.source_id || "");
    const m = /^(?:param|lever):(.+)$/.exec(raw);
    const pid = m ? m[1] : raw;
    const defs = (this.ctx.data.parameters && this.ctx.data.parameters.by_id) || {};
    const def = defs[pid];
    return def && def.zh ? def.zh : raw;
  }

  /** _node_history: last 30 daily values (fuzzy -> band centres). */
  _series(history, card, view, fuzzy) {
    let values = Array.isArray(history) ? history.map((r) => Number(r && r.value)) : [];
    if (values.length < 2 && !card.key && view && view.raw && view.raw.history) {
      // Fallback like Godot's monthly_snapshots: Python history.series.metrics[param] (monthly).
      const metrics = (view.raw.history.series && view.raw.history.series.metrics) || {};
      const vs = Array.isArray(metrics[card.param]) ? metrics[card.param].slice(-30).map(Number) : [];
      if (vs.length >= 2) values = vs;
    }
    values = values.filter((v) => Number.isFinite(v));
    if (fuzzy) values = values.map((v) => FuzzyBand.bandCentre(FuzzyBand.bandIndex(v)));
    return values;
  }

  /** lock_tooltip(id): max 3 through UIManager.tooltipStack; header "锁定 %d/3  %s". */
  lockTooltip(card) {
    if (typeof card === "string") card = this.cards.find((c) => c.id === card);
    if (!card || card.locked) return !!card;
    if (!this.ctx.ui.lockTooltip(card.id)) {
      card.lockBtn.textContent = "已满 3/3";
      setTimeout(() => { if (!card.locked) card.lockBtn.textContent = "锁定"; }, 1200);
      return false;
    }
    card.locked = true;
    this._layout();
    return true;
  }

  _unlock(card) {
    const stack = this.ctx.ui.tooltipStack;
    const i = stack.indexOf(card.id);
    if (i >= 0) {
      stack.splice(i, 1);
      this.ctx.bus.emit("tooltip_lock_toggled", card.id, false);
    } else this._onUnlocked(card.id);
  }

  _onUnlocked(id) {
    const card = this.cards.find((c) => c.id === id);
    if (card) this._close(card);
  }

  _close(card) {
    card.root.remove();
    this.cards = this.cards.filter((c) => c !== card);
    this._layout();
  }

  /** Locked cards first (in lock order), then the transient one. */
  _layout() {
    const stack = this.ctx.ui.tooltipStack;
    const locked = this.cards.filter((c) => c.locked).sort((a, b) => stack.indexOf(a.id) - stack.indexOf(b.id));
    const rest = this.cards.filter((c) => !c.locked);
    locked.forEach((c, i) => {
      c.lockLine.textContent = fmt("锁定 %d/3  %s", i + 1, c.id);
      c.lockBtn.textContent = "解锁";
      c.root.classList.add("locked");
    });
    for (const c of rest) {
      c.lockLine.textContent = "";
      c.lockBtn.textContent = "锁定";
      c.root.classList.remove("locked");
    }
    for (const c of [...locked, ...rest]) this.root.appendChild(c.root);
  }

  _refreshLocked() {
    for (const c of this.cards) if (c.locked && !c.busy) this._fill(c);
  }
}
