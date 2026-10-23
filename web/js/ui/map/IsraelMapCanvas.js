/* Port of game/ui/map/IsraelMapCanvas.gd + RegionPolygonNode.gd + MapSitePin.gd
 * (+ occupied_hatch.gdshader, intended look).
 *
 * Map-local origin = screen (240,52), size 1440x942. Regions are the hard-coded schematic
 * rectangles, drawn in sorted-id order; non-existing regions are hidden; site pins are drawn
 * after all regions. Heat layers F1–F7 use the exact _layer_color formulas.
 *
 * Intent fixes vs the Godot build (see spec §8d):
 *  - wheel zoom ±0.1 in [0.8, 3.0] about the cursor (Godot scales about the top-left);
 *  - right/middle drag pans without discarding the (240,52) offset; double-click restores
 *    the original placement (Godot jumps to screen (0,0));
 *  - left click hit-tests the polygons (zoom/pan aware) and emits region_selected(id);
 *    clicking empty map emits region_selected("") which clears the selection;
 *  - selected region border 4px #C88A1E (RegionPolygonNode.set_selected, never called in Godot);
 *  - occupied regions get layer colour + 45° hatch (the shader's intent) instead of the
 *    untextured-white result of the literal shader;
 *  - addition: a small legend label naming the active layer (Godot shows none).
 * Drawing is clipped to the map rect (Godot Control does not clip, but HUD layers cover it). */
import { registerReads } from "../../core/StateView.js";
import { el, rect, label } from "../../core/controls.js";
import { MAP_RECT, REGION_IDS, schematic, centroid, isOccupied, regionExists, pointInPolygon } from "./mapGeometry.js";

registerReads(REGION_IDS.flatMap((id) => [["region_security", id], ["region_development", id]]));

/** Legend names (web addition; names follow docs/specs/M11_map_regions.md §9.2 where they
 * match what the Godot formula actually shows). */
export const LAYER_NAMES = [
  "",
  "F1 主权与法律地位",
  "F2 行政区划",
  "F3 治安热度",
  "F4 发展水平",
  "F5 定居与人口",
  "F6 选民倾向",
  "F7 战略纵深与水源",
];

const INK = "#1E1C1A";
const AMBER = "#C88A1E";
const HATCH = [46, 41, 36, 0.55]; // vec4(0.18, 0.16, 0.14, 0.55)
const HATCH_DENSITY = 14;

const rgba = (r, g, b, a) => `rgba(${r},${g},${b},${a})`;
const c255 = (v) => Math.max(0, Math.min(255, v * 255));

function pinColor(status) {
  switch (status) {
    case "planned": case "building": return "#C88A1E";   // (0.784,0.541,0.118)
    case "crisis": case "attacked": return "#B8292F";     // (0.722,0.161,0.184)
    case "demolished": case "removed": return "#736B61";  // (0.45,0.42,0.38)
    default: return "#9E7529";                            // (0.62,0.46,0.16)
  }
}

export class IsraelMapCanvas {
  constructor(ctx) {
    this.ctx = ctx;
    this.layerIndex = 1;
    this.zoom = 1.0;
    this.pan = [0, 0]; // map-local translation (screen offset 240,52 is kept by the DOM rect)
    this.view = null;
    this.selected = "";
    this.regions = []; // [{id, src, poly, occupied, visible, color}]
    this.sites = [];
    this.panning = null;
  }

  mount(layer) {
    this.layer = layer;
    const root = rect(el("div", "map-canvas"), MAP_RECT.left, MAP_RECT.top, MAP_RECT.left + MAP_RECT.width, MAP_RECT.top + MAP_RECT.height);
    this.root = root;
    this.canvas = el("canvas", "map-canvas-surface");
    this.dpr = Math.max(1, window.devicePixelRatio || 1) * 1.5;
    this.canvas.width = Math.round(MAP_RECT.width * this.dpr);
    this.canvas.height = Math.round(MAP_RECT.height * this.dpr);
    this.canvas.style.width = `${MAP_RECT.width}px`;
    this.canvas.style.height = `${MAP_RECT.height}px`;
    this.g = this.canvas.getContext("2d");
    root.appendChild(this.canvas);
    this.legend = label(LAYER_NAMES[this.layerIndex], { cls: "map-legend" });
    root.appendChild(this.legend);
    layer.appendChild(root);
    this._bindInput();
    this.ctx.bus.connect("region_selected", (id) => { this.selected = id || ""; this._draw(); });
    this.buildFromRegistry(null);
  }

  /** build_from_registry: region nodes in sorted id order, then pins. */
  buildFromRegistry(view) {
    if (view) this.view = view;
    const defs = (this.ctx.data.regions && this.ctx.data.regions.regions) || {};
    const ids = Object.keys(defs).sort();
    this.regions = ids.map((id) => ({
      id,
      src: defs[id] || {},
      poly: schematic(id),
      occupied: isOccupied(defs[id]),
      visible: regionExists(id, defs[id], this.view),
      color: "",
    }));
    this._placePins();
    this.setMapLayer(this.layerIndex, this.view);
  }

