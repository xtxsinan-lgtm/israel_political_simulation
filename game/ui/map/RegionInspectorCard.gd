class_name RegionInspectorCard
extends PanelContainer

var region_id: String = ""
var bound_state: SimState = null
var title_label: Label
var body_label: Label
var absorption: HSlider
var investment: HSlider
var posture: OptionButton
var preview_label: Label


func _ready() -> void:
	_ensure_widgets()


func _ensure_widgets() -> void:
	if title_label != null:
		return
	var box: VBoxContainer = VBoxContainer.new()
	add_child(box)
	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", 18)
	body_label = Label.new()
	body_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	preview_label = Label.new()
	absorption = _slider("阿利亚安置优先级")
	investment = _slider("基建投资优先级")
	posture = OptionButton.new()
	posture.add_item("缓和", 0)
	posture.add_item("常规", 1)
	posture.add_item("高压", 2)
	posture.item_selected.connect(_on_posture)
	box.add_child(title_label)
	box.add_child(body_label)
	box.add_child(absorption)
	box.add_child(investment)
	box.add_child(posture)
	box.add_child(preview_label)
	visible = false


func present(next_region: String, state: SimState) -> void:
	_ensure_widgets()
	region_id = next_region
	bound_state = state
	visible = true
	var src: Dictionary = {}
	if GameData.current != null:
		src = _dict(GameData.current.regions_def.get(next_region, {}))
	title_label.text = "%s  %s" % [String(src.get("name_zh", next_region)), String(src.get("name_en", next_region))]
	var security: float = _metric("region_security", src)
	var development: float = _metric("region_development", src)
	var alienation: float = _metric("region_alienation", src)
	body_label.text = "法律地位 %s\n治安 %.1f  发展 %.1f  离异 %.1f" % [
		String(src.get("legal_status", "sovereign")), security, development, alienation,
	]
	absorption.set_value_no_signal(_metric("region_absorption_priority", src))
	investment.set_value_no_signal(_metric("region_investment_priority", src))


func _metric(param_id: String, src: Dictionary) -> float:
	if bound_state != null:
		return bound_state.params.get_val(param_id, region_id, bound_state)
	return float(src.get(param_id, 0.0))


func _slider(caption: String) -> HSlider:
	var slider: HSlider = HSlider.new()
	slider.min_value = 0.0
	slider.max_value = 100.0
	slider.step = 1.0
	slider.tooltip_text = caption
	slider.value_changed.connect(_on_slider.bind(caption))
	return slider


func _on_slider(value: float, caption: String) -> void:
	var param_id: String = "region_absorption_priority" if caption.contains("阿利亚") else "region_investment_priority"
	_submit(param_id, value)


func _on_posture(index: int) -> void:
	_submit("region_security_posture", float(index))


func _submit(param_id: String, value: float) -> void:
	var cmd: Dictionary = {"op": "set_region_priority", "region": region_id, "param": param_id, "value": value}
	var loop: MainLoop = Engine.get_main_loop()
	if loop is SceneTree and (loop as SceneTree).root.has_node("SimEngine"):
		(loop as SceneTree).root.get_node("SimEngine").call("submit_command", cmd)
	elif bound_state != null:
		bound_state.params.set_val(param_id, region_id, value, bound_state)
	if bound_state != null:
		var expr: ExprEngine = ExprEngine.new()
		expr.bind(bound_state)
		var preview: Dictionary = PreviewEngine.preview_effects_on_three_layers(bound_state, [{
			"op": "add", "target": param_id, "key": region_id, "value": value,
		}], expr)
		preview_label.text = "预览 L1/L2/L3 %s" % preview.keys().size()


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
