class_name GameData
extends RefCounted

static var current: GameData


func _init() -> void:
	current = self

var ruleset_hash: String = ""
var parameters_def: Dictionary = {}
var param_aliases: Dictionary = {}
var entity_aliases: Dictionary = {}
var modifiers_def: Dictionary = {}
var causal_nodes_def: Dictionary = {}
var causal_edges_def: Array[Dictionary] = []
var thresholds_def: Array[Dictionary] = []
var policies_def: Dictionary = {}
var actions_def: Dictionary = {}
var characters_def: Dictionary = {}
var world_tracks_def: Dictionary = {}
var pal_factions_def: Dictionary = {}
var regions_def: Dictionary = {}
var sites_def: Dictionary = {}
var plans_def: Dictionary = {}
var events_def: Dictionary = {}
var ui_config: Dictionary = {}
var codex_terms: Dictionary = {}
var migrations_def: Array[Dictionary] = []
var compiled_ast_cache: Dictionary = {}

var _int_keys: Dictionary = {}
var _handler_owners: Dictionary = {}
var _scenario_cache: Dictionary = {}


func load_all_runtime_data() -> Error:
	_ensure_handlers()
	var manifest_v: Variant = _read_json("res://res/data/manifest.json")
	if typeof(manifest_v) != TYPE_DICTIONARY:
		return ERR_FILE_CORRUPT
	var manifest: Dictionary = manifest_v
	ruleset_hash = String(manifest.get("ruleset_hash", ""))
	_int_keys = {}
	var schema: Dictionary = _as_dict(manifest.get("int_schema_paths", {}))
	var key_list: Array = _as_array(schema.get("global_int_keys", []))
	for i: int in range(key_list.size()):
		_int_keys[String(key_list[i])] = true

	var parameters: Dictionary = _load_dict("res://res/data/parameters.json")
	parameters_def = _as_dict(parameters.get("by_id", {}))
	_load_param_aliases(_as_dict(parameters.get("aliases", {})))
	entity_aliases = _as_dict(parameters.get("entities", {}))

	var modifiers: Dictionary = _load_dict("res://res/data/modifiers.json")
	modifiers_def = _as_dict(modifiers.get("by_id", {}))

	var causal: Dictionary = _load_dict("res://res/data/causal_edges.json")
	causal_nodes_def = _as_dict(causal.get("by_param", {}))
	causal_edges_def = _dict_array(causal.get("edges", []))
	thresholds_def = _dict_array(causal.get("thresholds", []))

	var policies: Dictionary = _load_dict("res://res/data/policies.json")
	policies_def = _as_dict(policies.get("by_id", {}))
	var actions: Dictionary = _load_dict("res://res/data/actions.json")
	actions_def = _as_dict(actions.get("by_id", {}))
	var characters: Dictionary = _load_dict("res://res/data/characters.json")
	characters_def = _as_dict(characters.get("by_id", {}))
	world_tracks_def = _load_dict("res://res/data/world_tracks.json")
	pal_factions_def = _load_dict("res://res/data/palestine_factions.json")

	var regions: Dictionary = _load_dict("res://res/data/regions.json")
	regions_def = _as_dict(regions.get("regions", {}))
	sites_def = _as_dict(regions.get("key_sites", {}))
	plans_def = _as_dict(regions.get("planning_overlays", {}))

	var events: Dictionary = _load_dict("res://res/data/events.json")
	events_def = _as_dict(events.get("by_id", {}))
	ui_config = _load_dict("res://res/data/ui_config.json")
	codex_terms = _load_dict("res://res/data/codex_terms.json")
	var migrations: Dictionary = _load_dict("res://res/data/migrations.json")
	migrations_def = _dict_array(migrations.get("migrations", []))

	var asts: Dictionary = _load_dict("res://res/data/compiled_asts.json")
	compiled_ast_cache = _as_dict(asts.get("asts", {}))
	_scenario_cache = {}
	if ruleset_hash.length() != 64:
		return ERR_INVALID_DATA
	return OK


func get_scenario_bundle(scenario_id: String) -> Dictionary:
	if _scenario_cache.has(scenario_id):
		return _as_dict(_scenario_cache[scenario_id])
	var loaded: Dictionary = _load_dict("res://res/data/scenarios/%s.json" % scenario_id)
	_scenario_cache[scenario_id] = loaded
	return loaded


