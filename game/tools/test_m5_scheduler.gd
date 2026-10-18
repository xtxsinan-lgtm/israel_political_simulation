extends SceneTree


func _initialize() -> void:
	quit(_run())


func _run() -> int:
	var registry: GameData = GameData.new()
	if registry.load_all_runtime_data() != OK:
		return _fail("load")
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	state.run["headless"] = true
	var scheduler: DailyScheduler = DailyScheduler.new()
	var first: Dictionary = scheduler.execute_day(state)
	if String(first.get("date", "")) != "1977-06-21":
		return _fail("date %s" % first.get("date", ""))
	var trace: String = String(first.get("trace", ""))
	if trace != "1,2,3,4,5,18,20":
		return _fail("weekday trace %s" % trace)
	var hash_a: String = CanonicalSerializer.compute_state_hash_sha256(state)
	var twin: SimState = SimState.new()
	twin.init_from_scenario_bundle("begin_1977", 19770620, false)
	twin.run["headless"] = true
	DailyScheduler.new().execute_day(twin)
	if CanonicalSerializer.compute_state_hash_sha256(twin) != hash_a:
		return _fail("day1 hash diverged")
	var sunday: Dictionary = {}
	while state.clock.day_index < 6:
		sunday = scheduler.execute_day(state)
	if not String(sunday.get("trace", "")).contains("6,7,8"):
		return _fail("sunday trace %s" % sunday.get("trace", ""))
	while state.clock.day_index < 11:
		scheduler.execute_day(state)
	if state.clock.date != "1977-07-01":
		return _fail("month date %s" % state.clock.date)
	if state.monthly_snapshots.is_empty():
		return _fail("monthly snapshot missing")
	var snap: SimReadonlySnapshot = SimReadonlySnapshot.capture(state)
	var before: float = snap.read_param("public_security")
	state.params.set_val("public_security", "", 1.0, state)
	if absf(snap.read_param("public_security") - before) > 0.000001:
		return _fail("snapshot mutated")
	var paused: SimState = SimState.new()
	paused.init_from_scenario_bundle("begin_1977", 19770620, false)
	paused.modules["M12"] = {"pending_events": [{"id": "E-TEST"}]}
	if not AutoPauseEvaluator.should_auto_pause(paused):
		return _fail("expected pause")
	paused.run["headless"] = true
	if AutoPauseEvaluator.should_auto_pause(paused):
		return _fail("headless must not pause")
	var events: M12Events = M12Events.new()
	var m12: Dictionary = {"major_events_this_month": 3}
	var today: Array[Dictionary] = [{"id": "E-CAP", "modal_class": "major", "major": true, "bypass_cap": false}]
	events._apply_throttle(paused, m12, today)
	if not today.is_empty():
		return _fail("major cap")
	var crisis: Array[Dictionary] = [{"id": "E-WAR", "modal_class": "crisis", "bypass_cap": true}]
	events._apply_throttle(paused, m12, crisis)
	if crisis.size() != 1:
		return _fail("bypass cap")
	state.params.set_val("deterrence", "", 100.0, state)
	state.params.set_val("intl_legitimacy", "", 100.0, state)
	state.params.set_val("inflation", "", 0.0, state)
	state.params.set_val("rule_of_law", "", 95.0, state)
	state.params.set_val("party_cohesion", "", 100.0, state)
	state.params.set_val("territorial_control", "", 100.0, state)
	state.params.set_val("immigration_inflow", "", 30.0, state)
	state.params.set_val("party_standing", "", 100.0, state)
	state.modules["M13"] = {"stage": 4}
	var graded: Dictionary = M14Endings.new().compute_final_evaluation(state)
	if String(graded.get("letter", "")) != "B":
		return _fail("redline letter %s" % graded.get("letter", ""))
	var book: Array[Dictionary] = M14Endings.new().build_epilogue_book(state, graded)
	if book.size() != 5:
		return _fail("epilogue")
	state.pending["tenure_end"] = {"reason": "election_defeat", "also": ["military_coup"]}
	M14Endings.new().step_20(state, {})
	var ended: Dictionary = state.modules["M14"]
	if String(ended.get("end_reason", "")) != "military_coup":
		return _fail("arbitration %s" % ended.get("end_reason", ""))
	var director: SimDirector = SimDirector.new()
	if director.start_new_game("begin_1977", 19770620, false) != OK:
		return _fail("start")
	director.state.run["headless"] = true
	director.step_one_day()
	if director.get_state_hash_sha256().length() != 64:
		return _fail("engine hash")
	var bot: BotAdapters.HistoricalBeginBot = BotAdapters.HistoricalBeginBot.new()
	if bot.choose_event_option(director.state, {}, [{"id": "A"}, {"id": "B", "historical": true}]) != "B":
		return _fail("historical bot")
	print("M5_SCHEDULER_OK")
	return 0


func _fail(message: String) -> int:
	push_error(message)
	print("M5_SCHEDULER_FAIL %s" % message)
	return 1
