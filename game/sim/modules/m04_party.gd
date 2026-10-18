class_name M04Party
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M04"


func get_corridor_bounds(state: SimState, axis: String) -> Vector2:
	var party_id: String = String(state.player.get("party_id", "likud"))
	var table: Dictionary = {
		"likud": {
			"territory": Vector2(35.0, 90.0),
			"security": Vector2(20.0, 85.0),
			"economy": Vector2(-10.0, 55.0),
			"religion": Vector2(-20.0, 40.0),
			"democracy": Vector2(-30.0, 45.0),
		},
		"labor": {
			"territory": Vector2(-70.0, 20.0),
			"security": Vector2(-20.0, 50.0),
			"economy": Vector2(-40.0, 30.0),
			"religion": Vector2(-80.0, 10.0),
			"democracy": Vector2(10.0, 70.0),
		},
	}
	var party: Dictionary = _as_dict(table.get(party_id, {}))
	if party.has(axis) and party[axis] is Vector2:
		return party[axis]
	return Vector2(-100.0, 100.0)


func compute_grace_factor(months_in_term: int) -> float:
	if months_in_term <= 6:
		return 0.0
	if months_in_term >= 24:
		return 1.0
	return float(months_in_term - 6) / 18.0


func stance_deviation(state: SimState, axis: String) -> float:
	var bounds: Vector2 = get_corridor_bounds(state, axis)
	var pos: float = float(state.gov_axis_position.get(axis, 0.0))
	if pos < bounds.x:
		return bounds.x - pos
	if pos > bounds.y:
		return pos - bounds.y
	return 0.0


func compute_faction_minister_share(state: SimState, faction_id: String) -> float:
	var offices: Dictionary = _as_dict(_as_dict(state.modules.get("M06", {})).get("offices", {}))
	var characters: Dictionary = _as_dict(_as_dict(state.modules.get("M06", {})).get("characters", {}))
	var seen: Dictionary = {}
	var faction_n: int = 0
	var keys: Array[String] = SimMath.sorted_keys(offices)
	for i: int in range(keys.size()):
		var holder: String = String(offices[keys[i]])
		if holder == "" or seen.has(holder):
			continue
		seen[holder] = true
		var faction: String = String(_as_dict(characters.get(holder, {})).get("faction", ""))
		if faction == faction_id:
			faction_n += 1
	var total: int = seen.size()
	if total <= 0:
		return 0.0
	return float(faction_n) / float(total)


func provide_terms(provider_name: String, state: SimState, param_id: String, scope_key: String) -> Array[Dictionary]:
	if provider_name != "m04_terms":
		return []
	var terms: Array[Dictionary] = []
	if param_id == "faction_mood":
		var share: float = compute_faction_minister_share(state, scope_key)
		var weight: float = state.params.get_val("faction_weight", scope_key, state)
		terms.append({"id": "minister_share", "value": (share - weight) * 20.0, "label_zh": "内阁分肥"})
	elif param_id == "party_standing":
		var mood: float = state.params.get_val("faction_mood", scope_key, state) - 50.0
		terms.append({"id": "faction_mood", "value": mood * 0.1, "label_zh": "派系情绪"})
		var axes: Array[String] = SimTypes.STANCE_AXES
		var penalty: float = 0.0
		for i: int in range(axes.size()):
			penalty += stance_deviation(state, axes[i])
		terms.append({"id": "corridor", "value": -0.05 * penalty, "label_zh": "走廊偏离"})
	elif param_id == "challenger_strength":
		var standing: float = state.params.get_val("party_standing", "", state)
		terms.append({"id": "low_standing", "value": maxf(0.0, 50.0 - standing) * 0.2, "label_zh": "党内地位"})
	return terms


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 11:
		return []
	var months: int = SimMath.idiv_floor(maxi(0, state.clock.day_index - int(state.player.get("tenure_start_day", 0))), 30)
	var grace: float = compute_grace_factor(months)
	var m04: Dictionary = _m04(state)
	m04["grace_factor"] = grace
	var axes: Array[String] = SimTypes.STANCE_AXES
	for i: int in range(axes.size()):
		var dev: float = stance_deviation(state, axes[i]) * maxf(grace, 0.0)
		state.params.set_val("stance_deviation", axes[i], dev, state)
	_tick_promises(state, m04)
	_tick_vision(state, m04)
	var liberal_mood: float = state.params.get_val("faction_mood", "likud_liberal", state)
	var herut_mood: float = state.params.get_val("faction_mood", "likud_herut", state)
	if absf(liberal_mood) > 0.001 or absf(herut_mood) > 0.001:
		var cohesion: float = 100.0 - absf(liberal_mood - herut_mood)
		state.params.set_val("party_cohesion", "", clampf(cohesion, 0.0, 100.0), state)
	var stage: int = 0
	var standing: float = state.params.get_val("party_standing", "", state)
	if standing < 20.0:
		stage = 4
	elif standing < 35.0:
		stage = 3
	elif standing < 50.0:
		stage = 2
	elif standing < 65.0:
		stage = 1
	m04["party_stage"] = stage
	state.modules["M04"] = m04
	return []


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	match op_name:
		"stance_shift_by_corridor", "m04_add_stance_by_corridor":
			return _shift_stance(state, String(args.get("axis", "security")), float(args.get("value", 0.0)))
		"m04_push_corridor":
			return _push_corridor(state, String(args.get("axis", "territory")), float(args.get("lo", 0.0)), float(args.get("hi", 0.0)))
		"m04_shift_corridor":
			return _push_corridor(state, String(args.get("axis", "territory")), float(args.get("dlo", 0.0)), float(args.get("dhi", args.get("value", 0.0))))
		"m04_add_promise_by_tag":
			return _add_promise(state, String(args.get("tag", args.get("promise", ""))))
		"m04_set_promises":
			var m04: Dictionary = _m04(state)
			m04["promises"] = _as_array(args.get("promises", []))
			state.modules["M04"] = m04
			return []
		"m04_party_convention":
			return _convention(state, args)
		"m04_faction_deal":
			state.params.set_val("faction_mood", String(args.get("faction", "")), state.params.get_val("faction_mood", String(args.get("faction", "")), state) + float(args.get("value", 8.0)), state)
			return []
		"m04_faction_exit", "m04_party_split":
			return [{"op": "custom", "key": "m03_split_party", "value": args}]
		"m04_found_new_party":
			return _found_new_party(state, args)
		"m04_leadership_vote", "m04_force_challenge":
			return _leadership(state, args)
		"m04_vision_event":
			return _vision_event(state, String(args.get("milestone", "")))
		"m04_open_campaign_pool", "m04_activate_campaign_promises":
			var pool: Dictionary = _m04(state)
			pool["campaign_open"] = true
			state.modules["M04"] = pool
			return []
		"m04_election_settle", "m04_finalize_promises":
			return _finalize(state)
		"m04_reset_goals_for_leader":
			return _reset_goals(state)
		_:
			return []
	return []


