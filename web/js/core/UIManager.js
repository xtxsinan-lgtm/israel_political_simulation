/* Port of game/ui/UIManager.gd (DeskUiRouter): drawer index, map layer, modal/tooltip
 * stacks, overlays and the hotkey scheme. Browser note: F1–F7 / Tab / Ctrl+1–7 would
 * trigger browser shortcuts, so handled keys call preventDefault(). Escape additionally
 * closes the event modal / tenure book in the web build only if the modal is dismissable
 * (it is not: matches Godot, which never pushes them to modal_stack). */
export const DRAWER_TITLES = [
  "", "D1 愿景与宪政", "D2 议会与政党", "D3 内阁与政策", "D4 经济与因果网",
  "D5 外交与阿利亚", "D6 巴勒斯坦事务", "D7 国防与情报",
];

export class UIManager {
  constructor(bus, engine) {
    this.bus = bus;
    this.engine = engine;
    this.drawerIndex = 0;
    this.mapLayer = 1;
    this.modalStack = [];
    this.tooltipStack = [];
    this.ledgerOpen = false;
    this.codexOpen = false;
    this.inputBlocked = false; // true while the boot splash is up
  }

  openDrawer(index) {
    this.drawerIndex = index === this.drawerIndex ? 0 : Math.min(7, Math.max(0, index));
    this.bus.emit("drawer_toggled", this.drawerIndex);
    this.bus.emit("drawer_requested", `D${this.drawerIndex}`, 0, "");
  }

  setMapLayer(index) {
    this.mapLayer = Math.min(7, Math.max(1, index));
    this.bus.emit("map_layer_changed", this.mapLayer);
    this.bus.emit("map_mode_changed", `F${this.mapLayer}`);
  }

  pushModal(id) { if (this.modalStack.length >= 1) return false; this.modalStack.push(id); return true; }
  popModal() { return this.modalStack.pop() || ""; }

  lockTooltip(id) {
    if (this.tooltipStack.length >= 3 || this.tooltipStack.includes(id)) return false;
    this.tooltipStack.push(id);
    this.bus.emit("tooltip_lock_toggled", id, true);
    return true;
  }

  popTooltip() {
    const id = this.tooltipStack.pop() || "";
    if (id) this.bus.emit("tooltip_lock_toggled", id, false);
    return id;
  }

  setOverlay(id, open) {
    if (id === "ledger") this.ledgerOpen = open;
    else if (id === "codex") {
      this.codexOpen = open;
      if (open) this.bus.emit("codex_entry_requested", "index");
    } else return;
    this.bus.emit("overlay_toggled", id, open);
  }

  handleEscape() {
    if (this.tooltipStack.length) this.popTooltip();
    else if (this.modalStack.length) this.popModal();
    else if (this.drawerIndex !== 0) this.openDrawer(this.drawerIndex);
    else if (this.ledgerOpen || this.codexOpen) { this.setOverlay("ledger", false); this.setOverlay("codex", false); }
  }

  handleAction(action) {
    const e = this.engine;
    if (action === "toggle_pause") e.togglePause();
    else if (action.startsWith("speed_")) { e.setSpeed(Number(action.slice(6))); e.setPaused(false); }
    else if (action.startsWith("map_mode_f")) this.setMapLayer(Number(action.slice(10)));
    else if (action === "toggle_ledger") this.setOverlay("ledger", !this.ledgerOpen);
    else if (action === "toggle_codex") this.setOverlay("codex", !this.codexOpen);
    else if (action === "quick_save") e.quickSave().catch((err) => console.warn("quick_save failed", err));
    else if (action === "quick_load") e.quickLoad().catch((err) => console.warn("quick_load failed", err));
  }

  /** InputMap of game/project.godot (exact modifier match, key-down, non-echo). */
  actionFor(ev) {
    if (ev.shiftKey || ev.altKey) return "";
    const k = ev.key;
    if (k === " " || ev.code === "Space") return "toggle_pause";
    if (/^[1-5]$/.test(k)) return `speed_${k}`;
    const f = /^F([1-9])$/.exec(k);
    if (f) {
      const n = Number(f[1]);
      if (n <= 7) return `map_mode_f${n}`;
      if (n === 8) return "quick_save";
      if (n === 9) return "quick_load";
    }
    if (k === "l" || k === "L") return "toggle_ledger";
    if (k === "c" || k === "C") return "toggle_codex";
    return "";
  }

  /** Returns true when consumed (mirrors handle_key). */
  handleKey(ev) {
    if (this.inputBlocked || ev.repeat) return false;
    const tag = (ev.target && ev.target.tagName) || "";
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return false;
    if (ev.ctrlKey || ev.metaKey) {
      if (/^[1-7]$/.test(ev.key)) { this.openDrawer(Number(ev.key)); return true; }
      return false;
    }
    const action = this.actionFor(ev);
    if (action) { this.handleAction(action); return true; }
    if (ev.key === "Escape") { this.handleEscape(); return true; }
    if (ev.key === "Tab") { this.openDrawer(this.drawerIndex === 0 ? 1 : (this.drawerIndex % 7) + 1); return true; }
    return false;
  }

  install() {
    window.addEventListener("keydown", (ev) => {
      if (this.handleKey(ev)) ev.preventDefault();
    });
  }
}
