class_name M05Actions
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const SOFT_CAP: float = 92.0


func _init() -> void:
	module_id = "M05"


func compute_monthly_pc_income(state: SimState) -> float:
	var standing: float = state.params.get_val("party_standing", "", state)
	var seats: float = state.params.get_val("coalition_seats", "", state)
	var fatigue: float = state.params.get_val("govt_fatigue", "", state)
	var income: float = 8.0
	income += 0.08 * (standing - 50.0)
	income += 0.15 * clampf(seats - 61.0, -15.0, 25.0)
	income -= 0.06 * fatigue
	var factor: float = 1.0
	if state.modifiers != null:
		factor = state.modifiers.get_factor("pc_income")
	income *= factor
	return clampf(income, 3.0, 28.0)


func apply_pc_soft_cap(state: SimState, raw_pc: float) -> float:
	var stored: float = raw_pc
	if raw_pc > SOFT_CAP:
		var overflow: float = raw_pc - SOFT_CAP
		stored = SOFT_CAP + 0.25 * overflow
		var standing: float = state.params.get_val("party_standing", "", state) + 0.05 * overflow
		state.params.set_val("party_standing", "", clampf(standing, 0.0, 100.0), state)
	return clampf(stored, 0.0, 100.0)


func recompute_gov_axis_positions(state: SimState) -> void:
	var axes: Array[String] = ["territory", "security", "economy", "religion", "foreign"]
	var totals: Dictionary = {}
	for i: int in range(axes.size()):
		totals[axes[i]] = 0.0
	if GameData.current != null:
		var ids: Array[String] = SimMath.sorted_keys(GameData.current.policies_def)
		for p: int in range(ids.size()):
			var pol: Dictionary = _as_dict(GameData.current.policies_def[ids[p]])
			var ax_map: Dictionary = _as_dict(pol.get("ax", pol.get("axis", {})))
			if ax_map.is_empty():
				continue
			var level: float = _policy_axis_level(state, ids[p], pol)
			var tiers: Array = _as_array(pol.get("tiers", []))
			var min_v: float = 0.0
			var max_v: float = 100.0
			var have_tier: bool = false
			for t: int in range(tiers.size()):
				var tier_v: float = _tier_scalar(tiers[t])
				if not have_tier:
					min_v = tier_v
					max_v = tier_v
					have_tier = true
				else:
					min_v = minf(min_v, tier_v)
					max_v = maxf(max_v, tier_v)
			var neutral: float = 0.0 if min_v < 0.0 else 50.0
			if pol.has("n"):
				neutral = float(pol.get("n", neutral))
			var rel: float = 0.0
			if level >= neutral:
				rel = (level - neutral) / maxf(1.0, max_v - neutral)
			else:
				rel = (level - neutral) / maxf(1.0, neutral - min_v)
			var ax_keys: Array[String] = SimMath.sorted_keys(ax_map)
			for a: int in range(ax_keys.size()):
				var axis_name: String = ax_keys[a]
				if totals.has(axis_name):
					totals[axis_name] = float(totals[axis_name]) + float(ax_map[axis_name]) * rel
	for i: int in range(axes.size()):
		var axis: String = axes[i]
		var impulse: float = clampf(float(state.axis_impulse.get(axis, 0.0)), -18.0, 18.0)
		state.axis_impulse[axis] = SimMath.quantize(impulse)
		var pos: float = SimMath.quantize(clampf(float(totals[axis]) + impulse, -100.0, 100.0))
		state.gov_axis_position[axis] = pos
		state.params.set_val("gov_axis_position", axis, pos, state)


func m05_policy_fiscal_delta(state: SimState) -> float:
	if GameData.current == null:
		return SimMath.quantize(-0.056)
	var delta_annual: float = 0.0
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.policies_def)
	for i: int in range(ids.size()):
		var pol: Dictionary = _as_dict(GameData.current.policies_def[ids[i]])
		var tiers: Array = _as_array(pol.get("tiers", []))
		if tiers.is_empty():
			continue
		var start_idx: int = _tier_index(_as_dict(pol.get("start", {})).get("begin_1977", 0), tiers.size())
		var cur_idx: int = start_idx
		var saved: Dictionary = _as_dict(state.policies.get(ids[i], {}))
		if saved.has("tier_idx"):
			cur_idx = _tier_index(saved.get("tier_idx", start_idx), tiers.size())
		var f0: float = _tier_fiscal(tiers, start_idx)
		var f_cur: float = _tier_fiscal(tiers, cur_idx)
		delta_annual -= (f_cur - f0)
	return SimMath.quantize(-0.056 + delta_annual / 12.0)


