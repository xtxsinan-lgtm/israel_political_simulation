class_name SimDirector
extends RefCounted

const DEFAULT_SEED: int = 19770620

var state: SimState = null
var scheduler: DailyScheduler = DailyScheduler.new()
var bot: RefCounted = null
var recording: bool = true
var command_log: Array[Dictionary] = []
var scenario_id: String = ""
var master_seed: int = DEFAULT_SEED
var is_ironman: bool = false


static func ensure_runtime_data() -> Error:
	if GameData.current != null and not GameData.current.parameters_def.is_empty():
		return OK
	var data: GameData = GameData.current if GameData.current != null else GameData.new()
	return data.load_all_runtime_data()


func start_new_game(new_scenario_id: String, custom_seed: int = -1, ironman: bool = false) -> Error:
	if new_scenario_id == "":
		return ERR_INVALID_PARAMETER
	var load_err: Error = ensure_runtime_data()
	if load_err != OK:
		return load_err
	scenario_id = new_scenario_id
	master_seed = custom_seed if custom_seed >= 0 else DEFAULT_SEED
	is_ironman = ironman
	command_log.clear()
	state = SimState.new()
	state.init_from_scenario_bundle(scenario_id, master_seed, is_ironman)
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
	var result: Error = OK
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
			if region_id == "" or (field != "region_investment_priority" and field != "region_security_posture" and field != "region_absorption_priority"):
				result = ERR_INVALID_PARAMETER
			else:
				state.params.set_val(field, region_id, clampf(float(cmd.get("value", 0.0)), 0.0, 100.0), state)
		"execute_action", "enact_policy", "enqueue_action":
			result = _stage_action(String(cmd.get("action", "")), cmd)
		_:
			result = ERR_INVALID_PARAMETER
	if result == OK and recording:
		command_log.append({
			"day_index": state.clock.day_index,
			"seq": command_log.size(),
			"cmd_type": kind,
			"payload": cmd.duplicate(true),
		})
	return result


func _stage_action(action_id: String, cmd: Dictionary) -> Error:
	if action_id == "" or GameData.current == null or not GameData.current.actions_def.has(action_id):
		return ERR_INVALID_PARAMETER
	var action_def: Dictionary = _dict(GameData.current.actions_def[action_id])
	var cost: Dictionary = _dict(action_def.get("cost", {}))
	var days: int = _int_or(cmd.get("days", action_def.get("dur", 1)), 1)
	var effects: Array = []
	if typeof(action_def.get("fx", [])) == TYPE_ARRAY:
		effects = (action_def["fx"] as Array).duplicate(true)
	var m05: Dictionary = _dict(state.modules.get("M05", {}))
	var staged: Array = []
	if typeof(m05.get("staged_actions", [])) == TYPE_ARRAY:
		staged = m05["staged_actions"]
	staged.append({
		"id": action_id,
		"pc_cost": _int_or(cost.get("pc", 0), 0),
		"days": maxi(1, days),
		"effects": effects,
		"is_minister_proposal": bool(cmd.get("is_minister_proposal", false)),
		"args": _dict(cmd.get("args", {})),
	})
	m05["staged_actions"] = staged
	state.modules["M05"] = m05
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


func _int_or(value: Variant, fallback: int) -> int:
	if typeof(value) == TYPE_INT or typeof(value) == TYPE_FLOAT:
		return int(value)
	return fallback


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
