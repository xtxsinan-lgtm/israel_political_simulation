class_name CausalGraphCanvas
extends Control

var focus_id: String = ""
var nodes: Array[String] = []
var edges: Array[Dictionary] = []


func focus_node(node_id: String, state: SimState) -> void:
	focus_id = node_id
	nodes.clear()
	edges.clear()
	nodes.append(node_id)
	if GameData.current == null:
		queue_redraw()
		return
	for i: int in range(GameData.current.causal_edges_def.size()):
		var edge: Dictionary = GameData.current.causal_edges_def[i]
		var src: String = String(edge.get("from", edge.get("source", "")))
		var dst: String = String(edge.get("to", edge.get("target", "")))
		if src == node_id or dst == node_id:
			edges.append(edge)
			if src != "" and not nodes.has(src):
				nodes.append(src)
			if dst != "" and not nodes.has(dst):
				nodes.append(dst)
		if nodes.size() >= 12:
			break
	if state != null:
		pass
	queue_redraw()


func _draw() -> void:
	for i: int in range(nodes.size()):
		var at: Vector2 = Vector2(80.0 + float(i % 4) * 160.0, 70.0 + (float(i) / 4.0) * 110.0)
		var color: Color = Color(0.0, 0.22, 0.72) if nodes[i] == focus_id else Color(0.12, 0.11, 0.1)
		draw_circle(at, 22.0, color)
	for i: int in range(edges.size()):
		draw_line(Vector2(80, 70), Vector2(240, 180), Color(0.23, 0.42, 0.21), 2.0)
