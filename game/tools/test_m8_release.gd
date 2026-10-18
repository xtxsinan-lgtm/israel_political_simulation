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
	print("M8_RELEASE_OK")
	return 0


func _fail(message: String) -> int:
	push_error(message)
	print("M8_FAIL %s" % message)
	return 1