  _placePins() {
    const live = this.view && this.view.modules && this.view.modules.M11 ? this.view.modules.M11.key_sites : null;
    const sites = Array.isArray(live) && live.length ? live : ((this.ctx.data.regions && this.ctx.data.regions.key_sites) || []);
    const byId = new Map(this.regions.map((r) => [r.id, r]));
    this.sites = [];
    sites.forEach((site, i) => {
      if (!site || typeof site !== "object") return;
      const rid = String(site.region_id || "");
      const c = centroid(rid);
      let at = [c[0] + (i % 5) * 8, c[1] + (i % 3) * 8];
      const node = byId.get(rid);
      if (node && node.poly.length) at = [node.poly[0][0] + 12 + (i % 4) * 10, node.poly[0][1] + 12];
      this.sites.push({ id: String(site.site_id || ""), region: rid, status: String(site.status || "active"), at });
    });
  }

  /** set_map_layer(index): recolour every region (DeskMain passes the current view). */
  setMapLayer(index, view) {
    if (view) this.view = view;
    this.layerIndex = Math.min(7, Math.max(1, Number(index) || 1));
    for (const r of this.regions) r.color = this._layerColor(r);
    if (this.legend) this.legend.textContent = LAYER_NAMES[this.layerIndex];
    this._draw();
  }

  refresh(view) {
    if (!view) return;
    const fresh = !this.view;
    this.view = view;
    for (const r of this.regions) r.visible = regionExists(r.id, r.src, view);
    if (fresh || !this.regions.length) this.buildFromRegistry(view);
    else { this._placePins(); this.setMapLayer(this.layerIndex, view); }
  }

  _layerColor(r) {
    let s = 60.0;
    let d = 40.0;
    if (this.view) {
      s = this.view.param("region_security", r.id);
      d = this.view.param("region_development", r.id);
    }
    switch (this.layerIndex) {
      case 1: return r.occupied ? rgba(c255(0.55), c255(0.42), c255(0.22), 0.8) : rgba(0, c255(0.22), c255(0.72), 0.75);
      case 2: return rgba(0, c255(0.22), c255(0.72), 0.8);
      case 3: return rgba(c255(1.0 - s / 100.0), c255(s / 100.0), c255(0.2), 0.85);
      case 4: return rgba(c255(0.15), c255(0.25 + d / 200.0), c255(0.45), 0.85);
      case 5: return rgba(c255(0.45), c255(0.25), c255(0.55), 0.8);
      case 6: return rgba(c255(0.72), c255(0.25), c255(0.18), 0.75);
      default: return rgba(c255(0.15), c255(0.35), c255(0.62), 0.55);
    }
  }

