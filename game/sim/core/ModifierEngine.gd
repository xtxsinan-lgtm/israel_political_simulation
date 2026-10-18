class_name ModifierEngine
extends RefCounted

var active: Array[Dictionary] = []
var _factor_cache: Dictionary = {}
var _cache_dirty: bool = true


func invalidate_factor_cache() -> void:
	_cache_dirty = true
	_factor_cache.clear()


func add_modifier(mod_id: String, opts: Dictionary, source_id: String, state: SimState) -> void:
	var scope_key: String = String(opts.get("scope_key", opts.get("key", "")))
	var policy: String = String(opts.get("stack", _def_stack(mod_id)))
	var existing: int = _find(mod_id, scope_key)
	var duration_days: int = _duration_days(opts, mod_id)
	var end_day: int = -1
	if duration_days >= 0:
		end_day = state.clock.day_index + duration_days
	if existing >= 0:
		var row: Dictionary = active[existing]
		match policy:
			"ignore":
				return
			"refresh":
				row["end_day"] = end_day
				active[existing] = row
				invalidate_factor_cache()
				return
			"stack":
				var max_stacks: int = int(opts.get("max_stacks", row.get("max_stacks", 5)))
				row["stacks"] = mini(int(row.get("stacks", 1)) + 1, max_stacks)
				row["end_day"] = end_day
				active[existing] = row
				invalidate_factor_cache()
				return
			_:
				active.remove_at(existing)
	var uid: int = state.counters.next_modifier_uid
	state.counters.next_modifier_uid += 1
	var created: Dictionary = {
		"uid": uid,
		"def_id": mod_id,
		"scope_key": scope_key,
		"source": source_id,
		"stacks": 1,
		"strength": float(opts.get("strength", 1.0)),
		"max_strength": float(opts.get("max_strength", 100.0)),
		"growth_per_month": float(opts.get("growth_per_month", 0.0)),
		"end_day": end_day,
		"remove_if": opts.get("remove_if", null),
		"remove_on": String(opts.get("remove_on", "")),
		"on_expire": opts.get("on_expire", []),
		"factors": _copy_factors(mod_id, opts),
	}
	active.append(created)
	_sort_by_uid()
	invalidate_factor_cache()


func remove_modifier(mod_id: String, scope_key: String, _state: SimState) -> void:
	var i: int = active.size() - 1
	while i >= 0:
		var row: Dictionary = active[i]
		var same_id: bool = String(row.get("def_id", "")) == mod_id
		var same_key: bool = scope_key == "" or String(row.get("scope_key", "")) == scope_key
		if same_id and same_key:
			active.remove_at(i)
		i -= 1
	invalidate_factor_cache()


func remove_on_signal(signal_name: String, _state: SimState) -> void:
	if signal_name == "":
		return
	var i: int = active.size() - 1
	while i >= 0:
		if String(active[i].get("remove_on", "")) == signal_name:
			active.remove_at(i)
		i -= 1
	invalidate_factor_cache()


func expire_and_check_remove_if(state: SimState, expr: ExprEngine) -> Array[Dictionary]:
	var follow: Array[Dictionary] = []
	var i: int = active.size() - 1
	while i >= 0:
		var row: Dictionary = active[i]
		var end_day: int = int(row.get("end_day", -1))
		var expired: bool = end_day != -1 and end_day <= state.clock.day_index
		var remove_if: Variant = row.get("remove_if", null)
		var condition: bool = false
		if remove_if != null and not (typeof(remove_if) == TYPE_STRING and String(remove_if).is_empty()):
			condition = expr.eval_bool(remove_if, {})
		if expired or condition:
			var on_expire: Variant = row.get("on_expire", [])
			if typeof(on_expire) == TYPE_ARRAY:
				var effects: Array = on_expire
				for j: int in range(effects.size()):
					if typeof(effects[j]) == TYPE_DICTIONARY:
						follow.append(effects[j])
			active.remove_at(i)
		i -= 1
	if not follow.is_empty() or true:
		invalidate_factor_cache()
	return follow


