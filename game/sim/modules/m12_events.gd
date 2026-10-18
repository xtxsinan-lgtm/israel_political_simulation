class_name M12Events
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const ANCHORS: Dictionary = {
	"E-1977-06": true, "E-1977-10": true, "E-1977-11": true, "E-1978-03": true,
	"E-1978-09": true, "E-1979-03": true, "E-1981-06a": true, "E-1982-06a": true,
	"E-1985-07": true, "E-1987-12a": true, "E-1991-01": true,
}


func _init() -> void:
	module_id = "M12"


func daily_step(step_no: int, state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 18:
		return []
	var expr: ExprEngine = _expr(ctx, state)
	var m12: Dictionary = _m12(state)
	_maintain(state, m12)
	var today: Array[Dictionary] = []
	_release_scheduled_events(state, m12, expr, today)
	_scan_fixed_events(state, m12, expr, today)
	_apply_throttle(state, m12, today)
	var pending: Array = _as_array(m12.get("pending_events", []))
	for i: int in range(today.size()):
		pending.append(today[i])
	m12["pending_events"] = pending
	_autoresolve_minors(state, m12, ctx)
	if bool(ctx.get("headless", state.run.get("headless", false))):
		_resolve_queue_headless(state, m12, ctx)
	m12["scheduled_events"] = _as_array(m12.get("scheduled_events", []))
	state.modules["M12"] = m12
	return []


func resolve_event_choice(state: SimState, event_id: String, option_id: String, ctx: Dictionary) -> Array[Dictionary]:
	var m12: Dictionary = _m12(state)
	var fired: Dictionary = _as_dict(m12.get("fired", {}))
	fired[event_id] = option_id
	m12["fired"] = fired
	var last: Dictionary = _as_dict(state.history.get("event_last_day", {}))
	last[event_id] = state.clock.day_index
	state.history["event_last_day"] = last
	var effects: Array[Dictionary] = []
	var ev: Dictionary = _event_def(event_id)
	var options: Array = _as_array(ev.get("options", []))
	for i: int in range(options.size()):
		var opt: Dictionary = _as_dict(options[i])
		if String(opt.get("id", "")) != option_id:
			continue
		var raw: Variant = opt.get("effects", [])
		if typeof(raw) == TYPE_ARRAY:
			var effect_rows: Array = raw
			for j: int in range(effect_rows.size()):
				if typeof(effect_rows[j]) == TYPE_DICTIONARY:
					effects.append(effect_rows[j])
	var queue: Array = _as_array(m12.get("pending_events", []))
	var kept: Array = []
	for i: int in range(queue.size()):
		if String(_as_dict(queue[i]).get("id", "")) != event_id:
			kept.append(queue[i])
	m12["pending_events"] = kept
	state.modules["M12"] = m12
	var processor: Variant = ctx.get("processor", null)
	if processor is EffectProcessor and not effects.is_empty():
		(processor as EffectProcessor).apply_effects(effects, ctx, state, 0)
		return []
	return effects


func evaluate_event_options_for_ui(event_id: String, state: SimState) -> Array[Dictionary]:
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(state)
	var ev: Dictionary = _event_def(event_id)
	var options: Array = _as_array(ev.get("options", []))
	var out: Array[Dictionary] = []
	for i: int in range(options.size()):
		var opt: Dictionary = _as_dict(options[i])
		var available: bool = true
		var reasons: Array[String] = []
		if opt.has("available_ast"):
			available = expr.eval_bool(opt["available_ast"], {})
			if not available:
				reasons.append(String(opt.get("locked_reason_zh", "条件未满足")))
		var pc_need: float = float(opt.get("pc_cost", 0.0))
		var pc_have: float = state.params.get_val("political_capital", "", state)
		if pc_need > pc_have:
			available = false
			reasons.append("需要政治资本 ≥ %d，当前 %d" % [int(pc_need), int(pc_have)])
		out.append({
			"id": String(opt.get("id", "A")),
			"available": available,
			"lock_reasons": reasons,
			"preview_l1": String(opt.get("summary", "")),
			"preview_l2": "盟党与内阁将按立场作出反应",
			"preview_hidden": "可能引发后续外交连锁反应",
		})
	return out


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	var m12: Dictionary = _m12(state)
	match op_name:
		"m12_enqueue_event":
			var scheduled: Array = _as_array(m12.get("scheduled_events", []))
			scheduled.append({
				"event_id": String(args.get("event", "")),
				"due_day": state.clock.day_index + int(args.get("delay_days", 1)),
			})
			m12["scheduled_events"] = scheduled
			state.modules["M12"] = m12
			state.push_scheduled_event_heap(scheduled[scheduled.size() - 1])
			return []
		"m12_suppress_event":
			var suppressed: Dictionary = _as_dict(m12.get("suppressed_events", {}))
			suppressed[String(args.get("event", ""))] = state.clock.day_index + int(args.get("days", 30))
			m12["suppressed_events"] = suppressed
			state.modules["M12"] = m12
			return []
		"m12_start_chain":
			var chains: Dictionary = _as_dict(m12.get("active_chains", {}))
			chains[String(args.get("chain", ""))] = {"stage": 0, "started_day": state.clock.day_index}
			m12["active_chains"] = chains
			state.modules["M12"] = m12
			return []
		"m12_advance_chain":
			var live: Dictionary = _as_dict(m12.get("active_chains", {}))
			var chain_id: String = String(args.get("chain", ""))
			var row: Dictionary = _as_dict(live.get(chain_id, {}))
			row["stage"] = int(row.get("stage", 0)) + 1
			live[chain_id] = row
			m12["active_chains"] = live
			state.modules["M12"] = m12
			return handle_custom_op("m12_enqueue_event", state, {"event": String(args.get("next", "")), "delay_days": int(args.get("delay_days", 7))}, {})
		"m12_end_chain":
			var ending: Dictionary = _as_dict(m12.get("active_chains", {}))
			var finished: String = String(args.get("chain", ""))
			var archived: Array = _as_array(m12.get("archived_chains", []))
			archived.append({"id": finished, "day": state.clock.day_index, "row": ending.get(finished, {})})
			ending.erase(finished)
			m12["active_chains"] = ending
			m12["archived_chains"] = archived
			state.modules["M12"] = m12
			return []
		_:
			return []
	return []


func _maintain(state: SimState, m12: Dictionary) -> void:
	var cool: Dictionary = _as_dict(m12.get("event_cooldowns", {}))
	var keys: Array[String] = SimMath.sorted_keys(cool)
	for i: int in range(keys.size()):
		if int(cool[keys[i]]) <= state.clock.day_index:
			cool.erase(keys[i])
	m12["event_cooldowns"] = cool
	var suppressed: Dictionary = _as_dict(m12.get("suppressed_events", {}))
	var skeys: Array[String] = SimMath.sorted_keys(suppressed)
	for i: int in range(skeys.size()):
		if int(suppressed[skeys[i]]) <= state.clock.day_index:
			suppressed.erase(skeys[i])
	m12["suppressed_events"] = suppressed


func _release_scheduled_events(state: SimState, m12: Dictionary, expr: ExprEngine, today: Array[Dictionary]) -> void:
	var due: Array[Dictionary] = SimContainers.heap_pop_all_due(state.scheduled_events, state.clock.day_index)
	for i: int in range(due.size()):
		var event_id: String = String(due[i].get("event_id", ""))
		if event_id == "" or _as_dict(m12.get("fired", {})).has(event_id):
			continue
		var ev: Dictionary = _event_def(event_id)
		var trig: Dictionary = _as_dict(ev.get("trigger", {}))
		if trig.has("invalidation_ast") and expr.eval_bool(trig["invalidation_ast"], {}):
			continue
		today.append(_instantiate(ev))


func _scan_fixed_events(state: SimState, m12: Dictionary, expr: ExprEngine, today: Array[Dictionary]) -> void:
	if GameData.current == null:
		return
	var rng: SimRNG.Stream = state.rng.get_stream("events")
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.events_def)
	var fired: Dictionary = _as_dict(m12.get("fired", {}))
	var suppressed: Dictionary = _as_dict(m12.get("suppressed_events", {}))
	var cool: Dictionary = _as_dict(m12.get("event_cooldowns", {}))
	for i: int in range(ids.size()):
		var ev: Dictionary = _as_dict(GameData.current.events_def[ids[i]])
		var event_id: String = String(ev.get("id", ids[i]))
		if fired.has(event_id) or suppressed.has(event_id):
			continue
		if int(cool.get(event_id, -1)) > state.clock.day_index:
			continue
		if not _in_window(state, ev):
			continue
		var trig: Dictionary = _as_dict(ev.get("trigger", {}))
		if trig.has("trigger_ast") and not expr.eval_bool(trig["trigger_ast"], {}):
			continue
		var anchor: bool = ANCHORS.has(event_id) or String(ev.get("type", "")) == "anchor" or int(ev.get("priority", 0)) >= 100 or bool(ev.get("mandatory", false))
		var daily_p: float = 1.0 if anchor else 0.02
		var prob: Dictionary = _as_dict(trig.get("probability", {}))
		if not anchor and prob.has("base"):
			daily_p = float(prob.get("base", daily_p))
		var period: String = String(prob.get("period", "day"))
		if period == "month":
			daily_p = daily_p / 30.0
		elif period == "week":
			daily_p = daily_p / 7.0
		if daily_p <= 0.0 or not rng.chance(clampf(daily_p, 0.0, 1.0)):
			continue
		today.append(_instantiate(ev))
		break


