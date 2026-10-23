/* Port of game/ui/map/IsraelMapCanvas.gd + RegionPolygonNode.gd + MapSitePin.gd
 * (+ occupied_hatch.gdshader, intended look), drawn as a real-geography antique map.
 *
 * Map-local origin = screen (240,52), size 1440x942. Geometry comes from ctx.data.map_geo
 * (game/res/map/map_geo.json, Natural Earth, see tools/build_map_geo.py): the 11 game regions,
 * neighbouring countries as context land, lakes, rivers, real site positions, sea/country labels.
 * Non-existing regions are hidden; site pins are drawn above all regions. Heat layers F1–F7 use
 * the exact _layer_color formulas (rendered as watercolour washes on the paper sheet).
 *
 * Rendering: one SVG built once in mount(); refresh() only touches fills / visibility / pin
 * status. Layers (bottom → top): sea wash + engraving lines, water-lining ripples, context land
 * (parchment + hachure), game regions (watercolour + edge darkening + occupied hatch), lakes,
 * rivers, graticule, wobbly ink borders, selection outline; then screen-space labels / pins (constant
 * size, positioned from the zoom/pan transform), and the fixed sheet ornaments (neat line with
 * degree band, compass rose, cartouche, scale bar).
 *
 * Intent fixes vs the Godot build (see spec §8d):
 *  - wheel zoom about the cursor in [0.8, 6.0] (Godot scales ±0.1 about the top-left); +/− and
 *    "聚焦以色列" buttons at the bottom-left;
 *  - right/middle drag pans without discarding the (240,52) offset; double-click restores
 *    the original placement (Godot jumps to screen (0,0));
 *  - left click hit-tests the real polygons (zoom/pan aware) and emits region_selected(id);
 *    clicking empty map emits region_selected("") which clears the selection;
 *  - selected region outlined #C88A1E (RegionPolygonNode.set_selected, never called in Godot);
 *  - occupied regions get layer colour + 45° hatch of rgba(46,41,36,0.55) (the shader's intent);
 *  - addition: a small legend label naming the active layer (Godot shows none). */
import { registerReads } from "../../core/StateView.js";
import { el, rect, label, button } from "../../core/controls.js";
import {
  MAP_RECT, REGION_IDS, setGeo, regionRings, centroid, isOccupied, regionExists,
  pointInRings, ringsPath, linePath, linesPath, classifyEdges, unproject,
} from "./mapGeometry.js";

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

const NS = "http://www.w3.org/2000/svg";
const W = MAP_RECT.width;
const H = MAP_RECT.height;
const AMBER = "#C88A1E";
const SEA = "#CBD8D5";
const ZOOM_MIN = 0.8;
const ZOOM_MAX = 6.0;
const FOCUS_LAT = [29.4, 33.5];
const FOCUS_REGIONS = ["galilee", "golan", "haifa", "tel_aviv", "triangle", "jerusalem", "negev", "west_bank", "gaza"];

/** Region label layout (zoom-1 map-local px). `anchor` = point inside the region, `at` = label
 * position; small regions get a leader line from anchor to a label in open sea / open land.
 * Leaders shrink as the map is zoomed in and vanish once the region is big enough (`full`). */
const REGION_LABELS = {
  galilee: { name: "加利利", anchor: [815, 118], at: [748, 104], align: "end", full: 2.6 },
  golan: { name: "戈兰", anchor: [877, 116], at: [930, 132], align: "start", full: 3.2 },
  haifa: { name: "海法", anchor: [784, 174], at: [714, 154], align: "end", full: 3.4 },
  triangle: { name: "中央区", anchor: [768, 228], at: [700, 207], align: "end", full: 9 },
  tel_aviv: { name: "特拉维夫", anchor: [753, 258], at: [690, 262], align: "end", full: 9 },
  jerusalem: { name: "耶路撒冷", anchor: [797, 307], at: [902, 318], align: "start", full: 9 },
  gaza: { name: "加沙", anchor: [699, 362], at: [642, 386], align: "end", full: 3.4 },
  west_bank: { name: "西岸", anchor: [823, 250], at: [902, 250], align: "start", full: 3 },
  negev: { name: "内盖夫", at: [756, 480], big: true },
  sinai: { name: "西奈", at: [628, 610], big: true },
  south_lebanon: { name: "南黎巴嫩", anchor: [842, 74], at: [770, 44], align: "end", full: 3 },
};

/** Context label overrides: position, style kind, minimum zoom. */
const LABEL_NUDGE = {
  黎巴嫩: { pos: [950, 44] },
  加利利海: { pos: [854, 146], minZoom: 1.9 },
  死海: { pos: [842, 352], minZoom: 1.25 },
  红海: { pos: [714, 912], kind: "sea_mid" },
  苏伊士湾: { pos: [520, 735] },
};

const rgba = (r, g, b, a) => `rgba(${r},${g},${b},${a})`;
const c255 = (v) => Math.round(Math.max(0, Math.min(255, v * 255)));

function pinColor(status) {
  switch (status) {
    case "planned": case "building": return "#C88A1E";   // (0.784,0.541,0.118)
    case "crisis": case "attacked": return "#B8292F";     // (0.722,0.161,0.184)
    case "demolished": case "removed": return "#736B61";  // (0.45,0.42,0.38)
    default: return "#9E7529";                            // (0.62,0.46,0.16)
  }
}

/** createElementNS helper. */
function S(tag, attrs = {}, parent = null, text = null) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v !== undefined && v !== null) n.setAttribute(k, String(v));
  if (text !== null) n.textContent = text;
  if (parent) parent.appendChild(n);
  return n;
}

