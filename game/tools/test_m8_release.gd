extends SceneTree


func _initialize() -> void:
	quit(_run())


func _run() -> int:
	var guide: OnboardingDirector = OnboardingDirector.new()
	guide._ready()
	guide.advance()
	if guide.step != 1:
		return _fail("step")
	guide.skip_tutorial()
	if not guide.finished():
		return _fail("skip")
	var skins: EraSkinManager = EraSkinManager.new()
	if skins.era_for_date("1978-01-01") != "era_1970s":
		return _fail("1970s")
	if skins.era_for_date("1985-06-01") != "era_1980s":
		return _fail("1980s")
	if skins.era_for_date("1992-03-01") != "era_1990s":
		return _fail("1990s")
	var audio: Node = root.get_node("AudioManager")
	audio.call("set_modal_ducking", true)
	var bus_index: int = AudioServer.get_bus_index("BGM")
	if bus_index < 0 or absf(AudioServer.get_bus_volume_db(bus_index) - (-8.0)) > 0.01:
		return _fail("duck")
	var access: Node = root.get_node("AccessibilityManager")
	access.call("set_scale_index", 0)
	if SimMath.round_half_up_int(float(access.call("font_px", 12))) < 12:
		return _fail("font floor")
	access.call("set_palette", "Deuteranopia")
	var registry: GameData = GameData.new()
	if registry.load_all_runtime_data() != OK:
		return _fail("load")
	var live: SimDirector = SimDirector.new()
	live.start_new_game("begin_1977", 19770620, false)
	live.state.run["headless"] = true
	live.submit_command({"op": "set_region_priority", "region": "galilee", "param": "region_investment_priority", "value": 40.0})
	for _i: int in range(4):
		live.step_one_day()
	var expected: String = live.get_state_hash_sha256()
	var saver: SaveSystem = SaveSystem.new()
	var envelope: Dictionary = saver.build_envelope(live.state, live.command_log)
	var restored: Dictionary = saver.from_ipsave_json(saver.to_ipsave_json(envelope))
	if typeof(restored.get("day_index", null)) != TYPE_INT:
		return _fail("day type")
	if String(restored.get("state_sha256", "")) != expected:
		return _fail("saved hash")
	var replay: Dictionary = ReplaySystem.new().run_headless_replay({
		"scenario_id": "begin_1977",
		"seed": 19770620,
		"target_day": live.state.clock.day_index,
		"command_log": live.command_log,
	})
	if String(replay.get("state_sha256", "")) != expected:
		return _fail("replay hash")
	var reloaded: SimDirector = SimDirector.new()
	if saver.load_into(reloaded, restored) != OK:
		return _fail("load_into")
	if reloaded.get_state_hash_sha256() != expected:
		return _fail("reloaded hash")
	if reloaded.command_log.size() != live.command_log.size():
		return _fail("reloaded command log")
	reloaded.state.run["headless"] = true
	for _j: int in range(3):
		live.step_one_day()
		reloaded.step_one_day()
	if reloaded.get_state_hash_sha256() != live.get_state_hash_sha256():
		return _fail("post-load divergence")
	var seeded: SimDirector = SimDirector.new()
	seeded.start_new_game("begin_1977", 4242, false)
	seeded.state.run["headless"] = true
	for _k: int in range(2):
		seeded.step_one_day()
	var seeded_env: Dictionary = saver.from_ipsave_json(saver.to_ipsave_json(saver.build_envelope(seeded.state, seeded.command_log)))
	if int(seeded_env.get("master_seed", 0)) != 4242:
		return _fail("seed not saved")
	var seeded_back: SimDirector = SimDirector.new()
	if saver.load_into(seeded_back, seeded_env) != OK or seeded_back.get_state_hash_sha256() != seeded.get_state_hash_sha256():
		return _fail("custom seed reload")
	var bogus: Error = live.submit_command({"op": "no_such_op"})
	if bogus == OK or String(live.command_log[live.command_log.size() - 1].get("cmd_type", "")) == "no_such_op":
		return _fail("invalid command logged")
	print("M8_RELEASE_OK")
	return 0


func _fail(message: String) -> int:
	push_error(message)
	print("M8_FAIL %s" % message)
	return 1
