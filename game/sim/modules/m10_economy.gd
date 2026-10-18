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
	var one_off: float = float(state.one_off_flows.get("budget_balance", 0.0))
	var revenue: float = state.params.get_val("tax_revenue", "", state)
	if revenue <= 0.0:
		revenue = 8.0
	var expense: float = 9.5 + maxf(0.0, -policy_delta)
	var balance: float = revenue - expense + one_off
	state.params.set_val("budget_balance", "", balance, state)
	var m10: Dictionary = _m10(state)
	m10["last_month_revenue_m"] = revenue
	m10["current_month_expense_m"] = expense
	state.one_off_flows["budget_balance"] = 0.0
	var debt: float = state.params.get_val("public_debt", "", state) + maxf(0.0, -balance) * 0.15
	state.params.set_val("public_debt", "", debt, state)
	var reserves: float = state.params.get_val("foreign_reserves", "", state) + balance * 0.05
	state.params.set_val("foreign_reserves", "", reserves, state)
	var strike: float = state.params.get_val("strike_risk", "", state)
	if state.params.get_val("inflation", "", state) > 40.0:
		strike += 1.0
	state.params.set_val("strike_risk", "", clampf(strike, 0.0, 100.0), state)
	_digest_aliyah(state, m10)
	state.modules["M10"] = m10
	return []


func quarterly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 16:
		return []
	var military: M09Military = M09Military.new()
	var drag: float = military.get_mobilization_growth_drag(int(state.params.get_val("mobilization", "", state)))
	var growth: float = state.params.get_val("growth", "", state) + drag * 0.25
	state.params.set_val("growth", "", growth, state)
	var inflation: float = state.params.get_val("inflation", "", state)
	if inflation > 20.0:
		inflation *= 1.04
	if bool(_m10(state).get("stabilization_1985", false)):
		inflation *= 0.85
	state.params.set_val("inflation", "", inflation, state)
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