func _shift_stance(state: SimState, axis: String, delta: float) -> Array[Dictionary]:
	var bounds: Vector2 = get_corridor_bounds(state, axis)
	var pos: float = float(state.gov_axis_position.get(axis, 0.0)) + delta
	pos = clampf(pos, -100.0, 100.0)
	state.gov_axis_position[axis] = pos
	var inside: float = pos
	if inside < bounds.x:
		inside = bounds.x
	elif inside > bounds.y:
		inside = bounds.y
	state.params.set_val("stance_deviation", axis, absf(pos - inside), state)
	return []


func _push_corridor(state: SimState, axis: String, lo_delta: float, hi_delta: float) -> Array[Dictionary]:
	var m04: Dictionary = _m04(state)
	var corridors: Dictionary = _as_dict(m04.get("corridors", {}))
	var bounds: Vector2 = get_corridor_bounds(state, axis)
	var row: Dictionary = {"lo": bounds.x + lo_delta, "hi": bounds.y + hi_delta}
	corridors[axis] = row
	m04["corridors"] = corridors
	state.modules["M04"] = m04
	return []


func _add_promise(state: SimState, tag: String) -> Array[Dictionary]:
	if tag == "":
		return []
	var m04: Dictionary = _m04(state)
	var promises: Array = _as_array(m04.get("promises", []))
	promises.append({"id": tag, "progress": 0.0, "active": true})
	m04["promises"] = promises
	state.modules["M04"] = m04
	state.params.set_val("promise_progress", tag, 0.0, state)
	return []


