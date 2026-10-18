class_name CodexController
extends Control

var linker: CodexAutoLinker = CodexAutoLinker.new()
var body: RichTextLabel
var query: String = ""


func _ready() -> void:
	if body != null:
		return
	body = RichTextLabel.new()
	body.bbcode_enabled = true
	body.custom_minimum_size = Vector2(640, 480)
	body.meta_clicked.connect(_on_meta)
	add_child(body)
	show_entry("mahapach")


func show_entry(entry_id: String) -> void:
	if body == null:
		_ready()
	var text: String = "大转折之后，议会席位按巴德尔-奥弗法分配。"
	body.text = linker.inject_codex_links(text)
	query = entry_id


func filter_entries(needle: String) -> Array[String]:
	var found: Array[String] = []
	for i: int in range(linker.terms.size()):
		var title: String = String(linker.terms[i].get("title", ""))
		if needle == "" or title.contains(needle):
			found.append(String(linker.terms[i].get("id", "")))
	return found


func _on_meta(meta: Variant) -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.codex_entry_requested.emit(String(meta))
