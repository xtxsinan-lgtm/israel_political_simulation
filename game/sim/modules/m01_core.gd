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
		state.counters.forced_popups_month = 0
		var m12: Dictionary = _as_dict(state.modules.get("M12", {}))
		m12["major_events_this_month"] = 0
		m12["month_random_count"] = 0
		state.modules["M12"] = m12
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
