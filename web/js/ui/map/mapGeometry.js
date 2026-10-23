/* Shared map geometry: real-geography region polygons from ctx.data.map_geo
 * (game/res/map/map_geo.json, built by tools/build_map_geo.py from Natural Earth), plus the
 * helpers mirroring IsraelMapCanvas.gd _occupied / _exists and RegionPolygonNode.contains_point.
 * All coordinates are map-local px of the 1440x942 map rect at zoom 1. */

export const MAP_RECT = { left: 240, top: 52, width: 1440, height: 942 };

/** The 11 game regions (used for registerReads before data loads). */
export const REGION_IDS = [
  "galilee", "gaza", "golan", "haifa", "jerusalem", "negev",
  "sinai", "south_lebanon", "tel_aviv", "triangle", "west_bank",
];

let GEO = null;

/** Install the map_geo dataset (IsraelMapCanvas.mount does this). */
export function setGeo(geo) { GEO = geo && geo.regions ? geo : null; }
export function geo() { return GEO; }

/** Rings [[x,y],...][] of a region (empty when the dataset is missing). */
export function regionRings(regionId) {
  const r = GEO && GEO.regions[regionId];
  return r && Array.isArray(r.rings) ? r.rings : [];
}

/** Label anchor of a region (map_geo label point, else ring-bbox centre). */
export function centroid(regionId) {
  const r = GEO && GEO.regions[regionId];
  if (r && Array.isArray(r.label)) return r.label;
  const pts = regionRings(regionId).flat();
  if (!pts.length) return [0, 0];
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  return [(Math.min(...xs) + Math.max(...xs)) / 2, (Math.min(...ys) + Math.max(...ys)) / 2];
}

/** lon/lat -> map-local px (equirectangular, projection block of map_geo). */
export function project(lon, lat) {
  const p = GEO.projection;
  return [(lon - p.lon_min) * p.px_per_deg_lon, (p.lat_max - lat) * p.px_per_deg_lat];
}

/** map-local px -> [lon, lat]. */
export function unproject(x, y) {
  const p = GEO.projection;
  return [p.lon_min + x / p.px_per_deg_lon, p.lat_max - y / p.px_per_deg_lat];
}

/** SVG path data for a list of rings (closed). */
export function ringsPath(rings) {
  let d = "";
  for (const ring of rings) {
    if (!ring || ring.length < 2) continue;
    d += "M" + ring.map((p) => `${p[0]},${p[1]}`).join("L") + "Z";
  }
  return d;
}

/** SVG path data for an open polyline. */
export function linePath(points) {
  return points && points.length > 1 ? "M" + points.map((p) => `${p[0]},${p[1]}`).join("L") : "";
}

export function isOccupied(src) {
  const status = String((src && src.legal_status) || "");
  return status === "occupied" || status === "military_occupation" || status.includes("occup");
}

/** _exists: live M11 region flag, else regions.json `exists`, else id != south_lebanon. */
export function regionExists(regionId, src, view) {
  const regions = view && view.modules && view.modules.M11 ? view.modules.M11.regions || {} : {};
  if (regions[regionId]) return regions[regionId].exists !== false;
  if (src && src.exists !== undefined) return !!src.exists;
  return regionId !== "south_lebanon";
}

/** Geometry2D.is_point_in_polygon (ray casting). */
export function pointInPolygon(pt, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}

/** Multi-ring even-odd containment (islands / holes). */
export function pointInRings(pt, rings) {
  let inside = false;
  for (const ring of rings) if (pointInPolygon(pt, ring)) inside = !inside;
  return inside;
}

function bboxOf(ring) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const [x, y] of ring) { if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; }
  return [x0, y0, x1, y1];
}

/** Split ring edges into runs of "kept" edges -> open polylines. */
function runs(ring, keep) {
  const n = ring.length;
  const out = [];
  if (n < 2) return out;
  const flags = [];
  for (let i = 0; i < n; i++) flags.push(keep(ring[i], ring[(i + 1) % n]));
  if (flags.every(Boolean)) return [[...ring, ring[0]]];
  // start right after a dropped edge so runs do not wrap
  let start = flags.findIndex((f) => !f);
  let cur = null;
  for (let k = 1; k <= n; k++) {
    const i = (start + k) % n;
    if (flags[i]) {
      if (!cur) cur = [ring[i]];
      cur.push(ring[(i + 1) % n]);
    } else if (cur) { out.push(cur); cur = null; }
  }
  if (cur) out.push(cur);
  return out;
}

