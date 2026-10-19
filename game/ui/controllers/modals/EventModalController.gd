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
	body.fit_content = true
	cards = VBoxContainer.new()
	var panel: PanelContainer = PanelContainer.new()
	panel.custom_minimum_size = custom_minimum_size
	var column: VBoxContainer = VBoxContainer.new()
	panel.add_child(column)
	column.add_child(title_label)
	column.add_child(body)
	column.add_child(cards)
	add_child(panel)


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
	var event_id: String = String(event_data.get("id", ""))
	for i: int in range(previews.size()):
		var card: Button = Button.new()
		var row: Dictionary = previews[i]
		var reasons: String = ""
		var raw_reasons: Variant = row.get("lock_reasons", [])
		if typeof(raw_reasons) == TYPE_ARRAY and not (raw_reasons as Array).is_empty():
			reasons = String((raw_reasons as Array)[0])
		var option_id: String = String(row.get("id", "A"))
		card.text = "%s  %s  %s" % [option_id, row.get("preview_l1", ""), reasons]
		card.add_theme_font_size_override("font_size", 14)
		card.disabled = not bool(row.get("available", true))
		card.pressed.connect(_choose.bind(event_id, option_id))
		cards.add_child(card)


func _choose(event_id: String, option_id: String) -> void:
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree) or not (loop as SceneTree).root.has_node("SimEngine"):
		return
	var engine: Node = (loop as SceneTree).root.get_node("SimEngine")
	var err: int = int(engine.call("submit_command", {"op": "resolve_event", "event": event_id, "option": option_id}))
	if err != OK:
		push_warning("resolve_event %s/%s failed: %s" % [event_id, option_id, error_string(err)])
		return
	var snap_v: Variant = engine.call("get_snapshot")
	var director_v: Variant = engine.get("director")
	if snap_v is SimReadonlySnapshot and director_v is SimDirector:
		var snap: SimReadonlySnapshot = snap_v
		if not snap.pending_events.is_empty():
			present(snap.pending_events[0], (director_v as SimDirector).state)
			return
	visible = false
