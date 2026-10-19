class_name EffectProcessor
extends RefCounted

const MAX_CUSTOM_DEPTH: int = 3

var expr_engine: ExprEngine = null
var causal_net: CausalNet = null
var modules: Dictionary = {}


func apply_effects(raw_effects: Array, step_ctx: Dictionary, state: SimState, depth: int = 0) -> void:
	if raw_effects.is_empty():
		return
	if depth > MAX_CUSTOM_DEPTH:
		state.record_error("E_CUSTOM_DEPTH", "Custom effect recursion depth exceeded 3")
		return
	if expr_engine == null:
		expr_engine = ExprEngine.new()
	expr_engine.bind(state)
	var rng_stream: SimRNG.Stream = state.rng.get_stream(String(step_ctx.get("stream_name", "core")))
	var step_owner_mod: String = String(step_ctx.get("module_id", ""))
	var active_effects: Array[Dictionary] = []
	var seq_counter: int = 0
	for i: int in range(raw_effects.size()):
		if typeof(raw_effects[i]) != TYPE_DICTIONARY:
			continue
		var eff: Dictionary = (raw_effects[i] as Dictionary).duplicate(true)
		eff["seq"] = seq_counter
		seq_counter += 1
		var delay_d: int = int(eff.get("delay_days", 0))
		if delay_d > 0 and String(eff.get("op", "")) != "schedule_event":
			if state.delayed_effects.size() >= 2000:
				state.record_error("W_CAPACITY", "delayed_effects capacity (2000) exceeded")
				continue
			eff["delay_days"] = 0
			eff["due_day"] = state.clock.day_index + delay_d
			eff["delayed_seq"] = state.counters.next_delayed_seq
			state.counters.next_delayed_seq += 1
			state.push_delayed_effect_heap(eff)
			continue
		if not _validate_effect_schema(eff, step_owner_mod, state):
			continue
		if eff.has("chance") and eff["chance"] != null:
			if not rng_stream.chance(float(eff["chance"])):
				continue
		eff["_computed_scale"] = _eval_scale(eff, step_ctx)
		active_effects.append(eff)
	var mod_changed: bool = false
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		if String(eff.get("op", "")) == "remove_modifier":
			state.modifiers.remove_modifier(String(eff.get("modifier", eff.get("key", ""))), _extract_mod_scope_key(eff), state)
			mod_changed = true
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		if String(eff.get("op", "")) == "add_modifier":
			var opts: Dictionary = {}
			if typeof(eff.get("value", {})) == TYPE_DICTIONARY:
				opts = eff.get("value", {})
			else:
				opts = {}
			if eff.has("duration_days"):
				opts = opts.duplicate()
				opts["duration_days"] = eff["duration_days"]
			state.modifiers.add_modifier(String(eff.get("modifier", eff.get("key", ""))), opts, String(eff.get("source", "")), state)
			mod_changed = true
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		if String(eff.get("op", "")) == "clear_flag":
			state.flags.erase(String(eff.get("flag", eff.get("key", ""))))
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		if String(eff.get("op", "")) == "set_flag":
			var flag_id: String = String(eff.get("flag", eff.get("key", "")))
			var f_val: float = float(eff.get("value", 1.0))
			if state.flags.has(flag_id) and typeof(state.flags[flag_id]) == TYPE_DICTIONARY:
				var row: Dictionary = state.flags[flag_id]
				row["value"] = f_val
				if String(eff.get("source", "")) != "":
					row["source"] = String(eff.get("source", ""))
				state.flags[flag_id] = row
			else:
				state.flags[flag_id] = {"set_day": state.clock.day_index, "value": f_val, "source": String(eff.get("source", ""))}
	if mod_changed:
		state.modifiers.invalidate_factor_cache()
	var grouped_numeric: Dictionary = {}
	var group_order: Array[String] = []
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		var op: String = String(eff.get("op", ""))
		if op != "add" and op != "set" and op != "mul" and op != "add_relation":
			continue
		var target_param: String = "relation" if op == "add_relation" else GameData.current.resolve_param_alias(String(eff.get("target", "")))
		var resolved_key: String = state.params.resolve_key_for_write(target_param, String(eff.get("key", "")), state)
		if resolved_key == "__INVALID_EMPTY_OFFICE__":
			continue
		if target_param == "budget_balance" and op == "add" and step_owner_mod != "M10":
			var flow_delta: float = float(eff.get("value", 0.0)) * float(eff.get("_computed_scale", 1.0))
			state.one_off_flows["budget_balance"] = SimMath.quantize(float(state.one_off_flows.get("budget_balance", 0.0)) + flow_delta)
			state.record_contrib("budget_balance", "", String(eff.get("source", "event")), flow_delta)
			continue
		var g_key: String = target_param + "|" + resolved_key
		if not grouped_numeric.has(g_key):
			grouped_numeric[g_key] = []
			group_order.append(g_key)
		var bucket: Array = grouped_numeric[g_key]
		bucket.append(eff)
		grouped_numeric[g_key] = bucket
	for i: int in range(group_order.size()):
		_apply_numeric_group(group_order[i], grouped_numeric[group_order[i]], step_owner_mod, state)
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		if String(eff.get("op", "")) != "change_seat":
			continue
		if not modules.has("M03") or not (modules["M03"] is SimModuleBase):
			state.record_error("E_UNKNOWN_CUSTOM", "m03_apply_seat_change")
			continue
		var seat_mod: SimModuleBase = modules["M03"]
		var seat_args: Dictionary = {
			"party": String(eff.get("key", "")),
			"delta": SimMath.round_half_up_int(float(eff.get("value", 0.0)) * float(eff.get("_computed_scale", 1.0))),
		}
		var seat_followup: Array[Dictionary] = seat_mod.handle_custom_op("m03_apply_seat_change", state, seat_args, step_ctx)
		if not seat_followup.is_empty():
			apply_effects(seat_followup, step_ctx, state, depth + 1)
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		var op: String = String(eff.get("op", ""))
		if op != "custom" and op != "random_branch" and op != "if":
			continue
		var handler_name: String = String(eff.get("handler", ""))
		var custom_name: String = op if op != "custom" else handler_name
		if custom_name == "":
			custom_name = String(eff.get("key", eff.get("custom", "")))
		if custom_name == "if":
			custom_name = "if_then"
		var raw_args: Variant = eff.get("value", eff.get("args", {}))
		var custom_args: Dictionary = raw_args if typeof(raw_args) == TYPE_DICTIONARY else {"value": raw_args}
		if handler_name != "" and not custom_args.has("axis"):
			custom_args["axis"] = String(eff.get("key", "territory"))
		if eff.has("direction") and not custom_args.has("direction"):
			custom_args["direction"] = String(eff.get("direction"))
		var passthrough: Array[String] = ["reason", "signal", "event", "branches", "cond", "then", "else"]
		for p_i: int in range(passthrough.size()):
			var p_key: String = passthrough[p_i]
			if eff.has(p_key) and not custom_args.has(p_key):
				custom_args[p_key] = eff[p_key]
		var owner_mod: String = GameData.current.get_custom_handler_owner(custom_name)
		if owner_mod == "" or not modules.has(owner_mod) or not (modules[owner_mod] is SimModuleBase):
			state.record_error("E_UNKNOWN_CUSTOM", "Unregistered custom op: " + custom_name)
			continue
		var owner: SimModuleBase = modules[owner_mod]
		var child_effects: Array[Dictionary] = owner.handle_custom_op(custom_name, state, custom_args, step_ctx)
		if not child_effects.is_empty():
			apply_effects(child_effects, step_ctx, state, depth + 1)
	for i: int in range(active_effects.size()):
		var mult_eff: Dictionary = active_effects[i]
		if String(mult_eff.get("op", "")) != "event_multiplier":
			continue
		var mult_event: String = String(mult_eff.get("event", mult_eff.get("key", "")))
		if mult_event == "":
			continue
		var m12_box: Dictionary = _as_dict(state.modules.get("M12", {}))
		var multipliers: Dictionary = _as_dict(m12_box.get("multipliers", {}))
		var next_mult: float = float(multipliers.get(mult_event, 1.0)) * float(mult_eff.get("value", 1.0)) * float(mult_eff.get("_computed_scale", 1.0))
		multipliers[mult_event] = SimMath.quantize(next_mult)
		m12_box["multipliers"] = multipliers
		state.modules["M12"] = m12_box
	for i: int in range(active_effects.size()):
		var eff: Dictionary = active_effects[i]
		var op: String = String(eff.get("op", ""))
		if op == "trigger_event":
			var ev_id: String = String(eff.get("event", eff.get("key", "")))
			if ev_id != "" and not state.forced_events.has(ev_id):
				state.forced_events.append(ev_id)
		elif op == "schedule_event":
			var ev_id: String = String(eff.get("event", eff.get("key", "")))
			var d_days: int = maxi(1, int(eff.get("delay_days", eff.get("value", 1))))
			state.push_scheduled_event_heap({
				"event_id": ev_id,
				"due_day": state.clock.day_index + d_days,
				"seq": state.counters.next_delayed_seq,
			})
			state.counters.next_delayed_seq += 1
	state.process_pending_signals()


