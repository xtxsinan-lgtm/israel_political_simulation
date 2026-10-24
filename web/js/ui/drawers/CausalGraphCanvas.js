/* Port of game/ui/components/CausalGraphCanvas.gd, upgraded into an intuitive 3-column
 * (上游原因 → 当前焦点指标 → 下游传导结果) Chinese causal network viewer.
 * Clicking any node both refocuses the graph on that node and emits tooltip_requested(nodeId, ""). */
import { canvas } from "../../core/controls.js";
import { paramZh } from "./drawer_helpers.js";

const W = 880;
const H = 270;
const R = 21;
const R_FOCUS = 26;
const BLUE = "#0038B8";
const INK = "#1F1C1A";
const GREEN = "#2E6F40";
const RED = "#B8292F";
const AMBER = "#8A5A0C";

export function normId(raw) {
  const s = String(raw ?? "");
  return s.startsWith("param:") ? s.slice(6) : s;
}

export class CausalGraphCanvas {
  constructor(ctx, onFocusChange = null) {
    this.ctx = ctx;
    this.onFocusChange = onFocusChange;
    this.focusId = "";
    this.nodes = [];
    this.edges = [];
    this.nodePositions = [];
    this.nodeRoles = {}; // id -> "focus" | "in" | "out" | "both"
    this.lastView = null;
  }

  mount(parent) {
    [this.canvas, this.g] = canvas(W, H);
    this.canvas.classList.add("causal-graph");
    this.canvas.addEventListener("click", (ev) => this.onClick(ev));
    this.canvas.addEventListener("mousemove", (ev) => {
      const idx = this.hit(ev);
      this.canvas.style.cursor = idx >= 0 ? "pointer" : "default";
      if (idx >= 0) {
        const nid = this.nodes[idx];
        const zh = paramZh(this.ctx, nid);
        const relEdges = this.edges.filter((e) => e.src === nid || e.dst === nid);
        const desc = relEdges.map((e) => e.label).filter(Boolean).join("；");
        this.canvas.title = `${zh} (${nid})${desc ? "\n因果机制：" + desc : "\n点击切换为焦点并查看因果拆解"}`;
      } else {
        this.canvas.title = "点击任意节点可将其设为中心焦点，并查看详细因果公式拆解";
      }
    });
    parent.appendChild(this.canvas);
  }

  setView(view) {
    this.lastView = view;
    if (this.focusId) this.draw();
  }

  focusNode(nodeId) {
    this.focusId = nodeId;
    this.nodes = [nodeId];
    this.edges = [];
    this.nodeRoles = { [nodeId]: "focus" };

    const def = this.ctx.data.causal_edges || {};
    const list = Array.isArray(def) ? def : (def.edges || []);
    const inNodes = [];
    const outNodes = [];

    for (const edge of list) {
      const src = normId(edge.from ?? edge.source ?? "");
      const dst = normId(edge.to ?? edge.target ?? "");
      if (!src || !dst || src === dst) continue;
      if (src === nodeId || dst === nodeId) {
        const coef = edge.coef !== undefined && edge.coef !== null ? Number(edge.coef) : null;
        this.edges.push({
          src,
          dst,
          coef,
          label: edge.label_zh || edge.id || "",
        });
        if (dst === nodeId && src !== nodeId) {
          if (!inNodes.includes(src) && inNodes.length < 5) inNodes.push(src);
        }
        if (src === nodeId && dst !== nodeId) {
          if (!outNodes.includes(dst) && !inNodes.includes(dst) && outNodes.length < 5) outNodes.push(dst);
        }
      }
    }

    for (const n of inNodes) {
      if (!this.nodes.includes(n)) {
        this.nodes.push(n);
        this.nodeRoles[n] = "in";
      }
    }
    for (const n of outNodes) {
      if (!this.nodes.includes(n)) {
        this.nodes.push(n);
        this.nodeRoles[n] = "out";
      }
    }

    // Compute structured 3-column positions: Left = Upstream causes, Center = Focus, Right = Downstream effects
    this.nodePositions = new Array(this.nodes.length);
    this.nodePositions[0] = [W / 2, H / 2 + 6];

    const placeColumn = (arr, x) => {
      const count = arr.length;
      if (!count) return;
      const topY = 52;
      const botY = H - 36;
      for (let k = 0; k < count; k++) {
        const y = count === 1 ? (H / 2 + 6) : topY + (k / (count - 1)) * (botY - topY);
        const idx = this.nodes.indexOf(arr[k]);
        if (idx >= 0) this.nodePositions[idx] = [x, y];
      }
    };
    placeColumn(inNodes, 145);
    placeColumn(outNodes, W - 145);

    this.draw();
  }

