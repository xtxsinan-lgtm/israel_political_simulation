class_name M09Military
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M09"


func get_mobilization_growth_drag(level: int) -> float:
	match level:
		1:
			return -0.15
		2:
			return -0.40
		3:
			return -0.75
		_:
			return 0.0


func daily_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 3:
		return []
	var m09: Dictionary = _m09(state)
	var level: int = int(m09.get("mobilization", 0))
	var target: int = int(m09.get("mobilization_target", level))
	if level < target:
		level += 1
	elif level > target:
		level -= 1
	m09["mobilization"] = level
	state.params.set_val("mobilization", "", float(level), state)
	var effects: Array[Dictionary] = []
	if bool(m09.get("minister_overreach", false)):
		effects.append({"op": "set_flag", "flag": "minister_overreach", "value": 1.0, "ai_reason_breakdown": build_ai_reason_breakdown("sharon", "mobilization", float(level), 2.0)})
		m09["minister_overreach"] = false
	var fronts: Dictionary = _as_dict(m09.get("fronts", {}))
	var ids: Array[String] = SimMath.sorted_keys(fronts)
	for i: int in range(ids.size()):
		var front: Dictionary = _as_dict(fronts[ids[i]])
		if String(front.get("status", "")) != "WAR":
			continue
		var cost: float = 0.15 + 0.1 * float(level)
		state.one_off_flows["budget_balance"] = float(state.one_off_flows.get("budget_balance", 0.0)) - cost
		front["casualties"] = float(front.get("casualties", 0.0)) + 0.2
		fronts[ids[i]] = front
	m09["fronts"] = fronts
	state.modules["M09"] = m09
	return effects


func weekly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 8:
		return []
	var security: float = state.params.get_val("public_security", "", state)
	var deterrence: float = state.params.get_val("deterrence", "", state)
	var patriot: bool = _flag(state, "patriot_deployed")
	var missile: float = state.params.get_val("missile_attacks", "", state)
	if patriot:
		missile *= 0.5
	security += (deterrence - 50.0) * 0.02 - missile * 0.3
	state.params.set_val("public_security", "", clampf(security, 0.0, 100.0), state)
	return []


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	var m09: Dictionary = _m09(state)
	match op_name:
		"m09_set_mobilization":
			m09["mobilization_target"] = clampi(int(args.get("level", 0)), 0, 3)
			state.modules["M09"] = m09
			return []
		"m09_start_war":
			var fronts: Dictionary = _as_dict(m09.get("fronts", {}))
			var front_id: String = String(args.get("front", args.get("country", "sinai")))
			fronts[front_id] = {"status": "WAR", "phase": "maneuver", "casualties": 0.0}
			m09["fronts"] = fronts
			state.modules["M09"] = m09
			return []
		"m09_ceasefire":
			var live: Dictionary = _as_dict(m09.get("fronts", {}))
			var front_id: String = String(args.get("front", ""))
			if live.has(front_id):
				var row: Dictionary = _as_dict(live[front_id])
				row["status"] = "CEASEFIRE"
				live[front_id] = row
			m09["fronts"] = live
			m09["last_ceasefire_date"] = state.clock.date
			var window: Dictionary = _as_dict(m09.get("retaliation_window", {}))
			window[front_id] = state.clock.day_index + 14
			m09["retaliation_window"] = window
			state.modules["M09"] = m09
			return []
		_:
			return []
	return []


func build_ai_reason_breakdown(actor_id: String, param_id: String, current_val: float, threshold_val: float) -> Dictionary:
	return {"actor_id": actor_id, "primary_param_id": param_id, "current_val": current_val, "threshold_val": threshold_val, "top_factors": ["deterrence", "state_integration"]}


func _m09(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M09", {}))
	state.modules["M09"] = current
	return current


func _flag(state: SimState, flag_id: String) -> bool:
	return state.flags.has(flag_id)


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