/** Mix two #RRGGBB colours (t = share of b). */
function mix(a, b, t) {
  const p = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [x, y] = [p(a), p(b)];
  return "#" + x.map((v, i) => Math.round(v + (y[i] - v) * t).toString(16).padStart(2, "0")).join("");
}

export class IsraelMapCanvas {
  constructor(ctx) {
    this.ctx = ctx;
    this.layerIndex = 1;
    this.zoom = 1.0;
    this.pan = [0, 0]; // map-local translation (screen offset 240,52 is kept by the DOM rect)
    this.view = null;
    this.selected = "";
    this.regions = []; // [{id, src, rings, occupied, visible, color, nodes}]
    this.sites = [];   // [{id, region, status, at, node}]
    this.screenItems = []; // labels / pins positioned in screen space
    this.panning = null;
    this.rafPending = false;
    this.geo = ctx.data && ctx.data.map_geo && ctx.data.map_geo.regions ? ctx.data.map_geo : null;
    setGeo(this.geo);
  }

  mount(layer) {
    this.layer = layer;
    const root = rect(el("div", "map-canvas"), MAP_RECT.left, MAP_RECT.top, MAP_RECT.left + W, MAP_RECT.top + H);
    this.root = root;
    this.svg = S("svg", { class: "map-svg", width: W, height: H, viewBox: `0 0 ${W} ${H}` });
    root.appendChild(this.svg);
    root.appendChild(el("div", "map-grain"));
    this.legend = label(LAYER_NAMES[this.layerIndex], { cls: "map-legend" });
    root.appendChild(this.legend);
    root.appendChild(this._buildControls());
    layer.appendChild(root);
    this._buildSvg();
    this._bindInput();
    this.ctx.bus.connect("region_selected", (id) => { this.selected = id || ""; this._updateSelection(); });
    this.buildFromRegistry(null);
    this._applyTransform();
  }

  // ------------------------------------------------------------------ static SVG
  _buildSvg() {
    const svg = this.svg;
    const g = this.geo || { countries: [], lakes: [], rivers: [], labels: [], sites: {}, regions: {} };
    const defs = S("defs", {}, svg);
    this._buildDefs(defs);

    // Sea wash + horizontal engraving lines (fixed to the sheet).
    S("rect", { x: 0, y: 0, width: W, height: H, fill: SEA }, svg);
    S("rect", { x: 0, y: 0, width: W, height: H, fill: "url(#map-engrave)" }, svg);

    const world = S("g", { class: "map-world" }, svg);
    this.world = world;

    // Land polygons (clip) and coastlines (water-lining = coast strokes drawn behind the land).
    const landRings = [...g.countries.flatMap((c) => c.rings), ...Object.values(g.regions).flatMap((r) => r.rings)];
    const edges = classifyEdges() || { coast: [], countryBorders: [], regionBorders: {} };
    this.edges = edges;
    S("path", { id: "map-land-outline", d: ringsPath(landRings) }, defs);
    S("path", { id: "map-coast", d: linesPath(edges.coast), "vector-effect": "non-scaling-stroke" }, defs);
    const ripples = S("g", { class: "map-ripples", fill: "none", "stroke-linejoin": "round", "stroke-linecap": "round" }, world);
    const LINE = "#4E6E73";
    // Outer rings are hidden while the view moves (cheap frames), see _scheduleTransform.
    this.ripplesOuter = S("g", {}, ripples);
    S("use", { href: "#map-coast", stroke: "#7D9A9B", "stroke-width": 16, "stroke-opacity": 0.2, filter: "url(#map-soft)" }, this.ripplesOuter);
    [[36, 0.86], [26, 0.76], [18, 0.62], [11, 0.45], [5.5, 0.25]].forEach(([w, t]) => {
      const parent = w > 20 ? this.ripplesOuter : ripples;
      S("use", { href: "#map-coast", stroke: mix(LINE, SEA, t), "stroke-width": w }, parent);
      S("use", { href: "#map-coast", stroke: w > 6 ? SEA : "#BCCDCB", "stroke-width": w - 1.2 }, parent);
    });

    // Context land: parchment base (also seals slivers between admin polygons) + hachure.
    const land = S("g", { class: "map-context" }, world);
    S("use", { href: "#map-land-outline", fill: "#E9DFC8" }, land);
    S("use", { href: "#map-land-outline", fill: "url(#map-hachure)" }, land);
    // Inner coast shading on land (sepia, soft).
    S("use", { href: "#map-coast", fill: "none", stroke: "#8A7454", "stroke-width": 7, "stroke-opacity": 0.14, "clip-path": "url(#map-land-clip)" }, land);
    S("path", { d: linesPath(edges.countryBorders), fill: "none", stroke: "#6E5A3E", "stroke-width": 0.9, "stroke-dasharray": "6 2.2 1.2 2.2", "vector-effect": "non-scaling-stroke", "stroke-opacity": 0.85 }, land);

    // Game regions (fills are recoloured by refresh / setMapLayer).
    this.regionLayer = S("g", { class: "map-regions" }, world);

    // Lakes (deeper blue + inner water-lining) and rivers.
    const water = S("g", { class: "map-water" }, world);
    g.lakes.forEach((lake, i) => {
      const d = ringsPath(lake.rings);
      S("path", { id: `map-lake-${i}`, d }, defs);
      const clip = S("clipPath", { id: `map-lake-clip-${i}` }, defs);
      S("use", { href: `#map-lake-${i}` }, clip);
      S("path", { d, fill: "#A9C0C2" }, water);
      const inner = S("g", { "clip-path": `url(#map-lake-clip-${i})`, fill: "none" }, water);
      S("path", { d, stroke: "#6E8F95", "stroke-width": 5, "stroke-opacity": 0.5, "vector-effect": "non-scaling-stroke" }, inner);
      S("path", { d, stroke: "#A9C0C2", "stroke-width": 3.8, "vector-effect": "non-scaling-stroke" }, inner);
      S("path", { d, fill: "none", stroke: "#3F5F6A", "stroke-width": 0.8, "vector-effect": "non-scaling-stroke" }, water);
    });
    for (const r of g.rivers) {
      const d = linePath(r.points);
      if (!d) continue;
      const canal = /canal/i.test(r.name || "");
      S("path", { d, fill: "none", stroke: "#4D7088", "stroke-width": canal ? 1.3 : 1.0, "stroke-linecap": "round", "stroke-linejoin": "round", "vector-effect": "non-scaling-stroke", "stroke-dasharray": canal ? "6 1.5" : null }, water);
    }

    // 1° graticule (dotted, faint).
    this.graticule = S("g", { class: "map-graticule", fill: "none", stroke: "#4A4034", "stroke-width": 0.6, "stroke-opacity": 0.35, "stroke-dasharray": "1 3", "vector-effect": "non-scaling-stroke" }, world);
    if (this.geo) {
      const p = this.geo.projection;
      for (let lon = Math.ceil(p.lon_min) - 4; lon <= p.lon_min + W / p.px_per_deg_lon + 4; lon++) {
        const x = (lon - p.lon_min) * p.px_per_deg_lon;
        S("line", { x1: x, y1: -1200, x2: x, y2: H + 1200, "vector-effect": "non-scaling-stroke" }, this.graticule);
      }
      for (let lat = Math.floor(p.lat_max) + 4; lat >= p.lat_max - H / p.px_per_deg_lat - 4; lat--) {
        const y = (p.lat_max - lat) * p.px_per_deg_lat;
        S("line", { x1: -1600, y1: y, x2: W + 1600, y2: y, "vector-effect": "non-scaling-stroke" }, this.graticule);
      }
    }

    // Ink coastline + borders (wobbly) + selection outline.
    const inkLayer = this.inkLayer = S("g", { class: "map-ink", filter: "url(#map-wobble)", fill: "none", "stroke-linejoin": "round", "stroke-linecap": "round" }, world);
    S("use", { href: "#map-coast", stroke: "#3A3026", "stroke-width": 1.15 }, inkLayer);
    this.borderLayer = S("g", { class: "map-borders" }, inkLayer);
    this.selLayer = S("g", { class: "map-selection" }, inkLayer);
    this.selOutline = S("path", { d: "", stroke: AMBER, "stroke-width": 3.4, "vector-effect": "non-scaling-stroke", display: "none" }, this.selLayer);

    // Screen-space overlay: leaders, labels, pins.
    this.overlay = S("g", { class: "map-overlay" }, svg);
    this.leaderLayer = S("g", { class: "map-leaders" }, this.overlay);
    this.labelLayer = S("g", { class: "map-labels" }, this.overlay);
    this.pinLayer = S("g", { class: "map-pins" }, this.overlay);
    this._buildContextLabels(g.labels || []);

    // Fixed sheet ornaments.
    this.frame = S("g", { class: "map-frame" }, svg);
    this._buildCompass(S("g", { class: "map-compass", transform: "translate(150 250)" }, svg));
    this._buildCartouche(S("g", { class: "map-cartouche", transform: "translate(36 44)" }, svg));
    this.scaleBar = S("g", { class: "map-scalebar", transform: `translate(262 ${H - 46})` }, svg);
  }

