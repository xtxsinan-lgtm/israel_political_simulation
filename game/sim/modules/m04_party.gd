class_name M04Party
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M04"


func get_corridor_bounds(state: SimState, axis: String) -> Vector2:
	var pair: Array = _corridor_pair(state, axis)
	return Vector2(float(pair[0]), float(pair[1]))


func _corridor_pair(state: SimState, axis: String) -> Array:
	var custom: Dictionary = _as_dict(_m04(state).get("corridors", {}))
	if custom.has(axis) and custom[axis] is Dictionary:
		var row: Dictionary = custom[axis]
		if row.has("lo") and row.has("hi"):
			return [float(row["lo"]), float(row["hi"])]
	var party_id: String = String(state.player.get("party_id", "likud"))
	var table: Dictionary = {
		"likud": {
			"territory": [-11.9, 91.8],
			"security": [-23.3, 65.4],
			"economy": [-45.7, 64.6],
			"religion": [-42.0, 26.4],
			"foreign": [-29.8, 41.5],
		},
		"labor": {
			"territory": [-70.0, 7.0],
			"security": [-27.0, 50.75],
			"economy": [-80.75, -6.0],
			"religion": [-52.4, 4.75],
			"foreign": [-39.1, 18.5],
		},
	}
	var party: Dictionary = _as_dict(table.get(party_id, {}))
	if party.has(axis) and typeof(party[axis]) == TYPE_ARRAY:
		return party[axis]
	return [-30.0, 70.0]


func compute_grace_factor(months_in_term: int) -> float:
	if months_in_term <= 6:
		return 0.0
	if months_in_term >= 24:
		return 1.0
	return float(months_in_term - 6) / 18.0


func stance_deviation(state: SimState, axis: String) -> float:
	var pair: Array = _corridor_pair(state, axis)
	var lo: float = float(pair[0])
	var hi: float = float(pair[1])
	var pos: float = float(state.gov_axis_position.get(axis, 0.0))
	if pos < lo:
		return lo - pos
	if pos > hi:
		return pos - hi
	return 0.0


func _stance_deviation_scalar(state: SimState) -> float:
	var keys: Array[String] = state.params.get_active_keys("stance_deviation")
	if keys.is_empty():
		return state.params.get_val("stance_deviation", "", state)
	var total: float = 0.0
	for i: int in range(keys.size()):
		total += state.params.get_val("stance_deviation", keys[i], state)
	return total * 0.25


func _peace_treaty_count(state: SimState) -> int:
	var countries: Array[String] = ["egypt", "jordan", "syria", "lebanon", "saudi"]
	var count: int = 0
	for i: int in range(countries.size()):
		if state.params.get_val("peace_treaty_state", countries[i], state) >= 3.0:
			count += 1
	return count


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


func provide_terms(provider_name: String, state: SimState, param_id: String, _scope_key: String) -> Array[Dictionary]:
	if provider_name != "m04_terms" or state.clock.day_index == 0:
		return []
	var dev: float = _stance_deviation_scalar(state)
	var value: float = 0.0
	if param_id == "party_standing":
		var prestige: float = maxf(0.0, state.params.get_val("public_security", "", state) - 60.0) * 0.2
		if _peace_treaty_count(state) >= 1:
			prestige += 10.0
		value = prestige - 0.15 * maxf(0.0, dev - 5.0)
	elif param_id == "faction_mood":
		value = -0.15 * maxf(0.0, dev - 5.0)
	elif param_id == "challenger_strength":
		value = 0.12 * maxf(0.0, dev - 10.0)
	return [{"id": "m04_terms", "value": value, "label_zh": "党内项"}]


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 11:
		return []
	var months: int = SimMath.idiv_floor(maxi(0, state.clock.day_index - int(state.player.get("tenure_start_day", 0))), 30)
	var grace: float = compute_grace_factor(months)
	var m04: Dictionary = _m04(state)
	m04["grace_factor"] = grace
	M05Actions.new().recompute_gov_axis_positions(state)
	var axes: Array[String] = ["territory", "security", "economy", "religion", "foreign"]
	for i: int in range(axes.size()):
		var raw_dev: float = stance_deviation(state, axes[i])
		var dev: float = minf(16.0, raw_dev * 0.32 * maxf(grace, 0.0))
		state.params.set_val("stance_deviation", axes[i], dev, state)
	_sync_leader_and_goals(state, m04)
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
			return _shift_stance(state, String(args.get("axis", args.get("key", "territory"))), float(args.get("value", args.get("amount", 5.0))), String(args.get("direction", "away")))
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


