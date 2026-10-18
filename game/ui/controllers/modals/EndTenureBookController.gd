class_name EndTenureBookController
extends Control

var chapter_index: int = 0
var chapters: Array[Dictionary] = []
var page: Label


func _ready() -> void:
	if page != null:
		return
	page = Label.new()
	page.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(page)


func present(state: SimState) -> void:
	if page == null:
		_ready()
	var endings: M14Endings = M14Endings.new()
	var evaluation: Dictionary = endings.compute_final_evaluation(state)
	chapters = endings.build_epilogue_book(state, evaluation)
	chapter_index = 0
	_render(evaluation)


func next_page() -> void:
	if chapters.is_empty():
		return
	chapter_index = mini(chapter_index + 1, chapters.size() - 1)
	_render({})


func _render(evaluation: Dictionary) -> void:
	var letter: String = String(evaluation.get("letter", "C"))
	var chapter: Dictionary = {}
	if chapter_index < chapters.size():
		chapter = chapters[chapter_index]
	var cap: String = ""
	if bool(evaluation.get("redline_cap", false)):
		cap = "宪政越界：最高评级封顶于 B"
	page.text = "评级 %s %s\n第 %s 章 %s\n%s" % [
		letter, cap, chapter.get("chapter", 1), chapter.get("title", ""), chapter.get("body", ""),
	]