  _buildDefs(defs) {
    // Engraving lines on the sea.
    const eng = S("pattern", { id: "map-engrave", width: 8, height: 5, patternUnits: "userSpaceOnUse" }, defs);
    S("line", { x1: 0, y1: 2.5, x2: 8, y2: 2.5, stroke: "#4F6A6E", "stroke-width": 0.45, "stroke-opacity": 0.14 }, eng);
    // Hachure on context land (screen-constant via patternTransform, see _applyTransform).
    this.hachure = S("pattern", { id: "map-hachure", width: 7, height: 7, patternUnits: "userSpaceOnUse" }, defs);
    S("path", { d: "M0,7 L7,0 M-1,1 L1,-1 M6,8 L8,6", stroke: "#7C6646", "stroke-width": 0.5, "stroke-opacity": 0.22 }, this.hachure);
    S("circle", { cx: 1.5, cy: 1.8, r: 0.35, fill: "#7C6646", "fill-opacity": 0.25 }, this.hachure);
    // Occupied hatch: 45° stripes of rgba(46,41,36,0.55) (occupied_hatch.gdshader intent).
    this.hatch = S("pattern", { id: "map-hatch", width: 6, height: 6, patternUnits: "userSpaceOnUse" }, defs);
    S("rect", { x: 0, y: 0, width: 1.7, height: 6, fill: "rgb(46,41,36)", "fill-opacity": 0.55 }, this.hatch);
    // Watercolour granulation over region washes (soft blotches, rasterised once as an image).
    const wash = S("pattern", { id: "map-wash", width: 360, height: 360, patternUnits: "userSpaceOnUse" }, defs);
    const washSvg = "<svg xmlns='http://www.w3.org/2000/svg' width='360' height='360'><filter id='w'><feTurbulence type='fractalNoise' baseFrequency='0.035' numOctaves='4' seed='11' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.16  0 0 0 0 0.12  0 0 0 0 0.08  1.1 0 0 0 -0.48'/></filter><rect width='360' height='360' filter='url(%23w)'/></svg>";
    S("image", { href: `data:image/svg+xml;utf8,${washSvg}`, width: 360, height: 360, opacity: 0.55 }, wash);
    // Soft blur.
    const soft = S("filter", { id: "map-soft", x: "-5%", y: "-5%", width: "110%", height: "110%" }, defs);
    S("feGaussianBlur", { stdDeviation: 2.2 }, soft);
    // Hand-drawn wobble for ink borders (scale kept ~1.5 screen px, see _applyTransform).
    const wob = S("filter", { id: "map-wobble", x: -400, y: -400, width: W + 800, height: H + 800, filterUnits: "userSpaceOnUse", primitiveUnits: "userSpaceOnUse" }, defs);
    this.wobbleNoise = S("feTurbulence", { type: "fractalNoise", baseFrequency: 0.06, numOctaves: 2, seed: 7, result: "n" }, wob);
    this.wobbleDisp = S("feDisplacementMap", { in: "SourceGraphic", in2: "n", scale: 1.5, xChannelSelector: "R", yChannelSelector: "G" }, wob);
    // Land clip (for the inner coast shading).
    const lc = S("clipPath", { id: "map-land-clip" }, defs);
    S("use", { href: "#map-land-outline" }, lc);
  }

