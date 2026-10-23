/* Port of game/ui/controllers/DiegeticDeskPropsController.gd + DiegeticDeskPropsBar.tscn.
 * HBox (240,994)-(1680,1080), 7 EXPAND_FILL Buttons (14px). Prop 4 (日历) cycles the speed
 * 1→5→1 without unpausing; the others open a drawer. Intent fix: paper Panel background. */
import { rect, button, panel, hbox } from "../core/controls.js";

export const PROPS = ["红电话", "打字机", "收音机", "日历", "天平", "报价纸带", "档案袋"];
export const DRAWERS = [7, 3, 2, 0, 1, 4, 5];

export class DiegeticDeskPropsController {
  constructor(ctx) { this.ctx = ctx; }

  mount(layer) {
    this.layer = layer;
    this.root = rect(panel("desk-props"), 240, 994, 1680, 1080);
    this.root.id = "DiegeticDeskPropsBar";
    const row = hbox("desk-props-row");
    PROPS.forEach((text, i) => {
      row.appendChild(button(text, () => this.toggle(DRAWERS[i]), { size: 14, cls: "expand-fill desk-prop" }));
    });
    this.root.appendChild(row);
    layer.appendChild(this.root);
  }

  toggle(drawerIndex) {
    const { ui, bus, engine } = this.ctx;
    if (drawerIndex !== 0) {
      if (ui) ui.openDrawer(drawerIndex);
      else bus.emit("drawer_toggled", drawerIndex);
      return;
    }
    const view = engine.view();
    if (!view) return;
    const speed = Number(view.run.speed ?? 1);
    engine.setSpeed(speed >= 5 ? 1 : speed + 1);
  }

  refresh() {}
}
