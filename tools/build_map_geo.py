#!/usr/bin/env python3
"""Build game/res/map/map_geo.json: real-geography map data for the strategic map.

Shared by the Godot client (game/ui/map) and the web prototype (web/js/ui/map).
Source: Natural Earth 1:10m vector data (public domain, https://www.naturalearthdata.com/).

Region mapping (game region id -> Natural Earth admin-1 units):
  galilee        Israel "HaZafon" (Northern District), west of the Golan split line
  golan          Israel "HaZafon", east of the split line (Jordan river / Sea of Galilee shore)
  haifa          Israel "Haifa"
  tel_aviv       Israel "Tel Aviv"
  triangle       Israel "HaMerkaz" (Central District; game alias "central")
  jerusalem      Israel "Jerusalem"
  negev          Israel "HaDarom" (Southern District)
  west_bank      "West Bank"
  gaza           "Gaza Strip"
  sinai          Egypt "Shamal Sina'" + "Janub Sina'"
  south_lebanon  Lebanon "South Lebanon" + "An Nabatiyah"
Plus context (neighbouring countries, lakes, rivers, sea/country labels) and real
coordinates for the 26 key sites of regions.json.

Coordinates are written in map-local pixels of the 1440x942 map rect at zoom 1
(equirectangular projection scaled by cos(latitude)), so both clients can draw them
directly. Pure Python (no shapely); polygons are simplified with Douglas-Peucker.

  python3 tools/build_map_geo.py --ne-dir /tmp/ne     # dir with ne_10m_*.geojson
  python3 tools/build_map_geo.py --download          # fetch from GitHub first
"""

import argparse
import json
import math
import urllib.request
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "game" / "res" / "map" / "map_geo.json"
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"
NE_FILES = ["ne_10m_admin_1_states_provinces", "ne_10m_admin_0_countries", "ne_10m_lakes", "ne_10m_rivers_lake_centerlines"]

MAP_W, MAP_H = 1440.0, 942.0
LAT_MIN, LAT_MAX = 27.55, 33.80          # Sharm el-Sheikh .. Sidon
LON_CENTER = 34.55                        # Israel + Sinai sit left of centre (right side hosts cards)
LAT_C = 31.0
SCALE = MAP_H / (LAT_MAX - LAT_MIN)       # px per degree latitude
KX = SCALE * math.cos(math.radians(LAT_C))
LON_MIN = LON_CENTER - (MAP_W / 2.0) / KX
LON_MAX = LON_CENTER + (MAP_W / 2.0) / KX
SIMPLIFY_PX = 0.35

Point = Tuple[float, float]

# Golan split: straight line along the Jordan / Hula / Sea of Galilee east shore.
GOLAN_LINE = ((35.695, 33.45), (35.630, 32.66))

# Real coordinates (lon, lat) of the regions.json key sites (representative point).
SITES_LONLAT: Dict[str, Point] = {
    "site_kiryat_shmona": (35.571, 33.207),
    "site_nazareth_sakhnin": (35.30, 32.70),
    "site_jezreel_kibbutzim": (35.33, 32.58),
    "site_haifa_port_refinery": (35.03, 32.81),
    "site_technion_carmel": (35.02, 32.776),
    "site_tel_aviv_kirya": (34.787, 32.074),
    "site_bnei_brak": (34.833, 32.084),
    "site_hatikva_south_ta": (34.790, 32.050),
    "site_umm_al_fahm_tayibe": (35.07, 32.40),
    "site_ben_gurion_lod": (34.886, 31.996),
    "site_old_city_temple_mount": (35.234, 31.777),
    "site_knesset_meah_shearim": (35.205, 31.777),
    "site_east_jerusalem_ring": (35.245, 31.815),
    "site_sderot_ofakim": (34.62, 31.43),
    "site_beersheba_rahat": (34.79, 31.25),
    "site_kiryat_arba_hebron": (35.11, 31.53),
    "site_elon_moreh_nablus": (35.27, 32.22),
    "site_ariel_samaria": (35.17, 32.105),
    "site_maale_adumim": (35.30, 31.78),
    "site_jordan_valley_belt": (35.50, 32.00),
    "site_jabalia_gaza_city": (34.48, 31.53),
    "site_gush_katif": (34.27, 31.35),
    "site_katzrin_golan": (35.69, 32.99),
    "site_yamit_rafah": (34.18, 31.25),
    "site_alma_oil_fields": (33.30, 28.75),
    "site_marjayoun_beaufort": (35.59, 33.36),
}

