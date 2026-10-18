class_name DailyScheduler
extends RefCounted

var m01: M01Core = M01Core.new()
var m02: M02Contradictions = M02Contradictions.new()
var m03: M03Parliament = M03Parliament.new()
var m04: M04Party = M04Party.new()
var m05: M05Actions = M05Actions.new()
var m06: M06Characters = M06Characters.new()
var m07: M07Diplomacy = M07Diplomacy.new()
var m08: M08Palestine = M08Palestine.new()
var m09: M09Military = M09Military.new()
var m10: M10Economy = M10Economy.new()
var m11: M11Regions = M11Regions.new()
var m12: M12Events = M12Events.new()
var m13: M13Centralization = M13Centralization.new()
var m14: M14Endings = M14Endings.new()
var processor: EffectProcessor = EffectProcessor.new()
var expr: ExprEngine = ExprEngine.new()
var trace: Array[String] = []


func _init() -> void:
	processor.causal_net = CausalNet.new()
	processor.modules = {
		"M01": m01, "M02": m02, "M03": m03, "M04": m04, "M05": m05,
		"M06": m06, "M07": m07, "M08": m08, "M09": m09, "M10": m10,
		"M11": m11, "M12": m12, "M13": m13, "M14": m14,
	}


func execute_day(state: SimState, bot: Variant = null) -> Dictionary:
	return execute_single_day(state, bot)


func execute_single_day(state: SimState, bot: Variant = null) -> Dictionary:
	trace.clear()
	if String(state.run.get("phase", "")) == "ENDED":
		return {"day_index": state.clock.day_index, "date": state.clock.date, "ended": true}
	var ctx: Dictionary = _ctx(state)
	if bot is Object and state.clock.is_week and (bot as Object).has_method("on_week"):
		(bot as Object).call("on_week", state)
	_run(m01.daily_step(1, state, ctx), state)
	trace.append("1")
	_run(m05.daily_step(2, state, ctx), state)
	trace.append("2")
	_run(m09.daily_step(3, state, ctx), state)
	trace.append("3")
	_run(m07.daily_step(4, state, ctx), state)
	trace.append("4")
	_run(m05.daily_step(5, state, ctx), state)
	trace.append("5")
	if state.clock.is_week:
		_run(m06.weekly_step(6, state, ctx), state)
		trace.append("6")
		_run(m03.weekly_step(7, state, ctx), state)
		trace.append("7")
		_run_step_8_locked_sequence(state, ctx)
		trace.append("8")
	if state.clock.is_month:
		_run(m10.monthly_step(9, state, ctx), state)
		trace.append("9")
		_run(m02.monthly_step(10, state, ctx), state)
		trace.append("10")
		_run(m04.monthly_step(11, state, ctx), state)
		trace.append("11")
		_run(m07.monthly_step(12, state, ctx), state)
		_run(m08.monthly_step(12, state, ctx), state)
		trace.append("12")
		_run_step_13_locked_sequence(state, ctx)
		trace.append("13")
		_run(m13.monthly_step(14, state, ctx), state)
		trace.append("14")
		_run(m05.monthly_step(15, state, ctx), state)
		m01.record_monthly_ring_snapshot(state)
		trace.append("15")
	if state.clock.is_quarter:
		_run(m02.step_tick(16, state, ctx, "quarterly"), state)
		_run(m10.quarterly_step(16, state, ctx), state)
		trace.append("16")
	if state.clock.is_year:
		_run(m02.step_tick(17, state, ctx, "yearly"), state)
		_run_step_17_locked_sequence(state, ctx)
		trace.append("17")
	_run(m12.daily_step(18, state, ctx), state)
	trace.append("18")
	var votes: Variant = state.pending.get("vote_requests", [])
	if typeof(votes) == TYPE_ARRAY and not (votes as Array).is_empty():
		_run(m03.daily_step(19, state, ctx), state)
		trace.append("19")
	_run(m01.daily_step(19, state, ctx), state)
	_run(m14.daily_step(20, state, ctx), state)
	trace.append("20")
	var paused: bool = AutoPauseEvaluator.should_auto_pause(state)
	state.run["paused"] = paused
	var ending: String = String(_dict(state.modules.get("M14", {})).get("primary_ending_id", ""))
	return {
		"day_index": state.clock.day_index,
		"date": state.clock.date,
		"ended": String(state.run.get("phase", "")) == "ENDED",
		"ending_id": ending,
		"paused": paused,
		"trace": ",".join(trace),
	}


func _run_step_8_locked_sequence(state: SimState, ctx: Dictionary) -> void:
	_run(m11.weekly_step(8, state, ctx), state)
	_run(m09.weekly_step(8, state, ctx), state)
	_run(m08.weekly_step(8, state, ctx), state)


func _run_step_13_locked_sequence(state: SimState, ctx: Dictionary) -> void:
	_run(m11.monthly_step(13, state, ctx), state)


func _run_step_17_locked_sequence(state: SimState, ctx: Dictionary) -> void:
	_run(m10.annual_step(17, state, ctx), state)
	_run(m06.annual_step(17, state, ctx), state)
	_run(m11.annual_step(17, state, ctx), state)


func _ctx(state: SimState) -> Dictionary:
	expr.bind(state)
	return {
		"processor": processor,
		"expr": expr,
		"modules": {
			"M01": m01, "M02": m02, "M03": m03, "M04": m04, "M05": m05,
			"M06": m06, "M07": m07, "M08": m08, "M09": m09, "M10": m10,
			"M11": m11, "M12": m12, "M13": m13, "M14": m14,
		},
		"headless": bool(state.run.get("headless", false)),
		"step_no": state.clock.day_index,
	}


func _run(effects: Array[Dictionary], state: SimState) -> void:
	if effects.is_empty():
		return
	processor.apply_effects(effects, _ctx(state), state, 0)


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
