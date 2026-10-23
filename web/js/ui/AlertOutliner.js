/* Port of game/ui/controllers/AlertOutlinerController.gd + scenes/components/AlertOutliner.tscn.
 * VBox (1680,52)-(1920,1080), rebuilt on every refresh. Intent fix: paper Panel background. */
import { rect, label, button, panel, vbox } from "../core/controls.js";

export class AlertOutlinerController {
  constructor(ctx) {
    this.ctx = ctx;
    this.boundState = null;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(panel("alert-outliner"), 1680, 52, 1920, 1080);
    this.root.id = "AlertOutliner";
    this.box = vbox("alert-outliner-box");
    this.root.appendChild(this.box);
    layer.appendChild(this.root);
  }

  refresh(view) {
    if (!view || !this.box) return;
    this.boundState = view;
    this.box.replaceChildren();
    const raw = view.history ? view.history.active_alerts : [];
    const alerts = Array.isArray(raw) ? raw : [];
    this.box.appendChild(label("红 / 黄 / 蓝 预警", { size: 14 }));
    if (!alerts.length) {
      this.box.appendChild(label("暂无激活预警", { cls: "alert-quiet" }));
      return;
    }
    for (const a of alerts) {
      const code = String(a);
      const drawer = this.drawerFor(code);
      this.box.appendChild(button(this.labelFor(code), () => this.openDrawer(drawer), { size: 12, cls: "alert-btn" }));
    }
  }

  openDrawer(drawerIndex) {
    this.ctx.bus.emit("drawer_toggled", drawerIndex);
    this.ctx.ui.openDrawer(drawerIndex);
  }

  labelFor(code) {
    if (code.endsWith("_red")) return "红 " + code;
    if (code.endsWith("_yellow")) return "黄 " + code;
    return "蓝 " + code;
  }

  drawerFor(code) {
    if (code.includes("inflation") || code.includes("budget")) return 4;
    if (code.includes("coalition")) return 2;
    if (code.includes("security")) return 7;
    return 1;
  }
}
