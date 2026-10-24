/* Port of game/ui/map/RegionInspectorCard.gd (PanelContainer at (1180,700), 240 wide, grows
 * with its content, hidden until present()).
 *
 * Wired (dead in Godot): shown on region_selected; region_selected("") (empty map click) hides
 * it; the metric numbers are clickable and emit tooltip_requested(param, regionId); refresh(view)
 * keeps the numbers live while open; × closes it.
 * Deviations: posture OptionButton index 0/1/2 is submitted as 20/50/80 (Godot sends the index
 * into a 0–100 param) and is initialised from the live posture; sliders submit on release
 * (`change`) instead of on every value step; the preview uses op "set" (Godot: "add"). */
import { registerReads } from "../../core/StateView.js";
import { el, rect, label, panel, vbox, fmt } from "../../core/controls.js";
import { REGION_IDS } from "./mapGeometry.js";

const METRICS = ["region_security", "region_development", "region_alienation"];
const LEVERS = ["region_absorption_priority", "region_investment_priority", "region_security_posture"];
registerReads(REGION_IDS.flatMap((id) => [...METRICS, ...LEVERS].map((p) => [p, id])));

const POSTURE_VALUES = [20, 50, 80];
const postureIndex = (v) => (v < 35 ? 0 : v < 65 ? 1 : 2);
const LEGAL_STATUS_ZH = {
  sovereign: "以色列主权领土",
  occupied: "军事占领区",
  annexed: "已立法吞并领土",
  security_zone: "边境安全缓冲区",
  returned: "已移交归还",
};

export class RegionInspectorCard {
  constructor(ctx) {
    this.ctx = ctx;
    this.regionId = "";
    this.view = null;
  }

  mount(layer) {
    this.layer = layer;
    const root = rect(panel("region-inspector"), 1180, 700, 1420, null);
    root.style.minHeight = "280px";
    const box = vbox("region-inspector-box");
    this.title = label("", { size: 18, cls: "region-inspector-title" });
    this.body = label("", { autowrap: true });
    this.absLabel = label("阿利亚安置优先级", { size: 12 });
    this.absorption = this._slider("阿利亚安置优先级", "region_absorption_priority");
    this.invLabel = label("基建投资优先级", { size: 12 });
    this.investment = this._slider("基建投资优先级", "region_investment_priority");
    this.posLabel = label("治安管控姿态", { size: 12 });
    this.posture = el("select", "option-button");
    ["缓和", "常规", "高压"].forEach((t, i) => {
      const o = el("option", "", t);
      o.value = String(i);
      this.posture.appendChild(o);
    });
    this.posture.addEventListener("change", () => this._submit("region_security_posture", POSTURE_VALUES[Number(this.posture.value)]));
    this.preview = label("");
    const close = el("button", "btn region-inspector-close", "×");
    close.type = "button";
    close.title = "关闭";
    close.addEventListener("click", () => this.hide());
    box.append(this.title, this.body, this.absLabel, this.absorption, this.invLabel, this.investment, this.posLabel, this.posture, this.preview);
    root.append(box, close);
    root.style.display = "none";
    this.root = root;
    layer.appendChild(root);
  }

  _slider(caption, param) {
    const s = el("input", "hslider");
    s.type = "range";
    s.min = "0";
    s.max = "100";
    s.step = "1";
    s.title = caption;
    s.addEventListener("change", () => this._submit(param, Number(s.value)));
    return s;
  }

  get visible() { return this.root && this.root.style.display !== "none"; }

  hide() {
    if (!this.root) return;
    this.root.style.display = "none";
    this.regionId = "";
  }

  present(regionId, view) {
    if (!this.root) return;
    if (!regionId) { this.hide(); return; }
    const changed = regionId !== this.regionId;
    this.regionId = regionId;
    this.view = view || this.view;
    this.root.style.display = "";
    if (changed) this.preview.textContent = "";
    this._render(true);
  }

  refresh(view) {
    if (!view) return;
    this.view = view;
    if (this.visible) this._render(false);
  }

  _src() {
    const defs = (this.ctx.data.regions && this.ctx.data.regions.regions) || {};
    return defs[this.regionId] || {};
  }

  _metric(param) {
    if (this.view) return this.view.param(param, this.regionId);
    return Number(this._src()[param] || 0);
  }

  _render(syncLevers) {
    const src = this._src();
    const live = (this.view && this.view.modules.M11.regions[this.regionId]) || {};
    this.title.textContent = src.name_zh || this.regionId;
    const status = String(live.legal_status || src.legal_status || "sovereign");
    // "法律地位 %s\n治安 %.1f  发展 %.1f  离异 %.1f" with each number clickable (tooltip_requested).
    this.body.textContent = "";
    this.body.append(fmt("法律地位：%s\n", LEGAL_STATUS_ZH[status] || status));
    const names = ["治安", "发展", "离异"];
    METRICS.forEach((p, i) => {
      const span = el("span", "region-metric", fmt("%s %.1f", names[i], this._metric(p)));
      span.title = p;
      span.addEventListener("click", () => this.ctx.bus.emit("tooltip_requested", p, this.regionId));
      if (i) this.body.append("  ");
      this.body.append(span);
    });
    const dragging = document.activeElement === this.absorption || document.activeElement === this.investment;
    if (syncLevers || !dragging) {
      this.absorption.value = String(this._metric("region_absorption_priority"));
      this.investment.value = String(this._metric("region_investment_priority"));
    }
    if (syncLevers || document.activeElement !== this.posture) {
      this.posture.value = String(postureIndex(this._metric("region_security_posture")));
    }
  }

  async _submit(param, value) {
    const region = this.regionId;
    if (!region) return;
    const cmd = { op: "set_region_priority", region, param, value: Number(value) };
    try {
      const res = await this.ctx.engine.submitCommand(cmd);
      if (res && !res.ok) console.warn("[RegionInspectorCard] command rejected", cmd, res.result);
    } catch (err) {
      console.warn("[RegionInspectorCard] command failed", err);
    }
    try {
      const preview = await this.ctx.sim.preview([{ op: "set", target: param, key: region, value: Number(value) }]);
      if (region === this.regionId) this.preview.textContent = fmt("预览 L1/L2/L3 %s", Object.keys(preview || {}).length);
    } catch (err) {
      console.warn("[RegionInspectorCard] preview failed", err);
    }
  }
}