  _buildContextLabels(labels) {
    for (const lb of labels) {
      const nudge = LABEL_NUDGE[lb.text] || {};
      const pos = nudge.pos || lb.pos;
      const kind = nudge.kind || lb.kind;
      const g = S("g", { class: `map-label map-label-${kind}` }, this.labelLayer);
      if (kind === "country") {
        S("text", { class: "map-country-zh", "text-anchor": "middle", y: 0 }, g, lb.text);
        if (lb.en) S("text", { class: "map-country-en", "text-anchor": "middle", y: 15 }, g, lb.en);
      } else if (kind === "sea") {
        S("text", { class: "map-sea-zh", "text-anchor": "middle", y: 0 }, g, lb.text);
        if (lb.en) S("text", { class: "map-sea-en", "text-anchor": "middle", y: 18 }, g, lb.en);
      } else if (kind === "sea_mid") {
        S("text", { class: "map-sea-mid", "text-anchor": "middle", y: 0 }, g, lb.text);
      } else if (kind === "sea_small") {
        S("text", { class: "map-sea-small", "text-anchor": "middle", y: 0 }, g, lb.text);
      } else {
        S("text", { class: "map-lake", "text-anchor": "middle", y: 3 }, g, lb.text);
      }
      this.screenItems.push({ node: g, at: pos, kind, minZoom: nudge.minZoom || 0 });
    }
  }

  _buildCompass(g) {
    const ink = "#2E2924";
    S("circle", { r: 58, fill: "none", stroke: ink, "stroke-width": 0.8, "stroke-opacity": 0.7 }, g);
    S("circle", { r: 54, fill: "none", stroke: ink, "stroke-width": 0.5, "stroke-opacity": 0.6 }, g);
    S("circle", { r: 22, fill: "none", stroke: ink, "stroke-width": 0.5, "stroke-opacity": 0.6, "stroke-dasharray": "1 2" }, g);
    for (let i = 0; i < 72; i++) {
      const a = (i * 5 * Math.PI) / 180;
      const r0 = i % 2 ? 55.5 : 54;
      S("line", { x1: Math.sin(a) * r0, y1: -Math.cos(a) * r0, x2: Math.sin(a) * 58, y2: -Math.cos(a) * 58, stroke: ink, "stroke-width": 0.5, "stroke-opacity": 0.7 }, g);
    }
    const point = (deg, len, wid, dark) => {
      const a = (deg * Math.PI) / 180;
      const tip = [Math.sin(a) * len, -Math.cos(a) * len];
      const l = [Math.sin(a - Math.PI / 2) * wid, -Math.cos(a - Math.PI / 2) * wid];
      const r = [Math.sin(a + Math.PI / 2) * wid, -Math.cos(a + Math.PI / 2) * wid];
      S("path", { d: `M0,0 L${l} L${tip} Z`, fill: dark ? ink : "#F4EFE6", stroke: ink, "stroke-width": 0.6, "stroke-linejoin": "round" }, g);
      S("path", { d: `M0,0 L${r} L${tip} Z`, fill: dark ? "#F4EFE6" : ink, stroke: ink, "stroke-width": 0.6, "stroke-linejoin": "round" }, g);
    };
    [45, 135, 225, 315].forEach((d) => point(d, 34, 6, false));
    [0, 90, 180, 270].forEach((d) => point(d, 50, 8, true));
    S("circle", { r: 3, fill: "#F4EFE6", stroke: ink, "stroke-width": 0.8 }, g);
    S("path", { d: "M0,-75 l-4,9 l4,-2.5 l4,2.5 z", fill: ink }, g); // fleur tip
    S("text", { class: "map-compass-n", "text-anchor": "middle", y: -80 }, g, "N");
    S("text", { class: "map-compass-zh", "text-anchor": "middle", x: 0, y: 74 }, g, "南");
    S("text", { class: "map-compass-zh", "text-anchor": "middle", x: 70, y: 4 }, g, "东");
    S("text", { class: "map-compass-zh", "text-anchor": "middle", x: -70, y: 4 }, g, "西");
  }

