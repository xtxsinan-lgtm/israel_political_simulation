/* Port of game/ui/controllers/OnboardingDirector.gd on the SpotlightTutorialOverlay node
 * ((1300,900)-(1660,980), hidden in Godot and never shown by code).
 *
 * Wired: maybeStart() shows it on the first visit (localStorage "onboarding_done"), with the
 * 8 exact steps "第 %d 步  %s", 下一步 (advance) and 跳过 (skip_tutorial). Finishing shows
 * 引导完成, skipping shows 教程已跳过，全部面板已解锁; both hide after 2 s and set the flag.
 * Addition: a spotlight outline around the screen area each step refers to. */
import { el, rect, label, button, panel, vbox, hbox, fmt } from "../core/controls.js";

export const STEP_COUNT = 8;
export const STEPS = [
  "看顶栏：61 席与政治资本",
  "在地图上查看西奈、西岸和 F1–F7",
  "锁定一个因果提示，看通胀从哪来",
  "打开 D2，核对利库德联盟",
  "打开 D3，处理部长提案和 30% 折扣",
  "打开 D4，看因果网络",
  "读第一份电报和三层预览",
  "解除暂停，走到第一个周日",
];
const FLAG = "onboarding_done";

/** Spotlight rects (left, top, right, bottom) in stage coordinates for each step. */
const SPOTS = [
  [0, 0, 1920, 52],        // TopBar
  [690, 104, 1150, 975],   // map: Israel, West Bank and Sinai (real geography)
  [440, 0, 660, 52],       // TopBar slot 4 (inflation) — open its causal tooltip
  [240, 52, 1160, 952],    // drawer area (D2)
  [240, 52, 1160, 952],    // drawer area (D3)
  [240, 52, 1160, 952],    // drawer area (D4)
  [500, 200, 1420, 600],   // event modal
  [1360, 0, 1920, 52],     // TopBar top-right TimeControlPanel (date / pace / pause / speed)
];

export class OnboardingDirector {
  constructor(ctx) {
    this.ctx = ctx;
    this.step = 0;
    this.skipped = false;
    this.hideTimer = null;
  }

  mount(layer) {
    this.layer = layer;
    this.spot = el("div", "onboarding-spotlight");
    this.spot.style.display = "none";
    const root = rect(panel("onboarding-overlay"), 1300, 900, 1660, 980);
    const box = vbox("onboarding-box");
    this.body = label("", { autowrap: true, cls: "onboarding-body" });
    const row = hbox("onboarding-buttons");
    this.nextBtn = button("下一步", () => this.advance());
    this.skipBtn = button("跳过", () => this.skipTutorial());
    row.append(this.nextBtn, this.skipBtn);
    box.append(this.body, row);
    root.appendChild(box);
    root.style.display = "none";
    this.root = root;
    layer.append(this.spot, root);
  }

  /** Show on the first visit only. */
  maybeStart() {
    let done = false;
    try { done = localStorage.getItem(FLAG) === "1"; } catch { done = false; }
    if (done || !this.root) return false;
    this.step = 0;
    this.skipped = false;
    this.root.style.display = "";
    this.nextBtn.disabled = false;
    this.skipBtn.disabled = false;
    this._show();
    return true;
  }

  advance() {
    if (this.skipped) return;
    this.step = Math.min(this.step + 1, STEP_COUNT);
    this._show();
  }

  skipTutorial() {
    this.skipped = true;
    this.step = STEP_COUNT;
    this.body.textContent = "教程已跳过，全部面板已解锁";
    this._finish();
  }

  finished() { return this.step >= STEP_COUNT; }

  _show() {
    if (this.step >= STEPS.length) {
      this.body.textContent = "引导完成";
      this._finish();
      return;
    }
    this.body.textContent = fmt("第 %d 步  %s", this.step + 1, STEPS[this.step]);
    const [l, t, r, b] = SPOTS[this.step];
    rect(this.spot, l, t, r, b);
    this.spot.style.display = "";
  }

  _finish() {
    this.spot.style.display = "none";
    this.nextBtn.disabled = true;
    this.skipBtn.disabled = true;
    try { localStorage.setItem(FLAG, "1"); } catch { /* storage unavailable */ }
    clearTimeout(this.hideTimer);
    this.hideTimer = setTimeout(() => { this.root.style.display = "none"; }, 2000);
  }
}
