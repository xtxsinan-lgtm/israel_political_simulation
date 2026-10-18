class_name CausalTooltipManager
extends Control

var locked: Array[String] = []
var sparkline: SparklineDrawer
var body: Label
var hover_seconds: float = 0.35


func _ready() -> void:
	_ensure_widgets()


func _ensure_widgets() -> void:
	if body != null:
		return
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	sparkline = SparklineDrawer.new()
	sparkline.custom_minimum_size = Vector2(220, 48)
	body = Label.new()
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var box: VBoxContainer = VBoxContainer.new()
	add_child(box)
	box.add_child(body)
	box.add_child(sparkline)
	visible = false


func lock_tooltip(tooltip_id: String) -> bool:
	_ensure_widgets()
	if locked.size() >= 3:
		return false
	if locked.has(tooltip_id):
		return true
	locked.append(tooltip_id)
	visible = true
	body.text = "锁定 %d/3  %s" % [locked.size(), tooltip_id]
	_emit_lock(tooltip_id, true)
	return true


func handle_escape() -> bool:
	if locked.is_empty():
		visible = false
		return false
	var tooltip_id: String = locked.pop_back()
	_emit_lock(tooltip_id, false)
	visible = not locked.is_empty()
	if visible:
		body.text = "锁定 %d/3  %s" % [locked.size(), locked[locked.size() - 1]]
	return true


func explain_node(state: SimState, node_id: String) -> Dictionary:
	_ensure_widgets()
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(state)
	var net: CausalNet = CausalNet.new()
	var explained: Dictionary = net.explain(state, node_id, "", expr, {}, 5)
	var history: PackedFloat64Array = PackedFloat64Array()
	var ring: Variant = state.history.get("daily_ring", [])
	if typeof(ring) == TYPE_ARRAY:
		var rows: Array = ring
		var start: int = maxi(0, rows.size() - 30)
		for i: int in range(start, rows.size()):
			if typeof(rows[i]) == TYPE_DICTIONARY:
				history.append(float((rows[i] as Dictionary).get("public_security", 0.0)))
	sparkline.set_series(history, 35.0)
	var lines: PackedStringArray = PackedStringArray()
	lines.append("%s = %.2f" % [node_id, state.params.get_val(node_id, "", state)])
	var top: Array = _array(explained.get("top_contributions", []))
	for i: int in range(mini(5, top.size())):
		var row: Dictionary = top[i] if typeof(top[i]) == TYPE_DICTIONARY else {}
		lines.append("%s %+0.2f" % [String(row.get("source_label_zh", row.get("source_id", ""))), float(row.get("delta_per_tick", 0.0))])
	body.text = "\n".join(lines)
	visible = true
	return explained


func preview_action(state: SimState, effects: Array) -> Dictionary:
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(state)
	var preview: Dictionary = PreviewEngine.preview_effects_on_three_layers(state, effects, expr)
	body.text = "L1 直接代价\nL2 下游区间\nL3 阈值预警\n%s" % preview.keys()
	visible = true
	return preview


func _emit_lock(tooltip_id: String, is_locked: bool) -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.tooltip_lock_toggled.emit(tooltip_id, is_locked)


func _array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
