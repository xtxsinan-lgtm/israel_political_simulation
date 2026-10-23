/* Port of game/ui/controllers/TopBarController.gd + scenes/components/TopBar.tscn.
 * HBox (0,0)-(1920,52) with 9 EXPAND_FILL Labels (14px, initial "—").
 * Intent fixes: paper Panel background so the ink text is readable; clicking a slot that
 * shows a parameter emits tooltip_requested(paramId, ""); the slot-5 red colour is reset
 * when inflation drops back to <= 100 (Godot never resets it). */
import { rect, label, panel, hbox, fmt } from "../core/controls.js";
import { registerReads, PARAM_ALIASES } from "../core/StateView.js";

registerReads([
  ["political_capital", ""], ["coalition_seats", ""], ["government_approval", ""], ["inflation", ""],
  ["fx_reserves", ""], ["idf_readiness", ""], ["us_wh_warmth", ""], ["us_cong_support", ""],
]);

/* Parameter behind each slot (Godot names); null = no parameter (date / static text). */
const SLOT_PARAMS = [null, "political_capital", "coalition_seats", "government_approval", "inflation",
  "fx_reserves", "idf_readiness", "us_wh_warmth", null];

export class TopBarController {
  constructor(ctx) {
    this.ctx = ctx;
    this.slots = [];
    this.boundState = null;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(panel("topbar"), 0, 0, 1920, 52);
    this.root.id = "TopBar";
    const row = hbox("topbar-row");
    this.root.appendChild(row);
    for (let i = 0; i < 9; i++) {
      const slot = label("—", { size: 14, cls: "expand-fill topbar-slot" });
      slot.dataset.slot = `Slot${i + 1}`;
      const param = SLOT_PARAMS[i];
      if (param) {
        slot.classList.add("clickable");
        // Emit the reference (Python) name so the causal tooltip can explain it.
        slot.addEventListener("click", () => this.ctx.bus.emit("tooltip_requested", PARAM_ALIASES[param] || param, ""));
      }
      row.appendChild(slot);
      this.slots.push(slot);
    }
    layer.appendChild(this.root);
  }

  refresh(view) {
    if (!view || !this.slots.length) return;
    this.boundState = view;
    const g = (p) => view.params.get_val(p, "");
    const speed = Number(view.run.speed ?? 1);
    const pace = view.run.paused ? "暂停" : fmt("%d倍", speed);
    const s = this.slots;
    s[0].textContent = fmt("%s  第%d天  %s", view.clock.date, view.clock.day_index, pace);
    const pc = g("political_capital");
    s[1].textContent = fmt("政治资本 %.1f%s", pc, pc > 92.0 ? " 软顶" : "");
    const seats = g("coalition_seats");
    s[2].textContent = fmt("执政席位 %.0f / 120%s", seats, seats < 61.0 ? " 少数派" : "");
    s[3].textContent = fmt("支持率 %.1f", g("government_approval"));
    const inflation = g("inflation");
    s[4].textContent = fmt("通胀 %.1f%%", inflation);
    s[5].textContent = fmt("外汇 %.1f", g("fx_reserves"));
    s[6].textContent = fmt("战备 %.1f", g("idf_readiness"));
    s[7].textContent = fmt("白宫 %.0f / 国会 %.0f", g("us_wh_warmth"), g("us_cong_support"));
    s[8].textContent = fmt("%s 账本L 百科C", "不可能三角");
    // Godot: add_theme_color_override(#B8292F) when > 100 and never removed (sticky).
    s[4].style.color = inflation > 100.0 ? "#B8292F" : "";
  }

  textsFilled() {
    return this.slots.length === 9 && this.slots.every((l) => l.textContent.trim() !== "");
  }
}
