class_name DiegeticDeskPropsController
extends HBoxContainer

const PROPS: Array[String] = [
	"红电话", "打字机", "收音机", "日历", "天平", "报价纸带", "档案袋",
]
const DRAWERS: Array[int] = [7, 3, 2, 0, 1, 4, 5]


func _ready() -> void:
	custom_minimum_size = Vector2(1440, 86)
	for i: int in range(PROPS.size()):
		var button: Button = Button.new()
		button.text = PROPS[i]
		button.add_theme_font_size_override("font_size", 14)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(_toggle.bind(DRAWERS[i]))
		add_child(button)


func _director_state() -> SimState:
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree):
		return null
	if not (loop as SceneTree).root.has_node("SimEngine"):
		return null
	var director: Variant = (loop as SceneTree).root.get_node("SimEngine").get("director")
	if director is SimDirector:
		return (director as SimDirector).state
	return null


func _toggle(drawer_index: int) -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.drawer_toggled.emit(drawer_index)
	var state: SimState = _director_state()
	if drawer_index == 0 and state != null and bus != null:
		var speed: int = int(state.run.get("speed", 1))
		state.run["speed"] = 1 if speed >= 3 else speed + 1
		bus.sim_speed_changed.emit(int(state.run["speed"]))
