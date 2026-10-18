extends SceneTree


func _initialize() -> void:
	var code: int = _run()
	quit(code)


func _run() -> int:
	var registry: GameData = GameData.new()
	var err: Error = registry.load_all_runtime_data()
	if err != OK:
		return _fail("DataRegistry.load_all_runtime_data returned %s" % err)
	var parameters_def: Dictionary = registry.get("parameters_def")
	var policies_def: Dictionary = registry.get("policies_def")
	var actions_def: Dictionary = registry.get("actions_def")
	var characters_def: Dictionary = registry.get("characters_def")
	if parameters_def.size() < 110:
		return _fail("parameters_def size %s" % parameters_def.size())
	if policies_def.size() != 76:
		return _fail("policies_def size %s" % policies_def.size())
	if actions_def.size() != 104:
		return _fail("actions_def size %s" % actions_def.size())
	if characters_def.size() != 43:
		return _fail("characters_def size %s" % characters_def.size())
	if not SimRNG.verify_t01_golden_vectors():
		return _fail("T01 golden vectors failed")
	if not SimCalendar.verify_t02_calendar_vectors():
		return _fail("T02 calendar vectors failed")
	if SimMath.imod_pos(-3, 7) != 4:
		return _fail("imod_pos")
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	for i: int in range(SimTypes.AUTHORITATIVE_RNG_STREAMS.size()):
		var stream_name: String = SimTypes.AUTHORITATIVE_RNG_STREAMS[i]
		var stream: SimRNG.Stream = state.rng.get_stream(stream_name)
		if stream.draws != 0:
			return _fail("RNG draws consumed during load for %s" % stream_name)
	var security: float = state.params.get_val("security_index", "", state)
	if absf(security - 62.0) > 0.000001:
		return _fail("security_index=%s" % security)
	var north: float = state.params.get_val("region_security", "north", state)
	var galilee: float = state.params.get_val("region_security", "galilee", state)
	if absf(north - galilee) > 0.000001:
		return _fail("region alias north=%s galilee=%s" % [north, galilee])
	if absf(state.params.get_val("mobilization", "", state) - 10.0) > 0.000001:
		return _fail("mobilization")
	var sample: Dictionary = {"b": 1.5, "a": 3}
	var canon: String = CanonicalSerializer.to_canonical_json_string(sample)
	if canon != "{\"a\":3000000,\"b\":1500000}":
		return _fail("canonical sample %s" % canon)
	var digest: String = CanonicalSerializer.compute_state_hash_sha256(state)
	if digest.length() != 64 or digest != digest.to_lower():
		return _fail("state hash %s" % digest)
	var again: String = CanonicalSerializer.compute_state_hash_sha256(state)
	if again != digest:
		return _fail("state hash unstable")
	if registry.get_custom_handler_owner("m01_trigger_tenure_end") != "M01":
		return _fail("handler m01")
	if registry.get_custom_handler_owner("m04_add_stance_by_corridor") != "M04":
		return _fail("handler m04")
	if registry.get_custom_handler_owner("m11_create_region") != "M11":
		return _fail("handler m11")
	if registry.resolve_party_id("alignment") != "labor":
		return _fail("party alias")
	if registry.resolve_pal_faction_id("notables") != "jordan_notables":
		return _fail("faction alias")
	var golden_security: float = _golden_public_security()
	if absf(golden_security - 62.0) > 0.000001:
		return _fail("golden public_security %s" % golden_security)
	print("M1_FOUNDATION_OK hash=%s" % digest)
	return 0


func _golden_public_security() -> float:
	var path: String = ProjectSettings.globalize_path("res://").path_join("../data/golden/begin_1977_365d.json")
	if not FileAccess.file_exists(path):
		push_error("golden file missing " + path)
		return -1.0
	var file: FileAccess = FileAccess.open(path, FileAccess.READ)
	if file == null:
		return -1.0
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return -1.0
	var root: Dictionary = parsed
	var checkpoints_v: Variant = root.get("checkpoints", [])
	if typeof(checkpoints_v) != TYPE_ARRAY:
		return -1.0
	var checkpoints: Array = checkpoints_v
	for i: int in range(checkpoints.size()):
		if typeof(checkpoints[i]) != TYPE_DICTIONARY:
			continue
		var row: Dictionary = checkpoints[i]
		if int(row.get("day_index", -1)) != 0:
			continue
		var key_params: Dictionary = row.get("key_params", {})
		return float(key_params.get("public_security", -1.0))
	return -1.0


func _fail(msg: String) -> int:
	push_error(msg)
	print("M1_FAIL: " + msg)
	return 1
