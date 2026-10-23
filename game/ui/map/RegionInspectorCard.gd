class_name RegionInspectorCard
extends PanelContainer

const METRICS: Array[String] = ["region_security", "region_development", "region_alienation"]
const METRIC_NAMES: Array[String] = ["治安", "发展", "离异"]
## Security posture OptionButton index 0/1/2 (缓和/常规/高压) -> 0–100 parameter value.
const POSTURE_VALUES: Array[float] = [20.0, 50.0, 80.0]

var region_id: String = ""
var bound_state: SimState = null
var title_label: Label
var body_label: Label
var metric_buttons: Array[Button] = []
var close_button: Button
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
	var head: HBoxContainer = HBoxContainer.new()
	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", 18)
	title_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	close_button = Button.new()
	close_button.text = "×"
	close_button.flat = true
	close_button.tooltip_text = "关闭"
	close_button.pressed.connect(close_card)
	head.add_child(title_label)
	head.add_child(close_button)
	body_label = Label.new()
	body_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var metrics_row: HBoxContainer = HBoxContainer.new()
	metric_buttons.clear()
	for i: int in range(METRICS.size()):
		var metric_button: Button = Button.new()
		metric_button.flat = true
		metric_button.tooltip_text = METRICS[i]
		metric_button.pressed.connect(_on_metric_pressed.bind(METRICS[i]))
		metrics_row.add_child(metric_button)
		metric_buttons.append(metric_button)
	preview_label = Label.new()
	absorption = _slider("阿利亚安置优先级")
	investment = _slider("基建投资优先级")
	posture = OptionButton.new()
	posture.add_item("缓和", 0)
	posture.add_item("常规", 1)
	posture.add_item("高压", 2)
	posture.item_selected.connect(_on_posture)
	box.add_child(head)
	box.add_child(body_label)
	box.add_child(metrics_row)
	box.add_child(absorption)
	box.add_child(investment)
	box.add_child(posture)
	box.add_child(preview_label)
	visible = false


## Shows the card for `next_region`; an empty id (click on empty map) hides it.
func present(next_region: String, state: SimState) -> void:
	_ensure_widgets()
	if next_region == "":
		close_card()
		return
	if next_region != region_id:
		preview_label.text = ""
	region_id = next_region
	if state != null:
		bound_state = state
	visible = true
	_render()


## Keeps the numbers live while the card is open.
func refresh(state: SimState) -> void:
	if state == null:
		return
	bound_state = state
	if visible and region_id != "":
		_render()


func close_card() -> void:
	visible = false
	region_id = ""


func _render() -> void:
	var src: Dictionary = {}
	if GameData.current != null:
		src = _dict(GameData.current.regions_def.get(region_id, {}))
	title_label.text = "%s  %s" % [String(src.get("name_zh", region_id)), String(src.get("name_en", region_id))]
	body_label.text = "法律地位 %s" % String(src.get("legal_status", "sovereign"))
	for i: int in range(metric_buttons.size()):
		metric_buttons[i].text = "%s %.1f" % [METRIC_NAMES[i], _metric(METRICS[i], src)]
	absorption.set_value_no_signal(_metric("region_absorption_priority", src))
	investment.set_value_no_signal(_metric("region_investment_priority", src))
	posture.select(posture_index(_metric("region_security_posture", src)))


static func posture_index(value: float) -> int:
	if value < 35.0:
		return 0
	if value < 65.0:
		return 1
	return 2


func _metric(param_id: String, src: Dictionary) -> float:
	if bound_state != null:
		return bound_state.params.get_val(param_id, region_id, bound_state)
	return float(src.get(param_id, 0.0))


func _on_metric_pressed(param_id: String) -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null and region_id != "":
		bus.tooltip_requested.emit(param_id, region_id)


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
	_submit("region_security_posture", POSTURE_VALUES[clampi(index, 0, POSTURE_VALUES.size() - 1)])


func _submit(param_id: String, value: float) -> void:
	if region_id == "":
		return
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
