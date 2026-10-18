class_name M13Authoritarian
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.

const ACTORS: Array[String] = ["supreme_court", "attorney_general", "idf_command", "reservists", "histadrut", "independent_media", "coalition_allies", "us_institutions", "party_constitutionalists"]


func _init() -> void:
	module_id = "M13"


func stage_from_centralization(value: float) -> int:
	if value >= 85.0:
		return 5
	if value >= 65.0:
		return 4
	if value >= 45.0:
		return 3
	if value >= 25.0:
		return 2
	if value >= 0.0:
		return 1
	return 0


func monthly_step(step_no: int, state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 14:
		return []
	var central: float = state.params.get_val("centralization", "", state)
	var stage: int = stage_from_centralization(central)
	var m13: Dictionary = _m13(state)
	m13["stage"] = stage
	m13["survival_mode"] = stage >= 5
	m13["survival_mode_active"] = stage >= 5
	var actors: Dictionary = _as_dict(m13.get("resist_actors", {}))
	for i: int in range(ACTORS.size()):
		var row: Dictionary = _as_dict(actors.get(ACTORS[i], {"stance": "dormant", "tension": 10.0}))
		var tension: float = float(row.get("tension", 10.0)) + maxf(0.0, central - 40.0) * 0.05
		row["tension"] = tension
		if tension >= 70.0:
			row["stance"] = "strike"
		elif tension >= 45.0:
			row["stance"] = "resist"
		else:
			row["stance"] = "dormant"
		actors[ACTORS[i]] = row
	m13["resist_actors"] = actors
	var protest: int = 0
	if central >= 75.0:
		protest = 3
	elif central >= 60.0:
		protest = 2
	elif central >= 45.0:
		protest = 1
	m13["protest_tier"] = protest
	state.modules["M13"] = m13
	var coup: float = clampf((central - 60.0) * 0.4 + float(_as_dict(actors.get("idf_command", {})).get("tension", 0.0)) * 0.1, 0.0, 100.0)
	state.params.set_val("coup_risk", "", coup, state)
	state.params.set_val("assassination_risk", "", coup * 0.3, state)
	return []


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	if op_name != "m13_apply_centralization_impulse":
		return []
	var next: float = state.params.get_val("centralization", "", state) + float(args.get("value", 0.0))
	state.params.set_val("centralization", "", clampf(next, 0.0, 100.0), state)
	return []


func _m13(state: SimState) -> Dictionary:
	var current: Dictionary = _as_dict(state.modules.get("M13", {}))
	state.modules["M13"] = current
	return current


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
