/* Port of game/ui/controllers/drawers/D4_EconomyController.gd: 8 budget slider lines
 * ("%s %.1f"), "一次性收支 %.2f" (budget_balance), "预算截止倒计时 90 天" and a
 * CausalGraphCanvas focused on "inflation".
 * Intent fixes: slider values come from the real budget_slider param when the key exists
 * (Godot hard-codes 12.5; "tax" is not a budget_slider key so it keeps 12.5); the graph is
 * laid out below the text instead of overlapping it at (0,0). */
import { label, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { CausalGraphCanvas } from "./CausalGraphCanvas.js";

export const SLIDERS = ["defense", "welfare", "infrastructure", "education", "religion", "settlements", "absorption", "tax"];

registerReads([["budget_balance", ""], ...SLIDERS.map((k) => ["budget_slider", k])]);

export class D4EconomyController {
  constructor(ctx) {
    this.ctx = ctx;
    this.shares = {};
    this.graph = new CausalGraphCanvas(ctx);
  }

  mount(parent) {
    this.root = document.createElement("div");
    this.root.className = "drawer-body d4-economy";
    this.summary = label("", { size: 16, autowrap: true, cls: "drawer-summary" });
    this.root.appendChild(this.summary);
    const holder = document.createElement("div");
    holder.className = "d4-graph";
    this.root.appendChild(holder);
    this.graph.mount(holder);
    parent.appendChild(this.root);
  }

  refresh(view) {
    const store = (view.raw.params || {}).budget_slider;
    const lines = [];
    for (const key of SLIDERS) {
      const present = store && typeof store === "object" && store[key] !== undefined && store[key] !== null;
      this.shares[key] = present ? view.param("budget_slider", key) : 12.5;
      lines.push(fmt("%s %.1f", key, this.shares[key]));
    }
    lines.push(fmt("一次性收支 %.2f", view.params.get_val("budget_balance", "")));
    lines.push("预算截止倒计时 90 天");
    this.summary.textContent = lines.join("\n");
    if (this.graph.focusId !== "inflation") this.graph.focusNode("inflation");
  }
}
