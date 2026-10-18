extends SceneTree

const GOLDEN_PATH: String = "/Users/xutongxin/Developer/israel_political_simulation/data/golden/begin_1977_365d.json"


func _initialize() -> void:
	quit(_run())


func _run() -> int:
	var registry: GameData = GameData.new()
	if registry.load_all_runtime_data() != OK:
		return _fail("load")
	var file: FileAccess = FileAccess.open(GOLDEN_PATH, FileAccess.READ)
	if file == null:
		file = FileAccess.open("res://data/golden/begin_1977_365d.json", FileAccess.READ)
	if file == null:
		return _fail("golden file missing")
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(parsed) != TYPE_DICTIONARY:
		return _fail("golden json")
	var checkpoints: Array = (parsed as Dictionary).get("checkpoints", [])
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	state.run["headless"] = true
	var scheduler: DailyScheduler = DailyScheduler.new()
	var mismatches: int = 0
	var hash_matches: int = 0
	for i: int in range(checkpoints.size()):
		var row: Dictionary = checkpoints[i]
		var target: int = int(row.get("day_index", 0))
		while state.clock.day_index < target:
			var stepped: Dictionary = scheduler.execute_day(state)
			if bool(stepped.get("ended", false)) and state.clock.day_index < target:
				return _fail("ended early on %s" % state.clock.date)
		if state.clock.date != String(row.get("date", "")):
			mismatches += 1
			print("GOLDEN_DATE %s expected %s" % [state.clock.date, row.get("date", "")])
		var keys: Dictionary = row.get("key_params", {})
		var names: Array = keys.keys()
		names.sort()
		for k: int in range(names.size()):
			var name: String = String(names[k])
			var actual: float = state.params.get_val(name, "", state)
			var expected: float = float(keys[name])
			if absf(actual - expected) > 0.05:
				mismatches += 1
				if mismatches <= 12:
					print("GOLDEN_PARAM day=%d %s actual=%s expected=%s" % [target, name, actual, expected])
		var digest: String = CanonicalSerializer.compute_state_hash_sha256(state)
		if digest == String(row.get("state_hash", "")):
			hash_matches += 1
	print("GOLDEN_COMPARE checkpoints=%d hash_matches=%d param_mismatches=%d" % [checkpoints.size(), hash_matches, mismatches])
	if mismatches == 0 and hash_matches == checkpoints.size():
		print("GOLDEN_PARITY_365D_PASSED")
		return 0
	print("GOLDEN_PARITY_365D_DIVERGED")
	return 1


func _fail(message: String) -> int:
	push_error(message)
	print("GOLDEN_FAIL %s" % message)
	return 1
