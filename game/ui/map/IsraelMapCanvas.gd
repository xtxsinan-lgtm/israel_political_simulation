class_name IsraelMapCanvas
extends Control

const LAYER_F1: String = "F1"
const LAYER_F2: String = "F2"
const LAYER_F3: String = "F3"
const LAYER_F4: String = "F4"
const LAYER_F5: String = "F5"
const LAYER_F6: String = "F6"
const LAYER_F7: String = "F7"

const ZOOM_MIN: float = 0.8
const ZOOM_MAX: float = 6.0
## Wheel zoom factor per notch (result snapped to 0.1).
const ZOOM_STEP: float = 1.15

const SEA: Color = Color(0.796078, 0.847059, 0.835294, 1.0)  # #CBD8D5
const LAND: Color = Color(0.913725, 0.874510, 0.784314, 1.0)  # #E9DFC8
const LAND_BORDER: Color = Color(0.478, 0.373, 0.235, 0.75)
const LAKE: Color = Color(0.615686, 0.733333, 0.768627, 1.0)  # #9DBBC4
const RIVER: Color = Color(0.333, 0.529, 0.62, 0.85)
const COAST_NEAR: Color = Color(0.43, 0.6, 0.66, 0.30)
const COAST_FAR: Color = Color(0.43, 0.6, 0.66, 0.14)
const GRATICULE: Color = Color(0.2, 0.27, 0.3, 0.12)
const INK: Color = Color(0.1176, 0.1098, 0.102, 1)
const COUNTRY_INK: Color = Color(0.42, 0.33, 0.22, 0.85)
const WATER_INK: Color = Color(0.22, 0.4, 0.48, 0.9)

## Short Chinese region names drawn at map_geo.json regions[id].label.
const REGION_NAMES: Dictionary = {
	"galilee": "加利利",
	"haifa": "海法",
	"tel_aviv": "特拉维夫",
	"triangle": "中央区",
	"jerusalem": "耶路撒冷",
	"negev": "内盖夫",
	"west_bank": "西岸",
	"gaza": "加沙",
	"golan": "戈兰",
	"sinai": "西奈",
	"south_lebanon": "南黎巴嫩",
}

var layer_index: int = 1
var zoom: float = 1.0
## Map-local translation of the region layer. The control itself never moves, so the
## (240,52) desk offset from DeskMain.tscn is preserved by pan, zoom and reset.
var pan: Vector2 = Vector2.ZERO
var region_nodes: Dictionary = {}
## Region ids in draw order (last = topmost); hit-testing walks it backwards.
var region_order: Array[String] = []
var pin_nodes: Array[MapSitePin] = []
## region id -> MapLabel with the short Chinese name.
var region_labels: Dictionary = {}
## Every MapLabel (context + regions); counter-scaled so text keeps its screen size.
var label_nodes: Array[MapLabel] = []
var bound_state: SimState = null
var selected_region: String = ""
## Real geography (res://res/map/map_geo.json), loaded once.
var geo: MapGeoData = null
## Holds the context, region polygons, labels and pins; carries the pan/zoom transform.
var world: Node2D = null
## Static geography under the regions (land, coast lining, rivers, graticule, country labels).
var context_layer: Node2D = null
var region_layer: Node2D = null
## Lakes drawn over the region fills (the Sea of Galilee lies inside the galilee polygon).
var water_layer: Node2D = null
var label_layer: Node2D = null
var pin_layer: Node2D = null


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	build_from_registry(null)


## Sea background under everything; the world node draws on top of it.
func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), SEA, true)


func _ensure_world() -> void:
	if world != null:
		return
	if geo == null:
		geo = MapGeoData.load_default()
	world = Node2D.new()
	world.name = "World"
	add_child(world)
	context_layer = _layer("Context", 0)
	region_layer = _layer("Regions", 0)
	water_layer = _layer("Water", 2)
	label_layer = _layer("Labels", 4)
	pin_layer = _layer("Pins", 3)
	_build_context()
	_apply_view()