func adjust_policy_level(state: SimState, policy_id: String, target_level: int, charge_costs: bool) -> Array[Dictionary]:
	var current: int = int(SimMath.round_half_up_int(state.params.get_val("policy_level", policy_id, state)))
	var pol: Dictionary = {}
	if GameData.current != null:
		pol = _as_dict(GameData.current.policies_def.get(policy_id, {}))
	var max_step: int = int(pol.get("max_step", 1))
	var delta: int = clampi(target_level - current, -max_step, max_step)
	var next: int = current + delta
	var effects: Array[Dictionary] = []
	if bool(pol.get("requires_vote", false)) and not bool(pol.get("skip_vote", false)):
		effects.append({"op": "custom", "key": "m03_submit_bill", "value": {"origin": "M05", "vote": "simple", "bill_uid": "pol-" + policy_id}})
	else:
		state.params.set_val("policy_level", policy_id, float(next), state)
	if charge_costs:
		var cost: float = absf(float(delta)) * float(pol.get("pc_cost", 2.0))
		var pc: float = state.params.get_val("political_capital", "", state) - cost
		state.params.set_val("political_capital", "", maxf(0.0, pc), state)
	recompute_gov_axis_positions(state)
	return effects


func daily_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no == 2:
		return _enqueue(state)
	if step_no == 5:
		return _advance(state)
	return []


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 15:
		return []
	var standing: float = state.params.get_val("party_standing", "", state)
	var seats: float = state.params.get_val("coalition_seats", "", state)
	var base_pc: float = 16.0 + (standing - 50.0) * 0.12 + (seats - 61.0) * 0.20
	var cur_pc: float = state.params.get_val("political_capital", "", state)
	if cur_pc < 110.0:
		state.params.set_val("political_capital", "", cur_pc + maxf(8.0, base_pc * 0.75), state)
	recompute_gov_axis_positions(state)
	return []


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	match op_name:
		"m05_change_policy":
			return adjust_policy_level(state, String(args.get("policy", "")), int(args.get("level", 0)), bool(args.get("charge", true)))
		"m05_grant_favor":
			return _favor(state, args, true)
		"m05_incur_favor":
			return _favor(state, args, false)
		"m05_cancel_action":
			return _cancel(state, String(args.get("action", "")))
		"m05_unlock":
			var unlocked: Dictionary = _as_dict(_m05(state).get("unlocked_actions", {}))
			unlocked[String(args.get("action_id", args.get("id", "")))] = true
			var m05u: Dictionary = _m05(state)
			m05u["unlocked_actions"] = unlocked
			state.modules["M05"] = m05u
			state.flags["unlock." + String(args.get("id", ""))] = {"value": 1.0, "set_day": state.clock.day_index}
			return []
		"m05_bill_result":
			var m05: Dictionary = _m05(state)
			var results: Dictionary = _as_dict(m05.get("bill_results", {}))
			results[String(args.get("bill_uid", ""))] = bool(args.get("passed", false))
			m05["bill_results"] = results
			state.modules["M05"] = m05
			return []
		"m05_add_axis_impulse":
			var m05b: Dictionary = _m05(state)
			var impulses: Dictionary = _as_dict(m05b.get("axis_impulses", {}))
			var axis: String = String(args.get("axis", "security"))
			impulses[axis] = float(impulses.get(axis, 0.0)) + float(args.get("value", 0.0))
			m05b["axis_impulses"] = impulses
			state.modules["M05"] = m05b
			recompute_gov_axis_positions(state)
			return []
		_:
			return []
	return []


func get_available_actions(state: SimState, expr: ExprEngine) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if GameData.current == null:
		return out
	expr.bind(state)
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.actions_def)
	var m05: Dictionary = _m05(state)
	var unlocked: Dictionary = _as_dict(m05.get("unlocked_actions", {}))
	var running: Dictionary = {}
	var active: Array = _as_array(m05.get("active_actions", []))
	for i: int in range(active.size()):
		running[String(_as_dict(active[i]).get("id", ""))] = true
	for i: int in range(ids.size()):
		var action_def: Dictionary = _as_dict(GameData.current.actions_def[ids[i]])
		if running.has(ids[i]):
			continue
		var cool: int = int(_as_dict(m05.get("action_cooldowns", {})).get(ids[i], -1))
		if cool > state.clock.day_index:
			continue
		if action_def.has("unlock_ast") and not expr.eval_bool(action_def["unlock_ast"], {}):
			continue
		if bool(action_def.get("locked", false)) and not bool(unlocked.get(ids[i], false)):
			continue
		out.append(action_def)
	return out


