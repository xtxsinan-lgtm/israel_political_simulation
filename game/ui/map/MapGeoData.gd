class_name MapGeoData
extends RefCounted

## Real-geography map data shared with the web prototype (res://res/map/map_geo.json, built by
## tools/build_map_geo.py from Natural Earth). Every coordinate is already map-local px of the
## 1440x942 map rect at zoom 1, so the canvas uses them directly.

const PATH: String = "res://res/map/map_geo.json"

var loaded: bool = false
var frame_size: Vector2 = Vector2(1440.0, 942.0)
var lon_min: float = 0.0
var lat_max: float = 0.0
var px_per_deg_lon: float = 1.0
var px_per_deg_lat: float = 1.0
var graticule_step: float = 1.0
## region id -> Array of PackedVector2Array rings (closing duplicate point stripped).
var region_rings: Dictionary = {}
## region id -> Vector2 label anchor.
var region_labels: Dictionary = {}
## Each entry: {"id": String, "name_zh": String, "rings": Array}.
var countries: Array[Dictionary] = []
## Lake rings.
var lakes: Array[PackedVector2Array] = []
## River polylines.
var rivers: Array[PackedVector2Array] = []
## site id -> Vector2.
var sites: Dictionary = {}
## Each entry: {"text": String, "en": String, "kind": String, "pos": Vector2}.
var labels: Array[Dictionary] = []


static func load_default() -> MapGeoData:
	var geo: MapGeoData = MapGeoData.new()
	geo.load_file(PATH)
	return geo


func load_file(path: String) -> bool:
	loaded = false
	if not FileAccess.file_exists(path):
		push_warning("map_geo missing: %s" % path)
		return false
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return false
	var text: String = file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		push_warning("map_geo parse failed: %s" % path)
		return false
	_read(parsed as Dictionary)
	loaded = true
	return true


func rings_of(region_id: String) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	var raw: Variant = region_rings.get(region_id, [])
	if typeof(raw) == TYPE_ARRAY:
		var list: Array = raw
		for i: int in range(list.size()):
			if list[i] is PackedVector2Array:
				out.append(list[i] as PackedVector2Array)
	return out


func label_of(region_id: String) -> Vector2:
	if region_labels.has(region_id):
		return region_labels[region_id] as Vector2
	return Vector2(-1.0, -1.0)


func has_site(site_id: String) -> bool:
	return sites.has(site_id)


func site_of(site_id: String) -> Vector2:
	if sites.has(site_id):
		return sites[site_id] as Vector2
	return Vector2.ZERO


## Polygons a Polygon2D can triangulate for `ring`. Douglas-Peucker can leave tiny bow-ties
## (e.g. near the Suez canal in sinai / EGY); those rings are cleaned with a Clipper union and
## only the outer parts (same winding as the largest part) are kept. Usually returns [ring].
static func fill_parts(ring: PackedVector2Array) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	if ring.size() < 3:
		return out
	if not Geometry2D.triangulate_polygon(ring).is_empty():
		out.append(ring)
		return out
	var merged: Array[PackedVector2Array] = Geometry2D.merge_polygons(ring, ring)
	var largest: float = -1.0
	var outer_clockwise: bool = false
	for i: int in range(merged.size()):
		var part_area: float = absf(_signed_area(merged[i]))
		if part_area > largest:
			largest = part_area
			outer_clockwise = Geometry2D.is_polygon_clockwise(merged[i])
	for i: int in range(merged.size()):
		var part: PackedVector2Array = merged[i]
		if part.size() < 3 or Geometry2D.is_polygon_clockwise(part) != outer_clockwise:
			continue
		if not Geometry2D.triangulate_polygon(part).is_empty():
			out.append(part)
	return out


static func _signed_area(points: PackedVector2Array) -> float:
	var total: float = 0.0
	var count: int = points.size()
	for i: int in range(count):
		var a: Vector2 = points[i]
		var b: Vector2 = points[(i + 1) % count]
		total += a.x * b.y - b.x * a.y
	return total * 0.5


## Union bounding box of several rings (hatch shader bbox for multi-ring regions).
static func rings_bounds(rings: Array[PackedVector2Array]) -> Rect2:
	var bounds: Rect2 = Rect2()
	var started: bool = false
	for i: int in range(rings.size()):
		var ring: PackedVector2Array = rings[i]
		for j: int in range(ring.size()):
			if not started:
				bounds = Rect2(ring[j], Vector2.ZERO)
				started = true
			else:
				bounds = bounds.expand(ring[j])
	if not started:
		return Rect2(0.0, 0.0, 1.0, 1.0)
	return bounds


