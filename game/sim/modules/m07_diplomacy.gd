class_name M07Diplomacy
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M07"


func interpolate_world_track(track: Array, year: int, month: int) -> float:
	if track.is_empty():
		return 0.0
	var at: float = float(year) + float(month - 1) / 12.0
	var prev_t: float = float(_as_dict(track[0]).get("t", year))
	var prev_v: float = float(_as_dict(track[0]).get("v", 0.0))
	if at <= prev_t:
		return prev_v
	for i: int in range(1, track.size()):
		var row: Dictionary = _as_dict(track[i])
		var next_t: float = float(row.get("t", prev_t))
		var next_v: float = float(row.get("v", prev_v))
		if at <= next_t:
			var span: float = next_t - prev_t
			if absf(span) < 1.0e-6:
				return next_v
			var mix: float = (at - prev_t) / span
			return prev_v + mix * (next_v - prev_v)
		prev_t = next_t
		prev_v = next_v
	return prev_v


func compute_war_probability(state: SimState, country_id: String) -> float:
	var countries: Dictionary = _countries(state)
	var row: Dictionary = _as_dict(countries.get(country_id, {}))
	if int(row.get("peace_treaty_state", 0)) >= 3:
		return 0.0
	var hostility: float = state.params.get_val("regime_hostility", country_id, state)
	var popular: float = state.params.get_val("popular_hostility", country_id, state)
	var ready: float = float(row.get("war_readiness", state.params.get_val("country_war_readiness", country_id, state)))
	var deterrence: float = state.params.get_val("deterrence", "", state)
	var p: float = (0.45 * hostility + 0.25 * popular + 0.30 * ready) / 100.0
	p *= clampf(1.0 - deterrence / 200.0, 0.15, 1.0)
	return clampf(p, 0.0, 0.85)


func compute_immigration_inflow(state: SimState) -> float:
	var base: float = 2.4
	if _flag(state, "world_soviet_emigration_open"):
		base += 8.0
	if state.clock.y >= 1990:
		base += 6.0
	var capacity: float = state.params.get_val("absorption_capacity", "", state)
	return SimMath.quantize(base * clampf(capacity / 50.0, 0.4, 1.6))


func provide_terms(provider_name: String, state: SimState, _param_id: String, scope_key: String) -> Array[Dictionary]:
	if provider_name == "m07_us_admin_baseline":
		var admin: float = interpolate_world_track(_track("us_admin"), state.clock.y, state.clock.m)
		admin += float(_perm(state).get("us_admin_relation", 0.0))
		return [{"id": "us_admin", "value": admin, "label_zh": "白宫基线"}]
	if provider_name == "m07_power_baseline":
		var power: float = interpolate_world_track(_track(scope_key), state.clock.y, state.clock.m)
		return [{"id": "power", "value": power, "label_zh": "大国基线"}]
	return []


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 12:
		return []
	var fired: Dictionary = _as_dict(_as_dict(state.modules.get("M12", {})).get("fired", {}))
	var nuclear: float = state.params.get_val("enemy_nuclear_progress", "iraq", state)
	if state.clock.date <= "1981-12-31" and not fired.has("E-1981-06a") and nuclear < 92.0:
		state.params.set_val("enemy_nuclear_progress", "iraq", minf(92.0, nuclear + 1.15), state)
	if state.clock.date >= "1978-06-01" and state.clock.date <= "1979-03-01" and not fired.has("E-1979-02"):
		state.params.set_val("regime_stability", "iran", 15.0, state)
	if state.clock.y >= 1990 and not fired.has("E-1991-05"):
		state.params.set_val("regime_stability", "ethiopia", 12.0, state)
	if state.clock.y >= 1989:
		state.params.set_val("power_relation", "ussr", state.params.get_val("power_relation", "ussr", state) + 1.5, state)
		state.params.set_val("regime_stability", "egypt", minf(38.0, state.params.get_val("regime_stability", "egypt", state)), state)
	var effects: Array[Dictionary] = []
	var countries: Dictionary = _countries(state)
	var ids: Array[String] = SimMath.sorted_keys(countries)
	for i: int in range(ids.size()):
		var p: float = compute_war_probability(state, ids[i])
		if p > 0.55:
			effects.append({"op": "custom", "key": "m09_start_war", "value": {"country": ids[i], "ai_reason_breakdown": build_ai_reason_breakdown(ids[i], "regime_hostility", p, 0.55)}})
	return effects