func compute_action_success_interval(state: SimState, action_def: Dictionary, _expr: ExprEngine) -> Dictionary:
	var capability: float = float(action_def.get("capability", 50.0))
	var intel: float = state.params.get_val("intel_accuracy", "", state)
	var mid: float = clampf(0.35 + capability / 200.0 + intel / 400.0, 0.05, 0.95)
	return {"p_lo": SimMath.quantize(maxf(0.0, mid - 0.08)), "p_hi": SimMath.quantize(minf(1.0, mid + 0.08))}


func sync_derived_policy_params(state: SimState) -> void:
	var exemption: float = state.params.get_val("policy_level", "haredi_exemption", state) * 12.0
	state.params.set_val("exemption_coverage", "", exemption, state)
	var enforcement: float = state.params.get_val("policy_level", "outpost_law", state) * 10.0
	state.params.set_val("outpost_enforcement", "", enforcement, state)


func _note_pc(state: SimState, income: float, spent: float) -> void:
	var m05: Dictionary = _m05(state)
	var ledger: Dictionary = _as_dict(m05.get("pc_ledger", {}))
	ledger["income"] = float(ledger.get("income", 0.0)) + income
	ledger["spent"] = float(ledger.get("spent", 0.0)) + spent
	m05["pc_ledger"] = ledger
	state.modules["M05"] = m05


func minister_proposal_cost(base_cost: int) -> int:
	return SimMath.round_half_up_int(float(base_cost) * 0.70)


func _enqueue(state: SimState) -> Array[Dictionary]:
	if state.clock.weekday == 6:
		var reset: Dictionary = _m05(state)
		reset["weekly_slots_used"] = 0
		state.modules["M05"] = reset
	var m05: Dictionary = _m05(state)
	var staged: Array = _as_array(m05.get("staged_actions", []))
	var running: Array = _as_array(m05.get("active_actions", []))
	var effects: Array[Dictionary] = []
	var keep: Array = []
	for i: int in range(staged.size()):
		var action: Dictionary = _as_dict(staged[i])
		var minister: bool = bool(action.get("is_minister_proposal", false))
		var used: int = int(m05.get("weekly_slots_used", 0))
		if not minister and used >= int(m05.get("weekly_slots_max", 2)):
			keep.append(action)
			continue
		var base_cost: int = int(action.get("pc_cost", 0))
		var cost: int = minister_proposal_cost(base_cost) if minister else base_cost
		var repeats: int = int(_as_dict(m05.get("completed_actions", {})).get(String(action.get("id", "")), 0))
		cost += repeats
		var pc: float = state.params.get_val("political_capital", "", state)
		if pc + 1.0e-6 < float(cost):
			if float(cost) - pc <= 10.0:
				state.params.set_val("party_standing", "", state.params.get_val("party_standing", "", state) - (float(cost) - pc), state)
				state.params.set_val("political_capital", "", 0.0, state)
			else:
				keep.append(action)
				continue
		else:
			state.params.set_val("political_capital", "", pc - float(cost), state)
		if not minister:
			m05["weekly_slots_used"] = used + 1
		running.append({
			"id": String(action.get("id", "")),
			"remaining_days": int(action.get("days", 7)),
			"effects": _as_array(action.get("effects", [])),
			"is_minister_proposal": minister,
		})
	m05["staged_actions"] = keep
	m05["active_actions"] = running
	state.modules["M05"] = m05
	return effects