  pos(i) {
    return this.nodePositions[i] || [80 + (i % 4) * 160, 70 + Math.floor(i / 4) * 90];
  }

  _nodeValueText(nid) {
    const v = this.lastView || (this.ctx && this.ctx.engine && this.ctx.engine.view && this.ctx.engine.view());
    if (!v || !v.raw) return "";
    const params = v.raw.params || {};
    if (typeof params[nid] === "number") return params[nid].toFixed(0);
    if (params.budget_slider && typeof params.budget_slider[nid] === "number") return params.budget_slider[nid].toFixed(0);
    if (v.policies && v.policies[nid] && typeof v.policies[nid].level === "number") return v.policies[nid].level.toFixed(0);
    return "";
  }

  draw() {
    const g = this.g;
    if (!g) return;
    g.clearRect(0, 0, W, H);

    // Column headers so the user immediately understands Left -> Center -> Right
    const fontUi = getComputedStyle(document.body).getPropertyValue("--font-ui") || "sans-serif";
    g.font = `bold 12px ${fontUi}`;
    g.fillStyle = "#736B61";
    g.textAlign = "center";
    g.textBaseline = "top";
    g.fillText("◀ 上游驱动原因 (影响当前指标的因素)", 155, 8);
    g.fillStyle = BLUE;
    g.fillText("● 当前聚焦指标 (点击其他节点可切换)", W / 2, 8);
    g.fillStyle = "#736B61";
    g.fillText("下游传导结果 (受当前指标影响的领域) ▶", W - 155, 8);

    // Legend in bottom-left
    g.font = `11px ${fontUi}`;
    g.textAlign = "left";
    g.fillStyle = GREEN;
    g.fillText("━━▶ 正向推动 (+)", 12, H - 18);
    g.fillStyle = RED;
    g.fillText("━━▶ 负向抑制 (−)", 125, H - 18);
    g.fillStyle = AMBER;
    g.fillText("━━▶ 复合公式传导 (ƒ)", 238, H - 18);

    // Draw edges beneath nodes
    for (const e of this.edges) {
      const a = this.nodes.indexOf(e.src);
      const b = this.nodes.indexOf(e.dst);
      if (a < 0 || b < 0 || a === b) continue;
      const color = e.coef === null ? AMBER : (e.coef >= 0 ? GREEN : RED);
      const signTag = e.coef === null ? "ƒ" : (e.coef >= 0 ? `+${e.coef}` : `${e.coef}`);
      const shortLabel = e.label ? (e.label.length > 12 ? e.label.slice(0, 12) + "…" : e.label) : signTag;
      this.drawArrow(...this.pos(a), ...this.pos(b), color, shortLabel, a === 0 ? R_FOCUS : R, b === 0 ? R_FOCUS : R);
    }

    // Draw nodes with value inside and Chinese name below
    for (let i = 0; i < this.nodes.length; i++) {
      const nid = this.nodes[i];
      const [x, y] = this.pos(i);
      const isFocus = nid === this.focusId;
      const rad = isFocus ? R_FOCUS : R;

      g.fillStyle = isFocus ? BLUE : INK;
      g.beginPath();
      g.arc(x, y, rad, 0, Math.PI * 2);
      g.fill();

      // Value inside the circle
      const valTxt = this._nodeValueText(nid);
      g.fillStyle = "#F4EFE6";
      g.font = `bold ${isFocus ? 13 : 11}px ${fontUi}`;
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText(valTxt || (isFocus ? "焦点" : "•"), x, y);

      // Chinese label pill below circle
      const zh = paramZh(this.ctx, nid);
      const labelTxt = zh !== nid ? `${zh}` : nid;
      g.font = `${isFocus ? "bold 12px" : "12px"} ${fontUi}`;
      const tw = g.measureText(labelTxt).width + 8;
      g.fillStyle = "rgba(244, 239, 230, 0.94)";
      g.fillRect(x - tw / 2, y + rad + 2, tw, 16);
      g.strokeStyle = isFocus ? BLUE : "rgba(30,28,26,0.25)";
      g.lineWidth = 1;
      g.strokeRect(x - tw / 2, y + rad + 2, tw, 16);
      g.fillStyle = isFocus ? BLUE : INK;
      g.textBaseline = "top";
      g.fillText(labelTxt, x, y + rad + 4);
    }
  }