  _buildCartouche(g) {
    const w = 318;
    const h = 92;
    const ink = "#2E2924";
    S("rect", { x: 0, y: 0, width: w, height: h, fill: "#F2EADB", stroke: ink, "stroke-width": 1.6 }, g);
    S("rect", { x: 5, y: 5, width: w - 10, height: h - 10, fill: "none", stroke: ink, "stroke-width": 0.6 }, g);
    // Corner flourishes: quarter-round notches + small diamonds.
    for (const [cx, cy, sx, sy] of [[5, 5, 1, 1], [w - 5, 5, -1, 1], [5, h - 5, 1, -1], [w - 5, h - 5, -1, -1]]) {
      S("path", { d: `M${cx + sx * 12},${cy} A12,12 0 0 ${sx * sy > 0 ? 0 : 1} ${cx},${cy + sy * 12}`, fill: "none", stroke: ink, "stroke-width": 0.6 }, g);
      S("path", { d: `M${cx + sx * 4},${cy + sy * 4} l${sx * 2.5},${sy * -2.5} l${sx * 2.5},${sy * 2.5} l${sx * -2.5},${sy * 2.5} z`, fill: ink }, g);
    }
    S("text", { class: "map-cartouche-title", x: w / 2, y: 40, "text-anchor": "middle" }, g, "以色列及其周边 · 1977");
    S("line", { x1: 46, y1: 52, x2: w - 46, y2: 52, stroke: ink, "stroke-width": 0.6 }, g);
    S("path", { d: `M${w / 2 - 5},52 l5,-3.5 l5,3.5 l-5,3.5 z`, fill: ink }, g);
    S("text", { class: "map-cartouche-sub", x: w / 2, y: 71, "text-anchor": "middle" }, g, "TERRA SANCTA ET REGIONES FINITIMAE");
    S("text", { class: "map-cartouche-sub2", x: w / 2, y: 84, "text-anchor": "middle" }, g, "一九七七年夏 · 地中海东岸形势图");
  }

  _buildControls() {
    const box = el("div", "map-zoom-controls");
    const plus = button("+", () => this.setZoom(this.zoom * 1.4, [W / 2, H / 2]), { cls: "map-zoom-btn" });
    const minus = button("−", () => this.setZoom(this.zoom / 1.4, [W / 2, H / 2]), { cls: "map-zoom-btn" });
    const focus = button("聚焦以色列", () => this.focusIsrael(), { cls: "map-zoom-btn map-focus-btn" });
    plus.title = "放大";
    minus.title = "缩小";
    focus.title = "将视图对准以色列本土及占领区（北纬 29.4°–33.5°）";
    box.append(plus, minus, focus);
    for (const t of ["dblclick", "pointerdown", "wheel", "click"]) box.addEventListener(t, (ev) => ev.stopPropagation());
    return box;
  }

  // ------------------------------------------------------------------ registry
  /** build_from_registry: region nodes in sorted id order, then pins. */
  buildFromRegistry(view) {
    if (view) this.view = view;
    const defs = (this.ctx.data.regions && this.ctx.data.regions.regions) || {};
    const ids = Object.keys(defs).sort();
    this.regionLayer.textContent = "";
    this.borderLayer.textContent = "";
    this.labelLayer.querySelectorAll(".map-label-region").forEach((n) => n.remove());
    this.leaderLayer.textContent = "";
    this.screenItems = this.screenItems.filter((it) => !it.region);
    const defsEl = this.svg.querySelector("defs");
    this.regions = ids.map((id) => {
      const rings = regionRings(id);
      const d = ringsPath(rings);
      const src = defs[id] || {};
      const g = S("g", { class: "map-region", "data-region": id }, this.regionLayer);
      let clip = defsEl.querySelector(`#map-clip-${id}`);
      if (!clip) {
        clip = S("clipPath", { id: `map-clip-${id}` }, defsEl);
        S("path", { d }, clip);
      }
      const fill = S("path", { d, class: "map-region-fill", "data-region": id }, g);
      const bd = this.edges && this.edges.regionBorders[id] ? linesPath(this.edges.regionBorders[id]) : d;
      S("title", {}, fill, String(src.name_zh || id));
      // Watercolour edge darkening: two inner strokes clipped to the region.
      const edge = S("g", { "clip-path": `url(#map-clip-${id})`, fill: "none", "pointer-events": "none" }, g);
      const edgeWide = S("path", { d: bd, "stroke-width": 10, "stroke-opacity": 0.16, "vector-effect": "non-scaling-stroke" }, edge);
      const edgeNarrow = S("path", { d: bd, "stroke-width": 3.2, "stroke-opacity": 0.38, "vector-effect": "non-scaling-stroke" }, edge);
      const hatch = S("path", { d, fill: "url(#map-hatch)", "pointer-events": "none" }, g);
      S("path", { d, fill: "url(#map-wash)", "pointer-events": "none" }, g);
      const border = S("path", { d: bd, stroke: "#1E1C1A", "stroke-width": 1.3, "stroke-opacity": 0.9, "vector-effect": "non-scaling-stroke" }, this.borderLayer);
      const node = { id, src, rings, d: bd, occupied: isOccupied(src), visible: regionExists(id, src, this.view), color: "", nodes: { g, fill, edgeWide, edgeNarrow, hatch, border } };
      this._buildRegionLabel(node);
      return node;
    });
    this._placePins();
    this.setMapLayer(this.layerIndex, this.view);
    this._updateSelection();
    this._applyTransform();
  }

  _buildRegionLabel(r) {
    const cfg = REGION_LABELS[r.id] || { name: String(r.src.name_zh || r.id), at: centroid(r.id) };
    const g = S("g", { class: `map-label map-label-region${cfg.big ? " big" : ""}` }, this.labelLayer);
    const text = S("text", { class: "map-region-name", "text-anchor": cfg.align || "middle", y: 4.5 }, g, cfg.name);
    let leader = null;
    let dot = null;
    if (cfg.anchor) {
      leader = S("line", { class: "map-leader" }, this.leaderLayer);
      dot = S("circle", { class: "map-leader-dot", r: 1.6 }, this.leaderLayer);
    }
    r.label = { cfg, g, text, leader, dot };
    this.screenItems.push({ region: r, node: g, at: cfg.at, cfg, leader, dot });
  }