CONTEXT_COUNTRIES = {
    "EGY": "埃及", "JOR": "约旦", "SYR": "叙利亚", "LBN": "黎巴嫩", "SAU": "沙特阿拉伯",
    "CYP": "塞浦路斯", "CYN": "塞浦路斯", "IRQ": "伊拉克",
}
# Static labels (lon, lat): seas and country names placed in open areas.
LABELS = [
    {"text": "地中海", "en": "MARE NOSTRUM", "kind": "sea", "lonlat": (32.6, 32.4)},
    {"text": "红海", "en": "", "kind": "sea", "lonlat": (34.6, 27.75)},
    {"text": "苏伊士湾", "en": "", "kind": "sea_small", "lonlat": (32.95, 29.0)},
    {"text": "亚喀巴湾", "en": "", "kind": "sea_small", "lonlat": (34.75, 28.75)},
    {"text": "埃及", "en": "EGYPT", "kind": "country", "lonlat": (31.2, 29.6)},
    {"text": "约旦", "en": "JORDAN", "kind": "country", "lonlat": (36.9, 31.0)},
    {"text": "叙利亚", "en": "SYRIA", "kind": "country", "lonlat": (36.9, 33.25)},
    {"text": "黎巴嫩", "en": "LEBANON", "kind": "country", "lonlat": (35.70, 33.70)},
    {"text": "沙特阿拉伯", "en": "SAUDI ARABIA", "kind": "country", "lonlat": (37.3, 28.4)},
    {"text": "加利利海", "en": "", "kind": "lake", "lonlat": (35.59, 32.82)},
    {"text": "死海", "en": "", "kind": "lake", "lonlat": (35.48, 31.50)},
]


def project(lon: float, lat: float) -> Point:
    return ((lon - LON_MIN) * KX, (LAT_MAX - lat) * SCALE)


# ----------------------------------------------------------------- geometry helpers
def rings_of(geom: dict) -> List[List[Point]]:
    """Outer rings of a Polygon/MultiPolygon (holes are irrelevant for these units)."""
    if geom["type"] == "Polygon":
        return [[(p[0], p[1]) for p in geom["coordinates"][0]]]
    if geom["type"] == "MultiPolygon":
        return [[(p[0], p[1]) for p in poly[0]] for poly in geom["coordinates"]]
    return []


def lines_of(geom: dict) -> List[List[Point]]:
    if geom["type"] == "LineString":
        return [[(p[0], p[1]) for p in geom["coordinates"]]]
    if geom["type"] == "MultiLineString":
        return [[(p[0], p[1]) for p in line] for line in geom["coordinates"]]
    return []


def clip_halfplane(ring: Sequence[Point], a: Point, b: Point, keep_left: bool) -> List[Point]:
    """Sutherland-Hodgman clip of a (possibly concave) ring against one half-plane."""
    def side(p: Point) -> float:
        return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])

    def inside(p: Point) -> bool:
        s = side(p)
        return s >= 0 if keep_left else s <= 0

    def cross(p: Point, q: Point) -> Point:
        sp, sq = side(p), side(q)
        t = sp / (sp - sq)
        return (p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t)

    out: List[Point] = []
    n = len(ring)
    for i in range(n):
        cur, prev = ring[i], ring[i - 1]
        if inside(cur):
            if not inside(prev):
                out.append(cross(prev, cur))
            out.append(cur)
        elif inside(prev):
            out.append(cross(prev, cur))
    return out


def clip_rect(ring: Sequence[Point], x0: float, y0: float, x1: float, y1: float) -> List[Point]:
    r = list(ring)
    for a, b in (((x0, y1), (x0, y0)), ((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1))):
        if not r:
            break
        r = clip_halfplane(r, a, b, keep_left=True)
    return r