func _layer(layer_name: String, z: int) -> Node2D:
	var node: Node2D = Node2D.new()
	node.name = layer_name
	node.z_index = z
	world.add_child(node)
	return node


func build_from_registry(state: SimState) -> void:
	bound_state = state
	_ensure_world()
	_clear(region_layer)
	_clear(pin_layer)
	for i: int in range(label_nodes.size() - 1, -1, -1):
		if label_nodes[i].get_parent() == label_layer:
			label_nodes.remove_at(i)
	_clear(label_layer)
	region_nodes.clear()
	region_order.clear()
	region_labels.clear()
	pin_nodes.clear()
	if GameData.current == null:
		return
	var font: Font = _map_font()
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.regions_def)
	for i: int in range(ids.size()):
		var region_id: String = ids[i]
		var src: Dictionary = _dict(GameData.current.regions_def[region_id])
		var node: RegionPolygonNode = RegionPolygonNode.new()
		node.name = region_id
		var occupied: bool = _occupied(src)
		node.setup(region_id, geo.rings_of(region_id), occupied, _exists(region_id, src))
		region_layer.add_child(node)
		region_nodes[region_id] = node
		region_order.append(region_id)
		var anchor: Vector2 = geo.label_of(region_id)
		if anchor.x >= 0.0:
			var label: MapLabel = MapLabel.new()
			label.setup(String(REGION_NAMES.get(region_id, region_id)), anchor, font, 13, INK)
			label.visible = node.visible
			label_layer.add_child(label)
			label_nodes.append(label)
			region_labels[region_id] = label
	_place_pins()
	_add_lake_labels(font)
	set_map_layer(layer_index)
	set_selected_region(selected_region)
	_apply_view()


func set_map_layer(index: int) -> void:
	layer_index = clampi(index, 1, 7)
	_refresh_visibility()
	var ids: Array = region_nodes.keys()
	for i: int in range(ids.size()):
		var region_id: String = String(ids[i])
		var node: RegionPolygonNode = region_nodes[region_id]
		node.set_fill(_layer_color(region_id))
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.map_layer_changed.emit(layer_index)


## Zooms in [0.8, 6.0] (0.1 steps) keeping the map-local `anchor` point fixed on screen.
func set_zoom(next_zoom: float, anchor: Vector2 = Vector2.ZERO) -> void:
	var target: float = clampf(snappedf(next_zoom, 0.1), ZOOM_MIN, ZOOM_MAX)
	var anchor_world: Vector2 = to_world(anchor)
	zoom = target
	pan = anchor - anchor_world * zoom
	_apply_view()


## One wheel notch: multiplicative step so 0.8 -> 6.0 takes ~15 notches, never stalls on snapping.
func wheel_zoom(direction: int, anchor: Vector2) -> void:
	var next_zoom: float = zoom * ZOOM_STEP if direction > 0 else zoom / ZOOM_STEP
	if absf(snappedf(next_zoom, 0.1) - zoom) < 0.05:
		next_zoom = zoom + (0.1 if direction > 0 else -0.1)
	set_zoom(next_zoom, anchor)


func reset_view() -> void:
	zoom = 1.0
	pan = Vector2.ZERO
	_apply_view()


func _apply_view() -> void:
	if world == null:
		return
	world.position = pan
	world.scale = Vector2(zoom, zoom)
	var inverse: Vector2 = Vector2.ONE / zoom
	for i: int in range(label_nodes.size()):
		label_nodes[i].scale = inverse
	for i: int in range(pin_nodes.size()):
		pin_nodes[i].scale = inverse
	var ids: Array = region_nodes.keys()
	for i: int in range(ids.size()):
		var node: RegionPolygonNode = region_nodes[ids[i]]
		node.set_view_zoom(zoom)