  // ------------------------------------------------------------------ drawing
  _draw() {
    const g = this.g;
    if (!g) return;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, this.canvas.width, this.canvas.height);
    const k = this.dpr * this.zoom;
    g.setTransform(k, 0, 0, k, this.dpr * this.pan[0], this.dpr * this.pan[1]);
    for (const r of this.regions) {
      if (!r.visible) continue;
      this._fillRegion(r);
      this._stroke(r.poly, INK, 2.0);
    }
    const sel = this.regions.find((r) => r.id === this.selected && r.visible);
    if (sel) this._stroke(sel.poly, AMBER, 4.0);
    for (const p of this.sites) {
      g.beginPath();
      g.arc(p.at[0], p.at[1], 5.0, 0, Math.PI * 2);
      g.fillStyle = pinColor(p.status);
      g.fill();
      g.beginPath();
      g.moveTo(p.at[0], p.at[1]);
      g.lineTo(p.at[0], p.at[1] + 10);
      g.strokeStyle = "#33291A";
      g.lineWidth = 1.5;
      g.stroke();
    }
  }

  _path(poly) {
    const g = this.g;
    g.beginPath();
    poly.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y)));
    g.closePath();
  }

  _stroke(poly, color, width) {
    this._path(poly);
    this.g.strokeStyle = color;
    this.g.lineWidth = width;
    this.g.lineJoin = "miter";
    this.g.stroke();
  }

  /** Polygon2D fill; occupied: stripe = step(0.55, fract((u+v)*14)), rgb = mix(rgb, hatch, stripe*0.55). */
  _fillRegion(r) {
    const g = this.g;
    if (!r.occupied) {
      this._path(r.poly);
      g.fillStyle = r.color;
      g.fill();
      return;
    }
    const xs = r.poly.map((p) => p[0]);
    const ys = r.poly.map((p) => p[1]);
    const x0 = Math.min(...xs);
    const y0 = Math.min(...ys);
    const w = Math.max(...xs) - x0 || 1;
    const h = Math.max(...ys) - y0 || 1;
    const m = /rgba\(([^,]+),([^,]+),([^,]+),([^)]+)\)/.exec(r.color);
    const [br, bg, bb, ba] = m.slice(1).map(Number);
    const t = HATCH[3];
    const striped = rgba(br + (HATCH[0] - br) * t, bg + (HATCH[1] - bg) * t, bb + (HATCH[2] - bb) * t, ba);
    // Stripe bands in UV space (u,v in [0,1] over the polygon bbox): u+v in [(n+0.55)/14, (n+1)/14].
    const stripes = new Path2D();
    for (let n = 0; n < HATCH_DENSITY * 2; n++) {
      const a = (n + 0.55) / HATCH_DENSITY;
      const b = (n + 1) / HATCH_DENSITY;
      const P = (u, v) => [x0 + u * w, y0 + v * h];
      const q = [P(a + 1, -1), P(b + 1, -1), P(-1, b + 1), P(-1, a + 1)];
      stripes.moveTo(...q[0]); stripes.lineTo(...q[1]); stripes.lineTo(...q[2]); stripes.lineTo(...q[3]); stripes.closePath();
    }
    const outside = new Path2D();
    outside.rect(x0 - 10, y0 - 10, w + 20, h + 20);
    outside.addPath(stripes);
    // Base colour outside the stripes.
    g.save();
    this._path(r.poly); g.clip();
    g.clip(outside, "evenodd");
    this._path(r.poly); g.fillStyle = r.color; g.fill();
    g.restore();
    // Hatched colour inside the stripes.
    g.save();
    this._path(r.poly); g.clip();
    g.clip(stripes);
    this._path(r.poly); g.fillStyle = striped; g.fill();
    g.restore();
  }

  // ------------------------------------------------------------------ input
  _stageScale() {
    const b = this.root.getBoundingClientRect();
    return b.width / MAP_RECT.width || 1;
  }

  /** Mouse event -> map-local (unzoomed control) coordinates. */
  _local(ev) {
    const b = this.root.getBoundingClientRect();
    const s = this._stageScale();
    return [(ev.clientX - b.left) / s, (ev.clientY - b.top) / s];
  }

  /** Map-local -> region coordinate space (undo pan/zoom). */
  _toWorld([x, y]) { return [(x - this.pan[0]) / this.zoom, (y - this.pan[1]) / this.zoom]; }

  setZoom(next, anchor = [0, 0]) {
    const z = Math.min(3.0, Math.max(0.8, Math.round(next * 10) / 10));
    const w = this._toWorld(anchor);
    this.zoom = z;
    this.pan = [anchor[0] - w[0] * z, anchor[1] - w[1] * z];
    this._draw();
  }

  resetView() {
    this.zoom = 1.0;
    this.pan = [0, 0];
    this._draw();
  }

  regionAt(world) {
    for (let i = this.regions.length - 1; i >= 0; i--) {
      const r = this.regions[i];
      if (r.visible && pointInPolygon(world, r.poly)) return r.id;
    }
    return "";
  }

  _bindInput() {
    const c = this.canvas;
    c.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      if (ev.deltaY === 0) return;
      this.setZoom(this.zoom + (ev.deltaY < 0 ? 0.1 : -0.1), this._local(ev));
    }, { passive: false });
    c.addEventListener("contextmenu", (ev) => ev.preventDefault());
    c.addEventListener("pointerdown", (ev) => {
      if (ev.button === 1 || ev.button === 2) {
        ev.preventDefault();
        this.panning = { id: ev.pointerId, x: ev.clientX, y: ev.clientY };
        try { c.setPointerCapture(ev.pointerId); } catch { /* synthetic / inactive pointer */ }
      }
    });
    c.addEventListener("pointermove", (ev) => {
      if (!this.panning || ev.pointerId !== this.panning.id) return;
      const s = this._stageScale();
      this.pan = [this.pan[0] + (ev.clientX - this.panning.x) / s, this.pan[1] + (ev.clientY - this.panning.y) / s];
      this.panning.x = ev.clientX;
      this.panning.y = ev.clientY;
      this._draw();
    });
    const end = (ev) => {
      if (this.panning && ev.pointerId === this.panning.id) {
        this.panning = null;
        if (c.hasPointerCapture(ev.pointerId)) c.releasePointerCapture(ev.pointerId);
      }
    };
    c.addEventListener("pointerup", end);
    c.addEventListener("pointercancel", end);
    c.addEventListener("auxclick", (ev) => ev.preventDefault());
    c.addEventListener("click", (ev) => {
      if (ev.button !== 0 || ev.detail > 1) return;
      const id = this.regionAt(this._toWorld(this._local(ev)));
      if (id || this.selected) this.ctx.bus.emit("region_selected", id);
    });
    c.addEventListener("dblclick", (ev) => { ev.preventDefault(); this.resetView(); });
  }
}
