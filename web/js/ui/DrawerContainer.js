/* Port of game/ui/controllers/DrawerContainerController.gd + scenes/drawers/DrawerContainer.tscn.
 * Control at (240,52), 920 wide: HBox of 7 tab Buttons (12px, shrink-to-text) and a
 * PanelContainer (hidden until a drawer opens). toggle_drawer(i): same index closes with a
 * 0.18 s alpha fade, otherwise opens instantly; emits drawer_toggled(open) and syncs
 * UIManager.drawerIndex.
 * Intent fixes: the panel sits directly below the tab row (Godot draws it over the tabs) and
 * still ends at y=852; it shows the drawer title plus the real D1–D7 drawer content (Godot
 * never instances the D*.tscn scenes); the transparent container rect does not swallow map
 * input (only tabs and the open panel are interactive). */
import { rect, label, button, panel, hbox } from "../core/controls.js";
import { DRAWER_TITLES } from "../core/UIManager.js";
import { D1GoalsController } from "./drawers/D1_Goals.js";
import { D2KnessetController } from "./drawers/D2_Knesset.js";
import { D3CabinetController } from "./drawers/D3_Cabinet.js";
import { D4EconomyController } from "./drawers/D4_Economy.js";
import { D5DiplomacyController } from "./drawers/D5_Diplomacy.js";
import { D6PalestiniansController } from "./drawers/D6_Palestinians.js";
import { D7MilitaryIntelController } from "./drawers/D7_MilitaryIntel.js";

export const DRAWER_WIDTH = 920;
const TITLES = DRAWER_TITLES.slice(1);
const DRAWER_CLASSES = [null, D1GoalsController, D2KnessetController, D3CabinetController, D4EconomyController,
  D5DiplomacyController, D6PalestiniansController, D7MilitaryIntelController];
const FADE_SECONDS = 0.18;
const TAB_ROW_HEIGHT = 25; // 12px font line + 8px content margin (Godot default Button)
const PANEL_TOP = TAB_ROW_HEIGHT + 4; // one box separation below the tabs
const PANEL_BOTTOM = 800; // local; screen y = 852 as in Godot (panel min height 800)

export class DrawerContainerController {
  constructor(ctx) {
    this.ctx = ctx;
    this.openIndex = 0;
    this.drawers = [];
    this.fadeTimer = null;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(document.createElement("div"), 240, 52, 240 + DRAWER_WIDTH, 952);
    this.root.id = "DrawerContainer";
    this.root.classList.add("drawer-container");

    this.tabs = hbox("drawer-tabs");
    this.tabButtons = TITLES.map((t, i) => {
      const b = button(t, () => this.toggleDrawer(i + 1), { size: 12, cls: "drawer-tab" });
      this.tabs.appendChild(b);
      return b;
    });
    this.root.appendChild(this.tabs);

    this.panel = rect(panel("drawer-panel"), 0, PANEL_TOP, DRAWER_WIDTH, PANEL_BOTTOM);
    this.panel.style.height = "auto";
    this.panel.style.maxHeight = `${PANEL_BOTTOM - PANEL_TOP}px`;
    this.panel.style.display = "none";
    const hdr = hbox("drawer-header-bar");
    this.title = label("", { size: 18, autowrap: true, cls: "drawer-title" });
    const hint = label("点击指标可查看因果链 · 再次按快捷键或点 × 收起", { size: 12, cls: "drawer-hint" });
    this.closeBtn = button("× 收起", () => this.toggleDrawer(this.openIndex), { size: 12, cls: "drawer-close-btn" });
    hdr.append(this.title, hint, this.closeBtn);
    this.content = document.createElement("div");
    this.content.className = "drawer-content";
    this.panel.append(hdr, this.content);
    this.root.appendChild(this.panel);

    // One instance per drawer (built lazily on first open).
    this.slots = [null];
    for (let i = 1; i <= 7; i++) {
      const slot = document.createElement("div");
      slot.className = `drawer-slot drawer-slot-d${i}`;
      slot.style.display = "none";
      this.content.appendChild(slot);
      this.slots.push(slot);
    }
    layer.appendChild(this.root);
  }

  _drawer(index) {
    if (!this.drawers[index]) {
      const d = new DRAWER_CLASSES[index](this.ctx);
      d.mount(this.slots[index]);
      this.drawers[index] = d;
    }
    return this.drawers[index];
  }

  /** DeskMainController._on_drawer_requested: 0 closes the open drawer; n != open toggles to n. */
  onDrawerRequested(index, view) {
    const target = Math.min(7, Math.max(0, Number(index) || 0));
    if (target === 0) {
      if (this.openIndex !== 0) this.toggleDrawer(this.openIndex, view);
    } else if (this.openIndex !== target) {
      this.toggleDrawer(target, view);
    }
  }

  toggleDrawer(index, view = null) {
    if (this.fadeTimer) { clearTimeout(this.fadeTimer); this.fadeTimer = null; }
    if (this.openIndex === index) {
      this.openIndex = 0;
      this.panel.style.transition = `opacity ${FADE_SECONDS}s linear`;
      this.panel.style.opacity = "0";
      this.fadeTimer = setTimeout(() => { this.fadeTimer = null; this._hidePanel(); }, FADE_SECONDS * 1000);
    } else {
      this.openIndex = index;
      this.panel.style.transition = "none";
      this.panel.style.display = "";
      this.panel.style.opacity = "1";
      this.title.textContent = TITLES[index - 1];
      this.slots.forEach((s, i) => { if (s) s.style.display = i === index ? "" : "none"; });
      this._refreshOpen(view || this.ctx.engine.view());
    }
    this.tabButtons.forEach((b, i) => b.classList.toggle("active", i + 1 === this.openIndex));
    this.ctx.bus.emit("drawer_toggled", this.openIndex);
    this.ctx.ui.drawerIndex = this.openIndex;
  }

  visibleDrawersCount() { return this.openIndex === 0 ? 0 : 1; }

  _hidePanel() {
    if (this.openIndex === 0) this.panel.style.display = "none";
  }

  _refreshOpen(view) {
    if (!view || this.openIndex === 0) return;
    try {
      this._drawer(this.openIndex).refresh(view);
    } catch (err) {
      console.error(`[DrawerContainer] D${this.openIndex} refresh failed`, err);
    }
  }

  refresh(view) { this._refreshOpen(view); }
}
