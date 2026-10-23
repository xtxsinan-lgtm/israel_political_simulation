/* Port of game/ui/controllers/DiegeticDeskPropsController.gd + DiegeticDeskPropsBar.tscn.
 * HBox (240,994)-(1680,1080), 7 EXPAND_FILL Buttons. Prop 4 (日历) cycles the speed
 * 1→5→1 without unpausing; the others open a drawer. Intent fixes: paper Panel background;
 * each prop shows a line icon, its name and what it does (+ hotkey), a hover sentence, the
 * live speed on the calendar, and the prop whose drawer is open is highlighted. */
import { el, rect, panel, hbox } from "../core/controls.js";

export const PROPS = ["红电话", "打字机", "收音机", "日历", "天平", "报价纸带", "档案袋"];
export const DRAWERS = [7, 3, 2, 0, 1, 4, 5];

const ACTIONS = [
  "国防与情报 D7 (Ctrl+7)",
  "内阁与政策 D3 (Ctrl+3)",
  "议会与政党 D2 (Ctrl+2)",
  "切换速度（当前 %d 倍）",
  "愿景与宪政 D1 (Ctrl+1)",
  "经济与因果网 D4 (Ctrl+4)",
  "外交与阿利亚 D5 (Ctrl+5)",
];

const HINTS = [
  "拿起红电话：打开国防与情报抽屉，查看战备、威胁与情报评估。",
  "坐到打字机前：打开内阁与政策抽屉，处理部长提案并下达政策。",
  "打开收音机：收听议会动向，查看各党席位与联盟稳定度。",
  "翻动日历：在 1–5 倍之间循环切换时间流速（不会解除暂停）。",
  "端详天平：打开愿景与宪政抽屉，衡量长期目标与宪政秩序。",
  "看报价纸带：打开经济与因果网抽屉，追踪通胀、外汇与因果链。",
  "翻开档案袋：打开外交与阿利亚抽屉，处理对外关系与移民事务。",
];

/** 24x24 line icons (stroke = currentColor). */
const ICONS = [
  // red telephone
  '<path d="M4 9c0-2.5 3.6-4 8-4s8 1.5 8 4l-2.5 1.2L15 8.6V7.4c-2-.5-4-.5-6 0v1.2l-2.5 1.6z"/><path d="M7.5 11h9l2 8H5.5z"/><circle cx="12" cy="15" r="2"/>',
  // typewriter
  '<path d="M7 4h10v5H7z"/><path d="M3 9h18v4H3z"/><path d="M4 13h16l1 6H3z"/><path d="M6.5 16h1M9.5 16h1M12.5 16h1M15.5 16h1M8 18h8"/>',
  // radio
  '<path d="M3 9h18v11H3z"/><path d="M6 9l11-5"/><circle cx="8.5" cy="14.5" r="3"/><path d="M14 12h4M14 14.5h4M14 17h4"/>',
  // calendar
  '<path d="M4 6h16v14H4z"/><path d="M4 10h16"/><path d="M8 4v4M16 4v4"/><path d="M8 13h2M11 13h2M14 13h2M8 16h2M11 16h2"/>',
  // scales
  '<path d="M12 4v15M7 20h10M5 7h14"/><path d="M5 7l-3 6h6zM19 7l-3 6h6z"/><path d="M2 13a3 2 0 0 0 6 0M16 13a3 2 0 0 0 6 0"/>',
  // ticker tape
  '<path d="M3 7c3-2 5 2 9 0s6 2 9 0v9c-3 2-5-2-9 0s-6-2-9 0z"/><path d="M5 12.5l2.5-2 2.5 1.5 3-3 2.5 2 3-2.5"/>',
  // dossier / file folder
  '<path d="M3 6h7l2 2h9v11H3z"/><path d="M3 10h18"/><circle cx="16" cy="14.5" r="1.6"/><path d="M16 14.5c1.5 1.5-1 2-2.5 3"/>',
];

export class DiegeticDeskPropsController {
  constructor(ctx) {
    this.ctx = ctx;
    this.buttons = [];
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(panel("desk-props"), 240, 994, 1680, 1080);
    this.root.id = "DiegeticDeskPropsBar";
    const row = hbox("desk-props-row");
    PROPS.forEach((text, i) => {
      const b = el("button", "btn expand-fill desk-prop");
      b.type = "button";
      b.title = HINTS[i];
      b.dataset.drawer = String(DRAWERS[i]);
      b.innerHTML = `<svg class="desk-prop-icon" viewBox="0 0 24 24" width="34" height="34" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[i]}</svg>`;
      const txt = el("span", "desk-prop-text");
      txt.append(el("span", "desk-prop-name", text), el("span", "desk-prop-action", ""));
      b.appendChild(txt);
      b.addEventListener("click", () => this.toggle(DRAWERS[i]));
      row.appendChild(b);
      this.buttons.push(b);
    });
    this.root.appendChild(row);
    layer.appendChild(this.root);
    const { bus, engine, ui } = this.ctx;
    bus.connect("drawer_toggled", (idx) => this._markOpen(Number(idx) || 0));
    bus.connect("sim_speed_changed", (lvl) => this._setSpeed(lvl));
    bus.connect("pause_state_changed", (_p, lvl) => this._setSpeed(lvl));
    this._setSpeed(engine && engine.speedLevel !== undefined ? engine.speedLevel : 1);
    this._markOpen(ui ? ui.drawerIndex || 0 : 0);
  }

  _setSpeed(level) {
    const n = Number(level);
    if (!Number.isFinite(n)) return;
    this.speed = n;
    this.buttons.forEach((b, i) => {
      b.querySelector(".desk-prop-action").textContent = i === 3 ? ACTIONS[3].replace("%d", String(n)) : ACTIONS[i];
    });
  }

  _markOpen(drawerIndex) {
    this.buttons.forEach((b, i) => b.classList.toggle("open", drawerIndex !== 0 && DRAWERS[i] === drawerIndex));
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

  refresh(view) {
    if (view && view.run && view.run.speed !== undefined && Number(view.run.speed) !== this.speed) this._setSpeed(view.run.speed);
  }
}