func tick_debt_modifiers(state: SimState) -> void:
	if not state.clock.is_month:
		return
	for i: int in range(active.size()):
		var row: Dictionary = active[i]
		var growth: float = float(row.get("growth_per_month", 0.0))
		if absf(growth) < 1.0e-12:
			continue
		var cap: float = float(row.get("max_strength", 100.0))
		row["strength"] = clampf(float(row.get("strength", 0.0)) + growth, 0.0, cap)
		active[i] = row
	invalidate_factor_cache()


func get_factor(factor_key: String, scope_key: String = "") -> float:
	var cache_key: String = factor_key + "|" + scope_key
	if not _cache_dirty and _factor_cache.has(cache_key):
		return float(_factor_cache[cache_key])
	var mult: float = 1.0
	var add: float = 0.0
	for i: int in range(active.size()):
		var row: Dictionary = active[i]
		if scope_key != "" and String(row.get("scope_key", "")) != scope_key and String(row.get("scope_key", "")) != "":
			continue
		var stacks: int = maxi(1, int(row.get("stacks", 1)))
		var factors: Array = _as_array(row.get("factors", []))
		for j: int in range(factors.size()):
			var factor: Dictionary = _as_dict(factors[j])
			if String(factor.get("key", "")) != factor_key:
				continue
			var mode: String = String(factor.get("mode", "mult"))
			var value: float = float(factor.get("value", 0.0)) * float(stacks)
			if mode == "add" or mode == "add_pct":
				add += value
			else:
				mult *= value if absf(value) > 1.0e-12 else 1.0
	var combined: float = mult + add
	_factor_cache[cache_key] = combined
	_cache_dirty = false
	return combined


func _find(mod_id: String, scope_key: String) -> int:
	for i: int in range(active.size()):
		var row: Dictionary = active[i]
		if String(row.get("def_id", "")) == mod_id and String(row.get("scope_key", "")) == scope_key:
			return i
	return -1


func _def_stack(mod_id: String) -> String:
	if GameData.current == null:
		return "replace"
	var row: Dictionary = _as_dict(GameData.current.modifiers_def.get(mod_id, {}))
	return String(row.get("stack", "replace"))


func _duration_days(opts: Dictionary, mod_id: String) -> int:
	if opts.has("duration_days"):
		return int(opts["duration_days"])
	if opts.has("end_day"):
		return -1
	var row: Dictionary = {}
	if GameData.current != null:
		row = _as_dict(GameData.current.modifiers_def.get(mod_id, {}))
	if row.has("duration_days") and row["duration_days"] != null:
		return int(row["duration_days"])
	var duration: Dictionary = _as_dict(row.get("duration", {}))
	if duration.is_empty():
		return -1
	var n: int = int(duration.get("n", 0))
	var unit: String = String(duration.get("unit", "days"))
	if unit == "months":
		return n * 30
	if unit == "years":
		return n * 365
	return n


func _copy_factors(mod_id: String, opts: Dictionary) -> Array:
	if opts.has("factors") and typeof(opts["factors"]) == TYPE_ARRAY:
		return (opts["factors"] as Array).duplicate(true)
	if GameData.current == null:
		return []
	var row: Dictionary = _as_dict(GameData.current.modifiers_def.get(mod_id, {}))
	var factors: Variant = row.get("factors", [])
	if typeof(factors) == TYPE_ARRAY:
		return (factors as Array).duplicate(true)
	return []


func _sort_by_uid() -> void:
	for i: int in range(1, active.size()):
		var row: Dictionary = active[i]
		var j: int = i
		while j > 0 and int(active[j - 1].get("uid", 0)) > int(row.get("uid", 0)):
			active[j] = active[j - 1]
			j -= 1
		active[j] = row


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