func _apply_throttle(state: SimState, m12: Dictionary, today: Array[Dictionary]) -> void:
	var count: int = int(m12.get("major_events_this_month", 0))
	var kept: Array[Dictionary] = []
	for i: int in range(today.size()):
		var row: Dictionary = today[i]
		var modal: String = String(row.get("modal_class", "minor"))
		var major: bool = modal == "major" or modal == "crisis" or modal == "chain_milestone" or bool(row.get("major", false))
		if major and not bool(row.get("bypass_cap", false)) and count >= 3:
			continue
		if major:
			count += 1
		kept.append(row)
	today.clear()
	for i: int in range(kept.size()):
		today.append(kept[i])
	m12["major_events_this_month"] = count


func _autoresolve_minors(state: SimState, m12: Dictionary, ctx: Dictionary) -> void:
	var pending: Array = _as_array(m12.get("pending_events", []))
	var kept: Array = []
	for i: int in range(pending.size()):
		var row: Dictionary = _as_dict(pending[i])
		if String(row.get("modal_class", "")) == "minor" and bool(state.run.get("advisor_auto", false)):
			var option_id: String = String(row.get("ai_default_option", "A"))
			resolve_event_choice(state, String(row.get("id", "")), option_id, ctx)
		else:
			kept.append(row)
	m12["pending_events"] = kept


