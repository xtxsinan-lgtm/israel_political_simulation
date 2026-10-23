/* Port of game/ui/controllers/modals/EventModalController.gd (+ scenes/modals/EventModal.tscn,
 * scenes/modals/OptionPreviewCard.tscn).
 *
 * EventModal: Control (500,200) min 920x400 on ModalLayer; PanelContainer -> VBox:
 *   title Label 18px "%s  %s" % [stamp, title]; RichTextLabel body (codex-linked);
 *   VBox of full-width option Buttons "%s  %s  %s" % [id, preview_l1, lock_reason].
 * Shown by DeskMain on event_modal_requested (engine auto-paused on a queued event).
 * Click -> submit {"op":"resolve_event"}; present the next pending event or hide; stays paused.
 *
 * Web intent fixes (the Godot build leaves these dead / constant):
 *  - body = real event text (summary, else background) instead of the constant default;
 *  - preview_l1 = option title (+ " [史实]" for the historical option): Python options carry no
 *    `summary`, so Godot would print an empty string;
 *  - lock state from the bridge (event_options = evaluate_event_options_for_ui on Python data);
 *  - hovering an option shows an OptionPreviewCard-style "L1 直接代价 / L2 下游区间 / L3 阈值预警"
 *    from sim.preview(effects); fuzzy params only as FuzzyBand words (D-088).
 */
import { el, rect, label, button, panel, vbox, fmt } from "../../core/controls.js";
import { FuzzyBand } from "../../core/FuzzyBand.js";
import { registerReads } from "../../core/StateView.js";
import { CodexAutoLinker } from "./Codex.js";

registerReads([["inflation", ""], ["public_security", ""], ["coalition_seats", ""], ["political_capital", ""]]);

const STAMPS = {
  crisis: "TOP SECRET 加急电报",
  newspaper: "国土报号外",
  chain_milestone: "历史纪念卷宗",
};
const CRISIS_TYPES = new Set(["war", "crisis"]);
const TENSION_ZH = {
  vision_vs_survival: "愿景与执政生存相互拉扯",
  vision_vs_party_corridor: "愿景与党内走廊相互拉扯",
  party_corridor_vs_survival: "党内走廊与执政生存相互拉扯",
};

/** modal_class derived from the Python queue item (Godot M12 sets "major"/"minor"). */
export function modalClassOf(ev) {
  if (ev.modal_class) return String(ev.modal_class);
  if (CRISIS_TYPES.has(String(ev.type || ""))) return "crisis";
  return ev.major ? "major" : "minor";
}

export function stampFor(modalClass) { return STAMPS[modalClass] || "内阁备忘录"; }

export class EventModalController {
  constructor(ctx) {
    this.ctx = ctx;
    this.modal_class = "major";
    this.linker = new CodexAutoLinker(ctx.data && ctx.data.codex_terms);
    this.event = null;
    this.visible = false;
    this.busy = false;
    this.previewCache = new Map();
    this.hoverToken = 0;
    const pdata = (ctx.data && ctx.data.parameters) || {};
    this.paramDefs = pdata.by_id || {};
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(el("div", "event-modal"), 500, 200, 1420, null);
    this.root.id = "EventModal";
    this.root.style.display = "none";
    this.panel = panel("event-modal-panel");
    const column = vbox("event-modal-column");
    this.titleLabel = label("", { size: 18, cls: "event-modal-title" });
    this.body = el("div", "event-modal-body rtl");
    this.cards = vbox("event-modal-cards");
    this.preview = el("div", "option-preview-card");
    this.preview.style.display = "none";
    column.append(this.titleLabel, this.body, this.cards, this.preview);
    this.panel.appendChild(column);
    this.root.appendChild(this.panel);
    layer.appendChild(this.root);
    // Web addition: if the shown event is resolved elsewhere (direct submitCommand, quick load),
    // advance to the next pending event or hide.
    const sync = (view) => this._syncWithView(view);
    this.ctx.bus.connect("snapshot_updated", sync);
    this.ctx.bus.connect("sim_day_advanced", sync);
  }

  _syncWithView(view) {
    if (!this.visible || this.busy || !this.event || !view) return;
    const pending = view.modules.M12.pending_events || [];
    if (pending.some((e) => e.id === this.event.id)) return;
    if (pending.length) this.present(pending[0], view);
    else this.hide();
  }

