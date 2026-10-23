class_name TopBarController
extends HBoxContainer

const PAPER: Color = Color(0.956863, 0.937255, 0.901961, 1.0)
const INK: Color = Color(0.117647, 0.109804, 0.101961, 1.0)
const ALERT_RED: Color = Color(0.722, 0.161, 0.184)
## Parameter behind each slot (real ParameterStore ids); "" = no parameter (date / static text).
const SLOT_PARAMS: Array[String] = [
	"", "political_capital", "coalition_seats", "party_standing", "inflation",
	"fx_reserves", "readiness", "us_admin_relation", "",
]

var slots: Array[Label] = []
var bound_state: SimState = null


func _ready() -> void:
	custom_minimum_size = Vector2(1920, 52)
	_ensure_slots()
	if not resized.is_connected(queue_redraw):
		resized.connect(queue_redraw)
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null and not bus.sim_day_advanced.is_connected(_on_snapshot):
		bus.sim_day_advanced.connect(_on_snapshot)


## Paper strip behind the slots (the HBox itself draws nothing), ink rule along the bottom edge.
func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), PAPER, true)
	draw_line(Vector2(0.0, size.y - 0.5), Vector2(size.x, size.y - 0.5), INK, 1.0)


func _ensure_slots() -> void:
	if not slots.is_empty():
		return
	for i: int in range(9):
		var label: Label = Label.new()
		label.name = "Slot%d" % (i + 1)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		label.add_theme_font_size_override("font_size", 14)
		label.text = "—"
		var param: String = SLOT_PARAMS[i]
		if param != "":
			label.mouse_filter = Control.MOUSE_FILTER_STOP
			label.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
			label.gui_input.connect(_on_slot_input.bind(param))
		add_child(label)
		slots.append(label)


func refresh(state: SimState) -> void:
	bound_state = state
	_ensure_slots()
	var speed: int = int(state.run.get("speed", 1))
	var paused: bool = bool(state.run.get("paused", false))
	var pace: String = "暂停" if paused else "%d倍" % speed
	slots[0].text = "%s  第%d天  %s" % [state.clock.date, state.clock.day_index, pace]
	var pc: float = state.params.get_val("political_capital", "", state)
	slots[1].text = "政治资本 %.1f%s" % [pc, " 软顶" if pc > 92.0 else ""]
	var seats: float = state.params.get_val("coalition_seats", "", state)
	slots[2].text = "执政席位 %.0f / 120%s" % [seats, " 少数派" if seats < 61.0 else ""]
	slots[3].text = "支持率 %.1f" % state.params.get_val("party_standing", "", state)
	var inflation: float = state.params.get_val("inflation", "", state)
	slots[4].text = "通胀 %.1f%%" % inflation
	slots[5].text = "外汇 %.1f" % state.params.get_val("fx_reserves", "", state)
	slots[6].text = "战备 %.1f" % state.params.get_val("readiness", "", state)
	slots[7].text = "白宫 %.0f / 国会 %.0f" % [
		state.params.get_val("us_admin_relation", "", state),
		state.params.get_val("us_congress_relation", "", state),
	]
	var trilemma: String = "不可能三角"
	slots[8].text = "%s 账本L 百科C" % trilemma
	if inflation > 100.0:
		slots[4].add_theme_color_override("font_color", ALERT_RED)
	elif slots[4].has_theme_color_override("font_color"):
		slots[4].remove_theme_color_override("font_color")


func texts_filled() -> bool:
	for i: int in range(slots.size()):
		if slots[i].text.strip_edges() == "":
			return false
	return slots.size() == 9


## True while the inflation slot carries the red alert colour (G13: cleared again at <= 100).
func inflation_alert_active() -> bool:
	return slots.size() > 4 and slots[4].has_theme_color_override("font_color")


func _on_slot_input(event: InputEvent, param: String) -> void:
	if not (event is InputEventMouseButton):
		return
	var click: InputEventMouseButton = event as InputEventMouseButton
	if not click.pressed or click.button_index != MOUSE_BUTTON_LEFT:
		return
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.tooltip_requested.emit(param, "")


func _on_snapshot(snapshot: SimReadonlySnapshot) -> void:
	if bound_state == null:
		slots[0].text = snapshot.date
		return
	refresh(bound_state)
