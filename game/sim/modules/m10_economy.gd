class_name M10Economy
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M10"


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 9:
		return []
	var actions: M05Actions = M05Actions.new()
	var policy_delta: float = actions.m05_policy_fiscal_delta(state)
	var m10: Dictionary = _m10(state)
	var one_off: float = float(m10.get("last_one_off_flow", 0.0))
	var inflation: float = state.params.get_val("inflation", "", state)
	var tanzi: float = maxf(0.0, (inflation - 35.0) * 0.012)
	if bool(m10.get("stabilization_plan_active", false)) or _has_modifier(state, "new_shekel"):
		tanzi = 0.0
		policy_delta = maxf(policy_delta, 0.8)
	var target_bb: float = clampf(-2.0 + policy_delta + one_off - tanzi, -18.0, 12.0)
	var current_bb: float = state.params.get_val("budget_balance", "", state)
	state.params.set_val("budget_balance", "", current_bb + 0.25 * (target_bb - current_bb), state)
	var fx: float = state.params.get_val("fx_reserves", "", state)
	if fx < 12.0 and state.params.get_val("us_admin_relation", "", state) >= 40.0:
		state.params.set_val("fx_reserves", "", fx + 2.2, state)
	elif fx > 88.0:
		state.params.set_val("fx_reserves", "", fx - 1.8, state)
	if bool(m10.get("stabilization_plan_active", false)):
		var left: int = int(m10.get("stabilization_months_left", 0)) - 1
		m10["stabilization_months_left"] = maxi(0, left)
		if left <= 0:
			m10["stabilization_plan_active"] = false
	m10["peak_inflation_tenure"] = maxf(float(m10.get("peak_inflation_tenure", 0.0)), inflation)
	m10["min_fx_tenure"] = minf(float(m10.get("min_fx_tenure", 100.0)), state.params.get_val("fx_reserves", "", state))
	_digest_aliyah(state, m10)
	state.modules["M10"] = m10
	return []


func quarterly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 16:
		return []
	var inflation: float = state.params.get_val("inflation", "", state)
	var balance: float = state.params.get_val("budget_balance", "", state)
	var m10: Dictionary = _m10(state)
	if state.clock.date >= "1986-04-01" and inflation >= 150.0 and not _has_modifier(state, "new_shekel") and state.params.get_val("centralization", "", state) < 55.0:
		state.modifiers.add_modifier("new_shekel", {"duration_days": -1}, "M10_stabilization", state)
		m10["stabilization_plan_active"] = true
		m10["stabilization_months_left"] = 24
		state.params.set_val("inflation", "", 23.5, state)
		state.params.set_val("budget_balance", "", balance + 3.5, state)
		state.params.set_val("fx_reserves", "", state.params.get_val("fx_reserves", "", state) + 10.0, state)
	elif _has_modifier(state, "new_shekel") or bool(m10.get("stabilization_plan_active", false)):
		if inflation > 27.5:
			state.params.set_val("inflation", "", maxf(19.5, 22.0 + (inflation - 22.0) * 0.25), state)
		elif inflation < 17.0:
			state.params.set_val("inflation", "", 19.5 + maxf(0.0, -balance) * 0.5, state)
	elif inflation >= 120.0 and balance <= -8.0:
		state.params.set_val("inflation", "", inflation + maxf(2.0, (-balance - 6.0) * 0.8), state)
	state.modules["M10"] = m10
	return []


func provide_terms(provider_name: String, state: SimState, param_id: String, _scope_key: String) -> Array[Dictionary]:
	if state.clock.day_index == 0:
		return [{"id": provider_name, "value": 0.0, "label_zh": "经济项"}]
	if provider_name == "m10_monthly_terms":
		return [{"id": provider_name, "value": _monthly_term(state, param_id), "label_zh": "月度经济项"}]
	if provider_name == "m10_quarterly_terms":
		return [{"id": provider_name, "value": _quarterly_term(state, param_id), "label_zh": "季度经济项"}]
	return []