  present(event, view) {
    if (!event) { this.hide(); return; }
    this.event = event;
    this.view = view || this.ctx.engine.view();
    this.modal_class = modalClassOf(event);
    const stamp = stampFor(this.modal_class);
    this.titleLabel.textContent = "";
    const stampEl = el("span", `ink-stamp event-stamp stamp-${this.modal_class}`, stamp);
    this.titleLabel.append(stampEl, document.createTextNode(fmt("  %s", String(event.title || event.id || ""))));
    const text = String(event.summary || event.background || "大转折正在发生。");
    this.linker.render(this.body, text, (id) => this.ctx.bus.emit("codex_entry_requested", `codex://${id}`));
    this.preview.style.display = "none";
    this.root.style.display = "";
    this.visible = true;
    this.busy = false;
    // Options from the queued instance first (all instantiated options passed `requires`),
    // then refined with the bridge's lock evaluation.
    const rows = (event.options || []).map((o) => ({
      id: String(o.id || "A"), title: String(o.title || ""), historical: !!o.historical,
      available: true, lock_reasons: [], preview_l1: String(o.title || ""), effects: o.effects || [],
    }));
    if (!rows.length) rows.push({ id: "A", available: true, preview_l1: "维持现状", lock_reasons: [], effects: [] });
    this._renderCards(rows);
    const eventId = String(event.id || "");
    const sim = this.ctx.sim;
    this.optionsReady = (sim.eventOptions ? sim.eventOptions(eventId) : Promise.resolve([])).then((list) => {
      if (this.event !== event || !Array.isArray(list) || !list.length) return;
      const effectsById = new Map(rows.map((r) => [r.id, r.effects]));
      this._renderCards(list.map((r) => ({ ...r, effects: effectsById.get(String(r.id)) || [] })));
    }).catch((err) => console.warn("[EventModal] event_options failed", err));
  }

  _renderCards(rows) {
    this.cards.textContent = "";
    const eventId = String(this.event.id || "");
    for (const row of rows) {
      const reasons = Array.isArray(row.lock_reasons) && row.lock_reasons.length ? String(row.lock_reasons[0]) : "";
      const optionId = String(row.id || "A");
      let l1 = String(row.preview_l1 ?? row.title ?? "");
      if (row.historical) l1 += " [史实]";
      const card = button(fmt("%s  %s  %s", optionId, l1, reasons), () => this._choose(eventId, optionId), { cls: "event-option" });
      card.dataset.option = optionId;
      card.disabled = !(row.available ?? true) || this.busy;
      card.addEventListener("mouseenter", () => this._showPreview(row));
      card.addEventListener("focus", () => this._showPreview(row));
      card.addEventListener("mouseleave", () => { this.hoverToken += 1; this.preview.style.display = "none"; });
      this.cards.appendChild(card);
    }
  }

  async _choose(eventId, optionId) {
    if (this.busy) return;
    this.busy = true;
    for (const b of this.cards.querySelectorAll("button")) b.disabled = true;
    let res;
    try {
      res = await this.ctx.engine.submitCommand({ op: "resolve_event", event: eventId, option: optionId });
    } catch (err) {
      res = { ok: false, error: String(err) };
    }
    this.busy = false;
    if (!res || !res.ok) {
      console.warn(`resolve_event ${eventId}/${optionId} failed: ${res && (res.error || JSON.stringify(res.result))}`);
      if (this.event) this.present(this.event, this.ctx.engine.view());
      return;
    }
    this.previewCache.clear();
    const view = this.ctx.engine.view();
    const pending = view ? view.modules.M12.pending_events : [];
    if (pending.length) { this.present(pending[0], view); return; }
    this.hide();
  }

  hide() {
    this.visible = false;
    this.event = null;
    this.hoverToken += 1;
    if (this.root) this.root.style.display = "none";
  }

  // ---------------------------------------------------------------- OptionPreviewCard
  async _showPreview(row) {
    const token = ++this.hoverToken;
    const effects = row.effects || [];
    const view = this.ctx.engine.view() || this.view;
    const key = `${this.event && this.event.id}|${row.id}|${view ? view.clock.day_index : ""}`;
    this._renderPreview(row, view, null);
    this.preview.style.display = "";
    let layers = this.previewCache.get(key);
    if (!layers && effects.length) {
      try {
        layers = await this.ctx.sim.preview(effects);
        this.previewCache.set(key, layers);
      } catch (err) {
        console.warn("[EventModal] preview failed", err);
        layers = null;
      }
    }
    if (token !== this.hoverToken) return;
    this._renderPreview(row, view, layers || {});
  }