  drawArrow(x1, y1, x2, y2, color, edgeLabel, r1, r2) {
    const g = this.g;
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len, ny = dx / len;
    const bend = Math.min(28, 6 + len * 0.04);
    const cx = (x1 + x2) / 2 + nx * bend;
    const cy = (y1 + y2) / 2 + ny * bend;
    const sa = Math.atan2(cy - y1, cx - x1);
    const ea = Math.atan2(cy - y2, cx - x2);
    const sx = x1 + Math.cos(sa) * r1;
    const sy = y1 + Math.sin(sa) * r1;
    const ex = x2 + Math.cos(ea) * (r2 + 2);
    const ey = y2 + Math.sin(ea) * (r2 + 2);

    g.strokeStyle = color;
    g.fillStyle = color;
    g.lineWidth = 2.0;
    g.beginPath();
    g.moveTo(sx, sy);
    g.quadraticCurveTo(cx, cy, ex, ey);
    g.stroke();
    this.drawHead(ex, ey, Math.atan2(ey - cy, ex - cx));

    if (edgeLabel) {
      const mx = 0.25 * sx + 0.5 * cx + 0.25 * ex;
      const my = 0.25 * sy + 0.5 * cy + 0.25 * ey;
      const fontUi = getComputedStyle(document.body).getPropertyValue("--font-ui") || "sans-serif";
      g.font = `10px ${fontUi}`;
      const w = g.measureText(edgeLabel).width + 6;
      g.fillStyle = "rgba(244, 239, 230, 0.88)";
      g.fillRect(mx - w / 2, my - 7, w, 13);
      g.fillStyle = color;
      g.textAlign = "center";
      g.textBaseline = "middle";
      g.fillText(edgeLabel, mx, my);
    }
  }

  drawHead(x, y, ang) {
    const g = this.g;
    const s = 8;
    g.beginPath();
    g.moveTo(x, y);
    g.lineTo(x - Math.cos(ang - 0.45) * s, y - Math.sin(ang - 0.45) * s);
    g.lineTo(x - Math.cos(ang + 0.45) * s, y - Math.sin(ang + 0.45) * s);
    g.closePath();
    g.fill();
  }

  hit(ev) {
    const r = this.canvas.getBoundingClientRect();
    const x = (ev.clientX - r.left) * (W / r.width);
    const y = (ev.clientY - r.top) * (H / r.height);
    for (let i = 0; i < this.nodes.length; i++) {
      const [nx, ny] = this.pos(i);
      const rad = i === 0 ? R_FOCUS : R;
      if (Math.hypot(x - nx, y - ny) <= rad + 4) return i;
    }
    return -1;
  }

  onClick(ev) {
    const i = this.hit(ev);
    if (i >= 0) {
      const clickedId = this.nodes[i];
      if (clickedId !== this.focusId) {
        this.focusNode(clickedId);
        if (this.onFocusChange) this.onFocusChange(clickedId);
      }
      this.ctx.bus.emit("tooltip_requested", clickedId, "");
    }
  }
}
