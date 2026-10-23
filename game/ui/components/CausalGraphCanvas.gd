class_name CausalGraphCanvas
extends Control

const GRAPH_W: float = 640.0
const GRAPH_H: float = 340.0
const NODE_R: float = 22.0
const MAX_NODES: int = 12
const FOCUS_BLUE: Color = Color(0.0, 0.22, 0.72)
const NODE_INK: Color = Color(0.12, 0.11, 0.1)
const EDGE_GREEN: Color = Color(0.23, 0.42, 0.21)
const LABEL_BG: Color = Color(0.956863, 0.937255, 0.901961, 0.9)

var focus_id: String = ""
var nodes: Array[String] = []
## One entry per real causal edge touching the focus: {"src", "dst", "label"} (ids without "param:").
var edges: Array[Dictionary] = []


func _init() -> void:
	custom_minimum_size = Vector2(GRAPH_W, GRAPH_H)
	mouse_filter = Control.MOUSE_FILTER_STOP


## "param:inflation" -> "inflation" (causal_edges.json prefixes param sources).
static func norm_id(raw: String) -> String:
	if raw.begins_with("param:"):
		return raw.substr(6)
	return raw


func focus_node(node_id: String, _state: SimState) -> void:
	focus_id = node_id
	nodes.clear()
	edges.clear()
	nodes.append(node_id)
	if GameData.current == null:
		queue_redraw()
		return
	for i: int in range(GameData.current.causal_edges_def.size()):
		var edge: Dictionary = GameData.current.causal_edges_def[i]
		var src: String = norm_id(String(edge.get("from", edge.get("source", ""))))
		var dst: String = norm_id(String(edge.get("to", edge.get("target", ""))))
		if src == node_id or dst == node_id:
			edges.append({"src": src, "dst": dst, "label": String(edge.get("label_zh", edge.get("id", "")))})
			if src != "" and not nodes.has(src):
				nodes.append(src)
			if dst != "" and not nodes.has(dst):
				nodes.append(dst)
		if nodes.size() >= MAX_NODES:
			break
	queue_redraw()


## Node i sits on a 4-column grid (integer row index).
func node_position(index: int) -> Vector2:
	var column: int = index % 4
	var row: int = int(floor(float(index) / 4.0))
	return Vector2(80.0 + float(column) * 160.0, 70.0 + float(row) * 110.0)


## Index of the node under `at` (local coordinates), or -1.
func node_at(at: Vector2) -> int:
	for i: int in range(nodes.size()):
		if at.distance_to(node_position(i)) <= NODE_R:
			return i
	return -1


func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var click: InputEventMouseButton = event as InputEventMouseButton
	if not click.pressed or click.button_index != MOUSE_BUTTON_LEFT:
		return
	var hit: int = node_at(click.position)
	if hit < 0:
		return
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.tooltip_requested.emit(nodes[hit], "")
	accept_event()


func _draw() -> void:
	# Edges first so the nodes and their labels stay legible on top.
	for i: int in range(edges.size()):
		var a: int = nodes.find(String(edges[i].get("src", "")))
		var b: int = nodes.find(String(edges[i].get("dst", "")))
		if a < 0 or b < 0:
			continue
		if a == b:
			_draw_loop(node_position(a))
		else:
			_draw_arrow(node_position(a), node_position(b))
	var font: Font = get_theme_default_font()
	var font_size: int = 12
	for i: int in range(nodes.size()):
		var at: Vector2 = node_position(i)
		var color: Color = FOCUS_BLUE if nodes[i] == focus_id else NODE_INK
		draw_circle(at, NODE_R, color)
		if font == null:
			continue
		var text_size: Vector2 = font.get_string_size(nodes[i], HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size)
		var box: Rect2 = Rect2(at.x - text_size.x * 0.5 - 3.0, at.y + NODE_R + 2.0, text_size.x + 6.0, text_size.y)
		draw_rect(box, LABEL_BG, true)
		draw_string(font, Vector2(box.position.x + 3.0, box.position.y + font.get_ascent(font_size)), nodes[i], HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size, NODE_INK)


## Curved arrow from rim to rim (A->B and B->A bow to opposite sides, so both stay visible).
func _draw_arrow(from_at: Vector2, to_at: Vector2) -> void:
	var delta: Vector2 = to_at - from_at
	var length: float = maxf(delta.length(), 1.0)
	var normal: Vector2 = Vector2(-delta.y / length, delta.x / length)
	var bend: float = minf(70.0, 14.0 + length * 0.12)
	var control: Vector2 = (from_at + to_at) * 0.5 + normal * bend
	var start: Vector2 = from_at + (control - from_at).normalized() * NODE_R
	var finish: Vector2 = to_at + (control - to_at).normalized() * (NODE_R + 1.0)
	var points: PackedVector2Array = PackedVector2Array()
	for step: int in range(17):
		var t: float = float(step) / 16.0
		var u: float = 1.0 - t
		points.append(start * (u * u) + control * (2.0 * u * t) + finish * (t * t))
	draw_polyline(points, EDGE_GREEN, 2.0, true)
	_draw_head(finish, (finish - control).angle())


func _draw_loop(at: Vector2) -> void:
	var center: Vector2 = at + Vector2(NODE_R * 0.9, -NODE_R * 0.9)
	draw_arc(center, 11.0, PI * 0.75, PI * 2.25 + 0.4, 16, EDGE_GREEN, 2.0, true)
	var tip: Vector2 = center + Vector2(cos(PI * 0.25 + 0.4), sin(PI * 0.25 + 0.4)) * 11.0
	_draw_head(tip, PI * 0.75 + 0.4)


func _draw_head(tip: Vector2, angle: float) -> void:
	var head: float = 8.0
	var left: Vector2 = tip - Vector2(cos(angle - 0.45), sin(angle - 0.45)) * head
	var right: Vector2 = tip - Vector2(cos(angle + 0.45), sin(angle + 0.45)) * head
	draw_colored_polygon(PackedVector2Array([tip, left, right]), EDGE_GREEN)