def clip_line_rect(line: Sequence[Point], x0: float, y0: float, x1: float, y1: float) -> List[List[Point]]:
    """Keep the parts of a polyline whose vertices fall inside the rect (cheap, good enough)."""
    parts: List[List[Point]] = []
    cur: List[Point] = []
    for p in line:
        if x0 <= p[0] <= x1 and y0 <= p[1] <= y1:
            cur.append(p)
        elif cur:
            parts.append(cur)
            cur = []
    if cur:
        parts.append(cur)
    return [p for p in parts if len(p) >= 2]


def dp(points: Sequence[Point], tol: float) -> List[Point]:
    """Douglas-Peucker simplification (iterative). Closed rings (first == last) are split at
    the vertex farthest from the start so the degenerate base segment does not collapse them."""
    if len(points) >= 4 and points[0] == points[-1]:
        x0, y0 = points[0]
        far = max(range(len(points)), key=lambda k: (points[k][0] - x0) ** 2 + (points[k][1] - y0) ** 2)
        return dp(points[: far + 1], tol)[:-1] + dp(points[far:], tol)
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        ax, ay = points[i]
        bx, by = points[j]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy) or 1e-12
        best, idx = -1.0, -1
        for k in range(i + 1, j):
            px, py = points[k]
            d = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if d > best:
                best, idx = d, k
        if best > tol and idx > 0:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for p, k in zip(points, keep) if k]


def area(ring: Sequence[Point]) -> float:
    s = 0.0
    for i in range(len(ring)):
        x0, y0 = ring[i - 1]
        x1, y1 = ring[i]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def centroid(rings: Sequence[Sequence[Point]]) -> Point:
    """Area-weighted centroid of the largest ring (good label anchor for these shapes)."""
    ring = max(rings, key=lambda r: abs(area(r)))
    a = area(ring)
    if abs(a) < 1e-9:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return (sum(xs) / len(xs), sum(ys) / len(ys))
    cx = cy = 0.0
    for i in range(len(ring)):
        x0, y0 = ring[i - 1]
        x1, y1 = ring[i]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    return (cx / (6.0 * a), cy / (6.0 * a))


def to_px(rings: Sequence[Sequence[Point]], tol: float = SIMPLIFY_PX, min_area: float = 1.5) -> List[List[List[float]]]:
    out = []
    for ring in rings:
        pts = dp([project(lon, lat) for lon, lat in ring], tol)
        if len(pts) >= 4 and abs(area(pts)) >= min_area:
            out.append([[round(x, 2), round(y, 2)] for x, y in pts])
    return out


# ----------------------------------------------------------------- build
def load(ne_dir: Path, name: str) -> dict:
    return json.loads((ne_dir / f"{name}.geojson").read_text(encoding="utf-8"))