func _found_new_party(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var slots: Array[String] = ["new_party_a", "new_party_b", "new_party_c"]
	var founders: Array[String] = ["founders_a", "founders_b", "founders_c"]
	var m04: Dictionary = _m04(state)
	var used: Dictionary = _as_dict(m04.get("new_party_slots", {}))
	var chosen: String = ""
	var faction: String = ""
	for i: int in range(slots.size()):
		if not bool(used.get(slots[i], false)):
			chosen = slots[i]
			faction = founders[i]
			used[slots[i]] = true
			break
	if chosen == "":
		state.record_error("E_NO_PARTY_SLOT", "new_party slots exhausted")
		return []
	m04["new_party_slots"] = used
	state.modules["M04"] = m04
	return [{"op": "custom", "key": "m03_split_party", "value": {"from": String(args.get("from", state.player.get("party_id", "likud"))), "to": chosen, "seats": int(args.get("seats", 3)), "faction": faction}}]


func _leadership(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var challenger: float = state.params.get_val("challenger_strength", "", state)
	var standing: float = state.params.get_val("party_standing", "", state)
	if challenger > standing or bool(args.get("force", false)):
		state.player["leader_id"] = String(args.get("challenger", "challenger"))
		return [{"op": "custom", "key": "m04_reset_goals_for_leader", "value": {}}]
	return []


func _vision_event(state: SimState, milestone: String) -> Array[Dictionary]:
	if milestone == "":
		return []
	var m04: Dictionary = _m04(state)
	var done: Dictionary = _as_dict(m04.get("milestones", {}))
	if bool(done.get(milestone, false)):
		return []
	done[milestone] = true
	m04["milestones"] = done
	var progress: float = state.params.get_val("vision_progress", "", state) + 33.4
	state.params.set_val("vision_progress", "", clampf(progress, 0.0, 100.0), state)
	state.params.set_val("party_standing", "", state.params.get_val("party_standing", "", state) + 3.0, state)
	state.modules["M04"] = m04
	return []


func _tick_promises(state: SimState, m04: Dictionary) -> void:
	var promises: Array = _as_array(m04.get("promises", []))
	for i: int in range(promises.size()):
		var row: Dictionary = _as_dict(promises[i])
		if not bool(row.get("active", true)):
			continue
		var pid: String = String(row.get("id", ""))
		var progress: float = state.params.get_val("promise_progress", pid, state) + float(row.get("monthly", 4.0))
		if progress >= 100.0:
			row["active"] = false
			state.params.set_val("party_standing", "", state.params.get_val("party_standing", "", state) + 2.0, state)
			state.params.set_val("promise_credit", "", state.params.get_val("promise_credit", "", state) + 5.0, state)
			progress = 100.0
		elif int(row.get("deadline_day", -1)) >= 0 and state.clock.day_index > int(row["deadline_day"]):
			row["active"] = false
			state.params.set_val("cynicism", "", state.params.get_val("cynicism", "", state) + 3.0, state)
			state.params.set_val("party_standing", "", state.params.get_val("party_standing", "", state) - 4.0, state)
		state.params.set_val("promise_progress", pid, progress, state)
		promises[i] = row
	m04["promises"] = promises


func _tick_vision(state: SimState, m04: Dictionary) -> void:
	var milestones: Array[String] = ["m1_egypt_peace", "m2_samaria_heartland", "m3_autonomy_framework"]
	var done: Dictionary = _as_dict(m04.get("milestones", {}))
	var count: int = 0
	for i: int in range(milestones.size()):
		if bool(done.get(milestones[i], false)):
			count += 1
	if count > 0:
		state.params.set_val("vision_progress", "", clampf(float(count) * 33.4, 0.0, 100.0), state)


func explain_m04(state: SimState, param_id: String, key: String) -> Dictionary:
	return {
		"param_id": param_id,
		"key": key,
		"promise": state.params.get_val("promise_progress", key, state),
		"corridor": stance_deviation(state, key if key != "" else "territory"),
		"vision": state.params.get_val("vision_progress", "", state),
	}


func _convention(state: SimState, args: Dictionary) -> Array[Dictionary]:
	var amount: float = clampf(float(args.get("amount", 0.0)), -15.0, 15.0)
	var axis: String = String(args.get("axis", "territory"))
	_push_corridor(state, axis, amount, amount)
	var faction: String = String(args.get("opposed_faction", ""))
	if faction != "":
		state.params.set_val("faction_mood", faction, state.params.get_val("faction_mood", faction, state) - absf(amount), state)
	return []


func _finalize(state: SimState) -> Array[Dictionary]:
	var promises: Array = _as_array(_m04(state).get("promises", []))
	var done: int = 0
	var total: int = 0
	for i: int in range(promises.size()):
		var row: Dictionary = _as_dict(promises[i])
		total += 1
		if float(row.get("progress", state.params.get_val("promise_progress", String(row.get("id", "")), state))) >= 100.0:
			done += 1
	if total > 0:
		var ratio: float = float(done) / float(total)
		if ratio >= 0.75:
			state.params.set_val("promise_credit", "", state.params.get_val("promise_credit", "", state) + 12.0, state)
			state.params.set_val("cynicism", "", state.params.get_val("cynicism", "", state) - 6.0, state)
		elif ratio < 0.40:
			state.params.set_val("promise_credit", "", state.params.get_val("promise_credit", "", state) - 15.0, state)
			state.params.set_val("cynicism", "", state.params.get_val("cynicism", "", state) + 10.0, state)
	var m04: Dictionary = _m04(state)
	for j: int in range(promises.size()):
		var done_row: Dictionary = _as_dict(promises[j])
		done_row["active"] = false
		promises[j] = done_row
	m04["promises"] = promises
	state.modules["M04"] = m04
	return []


func _reset_goals(state: SimState) -> Array[Dictionary]:
	var m04: Dictionary = _m04(state)
	if int(state.player.get("tenure_index", 0)) > 0 or bool(args_failed(m04)):
		var progress: float = state.params.get_val("vision_progress", "", state)
		if progress < 100.0:
			m04["vision_failed"] = true
	m04["milestones"] = {}
	m04["promises"] = [{"id": "continue_predecessor", "progress": 0.0, "active": true, "monthly": 2.0}]
	state.modules["M04"] = m04
	state.params.set_val("vision_progress", "", 0.0, state)
	return []


func args_failed(m04: Dictionary) -> bool:
	return bool(m04.get("vision_failed", false)) or int(m04.get("tenure_index_seen", 0)) > 0


func _m04(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M04", {}))
	state.modules["M04"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