## Map-local (control) coordinates -> region coordinate space (undo pan/zoom).
func to_world(local_point: Vector2) -> Vector2:
	return (local_point - pan) / zoom


## Topmost visible region under a map-local point, or "" for empty map.
func region_at(local_point: Vector2) -> String:
	var world_point: Vector2 = to_world(local_point)
	for i: int in range(region_order.size() - 1, -1, -1):
		var region_id: String = region_order[i]
		var node: RegionPolygonNode = region_nodes.get(region_id, null)
		if node != null and node.visible and node.contains_point(world_point):
			return region_id
	return ""


## Highlights one region (amber outline above its neighbours); "" clears the highlight.
func set_selected_region(region_id: String) -> void:
	selected_region = region_id if region_nodes.has(region_id) else ""
	var ids: Array = region_nodes.keys()
	for i: int in range(ids.size()):
		var node: RegionPolygonNode = region_nodes[ids[i]]
		node.set_selected(String(ids[i]) == selected_region)


## Left-click handler: hit-tests and emits region_selected(id) ("" on empty map).
func click_at(local_point: Vector2) -> String:
	var hit: String = region_at(local_point)
	if hit == "" and selected_region == "":
		return hit
	set_selected_region(hit)
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.region_selected.emit(hit)
	return hit


func visible_region_count() -> int:
	var count: int = 0
	var ids: Array = region_nodes.keys()
	for i: int in range(ids.size()):
		var node: RegionPolygonNode = region_nodes[ids[i]]
		if node.visible:
			count += 1
	return count


## Real map-local (zoom 1) position of a site pin, or (-1,-1) if the pin does not exist.
func pin_position(site_id: String) -> Vector2:
	for i: int in range(pin_nodes.size()):
		if pin_nodes[i].site_id == site_id:
			return pin_nodes[i].position
	return Vector2(-1.0, -1.0)


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button: InputEventMouseButton = event as InputEventMouseButton
		if not button.pressed:
			return
		if button.button_index == MOUSE_BUTTON_WHEEL_UP:
			wheel_zoom(1, button.position)
			accept_event()
		elif button.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			wheel_zoom(-1, button.position)
			accept_event()
		elif button.button_index == MOUSE_BUTTON_LEFT:
			if button.double_click:
				reset_view()
			else:
				click_at(button.position)
			accept_event()
	elif event is InputEventMouseMotion and (Input.is_mouse_button_pressed(MOUSE_BUTTON_MIDDLE) or Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT)):
		var motion: InputEventMouseMotion = event as InputEventMouseMotion
		pan += motion.relative
		_apply_view()
		accept_event()


func _exists(region_id: String, src: Dictionary) -> bool:
	if bound_state != null:
		var m11: Dictionary = _dict(bound_state.modules.get("M11", {}))
		var regions: Dictionary = _dict(m11.get("regions", {}))
		if regions.has(region_id):
			return bool(_dict(regions[region_id]).get("exists", true))
	if src.has("exists"):
		return bool(src["exists"])
	return region_id != "south_lebanon"


## M11 `exists` can flip during play (e.g. south_lebanon); regions, their names and pins follow.
func _refresh_visibility() -> void:
	if GameData.current == null:
		return
	var ids: Array = region_nodes.keys()
	for i: int in range(ids.size()):
		var region_id: String = String(ids[i])
		var node: RegionPolygonNode = region_nodes[region_id]
		node.visible = _exists(region_id, _dict(GameData.current.regions_def.get(region_id, {})))
		if region_labels.has(region_id):
			var label: MapLabel = region_labels[region_id]
			label.visible = node.visible
	for i: int in range(pin_nodes.size()):
		var pin: MapSitePin = pin_nodes[i]
		var owner_node: RegionPolygonNode = region_nodes.get(pin.region_id, null)
		pin.visible = owner_node == null or owner_node.visible


