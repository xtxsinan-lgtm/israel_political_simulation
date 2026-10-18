class_name M06Characters
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const OFFICE_IDS: Array[String] = [
	"pm", "defense_minister", "foreign_minister", "finance_minister", "interior_minister",
	"justice_minister", "housing_minister", "education_minister", "religion_minister",
	"chief_of_staff", "mossad_director", "shin_bet_director", "boj_governor", "ag_advisor",
]


func _init() -> void:
	module_id = "M06"


func recompute_appointment_gap(state: SimState) -> void:
	var expected: Dictionary = {"mizrahi": 0.35, "haredi": 0.12, "ashkenazi": 0.45, "arab": 0.08}
	var offices: Dictionary = _offices(state)
	var characters: Dictionary = _characters(state)
	var counts: Dictionary = {}
	var total: int = 0
	var keys: Array[String] = SimMath.sorted_keys(offices)
	var seen: Dictionary = {}
	for i: int in range(keys.size()):
		var holder: String = String(offices[keys[i]])
		if holder == "" or seen.has(holder):
			continue
		seen[holder] = true
		total += 1
		var group: String = String(_as_dict(characters.get(holder, {})).get("group", "ashkenazi"))
		counts[group] = int(counts.get(group, 0)) + 1
	var groups: Array[String] = SimMath.sorted_keys(expected)
	for i: int in range(groups.size()):
		var actual: float = 0.0
		if total > 0:
			actual = float(int(counts.get(groups[i], 0))) / float(total)
		var gap: float = actual - float(expected[groups[i]])
		state.params.set_val("appointment_gap", groups[i], SimMath.quantize(gap * 100.0), state)


func weekly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 6:
		return []
	recompute_appointment_gap(state)
	var rng: SimRNG.Stream = state.rng.get_stream("characters")
	var proposal: Dictionary = {}
	if rng.chance(0.15):
		proposal = {"id": "minister_proposal", "is_minister_proposal": true, "pc_cost": 10, "days": 3}
		var m05: Dictionary = _as_dict(state.modules.get("M05", {}))
		var staged: Array = []
		if typeof(m05.get("staged_actions", [])) == TYPE_ARRAY:
			staged = m05["staged_actions"]
		if staged.is_empty():
			staged.append(proposal)
			m05["staged_actions"] = staged
			state.modules["M05"] = m05
	return []


func annual_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 17:
		return []
	var characters: Dictionary = _characters(state)
	var ids: Array[String] = SimMath.sorted_keys(characters)
	var effects: Array[Dictionary] = []
	for i: int in range(ids.size()):
		var row: Dictionary = _as_dict(characters[ids[i]])
		row["age"] = int(row.get("age", 40)) + 1
		var stress: float = state.params.get_val("character_stress", ids[i], state)
		var health: float = state.params.get_val("health", ids[i], state)
		if health <= 0.0:
			health = float(row.get("health", 80.0))
		health = clampf(health - 0.4 - stress * 0.02, 0.0, 100.0)
		if ids[i] == "begin" and state.clock.y >= 1982:
			health -= 4.0
		state.params.set_val("health", ids[i], health, state)
		row["health"] = health
		characters[ids[i]] = row
		if health <= 5.0 and bool(row.get("alive", true)):
			effects.append_array(handle_custom_op("m06_kill_character", state, {"character": ids[i], "cause": "health"}, {}))
	var m06: Dictionary = _m06(state)
	m06["characters"] = characters
	state.modules["M06"] = m06
	return effects


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	match op_name:
		"m06_appoint":
			return _appoint(state, String(args.get("office", "")), String(args.get("character", "")), false)
		"m06_dismiss":
			return _appoint(state, String(args.get("office", "")), "", true)
		"m06_open_reshuffle":
			var m06: Dictionary = _m06(state)
			m06["reshuffle_open"] = true
			state.modules["M06"] = m06
			return []
		"m06_add_relation_cabinet":
			state.params.set_val("relation", String(args.get("character", "")), state.params.get_val("relation", String(args.get("character", "")), state) + float(args.get("value", 0.0)), state)
			return []
		"m06_promote_group":
			state.params.set_val("appointment_gap", String(args.get("group", "mizrahi")), state.params.get_val("appointment_gap", String(args.get("group", "mizrahi")), state) + float(args.get("value", 1.0)), state)
			return []
		"m06_pick_successor":
			state.player["successor"] = String(args.get("character", ""))
			return []
		"m06_rebase_relations":
			return []
		"m06_health_check":
			return annual_step(17, state, {})
		"m06_kill_character":
			return _kill(state, String(args.get("character", "")))
		"m06_inquiry_report":
			return _appoint(state, "defense_minister", "", true)
		_:
			return []
	return []


func _appoint(state: SimState, office: String, who: String, dismissed: bool) -> Array[Dictionary]:
	if office == "":
		return []
	var m06: Dictionary = _m06(state)
	var offices: Dictionary = _as_dict(m06.get("offices", {}))
	var previous: String = String(offices.get(office, ""))
	offices[office] = who
	m06["offices"] = offices
	state.modules["M06"] = m06
	state.offices[office] = who
	recompute_appointment_gap(state)
	if dismissed and previous != "" and previous != String(state.player.get("leader_id", "")):
		return [{"op": "set_flag", "flag": "ally_minister_dismissed", "value": 1.0, "source": previous}]
	return []


func _kill(state: SimState, char_id: String) -> Array[Dictionary]:
	if char_id == "":
		return []
	var m06: Dictionary = _m06(state)
	var characters: Dictionary = _as_dict(m06.get("characters", {}))
	var row: Dictionary = _as_dict(characters.get(char_id, {}))
	row["alive"] = false
	characters[char_id] = row
	m06["characters"] = characters
	var offices: Dictionary = _as_dict(m06.get("offices", {}))
	var keys: Array[String] = SimMath.sorted_keys(offices)
	for i: int in range(keys.size()):
		if String(offices[keys[i]]) == char_id:
			offices[keys[i]] = ""
	m06["offices"] = offices
	state.modules["M06"] = m06
	return []


func _offices(state: SimState) -> Dictionary:
	return _as_dict(_m06(state).get("offices", {}))


func _characters(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(_m06(state).get("characters", {}))
	if current.is_empty() and GameData.current != null:
		var ids: Array[String] = SimMath.sorted_keys(GameData.current.characters_def)
		for i: int in range(ids.size()):
			var src: Dictionary = _as_dict(GameData.current.characters_def[ids[i]])
			current[ids[i]] = {
				"age": int(src.get("age_1977", src.get("age", 40))),
				"alive": bool(src.get("alive_1977", true)),
				"group": String(src.get("group", src.get("ethnic", "ashkenazi"))),
				"faction": String(src.get("faction", "")),
				"health": 80.0,
			}
		var m06: Dictionary = _m06(state)
		m06["characters"] = current
		state.modules["M06"] = m06
	return current


func _m06(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M06", {}))
	state.modules["M06"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