  _paramName(id) {
    const d = this.paramDefs[id];
    return (d && d.zh) || id;
  }

  _isFuzzy(id) {
    const d = this.paramDefs[id];
    return FuzzyBand.isFuzzy(id) || (d && d.visible === "fuzzy");
  }

  /** L1: the option's direct effects (exact numbers only for visible, non-fuzzy params). */
  _directCosts(effects, view) {
    const out = [];
    for (const fx of effects) {
      const op = String(fx.op || "");
      const target = String(fx.target || "");
      if ((op === "add" || op === "set" || op === "mul") && target) {
        const name = this._paramName(target) + (fx.key ? `·${fx.key}` : "");
        const v = Number(fx.value ?? 0);
        const d = this.paramDefs[target];
        if (d && d.visible === false) { out.push(`${name} 变化未知`); continue; }
        if (this._isFuzzy(target)) {
          const cur = view ? view.param(target, fx.key || "") : 0;
          const after = op === "add" ? cur + v : op === "mul" ? cur * v : v;
          const arrow = after > cur ? "↑" : after < cur ? "↓" : "—";
          out.push(`${name} ${arrow} ${FuzzyBand.describe(after, target)}`);
          continue;
        }
        if (op === "add") out.push(`${name} ${fmt("%+.1f", v)}`);
        else if (op === "mul") out.push(`${name} ×${fmt("%.2f", v)}`);
        else out.push(`${name} = ${fmt("%.1f", v)}`);
      } else if (op === "add_modifier" && fx.modifier) {
        out.push(`修正 ${fx.modifier}${fx.duration_days ? fmt("（%d天）", fx.duration_days) : ""}`);
      } else if (op === "set_flag" && fx.flag) {
        out.push(`标记 ${fx.flag}`);
      } else if (op === "event_multiplier" && fx.event) {
        out.push(`事件 ${fx.event} 概率 ×${fmt("%.2f", Number(fx.value ?? 1))}`);
      } else if (op) {
        out.push(op === "custom" ? `连锁 ${fx.handler || op}` : op);
      }
    }
    const uniq = [...new Set(out)];
    return uniq.length ? uniq.slice(0, 6).join("；") + (uniq.length > 6 ? " …" : "") : "无直接代价";
  }

  /** L3: tension axes from the preview + crossings of the sim's alert thresholds. */
  _thresholdWarnings(effects, view, layers, row) {
    const warn = [];
    for (const axis of (layers && layers.tension_axes) || []) warn.push(TENSION_ZH[axis] || axis);
    if (view) {
      const delta = (p) => effects.filter((f) => f.op === "add" && f.target === p && !f.key).reduce((s, f) => s + Number(f.value || 0), 0);
      const infl = view.param("inflation"), dI = delta("inflation");
      if (infl < 100 && infl + dI >= 100) warn.push("通胀将越过 100% 红线");
      else if (infl < 50 && infl + dI >= 50) warn.push("通胀将越过 50% 黄线");
      const seats = view.param("coalition_seats"), dS = delta("coalition_seats");
      if (seats >= 61 && seats + dS < 61) warn.push("执政联盟将跌破 61 席");
      const sec = view.param("public_security"), dP = delta("public_security");
      if (sec > 35 && sec + dP <= 35) warn.push("公共安全将跌破 35 红线");
    }
    if (row.risk_hint) warn.push(`风险 ${row.risk_hint}`);
    return warn.length ? warn.join("；") : "暂无阈值预警";
  }

  _renderPreview(row, view, layers) {
    const effects = row.effects || [];
    const l1 = this._directCosts(effects, view);
    let l2 = "推演中…";
    if (layers) {
      const n = (o) => Number((o && o.net_delta) || 0);
      l2 = layers.layer1_goals
        ? fmt("愿景与承诺 %+.1f  党内走廊 %+.1f  执政生存 %+.1f", n(layers.layer1_goals), n(layers.layer2_corridors), n(layers.layer3_survival))
        : "盟党与内阁将按立场作出反应";
    }
    const l3 = layers ? this._thresholdWarnings(effects, view, layers, row) : "推演中…";
    this.preview.textContent = "";
    const lines = [["L1 直接代价", l1], ["L2 下游区间", l2], ["L3 阈值预警", l3]];
    for (const [k, v] of lines) {
      const line = el("div", "preview-line");
      line.append(el("span", "preview-key", k), el("span", "preview-val", v));
      this.preview.appendChild(line);
    }
  }
}
