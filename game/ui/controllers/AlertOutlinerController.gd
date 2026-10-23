class_name AlertOutlinerController
extends VBoxContainer

const PAPER: Color = Color(0.956863, 0.937255, 0.901961, 1.0)
const INK: Color = Color(0.117647, 0.109804, 0.101961, 1.0)

var bound_state: SimState = null


func _ready() -> void:
	custom_minimum_size = Vector2(240, 400)
	if not resized.is_connected(queue_redraw):
		resized.connect(queue_redraw)


## Paper panel behind the alert list (the VBox itself draws nothing): #F4EFE6 with a 1px ink border.
func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), PAPER, true)
	draw_rect(Rect2(Vector2(0.5, 0.5), size - Vector2(1.0, 1.0)), INK, false, 1.0)


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
