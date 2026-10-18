class_name SimDirector
extends RefCounted

var state: SimState = null
var scheduler: DailyScheduler = DailyScheduler.new()
var bot: RefCounted = null


func start_new_game(scenario_id: String, custom_seed: int = -1, is_ironman: bool = false) -> Error:
	if scenario_id == "":
		return ERR_INVALID_PARAMETER
	if GameData.current == null:
		var data: GameData = GameData.new()
		data.load_all_runtime_data()
	state = SimState.new()
	var seed: int = custom_seed if custom_seed >= 0 else 19770620
	state.init_from_scenario_bundle(scenario_id, seed, is_ironman)
	state.run["headless"] = false
	return OK


func submit_command(cmd: Dictionary) -> Error:
	if state == null or cmd.is_empty():
		return ERR_INVALID_PARAMETER
	if String(state.run.get("phase", "")) == "ENDED":
		return ERR_INVALID_PARAMETER
	var kind: String = String(cmd.get("op", cmd.get("type", "")))
	var ctx: Dictionary = {"processor": scheduler.processor, "expr": scheduler.expr, "headless": true}
	scheduler.expr.bind(state)
	match kind:
		"resolve_event":
			scheduler.m12.resolve_event_choice(state, String(cmd.get("event", "")), String(cmd.get("option", "A")), ctx)
		"adjust_policy":
			var adjusted: Array[Dictionary] = scheduler.m05.adjust_policy_level(state, String(cmd.get("policy", "")), int(cmd.get("level", 0)), true)
			if not adjusted.is_empty():
				scheduler.processor.apply_effects(adjusted, ctx, state, 0)
		"set_region_priority":
			var region_id: String = String(cmd.get("region", ""))
			var field: String = String(cmd.get("param", "region_investment_priority"))
			state.params.set_val(field, region_id, float(cmd.get("value", 0.0)), state)
		"execute_action", "enact_policy", "enqueue_action":
			var queue: Array = []
			var m05: Variant = state.modules.get("M05", {})
			if typeof(m05) == TYPE_DICTIONARY:
				var row: Dictionary = m05
				if typeof(row.get("action_queue", [])) == TYPE_ARRAY:
					queue = row["action_queue"]
				queue.append({"id": String(cmd.get("action", "")), "days_left": int(cmd.get("days", 7))})
				row["action_queue"] = queue
				state.modules["M05"] = row
		_:
			return ERR_INVALID_PARAMETER
	return OK


func step_one_day() -> Dictionary:
	if state == null:
		return {"ended": true}
	return scheduler.execute_day(state, bot)


func get_state_hash_sha256() -> String:
	if state == null:
		return ""
	return CanonicalSerializer.compute_state_hash_sha256(state)


func capture_snapshot() -> SimReadonlySnapshot:
	return SimReadonlySnapshot.capture(state)