  _placePins() {
    const live = this.view && this.view.modules && this.view.modules.M11 ? this.view.modules.M11.key_sites : null;
    const staticSites = (this.ctx.data.regions && this.ctx.data.regions.key_sites) || [];
    const sites = Array.isArray(live) && live.length ? live : staticSites;
    const names = new Map(staticSites.map((s) => [s.site_id, s.name_zh]));
    const geoSites = (this.geo && this.geo.sites) || {};
    const key = sites.map((s) => (s && s.site_id) || "").join("|");
    if (key !== this.pinKey) {
      this.pinKey = key;
      this.pinLayer.textContent = "";
      this.sites = [];
      sites.forEach((site, i) => {
        if (!site || typeof site !== "object") return;
        const id = String(site.site_id || "");
        const rid = String(site.region_id || "");
        let at = geoSites[id];
        if (!at) { const c = centroid(rid); at = [c[0] + (i % 5) * 4, c[1] + (i % 3) * 4]; }
        const node = S("g", { class: "map-pin" }, this.pinLayer);
        S("circle", { class: "map-pin-halo", r: 5.4 }, node);
        const dot = S("circle", { class: "map-pin-dot", r: 3.6 }, node);
        const title = S("title", {}, node);
        this.sites.push({ id, region: rid, status: "", at, node, dot, title, name: String(site.name_zh || names.get(id) || id) });
      });
    }
    sites.forEach((site, i) => {
      const p = this.sites[i];
      if (!p || !site) return;
      const status = String(site.status || "active");
      if (status !== p.status) {
        p.status = status;
        p.dot.setAttribute("fill", pinColor(status));
        p.title.textContent = `${p.name}（${status}）`;
      }
    });
  }

  /** set_map_layer(index): recolour every region (DeskMain passes the current view). */
  setMapLayer(index, view) {
    if (view) this.view = view;
    this.layerIndex = Math.min(7, Math.max(1, Number(index) || 1));
    for (const r of this.regions) this._paintRegion(r);
    if (this.legend) this.legend.textContent = LAYER_NAMES[this.layerIndex];
  }

  refresh(view) {
    if (!view) return;
    const fresh = !this.view;
    this.view = view;
    if (fresh || !this.regions.length) { this.buildFromRegistry(view); return; }
    let visChanged = false;
    for (const r of this.regions) {
      const vis = regionExists(r.id, r.src, view);
      if (vis !== r.visible) { r.visible = vis; visChanged = true; }
    }
    this._placePins();
    this.setMapLayer(this.layerIndex, view);
    if (visChanged) { this._updateSelection(); this._applyTransform(); }
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

  /** Watercolour wash of the layer colour: same rgb, alpha reduced (×0.78 → ~0.43–0.66). */
  _paintRegion(r) {
    const color = this._layerColor(r);
    const n = r.nodes;
    const disp = r.visible ? null : "none";
    if (n.g.getAttribute("display") !== disp) {
      if (disp) { n.g.setAttribute("display", disp); n.border.setAttribute("display", disp); r.label.g.setAttribute("display", disp); }
      else { n.g.removeAttribute("display"); n.border.removeAttribute("display"); r.label.g.removeAttribute("display"); }
    }
    n.hatch.setAttribute("display", r.occupied ? "inline" : "none");
    if (color === r.color) return;
    r.color = color;
    const m = /rgba\(([^,]+),([^,]+),([^,]+),([^)]+)\)/.exec(color);
    const [cr, cg, cb, ca] = m.slice(1).map(Number);
    const rgb = `rgb(${cr},${cg},${cb})`;
    const dark = `rgb(${Math.round(cr * 0.55)},${Math.round(cg * 0.55)},${Math.round(cb * 0.55)})`;
    n.fill.setAttribute("fill", rgb);
    n.fill.setAttribute("fill-opacity", Math.max(0.4, Math.min(0.62, ca * 0.74)).toFixed(3));
    n.edgeWide.setAttribute("stroke", dark);
    n.edgeNarrow.setAttribute("stroke", dark);
  }

  _updateSelection() {
    if (!this.selOutline) return;
    const sel = this.regions.find((r) => r.id === this.selected && r.visible);
    if (sel) {
      this.selOutline.setAttribute("d", sel.d);
      this.selOutline.removeAttribute("display");
    } else {
      this.selOutline.setAttribute("display", "none");
    }
    for (const r of this.regions) r.label.g.classList.toggle("selected", !!sel && r.id === sel.id);
  }

  // ------------------------------------------------------------------ transform
  _scheduleTransform() {
    // Drop the wobble filter while the view is moving (cheap frames), restore when it settles.
    if (this.inkLayer) {
      this.inkLayer.removeAttribute("filter");
      this.ripplesOuter.setAttribute("display", "none");
      clearTimeout(this.settleTimer);
      this.settleTimer = setTimeout(() => {
        this.inkLayer.setAttribute("filter", "url(#map-wobble)");
        this.ripplesOuter.removeAttribute("display");
      }, 180);
    }
    if (this.rafPending) return;
    this.rafPending = true;
    requestAnimationFrame(() => { this.rafPending = false; this._applyTransform(); });
  }

  _toScreen([x, y]) { return [x * this.zoom + this.pan[0], y * this.zoom + this.pan[1]]; }

