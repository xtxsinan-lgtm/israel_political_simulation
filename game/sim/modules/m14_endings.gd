class_name M14Endings
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

## Python sim/modules.py ENDING_PRIORITY, extended with the legacy GD-only reasons.
const ENDING_PRIORITY: Array[String] = [
	"state_collapse", "assassination", "coup", "death", "overthrow", "constitutional_collapse",
	"health_incapacity", "primary_loss", "no_confidence", "coalition_failure", "budget_overdue",
	"election_loss", "resignation", "player_quit", "full_term_retirement", "scenario_end_date",
]
const REASON_ALIASES: Dictionary = {
	"military_coup": "coup",
	"election_defeat": "election_loss",
	"coalition_collapse": "coalition_failure",
}
## Python: end of the 15-year historical era (day 5478 = 1992-06-19).
const ERA_END_DAY: int = 5478
const TERMINAL_REASONS: Array[String] = ["state_collapse", "coup", "assassination", "overthrow"]


func _init() -> void:
	module_id = "M14"


func daily_step(step_no: int, state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 20:
		return []
	return step_20(state, ctx)


func step_20(state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if bool(state.run.get("perf_bench", false)):
		return []
	if String(state.run.get("phase", "")) == "ENDED":
		return []
	var candidates: Array[String] = _pending_reasons(state)
	var m14: Dictionary = _m14(state)
	var danger: bool = (
		state.params.get_val("fx_reserves", "", state) <= 3.0
		and state.params.get_val("inflation", "", state) >= 380.0
		and state.params.get_val("public_security", "", state) <= 22.0
	)
	var streak: int = int(m14.get("collapse_danger_streak_days", 0))
	streak = streak + 1 if danger else maxi(0, streak - 1)
	m14["collapse_danger_streak_days"] = streak
	if danger and streak >= 30:
		candidates.append("state_collapse")
	var leader: String = str(state.player.get("leader_id", "begin"))
	if state.params.get_active_keys("health").has(leader):
		var health: float = state.params.get_val("health", leader, state)
		var stress: float = state.params.get_val("character_stress", leader, state)
		if health <= 0.0:
			candidates.append("death")
		elif health <= 20.0 or (health <= 27.0 and stress >= 72.0):
			candidates.append("health_incapacity")
	if state.clock.day_index >= ERA_END_DAY and candidates.is_empty():
		if state.params.get_val("centralization", "", state) >= 48.0:
			candidates.append("overthrow")
		elif state.params.get_val("coalition_seats", "", state) < 61.0 or state.params.get_val("party_cohesion", "", state) < 48.0:
			candidates.append("coalition_failure")
		elif state.params.get_val("poll_lead", "", state) < -1.0:
			candidates.append("election_loss")
		else:
			candidates.append("resignation")
	state.modules["M14"] = m14
	var reason: String = _highest_priority(candidates)
	if reason == "":
		check_achievements(state, false)
		return []
	m14 = _m14(state)
	m14["end_reason"] = reason
	m14["primary_ending_id"] = _match_ending(state, reason)
	var evaluation: Dictionary = compute_final_evaluation(state)
	m14["evaluation"] = evaluation
	m14["epilogue"] = build_epilogue_book(state, evaluation)
	m14["run_terminal"] = TERMINAL_REASONS.has(reason) or state.clock.day_index >= ERA_END_DAY
	state.modules["M14"] = m14
	state.pending["tenure_end"] = reason
	# Succession (Python continue_as_successor) is not ported yet, so every tenure end ends the run.
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
			state.pending["tenure_end"] = _normalize_reason(str(args.get("reason", "resignation")))
			return []
		_:
			return []
	return []


func _grant(state: SimState, unlocked: Dictionary, ach_id: String) -> void:
	if ach_id == "" or unlocked.has(ach_id):
		return
	unlocked[ach_id] = state.clock.day_index


func _normalize_reason(raw: String) -> String:
	return String(REASON_ALIASES.get(raw, raw))


## pending.tenure_end is a String in the Python convention (written by M01 end_tenure and
## M06 death) or a legacy Dictionary {"reason": ..., "also": [...]}.
func _pending_reasons(state: SimState) -> Array[String]:
	var offered: Array[String] = []
	var raw: Variant = state.pending.get("tenure_end", null)
	if typeof(raw) == TYPE_STRING or typeof(raw) == TYPE_STRING_NAME:
		if str(raw) != "":
			offered.append(_normalize_reason(str(raw)))
	elif typeof(raw) == TYPE_DICTIONARY:
		var pending: Dictionary = raw
		if pending.has("reason") and str(pending["reason"]) != "":
			offered.append(_normalize_reason(str(pending["reason"])))
		var extra: Variant = pending.get("also", [])
		if typeof(extra) == TYPE_ARRAY:
			var also: Array = extra
			for i: int in range(also.size()):
				offered.append(_normalize_reason(str(also[i])))
	return offered


func _highest_priority(candidates: Array[String]) -> String:
	if candidates.is_empty():
		return ""
	for i: int in range(ENDING_PRIORITY.size()):
		if candidates.has(ENDING_PRIORITY[i]):
			return ENDING_PRIORITY[i]
	return candidates[0]


func _pick_reason(state: SimState) -> String:
	return _highest_priority(_pending_reasons(state))


func _match_ending(state: SimState, reason: String) -> String:
	match reason:
		"state_collapse", "coup", "assassination", "overthrow":
			return "ending_collapse"
		"constitutional_collapse":
			return "ending_constitutional_collapse"
		"death", "health_incapacity":
			return "ending_died_in_office"
		"primary_loss", "no_confidence", "coalition_failure", "budget_overdue", "election_loss":
			return "ending_electoral_loss"
		_:
			pass
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
