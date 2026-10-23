class_name D3CabinetController
extends Control

var summary: Label
var status: Label
var action_list: VBoxContainer
var minister_proposals: Array[Dictionary] = []
var active_policies: Array[String] = []
## Action id -> its execute Button (built once, re-labelled / re-enabled on every refresh).
var action_buttons: Dictionary = {}
var bound_state: SimState = null


func _ready() -> void:
	if summary != null:
		return
	var layout: VBoxContainer = VBoxContainer.new()
	add_child(layout)
	layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	summary = Label.new()
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	layout.add_child(summary)
	status = Label.new()
	status.add_theme_font_size_override("font_size", 13)
	layout.add_child(status)
	var scroll: ScrollContainer = ScrollContainer.new()
	scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	layout.add_child(scroll)
	action_list = VBoxContainer.new()
	action_list.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	scroll.add_child(action_list)


func refresh(state: SimState) -> void:
	if summary == null:
		_ready()
	bound_state = state
	minister_proposals.clear()
	active_policies.clear()
	var offices: Dictionary = _dict(_dict(state.modules.get("M06", {})).get("offices", {}))
	if offices.is_empty():
		offices = state.offices
	var ids: Array[String] = SimMath.sorted_keys(offices)
	for i: int in range(mini(6, ids.size())):
		minister_proposals.append({
			"office": ids[i],
			"holder": String(offices[ids[i]]),
			"discount": 0.30,
		})
	if GameData.current != null:
		var policies: Array[String] = SimMath.sorted_keys(GameData.current.policies_def)
		for i: int in range(mini(76, policies.size())):
			active_policies.append(policies[i])
	summary.text = "部长提案 %d（批准可享 30%% 政治资本折扣）\n政策 %d" % [minister_proposals.size(), active_policies.size()]
	_refresh_actions(state)


## Number of action buttons currently enabled (player can submit them today).
func available_action_count() -> int:
	var count: int = 0
	for key: Variant in action_buttons.keys():
		var button: Button = action_buttons[key] as Button
		if button != null and not button.disabled:
			count += 1
	return count


func _refresh_actions(state: SimState) -> void:
	if GameData.current == null:
		return
	var m05: Dictionary = _dict(state.modules.get("M05", {}))
	var busy: Dictionary = {}
	for list_key: String in ["active_actions", "staged_actions"]:
		var raw: Variant = m05.get(list_key, [])
		if typeof(raw) == TYPE_ARRAY:
			var entries: Array = raw
			for j: int in range(entries.size()):
				busy[String(_dict(entries[j]).get("id", ""))] = true
	var cooldowns: Dictionary = _dict(m05.get("action_cooldowns", {}))
	var unlocked: Dictionary = _dict(m05.get("unlocked_actions", {}))
	var day: int = state.clock.day_index
	var year: int = state.clock.y
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.actions_def)
	for i: int in range(ids.size()):
		var action_id: String = ids[i]
		var action_def: Dictionary = _dict(GameData.current.actions_def[action_id])
		var button: Button = null
		if action_buttons.has(action_id):
			button = action_buttons[action_id] as Button
		else:
			button = Button.new()
			button.alignment = HORIZONTAL_ALIGNMENT_LEFT
			button.add_theme_font_size_override("font_size", 13)
			button.pressed.connect(_on_action_pressed.bind(action_id))
			action_list.add_child(button)
			action_buttons[action_id] = button
		var pc: int = int(_dict(action_def.get("cost", {})).get("pc", 0))
		var dur_raw: Variant = action_def.get("dur", null)
		var dur: String = "即时" if dur_raw == null else "%d天" % int(dur_raw)
		var text: String = "%s  政治资本 %d  %s" % [String(action_def.get("zh", action_id)), pc, dur]
		var available: bool = true
		var cool_until: int = int(cooldowns.get(action_id, -1))
		if busy.has(action_id):
			available = false
			text += "  进行中"
		elif cool_until > day:
			available = false
			text += "  冷却至第%d天" % cool_until
		if bool(action_def.get("locked", false)) and not bool(unlocked.get(action_id, false)):
			available = false
		if not _era_open(action_def.get("era", null), year):
			available = false
		button.text = text
		button.tooltip_text = "%s · %s" % [action_id, String(action_def.get("cat", ""))]
		button.disabled = not available


func _era_open(era: Variant, year: int) -> bool:
	if typeof(era) != TYPE_ARRAY:
		return true
	var bounds: Array = era
	if bounds.size() >= 1 and bounds[0] != null and year < int(floor(float(bounds[0]))):
		return false
	if bounds.size() >= 2 and bounds[1] != null and year > int(floor(float(bounds[1]))):
		return false
	return true


func _on_action_pressed(action_id: String) -> void:
	var title: String = action_id
	if GameData.current != null and GameData.current.actions_def.has(action_id):
		title = String(_dict(GameData.current.actions_def[action_id]).get("zh", action_id))
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree) or not (loop as SceneTree).root.has_node("SimEngine"):
		status.text = "未执行：%s" % title
		return
	var cmd: Dictionary = {"op": "execute_action", "action": action_id}
	var err: int = int((loop as SceneTree).root.get_node("SimEngine").call("submit_command", cmd))
	if err == OK:
		status.text = "已提交：%s" % title
	else:
		status.text = "未执行：%s  %s" % [title, error_string(err)]
	if bound_state != null:
		_refresh_actions(bound_state)


func execute_action(state: SimState, action_id: String) -> void:
	var loop: MainLoop = Engine.get_main_loop()
	var cmd: Dictionary = {"op": "execute_action", "action": action_id}
	if loop is SceneTree and (loop as SceneTree).root.has_node("SimEngine"):
		(loop as SceneTree).root.get_node("SimEngine").call("submit_command", cmd)
	else:
		var queue: Array = []
		var m05: Dictionary = _dict(state.modules.get("M05", {}))
		if typeof(m05.get("action_queue", [])) == TYPE_ARRAY:
			queue = m05["action_queue"]
		queue.append({"id": action_id, "days_left": 7})
		m05["action_queue"] = queue
		state.modules["M05"] = m05


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
