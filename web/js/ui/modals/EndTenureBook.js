/* Port of game/ui/controllers/modals/EndTenureBookController.gd (+ EndTenureBookModal.tscn).
 *
 * EndTenureBook: Control (500,200), min 920x400 on ModalLayer (enlarged here to fit the radar).
 * Single autowrap page: "评级 %s %s\n第 %s 章 %s\n%s" % [letter, cap, chapter, title, body]
 * with the 5 build_epilogue_book chapters; body "<title>。任期至 <date>，综合分 <score>，等级 <letter>。"
 *
 * Data: the Python M14 compute_final_evaluation (overall_score, final_grade,
 * grade_capped_by_auth, dimensions{8}, ending_title, ...) fetched through the bridge.
 * Web intent fixes: next_page is wired (click / → key) and keeps the evaluation (Godot re-renders
 * with {} and would show letter "C"); the 8 dimension scores are drawn as a radar + list.
 */
import { el, rect, label, fmt, canvas } from "../../core/controls.js";

export const CHAPTER_TITLES = [
  "政治生涯与联盟沉浮",
  "战争、条约与中东棋局",
  "谢克尔、通胀与社会转型",
  "土地、定居点与不可能三角",
  "最高法院、宪政遗产与后世盖棺定论",
];

/* M14 8 dimensions (sim/modules.py compute_final_evaluation D1..D8). */
const DIMENSIONS = [
  ["security", "安全与威慑", "安全"],
  ["economy", "经济与稳定", "经济"],
  ["cohesion", "社会凝聚与平等", "凝聚"],
  ["democracy", "民主与法治", "民主"],
  ["diplomacy", "外交与同盟", "外交"],
  ["territory", "领土与定居愿景", "领土"],
  ["palestine", "巴以冲突管理", "巴以"],
  ["leadership", "政党领导与政治遗产", "领导"],
];

const RADAR = 300;

export class EndTenureBookController {
  constructor(ctx) {
    this.ctx = ctx;
    this.chapter_index = 0;
    this.chapters = [];
    this.evaluation = {};
    this.visible = false;
    this._onKey = (ev) => {
      if (!this.visible || ev.repeat) return;
      if (ev.key === "ArrowRight") { ev.preventDefault(); this.nextPage(); }
    };
  }

  mount(layer) {
    this.layer = layer;
    this.root = rect(el("div", "end-book panel"), 500, 200, 1420, 760);
    this.root.id = "EndTenureBook";
    this.root.style.display = "none";
    this.header = label("", { size: 14, cls: "end-book-ending" });
    this.page = label("", { autowrap: true, cls: "end-book-page" });
    const [cv, g] = canvas(RADAR, RADAR);
    this.radar = cv;
    this.radarCtx = g;
    cv.classList.add("end-book-radar");
    this.dimList = label("", { cls: "end-book-dims" });
    this.footer = label("", { cls: "end-book-footer" });
    const left = el("div", "end-book-left");
    left.append(this.header, this.page);
    const right = el("div", "end-book-right");
    right.append(cv, this.dimList);
    this.root.append(left, right, this.footer);
    this.root.addEventListener("click", () => this.nextPage());
    layer.appendChild(this.root);
    window.addEventListener("keydown", this._onKey);
  }

  /** DeskMain: end_tenure_triggered(info) -> show(info, view). */
  async show(info, view) {
    view = view || this.ctx.engine.view();
    this.visible = true;
    this.root.style.display = "";
    this.page.textContent = "正在撰写盖棺定论…";
    const m14 = (view && view.modules.M14) || {};
    const pending = (view && view.pending) || {};
    const reason = String((m14.final_evaluation && m14.final_evaluation.end_reason) || m14.end_reason || pending.tenure_end || "resignation");
    let ev = {};
    try {
      ev = this.ctx.sim.finalEvaluation ? await this.ctx.sim.finalEvaluation(reason) : await this.ctx.sim.evaluate(reason);
    } catch (err) {
      console.warn("[EndTenureBook] evaluation failed", err);
    }
    this.present(ev || {}, (view && view.clock.date) || (info && info.date) || "");
  }

