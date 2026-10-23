/* Port of game/ui/components/SparklineDrawer.gd (draw code reproduced 1:1 on a canvas). */
import { canvas } from "../../core/controls.js";

export class SparklineDrawer {
  constructor(width = 220, height = 48) {
    this.width = width;
    this.height = height;
    [this.node, this.g] = canvas(width, height);
    this.node.classList.add("sparkline");
    this.series = [];
    this.warnAt = -1.0;
    this.lineColor = [0, 56.1, 183.6]; // Color(0.0, 0.22, 0.72)
  }

  setSeries(values, threshold = -1.0) {
    this.series = (values || []).map(Number).filter((v) => Number.isFinite(v));
    this.warnAt = threshold;
    this.draw();
  }

  draw() {
    const g = this.g;
    const { width, height, series } = this;
    g.clearRect(0, 0, width, height);
    if (series.length < 2) return;
    let lo = series[0];
    let hi = series[0];
    for (const v of series) { lo = Math.min(lo, v); hi = Math.max(hi, v); }
    if (Math.abs(hi - lo) < 0.001) hi = lo + 1.0;
    const pts = series.map((v, i) => [width * i / (series.length - 1), height - (v - lo) / (hi - lo) * height]);
    const [r, gg, b] = this.lineColor;
    // draw_colored_polygon(points + (w,h) + (0,h), colour α0.18)
    g.beginPath();
    pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
    g.lineTo(width, height);
    g.lineTo(0, height);
    g.closePath();
    g.fillStyle = `rgba(${r},${gg},${b},0.18)`;
    g.fill();
    // draw_polyline(points, colour, 1.5, antialiased)
    g.beginPath();
    pts.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
    g.strokeStyle = `rgb(${r},${gg},${b})`;
    g.lineWidth = 1.5;
    g.lineJoin = "round";
    g.stroke();
    // draw_circle(last, 3.0, colour)
    const [lx, ly] = pts[pts.length - 1];
    g.beginPath();
    g.arc(lx, ly, 3.0, 0, Math.PI * 2);
    g.fillStyle = `rgb(${r},${gg},${b})`;
    g.fill();
    // draw_dashed_line at warn_at (#B8292F, width 1, Godot default dash 2)
    if (this.warnAt >= lo && this.warnAt <= hi) {
      const yw = height - (this.warnAt - lo) / (hi - lo) * height;
      g.save();
      g.setLineDash([2, 2]);
      g.beginPath();
      g.moveTo(0, yw);
      g.lineTo(width, yw);
      g.strokeStyle = "#B8292F";
      g.lineWidth = 1.0;
      g.stroke();
      g.restore();
    }
  }
}
