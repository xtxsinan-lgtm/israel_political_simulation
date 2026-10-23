/* Port of game/ui/controllers/drawers/D7_MilitaryIntelController.gd: summary Label with the
 * crt_scanline shader (CSS class .crt-scanline from theme.css). */
import { label, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";

registerReads([["mobilization", ""], ["intel_accuracy", ""]]);

export class D7MilitaryIntelController {
  constructor(ctx) {
    this.ctx = ctx;
    this.mobilizationLevel = 0;
    this.frontStatus = {};
    this.nuclearAmbiguity = "opaque";
    this.intelQuality = 0.0;
  }

  mount(parent) {
    this.root = document.createElement("div");
    this.root.className = "drawer-body d7-military";
    this.summary = label("", { size: 16, autowrap: true, cls: "drawer-summary crt-scanline" });
    this.root.appendChild(this.summary);
    parent.appendChild(this.root);
  }

  refresh(view) {
    this.mobilizationLevel = Math.floor(view.params.get_val("mobilization", "") + 0.5);
    this.intelQuality = view.params.get_val("intel_accuracy", "");
    this.nuclearAmbiguity = "opaque";
    const fronts = (view.modules.M09 && view.modules.M09.fronts) || {};
    this.frontStatus = {};
    for (const id of Object.keys(fronts).sort()) {
      const f = fronts[id];
      this.frontStatus[id] = String((f && typeof f === "object" && f.status) || "PEACE");
    }
    this.summary.textContent = fmt("动员 %d  情报 %.1f  核模糊 %s  战线 %d",
      this.mobilizationLevel, this.intelQuality, this.nuclearAmbiguity, Object.keys(this.frontStatus).length);
  }
}
