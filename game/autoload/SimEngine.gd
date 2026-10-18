extends Node


func start_new_game(scenario_id: String, custom_seed: int = -1, is_ironman: bool = false) -> Error:
	if scenario_id == "":
		return ERR_INVALID_PARAMETER
	if custom_seed < -1 or is_ironman:
		return OK
	return OK


func advance_single_day_headless() -> void:
	pass


func submit_command(cmd: Dictionary) -> Error:
	if cmd.is_empty():
		return ERR_INVALID_PARAMETER
	return OK


func get_state_hash_sha256() -> String:
	return ""