## Map-local x of a meridian / y of a parallel (equirectangular projection of the builder).
func lon_to_x(lon: float) -> float:
	return (lon - lon_min) * px_per_deg_lon


func lat_to_y(lat: float) -> float:
	return (lat_max - lat) * px_per_deg_lat


func _read(src: Dictionary) -> void:
	var frame: Dictionary = _dict(src.get("frame", {}))
	frame_size = Vector2(float(frame.get("width", 1440.0)), float(frame.get("height", 942.0)))
	var proj: Dictionary = _dict(src.get("projection", {}))
	lon_min = float(proj.get("lon_min", 0.0))
	lat_max = float(proj.get("lat_max", 0.0))
	px_per_deg_lon = maxf(float(proj.get("px_per_deg_lon", 1.0)), 0.001)
	px_per_deg_lat = maxf(float(proj.get("px_per_deg_lat", 1.0)), 0.001)
	graticule_step = maxf(float(src.get("graticule_step_deg", 1.0)), 0.25)
	region_rings.clear()
	region_labels.clear()
	var regions: Dictionary = _dict(src.get("regions", {}))
	var region_ids: Array = regions.keys()
	for i: int in range(region_ids.size()):
		var region_id: String = String(region_ids[i])
		var entry: Dictionary = _dict(regions[region_ids[i]])
		region_rings[region_id] = _rings(entry.get("rings", []))
		region_labels[region_id] = _vec(entry.get("label", []))
	countries.clear()
	var country_list: Array = _arr(src.get("countries", []))
	for i: int in range(country_list.size()):
		var country: Dictionary = _dict(country_list[i])
		countries.append({
			"id": String(country.get("id", "")),
			"name_zh": String(country.get("name_zh", "")),
			"rings": _rings(country.get("rings", [])),
		})
	lakes.clear()
	var lake_list: Array = _arr(src.get("lakes", []))
	for i: int in range(lake_list.size()):
		var lake_rings: Array[PackedVector2Array] = _rings(_dict(lake_list[i]).get("rings", []))
		for j: int in range(lake_rings.size()):
			lakes.append(lake_rings[j])
	rivers.clear()
	var river_list: Array = _arr(src.get("rivers", []))
	for i: int in range(river_list.size()):
		var line: PackedVector2Array = _points(_dict(river_list[i]).get("points", []), false)
		if line.size() >= 2:
			rivers.append(line)
	sites.clear()
	var site_src: Dictionary = _dict(src.get("sites", {}))
	var site_ids: Array = site_src.keys()
	for i: int in range(site_ids.size()):
		sites[String(site_ids[i])] = _vec(site_src[site_ids[i]])
	labels.clear()
	var label_list: Array = _arr(src.get("labels", []))
	for i: int in range(label_list.size()):
		var lab: Dictionary = _dict(label_list[i])
		labels.append({
			"text": String(lab.get("text", "")),
			"en": String(lab.get("en", "")),
			"kind": String(lab.get("kind", "")),
			"pos": _vec(lab.get("pos", [])),
		})


func _rings(value: Variant) -> Array[PackedVector2Array]:
	var out: Array[PackedVector2Array] = []
	var list: Array = _arr(value)
	for i: int in range(list.size()):
		var ring: PackedVector2Array = _points(list[i], true)
		if ring.size() >= 3:
			out.append(ring)
	return out


## [[x, y], ...] -> PackedVector2Array; rings drop the explicit closing point (Polygon2D and
## Line2D.closed close the shape themselves, and a zero-length edge can break triangulation).
func _points(value: Variant, is_ring: bool) -> PackedVector2Array:
	var out: PackedVector2Array = PackedVector2Array()
	var list: Array = _arr(value)
	for i: int in range(list.size()):
		var pair: Array = _arr(list[i])
		if pair.size() < 2:
			continue
		var point: Vector2 = Vector2(float(pair[0]), float(pair[1]))
		if out.size() > 0 and out[out.size() - 1].is_equal_approx(point):
			continue
		out.append(point)
	if is_ring and out.size() > 1 and out[0].is_equal_approx(out[out.size() - 1]):
		out.remove_at(out.size() - 1)
	return out


func _vec(value: Variant) -> Vector2:
	var pair: Array = _arr(value)
	if pair.size() < 2:
		return Vector2(-1.0, -1.0)
	return Vector2(float(pair[0]), float(pair[1]))


func _arr(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