func _apply_numeric_group(g_key: String, group_v: Variant, step_owner_mod: String, state: SimState) -> void:
	var parts: PackedStringArray = g_key.split("|", true, 1)
	var param_id: String = parts[0]
	var scope_key: String = parts[1] if parts.size() > 1 else ""
	var group: Array = _as_array(group_v)
	var has_set: bool = false
	var max_priority: int = -999999
	var best_seq: int = -1
	var old_val: float = state.params.get_val(param_id, scope_key, state)
	var v_base: float = old_val
	for i: int in range(group.size()):
		var eff: Dictionary = _as_dict(group[i])
		if String(eff.get("op", "")) != "set":
			continue
		var priority: int = int(eff.get("priority", 0))
		var seq: int = int(eff.get("seq", 0))
		if not has_set or priority > max_priority or (priority == max_priority and seq >= best_seq):
			has_set = true
			max_priority = priority
			best_seq = seq
			v_base = float(eff.get("value", 0.0))
	var is_owner_set: bool = has_set and max_priority >= 100
	var prod: float = 1.0
	var delta_sum: float = 0.0
	for i: int in range(group.size()):
		var eff: Dictionary = _as_dict(group[i])
		var op: String = String(eff.get("op", ""))
		var scale: float = float(eff.get("_computed_scale", 1.0))
		if op == "mul":
			var m_eff: float = 1.0 + (float(eff.get("value", 1.0)) - 1.0) * scale
			prod *= m_eff
		elif op == "add" or op == "add_relation":
			var pdef: Dictionary = {}
			if GameData.current != null:
				pdef = _as_dict(GameData.current.parameters_def.get(param_id, {}))
			var delta: float = float(eff.get("value", 0.0)) * scale
			var debt: bool = String(pdef.get("type", "")) == "debt" or param_id == "draft_exemption" or param_id == "historical_grievance" or param_id == "land_grievance"
			var source: String = String(eff.get("source", ""))
			if debt and op == "add" and delta < 0.0 and not source.begins_with("act.") and step_owner_mod != "M02":
				state.record_error("W_DEBT_DECREASE", param_id)
				continue
			delta_sum += delta
	var v_after_mul: float = v_base * prod
	var v_new: float = state.params.set_val(param_id, scope_key, v_after_mul + delta_sum, state)
	if causal_net != null and not is_owner_set:
		for i: int in range(group.size()):
			var eff: Dictionary = _as_dict(group[i])
			if String(eff.get("op", "")) != "add" and String(eff.get("op", "")) != "add_relation":
				continue
			var actual: float = float(eff.get("value", 0.0)) * float(eff.get("_computed_scale", 1.0))
			causal_net.on_effect_applied(state, param_id, scope_key, actual, String(eff.get("source", step_owner_mod)), false)
	state.record_contrib(param_id, scope_key, step_owner_mod if step_owner_mod != "" else "effect", v_new - old_val)


func _eval_scale(eff: Dictionary, step_ctx: Dictionary) -> float:
	if not eff.has("scale") or eff["scale"] == null:
		return 1.0
	var scale_v: Variant = eff["scale"]
	if typeof(scale_v) == TYPE_FLOAT or typeof(scale_v) == TYPE_INT:
		return float(scale_v)
	if typeof(scale_v) == TYPE_STRING and String(scale_v).is_empty():
		return 1.0
	return expr_engine.eval_float(scale_v, step_ctx)


func _validate_effect_schema(eff: Dictionary, _owner: String, state: SimState) -> bool:
	var op: String = String(eff.get("op", ""))
	if op == "":
		state.record_error("E_EFFECT_SCHEMA", "missing op")
		return false
	return true


func _extract_mod_scope_key(eff: Dictionary) -> String:
	if typeof(eff.get("value", null)) == TYPE_DICTIONARY:
		var opts: Dictionary = eff["value"]
		if opts.has("scope_key") or opts.has("key"):
			return String(opts.get("scope_key", opts.get("key", "")))
	return String(eff.get("key", ""))


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
