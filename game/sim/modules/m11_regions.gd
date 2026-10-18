class_name M11Regions
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M11"


func weekly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 8:
		return []
	var core: Array[String] = ["galilee", "haifa", "tel_aviv", "triangle", "jerusalem", "negev"]
	for i: int in range(core.size()):
		var security: float = state.params.get_val("region_security", core[i], state)
		if security < 35.0:
			security += 0.4
		elif security > 90.0:
			security -= 0.3
		state.params.set_val("region_security", core[i], security, state)
	return []


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 13:
		return []
	if _exists(state, "west_bank"):
		var sp_pol: float = state.params.get_val("settlement_policy", "west_bank", state)
		var mom: float = state.params.get_val("settler_momentum", "", state)
		var growth: float = maxf(0.0, (sp_pol - 15.0) * 4.5 + (mom - 40.0) * 6.0)
		state.params.set_val("settler_population", "west_bank", state.params.get_val("settler_population", "west_bank", state) + growth, state)
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
	var rol: float = state.params.get_val("rule_of_law", "", state)
	var cent: float = state.params.get_val("centralization", "", state)
	var arab_id: float = state.params.get_val("civic_identification", "arab", state)
	var autonomy: float = state.params.get_val("autonomy_progress", "", state)
	var settler_regions: Array[String] = ["jerusalem", "west_bank", "gaza", "golan", "sinai"]
	var settlers: float = 0.0
	for i: int in range(settler_regions.size()):
		if not _exists(state, settler_regions[i]):
			continue
		settlers += float(int(floor(state.params.get_val("settler_population", settler_regions[i], state))))
	var t_dem: float = clampf(0.55 * rol + 0.25 * (100.0 - cent) + 0.10 * arab_id + 0.10 * autonomy, 15.0, 95.0)
	var sinai_term: float = 8.0 if _exists(state, "sinai") else -4.0
	var t_terr: float = clampf(65.0 + minf(30.0, settlers / 3500.0) + sinai_term, 25.0, 96.0)
	var annexed_pen: float = 6.0 if _flag_on(state, "west_bank_annexed") and autonomy < 20.0 else 0.0
	var t_jew: float = clampf(72.0 + 0.10 * (100.0 - state.params.get_val("alienation", "mizrahi", state)) - annexed_pen, 30.0, 95.0)
	var tri: float = clampf((t_dem + t_terr + t_jew) / 3.0 - 0.15 * maxf(0.0, t_terr - 82.0), 20.0, 92.0)
	state.params.set_val("trilemma_democratic", "", t_dem, state)
	state.params.set_val("trilemma_territory", "", t_terr, state)
	state.params.set_val("trilemma_jewish", "", t_jew, state)
	state.params.set_val("trilemma", "", tri, state)


func _flag_on(state: SimState, flag_id: String) -> bool:
	return state.flags.has(flag_id) and float(_as_dict(state.flags[flag_id]).get("value", 1.0)) != 0.0


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
