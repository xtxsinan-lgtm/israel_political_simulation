class_name DiegeticDeskPropsController
extends HBoxContainer

const PROPS: Array[String] = [
	"红电话", "打字机", "收音机", "日历", "天平", "报价纸带", "档案袋",
]
const DRAWERS: Array[int] = [7, 3, 2, 0, 1, 4, 5]
const PAPER: Color = Color(0.956863, 0.937255, 0.901961, 1.0)
const INK: Color = Color(0.117647, 0.109804, 0.101961, 1.0)


func _ready() -> void:
	custom_minimum_size = Vector2(1440, 86)
	if not resized.is_connected(queue_redraw):
		resized.connect(queue_redraw)
	for i: int in range(PROPS.size()):
		var button: Button = Button.new()
		button.text = PROPS[i]
		button.add_theme_font_size_override("font_size", 14)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(_toggle.bind(DRAWERS[i]))
		add_child(button)


## Paper strip behind the prop buttons (the HBox itself draws nothing): #F4EFE6 with a 1px ink border.
func _draw() -> void:
	draw_rect(Rect2(Vector2.ZERO, size), PAPER, true)
	draw_rect(Rect2(Vector2(0.5, 0.5), size - Vector2(1.0, 1.0)), INK, false, 1.0)


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
	if drawer_index != 0:
		var router: DeskUiRouter = DeskUiRouter.current()
		if router != null:
			router.open_drawer(drawer_index)
		elif bus != null:
			bus.drawer_toggled.emit(drawer_index)
		return
	var state: SimState = _director_state()
	if state == null:
		return
	var speed: int = int(state.run.get("speed", 1))
	var next_speed: int = 1 if speed >= 5 else speed + 1
	var loop: MainLoop = Engine.get_main_loop()
	if loop is SceneTree and (loop as SceneTree).root.has_node("SimEngine"):
		(loop as SceneTree).root.get_node("SimEngine").call("set_speed", next_speed)
	elif bus != null:
		state.run["speed"] = next_speed
		bus.sim_speed_changed.emit(next_speed)
