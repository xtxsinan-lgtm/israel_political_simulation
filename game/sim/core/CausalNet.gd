class_name CausalNet
extends RefCounted

const INERTIA_ALPHA: float = 0.10
const MEMORY_RHO: float = 0.30
const MEMORY_MU: float = 0.05

var _edge_cache: Dictionary = {}
var _edge_index_ready: bool = false


func on_effect_applied(state: SimState, param_id: String, scope_key: String, delta_actual: float, source_id: String, is_owner_set: bool) -> void:
	if is_owner_set or absf(delta_actual) < 1.0e-9:
		return
	if GameData.current == null or not GameData.current.causal_nodes_def.has(param_id):
		return
	var ndef: Dictionary = _as_dict(GameData.current.causal_nodes_def[param_id])
	var node_type: String = String(ndef.get("node_type", ndef.get("mode", "")))
	if node_type != "level":
		return
	var node_key: String = _make_node_key(param_id, scope_key)
	var mem_delta: float = SimMath.quantize(delta_actual * MEMORY_RHO)
	var m02: Dictionary = _m02(state)
	var memories: Dictionary = _as_dict(m02.get("shock_memories", {}))
	var bucket: Array = _as_array(memories.get(node_key, []))
	var merged: bool = false
	for i: int in range(bucket.size()):
		var item: Dictionary = _as_dict(bucket[i])
		if String(item.get("source_id", "")) == source_id:
			item["remaining"] = SimMath.quantize(float(item.get("remaining", 0.0)) + mem_delta)
			item["day"] = state.clock.day_index
			bucket[i] = item
			merged = true
			break
	if not merged:
		bucket.append({
			"source_id": source_id,
			"remaining": mem_delta,
			"day": state.clock.day_index,
		})
	memories[node_key] = bucket
	m02["shock_memories"] = memories
	var shock_mem: Dictionary = _as_dict(m02.get("shock_mem", {}))
	shock_mem[node_key] = SimMath.quantize(float(shock_mem.get(node_key, 0.0)) + mem_delta)
	m02["shock_mem"] = shock_mem
	state.modules["M02"] = m02


