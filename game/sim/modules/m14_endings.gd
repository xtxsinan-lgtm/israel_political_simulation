class_name M14Endings
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const ENDING_PRIORITY: Array[String] = [
	"military_coup", "assassination", "state_collapse", "constitutional_collapse",
	"election_defeat", "coalition_collapse", "budget_overdue", "full_term_retirement", "scenario_end_date",
]


func _init() -> void:
	module_id = "M14"


func daily_step(step_no: int, state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 20:
		return []
	return step_20(state, ctx)


func step_20(state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	var reason: String = _pick_reason(state)
	if reason == "" and state.clock.date < "1995-11-04":
		check_achievements(state, false)
		return []
	if reason == "":
		reason = "scenario_end_date"
	var m14: Dictionary = _m14(state)
	m14["end_reason"] = reason
	m14["primary_ending_id"] = _match_ending(state, reason)
	var evaluation: Dictionary = compute_final_evaluation(state)
	m14["evaluation"] = evaluation
	m14["epilogue"] = build_epilogue_book(state, evaluation)
	state.modules["M14"] = m14
	state.run["phase"] = "ENDED"
	check_achievements(state, true)
	return []


func compute_final_evaluation(state: SimState) -> Dictionary:
	var security_defense: float = clampf(state.params.get_val("deterrence", "", state), 0.0, 100.0)
	var diplomacy_peace: float = clampf(state.params.get_val("intl_legitimacy", "", state), 0.0, 100.0)
	var economy_prosperity: float = clampf(100.0 - state.params.get_val("inflation", "", state) * 0.4, 0.0, 100.0)
	var democracy_rule_of_law: float = clampf(state.params.get_val("rule_of_law", "", state), 0.0, 100.0)
	var social_cohesion: float = clampf(state.params.get_val("party_cohesion", "", state), 0.0, 100.0)
	var territorial_settlement: float = clampf(state.params.get_val("territorial_control", "", state), 0.0, 100.0)
	var aliyah_zionism: float = clampf(state.params.get_val("immigration_inflow", "", state) * 4.0, 0.0, 100.0)
	var political_survival: float = clampf(state.params.get_val("party_standing", "", state), 0.0, 100.0)
	var composite_score: float = (
		security_defense + diplomacy_peace + economy_prosperity + democracy_rule_of_law
		+ social_cohesion + territorial_settlement + aliyah_zionism + political_survival
	) / 8.0
	var vision: float = state.params.get_val("vision_progress", "", state)
	if vision >= 80.0:
		composite_score += 8.0
	var stage: int = int(_as_dict(state.modules.get("M13", {})).get("stage", 0))
	var redline: bool = stage >= 4 or democracy_rule_of_law < 35.0 or bool(_m14(state).get("constitutional_crisis", false))
	var letter: String = _letter(composite_score)
	if redline and (letter == "S" or letter == "A"):
		letter = "B"
	return {
		"security_defense": security_defense,
		"diplomacy_peace": diplomacy_peace,
		"economy_prosperity": economy_prosperity,
		"democracy_rule_of_law": democracy_rule_of_law,
		"social_cohesion": social_cohesion,
		"territorial_settlement": territorial_settlement,
		"aliyah_zionism": aliyah_zionism,
		"political_survival": political_survival,
		"composite_score": SimMath.quantize(composite_score),
		"letter": letter,
		"redline_cap": redline,
	}


func build_epilogue_book(state: SimState, eval_result: Dictionary) -> Array[Dictionary]:
	var chapters: Array[String] = [
		"政治生涯与联盟沉浮",
		"战争、条约与中东棋局",
		"谢克尔、通胀与社会转型",
		"土地、定居点与不可能三角",
		"最高法院、宪政遗产与后世盖棺定论",
	]
	var book: Array[Dictionary] = []
	for i: int in range(chapters.size()):
		book.append({
			"chapter": i + 1,
			"title": chapters[i],
			"body": "%s。任期至 %s，综合分 %s，等级 %s。" % [
				chapters[i], state.clock.date, eval_result.get("composite_score", 0), eval_result.get("letter", "C"),
			],
			"compare_to": ["begin", "shamir", "peres", "rabin"],
			"source": "epilogue_paragraphs",
		})
	return book


func check_achievements(state: SimState, is_end_of_tenure: bool) -> void:
	var unlocked: Dictionary = _as_dict(_m14(state).get("unlocked_achievements", {}))
	if state.flags.has("likud_in_power"):
		_grant(state, unlocked, "mahapach")
	if state.params.get_val("vision_progress", "", state) >= 80.0:
		_grant(state, unlocked, "vision_route")
	if is_end_of_tenure and String(_m14(state).get("primary_ending_id", "")) != "":
		_grant(state, unlocked, "tenure_closed")
	var m14: Dictionary = _m14(state)
	m14["unlocked_achievements"] = unlocked
	state.modules["M14"] = m14


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	match op_name:
		"m14_unlock_achievement":
			var unlocked: Dictionary = _as_dict(_m14(state).get("unlocked_achievements", {}))
			_grant(state, unlocked, String(args.get("id", "")))
			var m14: Dictionary = _m14(state)
			m14["unlocked_achievements"] = unlocked
			state.modules["M14"] = m14
			return []
		"m14_record_ending":
			var recorded: Dictionary = _m14(state)
			recorded["primary_ending_id"] = String(args.get("ending", recorded.get("primary_ending_id", "")))
			state.modules["M14"] = recorded
			return []
		"m14_record_turning_point", "m14_grant_achievement":
			return handle_custom_op("m14_unlock_achievement", state, {"id": String(args.get("id", args.get("achievement", "")))}, {})
		"m14_generate_fictional_leader":
			state.player["leader_id"] = "fictional_successor"
			state.player["fictional"] = true
			return []
		"end_tenure":
			state.pending["tenure_end"] = {"reason": String(args.get("reason", "full_term_retirement"))}
			return []
		_:
			return []
	return []


func _grant(state: SimState, unlocked: Dictionary, ach_id: String) -> void:
	if ach_id == "" or unlocked.has(ach_id):
		return
	unlocked[ach_id] = state.clock.day_index


func _pick_reason(state: SimState) -> String:
	var pending: Dictionary = _as_dict(state.pending.get("tenure_end", {}))
	var offered: Array[String] = []
	if pending.has("reason"):
		offered.append(String(pending["reason"]))
	var extra: Variant = pending.get("also", [])
	if typeof(extra) == TYPE_ARRAY:
		var also: Array = extra
		for i: int in range(also.size()):
			offered.append(String(also[i]))
	for i: int in range(ENDING_PRIORITY.size()):
		if offered.has(ENDING_PRIORITY[i]):
			return ENDING_PRIORITY[i]
	return ""


func _match_ending(state: SimState, reason: String) -> String:
	if reason == "military_coup" or reason == "assassination" or reason == "state_collapse":
		return "ending_collapse"
	if reason == "constitutional_collapse":
		return "ending_constitutional_collapse"
	if reason == "election_defeat" or reason == "coalition_collapse" or reason == "budget_overdue":
		return "ending_electoral_loss"
	if state.params.get_val("vision_progress", "", state) >= 80.0:
		return "ending_vision"
	return "ending_retirement"


func _letter(score: float) -> String:
	if score >= 90.0:
		return "S"
	if score >= 80.0:
		return "A"
	if score >= 70.0:
		return "B"
	if score >= 55.0:
		return "C"
	if score >= 40.0:
		return "D"
	return "F"


func _m14(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M14", {}))
	state.modules["M14"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
