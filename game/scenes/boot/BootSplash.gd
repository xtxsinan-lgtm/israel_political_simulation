extends Control

const DESK_SCENE: String = "res://ui/scenes/DeskMain.tscn"
const START_SCENARIO: String = "begin_1977"


func _ready() -> void:
	if not SimRNG.verify_t01_golden_vectors():
		push_error("T01 golden vectors failed")
	if not SimCalendar.verify_t02_calendar_vectors():
		push_error("T02 calendar vectors failed")
	var load_err: Error = SimDirector.ensure_runtime_data()
	if load_err != OK:
		push_error("Runtime data failed to load: %s" % error_string(load_err))
		return
	var engine: Node = get_node_or_null("/root/SimEngine")
	if engine == null:
		push_error("SimEngine autoload missing")
		return
	var start_err: int = int(engine.call("start_new_game", START_SCENARIO))
	if start_err != OK:
		push_error("start_new_game(%s) failed: %s" % [START_SCENARIO, error_string(start_err)])
		return
	_enter_desk.call_deferred()


func _enter_desk() -> void:
	var err: Error = get_tree().change_scene_to_file(DESK_SCENE)
	if err != OK:
		push_error("Could not open %s: %s" % [DESK_SCENE, error_string(err)])
