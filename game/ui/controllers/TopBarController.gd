class_name TopBarController
extends HBoxContainer

var slots: Array[Label] = []
var bound_state: SimState = null


func _ready() -> void:
	custom_minimum_size = Vector2(1920, 52)
	_ensure_slots()
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null and not bus.sim_day_advanced.is_connected(_on_snapshot):
		bus.sim_day_advanced.connect(_on_snapshot)


func _ensure_slots() -> void:
	if not slots.is_empty():
		return
	for i: int in range(9):
		var label: Label = Label.new()
		label.name = "Slot%d" % (i + 1)
		label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		label.add_theme_font_size_override("font_size", 14)
		label.text = "—"
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
	slots[3].text = "支持率 %.1f" % state.params.get_val("government_approval", "", state)
	var inflation: float = state.params.get_val("inflation", "", state)
	slots[4].text = "通胀 %.1f%%" % inflation
	slots[5].text = "外汇 %.1f" % state.params.get_val("fx_reserves", "", state)
	slots[6].text = "战备 %.1f" % state.params.get_val("idf_readiness", "", state)
	slots[7].text = "白宫 %.0f / 国会 %.0f" % [
		state.params.get_val("us_wh_warmth", "", state),
		state.params.get_val("us_cong_support", "", state),
	]
	var trilemma: String = "不可能三角"
	slots[8].text = "%s 账本L 百科C" % trilemma
	if inflation > 100.0:
		slots[4].add_theme_color_override("font_color", Color(0.722, 0.161, 0.184))


func texts_filled() -> bool:
	for i: int in range(slots.size()):
		if slots[i].text.strip_edges() == "":
			return false
	return slots.size() == 9


func _on_snapshot(snapshot: SimReadonlySnapshot) -> void:
	if bound_state == null:
		slots[0].text = snapshot.date
		return
	refresh(bound_state)
