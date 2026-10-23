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
const ZOOM_MAX: float = 3.0

var layer_index: int = 1
var zoom: float = 1.0
## Map-local translation of the region layer. The control itself never moves, so the
## (240,52) desk offset from DeskMain.tscn is preserved by pan, zoom and reset.
var pan: Vector2 = Vector2.ZERO
var region_nodes: Dictionary = {}
## Region ids in draw order (last = topmost); hit-testing walks it backwards.
var region_order: Array[String] = []
var pin_nodes: Array[MapSitePin] = []
var bound_state: SimState = null
var selected_region: String = ""
## Holds the region polygons and pins; carries the pan/zoom transform.
var world: Node2D = null


func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	clip_contents = true
	build_from_registry(null)


func _ensure_world() -> void:
	if world != null:
		return
	world = Node2D.new()
	world.name = "World"
	add_child(world)
	_apply_view()


func build_from_registry(state: SimState) -> void:
	bound_state = state
	_ensure_world()
	for child: Node in world.get_children():
		world.remove_child(child)
		child.queue_free()
	region_nodes.clear()
	region_order.clear()
	pin_nodes.clear()
	if GameData.current == null:
		return
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.regions_def)
	for i: int in range(ids.size()):
		var region_id: String = ids[i]
		var src: Dictionary = _dict(GameData.current.regions_def[region_id])
		var node: RegionPolygonNode = RegionPolygonNode.new()
		var occupied: bool = _occupied(src)
		node.setup(region_id, _schematic(region_id), occupied, _exists(region_id, src))
		world.add_child(node)
		region_nodes[region_id] = node
		region_order.append(region_id)
	_place_pins()
	set_map_layer(layer_index)
	set_selected_region(selected_region)


func set_map_layer(index: int) -> void:
	layer_index = clampi(index, 1, 7)
	var ids: Array = region_nodes.keys()
	for i: int in range(ids.size()):
		var region_id: String = String(ids[i])
		var node: RegionPolygonNode = region_nodes[region_id]
		node.set_fill(_layer_color(region_id))
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.map_layer_changed.emit(layer_index)


## Zooms in [0.8, 3.0] (0.1 steps) keeping the map-local `anchor` point fixed on screen.
func set_zoom(next_zoom: float, anchor: Vector2 = Vector2.ZERO) -> void:
	var target: float = clampf(snappedf(next_zoom, 0.1), ZOOM_MIN, ZOOM_MAX)
	var anchor_world: Vector2 = to_world(anchor)
	zoom = target
	pan = anchor - anchor_world * zoom
	_apply_view()


func reset_view() -> void:
	zoom = 1.0
	pan = Vector2.ZERO
	_apply_view()


func _apply_view() -> void:
	if world == null:
		return
	world.position = pan
	world.scale = Vector2(zoom, zoom)


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


## Highlights one region (4 px amber outline); "" clears the highlight.
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


func _gui_input(event: InputEvent) -> void:
	if event is InputEventMouseButton:
		var button: InputEventMouseButton = event as InputEventMouseButton
		if not button.pressed:
			return
		if button.button_index == MOUSE_BUTTON_WHEEL_UP:
			set_zoom(zoom + 0.1, button.position)
			accept_event()
		elif button.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			set_zoom(zoom - 0.1, button.position)
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


func _place_pins() -> void:
	if GameData.current == null:
		return
	var sites: Array = GameData.current.sites_list
	for i: int in range(sites.size()):
		if typeof(sites[i]) != TYPE_DICTIONARY:
			continue
		var site: Dictionary = sites[i]
		var region_id: String = String(site.get("region_id", ""))
		var node: RegionPolygonNode = region_nodes.get(region_id, null)
		var at: Vector2 = _centroid(region_id) + Vector2(float(i % 5) * 8.0, float(i % 3) * 8.0)
		if node != null and not node.polygon.is_empty():
			at = node.polygon[0] + Vector2(12.0 + float(i % 4) * 10.0, 12.0)
		var pin: MapSitePin = MapSitePin.new()
		pin.setup(site, at)
		pin.z_index = 2
		world.add_child(pin)
		pin_nodes.append(pin)


func _centroid(region_id: String) -> Vector2:
	var points: PackedVector2Array = _schematic(region_id)
	if points.is_empty():
		return Vector2.ZERO
	var sum: Vector2 = Vector2.ZERO
	for i: int in range(points.size()):
		sum += points[i]
	return sum / float(points.size())


func _schematic(region_id: String) -> PackedVector2Array:
	var box: Rect2 = _box(region_id)
	return PackedVector2Array([
		box.position,
		box.position + Vector2(box.size.x, 0),
		box.position + box.size,
		box.position + Vector2(0, box.size.y),
	])


func _box(region_id: String) -> Rect2:
	match region_id:
		"south_lebanon":
			return Rect2(80, 8, 220, 70)
		"golan":
			return Rect2(620, 40, 180, 150)
		"galilee":
			return Rect2(300, 40, 300, 170)
		"haifa":
			return Rect2(180, 210, 200, 140)
		"triangle":
			return Rect2(390, 230, 180, 160)
		"tel_aviv":
			return Rect2(140, 360, 240, 150)
		"jerusalem":
			return Rect2(400, 370, 200, 160)
		"west_bank":
			return Rect2(610, 210, 200, 300)
		"gaza":
			return Rect2(70, 520, 120, 140)
		"negev":
			return Rect2(200, 530, 420, 280)
		"sinai":
			return Rect2(40, 680, 280, 180)
		_:
			return Rect2(20, 20, 80, 80)


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
