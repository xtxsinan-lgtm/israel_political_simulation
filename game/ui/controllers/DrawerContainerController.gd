class_name DrawerContainerController
extends Control

const DRAWER_WIDTH: int = 920
var titles: PackedStringArray = PackedStringArray([
	"D1 愿景与宪政", "D2 议会与政党", "D3 内阁与政策", "D4 经济与因果网",
	"D5 外交与阿利亚", "D6 巴勒斯坦事务", "D7 国防与情报",
])

var open_index: int = 0
var panel: Control
var body: Label


func _ready() -> void:
	if panel != null:
		return
	custom_minimum_size = Vector2(float(DRAWER_WIDTH), 900)
	var tabs: HBoxContainer = HBoxContainer.new()
	add_child(tabs)
	for i: int in range(titles.size()):
		var button: Button = Button.new()
		button.text = titles[i]
		button.add_theme_font_size_override("font_size", 12)
		button.pressed.connect(toggle_drawer.bind(i + 1))
		tabs.add_child(button)
	panel = PanelContainer.new()
	panel.custom_minimum_size = Vector2(float(DRAWER_WIDTH), 800)
	panel.visible = false
	body = Label.new()
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	panel.add_child(body)
	add_child(panel)


func toggle_drawer(index: int) -> void:
	if open_index == index:
		open_index = 0
		if is_inside_tree():
			var tween: Tween = create_tween()
			tween.tween_property(panel, "modulate:a", 0.0, 0.18)
			tween.finished.connect(_hide_panel)
		else:
			panel.visible = false
	else:
		open_index = index
		panel.visible = true
		panel.modulate.a = 1.0
		body.text = titles[index - 1]
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.drawer_toggled.emit(open_index)
	var router: DeskUiRouter = DeskUiRouter.current()
	if router != null:
		router.drawer_index = open_index


func visible_drawers_count() -> int:
	return 0 if open_index == 0 else 1


func _hide_panel() -> void:
	if open_index == 0:
		panel.visible = false
