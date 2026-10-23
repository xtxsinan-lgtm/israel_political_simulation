/* Port of game/ui/controllers/drawers/D6_PalestiniansController.gd: faction_legitimacy for 9
 * factions normalised to sum 100 (even split if all zero), uprising_risk shown only as a
 * FuzzyBand (D-088 fog of war). */
import { label, fmt } from "../../core/controls.js";
import { registerReads } from "../../core/StateView.js";
import { FuzzyBand } from "../../core/FuzzyBand.js";

export const FACTIONS = ["fatah", "pflp", "jordan_notables", "local_mayors", "village_leagues", "mujama", "hamas", "pij", "pa_security"];

registerReads([["uprising_risk", ""], ...FACTIONS.map((f) => ["faction_legitimacy", f])]);

export class D6PalestiniansController {
  constructor(ctx) {
    this.ctx = ctx;
    this.palLegitimacy = {};
    this.intifadaPhase = "calm";
  }

  mount(parent) {
    this.root = document.createElement("div");
    this.root.className = "drawer-body d6-palestinians";
    this.summary = label("", { size: 16, autowrap: true, cls: "drawer-summary" });
    this.root.appendChild(this.summary);
    parent.appendChild(this.root);
  }

  refresh(view) {
    let total = 0.0;
    for (const f of FACTIONS) {
      const share = view.params.get_val("faction_legitimacy", f);
      this.palLegitimacy[f] = share;
      total += share;
    }
    if (total <= 0.0) {
      const even = 100.0 / FACTIONS.length;
      for (const f of FACTIONS) this.palLegitimacy[f] = even;
    } else if (Math.abs(total - 100.0) > 0.001) {
      const scale = 100.0 / total;
      for (const f of FACTIONS) this.palLegitimacy[f] = this.palLegitimacy[f] * scale;
    }
    const band = FuzzyBand.bandIndex(view.params.get_val("uprising_risk", ""));
    this.intifadaPhase = band >= 3 ? "intifada" : (band >= 2 ? "unrest" : "calm");
    this.summary.textContent = fmt("阶段 %s  起义风险 %s\nmujama %s  hamas %s",
      this.intifadaPhase,
      FuzzyBand.describeBand(band, "uprising_risk"),
      FuzzyBand.describe(this.palLegitimacy.mujama, "faction_legitimacy"),
      FuzzyBand.describe(this.palLegitimacy.hamas, "faction_legitimacy"));
  }

  legitimacySum() {
    return FACTIONS.reduce((s, f) => s + Number(this.palLegitimacy[f] || 0), 0);
  }
}
