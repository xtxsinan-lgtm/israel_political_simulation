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


func handle_key(keycode: int) -> void:
	match keycode:
		KEY_SPACE:
			paused = not paused
			var bus: DeskEventBus = DeskEventBus.hub()
			if bus != null:
				bus.sim_speed_changed.emit(0 if paused else speed)
		KEY_1, KEY_2, KEY_3:
			speed = keycode - KEY_0
			paused = false
			var speed_bus: DeskEventBus = DeskEventBus.hub()
			if speed_bus != null:
				speed_bus.sim_speed_changed.emit(speed)
		KEY_F1, KEY_F2, KEY_F3, KEY_F4, KEY_F5, KEY_F6, KEY_F7:
			set_map_layer(keycode - KEY_F1 + 1)
		KEY_L:
			ledger_open = not ledger_open
		KEY_C:
			codex_open = not codex_open
			var codex_bus: DeskEventBus = DeskEventBus.hub()
			if codex_bus != null and codex_open:
				codex_bus.codex_entry_requested.emit("index")
		KEY_ESCAPE:
			if not tooltip_stack.is_empty():
				pop_tooltip()
			elif not modal_stack.is_empty():
				pop_modal()
			elif drawer_index != 0:
				open_drawer(drawer_index)
			elif ledger_open or codex_open:
				ledger_open = false
				codex_open = false
		KEY_TAB:
			open_drawer(1 if drawer_index == 0 else (drawer_index % 7) + 1)
		_:
			if keycode >= KEY_1 and keycode <= KEY_7 and not paused:
				open_drawer(keycode - KEY_0)


static func current() -> DeskUiRouter:
	var loop: MainLoop = Engine.get_main_loop()
	if loop is SceneTree and (loop as SceneTree).root.has_node("UIManager"):
		return (loop as SceneTree).root.get_node("UIManager") as DeskUiRouter
	return null
