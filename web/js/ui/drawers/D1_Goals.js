/* Port of game/ui/controllers/drawers/D1_GoalsController.gd (Control min 920x400, autowrap Label). */
import { label, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";

registerReads([["vision_progress", ""], ["trilemma_jewish", ""], ["trilemma_democratic", ""], ["trilemma_territory", ""]]);

export class D1GoalsController {
  constructor(ctx) { this.ctx = ctx; }

  mount(parent) {
    this.root = document.createElement("div");
    this.root.className = "drawer-body d1-goals";
    this.summary = label("", { size: 16, autowrap: true, cls: "drawer-summary" });
    this.root.appendChild(this.summary);
    parent.appendChild(this.root);
  }

  refresh(view) {
    const g = (p) => view.params.get_val(p, "");
    const vision = g("vision_progress");
    const nationalVision = vision < 80.0 ? "完整以色列地" : "愿景里程碑";
    const trilemma = fmt("犹太 %.0f / 民主 %.0f / 领土 %.0f", g("trilemma_jewish"), g("trilemma_democratic"), g("trilemma_territory"));
    const m13 = view.modules.M13 || {};
    const stage = String(m13.centralization_stage ?? "C1");
    const tier = Number(m13.protest_tier ?? m13.social_protest_tier ?? 0);
    this.summary.textContent = fmt("%s 进度 %.0f%%（80%% 终局 +8）\n不可能三角 %s\n集权 %s 抗议 %d",
      nationalVision, vision, trilemma, stage, tier);
  }
}
