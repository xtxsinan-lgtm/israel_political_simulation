class_name DiegeticDeskPropsController
extends HBoxContainer

const PROPS: Array[String] = [
	"红电话", "打字机", "收音机", "日历", "天平", "报价纸带", "档案袋",
]
const DRAWERS: Array[int] = [7, 3, 2, 0, 1, 4, 5]
## Second line of each prop button: the drawer it opens (same titles as DrawerContainerController)
## and its hotkey. Index 3 (日历) is rebuilt from the live speed by _calendar_text().
const FUNCTIONS: Array[String] = [
	"国防与情报 D7 · Ctrl+7", "内阁与政策 D3 · Ctrl+3", "议会与政党 D2 · Ctrl+2", "",
	"愿景与宪政 D1 · Ctrl+1", "经济与因果网 D4 · Ctrl+4", "外交与阿利亚 D5 · Ctrl+5",
]
const TOOLTIPS: Array[String] = [
	"拿起红电话：打开 D7 国防与情报抽屉，查看战备、威胁与情报（Ctrl+7）。",
	"敲打字机：打开 D3 内阁与政策抽屉，起草并提交政策法案（Ctrl+3）。",
	"打开收音机：打开 D2 议会与政党抽屉，收听议席与联盟动态（Ctrl+2）。",
	"翻日历：在 1–5 倍之间循环切换模拟速度，不会解除暂停（数字键 1–5，空格暂停）。",
	"看天平：打开 D1 愿景与宪政抽屉，查看执政愿景与宪政议题（Ctrl+1）。",
	"读报价纸带：打开 D4 经济与因果网抽屉，查看经济指标及其因果链（Ctrl+4）。",
	"翻档案袋：打开 D5 外交与阿利亚抽屉，处理外交关系与移民（Ctrl+5）。",
]
const CALENDAR_INDEX: int = 3
const PAPER: Color = Color(0.956863, 0.937255, 0.901961, 1.0)
const INK: Color = Color(0.117647, 0.109804, 0.101961, 1.0)
## Font colour of the prop whose drawer is open (flag blue #0038B8).
const ACTIVE: Color = Color(0.0, 0.219608, 0.721569, 1.0)

var buttons: Array[Button] = []
## Drawer currently open according to drawer_toggled (0 = none).
var active_drawer: int = 0
var speed_level: int = 1


func _ready() -> void:
	custom_minimum_size = Vector2(1440, 86)
	if not resized.is_connected(queue_redraw):
		resized.connect(queue_redraw)
	var state: SimState = _director_state()
	if state != null:
		speed_level = int(state.run.get("speed", 1))
	for i: int in range(PROPS.size()):
		var button: Button = Button.new()
		button.text = _label_text(i)
		button.tooltip_text = TOOLTIPS[i]
		button.add_theme_font_size_override("font_size", 14)
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(_toggle.bind(DRAWERS[i]))
		add_child(button)
		buttons.append(button)
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		if not bus.drawer_toggled.is_connected(_on_drawer_toggled):
			bus.drawer_toggled.connect(_on_drawer_toggled)
		if not bus.sim_speed_changed.is_connected(_on_speed_changed):
			bus.sim_speed_changed.connect(_on_speed_changed)
		if not bus.pause_state_changed.is_connected(_on_pause_state):
			bus.pause_state_changed.connect(_on_pause_state)


## "object name\nfunction · hotkey"; the calendar shows the current speed.
func _label_text(index: int) -> String:
	if index == CALENDAR_INDEX:
		return "%s\n%s" % [PROPS[index], _calendar_text()]
	return "%s\n%s" % [PROPS[index], FUNCTIONS[index]]


func _calendar_text() -> String:
	return "切换速度（当前 %d 倍）" % speed_level


func set_speed_label(level: int) -> void:
	speed_level = clampi(level, 1, 5)
	if buttons.size() > CALENDAR_INDEX:
		buttons[CALENDAR_INDEX].text = _label_text(CALENDAR_INDEX)


## Highlights the prop whose drawer is open (font colour #0038B8); 0 clears the highlight.
func set_active_drawer(drawer_index: int) -> void:
	active_drawer = drawer_index
	for i: int in range(buttons.size()):
		var button: Button = buttons[i]
		var is_active: bool = drawer_index != 0 and DRAWERS[i] == drawer_index
		if is_active:
			button.add_theme_color_override("font_color", ACTIVE)
			button.add_theme_color_override("font_hover_color", ACTIVE)
			button.add_theme_color_override("font_focus_color", ACTIVE)
			button.add_theme_color_override("font_pressed_color", ACTIVE)
		else:
			button.remove_theme_color_override("font_color")
			button.remove_theme_color_override("font_hover_color")
			button.remove_theme_color_override("font_focus_color")
			button.remove_theme_color_override("font_pressed_color")


## Prop button that is currently highlighted, or -1.
func active_button_index() -> int:
	for i: int in range(buttons.size()):
		if active_drawer != 0 and DRAWERS[i] == active_drawer:
			return i
	return -1


func _on_drawer_toggled(drawer_index: int) -> void:
	set_active_drawer(drawer_index)


func _on_speed_changed(new_speed: int) -> void:
	set_speed_label(new_speed)


func _on_pause_state(_is_paused: bool, level: int, _pause_reasons: PackedStringArray) -> void:
	set_speed_label(level)


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
