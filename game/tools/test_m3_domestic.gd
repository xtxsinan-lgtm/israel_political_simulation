extends SceneTree


func _initialize() -> void:
	_run()


func _run() -> void:
	var data: GameData = GameData.new()
	if data.load_all_runtime_data() != OK:
		push_error("load failed")
		quit(1)
		return
	var parliament: M03Parliament = M03Parliament.new()
	if not _seats_always_120(parliament):
		quit(1)
		return
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	var party: M04Party = M04Party.new()
	if not is_equal_approx(party.compute_grace_factor(6), 0.0):
		push_error("grace 6")
		quit(1)
		return
	if not is_equal_approx(party.compute_grace_factor(12), 6.0 / 18.0):
		push_error("grace 12")
		quit(1)
		return
	if not is_equal_approx(party.compute_grace_factor(24), 1.0):
		push_error("grace 24")
		quit(1)
		return
	var bounds: Vector2 = party.get_corridor_bounds(state, "territory")
	if not is_equal_approx(bounds.x, -11.9) or not is_equal_approx(bounds.y, 91.8):
		push_error("corridor")
		quit(1)
		return
	state.params.set_val("party_standing", "", 50.0, state)
	state.params.set_val("coalition_seats", "", 61.0, state)
	state.params.set_val("govt_fatigue", "", 0.0, state)
	var actions: M05Actions = M05Actions.new()
	var income: float = actions.compute_monthly_pc_income(state)
	if income < 3.0 or income > 28.0 or not is_equal_approx(income, 8.0):
		push_error("pc income %s" % income)
		quit(1)
		return
	var capped: float = actions.apply_pc_soft_cap(state, 100.0)
	if not is_equal_approx(capped, 94.0):
		push_error("soft cap %s" % capped)
		quit(1)
		return
	if actions.minister_proposal_cost(10) != 7:
		push_error("minister discount")
		quit(1)
		return
	var characters: M06Characters = M06Characters.new()
	characters.recompute_appointment_gap(state)
	var below: Dictionary = parliament.allocate_knesset_seats({"tiny": 1.2, "big": 98.8}, 1992, [])
	if int(below["tiny"]) != 0 or int(below["big"]) != 120:
		push_error("threshold seats %s" % below)
		quit(1)
		return
	print("M3_DOMESTIC_OK")
	quit(0)


func _seats_always_120(parliament: M03Parliament) -> bool:
	var cases: Array[Dictionary] = [
		{"a": 50.0, "b": 30.0, "c": 20.0},
		{"a": 10.0, "b": 10.0, "c": 10.0, "d": 70.0},
		{"only": 3.0},
		{"a": 0.4, "b": 0.6},
	]
	for i: int in range(cases.size()):
		var seats: Dictionary = parliament.allocate_knesset_seats(cases[i], 1977, [])
		var total: int = 0
		var ids: Array[String] = SimMath.sorted_keys(seats)
		for k: int in range(ids.size()):
			total += int(seats[ids[k]])
		if total != 120:
			push_error("seat sum %s for %s" % [total, cases[i]])
			return false
		var paired: Dictionary = parliament.allocate_knesset_seats(cases[0], 1977, [["a", "b"]])
		var paired_total: int = 0
		var pids: Array[String] = SimMath.sorted_keys(paired)
		for k: int in range(pids.size()):
			paired_total += int(paired[pids[k]])
		if paired_total != 120:
			push_error("paired sum %s" % paired_total)
			return false
	return true