func compute_node_step_breakdown(state: SimState, param_id: String, scope_key: String, expr: ExprEngine, modules: Dictionary, include_contribs: bool = true) -> Dictionary:
	var current_val: float = state.params.get_val(param_id, scope_key, state)
	var ndef: Dictionary = {}
	if GameData.current != null:
		ndef = _as_dict(GameData.current.causal_nodes_def.get(param_id, {}))
	var node_key: String = _make_node_key(param_id, scope_key)
	var m02: Dictionary = _m02(state)
	var contributions: Array[Dictionary] = []
	var baseline: float = _baseline(ndef, scope_key)
	var shifts: Dictionary = _as_dict(m02.get("baseline_shifts", {}))
	baseline += float(shifts.get(node_key, 0.0))
	var target_sum: float = baseline
	var edges: Array[Dictionary] = _get_active_edges_for_target(state, param_id, scope_key)
	for i: int in range(edges.size()):
		var edge: Dictionary = edges[i]
		if edge.has("cond_ast") and not expr.eval_bool(edge["cond_ast"], {"key": scope_key}):
			continue
		var src_val: float = CausalShapes.read_source_effective_val(state, edge, scope_key)
		var raw_contrib: float = CausalShapes.eval_shape(src_val, edge)
		if edge.has("cap") and edge["cap"] != null:
			var cap: float = float(edge["cap"])
			raw_contrib = clampf(raw_contrib, -cap, cap)
		target_sum += raw_contrib
		if include_contribs:
			contributions.append({
				"source_id": String(edge.get("id", "edge")),
				"source_label_zh": String(edge.get("label_zh", edge.get("id", "edge"))),
				"linked_param": String(edge.get("source", "")),
				"delta_per_tick": SimMath.quantize(raw_contrib * _alpha(ndef)),
				"raw_target_shift": raw_contrib,
				"kind": "edge",
			})
	var injected: Dictionary = _as_dict(m02.get("injected_edges", {}))
	var extra: Array = _as_array(injected.get(param_id, []))
	for i: int in range(extra.size()):
		var edge: Dictionary = _as_dict(extra[i])
		var raw_contrib: float = float(edge.get("raw_target_shift", edge.get("delta", 0.0)))
		target_sum += raw_contrib
		if include_contribs:
			contributions.append({
				"source_id": String(edge.get("source_id", "injected")),
			"source_label_zh": String(edge.get("source_label_zh", edge.get("source_id", "injected"))),
			"linked_param": String(edge.get("linked_param", "")),
			"delta_per_tick": SimMath.quantize(float(edge.get("delta_per_tick", raw_contrib * _alpha(ndef)))),
			"raw_target_shift": raw_contrib,
				"kind": "edge",
			})
	var provider_name: String = String(ndef.get("term_provider", ""))
	if provider_name != "":
		var owner_mod_id: String = String(ndef.get("provider_module", ""))
		if modules.has(owner_mod_id) and modules[owner_mod_id] is SimModuleBase:
			var owner: SimModuleBase = modules[owner_mod_id]
			var dynamic_terms: Array[Dictionary] = owner.provide_terms(provider_name, state, param_id, scope_key)
			for i: int in range(dynamic_terms.size()):
				var term: Dictionary = dynamic_terms[i]
				var t_val: float = float(term.get("value", 0.0))
				target_sum += t_val
				if include_contribs:
					contributions.append({
					"source_id": String(term.get("id", provider_name)),
					"source_label_zh": String(term.get("label_zh", provider_name)),
					"linked_param": String(term.get("linked_param", "")),
					"delta_per_tick": SimMath.quantize(t_val),
					"raw_target_shift": t_val,
						"kind": "term_provider",
					})
	var memories: Dictionary = _as_dict(m02.get("shock_memories", {}))
	var mem_list: Array = _as_array(memories.get(node_key, []))
	for i: int in range(mem_list.size()):
		var item: Dictionary = _as_dict(mem_list[i])
		var rem: float = float(item.get("remaining", 0.0))
		target_sum += rem
		if include_contribs:
			contributions.append({
				"source_id": String(item.get("source_id", "memory")),
			"source_label_zh": "事件冲击余波 (" + String(item.get("source_id", "")) + ")",
			"linked_param": "",
			"delta_per_tick": SimMath.quantize(rem * _alpha(ndef)),
			"raw_target_shift": rem,
				"kind": "memory",
			})
	var alpha: float = _alpha(ndef)
	var raw_step: float = alpha * (target_sum - current_val)
	var max_step: float = float(ndef.get("max_step_per_month", 5.0))
	var clamped_step: float = clampf(raw_step, -max_step, max_step)
	var soft: Dictionary = _as_dict(ndef.get("soft", {}))
	if not soft.is_empty():
		var lo_s: float = float(soft.get("lo_s", 0.0))
		var hi_s: float = float(soft.get("hi_s", 100.0))
		var width: float = float(soft.get("w", 13.0))
		var proposed: float = current_val + clamped_step
		var softened: float = SimMath.soft_clamp(proposed, lo_s, hi_s, width)
		clamped_step = softened - current_val
	var convergence_pct: float = 100.0
	if absf(target_sum - current_val) >= 0.5:
		convergence_pct = clampf((1.0 - absf(target_sum - current_val) / 50.0) * 100.0, 0.0, 99.0)
	return {
		"param_id": param_id,
		"scope_key": scope_key,
		"current_val": current_val,
		"target_val": SimMath.quantize(target_sum),
		"raw_step": SimMath.quantize(raw_step),
		"clamped_step": SimMath.quantize(clamped_step),
		"convergence_pct": SimMath.quantize(convergence_pct),
		"contributions": contributions,
	}


func step_all_nodes(state: SimState, expr: ExprEngine, modules: Dictionary) -> Array[Dictionary]:
	_decay_memories(state)
	var effects: Array[Dictionary] = []
	if GameData.current == null:
		return effects
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.causal_nodes_def)
	for i: int in range(ids.size()):
		var param_id: String = ids[i]
		var ndef: Dictionary = _as_dict(GameData.current.causal_nodes_def[param_id])
		if String(ndef.get("mode", ndef.get("node_type", ""))) == "none":
			continue
		var keys: Array[String] = _node_keys(state, param_id, ndef)
		for k: int in range(keys.size()):
			var scope_key: String = keys[k]
			var breakdown: Dictionary = compute_node_step_breakdown(state, param_id, scope_key, expr, modules, false)
			var next_val: float = SimMath.quantize(float(breakdown["current_val"]) + float(breakdown["clamped_step"]))
			effects.append({
				"op": "set",
				"target": param_id,
				"key": scope_key,
				"value": next_val,
				"priority": 100,
				"source": "M02." + param_id,
			})
	return effects