let EDGES = null;

/** Classify outline edges once (probing ±1.2 px either side of every edge midpoint):
 *  coast = edges with sea on one side (all land polygons); countryBorders = country edges with
 *  land on both sides; regionBorders[id] = region outline minus edges internal to the region
 *  (e.g. the North/South Sinai admin split). */
export function classifyEdges() {
  if (EDGES || !GEO) return EDGES;
  const polys = [];
  for (const c of GEO.countries || []) for (const r of c.rings) polys.push({ ring: r, bb: bboxOf(r) });
  for (const reg of Object.values(GEO.regions)) for (const r of reg.rings) polys.push({ ring: r, bb: bboxOf(r) });
  const onLand = ([x, y]) => polys.some(({ ring, bb }) => x >= bb[0] && x <= bb[2] && y >= bb[1] && y <= bb[3] && pointInPolygon([x, y], ring));
  const sides = (a, b) => {
    const dx = b[0] - a[0];
    const dy = b[1] - a[1];
    const len = Math.hypot(dx, dy) || 1;
    const m = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
    const nx = (-dy / len) * 1.2;
    const ny = (dx / len) * 1.2;
    return [[m[0] + nx, m[1] + ny], [m[0] - nx, m[1] - ny]];
  };
  const isCoast0 = (a, b) => { const [p, q] = sides(a, b); return !(onLand(p) && onLand(q)); };
  // Edges on the dataset clip rectangle are neither coast nor border.
  const all = polys.map((p) => p.bb);
  const [X0, Y0, X1, Y1] = [Math.min(...all.map((b) => b[0])), Math.min(...all.map((b) => b[1])), Math.max(...all.map((b) => b[2])), Math.max(...all.map((b) => b[3]))];
  const near = (v, w) => Math.abs(v - w) < 0.5;
  const onClip = (a, b) => (near(a[0], b[0]) && (near(a[0], X0) || near(a[0], X1))) || (near(a[1], b[1]) && (near(a[1], Y0) || near(a[1], Y1)));
  const isCoast = (a, b) => !onClip(a, b) && isCoast0(a, b);
  const coast = [];
  const countryBorders = [];
  for (const c of GEO.countries || []) {
    for (const r of c.rings) {
      coast.push(...runs(r, isCoast));
      countryBorders.push(...runs(r, (a, b) => !onClip(a, b) && !isCoast0(a, b)));
    }
  }
  const regionBorders = {};
  const countryPolys = polys.slice(0, (GEO.countries || []).reduce((n, c) => n + c.rings.length, 0));
  const inCountry = ([x, y]) => countryPolys.some(({ ring, bb }) => x >= bb[0] && x <= bb[2] && y >= bb[1] && y <= bb[3] && pointInPolygon([x, y], ring));
  for (const [id, reg] of Object.entries(GEO.regions)) {
    const regPolys = reg.rings.map((r) => ({ ring: r, bb: bboxOf(r) }));
    const inReg = ([x, y]) => regPolys.some(({ ring, bb }) => x >= bb[0] && x <= bb[2] && y >= bb[1] && y <= bb[3] && pointInPolygon([x, y], ring));
    // Regions inside a context country (Sinai ⊂ Egypt, South Lebanon ⊂ Lebanon) reuse its coast.
    const ownCoast = !(Array.isArray(reg.label) && inCountry(reg.label));
    regionBorders[id] = [];
    for (const r of reg.rings) {
      if (ownCoast) coast.push(...runs(r, isCoast));
      regionBorders[id].push(...runs(r, (a, b) => { const [p, q] = sides(a, b); return !(inReg(p) && inReg(q)); }));
    }
  }
  EDGES = { coast, countryBorders, regionBorders };
  return EDGES;
}

/** SVG path data for several open polylines. */
export function linesPath(lines) {
  return lines.map(linePath).join("");
}
