class_name EventModalController
extends Control

var modal_class: String = "major"
var title_label: Label
var body: RichTextLabel
var cards: VBoxContainer


func _ready() -> void:
	if title_label != null:
		return
	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", 18)
	body = RichTextLabel.new()
	body.bbcode_enabled = true
	cards = VBoxContainer.new()
	add_child(title_label)
	add_child(body)
	add_child(cards)


func present(event_data: Dictionary, state: SimState) -> void:
	if title_label == null:
		_ready()
	modal_class = String(event_data.get("modal_class", "major"))
	var stamp: String = "备忘录"
	match modal_class:
		"crisis":
			stamp = "TOP SECRET 加急电报"
		"newspaper":
			stamp = "国土报号外"
		"chain_milestone":
			stamp = "历史纪念卷宗"
		_:
			stamp = "内阁备忘录"
	title_label.text = "%s  %s" % [stamp, String(event_data.get("title", event_data.get("id", "")))]
	body.text = CodexAutoLinker.new().inject_codex_links(String(event_data.get("summary", "大转折正在发生。")))
	for child: Node in cards.get_children():
		child.queue_free()
	var previews: Array[Dictionary] = M12Events.new().evaluate_event_options_for_ui(String(event_data.get("id", "")), state)
	if previews.is_empty():
		previews.append({"id": "A", "available": true, "preview_l1": "维持现状", "lock_reasons": []})
	for i: int in range(previews.size()):
		var card: Label = Label.new()
		var row: Dictionary = previews[i]
		var reasons: String = ""
		var raw_reasons: Variant = row.get("lock_reasons", [])
		if typeof(raw_reasons) == TYPE_ARRAY and not (raw_reasons as Array).is_empty():
			reasons = String((raw_reasons as Array)[0])
		card.text = "%s  %s  %s" % [row.get("id", "A"), row.get("preview_l1", ""), reasons]
		card.add_theme_font_size_override("font_size", 14)
		cards.add_child(card)
