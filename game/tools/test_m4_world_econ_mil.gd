extends SceneTree


func _initialize() -> void:
	_run()


func _run() -> void:
	var data: GameData = GameData.new()
	if data.load_all_runtime_data() != OK:
		push_error("load")
		quit(1)
		return
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	var diplomacy: M07Diplomacy = M07Diplomacy.new()
	diplomacy.handle_custom_op("m07_open_negotiation", state, {"summit": "camp_david_1978", "days": 13}, {})
	var issues: Dictionary = (state.modules["M07"]["summit"] as Dictionary)["issues"]
	if issues.size() != 4:
		push_error("camp david issues")
		quit(1)
		return
	var pal: M08Palestine = M08Palestine.new()
	var leg: float = 0.0
	for i: int in range(M08Palestine.FACTIONS.size()):
		state.params.set_val("faction_legitimacy", M08Palestine.FACTIONS[i], 1.0, state)
		leg += 1.0
	pal._conserve_legitimacy(state)
	leg = 0.0
	for i: int in range(M08Palestine.FACTIONS.size()):
		leg += state.params.get_val("faction_legitimacy", M08Palestine.FACTIONS[i], state)
	if absf(leg - 100.0) > 0.000001:
		push_error("legitimacy")
		quit(1)
		return
	var military: M09Military = M09Military.new()
	if not is_equal_approx(military.get_mobilization_growth_drag(3), -0.75):
		push_error("drag")
		quit(1)
		return
	state.flags["patriot_deployed"] = {"value": 1.0}
	state.params.set_val("missile_attacks", "", 10.0, state)
	var before: float = state.params.get_val("public_security", "", state)
	military.weekly_step(8, state, {})
	var after_patriot: float = state.params.get_val("public_security", "", state)
	state.flags.erase("patriot_deployed")
	state.params.set_val("public_security", "", before, state)
	military.weekly_step(8, state, {})
	var after_raw: float = state.params.get_val("public_security", "", state)
	if after_patriot <= after_raw:
		push_error("patriot")
		quit(1)
		return
	var regions: Dictionary = state.modules["M11"]["regions"]
	if bool((regions["south_lebanon"] as Dictionary).get("exists", true)):
		push_error("south lebanon")
		quit(1)
		return
	var central: M13Centralization = M13Centralization.new()
	if central.stage_label(10.0) != "C1" or central.stage_label(90.0) != "C5":
		push_error("stages")
		quit(1)
		return
	state.params.set_val("centralization", "", 90.0, state)
	central.monthly_step(15, state, {})
	if not bool(state.modules["M13"]["survival_mode"]):
		push_error("survival")
		quit(1)
		return
	print("M4_WORLD_ECON_MIL_ALL_PASSED")
	quit(0)
