class_name DrawerContainerController
extends Control

const DRAWER_WIDTH: int = 920
## Local y of the panel: tab row (12px Button + 4+4 content margins ≈ 25px) + one 4px box separation.
const PANEL_TOP: float = 29.0
## Local y of the panel bottom (screen y 852 with the container at y 52).
const PANEL_BOTTOM: float = 800.0
const FADE_SECONDS: float = 0.18
const DRAWER_SCENES: PackedStringArray = PackedStringArray([
	"res://ui/scenes/drawers/D1_GoalsDrawer.tscn",
	"res://ui/scenes/drawers/D2_KnessetDrawer.tscn",
	"res://ui/scenes/drawers/D3_CabinetDrawer.tscn",
	"res://ui/scenes/drawers/D4_EconomyDrawer.tscn",
	"res://ui/scenes/drawers/D5_DiplomacyDrawer.tscn",
	"res://ui/scenes/drawers/D6_PalestiniansDrawer.tscn",
	"res://ui/scenes/drawers/D7_MilitaryIntelDrawer.tscn",
])
var titles: PackedStringArray = PackedStringArray([
	"D1 愿景与宪政", "D2 议会与政党", "D3 内阁与政策", "D4 经济与因果网",
	"D5 外交与阿利亚", "D6 巴勒斯坦事务", "D7 国防与情报",
])

var open_index: int = 0
var panel: Control
## Drawer title label (first row of the open panel).
var body: Label
var column: VBoxContainer
## Drawer index (1..7) -> instanced D*_Drawer root, built lazily on first open.
var drawer_nodes: Dictionary = {}
var fade: Tween = null


func _ready() -> void:
	if panel != null:
		return
	custom_minimum_size = Vector2(float(DRAWER_WIDTH), 900)
	# The container rect itself never takes the mouse: only the tabs and the open panel do (G7).
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	var tabs: HBoxContainer = HBoxContainer.new()
	tabs.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(tabs)
	for i: int in range(titles.size()):
		var button: Button = Button.new()
		button.text = titles[i]
		button.add_theme_font_size_override("font_size", 12)
		button.pressed.connect(toggle_drawer.bind(i + 1))
		tabs.add_child(button)
	var box: PanelContainer = PanelContainer.new()
	box.mouse_filter = Control.MOUSE_FILTER_STOP
	box.position = Vector2(0.0, PANEL_TOP)
	box.custom_minimum_size = Vector2(float(DRAWER_WIDTH), PANEL_BOTTOM - PANEL_TOP)
	box.size = box.custom_minimum_size
	box.visible = false
	panel = box
	column = VBoxContainer.new()
	box.add_child(column)
	body = Label.new()
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_font_size_override("font_size", 18)
	column.add_child(body)
	add_child(panel)
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		if not bus.sim_day_advanced.is_connected(_on_day):
			bus.sim_day_advanced.connect(_on_day)
		if not bus.snapshot_updated.is_connected(_on_snapshot_updated):
			bus.snapshot_updated.connect(_on_snapshot_updated)


func toggle_drawer(index: int) -> void:
	if panel == null:
		_ready()
	if fade != null and fade.is_valid():
		fade.kill()
	fade = null
	if open_index == index:
		open_index = 0
		if is_inside_tree():
			fade = create_tween()
			fade.tween_property(panel, "modulate:a", 0.0, FADE_SECONDS)
			fade.finished.connect(_hide_panel)
		else:
			panel.visible = false
	else:
		open_index = index
		panel.visible = true
		panel.modulate.a = 1.0
		body.text = titles[index - 1]
		_show_drawer(index)
		refresh_open(_director_state())
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.drawer_toggled.emit(open_index)
	var router: DeskUiRouter = DeskUiRouter.current()
	if router != null:
		router.drawer_index = open_index


func visible_drawers_count() -> int:
	return 0 if open_index == 0 else 1


## The instanced drawer scene for `index` (1..7), or null if it is not built yet.
func drawer_node(index: int) -> Control:
	if drawer_nodes.has(index):
		return drawer_nodes[index] as Control
	return null


## Re-reads the live game into the open drawer (called on open and every sim day).
func refresh_open(state: SimState) -> void:
	if state == null or open_index == 0:
		return
	var node: Control = drawer_node(open_index)
	if node != null and node.has_method("refresh"):
		node.call("refresh", state)


func _show_drawer(index: int) -> void:
	if not drawer_nodes.has(index) and index >= 1 and index <= DRAWER_SCENES.size():
		var packed: PackedScene = load(DRAWER_SCENES[index - 1]) as PackedScene
		if packed != null:
			var made: Control = packed.instantiate() as Control
			if made != null:
				made.size_flags_horizontal = Control.SIZE_EXPAND_FILL
				made.size_flags_vertical = Control.SIZE_EXPAND_FILL
				column.add_child(made)
				drawer_nodes[index] = made
	for key: Variant in drawer_nodes.keys():
		var node: Control = drawer_nodes[key] as Control
		if node != null:
			node.visible = int(key) == index


func _hide_panel() -> void:
	fade = null
	if open_index == 0:
		panel.visible = false


func _on_day(_snapshot: SimReadonlySnapshot) -> void:
	refresh_open(_director_state())


func _on_snapshot_updated(_snapshot: Variant) -> void:
	refresh_open(_director_state())


func _director_state() -> SimState:
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree) or not (loop as SceneTree).root.has_node("SimEngine"):
		return null
	var director: Variant = (loop as SceneTree).root.get_node("SimEngine").get("director")
	if director is SimDirector:
		return (director as SimDirector).state
	return null