  /** present(state): compute_final_evaluation + build_epilogue_book, then render chapter 1. */
  present(evaluation, date) {
    const score = Number(evaluation.overall_score ?? evaluation.composite_score ?? 0);
    this.evaluation = {
      ...evaluation,
      letter: String(evaluation.final_grade ?? evaluation.letter ?? "C"),
      redline_cap: !!(evaluation.grade_capped_by_auth || evaluation.redline_cap),
      composite_score: score.toFixed(1),
    };
    this.chapters = CHAPTER_TITLES.map((title, i) => ({
      chapter: i + 1,
      title,
      body: fmt("%s。任期至 %s，综合分 %s，等级 %s。", title, date, this.evaluation.composite_score, this.evaluation.letter),
      compare_to: ["begin", "shamir", "peres", "rabin"],
      source: "epilogue_paragraphs",
    }));
    this.chapter_index = 0;
    const endTitle = evaluation.ending_title ? `结局  ${evaluation.ending_title}` : "";
    this.header.textContent = endTitle;
    this._drawDimensions(evaluation.dimensions || {});
    this._render(this.evaluation);
  }

  nextPage() {
    if (!this.chapters.length) return;
    this.chapter_index = Math.min(this.chapter_index + 1, this.chapters.length - 1);
    this._render(this.evaluation);
  }

  hide() {
    this.visible = false;
    if (this.root) this.root.style.display = "none";
  }

  _render(evaluation) {
    const letter = String(evaluation.letter ?? "C");
    const chapter = this.chapter_index < this.chapters.length ? this.chapters[this.chapter_index] : {};
    const cap = evaluation.redline_cap ? "宪政越界：最高评级封顶于 B" : "";
    this.page.textContent = fmt("评级 %s %s\n第 %s 章 %s\n%s", letter, cap, chapter.chapter ?? 1, chapter.title ?? "", chapter.body ?? "");
    const n = this.chapters.length || 1;
    this.footer.textContent = fmt("%d / %d   点击或按 → 翻页", this.chapter_index + 1, n);
  }

  _drawDimensions(dims) {
    const g = this.radarCtx;
    const c = RADAR / 2;
    const r = RADAR / 2 - 44;
    g.clearRect(0, 0, RADAR, RADAR);
    const n = DIMENSIONS.length;
    const pt = (i, v) => {
      const a = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      return [c + Math.cos(a) * r * v, c + Math.sin(a) * r * v];
    };
    g.lineWidth = 1;
    g.strokeStyle = "rgba(30,28,26,0.35)";
    for (const ring of [0.25, 0.5, 0.75, 1]) {
      g.beginPath();
      for (let i = 0; i <= n; i++) { const [x, y] = pt(i % n, ring); i ? g.lineTo(x, y) : g.moveTo(x, y); }
      g.stroke();
    }
    for (let i = 0; i < n; i++) { const [x, y] = pt(i, 1); g.beginPath(); g.moveTo(c, c); g.lineTo(x, y); g.stroke(); }
    g.beginPath();
    DIMENSIONS.forEach(([k], i) => {
      const v = Math.max(0, Math.min(100, Number(dims[k] ?? 0))) / 100;
      const [x, y] = pt(i, v);
      i ? g.lineTo(x, y) : g.moveTo(x, y);
    });
    g.closePath();
    g.fillStyle = "rgba(0,56,184,0.18)";
    g.fill();
    g.strokeStyle = "#0038B8";
    g.lineWidth = 2;
    g.stroke();
    g.fillStyle = "#1E1C1A";
    g.font = "12px " + getComputedStyle(document.body).fontFamily;
    g.textAlign = "center";
    g.textBaseline = "middle";
    DIMENSIONS.forEach(([, , short], i) => {
      const [x, y] = pt(i, 1.2);
      g.fillText(short, x, y);
    });
    this.dimList.textContent = DIMENSIONS.map(([k, zh]) => fmt("%s  %.1f", zh, Number(dims[k] ?? 0))).join("\n");
  }
}