  _applyTransform() {
    if (!this.world) return;
    const z = this.zoom;
    this.world.setAttribute("transform", `translate(${this.pan[0].toFixed(2)} ${this.pan[1].toFixed(2)}) scale(${z})`);
    // Screen-constant textures and wobble.
    this.hachure.setAttribute("patternTransform", `scale(${1 / z})`);
    this.hatch.setAttribute("patternTransform", `scale(${1 / z}) rotate(45)`);
    this.wobbleDisp.setAttribute("scale", (1.5 / z).toFixed(3));
    this.wobbleNoise.setAttribute("baseFrequency", (0.06 * z).toFixed(4));
    // Labels.
    for (const it of this.screenItems) {
      let pos;
      if (it.cfg && it.cfg.anchor) {
        const a = this._toScreen(it.cfg.anchor);
        const full = it.cfg.full || 3;
        const f = Math.max(0, Math.min(1, (full - z) / (full - 1)));
        pos = [a[0] + (it.cfg.at[0] - it.cfg.anchor[0]) * f, a[1] + (it.cfg.at[1] - it.cfg.anchor[1]) * f];
        const showLeader = f > 0.12 && it.region.visible;
        const anchorText = showLeader ? it.cfg.align || "middle" : "middle";
        it.node.firstChild.setAttribute("text-anchor", anchorText);
        if (showLeader) {
          const gap = anchorText === "end" ? 4 : anchorText === "start" ? -4 : 0;
          setAttrs(it.leader, { x1: a[0], y1: a[1], x2: pos[0] + gap, y2: pos[1], display: "inline" });
          setAttrs(it.dot, { cx: a[0], cy: a[1], display: "inline" });
        } else {
          it.leader.setAttribute("display", "none");
          it.dot.setAttribute("display", "none");
        }
      } else {
        pos = this._toScreen(it.at);
        if (it.minZoom) it.node.setAttribute("display", z >= it.minZoom ? "inline" : "none");
        // Big sea names slide clear of the fixed compass rose / cartouche.
        if (it.kind === "sea" && pos[1] > 20 && pos[1] < 370) pos[0] = Math.max(pos[0], pos[1] < 170 ? 480 : 430);
        // Country names never collide with the neat line.
        if (it.kind === "country") it.node.setAttribute("display", pos[1] > 34 && pos[1] < H - 40 && pos[0] > 60 && pos[0] < W - 60 ? "inline" : "none");
      }
      it.node.setAttribute("transform", `translate(${pos[0].toFixed(1)} ${pos[1].toFixed(1)})`);
    }
    for (const p of this.sites) {
      const s = this._toScreen(p.at);
      p.node.setAttribute("transform", `translate(${s[0].toFixed(1)} ${s[1].toFixed(1)})`);
      const vis = this.regions.find((r) => r.id === p.region);
      p.node.setAttribute("display", vis && !vis.visible ? "none" : "inline");
    }
    this._drawFrame();
    this._drawScaleBar();
  }

  /** Double neat line with a degree band (alternating 10′ bars) and degree labels. */
  _drawFrame() {
    const f = this.frame;
    f.textContent = "";
    if (!this.geo) return;
    const O = 4;   // outer rule inset
    const I = 13;  // inner rule inset
    const band = S("path", { d: `M0,0H${W}V${H}H0Z M${I},${I}V${H - I}H${W - I}V${I}Z`, fill: "#F2EADB", "fill-rule": "evenodd" }, f);
    band.setAttribute("pointer-events", "none");
    const p = this.geo.projection;
    const bars = [];
    const labels = S("g", { class: "map-frame-labels" }, f);
    const step = 1 / 6;
    // Longitude bars along top/bottom.
    const lonAt = (sx) => unproject((sx - this.pan[0]) / this.zoom, 0)[0];
    const latAt = (sy) => unproject(0, (sy - this.pan[1]) / this.zoom)[1];
    const sxOf = (lon) => (lon - p.lon_min) * p.px_per_deg_lon * this.zoom + this.pan[0];
    const syOf = (lat) => (p.lat_max - lat) * p.px_per_deg_lat * this.zoom + this.pan[1];
    const lon0 = Math.floor(lonAt(I) / step) * step;
    const lon1 = lonAt(W - I);
    for (let k = Math.round(lon0 / step); k * step <= lon1; k++) {
      if (k % 2) continue;
      const a = Math.max(I, sxOf(k * step));
      const b = Math.min(W - I, sxOf((k + 1) * step));
      if (b > a) bars.push(`M${a},${O + 2.5}H${b}V${I - 2.5}H${a}Z M${a},${H - I + 2.5}H${b}V${H - O - 2.5}H${a}Z`);
    }
    const lat1 = latAt(I);
    const lat0 = latAt(H - I);
    for (let k = Math.floor(lat0 / step); k * step <= lat1; k++) {
      if (k % 2) continue;
      const a = Math.max(I, syOf((k + 1) * step));
      const b = Math.min(H - I, syOf(k * step));
      if (b > a) bars.push(`M${O + 2.5},${a}V${b}H${I - 2.5}V${a}Z M${W - I + 2.5},${a}V${b}H${W - O - 2.5}V${a}Z`);
    }
    S("path", { d: bars.join(""), fill: "#2E2924", "fill-opacity": 0.85 }, f);
    S("rect", { x: O, y: O, width: W - 2 * O, height: H - 2 * O, fill: "none", stroke: "#1E1C1A", "stroke-width": 1.8 }, f);
    S("rect", { x: O + 2.5, y: O + 2.5, width: W - 2 * O - 5, height: H - 2 * O - 5, fill: "none", stroke: "#1E1C1A", "stroke-width": 0.5 }, f);
    S("rect", { x: I, y: I, width: W - 2 * I, height: H - 2 * I, fill: "none", stroke: "#1E1C1A", "stroke-width": 0.9 }, f);
    // Whole-degree ticks + labels inside the inner rule.
    for (let lon = Math.ceil(lonAt(I)); lon <= lon1; lon++) {
      const x = sxOf(lon);
      if (x < I + 12 || x > W - I - 12) continue;
      S("line", { x1: x, y1: I, x2: x, y2: I + 7, stroke: "#1E1C1A", "stroke-width": 0.9 }, f);
      S("line", { x1: x, y1: H - I, x2: x, y2: H - I - 7, stroke: "#1E1C1A", "stroke-width": 0.9 }, f);
      if (x > 470) S("text", { class: "map-deg", x: x + 3, y: H - I - 4 }, labels, `${lon}°E`);
    }
    for (let lat = Math.ceil(lat0); lat <= lat1; lat++) {
      const y = syOf(lat);
      if (y < I + 30 || y > H - I - 12) continue;
      S("line", { x1: I, y1: y, x2: I + 7, y2: y, stroke: "#1E1C1A", "stroke-width": 0.9 }, f);
      S("line", { x1: W - I, y1: y, x2: W - I - 7, y2: y, stroke: "#1E1C1A", "stroke-width": 0.9 }, f);
      S("text", { class: "map-deg", x: W - I - 4, y: y - 3, "text-anchor": "end" }, labels, `${lat}°N`);
    }
  }

