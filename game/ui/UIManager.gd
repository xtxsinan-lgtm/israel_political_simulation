class_name DeskUiRouter
extends Node

var drawer_index: int = 0
var map_layer: int = 1
var modal_stack: Array[String] = []
var tooltip_stack: Array[String] = []
var ledger_open: bool = false
var codex_open: bool = false
var paused: bool = true
var speed: int = 1

const INPUT_ACTIONS: Array[String] = [
	"toggle_pause", "speed_1", "speed_2", "speed_3", "speed_4", "speed_5",
	"map_mode_f1", "map_mode_f2", "map_mode_f3", "map_mode_f4", "map_mode_f5", "map_mode_f6", "map_mode_f7",
	"toggle_ledger", "toggle_codex", "quick_save", "quick_load",
]


func open_drawer(index: int) -> void:
	if index == drawer_index:
		drawer_index = 0
	else:
		drawer_index = clampi(index, 0, 7)
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.drawer_toggled.emit(drawer_index)
		bus.drawer_requested.emit("D%d" % drawer_index, 0, "")


func set_map_layer(index: int) -> void:
	map_layer = clampi(index, 1, 7)
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.map_layer_changed.emit(map_layer)
		bus.map_mode_changed.emit("F%d" % map_layer)


func push_modal(modal_id: String) -> bool:
	if modal_stack.size() >= 1:
		return false
	modal_stack.append(modal_id)
	return true


func pop_modal() -> String:
	if modal_stack.is_empty():
		return ""
	return modal_stack.pop_back()


func lock_tooltip(tooltip_id: String) -> bool:
	if tooltip_stack.size() >= 3 or tooltip_stack.has(tooltip_id):
		return false
	tooltip_stack.append(tooltip_id)
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.tooltip_lock_toggled.emit(tooltip_id, true)
	return true


func pop_tooltip() -> String:
	if tooltip_stack.is_empty():
		return ""
	var tooltip_id: String = tooltip_stack.pop_back()
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.tooltip_lock_toggled.emit(tooltip_id, false)
	return tooltip_id


## Hotkey scheme (M15 §10, kept free of collisions):
##   Space pause | 1–5 speed | Ctrl/Cmd+1–7 drawers D1–D7 | Tab cycle drawers
##   F1–F7 map layers | L ledger | C codex | F8 quick save | F9 quick load | Esc close by stack.
func _unhandled_input(event: InputEvent) -> void:
	if not (event is InputEventKey):
		return
	var key: InputEventKey = event as InputEventKey
	if not key.pressed or key.echo:
		return
	if handle_key(key.keycode, key.ctrl_pressed or key.meta_pressed, event):
		get_viewport().set_input_as_handled()


## Returns true when the key was consumed. `event` (optional) is matched against the InputMap.
func handle_key(keycode: int, ctrl: bool = false, event: InputEvent = null) -> bool:
	if ctrl:
		if keycode >= KEY_1 and keycode <= KEY_7:
			open_drawer(keycode - KEY_0)
			return true
		return false
	var action: String = _action_for(keycode, event)
	if action != "":
		handle_action(action)
		return true
	match keycode:
		KEY_ESCAPE:
			handle_escape()
			return true
		KEY_TAB:
			open_drawer(1 if drawer_index == 0 else (drawer_index % 7) + 1)
			return true
	return false


func handle_action(action: String) -> void:
	match action:
		"toggle_pause":
			_engine_call("toggle_pause", [])
			_sync_from_engine()
		"speed_1", "speed_2", "speed_3", "speed_4", "speed_5":
			_engine_call("set_speed", [int(action.substr(6))])
			_engine_call("set_paused", [false])
			_sync_from_engine()
		"map_mode_f1", "map_mode_f2", "map_mode_f3", "map_mode_f4", "map_mode_f5", "map_mode_f6", "map_mode_f7":
			set_map_layer(int(action.substr(10)))
		"toggle_ledger":
			set_overlay("ledger", not ledger_open)
		"toggle_codex":
			set_overlay("codex", not codex_open)
		"quick_save":
			var save_err: int = int(_engine_call("quick_save", []))
			if save_err != OK:
				push_warning("quick_save failed: %s" % error_string(save_err))
		"quick_load":
			var load_err: int = int(_engine_call("quick_load", []))
			if load_err != OK:
				push_warning("quick_load failed: %s" % error_string(load_err))
			_sync_from_engine()


func handle_escape() -> void:
	if not tooltip_stack.is_empty():
		pop_tooltip()
	elif not modal_stack.is_empty():
		pop_modal()
	elif drawer_index != 0:
		open_drawer(drawer_index)
	elif ledger_open or codex_open:
		set_overlay("ledger", false)
		set_overlay("codex", false)


func set_overlay(overlay_id: String, open: bool) -> void:
	if overlay_id == "ledger":
		ledger_open = open
	elif overlay_id == "codex":
		codex_open = open
		var codex_bus: DeskEventBus = DeskEventBus.hub()
		if codex_bus != null and open:
			codex_bus.codex_entry_requested.emit("index")
	else:
		return
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.overlay_toggled.emit(overlay_id, open)


func _action_for(keycode: int, event: InputEvent) -> String:
	for i: int in range(INPUT_ACTIONS.size()):
		var action: String = INPUT_ACTIONS[i]
		if not InputMap.has_action(action):
			continue
		if event != null:
			if event.is_action_pressed(action, false, true):
				return action
			continue
		var bound: Array[InputEvent] = InputMap.action_get_events(action)
		for j: int in range(bound.size()):
			if bound[j] is InputEventKey and (bound[j] as InputEventKey).keycode == keycode:
				return action
	return ""


func _engine_call(method: String, args: Array) -> Variant:
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree) or not (loop as SceneTree).root.has_node("SimEngine"):
		return ERR_UNCONFIGURED
	return (loop as SceneTree).root.get_node("SimEngine").callv(method, args)


func _sync_from_engine() -> void:
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree) or not (loop as SceneTree).root.has_node("SimEngine"):
		return
	var engine: Node = (loop as SceneTree).root.get_node("SimEngine")
	paused = bool(engine.get("paused"))
	speed = int(engine.get("speed_level"))


static func current() -> DeskUiRouter:
	var loop: MainLoop = Engine.get_main_loop()
	if loop is SceneTree and (loop as SceneTree).root.has_node("UIManager"):
		return (loop as SceneTree).root.get_node("UIManager") as DeskUiRouter
	return null