func _occupied(src: Dictionary) -> bool:
	var status: String = String(src.get("legal_status", ""))
	return status == "occupied" or status == "military_occupation" or status.contains("occup")


func _layer_color(region_id: String) -> Color:
	var security: float = 60.0
	var development: float = 40.0
	if bound_state != null:
		security = bound_state.params.get_val("region_security", region_id, bound_state)
		development = bound_state.params.get_val("region_development", region_id, bound_state)
	match layer_index:
		1:
			return Color(0.0, 0.22, 0.72, 0.75) if not _node_occupied(region_id) else Color(0.55, 0.42, 0.22, 0.8)
		2:
			return Color(0.0, 0.22, 0.72, 0.8)
		3:
			return Color(1.0 - security / 100.0, security / 100.0, 0.2, 0.85)
		4:
			return Color(0.15, 0.25 + development / 200.0, 0.45, 0.85)
		5:
			return Color(0.45, 0.25, 0.55, 0.8)
		6:
			return Color(0.72, 0.25, 0.18, 0.75)
		_:
			return Color(0.15, 0.35, 0.62, 0.55)


func _node_occupied(region_id: String) -> bool:
	var node: RegionPolygonNode = region_nodes[region_id]
	return node.occupied


## Pins sit on the real site coordinates (map_geo.json `sites`); unknown sites fall back to the
## region label anchor with a small fan-out so they stay inside their region.
func _place_pins() -> void:
	if GameData.current == null:
		return
	var sites: Array = GameData.current.sites_list
	for i: int in range(sites.size()):
		if typeof(sites[i]) != TYPE_DICTIONARY:
			continue
		var site: Dictionary = sites[i]
		var site_id: String = String(site.get("site_id", ""))
		var region_id: String = String(site.get("region_id", ""))
		var at: Vector2 = geo.site_of(site_id)
		if not geo.has_site(site_id):
			var anchor: Vector2 = geo.label_of(region_id)
			if anchor.x < 0.0:
				anchor = Vector2.ZERO
			at = anchor + Vector2(float(i % 3) * 8.0 - 8.0, 14.0 + float(i % 2) * 8.0)
		var pin: MapSitePin = MapSitePin.new()
		pin.setup(site, at)
		var owner_node: RegionPolygonNode = region_nodes.get(region_id, null)
		pin.visible = owner_node == null or owner_node.visible
		pin_layer.add_child(pin)
		pin_nodes.append(pin)