def build(ne_dir: Path) -> dict:
    a1 = load(ne_dir, "ne_10m_admin_1_states_provinces")
    by_name: Dict[str, List[List[Point]]] = {}
    for f in a1["features"]:
        p = f["properties"]
        key = f"{p.get('adm0_a3')}:{p.get('name')}"
        by_name.setdefault(key, []).extend(rings_of(f["geometry"]))

    def units(*keys: str) -> List[List[Point]]:
        rings: List[List[Point]] = []
        for k in keys:
            if k not in by_name:
                raise SystemExit(f"Natural Earth unit missing: {k}")
            rings.extend(by_name[k])
        return rings

    north = units("ISR:HaZafon")
    a, b = GOLAN_LINE
    # GOLAN_LINE runs north -> south, so "left" of it is the east (Golan) side.
    golan = [r for r in (clip_halfplane(ring, a, b, keep_left=True) for ring in north) if len(r) >= 3]
    galilee = [r for r in (clip_halfplane(ring, a, b, keep_left=False) for ring in north) if len(r) >= 3]
    region_rings = {
        "galilee": galilee,
        "golan": golan,
        "haifa": units("ISR:Haifa"),
        "tel_aviv": units("ISR:Tel Aviv"),
        "triangle": units("ISR:HaMerkaz"),
        "jerusalem": units("ISR:Jerusalem"),
        "negev": units("ISR:HaDarom"),
        "west_bank": units("PSX:West Bank"),
        "gaza": units("PSX:Gaza Strip"),
        "sinai": units("EGY:Shamal Sina'", "EGY:Janub Sina'"),
        "south_lebanon": units("LBN:South Lebanon", "LBN:An Nabatiyah"),
    }
    regions = {}
    for rid, rings in region_rings.items():
        px = to_px(rings, min_area=0.5)
        cx, cy = centroid([[tuple(p) for p in r] for r in px])
        regions[rid] = {"rings": px, "label": [round(cx, 1), round(cy, 1)]}

    # Context: neighbouring countries clipped to the frame (in lon/lat), then projected.
    a0 = load(ne_dir, "ne_10m_admin_0_countries")
    pad = 0.6
    countries = []
    for f in a0["features"]:
        code = f["properties"]["ADM0_A3"]
        if code not in CONTEXT_COUNTRIES:
            continue
        rings = []
        for ring in rings_of(f["geometry"]):
            clipped = clip_rect(ring, LON_MIN - pad, LAT_MIN - pad, LON_MAX + pad, LAT_MAX + pad)
            if len(clipped) >= 3:
                rings.append(clipped)
        px = to_px(rings, tol=0.6, min_area=4.0)
        if px:
            countries.append({"id": code, "name_zh": CONTEXT_COUNTRIES[code], "rings": px})

    lakes = []
    for f in load(ne_dir, "ne_10m_lakes")["features"]:
        rings = [r for r in rings_of(f["geometry"]) if all(LON_MIN <= x <= LON_MAX and LAT_MIN <= y <= LAT_MAX for x, y in r)]
        px = to_px(rings, tol=0.25, min_area=2.0)
        if px:
            lakes.append({"name": f["properties"].get("name") or "", "rings": px})

    rivers = []
    for f in load(ne_dir, "ne_10m_rivers_lake_centerlines")["features"]:
        name = f["properties"].get("name") or ""
        for line in lines_of(f["geometry"]):
            for part in clip_line_rect(line, LON_MIN, LAT_MIN, LON_MAX, LAT_MAX):
                pts = dp([project(x, y) for x, y in part], 0.4)
                if len(pts) >= 2:
                    rivers.append({"name": name, "points": [[round(x, 2), round(y, 2)] for x, y in pts]})

    sites = {sid: [round(v, 2) for v in project(*ll)] for sid, ll in SITES_LONLAT.items()}
    labels = [{**{k: v for k, v in lab.items() if k != "lonlat"},
               "pos": [round(v, 1) for v in project(*lab["lonlat"])]} for lab in LABELS]

    return {
        "schema_version": 1,
        "source": "Natural Earth 1:10m (public domain); built by tools/build_map_geo.py",
        "frame": {"width": MAP_W, "height": MAP_H},
        "projection": {
            "type": "equirectangular", "lat_center": LAT_C, "lon_min": round(LON_MIN, 6),
            "lat_max": LAT_MAX, "px_per_deg_lat": round(SCALE, 6), "px_per_deg_lon": round(KX, 6),
        },
        "graticule_step_deg": 1,
        "regions": regions,
        "countries": countries,
        "lakes": lakes,
        "rivers": rivers,
        "sites": sites,
        "labels": labels,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ne-dir", default="/tmp/ne")
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    ne_dir = Path(args.ne_dir)
    if args.download:
        ne_dir.mkdir(parents=True, exist_ok=True)
        for name in NE_FILES:
            urllib.request.urlretrieve(NE_URL.format(name), ne_dir / f"{name}.geojson")
    data = build(ne_dir)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    pts = sum(len(r) for reg in data["regions"].values() for r in reg["rings"])
    print(f"WROTE {OUT.relative_to(ROOT)} regions={len(data['regions'])} region_pts={pts} "
          f"countries={len(data['countries'])} lakes={len(data['lakes'])} rivers={len(data['rivers'])} "
          f"bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
