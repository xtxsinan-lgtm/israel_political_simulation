class_name EndTenureBookController
extends Control

var chapter_index: int = 0
var chapters: Array[Dictionary] = []
var page: Label
var footer: Label
## Final evaluation from the first compute; every page re-renders with it (keeps the real grade).
var evaluation: Dictionary = {}


func _ready() -> void:
	if page != null:
		return
	mouse_filter = Control.MOUSE_FILTER_STOP
	var panel: PanelContainer = PanelContainer.new()
	panel.custom_minimum_size = custom_minimum_size
	panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var column: VBoxContainer = VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	panel.add_child(column)
	page = Label.new()
	page.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	page.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(page)
	footer = Label.new()
	column.add_child(footer)
	add_child(panel)


func present(state: SimState) -> void:
	if page == null:
		_ready()
	var endings: M14Endings = M14Endings.new()
	evaluation = endings.compute_final_evaluation(state)
	chapters = endings.build_epilogue_book(state, evaluation)
	chapter_index = 0
	_render(evaluation)


func next_page() -> void:
	if chapters.is_empty():
		return
	chapter_index = mini(chapter_index + 1, chapters.size() - 1)
	_render(evaluation)


## Click anywhere on the book turns the page (G11).
func _gui_input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton):
		return
	var click: InputEventMouseButton = event as InputEventMouseButton
	if click.pressed and click.button_index == MOUSE_BUTTON_LEFT:
		next_page()
		accept_event()


## → (ui_right) turns the page while the book is open.
func _unhandled_input(event: InputEvent) -> void:
	if not is_visible_in_tree() or chapters.is_empty():
		return
	if event.is_action_pressed("ui_right", false):
		next_page()
		get_viewport().set_input_as_handled()


func _render(eval_data: Dictionary) -> void:
	if page == null:
		_ready()
	var letter: String = String(eval_data.get("letter", "C"))
	var chapter: Dictionary = {}
	if chapter_index < chapters.size():
		chapter = chapters[chapter_index]
	var cap: String = ""
	if bool(eval_data.get("redline_cap", false)):
		cap = "宪政越界：最高评级封顶于 B"
	page.text = "评级 %s %s\n第 %s 章 %s\n%s" % [
		letter, cap, chapter.get("chapter", 1), chapter.get("title", ""), chapter.get("body", ""),
	]
	footer.text = "%d / %d   点击或按 → 翻页" % [chapter_index + 1, maxi(chapters.size(), 1)]
