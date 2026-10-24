/* MapModeBottomBar: Replaces redundant desk props at (240, 994)-(1680, 1080).
 * Displays one-click buttons for strategic map modes F1–F7 along with dynamic legend hints.
 * Fully decoupled from drawer navigation; eliminates duplicate window buttons. */
import { el, rect, panel, hbox } from "../../core/controls.js";

export const MAP_LAYERS = [
  { id: 1, key: "F1", name: "政治法律", desc: "主权领土 / 军事管制区 / 停火巡逻线", color: "#0038B8" },
  { id: 2, key: "F2", name: "族群区划", desc: "各行政区与被占领地非犹太居民疏离度热力分布", color: "#2B5E8A" },
  { id: 3, key: "F3", name: "治安战备", desc: "前线战备水平、治安巡逻与敌对渗透冲突威胁", color: "#C87D12" },
  { id: 4, key: "F4", name: "区域发展", desc: "各区域基础设施投资、经济繁荣度与发展指数", color: "#2E7D32" },
  { id: 5, key: "F5", name: "定居人口", desc: "西岸、加沙、戈兰高地定居点建设与定居人口分布", color: "#6A1B9A" },
  { id: 6, key: "F6", name: "选民倾向", desc: "各地区选民意识形态倾向与各党派基本盘票仓", color: "#B8292F" },
  { id: 7, key: "F7", name: "人口三难", desc: "犹太多数 · 民主宪政 · 领土完整之三难三角平衡", color: "#455A64" },
];

export class MapModeBottomBar {
  constructor(ctx) {
    this.ctx = ctx;
    this.buttons = [];
    this.activeLayer = 1;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(panel("map-mode-bar"), 240, 994, 1680, 1080);
    this.root.id = "MapModeBottomBar";

    const container = hbox("map-mode-container");

    // Title / Badge with map icon
    const titleBox = el("div", "map-mode-title-box");
    titleBox.innerHTML = `
      <svg class="map-mode-icon" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="1 6 1 22 8 18 16 22 23 18 23 2 16 6 8 2 1 6"/>
        <line x1="8" y1="2" x2="8" y2="18"/>
        <line x1="16" y1="6" x2="16" y2="22"/>
      </svg>
      <span class="map-mode-title-text">战略热力图层</span>
    `;
    container.appendChild(titleBox);

    // F1–F7 buttons
    const btnGroup = hbox("map-mode-btn-group");
    MAP_LAYERS.forEach((m) => {
      const b = el("button", "btn map-mode-btn");
      b.type = "button";
      b.dataset.layer = String(m.id);
      b.title = `${m.key} ${m.name}：${m.desc} (按键 ${m.key})`;

      const keySpan = el("span", "map-mode-btn-key", m.key);
      const nameSpan = el("span", "map-mode-btn-name", m.name);
      b.append(keySpan, nameSpan);

      b.addEventListener("click", () => {
        if (this.ctx.ui) this.ctx.ui.setMapLayer(m.id);
        else this.ctx.bus.emit("map_layer_changed", m.id);
      });

      btnGroup.appendChild(b);
      this.buttons.push(b);
    });
    container.appendChild(btnGroup);

    // Dynamic legend hint
    this.legendBox = el("div", "map-mode-legend-box");
    this.legendDot = el("span", "map-mode-legend-dot");
    this.legendText = el("span", "map-mode-legend-text", "");
    this.legendBox.append(this.legendDot, this.legendText);
    container.appendChild(this.legendBox);

    this.root.appendChild(container);
    layer.appendChild(this.root);

    // Connect bus
    const { bus, ui } = this.ctx;
    bus.connect("map_layer_changed", (idx) => this._setActive(Number(idx) || 1));
    bus.connect("map_mode_changed", (mode) => {
      const n = Number(String(mode).replace(/\D/g, "")) || 1;
      this._setActive(n);
    });

    const initLayer = ui && ui.mapLayer ? ui.mapLayer : 1;
    this._setActive(initLayer);
  }

  _setActive(layerIndex) {
    this.activeLayer = Math.min(7, Math.max(1, layerIndex));
    this.buttons.forEach((b, i) => {
      b.classList.toggle("active", i + 1 === this.activeLayer);
    });
    const info = MAP_LAYERS.find((m) => m.id === this.activeLayer) || MAP_LAYERS[0];
    if (this.legendText) {
      this.legendText.textContent = `${info.key} ${info.name}：${info.desc}`;
    }
    if (this.legendDot) {
      this.legendDot.style.backgroundColor = info.color;
    }
  }

  refresh(_view) {
    // Re-verify active layer state if needed
    if (this.ctx.ui && this.ctx.ui.mapLayer !== this.activeLayer) {
      this._setActive(this.ctx.ui.mapLayer);
    }
  }
}
