class_name ParameterStore
extends RefCounted

var _scalars: Dictionary = {}
var _scoped: Dictionary = {}
var _active_keys: Dictionary = {}


func get_val(raw_param: String, raw_key: String = "", state: Variant = null) -> float:
	if raw_param == "country_relation":
		if raw_key == "usa":
			return get_val("us_admin_relation", "", state)
		var power_dict: Dictionary = _as_dict(_scoped.get("power_relation", {}))
		if power_dict.has(raw_key):
			return float(power_dict[raw_key])
		var host_dict: Dictionary = _as_dict(_scoped.get("regime_hostility", {}))
		if host_dict.has(raw_key):
			return 100.0 - float(host_dict[raw_key])
		return 50.0
	if raw_param == "islamic_assoc_strength":
		return get_val("faction_strength", "mujama", state)
	var param_id: String = GameData.current.resolve_param_alias(raw_param)
	var pdef: Dictionary = _as_dict(GameData.current.parameters_def.get(param_id, {}))
	var scope: String = String(pdef.get("scope", "national"))
	if scope == "national":
		return float(_scalars.get(param_id, 0.0))
	var scope_key: String = _resolve_scope_key(scope, raw_key, state)
	if scope_key == "":
		return 0.0
	var sub_dict: Dictionary = _as_dict(_scoped.get(param_id, {}))
	return float(sub_dict.get(scope_key, 0.0))


func set_val(raw_param: String, raw_key: String, new_val: float, state: Variant = null) -> float:
	if raw_param == "islamic_assoc_strength":
		return set_val("faction_strength", "mujama", new_val, state)
	var param_id: String = GameData.current.resolve_param_alias(raw_param)
	var pdef: Dictionary = _as_dict(GameData.current.parameters_def.get(param_id, {}))
	var scope: String = String(pdef.get("scope", "national"))
	var lo: float = -1.0e12
	var hi: float = 1.0e12
	var range_v: Variant = pdef.get("range", null)
	if typeof(range_v) == TYPE_ARRAY:
		var range_arr: Array = range_v
		if range_arr.size() >= 2:
			lo = float(range_arr[0])
			hi = float(range_arr[1])
	var stored: float = SimMath.quantize(clampf(new_val, lo, hi))
	if scope == "national":
		_scalars[param_id] = stored
		if param_id == "us_admin_relation":
			_write_scoped_raw("power_relation", "usa", stored)
		return stored
	var scope_key: String = _resolve_scope_key(scope, raw_key, state)
	if scope_key == "":
		return 0.0
	_write_scoped_raw(param_id, scope_key, stored)
	if param_id == "power_relation" and scope_key == "usa":
		_scalars["us_admin_relation"] = stored
	if param_id == "promise_progress":
		_sync_promise_progress(state, scope_key, stored)
	return stored


func resolve_key_for_write(raw_param: String, raw_key: String, state: Variant = null) -> String:
	var param_id: String = GameData.current.resolve_param_alias(raw_param)
	var pdef: Dictionary = _as_dict(GameData.current.parameters_def.get(param_id, {}))
	var scope: String = String(pdef.get("scope", "national"))
	if scope == "national":
		return ""
	var offices: Dictionary = _offices_of(state)
	var office_id: String = raw_key
	if GameData.current != null:
		office_id = GameData.current.resolve_office_id(raw_key)
	if offices.has(raw_key) and String(offices[raw_key]) == "":
		return "__INVALID_EMPTY_OFFICE__"
	if offices.has(office_id) and String(offices[office_id]) == "":
		return "__INVALID_EMPTY_OFFICE__"
	return _resolve_scope_key(scope, raw_key, state)


func activate_key(param_id: String, key: String, init_val: float) -> void:
	var sub_dict: Dictionary = _as_dict(_scoped.get(param_id, {}))
	if not sub_dict.has(key):
		sub_dict[key] = SimMath.quantize(init_val)
		_scoped[param_id] = sub_dict
	_remember_key(param_id, key)


func deactivate_key(param_id: String, key: String) -> void:
	var sub_dict: Dictionary = _as_dict(_scoped.get(param_id, {}))
	sub_dict.erase(key)
	_scoped[param_id] = sub_dict
	var keys: Array = _as_array(_active_keys.get(param_id, []))
	var next: Array[String] = []
	for i: int in range(keys.size()):
		var item: String = String(keys[i])
		if item != key:
			next.append(item)
	_active_keys[param_id] = next


func get_active_keys(param_id: String) -> Array[String]:
	if _active_keys.has(param_id):
		var listed: Array = _as_array(_active_keys[param_id])
		var out: Array[String] = []
		for i: int in range(listed.size()):
			out.append(String(listed[i]))
		out.sort()
		return out
	var sub_dict: Dictionary = _as_dict(_scoped.get(param_id, {}))
	return SimMath.sorted_keys(sub_dict)


func export_scalars() -> Dictionary:
	return _scalars.duplicate(true)


func export_scoped() -> Dictionary:
	return _scoped.duplicate(true)


func _write_scoped_raw(param_id: String, scope_key: String, stored: float) -> void:
	var sub_dict: Dictionary = _as_dict(_scoped.get(param_id, {}))
	sub_dict[scope_key] = stored
	_scoped[param_id] = sub_dict
	_remember_key(param_id, scope_key)


func _remember_key(param_id: String, key: String) -> void:
	var keys: Array = _as_array(_active_keys.get(param_id, []))
	for i: int in range(keys.size()):
		if String(keys[i]) == key:
			return
	keys.append(key)
	_active_keys[param_id] = keys


func _resolve_scope_key(scope_type: String, raw_key: String, state: Variant) -> String:
	match scope_type:
		"region":
			return GameData.current.resolve_region_id(raw_key)
		"pal_faction":
			return GameData.current.resolve_pal_faction_id(raw_key)
		"party":
			return GameData.current.resolve_party_id(raw_key)
		"character":
			if GameData.current.characters_def.has(raw_key):
				return raw_key
			var offices: Dictionary = _offices_of(state)
			if offices.has(raw_key):
				return String(offices[raw_key])
			var canon_office: String = GameData.current.resolve_office_id(raw_key)
			if offices.has(canon_office):
				return String(offices[canon_office])
			return raw_key
		_:
			return raw_key


func _sync_promise_progress(state: Variant, promise_id: String, stored: float) -> void:
	if state == null or typeof(state) != TYPE_OBJECT or promise_id == "":
		return
	var obj: Object = state
	var rows_v: Variant = obj.get("promises")
	if typeof(rows_v) != TYPE_ARRAY:
		return
	var rows: Array = rows_v
	for i: int in range(rows.size()):
		var row: Dictionary = _as_dict(rows[i])
		var row_id: String = String(row.get("id", row.get("promise_id", "")))
		if row_id != promise_id:
			continue
		row["progress"] = stored
		rows[i] = row
	obj.set("promises", rows)


func _offices_of(state: Variant) -> Dictionary:
	if state == null or typeof(state) != TYPE_OBJECT:
		return {}
	var obj: Object = state
	var modules_v: Variant = obj.get("modules")
	if typeof(modules_v) != TYPE_DICTIONARY:
		return {}
	var modules: Dictionary = modules_v
	var m06: Dictionary = _as_dict(modules.get("M06", {}))
	return _as_dict(m06.get("offices", {}))


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
