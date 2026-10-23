class_name RegionPolygonNode
extends Node2D

var region_id: String = ""
var occupied: bool = false
var polygon: PackedVector2Array = PackedVector2Array()
var fill: Polygon2D
var border: Line2D


func setup(id: String, points: PackedVector2Array, is_occupied: bool, show_region: bool) -> void:
	region_id = id
	occupied = is_occupied
	polygon = points
	visible = show_region
	fill = Polygon2D.new()
	fill.polygon = points
	fill.color = Color(0.227, 0.42, 0.208, 0.85)
	if is_occupied:
		var hatch_material: ShaderMaterial = ShaderMaterial.new()
		hatch_material.shader = load("res://ui/shaders/occupied_hatch.gdshader") as Shader
		var bounds: Rect2 = _bounds(points)
		hatch_material.set_shader_parameter("bbox", Vector4(bounds.position.x, bounds.position.y, bounds.size.x, bounds.size.y))
		fill.material = hatch_material
	add_child(fill)
	border = Line2D.new()
	border.width = 2.0
	border.default_color = Color(0.1176, 0.1098, 0.102, 1)
	border.closed = true
	border.points = points
	add_child(border)


func set_fill(color: Color) -> void:
	if fill != null:
		fill.color = color


func set_selected(selected: bool) -> void:
	if border == null:
		return
	border.default_color = Color(0.784, 0.541, 0.118, 1) if selected else Color(0.1176, 0.1098, 0.102, 1)
	border.width = 4.0 if selected else 2.0
	# Keep the amber outline above neighbouring regions that are drawn later.
	border.z_index = 1 if selected else 0


func _bounds(points: PackedVector2Array) -> Rect2:
	if points.is_empty():
		return Rect2(0.0, 0.0, 1.0, 1.0)
	var bounds: Rect2 = Rect2(points[0], Vector2.ZERO)
	for i: int in range(1, points.size()):
		bounds = bounds.expand(points[i])
	return bounds


func contains_point(point: Vector2) -> bool:
	return Geometry2D.is_point_in_polygon(point, polygon)


func select_from_ui() -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.region_selected.emit(region_id)
