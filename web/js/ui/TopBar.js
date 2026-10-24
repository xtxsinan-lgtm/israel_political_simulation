/* TopBarController + Top-Right Time & Flow Control Dashboard.
 * Left/Center: 9 Resource and Policy KPI slots with causal tooltip triggers.
 * Right: Dedicated Time Control Widget with Date, Pause/Resume, Step 1 Day, and Speed 1–5 controls.
 */
import { el, rect, label, panel, hbox, fmt } from "../core/controls.js";
import { registerReads, PARAM_ALIASES } from "../core/StateView.js";

registerReads([
  ["political_capital", ""], ["coalition_seats", ""], ["government_approval", ""], ["inflation", ""],
  ["fx_reserves", ""], ["idf_readiness", ""], ["us_wh_warmth", ""], ["us_cong_support", ""],
]);

/* Parameter mapped to each KPI slot (null = special/compound slot). */
const SLOT_PARAMS = [
  "political_capital",
  "coalition_seats",
  "government_approval",
  "inflation",
  "fx_reserves",
  "idf_readiness",
  "us_wh_warmth",
  null, // 不可能三角
  null, // 账本与百科快捷入口
];

export class TopBarController {
  constructor(ctx) {
    this.ctx = ctx;
    this.slots = [];
    this.boundState = null;
    this.speedBtns = [];
    this.currentSpeed = 1;
    this.isPaused = true;
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(panel("topbar"), 0, 0, 1920, 52);
    this.root.id = "TopBar";

    const mainRow = hbox("topbar-main-row");

    // 1. KPI Slots Bar (Left & Center)
    const kpiRow = hbox("topbar-kpis-row");
    for (let i = 0; i < 9; i++) {
      const slot = label("—", { size: 13, cls: "topbar-slot" });
      slot.dataset.slot = `Slot${i + 1}`;
      const param = SLOT_PARAMS[i];
      if (param) {
        slot.classList.add("clickable");
        slot.addEventListener("click", () => this.ctx.bus.emit("tooltip_requested", PARAM_ALIASES[param] || param, ""));
      } else if (i === 7) {
        // 不可能三角
        slot.classList.add("clickable");
        slot.title = "三难三角：犹太多数 · 民主宪政 · 领土完整";
        slot.addEventListener("click", () => this.ctx.ui.setMapLayer(7));
      } else if (i === 8) {
        slot.classList.add("topbar-quick-actions");
      }
      kpiRow.appendChild(slot);
      this.slots.push(slot);
    }
    mainRow.appendChild(kpiRow);

    // 2. Time & Flow Control Dashboard (Top Right)
    const timePanel = el("div", "topbar-time-panel");
    timePanel.id = "TimeControlPanel";

    // 2a. Date & Calendar box
    const dateBox = el("div", "time-clock-box");
    dateBox.title = "时间与日历";
    const calSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    calSvg.setAttribute("class", "time-clock-icon");
    calSvg.setAttribute("viewBox", "0 0 24 24");
    calSvg.setAttribute("width", "16");
    calSvg.setAttribute("height", "16");
    calSvg.setAttribute("fill", "none");
    calSvg.setAttribute("stroke", "currentColor");
    calSvg.setAttribute("stroke-width", "1.8");
    calSvg.innerHTML = `<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>`;
    this.dateText = el("span", "time-date-text", "1977-06-20  第0天  暂停");
    dateBox.append(calSvg, this.dateText);
    timePanel.appendChild(dateBox);

    timePanel.appendChild(el("div", "time-panel-divider"));

    // 2b. Flow buttons (Pause/Play & Step 1 Day)
    const flowBox = el("div", "time-flow-btns");

    // Pause / Resume toggle button
    this.pauseBtn = el("button", "btn time-flow-btn time-pause-btn paused");
    this.pauseBtn.type = "button";
    this.pauseBtn.title = "暂停 / 继续模拟 (快捷键: 空格 Space)";
    this.pauseBtnIcon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.pauseBtnIcon.setAttribute("class", "time-btn-svg");
    this.pauseBtnIcon.setAttribute("viewBox", "0 0 24 24");
    this.pauseBtnIcon.setAttribute("width", "14");
    this.pauseBtnIcon.setAttribute("height", "14");
    this.pauseBtnIcon.setAttribute("fill", "currentColor");
    this.pauseBtnText = el("span", "time-btn-text", "继续");
    this.pauseBtn.append(this.pauseBtnIcon, this.pauseBtnText);
    this.pauseBtn.addEventListener("click", () => this.ctx.engine.togglePause());
    flowBox.appendChild(this.pauseBtn);

    // Step 1 Day button
    this.stepBtn = el("button", "btn time-flow-btn time-step-btn");
    this.stepBtn.type = "button";
    this.stepBtn.title = "单日推进 (前进 1 天并保持暂停)";
    const stepSvg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    stepSvg.setAttribute("class", "time-btn-svg");
    stepSvg.setAttribute("viewBox", "0 0 24 24");
    stepSvg.setAttribute("width", "14");
    stepSvg.setAttribute("height", "14");
    stepSvg.setAttribute("fill", "currentColor");
    stepSvg.innerHTML = `<polygon points="4,4 14,12 4,20"/><rect x="16" y="4" width="3" height="16" rx="0.5"/>`;
    const stepText = el("span", "time-btn-text", "+1天");
    this.stepBtn.append(stepSvg, stepText);
    this.stepBtn.addEventListener("click", () => this.ctx.engine.stepOneDay());
    flowBox.appendChild(this.stepBtn);

    timePanel.appendChild(flowBox);

    timePanel.appendChild(el("div", "time-panel-divider"));

    // 2c. Speed buttons (1x..5x)
    const speedBox = el("div", "time-speed-box");
    speedBox.title = "时间推进速度 (数字键 1–5)";
    const speedLbl = el("span", "time-speed-label", "速度");
    const speedGroup = el("div", "time-speed-group");

    for (let s = 1; s <= 5; s++) {
      const b = el("button", `btn time-speed-btn${s === 1 ? " active" : ""}`);
      b.type = "button";
      b.dataset.speed = String(s);
      b.textContent = `${s}x`;
      b.title = `${s}倍速度 (按键 ${s})`;
      b.addEventListener("click", () => this.ctx.engine.setSpeed(s));
      speedGroup.appendChild(b);
      this.speedBtns.push(b);
    }
    speedBox.append(speedLbl, speedGroup);
    timePanel.appendChild(speedBox);

    mainRow.appendChild(timePanel);
    this.root.appendChild(mainRow);
    layer.appendChild(this.root);

    // Initial icon state
    this._renderPauseState(true);
    this._renderSpeedState(1);

    // Bus subscriptions
    const { bus, engine } = this.ctx;
    bus.connect("sim_speed_changed", (lvl) => this._renderSpeedState(lvl));
    bus.connect("pause_state_changed", (paused, lvl) => {
      this._renderPauseState(paused);
      if (lvl !== undefined) this._renderSpeedState(lvl);
      const v = engine.view();
      if (v) this.refresh(v);
    });
  }

