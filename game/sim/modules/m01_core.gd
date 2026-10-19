class_name M01Core
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M01"


func daily_step(step_no: int, state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	if step_no == 1:
		return _step_1(state, ctx)
	if step_no == 19:
		_record_daily_history(state)
		return []
	return []


func record_monthly_ring_snapshot(state: SimState) -> void:
	var snap: Dictionary = {
		"day_index": state.clock.day_index,
		"date": state.clock.date,
		"political_capital": state.params.get_val("political_capital", "", state),
		"public_security": state.params.get_val("public_security", "", state),
		"inflation": state.params.get_val("inflation", "", state),
	}
	state.monthly_snapshots.append(snap)
	while state.monthly_snapshots.size() > 24:
		state.monthly_snapshots.pop_front()


func _step_1(state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	state._set_clock(state.clock.start_date, state.clock.day_index + 1)
	if state.clock.is_month:
		var m10: Dictionary = _as_dict(state.modules.get("M10", {}))
		m10["last_one_off_flow"] = float(state.one_off_flows.get("budget_balance", 0.0))
		state.one_off_flows["budget_balance"] = 0.0
		state.modules["M10"] = m10
		state.counters.forced_popups_month = 0
		var m12: Dictionary = _as_dict(state.modules.get("M12", {}))
		m12["major_events_this_month"] = 0
		m12["month_random_count"] = 0
		state.modules["M12"] = m12
		var impulse_axes: Array[String] = ["territory", "security", "economy", "religion", "foreign"]
		for axis_i: int in range(impulse_axes.size()):
			var axis_name: String = impulse_axes[axis_i]
			if state.axis_impulse.has(axis_name):
				state.axis_impulse[axis_name] = SimMath.quantize(float(state.axis_impulse[axis_name]) * 0.95)
	if state.clock.is_week:
		var m05: Dictionary = _as_dict(state.modules.get("M05", {}))
		m05["weekly_slots_used"] = 0
		state.modules["M05"] = m05
	var expr: ExprEngine = _expr(ctx, state)
	var follow: Array[Dictionary] = state.modifiers.expire_and_check_remove_if(state, expr)
	state.modifiers.tick_debt_modifiers(state)
	var due: Array[Dictionary] = SimContainers.heap_pop_all_due(state.delayed_effects, state.clock.day_index)
	for i: int in range(due.size()):
		follow.append(due[i])
	var processor: Variant = ctx.get("processor", null)
	if processor is EffectProcessor and not follow.is_empty():
		(processor as EffectProcessor).apply_effects(follow, ctx, state, 0)
		return []
	return follow


func _record_daily_history(state: SimState) -> void:
	var ring: Array = []
	var hist: Dictionary = state.history
	if hist.has("daily_ring") and typeof(hist["daily_ring"]) == TYPE_ARRAY:
		ring = hist["daily_ring"]
	ring.append({
		"day_index": state.clock.day_index,
		"date": state.clock.date,
		"public_security": state.params.get_val("public_security", "", state),
		"inflation": state.params.get_val("inflation", "", state),
		"political_capital": state.params.get_val("political_capital", "", state),
	})
	while ring.size() > 365:
		ring.pop_front()
	hist["daily_ring"] = ring
	state.history = hist
	_scan_alerts(state)


func _scan_alerts(state: SimState) -> void:
	var alerts: Array[String] = []
	if state.params.get_val("coalition_seats", "", state) < 61.0:
		alerts.append("coalition_minority")
	if state.params.get_val("inflation", "", state) >= 100.0:
		alerts.append("inflation_red")
	elif state.params.get_val("inflation", "", state) >= 50.0:
		alerts.append("inflation_yellow")
	if state.params.get_val("public_security", "", state) <= 35.0:
		alerts.append("security_red")
	state.history["active_alerts"] = alerts


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, ctx: Dictionary) -> Array[Dictionary]:
	match op_name:
		"if_then":
			var cond: Variant = args.get("cond_ast", args.get("cond", args.get("condition", "true")))
			var take_then: bool = _expr(ctx, state).eval_bool(cond, {})
			return _as_effect_list(args.get("then", []) if take_then else args.get("else", []))
		"random_branch":
			var branches: Array = _as_array(args.get("branches", []))
			if branches.is_empty():
				return []
			var weights: PackedFloat64Array = PackedFloat64Array()
			for i: int in range(branches.size()):
				weights.append(float(_as_dict(branches[i]).get("weight", 1.0)))
			var chosen: Variant = _stream(state, ctx).weighted_pick(branches, weights)
			if typeof(chosen) != TYPE_DICTIONARY:
				return []
			return _as_effect_list((chosen as Dictionary).get("effects", []))
		"add_all_keys":
			var t_param: String = String(args.get("target", "bloc_support"))
			var delta: float = float(args.get("value", 0.0))
			var exclude: Array = _as_array(args.get("exclude", []))
			var keys: Array[String] = []
			var listed: Array = _as_array(args.get("keys", []))
			if listed.size() == 1 and String(listed[0]) == "cabinet":
				var offices: Dictionary = _as_dict(_as_dict(state.modules.get("M06", {})).get("offices", {}))
				var office_ids: Array[String] = SimMath.sorted_keys(offices)
				for i: int in range(office_ids.size()):
					var holder: String = str(offices[office_ids[i]]) if offices[office_ids[i]] != null else ""
					if holder != "" and not keys.has(holder):
						keys.append(holder)
			elif not listed.is_empty():
				for i: int in range(listed.size()):
					keys.append(String(listed[i]))
			else:
				keys = state.params.get_active_keys(t_param)
			for i: int in range(keys.size()):
				var k: String = keys[i]
				if exclude.has(k):
					continue
				state.params.set_val(t_param, k, state.params.get_val(t_param, k, state) + delta, state)
			return []
		"schedule_event_window":
			var ev_id: String = String(args.get("event", ""))
			var stream: SimRNG.Stream = _stream(state, ctx)
			if ev_id != "" and stream.chance(float(args.get("chance", 1.0))):
				var wait_days: int = stream.range_int(int(args.get("min_days", 7)), int(args.get("max_days", 30)))
				state.push_scheduled_event_heap({"event_id": ev_id, "due_day": state.clock.day_index + wait_days, "source": "schedule_event_window"})
			return []
		"end_tenure", "m01_trigger_tenure_end":
			var reason: String = str(args.get("reason", args.get("value", "resignation")))
			if reason == "":
				reason = "resignation"
			state.pending["tenure_end"] = reason
			return []
		"m01_raise_signal":
			var hooks: Array = _as_array(state.pending.get("hooks", []))
			hooks.append({"signal": String(args.get("signal", "generic")), "day": state.clock.day_index, "payload": args.get("payload", {})})
			state.pending["hooks"] = hooks
			return []
		"m01_force_pause":
			var pauses: Array = _as_array(state.pending.get("pause_signals", []))
			pauses.append(String(args.get("reason_zh", "重大事态暂停")))
			state.pending["pause_signals"] = pauses
			return []
		"m01_set_player_party":
			state.player["party_id"] = String(args.get("party", "new_party_a"))
			return []
		"activate_key":
			var p_on: String = String(args.get("param", ""))
			var k_on: String = String(args.get("key", ""))
			if p_on != "" and k_on != "":
				state.params.activate_key(p_on, k_on, float(args.get("value", 35.0)))
				state.params.set_val(p_on, k_on, float(args.get("value", 35.0)), state)
			return []
		"deactivate_key":
			return []
		_:
			return []
	return []


func _stream(state: SimState, ctx: Dictionary) -> SimRNG.Stream:
	return state.rng.get_stream(String(ctx.get("stream_name", "events")))


func _as_effect_list(value: Variant) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	var raw: Array = _as_array(value)
	for i: int in range(raw.size()):
		if typeof(raw[i]) == TYPE_DICTIONARY:
			out.append(raw[i])
	return out


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []


func _expr(ctx: Dictionary, state: SimState) -> ExprEngine:
	var existing: Variant = ctx.get("expr", null)
	if existing is ExprEngine:
		(existing as ExprEngine).bind(state)
		return existing
	var created: ExprEngine = ExprEngine.new()
	created.bind(state)
	return created


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
