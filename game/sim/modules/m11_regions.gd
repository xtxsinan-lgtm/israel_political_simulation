class_name M11Regions
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M11"


func weekly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 8:
		return []
	var ids: Array[String] = _region_ids(state)
	for i: int in range(ids.size()):
		if not _exists(state, ids[i]):
			continue
		var security: float = state.params.get_val("region_security", ids[i], state)
		security += (state.params.get_val("public_security", "", state) - security) * 0.05
		state.params.set_val("region_security", ids[i], security, state)
	return []


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 13:
		return []
	var ids: Array[String] = _region_ids(state)
	for i: int in range(ids.size()):
		if not _exists(state, ids[i]):
			continue
		var dev: float = state.params.get_val("region_development", ids[i], state) + 0.1
		state.params.set_val("region_development", ids[i], dev, state)
		var settlers: float = state.params.get_val("settler_population", ids[i], state)
		if settlers > 0.0:
			state.params.set_val("settler_population", ids[i], settlers * 1.004, state)
	_update_trilemma(state)
	return []


func annual_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 17:
		return []
	var m11: Dictionary = _m11(state)
	m11["haredi_cohort"] = float(m11.get("haredi_cohort", 10.0)) * 1.04
	state.modules["M11"] = m11
	return []


func provide_terms(provider_name: String, state: SimState, _param_id: String, _scope_key: String) -> Array[Dictionary]:
	if provider_name != "m11_settler_demography_term":
		return []
	var total: float = 0.0
	var ids: Array[String] = _region_ids(state)
	for i: int in range(ids.size()):
		total += state.params.get_val("settler_population", ids[i], state)
	return [{"id": "settlers", "value": total * 0.001, "label_zh": "定居者人口"}]


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	var region_id: String = String(args.get("region", ""))
	match op_name:
		"m11_activate_region", "m11_create_region", "m11_add_region":
			return _set_exists(state, region_id, true)
		"m11_remove_region":
			return _set_exists(state, region_id, false)
		"m11_set_legal_status":
			return _set_field(state, region_id, "legal_status", String(args.get("status", "occupied")))
		"m11_activate_overlay":
			var m11: Dictionary = _m11(state)
			m11["active_overlay"] = String(args.get("plan", ""))
			state.modules["M11"] = m11
			return []
		"m11_update_site_status":
			var sites: Dictionary = _as_dict(_m11(state).get("key_sites", {}))
			sites[String(args.get("site", ""))] = String(args.get("status", "planned"))
			var m11s: Dictionary = _m11(state)
			m11s["key_sites"] = sites
			state.modules["M11"] = m11s
			return []
		"m11_advance_plan_stage":
			var plans: Dictionary = _as_dict(_m11(state).get("plans", {}))
			var plan_id: String = String(args.get("plan", ""))
			plans[plan_id] = int(plans.get(plan_id, 0)) + 1
			var m11p: Dictionary = _m11(state)
			m11p["plans"] = plans
			state.modules["M11"] = m11p
			return []
		"m11_set_region_priority":
			var pri: Dictionary = _as_dict(_m11(state).get("priorities", {}))
			pri[region_id] = String(args.get("priority", "security"))
			var m11r: Dictionary = _m11(state)
			m11r["priorities"] = pri
			state.modules["M11"] = m11r
			return []
		_:
			return []
	return []


func compute_oslo_shares(state: SimState) -> Dictionary:
	var west: Array[String] = ["west_bank", "gaza"]
	var a: float = 0.0
	var b: float = 0.0
	var c: float = 0.0
	for i: int in range(west.size()):
		var status: String = String(_as_dict(_regions(state).get(west[i], {})).get("oslo", "C"))
		var pop: float = maxf(1.0, state.params.get_val("region_population", west[i], state))
		if status == "A":
			a += pop
		elif status == "B":
			b += pop
		else:
			c += pop
	var total: float = maxf(1.0, a + b + c)
	var shares: Dictionary = {"A": a / total, "B": b / total, "C": c / total}
	var m11: Dictionary = _m11(state)
	m11["oslo_shares"] = shares
	state.modules["M11"] = m11
	return shares


func _update_trilemma(state: SimState) -> void:
	var jewish: float = state.params.get_val("jewish_majority", "", state)
	var democracy: float = state.params.get_val("democracy_index", "", state)
	var territory: float = state.params.get_val("territorial_control", "", state)
	if jewish <= 0.0:
		jewish = 70.0
	if democracy <= 0.0:
		democracy = 75.0
	if territory <= 0.0:
		territory = 80.0
	var tension: float = maxf(0.0, (jewish + democracy + territory) - 200.0) * 0.1
	state.params.set_val("trilemma_tension", "", tension, state)
	state.params.set_val("trilemma_jewish", "", jewish, state)
	state.params.set_val("trilemma_democracy", "", democracy, state)
	state.params.set_val("trilemma_territory", "", territory, state)


func _set_exists(state: SimState, region_id: String, exists: bool) -> Array[Dictionary]:
	var regions: Dictionary = _regions(state)
	var row: Dictionary = _as_dict(regions.get(region_id, {}))
	row["exists"] = exists
	regions[region_id] = row
	var m11: Dictionary = _m11(state)
	m11["regions"] = regions
	state.modules["M11"] = m11
	return []


func _set_field(state: SimState, region_id: String, field: String, value: String) -> Array[Dictionary]:
	var regions: Dictionary = _regions(state)
	var row: Dictionary = _as_dict(regions.get(region_id, {}))
	row[field] = value
	regions[region_id] = row
	var m11: Dictionary = _m11(state)
	m11["regions"] = regions
	state.modules["M11"] = m11
	return []


func _exists(state: SimState, region_id: String) -> bool:
	return bool(_as_dict(_regions(state).get(region_id, {})).get("exists", false))


func _region_ids(state: SimState) -> Array[String]:
	var ids: Array[String] = SimMath.sorted_keys(_regions(state))
	if not ids.is_empty():
		return ids
	if GameData.current != null:
		return SimMath.sorted_keys(GameData.current.regions_def)
	return []


func _regions(state: SimState) -> Dictionary:
	return _as_dict(_m11(state).get("regions", {}))


func _m11(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M11", {}))
	state.modules["M11"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
