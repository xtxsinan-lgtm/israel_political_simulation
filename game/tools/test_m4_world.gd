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
	var mid: float = diplomacy.interpolate_world_track([{"t": 1977, "v": 0.0}, {"t": 1979, "v": 10.0}], 1978, 1)
	if absf(mid - 5.0) > 0.2:
		push_error("track %s" % mid)
		quit(1)
		return
	var countries: Dictionary = diplomacy._countries(state)
	var egypt: Dictionary = countries["egypt"]
	egypt["peace_treaty_state"] = 3
	countries["egypt"] = egypt
	var m07: Dictionary = state.modules["M07"]
	m07["countries"] = countries
	state.modules["M07"] = m07
	if diplomacy.compute_war_probability(state, "egypt") != 0.0:
		push_error("treaty war")
		quit(1)
		return
	var military: M09Military = M09Military.new()
	if not is_equal_approx(military.get_mobilization_growth_drag(3), -0.75):
		push_error("drag")
		quit(1)
		return
	state.params.set_val("faction_legitimacy", "fatah", 30.0, state)
	state.params.set_val("faction_legitimacy", "pflp", 70.0, state)
	var pal: M08Palestine = M08Palestine.new()
	pal._conserve_legitimacy(state)
	var leg: float = 0.0
	for i: int in range(M08Palestine.FACTIONS.size()):
		leg += state.params.get_val("faction_legitimacy", M08Palestine.FACTIONS[i], state)
	if absf(leg - 100.0) > 0.05:
		push_error("legitimacy %s" % leg)
		quit(1)
		return
	state.one_off_flows["budget_balance"] = -3.0
	var economy: M10Economy = M10Economy.new()
	economy.monthly_step(9, state, {})
	if float(state.one_off_flows["budget_balance"]) != 0.0:
		push_error("one off")
		quit(1)
		return
	var regions: M11Regions = M11Regions.new()
	regions.handle_custom_op("m11_activate_region", state, {"region": "south_lebanon"}, {})
	if not bool((state.modules["M11"]["regions"] as Dictionary)["south_lebanon"]["exists"]):
		push_error("region")
		quit(1)
		return
	state.params.set_val("centralization", "", 90.0, state)
	var auth: M13Authoritarian = M13Authoritarian.new()
	auth.monthly_step(14, state, {})
	if int(state.modules["M13"]["stage"]) != 5 or not bool(state.modules["M13"]["survival_mode"]):
		push_error("stage")
		quit(1)
		return
	print("M4_WORLD_OK")
	quit(0)
