class_name M08Palestine
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const FACTIONS: Array[String] = ["fatah", "pflp", "dflp", "jordan_notables", "local_mayors", "village_leagues", "mujama", "hamas", "pij"]


func _init() -> void:
	module_id = "M08"


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 12:
		return []
	var pal_host: float = state.params.get_val("pal_hostility", "", state)
	var autonomy: float = state.params.get_val("autonomy_progress", "", state)
	var settler_mom: float = state.params.get_val("settler_momentum", "", state)
	var terr_axis: float = state.params.get_val("gov_axis_position", "territory", state)
	var drift: float = 0.06 * maxf(0.0, pal_host - 46.0) + 0.04 * maxf(0.0, settler_mom - 42.0) - 0.03 * maxf(0.0, autonomy - 15.0)
	if state.clock.y >= 1985 and terr_axis >= 5.0 and autonomy < 28.0:
		drift += 0.45
	state.params.set_val("uprising_risk", "", state.params.get_val("uprising_risk", "", state) + drift, state)
	var backlash: Dictionary = _as_dict(_m08(state).get("repression_months", {}))
	var keys: Array[String] = SimMath.sorted_keys(backlash)
	for i: int in range(keys.size()):
		var left: int = int(backlash[keys[i]]) - 1
		if left <= 0:
			backlash.erase(keys[i])
			state.params.set_val("pal_hostility", "", state.params.get_val("pal_hostility", "", state) + 4.0, state)
		else:
			backlash[keys[i]] = left
	var m08: Dictionary = _m08(state)
	m08["repression_months"] = backlash
	state.modules["M08"] = m08
	return []


func weekly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 8:
		return []
	var hostility: float = state.params.get_val("pal_hostility", "", state)
	if hostility <= 65.0:
		return []
	if not state.rng.get_stream("combat").chance((hostility - 60.0) / 220.0):
		return []
	state.params.set_val("public_security", "", state.params.get_val("public_security", "", state) - 1.2, state)
	return [{"op": "set_flag", "flag": "sig.m08_armed_incident", "value": 1.0, "ai_reason_breakdown": build_ai_reason_breakdown("fatah", "pal_hostility", hostility, 65.0)}]


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	match op_name:
		"m08_spawn_hamas":
			var m08: Dictionary = _m08(state)
			var active: Dictionary = _as_dict(m08.get("faction_active", {}))
			active["hamas"] = true
			m08["faction_active"] = active
			state.modules["M08"] = m08
			state.params.set_val("faction_strength", "hamas", maxf(8.0, state.params.get_val("faction_strength", "mujama", state) * 0.4), state)
			return []
		"m08_activate_delegation":
			var m08b: Dictionary = _m08(state)
			m08b["delegation"] = String(args.get("who", "local_mayors"))
			state.modules["M08"] = m08b
			return []
		"m08_set_autonomy_modality":
			var mode: String = String(args.get("mode", "camp_david_autonomy"))
			var m08c: Dictionary = _m08(state)
			m08c["autonomy_modality"] = mode
			m08c["camp_david_autonomy"] = mode == "camp_david_autonomy"
			state.modules["M08"] = m08c
			state.params.set_val("autonomy_progress", "", state.params.get_val("autonomy_progress", "", state) + 10.0, state)
			return []
		"m08_start_intifada":
			state.flags["intifada_active"] = {"value": 1.0, "set_day": state.clock.day_index}
			var clock: Dictionary = _m08(state)
			clock["repression_months"] = {"occupation": int(args.get("months", 36))}
			state.modules["M08"] = clock
			return []
		_:
			return []
	return []


func build_ai_reason_breakdown(actor_id: String, param_id: String, current_val: float, threshold_val: float) -> Dictionary:
	return {"actor_id": actor_id, "primary_param_id": param_id, "current_val": current_val, "threshold_val": threshold_val, "top_factors": ["legitimacy", "militancy"]}


func _conserve_legitimacy(state: SimState) -> void:
	var values: Dictionary = {}
	var total: float = 0.0
	for i: int in range(FACTIONS.size()):
		var value: float = maxf(0.0, state.params.get_val("faction_legitimacy", FACTIONS[i], state))
		values[FACTIONS[i]] = value
		total += value
	if total <= 1.0e-6:
		return
	var assigned: float = 0.0
	for i: int in range(FACTIONS.size()):
		var share: float = 100.0 * float(values[FACTIONS[i]]) / total
		if i == FACTIONS.size() - 1:
			share = 100.0 - assigned
		else:
			share = SimMath.quantize(share)
			assigned += share
		state.params.set_val("faction_legitimacy", FACTIONS[i], share, state)


func _m08(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M08", {}))
	state.modules["M08"] = current
	return current


func _flag(state: SimState, flag_id: String) -> bool:
	return state.flags.has(flag_id) and float(_as_dict(state.flags[flag_id]).get("value", 1.0)) != 0.0


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