func _resolve_queue_headless(state: SimState, m12: Dictionary, ctx: Dictionary) -> void:
	var pending: Array = _as_array(m12.get("pending_events", []))
	for i: int in range(pending.size()):
		var row: Dictionary = _as_dict(pending[i])
		var option_id: String = _historical_option(row)
		resolve_event_choice(state, String(row.get("id", "")), option_id, ctx)
	m12["pending_events"] = []


func _historical_option(row: Dictionary) -> String:
	var options: Array = _as_array(row.get("options", []))
	for i: int in range(options.size()):
		var opt: Dictionary = _as_dict(options[i])
		if bool(opt.get("historical", false)):
			return String(opt.get("id", "A"))
	if options.is_empty():
		return "A"
	return String(_as_dict(options[0]).get("id", "A"))


func _instantiate(ev: Dictionary) -> Dictionary:
	var modal: String = "minor"
	if bool(ev.get("major", false)):
		modal = "major"
	return {
		"id": String(ev.get("id", "")),
		"title": String(ev.get("title", "")),
		"modal_class": modal,
		"major": bool(ev.get("major", false)),
		"bypass_cap": bool(ev.get("bypass_cap", false)),
		"options": _as_array(ev.get("options", [])),
		"ai_default_option": "A",
	}


func _in_window(state: SimState, ev: Dictionary) -> bool:
	var trig: Dictionary = _as_dict(ev.get("trigger", {}))
	var window: Dictionary = _as_dict(trig.get("window", {}))
	var start: String = String(window.get("from", ""))
	var end: String = String(window.get("to", ""))
	if start != "" and state.clock.date < start:
		return false
	if end != "" and state.clock.date > end:
		return false
	return true


func _event_def(event_id: String) -> Dictionary:
	if GameData.current == null:
		return {}
	return _as_dict(GameData.current.events_def.get(event_id, {}))


func _m12(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M12", {}))
	if not current.has("fired"):
		current["fired"] = {}
		current["pending_events"] = []
		current["scheduled_events"] = []
		current["suppressed_events"] = {}
		current["event_cooldowns"] = {}
		current["active_chains"] = {}
		current["major_events_this_month"] = 0
	state.modules["M12"] = current
	return current


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


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