func _shift_stance(state: SimState, axis: String, delta: float, direction: String) -> Array[Dictionary]:
	var party_id: String = String(state.player.get("party_id", "likud"))
	var right_party: bool = party_id != "labor" and party_id != "mapam" and party_id != "ratz"
	var sign: float = 1.0
	if direction == "away" or direction == "left" or direction == "dove":
		sign = -1.0 if right_party else 1.0
	else:
		sign = 1.0 if right_party else -1.0
	state.axis_impulse[axis] = float(state.axis_impulse.get(axis, 0.0)) + sign * absf(delta)
	M05Actions.new().recompute_gov_axis_positions(state)
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


func _sync_leader_and_goals(state: SimState, m04: Dictionary) -> void:
	var leader: String = String(state.player.get("leader_id", "begin"))
	var sec_axis: float = state.params.get_val("gov_axis_position", "security", state)
	var terr_axis: float = state.params.get_val("gov_axis_position", "territory", state)
	var fired: Dictionary = _as_dict(_as_dict(state.modules.get("M12", {})).get("fired", {}))
	var quag: bool = not _flag_on(state, "peace_decompression_mode") and (_has_mod(state, "lebanon_quagmire") or _has_mod(state, "sabra_shatila_stigma") or _any_war(state) or (fired.has("E-1982-06a") and String(fired["E-1982-06a"]) == "B") or (state.clock.y >= 1982 and sec_axis >= 10.0))
	var treaties: int = _treaty_count(state)
	var peace_decompression: bool = _flag_on(state, "peace_decompression_mode") or (not quag and sec_axis <= 6.0 and (state.clock.y < 1979 or treaties >= 1 or state.params.get_val("autonomy_progress", "", state) >= 10.0 or terr_axis <= -15.0))
	var cur_stress: float = state.params.get_val("character_stress", leader, state)
	var target_stress: float = 18.0
	if quag:
		target_stress += 32.0
	var silent: bool = _has_mod(state, "silent_pm") or fired.has("E-1982-11")
	if silent and leader == "begin" and quag:
		target_stress += 28.0
	var inf: float = state.params.get_val("inflation", "", state)
	if inf >= 110.0 and not peace_decompression:
		target_stress += 16.0
	if peace_decompression:
		target_stress = 15.0
	var new_stress: float = clampf(cur_stress + 0.30 * (target_stress - cur_stress), 10.0, 96.0)
	state.params.set_val("character_stress", leader, new_stress, state)
	var base_drain: float = 0.16
	var stress_drain: float = maxf(0.0, (new_stress - 55.0) * 0.018)
	if leader == "begin":
		if peace_decompression:
			base_drain = 0.21
			stress_drain = 0.0
			if _flag_on(state, "peace_decompression_mode"):
				state.params.set_val("public_approval", "", state.params.get_val("public_approval", "", state) + 2.5, state)
				state.params.set_val("poll_lead", "", state.params.get_val("poll_lead", "", state) + 2.0, state)
		else:
			base_drain = 0.36
			stress_drain = maxf(0.0, (new_stress - 48.0) * 0.032)
			if state.clock.y >= 1982 and (quag or inf >= 120.0):
				stress_drain += 0.95
			if silent and quag:
				stress_drain += 0.65
	var new_health: float = clampf(state.params.get_val("health", leader, state) - (base_drain + stress_drain), 0.0, 95.0)
	state.params.set_val("health", leader, new_health, state)
	if state.params.get_val("settler_population", "west_bank", state) >= 6000.0 or state.params.get_val("settler_momentum", "", state) >= 48.0:
		_bump_promise(state, "settle_eretz_israel", 1.2)
	if state.params.get_val("economic_model", "", state) >= -25.0 or _has_mod(state, "new_shekel"):
		_bump_promise(state, "economic_liberalization", 1.4)
	if state.params.get_val("alienation", "mizrahi", state) <= 38.0 or state.params.get_val("region_development", "negev", state) >= 35.0:
		_bump_promise(state, "social_justice", 1.3)
	if treaties >= 1 or (state.params.get_val("public_security", "", state) >= 62.0 and not quag):
		_bump_promise(state, "peace_and_security", 1.5)
	for i: int in range(state.promises.size()):
		var pr: Dictionary = _as_dict(state.promises[i])
		var pk: String = String(pr.get("id", pr.get("key", pr.get("promise_id", ""))))
		if pk == "":
			continue
		pr["id"] = pk
		var prog_val: float = state.params.get_val("promise_progress", pk, state)
		pr["progress"] = prog_val
		if prog_val >= 80.0:
			pr["status"] = "fulfilled"
		state.promises[i] = pr
	if String(state.meta.scenario_id) == "begin_1977" and leader == "begin":
		_tick_begin_vision(state, m04, terr_axis)


func _bump_promise(state: SimState, promise_id: String, amount: float) -> void:
	state.params.set_val("promise_progress", promise_id, state.params.get_val("promise_progress", promise_id, state) + amount, state)