  /** Scale bar in km (1° lat ≈ 111.32 km). */
  _drawScaleBar() {
    const g = this.scaleBar;
    g.textContent = "";
    if (!this.geo) return;
    const pxPerKm = (this.geo.projection.px_per_deg_lat * this.zoom) / 111.32;
    const nice = [5, 10, 20, 25, 50, 100, 150, 200, 250, 500];
    let km = nice[0];
    for (const n of nice) if (n * pxPerKm <= 190) km = n;
    const len = km * pxPerKm;
    const seg = len / 4;
    S("rect", { x: -10, y: -16, width: len + 52, height: 34, fill: "#F2EADB", "fill-opacity": 0.85, stroke: "#2E2924", "stroke-width": 0.6 }, g);
    for (let i = 0; i < 4; i++) {
      S("rect", { x: i * seg, y: 0, width: seg, height: 5, fill: i % 2 ? "#F4EFE6" : "#2E2924", stroke: "#2E2924", "stroke-width": 0.8 }, g);
    }
    for (let i = 0; i <= 4; i += 2) S("text", { class: "map-scale-num", x: i * seg, y: -4, "text-anchor": "middle" }, g, String((km * i) / 4));
    S("text", { class: "map-scale-unit", x: len + 6, y: 6 }, g, "公里");
    S("text", { class: "map-scale-num", x: len / 2, y: 15, "text-anchor": "middle" }, g, "比例尺");
  }

  // ------------------------------------------------------------------ input
  _stageScale() {
    const b = this.root.getBoundingClientRect();
    return b.width / W || 1;
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
    const z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.round(next * 100) / 100));
    const w = this._toWorld(anchor);
    this.zoom = z;
    this.pan = [anchor[0] - w[0] * z, anchor[1] - w[1] * z];
    this._scheduleTransform();
  }

  resetView() {
    this.zoom = 1.0;
    this.pan = [0, 0];
    this._scheduleTransform();
  }

  /** Frame lat 29.4–33.5 (and the lon span of Israel + territories) in the map rect. */
  focusIsrael() {
    if (!this.geo) return;
    const p = this.geo.projection;
    const y0 = (p.lat_max - FOCUS_LAT[1]) * p.px_per_deg_lat;
    const y1 = (p.lat_max - FOCUS_LAT[0]) * p.px_per_deg_lat;
    const xs = FOCUS_REGIONS.flatMap((id) => regionRings(id).flat().map((pt) => pt[0]));
    const x0 = xs.length ? Math.min(...xs) : 0;
    const x1 = xs.length ? Math.max(...xs) : W;
    const z = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Math.min((H - 40) / (y1 - y0), (W - 40) / (x1 - x0))));
    this.zoom = Math.round(z * 100) / 100;
    this.pan = [W / 2 - ((x0 + x1) / 2) * this.zoom, H / 2 - ((y0 + y1) / 2) * this.zoom];
    this._scheduleTransform();
  }

  regionAt(world) {
    for (let i = this.regions.length - 1; i >= 0; i--) {
      const r = this.regions[i];
      if (r.visible && pointInRings(world, r.rings)) return r.id;
    }
    return "";
  }

  _bindInput() {
    const c = this.svg;
    c.addEventListener("wheel", (ev) => {
      ev.preventDefault();
      if (ev.deltaY === 0) return;
      this.setZoom(this.zoom * (ev.deltaY < 0 ? 1.15 : 1 / 1.15), this._local(ev));
    }, { passive: false });
    c.addEventListener("contextmenu", (ev) => ev.preventDefault());
    c.addEventListener("pointerdown", (ev) => {
      if (ev.button === 1 || ev.button === 2) {
        ev.preventDefault();
        this.panning = { id: ev.pointerId, x: ev.clientX, y: ev.clientY };
        c.classList.add("panning");
        try { c.setPointerCapture(ev.pointerId); } catch { /* synthetic / inactive pointer */ }
      }
    });
    c.addEventListener("pointermove", (ev) => {
      if (!this.panning || ev.pointerId !== this.panning.id) return;
      const s = this._stageScale();
      this.pan = [this.pan[0] + (ev.clientX - this.panning.x) / s, this.pan[1] + (ev.clientY - this.panning.y) / s];
      this.panning.x = ev.clientX;
      this.panning.y = ev.clientY;
      this._scheduleTransform();
    });
    const end = (ev) => {
      if (this.panning && ev.pointerId === this.panning.id) {
        this.panning = null;
        c.classList.remove("panning");
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

function setAttrs(node, attrs) {
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, typeof v === "number" ? v.toFixed(1) : v);
}