func resolve_param_alias(raw_param_id: String) -> String:
	if param_aliases.has(raw_param_id):
		var mapped: String = String(param_aliases[raw_param_id])
		if not mapped.begins_with("@"):
			return mapped
	match raw_param_id:
		"voter_cynicism":
			return "cynicism"
		"security_index":
			return "public_security"
		"country_stability":
			return "regime_stability"
		"country_nuclear_progress":
			return "enemy_nuclear_progress"
		"annual_immigration":
			return "immigration_inflow"
		"palestinian_hostility":
			return "pal_hostility"
		"intifada_risk":
			return "uprising_risk"
		"us_stance":
			return "us_admin_relation"
		"policy":
			return "policy_level"
		_:
			return raw_param_id


func resolve_region_id(raw_region_id: String) -> String:
	match raw_region_id:
		"north":
			return "galilee"
		"central":
			return "triangle"
		"south":
			return "negev"
		_:
			return raw_region_id


func resolve_pal_faction_id(raw_faction_id: String) -> String:
	match raw_faction_id:
		"notables":
			return "jordan_notables"
		"left_factions":
			return "pflp"
		"islamic_jihad":
			return "pij"
		_:
			return raw_faction_id


func resolve_party_id(raw_party_id: String) -> String:
	match raw_party_id:
		"pm_new_party":
			return "new_party_a"
		"alignment":
			return "labor"
		"agudat_yisrael":
			return "agudat"
		"hadash":
			return "rakah_hadash"
		_:
			return raw_party_id


func resolve_bloc_id(raw_bloc_id: String) -> String:
	match raw_bloc_id:
		"mizrahi_working":
			return "mizrahi"
		"haredi_orth":
			return "haredi"
		"russian_immigrants":
			return "russian"
		_:
			return raw_bloc_id


func resolve_office_id(raw_office_id: String) -> String:
	match raw_office_id:
		"pm":
			return "prime_minister"
		"defense_minister":
			return "defense"
		"finance_minister":
			return "finance"
		"foreign_minister":
			return "foreign"
		"interior_minister":
			return "interior"
		"justice_minister":
			return "justice"
		"housing_minister":
			return "housing"
		"religion", "religion_minister":
			return "religious_affairs"
		"education_minister":
			return "education"
		"absorption_minister":
			return "absorption"
		"agriculture_minister":
			return "agriculture"
		"transport_minister":
			return "transport"
		"cos":
			return "chief_of_staff"
		"mossad":
			return "mossad_chief"
		"shin_bet":
			return "shin_bet_chief"
		"ag":
			return "attorney_general"
		"boi", "central_bank_governor":
			return "boi_governor"
		"supreme_court":
			return "supreme_court_president"
		"opposition":
			return "opposition_leader"
		_:
			return raw_office_id


func get_custom_handler_owner(custom_name: String) -> String:
	_ensure_handlers()
	return String(_handler_owners.get(custom_name, ""))


func get_compiled_ast(expr_str: String) -> Array:
	if not compiled_ast_cache.has(expr_str):
		return []
	var found: Variant = compiled_ast_cache[expr_str]
	if typeof(found) == TYPE_ARRAY:
		return found
	return []


func _load_param_aliases(aliases: Dictionary) -> void:
	param_aliases = {}
	var table: Dictionary = _as_dict(aliases.get("parameters", aliases))
	var keys: Array[String] = SimMath.sorted_keys(table)
	for i: int in range(keys.size()):
		var key: String = keys[i]
		var target: String = String(table[key])
		if target.begins_with("@"):
			continue
		param_aliases[key] = target