func annual_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 17:
		return []
	var m10: Dictionary = _m10(state)
	m10["budget_due_day"] = state.clock.day_index + 90
	m10["budget_open"] = true
	state.modules["M10"] = m10
	return [{"op": "custom", "key": "m03_submit_bill", "value": {"origin": "M10", "vote": "budget", "bill_uid": "budget-%d" % state.clock.y}}]


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	var m10: Dictionary = _m10(state)
	match op_name:
		"m10_pass_budget", "m10_budget_result":
			m10["budget_open"] = false
			m10["budget_passed"] = bool(args.get("passed", true))
			if not bool(args.get("passed", true)) and state.clock.day_index > int(m10.get("budget_due_day", 0)):
				return [{"op": "custom", "key": "m03_dissolve_knesset", "value": {}}]
			state.modules["M10"] = m10
			return []
		"m10_set_draft_slider":
			var sliders: Dictionary = _as_dict(m10.get("draft_sliders", {}))
			sliders[String(args.get("slider", "defense"))] = float(args.get("value", 0.0))
			m10["draft_sliders"] = sliders
			state.modules["M10"] = m10
			return []
		"m10_set_enacted_slider_delta":
			var enacted: Dictionary = _as_dict(m10.get("enacted_sliders", {}))
			var key: String = String(args.get("slider", "defense"))
			enacted[key] = float(enacted.get(key, 0.0)) + float(args.get("delta", 0.0))
			m10["enacted_sliders"] = enacted
			state.modules["M10"] = m10
			return []
		"m10_apply_stabilization_plan":
			m10["stabilization_1985"] = true
			state.modules["M10"] = m10
			return []
		"m10_trigger_bank_bailout":
			state.one_off_flows["budget_balance"] = float(state.one_off_flows.get("budget_balance", 0.0)) - float(args.get("cost", 4.0))
			return []
		"m10_inject_external_inflation_shock":
			state.params.set_val("inflation", "", state.params.get_val("inflation", "", state) + float(args.get("value", 5.0)), state)
			return []
		"m10_spawn_aliyah_cohort":
			var cohorts: Array = []
			var existing: Variant = m10.get("aliyah_cohorts", [])
			if typeof(existing) == TYPE_ARRAY:
				cohorts = existing
			cohorts.append({"size": float(args.get("size", 10.0)), "months_left": int(args.get("months", 12))})
			m10["aliyah_cohorts"] = cohorts
			state.modules["M10"] = m10
			return []
		_:
			return []
	return []


func _monthly_term(state: SimState, param_id: String) -> float:
	var balance: float = state.params.get_val("budget_balance", "", state)
	if param_id == "public_debt":
		return clampf(-balance * 0.12, -1.5, 2.5)
	if param_id == "fx_reserves":
		var us_rel: float = state.params.get_val("us_admin_relation", "", state)
		return (balance + 2.0) * 0.4 + (us_rel - 58.0) * 0.05
	return 0.0


func _quarterly_term(state: SimState, param_id: String) -> float:
	if param_id == "growth":
		var mob: float = state.params.get_val("mobilization", "", state)
		if mob >= 80.0:
			return -0.75
		if mob >= 50.0:
			return -0.25
		if mob >= 25.0:
			return -0.08
		return 0.0
	if param_id != "inflation":
		return 0.0
	var balance: float = state.params.get_val("budget_balance", "", state)
	var inflation: float = state.params.get_val("inflation", "", state)
	var econ: float = state.params.get_val("economic_model", "", state)
	var m10: Dictionary = _m10(state)
	if bool(m10.get("stabilization_plan_active", false)) or _has_modifier(state, "new_shekel") or bool(m10.get("indexation_removed", false)):
		return clampf((-balance - 1.5) * 1.1 - maxf(0.0, econ) * 0.08, -5.0, 5.0)
	var deficit: float = maxf(0.0, -balance - 1.5)
	var war_stress: float = 16.0 if (_at_war(state) or _has_modifier(state, "lebanon_quagmire")) else 0.0
	var bailout: float = 32.0 if state.flags.has("bank_nationalization") else 0.0
	var hist: float = _inflation_corridor(state.clock.y) + deficit * 5.5 + war_stress + bailout
	if econ >= 15.0 and balance >= -1.8:
		hist *= 0.62
	var target_inf: float = clampf(hist, 25.0, 375.0)
	return (target_inf - 35.0) + 0.45 * (target_inf - inflation)


func _inflation_corridor(year: int) -> float:
	match year:
		1977:
			return 44.0
		1978:
			return 56.0
		1979:
			return 82.0
		1980:
			return 115.0
		1981:
			return 112.0
		1982:
			return 138.0
		1983:
			return 275.0
		1984:
			return 345.0
		_:
			return 330.0 if year >= 1985 else 44.0


func _at_war(state: SimState) -> bool:
	var fronts: Dictionary = _as_dict(_as_dict(state.modules.get("M09", {})).get("fronts", {}))
	var ids: Array[String] = SimMath.sorted_keys(fronts)
	for i: int in range(ids.size()):
		var front: Dictionary = _as_dict(fronts[ids[i]])
		var status: String = String(front.get("status", ""))
		if status == "FULL_WAR" or status == "LIMITED_OP" or front.get("active_war", null) != null:
			return true
	return false


func _has_modifier(state: SimState, mod_id: String) -> bool:
	for i: int in range(state.active_modifiers.size()):
		if String(state.active_modifiers[i].get("def_id", "")) == mod_id:
			return true
	return false


func _digest_aliyah(state: SimState, m10: Dictionary) -> void:
	var cohorts: Array = []
	var existing: Variant = m10.get("aliyah_cohorts", [])
	if typeof(existing) == TYPE_ARRAY:
		cohorts = existing
	var kept: Array = []
	var capacity: float = maxf(1.0, state.params.get_val("absorption_capacity", "", state) / 20.0)
	for i: int in range(cohorts.size()):
		var row: Dictionary = {}
		if typeof(cohorts[i]) == TYPE_DICTIONARY:
			row = cohorts[i]
		row["size"] = maxf(0.0, float(row.get("size", 0.0)) - capacity)
		row["months_left"] = int(row.get("months_left", 1)) - 1
		if float(row["size"]) > 0.2 and int(row["months_left"]) > 0:
			kept.append(row)
	m10["aliyah_cohorts"] = kept


func _m10(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M10", {}))
	state.modules["M10"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
