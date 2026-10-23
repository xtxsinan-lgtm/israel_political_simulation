/* Port of game/ui/components/CausalGraphCanvas.gd.
 * focus_node(id): collect edges of causal_edges_def touching the node (keys from/source,
 * to/target), adding endpoints until 12 nodes. Node i at (80+(i%4)*160, 70+row*110), r22,
 * focus #0038B8 else #1F1C1A; edges #3B6B36 2px.
 * Intent fixes (Godot draws every edge as the same (80,70)->(240,180) line, uses float
 * division for rows and compares "param:"-prefixed sources verbatim):
 *  - endpoint ids are normalised ("param:inflation" -> "inflation"),
 *  - rows use integer division (4 nodes per row) and the canvas is 640x340 so the 3rd row fits,
 *  - one arrow per real edge between its endpoints (curved so A->B and B->A stay distinct),
 *  - node labels; clicking a node emits tooltip_requested(nodeId, ""). */
import { canvas } from "../../core/controls.js";

const W = 640;
const H = 340;
const R = 22;
const BLUE = "#0038B8";
const INK = "#1F1C1A";
const GREEN = "#3B6B36";

export function normId(raw) {
  const s = String(raw ?? "");
  return s.startsWith("param:") ? s.slice(6) : s;
}

export class CausalGraphCanvas {
  constructor(ctx) {
    this.ctx = ctx;
    this.focusId = "";
    this.nodes = [];
    this.edges = [];
  }

  mount(parent) {
    [this.canvas, this.g] = canvas(W, H);
    this.canvas.classList.add("causal-graph");
    this.canvas.addEventListener("click", (ev) => this.onClick(ev));
    this.canvas.addEventListener("mousemove", (ev) => {
      this.canvas.style.cursor = this.hit(ev) >= 0 ? "pointer" : "default";
    });
    parent.appendChild(this.canvas);
  }

  focusNode(nodeId) {
    this.focusId = nodeId;
    this.nodes = [nodeId];
    this.edges = [];
    const def = this.ctx.data.causal_edges || {};
    const list = Array.isArray(def) ? def : (def.edges || []);
    for (const edge of list) {
      const src = normId(edge.from ?? edge.source ?? "");
      const dst = normId(edge.to ?? edge.target ?? "");
      if (src === nodeId || dst === nodeId) {
        this.edges.push({ src, dst, label: edge.label_zh || edge.id || "" });
        if (src !== "" && !this.nodes.includes(src)) this.nodes.push(src);
        if (dst !== "" && !this.nodes.includes(dst)) this.nodes.push(dst);
      }
      if (this.nodes.length >= 12) break;
    }
    this.draw();
  }

  pos(i) { return [80 + (i % 4) * 160, 70 + Math.floor(i / 4) * 110]; }

  draw() {
    const g = this.g;
    g.clearRect(0, 0, W, H);
    // Edges are drawn under the nodes (Godot draws them on top) so labels stay legible.
    g.strokeStyle = GREEN;
    g.fillStyle = GREEN;
    g.lineWidth = 2.0;
    for (const e of this.edges) {
      const a = this.nodes.indexOf(e.src);
      const b = this.nodes.indexOf(e.dst);
      if (a < 0 || b < 0) continue;
      if (a === b) this.drawLoop(...this.pos(a));
      else this.drawArrow(...this.pos(a), ...this.pos(b));
    }
    g.font = "12px " + getComputedStyle(document.body).getPropertyValue("--font-ui");
    g.textAlign = "center";
    g.textBaseline = "top";
    for (let i = 0; i < this.nodes.length; i++) {
      const [x, y] = this.pos(i);
      g.fillStyle = this.nodes[i] === this.focusId ? BLUE : INK;
      g.beginPath();
      g.arc(x, y, R, 0, Math.PI * 2);
      g.fill();
      const w = g.measureText(this.nodes[i]).width + 6;
      g.fillStyle = "rgba(244,239,230,0.9)";
      g.fillRect(x - w / 2, y + R + 2, w, 15);
      g.fillStyle = INK;
      g.fillText(this.nodes[i], x, y + R + 3);
    }
  }

  drawArrow(x1, y1, x2, y2) {
    const g = this.g;
    const dx = x2 - x1, dy = y2 - y1;
    const len = Math.hypot(dx, dy) || 1;
    const nx = -dy / len, ny = dx / len;
    // Longer edges bow further so they clear the nodes in between.
    const bend = Math.min(70, 14 + len * 0.12);
    const cx = (x1 + x2) / 2 + nx * bend, cy = (y1 + y2) / 2 + ny * bend;
    // Start/end on the circle rims, aimed at the control point.
    const sa = Math.atan2(cy - y1, cx - x1), ea = Math.atan2(cy - y2, cx - x2);
    const sx = x1 + Math.cos(sa) * R, sy = y1 + Math.sin(sa) * R;
    const ex = x2 + Math.cos(ea) * (R + 1), ey = y2 + Math.sin(ea) * (R + 1);
    g.beginPath();
    g.moveTo(sx, sy);
    g.quadraticCurveTo(cx, cy, ex, ey);
    g.stroke();
    this.drawHead(ex, ey, Math.atan2(ey - cy, ex - cx));
  }

  drawLoop(x, y) {
    const g = this.g;
    g.beginPath();
    g.arc(x + R * 0.9, y - R * 0.9, 11, Math.PI * 0.75, Math.PI * 2.25 + 0.4);
    g.stroke();
    const ex = x + R * 0.9 + Math.cos(Math.PI * 0.25 + 0.4) * 11;
    const ey = y - R * 0.9 + Math.sin(Math.PI * 0.25 + 0.4) * 11;
    this.drawHead(ex, ey, Math.PI * 0.75 + 0.4);
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
      if (Math.hypot(x - nx, y - ny) <= R) return i;
    }
    return -1;
  }

  onClick(ev) {
    const i = this.hit(ev);
    if (i >= 0) this.ctx.bus.emit("tooltip_requested", this.nodes[i], "");
  }
}