func _ensure_handlers() -> void:
	if not _handler_owners.is_empty():
		return
	var pairs: Array[String] = [
		"random_branch", "M01", "if_then", "M01", "add_all_keys", "M01",
		"schedule_event_window", "M01", "end_tenure", "M01", "m01_trigger_tenure_end", "M01",
		"m01_raise_signal", "M01", "m01_force_pause", "M01", "m01_set_player_party", "M01",
		"activate_key", "M01", "deactivate_key", "M01",
		"m02_add_baseline_shift", "M02",
		"m03_apply_seat_change", "M03", "m03_request_vote", "M03", "m03_submit_bill", "M03",
		"m03_offer", "M03", "m03_form_unity_rotation", "M03", "m03_add_to_coalition", "M03",
		"m03_remove_from_coalition", "M03", "m03_split_party", "M03", "m03_found_party", "M03",
		"m03_merge_parties", "M03", "m03_dissolve_party", "M03", "m03_mk_defect", "M03",
		"m03_set_role", "M03", "m03_assign_portfolio", "M03", "m03_delay_demand", "M03",
		"m03_force_support", "M03", "m03_postpone_election", "M03", "m03_dissolve_knesset", "M03",
		"stance_shift_by_corridor", "M04", "m04_add_stance_by_corridor", "M04",
		"m04_push_corridor", "M04", "m04_shift_corridor", "M04",
		"m04_add_promise_by_tag", "M04", "m04_set_promises", "M04",
		"m04_party_convention", "M04", "m04_faction_deal", "M04",
		"m04_faction_exit", "M04", "m04_party_split", "M04", "m04_found_new_party", "M04",
		"m04_leadership_vote", "M04", "m04_force_challenge", "M04", "m04_vision_event", "M04",
		"m04_open_campaign_pool", "M04", "m04_election_settle", "M04",
		"m04_activate_campaign_promises", "M04", "m04_finalize_promises", "M04",
		"m04_reset_goals_for_leader", "M04",
		"m05_change_policy", "M05", "m05_grant_favor", "M05", "m05_incur_favor", "M05",
		"m05_cancel_action", "M05", "m05_unlock", "M05", "m05_bill_result", "M05",
		"m05_add_axis_impulse", "M05",
		"m06_appoint", "M06", "m06_dismiss", "M06", "m06_open_reshuffle", "M06",
		"m06_add_relation_cabinet", "M06", "m06_promote_group", "M06",
		"m06_pick_successor", "M06", "m06_rebase_relations", "M06",
		"m06_health_check", "M06", "m06_kill_character", "M06", "m06_inquiry_report", "M06",
		"m07_set_world_track", "M07", "m07_open_negotiation", "M07", "m07_set_issue_tier", "M07",
		"m07_trade_concession", "M07", "m07_conclude_summit", "M07", "m07_ratification_result", "M07",
		"m08_spawn_hamas", "M08", "m08_activate_delegation", "M08",
		"m08_set_autonomy_modality", "M08", "m08_start_intifada", "M08",
		"m09_start_war", "M09", "m09_ceasefire", "M09", "m09_set_mobilization", "M09",
		"m10_pass_budget", "M10", "m10_budget_result", "M10",
		"m10_set_draft_slider", "M10", "m10_set_enacted_slider_delta", "M10",
		"m10_apply_stabilization_plan", "M10", "m10_trigger_bank_bailout", "M10",
		"m10_inject_external_inflation_shock", "M10", "m10_spawn_aliyah_cohort", "M10",
		"m11_activate_region", "M11", "m11_remove_region", "M11",
		"m11_create_region", "M11", "m11_add_region", "M11",
		"m11_set_legal_status", "M11", "m11_activate_overlay", "M11",
		"m13_apply_centralization_impulse", "M13",
		"m14_record_turning_point", "M14", "m14_grant_achievement", "M14",
		"m14_generate_fictional_leader", "M14",
	]
	for i: int in range(0, pairs.size(), 2):
		_handler_owners[pairs[i]] = pairs[i + 1]


func _load_dict(res_path: String) -> Dictionary:
	var parsed: Variant = _restore_json_ints(_read_json(res_path), _int_keys)
	return _as_dict(parsed)


func _read_json(res_path: String) -> Variant:
	if not FileAccess.file_exists(res_path):
		push_error("missing json " + res_path)
		return {}
	var file: FileAccess = FileAccess.open(res_path, FileAccess.READ)
	if file == null:
		push_error("open failed " + res_path)
		return {}
	var text: String = file.get_as_text()
	file.close()
	var parsed: Variant = JSON.parse_string(text)
	if parsed == null:
		push_error("json parse failed " + res_path)
		return {}
	return parsed


func _restore_json_ints(data: Variant, int_keys: Dictionary) -> Variant:
	var kind: int = typeof(data)
	if kind == TYPE_DICTIONARY:
		var src: Dictionary = data
		var out: Dictionary = {}
		var keys: Array = src.keys()
		for i: int in range(keys.size()):
			var key: String = String(keys[i])
			var child: Variant = _restore_json_ints(src[keys[i]], int_keys)
			if int_keys.has(key) and typeof(child) == TYPE_FLOAT:
				child = int(floor(float(child) + 0.5))
			out[key] = child
		return out
	if kind == TYPE_ARRAY:
		var src_arr: Array = data
		var out_arr: Array = []
		out_arr.resize(src_arr.size())
		for i: int in range(src_arr.size()):
			out_arr[i] = _restore_json_ints(src_arr[i], int_keys)
		return out_arr
	return data


func _dict_array(value: Variant) -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	if typeof(value) != TYPE_ARRAY:
		return out
	var src: Array = value
	for i: int in range(src.size()):
		if typeof(src[i]) == TYPE_DICTIONARY:
			out.append(src[i])
	return out


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