func _tick_begin_vision(state: SimState, m04: Dictionary, terr_axis: float) -> void:
	var held: Dictionary = _as_dict(m04.get("vision_held_months", {}))
	var fired: Dictionary = _as_dict(_as_dict(state.modules.get("M12", {})).get("fired", {}))
	var m1_done: bool = _flag_on(state, "egypt_peace_treaty_signed") or _flag_on(state, "camp_david_signed") or (fired.has("E-1977-11") and String(fired["E-1977-11"]) == "A") or (fired.has("E-1978-09") and String(fired["E-1978-09"]) == "A") or state.params.get_val("peace_treaty_state", "egypt", state) >= 2.0
	if m1_done:
		held["m1_cairo"] = 12
	if m1_done and not _front_at_war(state, "egypt") and state.params.get_val("regime_hostility", "egypt", state) <= 55.0:
		held["m2_rooted"] = int(held.get("m2_rooted", 0)) + 1
	var auto_ok: bool = (_flag_on(state, "autonomy_framework_signed") or m1_done or state.params.get_val("autonomy_progress", "", state) >= 8.0) and state.params.get_val("pal_hostility", "", state) <= 72.0 and not _flag_on(state, "first_intifada_active")
	if auto_ok:
		held["m3_autonomy"] = int(held.get("m3_autonomy", 0)) + 1
	var settlers: float = _settler_total(state)
	var jordan_ok: bool = not _front_at_war(state, "jordan") and state.params.get_val("regime_hostility", "jordan", state) <= 65.0 and _region_exists(state, "west_bank") and settlers >= 52000.0
	if jordan_ok:
		held["m4_jordan"] = int(held.get("m4_jordan", 0)) + 1
	var guard_eretz: bool = _region_exists(state, "west_bank") and terr_axis >= -16.0 and terr_axis <= 68.0 and settlers >= 52000.0
	var guard_law: bool = state.params.get_val("rule_of_law", "", state) >= 50.0 and state.params.get_val("centralization", "", state) <= 28.0 and state.params.get_val("party_standing", "", state) >= 48.0
	var progress: float = 0.0
	if int(held.get("m1_cairo", 0)) >= 1:
		progress += 25.0
	progress += minf(20.0, float(int(held.get("m2_rooted", 0))) * 1.4)
	progress += minf(25.0, float(int(held.get("m3_autonomy", 0))) * 1.8)
	progress += minf(15.0, float(int(held.get("m4_jordan", 0))) * 1.6)
	if guard_eretz:
		progress += 10.0
	if guard_law:
		progress += 5.0
	state.params.set_val("vision_progress", "", clampf(progress, 0.0, 100.0), state)
	m04["vision_held_months"] = held


func _treaty_count(state: SimState) -> int:
	var countries: Array[String] = ["egypt", "jordan", "syria", "lebanon", "saudi"]
	var count: int = 0
	for i: int in range(countries.size()):
		if state.params.get_val("peace_treaty_state", countries[i], state) >= 3.0:
			count += 1
	return count


func _has_mod(state: SimState, mod_id: String) -> bool:
	if state.modifiers == null:
		return false
	for i: int in range(state.modifiers.active.size()):
		if String(state.modifiers.active[i].get("def_id", "")) == mod_id:
			return true
	return false


func _flag_on(state: SimState, flag_id: String) -> bool:
	return state.flags.has(flag_id) and float(_as_dict(state.flags[flag_id]).get("value", 1.0)) != 0.0


func _any_war(state: SimState) -> bool:
	var fronts: Dictionary = _as_dict(_as_dict(state.modules.get("M09", {})).get("fronts", {}))
	var ids: Array[String] = SimMath.sorted_keys(fronts)
	for i: int in range(ids.size()):
		if _front_at_war(state, ids[i]):
			return true
	return false


func _front_at_war(state: SimState, front_id: String) -> bool:
	var fronts: Dictionary = _as_dict(_as_dict(state.modules.get("M09", {})).get("fronts", {}))
	var status: String = String(_as_dict(fronts.get(front_id, {})).get("status", ""))
	return status == "WAR" or status == "war"


func _region_exists(state: SimState, region_id: String) -> bool:
	var regions: Dictionary = _as_dict(_as_dict(state.modules.get("M11", {})).get("regions", {}))
	return bool(_as_dict(regions.get(region_id, {})).get("exists", false))


func _settler_total(state: SimState) -> float:
	var regions: Dictionary = _as_dict(_as_dict(state.modules.get("M11", {})).get("regions", {}))
	var ids: Array[String] = SimMath.sorted_keys(regions)
	var total: float = 0.0
	for i: int in range(ids.size()):
		total += state.params.get_val("settler_population", ids[i], state)
	return total


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
