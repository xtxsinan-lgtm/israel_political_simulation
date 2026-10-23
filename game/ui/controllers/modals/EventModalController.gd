class_name EventModalController
extends Control

const DEFAULT_BODY: String = "大转折正在发生。"

var modal_class: String = "major"
var title_label: Label
var body: RichTextLabel
var cards: VBoxContainer


func _ready() -> void:
	if title_label != null:
		return
	title_label = Label.new()
	title_label.add_theme_font_size_override("font_size", 18)
	title_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body = RichTextLabel.new()
	body.bbcode_enabled = true
	body.fit_content = true
	body.meta_clicked.connect(_on_meta)
	cards = VBoxContainer.new()
	var panel: PanelContainer = PanelContainer.new()
	panel.custom_minimum_size = custom_minimum_size
	var column: VBoxContainer = VBoxContainer.new()
	panel.add_child(column)
	column.add_child(title_label)
	column.add_child(body)
	column.add_child(cards)
	add_child(panel)


## Event text shown in the body: the payload summary, else the event definition's summary,
## else its background, else the old default sentence (pending events carry no text, G12).
static func event_text(event_data: Dictionary) -> String:
	var own: String = String(event_data.get("summary", "")).strip_edges()
	if own != "":
		return own
	var ev: Dictionary = event_definition(String(event_data.get("id", "")))
	var summary_text: String = String(ev.get("summary", "")).strip_edges()
	if summary_text != "":
		return summary_text
	var background: String = String(ev.get("background", "")).strip_edges()
	if background != "":
		return background
	return DEFAULT_BODY


static func event_definition(event_id: String) -> Dictionary:
	if event_id == "" or GameData.current == null or not GameData.current.events_def.has(event_id):
		return {}
	var raw: Variant = GameData.current.events_def[event_id]
	if typeof(raw) == TYPE_DICTIONARY:
		return raw
	return {}


## Option id -> {"title", "historical"} from the event definition (UI text only).
static func option_titles(event_id: String) -> Dictionary:
	var out: Dictionary = {}
	var raw: Variant = event_definition(event_id).get("options", [])
	if typeof(raw) != TYPE_ARRAY:
		return out
	var options: Array = raw
	for i: int in range(options.size()):
		if typeof(options[i]) != TYPE_DICTIONARY:
			continue
		var opt: Dictionary = options[i]
		var title: String = String(opt.get("title", opt.get("label", "")))
		out[String(opt.get("id", ""))] = {"title": title, "historical": bool(opt.get("historical", false))}
	return out


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
	var event_id: String = String(event_data.get("id", ""))
	var ev: Dictionary = event_definition(event_id)
	var title: String = String(event_data.get("title", ""))
	if title == "":
		title = String(ev.get("title", event_id))
	title_label.text = "%s  %s" % [stamp, title]
	body.text = CodexAutoLinker.new().inject_codex_links(event_text(event_data))
	for child: Node in cards.get_children():
		cards.remove_child(child)
		child.queue_free()
	var previews: Array[Dictionary] = M12Events.new().evaluate_event_options_for_ui(event_id, state)
	if previews.is_empty():
		previews.append({"id": "A", "available": true, "preview_l1": "维持现状", "lock_reasons": []})
	var titles: Dictionary = option_titles(event_id)
	for i: int in range(previews.size()):
		var card: Button = Button.new()
		var row: Dictionary = previews[i]
		var reasons: String = ""
		var raw_reasons: Variant = row.get("lock_reasons", [])
		if typeof(raw_reasons) == TYPE_ARRAY and not (raw_reasons as Array).is_empty():
			reasons = String((raw_reasons as Array)[0])
		var option_id: String = String(row.get("id", "A"))
		var preview: String = String(row.get("preview_l1", ""))
		if preview == "" and titles.has(option_id):
			var meta: Dictionary = titles[option_id]
			preview = String(meta.get("title", ""))
			if bool(meta.get("historical", false)):
				preview += " [史实]"
		card.text = "%s  %s  %s" % [option_id, preview, reasons]
		card.alignment = HORIZONTAL_ALIGNMENT_LEFT
		card.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
		card.add_theme_font_size_override("font_size", 14)
		card.disabled = not bool(row.get("available", true))
		card.pressed.connect(_choose.bind(event_id, option_id))
		cards.add_child(card)


## Text of option card `index` (for tests / onboarding), or "".
func option_text(index: int) -> String:
	if cards == null or index < 0 or index >= cards.get_child_count():
		return ""
	var card: Button = cards.get_child(index) as Button
	return card.text if card != null else ""


func _on_meta(meta: Variant) -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.codex_entry_requested.emit(String(meta))


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