func record_monthly_history(state: SimState) -> void:
	var m02: Dictionary = _m02(state)
	var hist: Dictionary = _as_dict(m02.get("hist", {}))
	if GameData.current == null:
		m02["hist"] = hist
		state.modules["M02"] = m02
		return
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.parameters_def)
	for i: int in range(ids.size()):
		var param_id: String = ids[i]
		var keys: Array[String] = state.params.get_active_keys(param_id)
		if keys.is_empty():
			_push_hist(hist, param_id, state.params.get_val(param_id, "", state))
		else:
			for k: int in range(keys.size()):
				var node_key: String = _make_node_key(param_id, keys[k])
				_push_hist(hist, node_key, state.params.get_val(param_id, keys[k], state))
	m02["hist"] = hist
	state.modules["M02"] = m02


func evaluate_thresholds(state: SimState) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if GameData.current == null:
		return out
	var m02: Dictionary = _m02(state)
	var thr_states: Dictionary = _as_dict(m02.get("thr_states", {}))
	for i: int in range(GameData.current.thresholds_def.size()):
		var thr: Dictionary = GameData.current.thresholds_def[i]
		if String(thr.get("type", "level")) == "compound":
			continue
		var param_id: String = String(thr.get("param", ""))
		var key_spec: String = "" if thr.get("key", null) == null else String(thr.get("key"))
		var keys: Array[String] = []
		if key_spec == "" or key_spec == "null":
			keys.append("")
		elif key_spec == "*":
			keys = state.params.get_active_keys(param_id)
		else:
			keys.append(key_spec)
		var enter_val: float = float(thr.get("enter_val", thr.get("on_at", 0.0)))
		var exit_val: float = float(thr.get("exit_val", thr.get("off_at", enter_val)))
		var direction: String = String(thr.get("direction", "above"))
		var above: bool = direction == "above" or direction == "up"
		for k: int in range(keys.size()):
			var scope_key: String = keys[k]
			var flag_id: String = "thr." + String(thr.get("id", param_id))
			if scope_key != "":
				flag_id += "." + scope_key
			var val: float = state.params.get_val(param_id, scope_key, state)
			var active: bool = bool(thr_states.get(flag_id, false))
			if above:
				if not active and val >= enter_val:
					thr_states[flag_id] = true
					out.append({"op": "set_flag", "flag": flag_id, "value": 1.0})
				elif active and val <= exit_val:
					thr_states[flag_id] = false
					out.append({"op": "clear_flag", "flag": flag_id})
			else:
				if not active and val <= enter_val:
					thr_states[flag_id] = true
					out.append({"op": "set_flag", "flag": flag_id, "value": 1.0})
				elif active and val >= exit_val:
					thr_states[flag_id] = false
					out.append({"op": "clear_flag", "flag": flag_id})
	m02["thr_states"] = thr_states
	state.modules["M02"] = m02
	return out


func explain(state: SimState, param_id: String, scope_key: String, expr: ExprEngine, modules: Dictionary, top_n: int = 5) -> Dictionary:
	var breakdown: Dictionary = compute_node_step_breakdown(state, param_id, scope_key, expr, modules)
	var raw: Array = _as_array(breakdown.get("contributions", []))
	var kept: Array[Dictionary] = []
	for i: int in range(raw.size()):
		var row: Dictionary = _as_dict(raw[i])
		if absf(float(row.get("delta_per_tick", 0.0))) >= 0.01:
			kept.append(row)
	_sort_contributions(kept)
	var top: Array[Dictionary] = []
	var limit: int = mini(top_n, kept.size())
	for i: int in range(limit):
		top.append(kept[i])
	var rest_sum: float = 0.0
	var rest_count: int = kept.size() - limit
	for i: int in range(limit, kept.size()):
		rest_sum += float(kept[i].get("delta_per_tick", 0.0))
	if rest_count > 0:
		top.append({
			"source_id": "_others",
			"source_label_zh": "其他 %d 项合计" % rest_count,
			"delta_per_tick": SimMath.quantize(rest_sum),
		})
	return {
		"param_id": param_id,
		"scope_key": scope_key,
		"top_contributions": top,
		"clamped_step": breakdown.get("clamped_step", 0.0),
	}


