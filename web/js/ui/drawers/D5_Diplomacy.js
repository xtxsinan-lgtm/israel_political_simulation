/* Port of game/ui/controllers/drawers/D5_DiplomacyController.gd. us_wh_warmth / us_cong_support
 * are aliased in StateView to the reference relation params (they are undefined in Godot → 0). */
import { label, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";

registerReads([["us_wh_warmth", ""], ["us_cong_support", ""]]);

export class D5DiplomacyController {
  constructor(ctx) { this.ctx = ctx; }

  mount(parent) {
    this.root = document.createElement("div");
    this.root.className = "drawer-body d5-diplomacy";
    this.summary = label("", { size: 16, autowrap: true, cls: "drawer-summary" });
    this.root.appendChild(this.summary);
    parent.appendChild(this.root);
  }

  refresh(view) {
    this.summary.textContent = fmt("白宫 %.0f  国会 %.0f\n苏联配额 / 埃塞俄比亚 / 欧美 / 中东\n埃及 约旦 叙利亚 黎巴嫩",
      view.params.get_val("us_wh_warmth", ""), view.params.get_val("us_cong_support", ""));
  }
}