## Static context drawn once: coast water-lining, land, borders, rivers, graticule, sea and
## country labels (under the regions) and lakes (over the region fills). Never touched per day.
func _build_context() -> void:
	if geo == null or not geo.loaded:
		return
	var land_rings: Array[PackedVector2Array] = []
	for i: int in range(geo.countries.size()):
		var country_rings: Array = geo.countries[i].get("rings", [])
		for j: int in range(country_rings.size()):
			if country_rings[j] is PackedVector2Array:
				land_rings.append(country_rings[j] as PackedVector2Array)
	var country_ring_count: int = land_rings.size()
	var region_ids: Array = geo.region_rings.keys()
	region_ids.sort()
	for i: int in range(region_ids.size()):
		var rings: Array[PackedVector2Array] = geo.rings_of(String(region_ids[i]))
		for j: int in range(rings.size()):
			land_rings.append(rings[j])
	# Water-lining: two soft coastline strokes per land ring, widest first, under the land fill.
	for i: int in range(land_rings.size()):
		context_layer.add_child(_line(land_rings[i], true, 11.0, COAST_FAR))
	for i: int in range(land_rings.size()):
		context_layer.add_child(_line(land_rings[i], true, 5.0, COAST_NEAR))
	# Land base (region rings too, so the translucent layer colours sit on land, not sea).
	for i: int in range(land_rings.size()):
		var parts: Array[PackedVector2Array] = MapGeoData.fill_parts(land_rings[i])
		for j: int in range(parts.size()):
			var land: Polygon2D = Polygon2D.new()
			land.polygon = parts[j]
			land.color = LAND
			land.antialiased = true
			context_layer.add_child(land)
	for i: int in range(country_ring_count):
		context_layer.add_child(_line(land_rings[i], true, 0.8, LAND_BORDER))
	for i: int in range(geo.rivers.size()):
		context_layer.add_child(_line(geo.rivers[i], false, 1.1, RIVER))
	_build_graticule()
	for i: int in range(geo.lakes.size()):
		var lake_parts: Array[PackedVector2Array] = MapGeoData.fill_parts(geo.lakes[i])
		for j: int in range(lake_parts.size()):
			var lake: Polygon2D = Polygon2D.new()
			lake.polygon = lake_parts[j]
			lake.color = LAKE
			lake.antialiased = true
			water_layer.add_child(lake)
		water_layer.add_child(_line(geo.lakes[i], true, 0.6, Color(0.33, 0.5, 0.58, 0.8)))
	var font: Font = _map_font()
	for i: int in range(geo.labels.size()):
		var entry: Dictionary = geo.labels[i]
		var kind: String = String(entry.get("kind", ""))
		if kind == "lake":
			continue
		var label: MapLabel = MapLabel.new()
		var size_px: int = 15
		var tint: Color = COUNTRY_INK
		if kind == "sea":
			size_px = 16
			tint = WATER_INK
		elif kind == "sea_small":
			size_px = 12
			tint = WATER_INK
		label.setup(String(entry.get("text", "")), entry.get("pos", Vector2.ZERO) as Vector2, font, size_px, tint, String(entry.get("en", "")))
		context_layer.add_child(label)
		label_nodes.append(label)


## Lake names sit with the lakes above the region fills (rebuilt with the region labels).
func _add_lake_labels(font: Font) -> void:
	if geo == null:
		return
	for i: int in range(geo.labels.size()):
		var entry: Dictionary = geo.labels[i]
		if String(entry.get("kind", "")) != "lake":
			continue
		var label: MapLabel = MapLabel.new()
		label.setup(String(entry.get("text", "")), entry.get("pos", Vector2.ZERO) as Vector2, font, 12, WATER_INK)
		label_layer.add_child(label)
		label_nodes.append(label)


## Faint 1° meridians / parallels from map_geo.json `projection`.
func _build_graticule() -> void:
	var frame: Vector2 = geo.frame_size
	var step: float = geo.graticule_step
	var lon_max: float = geo.lon_min + frame.x / geo.px_per_deg_lon
	var lat_min: float = geo.lat_max - frame.y / geo.px_per_deg_lat
	var lon: float = ceilf(geo.lon_min / step) * step
	while lon <= lon_max:
		var x: float = geo.lon_to_x(lon)
		context_layer.add_child(_line(PackedVector2Array([Vector2(x, 0.0), Vector2(x, frame.y)]), false, 1.0, GRATICULE))
		lon += step
	var lat: float = ceilf(lat_min / step) * step
	while lat <= geo.lat_max:
		var y: float = geo.lat_to_y(lat)
		context_layer.add_child(_line(PackedVector2Array([Vector2(0.0, y), Vector2(frame.x, y)]), false, 1.0, GRATICULE))
		lat += step


func _line(points: PackedVector2Array, closed: bool, width: float, tint: Color) -> Line2D:
	var line: Line2D = Line2D.new()
	line.points = points
	line.closed = closed
	line.width = width
	line.default_color = tint
	line.joint_mode = Line2D.LINE_JOINT_ROUND
	line.antialiased = true
	return line


func _map_font() -> Font:
	var font: Font = get_theme_font("font", "Label")
	if font == null:
		font = ThemeDB.fallback_font
	return font


func _clear(parent: Node) -> void:
	if parent == null:
		return
	for child: Node in parent.get_children():
		parent.remove_child(child)
		child.queue_free()


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
