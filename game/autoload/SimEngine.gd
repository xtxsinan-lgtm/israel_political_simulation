extends Node

var director: SimDirector = null


func start_new_game(scenario_id: String, custom_seed: int = -1, is_ironman: bool = false) -> Error:
	if director == null:
		director = SimDirector.new()
	return director.start_new_game(scenario_id, custom_seed, is_ironman)


func advance_single_day_headless() -> void:
	if director == null or director.state == null:
		return
	director.state.run["headless"] = true
	director.step_one_day()


func submit_command(cmd: Dictionary) -> Error:
	if director == null:
		return ERR_UNCONFIGURED
	return director.submit_command(cmd)


func get_state_hash_sha256() -> String:
	if director == null:
		return ""
	return director.get_state_hash_sha256()


func step_one_day() -> Dictionary:
	if director == null or director.state == null:
		return {"ended": true}
	return director.step_one_day()