func predict_months_to_threshold(state: SimState, param_id: String, scope_key: String, threshold_val: float, direction: String, expr: ExprEngine, modules: Dictionary) -> int:
	var breakdown: Dictionary = compute_node_step_breakdown(state, param_id, scope_key, expr, modules)
	var current: float = float(breakdown.get("current_val", 0.0))
	var step: float = float(breakdown.get("clamped_step", 0.0))
	var upward: bool = direction == "above" or direction == "up"
	if upward:
		if current >= threshold_val:
			return 0
		if step <= 1.0e-6:
			return -1
		return int(ceil((threshold_val - current) / step))
	if current <= threshold_val:
		return 0
	if step >= -1.0e-6:
		return -1
	return int(ceil((current - threshold_val) / (-step)))


func init_zero_drift_offsets(state: SimState, expr: ExprEngine, modules: Dictionary) -> void:
	if GameData.current == null:
		return
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.causal_nodes_def)
	for i: int in range(ids.size()):
		var param_id: String = ids[i]
		var ndef: Dictionary = _as_dict(GameData.current.causal_nodes_def[param_id])
		if String(ndef.get("mode", ndef.get("node_type", ""))) != "level":
			continue
		var keys: Array[String] = _node_keys(state, param_id, ndef)
		for k: int in range(keys.size()):
			var scope_key: String = keys[k]
			var breakdown: Dictionary = compute_node_step_breakdown(state, param_id, scope_key, expr, modules)
			var drift: float = float(breakdown.get("current_val", 0.0)) - float(breakdown.get("target_val", 0.0))
			if absf(drift) < 1.0e-6:
				continue
			var m02: Dictionary = _m02(state)
			var shifts: Dictionary = _as_dict(m02.get("baseline_shifts", {}))
			var node_key: String = _make_node_key(param_id, scope_key)
			shifts[node_key] = SimMath.quantize(float(shifts.get(node_key, 0.0)) + drift)
			m02["baseline_shifts"] = shifts
			state.modules["M02"] = m02


func verify_day0_zero_drift(state: SimState, expr: ExprEngine, modules: Dictionary) -> Dictionary:
	var max_err: float = 0.0
	if GameData.current == null:
		return {"max_drift_err": 0.0, "ok": true}
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.causal_nodes_def)
	for i: int in range(ids.size()):
		var param_id: String = ids[i]
		var ndef: Dictionary = _as_dict(GameData.current.causal_nodes_def[param_id])
		if String(ndef.get("mode", ndef.get("node_type", ""))) != "level":
			continue
		var keys: Array[String] = _node_keys(state, param_id, ndef)
		for k: int in range(keys.size()):
			var breakdown: Dictionary = compute_node_step_breakdown(state, param_id, keys[k], expr, modules)
			var err: float = absf(float(breakdown.get("target_val", 0.0)) - float(breakdown.get("current_val", 0.0)))
			if err > max_err:
				max_err = err
	return {"max_drift_err": max_err, "ok": max_err < 1.0e-4}


func _decay_memories(state: SimState) -> void:
	var m02: Dictionary = _m02(state)
	var memories: Dictionary = _as_dict(m02.get("shock_memories", {}))
	var keys: Array[String] = SimMath.sorted_keys(memories)
	var shock_mem: Dictionary = _as_dict(m02.get("shock_mem", {}))
	for i: int in range(keys.size()):
		var node_key: String = keys[i]
		var bucket: Array = _as_array(memories[node_key])
		var kept: Array = []
		var total: float = 0.0
		for j: int in range(bucket.size()):
			var item: Dictionary = _as_dict(bucket[j])
			var remaining: float = SimMath.quantize(float(item.get("remaining", 0.0)) * (1.0 - MEMORY_MU))
			if absf(remaining) < 0.05:
				continue
			item["remaining"] = remaining
			kept.append(item)
			total += remaining
		if kept.is_empty():
			memories.erase(node_key)
			shock_mem.erase(node_key)
		else:
			memories[node_key] = kept
			shock_mem[node_key] = SimMath.quantize(total)
	m02["shock_memories"] = memories
	m02["shock_mem"] = shock_mem
	state.modules["M02"] = m02


func _get_active_edges_for_target(_state: SimState, param_id: String, scope_key: String) -> Array[Dictionary]:
	var built: Array = _edges_for_param(param_id)
	var out: Array[Dictionary] = []
	for i: int in range(built.size()):
		var edge: Dictionary = built[i]
		var target_key: String = "" if edge.get("target_key", null) == null else String(edge.get("target_key"))
		if target_key != "" and target_key != "*" and target_key != scope_key:
			continue
		out.append(edge)
	return out