func daily_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 4:
		return []
	var m07: Dictionary = _m07(state)
	var summit: Dictionary = _as_dict(m07.get("summit", {}))
	if summit.is_empty():
		return []
	summit["day"] = int(summit.get("day", 0)) + 1
	if int(summit["day"]) >= int(summit.get("days", 13)):
		m07["summit"] = summit
		state.modules["M07"] = m07
		return handle_custom_op("m07_conclude_summit", state, {}, {})
	m07["summit"] = summit
	state.modules["M07"] = m07
	return []


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	var m07: Dictionary = _m07(state)
	match op_name:
		"m07_set_world_track":
			var perm: Dictionary = _as_dict(m07.get("perm_deltas", {}))
			perm[String(args.get("param", "us_admin_relation"))] = float(perm.get(String(args.get("param", "")), 0.0)) + float(args.get("delta", 0.0))
			m07["perm_deltas"] = perm
			state.modules["M07"] = m07
			return []
		"m07_open_negotiation":
			m07["summit"] = {
				"id": String(args.get("summit", "camp_david_1978")),
				"days": int(args.get("days", 13)),
				"day": 0,
				"issues": {"sinai_withdrawal": 0, "palestinian_autonomy": 0, "settlement_freeze": 0, "us_security_guarantee": 0},
			}
			state.modules["M07"] = m07
			return []
		"m07_set_issue_tier":
			var summit: Dictionary = _as_dict(m07.get("summit", {}))
			var issues: Dictionary = _as_dict(summit.get("issues", {}))
			issues[String(args.get("issue", ""))] = clampi(int(args.get("tier", 0)), 0, 3)
			summit["issues"] = issues
			m07["summit"] = summit
			state.modules["M07"] = m07
			return []
		"m07_trade_concession":
			var channels: Dictionary = _as_dict(m07.get("secret_channels", {}))
			channels[String(args.get("country", "egypt"))] = true
			m07["secret_channels"] = channels
			state.modules["M07"] = m07
			state.params.set_val("regime_hostility", String(args.get("country", "egypt")), state.params.get_val("regime_hostility", String(args.get("country", "egypt")), state) - float(args.get("value", 4.0)), state)
			return []
		"m07_conclude_summit":
			m07["summit_closed"] = true
			state.modules["M07"] = m07
			return [{"op": "custom", "key": "m03_submit_bill", "value": {"origin": "M07", "vote": "absolute61", "bill_uid": "treaty"}}]
		"m07_ratification_result":
			if bool(args.get("passed", false)):
				var countries: Dictionary = _countries(state)
				var egypt: Dictionary = _as_dict(countries.get("egypt", {}))
				egypt["peace_treaty_state"] = 3
				countries["egypt"] = egypt
				m07["countries"] = countries
				state.modules["M07"] = m07
				state.params.set_val("intl_legitimacy", "", state.params.get_val("intl_legitimacy", "", state) + 6.0, state)
			return []
		_:
			return []
	return []


func build_ai_reason_breakdown(actor_id: String, param_id: String, current_val: float, threshold_val: float) -> Dictionary:
	return {"actor_id": actor_id, "primary_param_id": param_id, "current_val": current_val, "threshold_val": threshold_val, "top_factors": [param_id]}


func _sync_congress(state: SimState) -> void:
	var admin: float = state.params.get_val("us_admin_relation", "", state)
	var congress: float = clampf(admin * 0.7 + float(_perm(state).get("us_congress_relation", 0.0)), 0.0, 100.0)
	state.params.set_val("us_congress_relation", "", congress, state)
	if congress >= 60.0 and admin >= 55.0:
		state.flags["us_aid"] = {"value": 1.0, "set_day": state.clock.day_index}


func _track(name: String) -> Array:
	if GameData.current == null:
		return []
	var raw: Variant = GameData.current.world_tracks_def.get(name, [])
	if typeof(raw) == TYPE_ARRAY:
		return raw
	var nested: Dictionary = _as_dict(raw)
	var points: Variant = nested.get("points", nested.get("track", []))
	if typeof(points) == TYPE_ARRAY:
		return points
	return []


func _perm(state: SimState) -> Dictionary:
	return _as_dict(_m07(state).get("perm_deltas", {}))


func _countries(state: SimState) -> Dictionary:
	var m07: Dictionary = _m07(state)
	var countries: Dictionary = _as_dict(m07.get("countries", {}))
	if countries.is_empty():
		countries = {"egypt": {"peace_treaty_state": 0, "war_readiness": 40.0}, "syria": {"peace_treaty_state": 0, "war_readiness": 35.0}, "jordan": {"peace_treaty_state": 0, "war_readiness": 20.0}}
		m07["countries"] = countries
		m07["perm_deltas"] = {}
		m07["secret_channels"] = {}
		state.modules["M07"] = m07
	return countries


func _m07(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M07", {}))
	state.modules["M07"] = current
	return current


func _flag(state: SimState, flag_id: String) -> bool:
	if not state.flags.has(flag_id):
		return false
	return float(_as_dict(state.flags[flag_id]).get("value", 1.0)) != 0.0


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
