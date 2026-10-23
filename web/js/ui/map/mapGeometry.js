/* Shared map geometry: hard-coded schematic boxes of game/ui/map/IsraelMapCanvas.gd (_box),
 * helpers mirroring _schematic / _occupied / _exists, and RegionPolygonNode.contains_point. */

export const MAP_RECT = { left: 240, top: 52, width: 1440, height: 942 };

const BOXES = {
  south_lebanon: [80, 8, 220, 70],
  golan: [620, 40, 180, 150],
  galilee: [300, 40, 300, 170],
  haifa: [180, 210, 200, 140],
  triangle: [390, 230, 180, 160],
  tel_aviv: [140, 360, 240, 150],
  jerusalem: [400, 370, 200, 160],
  west_bank: [610, 210, 200, 300],
  gaza: [70, 520, 120, 140],
  negev: [200, 530, 420, 280],
  sinai: [40, 680, 280, 180],
};

/** The 11 regions the schematic knows (used for registerReads before data loads). */
export const REGION_IDS = Object.keys(BOXES).sort();

/** Rect2(x, y, w, h) of IsraelMapCanvas._box (fallback (20,20,80,80)). */
export function box(regionId) { return BOXES[regionId] || [20, 20, 80, 80]; }

/** _schematic: [p, p+(w,0), p+(w,h), p+(0,h)] in map-local coordinates. */
export function schematic(regionId) {
  const [x, y, w, h] = box(regionId);
  return [[x, y], [x + w, y], [x + w, y + h], [x, y + h]];
}

export function centroid(regionId) {
  const pts = schematic(regionId);
  const s = pts.reduce((a, p) => [a[0] + p[0], a[1] + p[1]], [0, 0]);
  return [s[0] / pts.length, s[1] / pts.length];
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
