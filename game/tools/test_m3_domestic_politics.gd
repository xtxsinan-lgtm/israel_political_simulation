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
	var parliament: M03Parliament = M03Parliament.new()
	var early: Dictionary = parliament.allocate_knesset_seats({"likud": 40.0, "labor": 35.0, "small": 0.8, "rest": 24.2}, 1977, [])
	var late: Dictionary = parliament.allocate_knesset_seats({"likud": 40.0, "labor": 35.0, "small": 1.2, "rest": 23.8}, 1992, [])
	if _sum(early) != 120 or _sum(late) != 120 or int(late.get("small", 0)) != 0:
		push_error("seats")
		quit(1)
		return
	var m03: Dictionary = state.modules["M03"]
	m03["months_to_election"] = 4
	state.modules["M03"] = m03
	var rng: SimRNG.Stream = state.rng.get_stream("politics")
	var failed: Array[Dictionary] = parliament._resolve_scheduled_bill({"vote": "absolute80", "votes_for_override": 65, "extend_months": 6, "uid": "postpone"}, state, rng)
	if bool((failed[0]["value"] as Dictionary)["passed"]):
		push_error("absolute80 65 passed")
		quit(1)
		return
	var passed: Array[Dictionary] = parliament._resolve_scheduled_bill({"vote": "absolute80", "votes_for_override": 82, "extend_months": 6, "uid": "postpone"}, state, rng)
	if not bool((passed[0]["value"] as Dictionary)["passed"]):
		push_error("absolute80 82 failed")
		quit(1)
		return
	if int(state.modules["M03"]["months_to_election"]) != 10:
		push_error("months")
		quit(1)
		return
	var party: M04Party = M04Party.new()
	if party.compute_grace_factor(3) != 0.0 or not is_equal_approx(party.compute_grace_factor(15), 0.5) or party.compute_grace_factor(24) != 1.0:
		push_error("grace")
		quit(1)
		return
	var m06: Dictionary = state.modules["M06"]
	m06["offices"] = {"defense": "weizman", "foreign": "weizman", "finance": "dayan"}
	m06["characters"] = {"weizman": {"faction": "herut", "is_living_person": false, "playable_as_pm": true}, "dayan": {"faction": "labor"}, "meridor": {"faction": "liberal", "is_living_person": true, "playable_as_pm": false}}
	state.modules["M06"] = m06
	state.offices = m06["offices"]
	var share: float = party.compute_faction_minister_share(state, "herut")
	if not is_equal_approx(share, 0.5):
		push_error("minister share %s" % share)
		quit(1)
		return
	var actions: M05Actions = M05Actions.new()
	var capped: float = actions.apply_pc_soft_cap(state, 100.0)
	if not is_equal_approx(capped, 94.0):
		push_error("cap")
		quit(1)
		return
	var m05: Dictionary = state.modules["M05"]
	m05["active_actions"] = [{"id": "demo_act", "remaining_days": 1, "effects": []}]
	state.modules["M05"] = m05
	actions.daily_step(5, state, {})
	if not state.flags.has("act.demo_act"):
		push_error("act flag")
		quit(1)
		return
	state.params.set_val("political_capital", "", 40.0, state)
	m05 = state.modules["M05"]
	m05["weekly_slots_used"] = 0
	m05["staged_actions"] = [{"id": "minister_idea", "is_minister_proposal": true, "pc_cost": 10, "days": 2, "kind": "MinisterProposal"}]
	state.modules["M05"] = m05
	actions.daily_step(2, state, {})
	if int(state.modules["M05"]["weekly_slots_used"]) != 0:
		push_error("slot")
		quit(1)
		return
	if not is_equal_approx(state.params.get_val("political_capital", "", state), 33.0):
		push_error("discount pc")
		quit(1)
		return
	state.params.set_val("relation", "weizman", 42.0, state)
	var via_office: float = state.params.get_val("relation", "defense_minister", state)
	if not is_equal_approx(via_office, 42.0):
		push_error("defense_minister relation %s" % via_office)
		quit(1)
		return
	var characters: M06Characters = M06Characters.new()
	characters.handle_custom_op("m06_pick_successor", state, {"character": "meridor", "same_party": true}, {})
	if String(state.player.get("successor", "")) == "meridor":
		push_error("living successor")
		quit(1)
		return
	if not is_equal_approx(state.params.get_val("political_capital", "", state), 40.0):
		push_error("pc reset")
		quit(1)
		return
	print("M3_DOMESTIC_POLITICS_OK")
	quit(0)


func _sum(seats: Dictionary) -> int:
	var total: int = 0
	var ids: Array[String] = SimMath.sorted_keys(seats)
	for i: int in range(ids.size()):
		total += int(seats[ids[i]])
	return total
