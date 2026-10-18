class_name AlertOutlinerController
extends VBoxContainer

var bound_state: SimState = null


func _ready() -> void:
	custom_minimum_size = Vector2(240, 400)


func refresh(state: SimState) -> void:
	bound_state = state
	for child: Node in get_children():
		child.queue_free()
	var alerts: Array = []
	var raw: Variant = state.history.get("active_alerts", [])
	if typeof(raw) == TYPE_ARRAY:
		alerts = raw
	var header: Label = Label.new()
	header.text = "红 / 黄 / 蓝 预警"
	header.add_theme_font_size_override("font_size", 14)
	add_child(header)
	if alerts.is_empty():
		var quiet: Label = Label.new()
		quiet.text = "暂无激活预警"
		add_child(quiet)
		return
	for i: int in range(alerts.size()):
		var code: String = String(alerts[i])
		var button: Button = Button.new()
		button.text = _label(code)
		button.add_theme_font_size_override("font_size", 12)
		var drawer: int = _drawer_for(code)
		button.pressed.connect(_open_drawer.bind(drawer))
		add_child(button)


func _open_drawer(drawer_index: int) -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.drawer_toggled.emit(drawer_index)
	var router: DeskUiRouter = DeskUiRouter.current()
	if router != null:
		router.open_drawer(drawer_index)


func _label(code: String) -> String:
	if code.ends_with("_red"):
		return "红 " + code
	if code.ends_with("_yellow"):
		return "黄 " + code
	return "蓝 " + code


func _drawer_for(code: String) -> int:
	if code.contains("inflation") or code.contains("budget"):
		return 4
	if code.contains("coalition"):
		return 2
	if code.contains("security"):
		return 7
	return 1