func _advance(state: SimState) -> Array[Dictionary]:
	var m05: Dictionary = _m05(state)
	var running: Array = _as_array(m05.get("active_actions", []))
	var still: Array = []
	var effects: Array[Dictionary] = []
	var done: Dictionary = _as_dict(m05.get("completed_actions", {}))
	for i: int in range(running.size()):
		var action: Dictionary = _as_dict(running[i])
		action["remaining_days"] = int(action.get("remaining_days", 1)) - 1
		if int(action["remaining_days"]) <= 0:
			var action_id: String = String(action.get("id", ""))
			done[action_id] = int(done.get(action_id, 0)) + 1
			state.flags["act." + action_id] = {"value": 1.0, "set_day": state.clock.day_index, "source": "M05"}
			var extra: Array = _as_array(action.get("effects", []))
			for e: int in range(extra.size()):
				if typeof(extra[e]) == TYPE_DICTIONARY:
					effects.append(extra[e])
			effects.append({"op": "set_flag", "flag": "action_completed." + action_id, "value": 1.0})
		else:
			still.append(action)
	m05["active_actions"] = still
	m05["completed_actions"] = done
	state.modules["M05"] = m05
	return effects


func _favor(state: SimState, args: Dictionary, incurred: bool) -> Array[Dictionary]:
	var m05: Dictionary = _m05(state)
	var ledger: Array = _as_array(m05.get("iou_ledger", []))
	ledger.append({
		"who": String(args.get("who", args.get("party", ""))),
		"amount": float(args.get("amount", 1.0)),
		"due_day": state.clock.day_index + int(args.get("days", 90)),
		"incurred": incurred,
	})
	m05["iou_ledger"] = ledger
	if incurred:
		m05["iou_incurred_total"] = int(m05.get("iou_incurred_total", 0)) + int(args.get("amount", 1))
	state.modules["M05"] = m05
	return []


func _cancel(state: SimState, action_id: String) -> Array[Dictionary]:
	var m05: Dictionary = _m05(state)
	var running: Array = _as_array(m05.get("active_actions", []))
	var still: Array = []
	var refund: float = 0.0
	for i: int in range(running.size()):
		var action: Dictionary = _as_dict(running[i])
		if String(action.get("id", "")) == action_id:
			var total_days: float = maxf(1.0, float(action.get("total_days", action.get("remaining_days", 1))))
			var left: float = float(action.get("remaining_days", 0))
			refund += float(action.get("pc_cost", 0.0)) * 0.5 * left / total_days
		else:
			still.append(running[i])
	m05["active_actions"] = still
	state.modules["M05"] = m05
	if refund > 0.0:
		state.params.set_val("political_capital", "", state.params.get_val("political_capital", "", state) + refund, state)
		_note_pc(state, refund, 0.0)
	return []


func _m05(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M05", {}))
	state.modules["M05"] = current
	return current


func _policy_axis_level(state: SimState, pol_id: String, pol: Dictionary) -> float:
	var saved: Dictionary = _as_dict(state.policies.get(pol_id, {}))
	if saved.has("level"):
		return float(saved.get("level", 0.0))
	var live_levels: Dictionary = _as_dict(state.params.export_scoped().get("policy_level", {}))
	if live_levels.has(pol_id):
		return float(live_levels[pol_id])
	var tiers: Array = _as_array(pol.get("tiers", []))
	var start_raw: Variant = _as_dict(pol.get("start", {})).get("begin_1977", 0)
	if typeof(start_raw) == TYPE_DICTIONARY:
		var start_map: Dictionary = start_raw
		var start_keys: Array = start_map.keys()
		start_raw = start_map[start_keys[0]] if not start_keys.is_empty() else 0
	var idx: int = _tier_index(saved.get("tier_idx", start_raw), tiers.size())
	return _tier_scalar(tiers[idx]) if idx >= 0 and idx < tiers.size() else 0.0


func _tier_scalar(tier: Variant) -> float:
	if typeof(tier) == TYPE_DICTIONARY:
		return float((tier as Dictionary).get("v", 0.0))
	if typeof(tier) == TYPE_INT or typeof(tier) == TYPE_FLOAT:
		return float(tier)
	return 0.0


func _tier_index(raw: Variant, size: int) -> int:
	var idx: int = 0
	if typeof(raw) == TYPE_BOOL:
		idx = 1 if bool(raw) else 0
	elif typeof(raw) == TYPE_INT or typeof(raw) == TYPE_FLOAT:
		idx = int(floor(float(raw)))
	if size <= 0:
		return 0
	return clampi(idx, 0, size - 1)


func _tier_fiscal(tiers: Array, idx: int) -> float:
	if idx < 0 or idx >= tiers.size() or typeof(tiers[idx]) != TYPE_DICTIONARY:
		return 0.0
	return float((tiers[idx] as Dictionary).get("f", 0.0))


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