func _edges_for_param(param_id: String) -> Array:
	_ensure_edge_index()
	if not _edge_cache.has(param_id):
		return []
	return _edge_cache[param_id]


func _ensure_edge_index() -> void:
	if _edge_index_ready:
		return
	_edge_index_ready = true
	if GameData.current == null:
		return
	for i: int in range(GameData.current.causal_edges_def.size()):
		var edge: Dictionary = GameData.current.causal_edges_def[i]
		if String(edge.get("status", "active")) != "active":
			continue
		var target: String = String(edge.get("target", edge.get("to", "")))
		if target == "":
			continue
		_cache_edge(target, edge)
	var policy_ids: Array[String] = SimMath.sorted_keys(GameData.current.policies_def)
	for i: int in range(policy_ids.size()):
		var pol: Dictionary = _as_dict(GameData.current.policies_def[policy_ids[i]])
		var lever_edges: Array = _as_array(pol.get("e", []))
		for j: int in range(lever_edges.size()):
			var pe: Dictionary = _as_dict(lever_edges[j])
			var target: String = String(pe.get("t", pe.get("to", pe.get("target", ""))))
			if target == "":
				continue
			var synthetic: Dictionary = pe.duplicate(true)
			synthetic["id"] = "pol." + policy_ids[i]
			synthetic["source"] = "policy:" + policy_ids[i]
			synthetic["label_zh"] = String(pol.get("name_zh", policy_ids[i]))
			if not synthetic.has("shape"):
				synthetic["shape"] = "linear"
			_cache_edge(target, synthetic)


func _cache_edge(target: String, edge: Dictionary) -> void:
	var bucket: Array = []
	if _edge_cache.has(target):
		bucket = _edge_cache[target]
	bucket.append(edge)
	_edge_cache[target] = bucket


func _node_keys(state: SimState, param_id: String, ndef: Dictionary) -> Array[String]:
	var raw_keys: Variant = ndef.get("keys", null)
	var out: Array[String] = []
	if typeof(raw_keys) == TYPE_ARRAY:
		var listed: Array = raw_keys
		for i: int in range(listed.size()):
			out.append(String(listed[i]))
		if not out.is_empty():
			return out
	var active: Array[String] = state.params.get_active_keys(param_id)
	if active.is_empty():
		out.append("")
		return out
	return active


func _baseline(ndef: Dictionary, scope_key: String) -> float:
	var raw: Variant = ndef.get("baseline", 50.0)
	if typeof(raw) == TYPE_DICTIONARY:
		var table: Dictionary = raw
		if table.has(scope_key):
			return float(table[scope_key])
		return 50.0
	if raw == null:
		return 50.0
	return float(raw)


func _alpha(ndef: Dictionary) -> float:
	return float(ndef.get("alpha", INERTIA_ALPHA))


func _push_hist(hist: Dictionary, node_key: String, value: float) -> void:
	var series: Array = _as_array(hist.get(node_key, []))
	series.append(SimMath.quantize(value))
	while series.size() > 13:
		series.pop_front()
	hist[node_key] = series


func _sort_contributions(rows: Array[Dictionary]) -> void:
	for i: int in range(1, rows.size()):
		var row: Dictionary = rows[i]
		var j: int = i
		while j > 0 and _contrib_before(row, rows[j - 1]):
			rows[j] = rows[j - 1]
			j -= 1
		rows[j] = row


func _contrib_before(a: Dictionary, b: Dictionary) -> bool:
	var ad: float = absf(float(a.get("delta_per_tick", 0.0)))
	var bd: float = absf(float(b.get("delta_per_tick", 0.0)))
	if not is_equal_approx(ad, bd):
		return ad > bd
	return String(a.get("source_id", "")) < String(b.get("source_id", ""))


func _make_node_key(param_id: String, scope_key: String) -> String:
	if scope_key == "":
		return param_id
	return "%s[%s]" % [param_id, scope_key]


func _m02(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M02", {}))
	if not current.has("shock_memories"):
		current["shock_memories"] = {}
	if not current.has("baseline_shifts"):
		current["baseline_shifts"] = {}
	if not current.has("thr_states"):
		current["thr_states"] = {}
	if not current.has("hist"):
		current["hist"] = {}
	state.modules["M02"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
