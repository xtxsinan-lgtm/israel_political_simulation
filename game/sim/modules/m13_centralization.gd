class_name M13Centralization
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const ACTORS: Array[String] = [
	"supreme_court", "attorney_general", "idf_general_staff", "intelligence_community",
	"histadrut", "bank_of_israel", "free_press", "civil_society_reservists", "presidency",
]


func _init() -> void:
	module_id = "M13"


func stage_label(value: float) -> String:
	if value >= 85.0:
		return "C5"
	if value >= 65.0:
		return "C4"
	if value >= 45.0:
		return "C3"
	if value >= 25.0:
		return "C2"
	return "C1"


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 14:
		return []
	var central: float = state.params.get_val("centralization", "", state)
	var label: String = stage_label(central)
	var m13: Dictionary = _m13(state)
	m13["centralization_stage"] = label
	m13["stage"] = int(label.substr(1))
	var survival: bool = label == "C5" or bool(m13.get("suspend_elections_indefinitely", false))
	m13["survival_mode"] = survival
	m13["survival_mode_active"] = survival
	if survival:
		state.params.set_val("us_admin_relation", "", state.params.get_val("us_admin_relation", "", state) - 2.0, state)
		state.params.set_val("coup_risk", "", minf(100.0, state.params.get_val("coup_risk", "", state) * 2.0 + 1.0), state)
		state.params.set_val("assassination_risk", "", minf(100.0, state.params.get_val("assassination_risk", "", state) * 2.0 + 0.5), state)
		m13["social_protest_tier"] = maxi(2, int(m13.get("social_protest_tier", 0)))
	_evolve_actors(state, m13, central)
	if state.clock.y >= 1992 and bool(m13.get("aharon_barak", false)) and bool(m13.get("basic_law_dignity", false)):
		m13["constitutional_revolution"] = true
		var actors: Dictionary = _as_dict(m13.get("resist_actors", {}))
		var court: Dictionary = _as_dict(actors.get("supreme_court", {}))
		court["judicial_review"] = true
		actors["supreme_court"] = court
		m13["resist_actors"] = actors
	state.modules["M13"] = m13
	var effects: Array[Dictionary] = []
	if state.params.get_val("coup_risk", "", state) >= 90.0:
		effects.append({"op": "custom", "key": "end_tenure", "value": {"reason": "military_coup"}})
	if state.params.get_val("assassination_risk", "", state) >= 95.0:
		effects.append({"op": "custom", "key": "end_tenure", "value": {"reason": "assassination"}})
	return effects


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	var m13: Dictionary = _m13(state)
	match op_name:
		"m13_advance_stage":
			var nxt: float = float(args.get("centralization", state.params.get_val("centralization", "", state) + 20.0))
			state.params.set_val("centralization", "", clampf(nxt, 0.0, 100.0), state)
			m13["centralization_stage"] = stage_label(nxt)
			state.modules["M13"] = m13
			return []
		"m13_unlock_action":
			var unlocked: Dictionary = _as_dict(m13.get("unlocked_actions", {}))
			unlocked[String(args.get("action", ""))] = true
			m13["unlocked_actions"] = unlocked
			state.modules["M13"] = m13
			return []
		"m13_set_actor_posture":
			return _actor_field(state, String(args.get("actor", "")), "stance", String(args.get("posture", "watchful")))
		"m13_modify_actor_power":
			return _actor_add(state, String(args.get("actor", "")), "power", float(args.get("delta", 0.0)))
		"m13_modify_actor_autonomy":
			return _actor_add(state, String(args.get("actor", "")), "autonomy", float(args.get("delta", 0.0)))
		"m13_trigger_counter_action":
			return [{"op": "set_flag", "flag": "counter." + String(args.get("actor", "supreme_court")), "value": 1.0}]
		"m13_escalate_protest":
			var tier: int = mini(3, int(m13.get("social_protest_tier", 0)) + int(args.get("steps", 1)))
			m13["social_protest_tier"] = tier
			state.modules["M13"] = m13
			if tier >= 2:
				state.params.set_val("growth", "", state.params.get_val("growth", "", state) - 0.4, state)
			return []
		"m13_apply_centralization_impulse":
			state.params.set_val("centralization", "", clampf(state.params.get_val("centralization", "", state) + float(args.get("value", 0.0)), 0.0, 100.0), state)
			return []
		_:
			return []
	return []


func _evolve_actors(state: SimState, m13: Dictionary, central: float) -> void:
	var actors: Dictionary = _as_dict(m13.get("resist_actors", {}))
	for i: int in range(ACTORS.size()):
		var row: Dictionary = _as_dict(actors.get(ACTORS[i], {"power": 50.0, "autonomy": 60.0, "stance": "compliant"}))
		var pressure: float = central - float(row.get("autonomy", 60.0))
		var stance: String = "compliant"
		if pressure > 40.0:
			stance = "defiant"
		elif pressure > 25.0:
			stance = "obstructing"
		elif pressure > 10.0:
			stance = "watchful"
		row["stance"] = stance
		actors[ACTORS[i]] = row
		if stance == "obstructing" or stance == "defiant":
			m13["last_counter"] = ACTORS[i]
	m13["resist_actors"] = actors


func _actor_field(state: SimState, actor: String, field: String, value: String) -> Array[Dictionary]:
	var m13: Dictionary = _m13(state)
	var actors: Dictionary = _as_dict(m13.get("resist_actors", {}))
	var row: Dictionary = _as_dict(actors.get(actor, {}))
	row[field] = value
	actors[actor] = row
	m13["resist_actors"] = actors
	state.modules["M13"] = m13
	return []


func _actor_add(state: SimState, actor: String, field: String, delta: float) -> Array[Dictionary]:
	var m13: Dictionary = _m13(state)
	var actors: Dictionary = _as_dict(m13.get("resist_actors", {}))
	var row: Dictionary = _as_dict(actors.get(actor, {}))
	row[field] = float(row.get(field, 50.0)) + delta
	actors[actor] = row
	m13["resist_actors"] = actors
	state.modules["M13"] = m13
	return []


func _m13(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M13", {}))
	if not current.has("aharon_barak"):
		current["aharon_barak"] = false
		current["suspend_elections_indefinitely"] = false
		current["social_protest_tier"] = 0
	state.modules["M13"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