  _renderPauseState(paused) {
    this.isPaused = !!paused;
    if (!this.pauseBtn) return;
    this.pauseBtn.classList.toggle("paused", this.isPaused);
    this.pauseBtn.classList.toggle("running", !this.isPaused);
    if (this.isPaused) {
      // Paused -> show Play icon and "继续"
      this.pauseBtnIcon.innerHTML = `<polygon points="6,4 20,12 6,20"/>`;
      this.pauseBtnText.textContent = "继续";
      this.pauseBtn.title = "模拟已暂停 · 点击继续运行 (空格 Space)";
    } else {
      // Running -> show Pause icon and "暂停"
      this.pauseBtnIcon.innerHTML = `<rect x="5" y="4" width="4" height="16" rx="1"/><rect x="15" y="4" width="4" height="16" rx="1"/>`;
      this.pauseBtnText.textContent = "暂停";
      this.pauseBtn.title = "模拟运行中 · 点击暂停 (空格 Space)";
    }
  }

  _renderSpeedState(speed) {
    const s = Math.min(5, Math.max(1, Number(speed) || 1));
    this.currentSpeed = s;
    this.speedBtns.forEach((b, i) => {
      b.classList.toggle("active", i + 1 === s);
    });
  }

  refresh(view) {
    if (!view || !this.slots.length) return;
    this.boundState = view;
    const g = (p) => view.params.get_val(p, "");
    const speed = Number(view.run.speed ?? 1);
    const pace = view.run.paused ? "暂停" : fmt("%d倍", speed);

    // Update Top-Right Clock & Pace Text (guarantees e2e HUDLayer match)
    if (this.dateText) {
      this.dateText.textContent = fmt("%s  第%d天  %s", view.clock.date, view.clock.day_index, pace);
    }
    this._renderPauseState(view.run.paused);
    this._renderSpeedState(speed);

    // Update 9 KPI slots
    const s = this.slots;
    const pc = g("political_capital");
    s[0].textContent = fmt("政治资本 %.1f%s", pc, pc > 92.0 ? " 软顶" : "");

    const seats = g("coalition_seats");
    s[1].textContent = fmt("执政席位 %.0f / 120%s", seats, seats < 61.0 ? " 少数派" : "");

    s[2].textContent = fmt("支持率 %.1f", g("government_approval"));

    const inflation = g("inflation");
    s[3].textContent = fmt("通胀 %.1f%%", inflation);
    s[3].style.color = inflation > 100.0 ? "#B8292F" : "";

    s[4].textContent = fmt("外汇 %.1f", g("fx_reserves"));

    s[5].textContent = fmt("战备 %.1f", g("idf_readiness"));

    s[6].textContent = fmt("白宫 %.0f / 国会 %.0f", g("us_wh_warmth"), g("us_cong_support"));

    s[7].textContent = "不可能三角";

    // Slot 9: Interactive badges for Ledger & Codex
    s[8].innerHTML = `
      <span class="topbar-overlay-link link-ledger" title="打开国家总账本 (快捷键 L)">账本 [L]</span>
      <span class="topbar-overlay-sep">·</span>
      <span class="topbar-overlay-link link-codex" title="打开政治百科全书 (快捷键 C)">百科 [C]</span>
    `;
    const ledgerLink = s[8].querySelector(".link-ledger");
    if (ledgerLink) {
      ledgerLink.addEventListener("click", (e) => {
        e.stopPropagation();
        this.ctx.ui.setOverlay("ledger", !this.ctx.ui.ledgerOpen);
      });
    }
    const codexLink = s[8].querySelector(".link-codex");
    if (codexLink) {
      codexLink.addEventListener("click", (e) => {
        e.stopPropagation();
        this.ctx.ui.setOverlay("codex", !this.ctx.ui.codexOpen);
      });
    }
  }

  textsFilled() {
    return this.slots.length === 9 && this.slots.every((l) => l && l.textContent.trim() !== "");
  }
}
