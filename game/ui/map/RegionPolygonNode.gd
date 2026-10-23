class_name RegionPolygonNode
extends Node2D

const INK: Color = Color(0.1176, 0.1098, 0.102, 1)
const AMBER: Color = Color(0.784, 0.541, 0.118, 1)
const BORDER_WIDTH: float = 1.5
const SELECTED_WIDTH: float = 3.5
## Hatch stripe period in map px (occupied_hatch.gdshader period_px).
const HATCH_PERIOD_PX: float = 9.0

var region_id: String = ""
var occupied: bool = false
var selected: bool = false
## Real-geography rings (map-local px at zoom 1); several for sinai / south_lebanon.
var rings: Array[PackedVector2Array] = []
## Largest ring (kept for callers that want a single outline).
var polygon: PackedVector2Array = PackedVector2Array()
var fills: Array[Polygon2D] = []
var borders: Array[Line2D] = []
var view_zoom: float = 1.0


func setup(id: String, region_rings: Array[PackedVector2Array], is_occupied: bool, show_region: bool) -> void:
	region_id = id
	occupied = is_occupied
	rings = region_rings
	visible = show_region
	for child: Node in get_children():
		remove_child(child)
		child.queue_free()
	fills.clear()
	borders.clear()
	polygon = PackedVector2Array()
	var hatch_material: ShaderMaterial = null
	if is_occupied:
		hatch_material = ShaderMaterial.new()
		hatch_material.shader = load("res://ui/shaders/occupied_hatch.gdshader") as Shader
		var bounds: Rect2 = MapGeoData.rings_bounds(region_rings)
		hatch_material.set_shader_parameter("bbox", Vector4(bounds.position.x, bounds.position.y, bounds.size.x, bounds.size.y))
		hatch_material.set_shader_parameter("period_px", HATCH_PERIOD_PX)
	for i: int in range(region_rings.size()):
		var ring: PackedVector2Array = region_rings[i]
		if ring.size() > polygon.size():
			polygon = ring
		var parts: Array[PackedVector2Array] = MapGeoData.fill_parts(ring)
		for j: int in range(parts.size()):
			var fill: Polygon2D = Polygon2D.new()
			fill.polygon = parts[j]
			fill.color = Color(0.227, 0.42, 0.208, 0.85)
			fill.antialiased = true
			if hatch_material != null:
				fill.material = hatch_material
			add_child(fill)
			fills.append(fill)
	for i: int in range(region_rings.size()):
		var border: Line2D = Line2D.new()
		border.closed = true
		border.points = region_rings[i]
		border.joint_mode = Line2D.LINE_JOINT_ROUND
		border.antialiased = true
		add_child(border)
		borders.append(border)
	_style_borders()


func set_fill(color: Color) -> void:
	for i: int in range(fills.size()):
		fills[i].color = color


func set_selected(is_selected: bool) -> void:
	selected = is_selected
	_style_borders()


## Keeps border widths constant on screen while the map zooms (the world node is scaled).
func set_view_zoom(next_zoom: float) -> void:
	view_zoom = maxf(next_zoom, 0.1)
	_style_borders()


func _style_borders() -> void:
	var width: float = (SELECTED_WIDTH if selected else BORDER_WIDTH) / view_zoom
	for i: int in range(borders.size()):
		var border: Line2D = borders[i]
		border.default_color = AMBER if selected else INK
		border.width = width
		# Keep the amber outline above neighbouring regions that are drawn later.
		border.z_index = 1 if selected else 0


func contains_point(point: Vector2) -> bool:
	for i: int in range(rings.size()):
		if Geometry2D.is_point_in_polygon(point, rings[i]):
			return true
	return false


func select_from_ui() -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.region_selected.emit(region_id)
