class_name ReplaySystem
extends RefCounted


func run_headless_replay(replay_data: Dictionary) -> Dictionary:
	var director: SimDirector = SimDirector.new()
	var scenario_id: String = String(replay_data.get("scenario_id", "begin_1977"))
	var seed: int = SimMath.round_half_up_int(float(replay_data.get("seed", 19770620)))
	if director.start_new_game(scenario_id, seed, false) != OK:
		return {"ok": false}
	director.recording = false
	director.state.run["headless"] = true
	var command_log: Array = []
	var raw_log: Variant = replay_data.get("command_log", [])
	if typeof(raw_log) == TYPE_ARRAY:
		command_log = raw_log
	var target: int = SimMath.round_half_up_int(float(replay_data.get("target_day", 0)))
	var cursor: int = 0
	while director.state.clock.day_index < target:
		while cursor < command_log.size():
			var row: Dictionary = {}
			if typeof(command_log[cursor]) == TYPE_DICTIONARY:
				row = command_log[cursor]
			if SimMath.round_half_up_int(float(row.get("day_index", -1))) != director.state.clock.day_index:
				break
			var payload: Dictionary = {}
			if typeof(row.get("payload", {})) == TYPE_DICTIONARY:
				payload = row["payload"]
			director.submit_command(payload)
			cursor += 1
		director.step_one_day()
	return {
		"ok": true,
		"day_index": director.state.clock.day_index,
		"state_sha256": CanonicalSerializer.compute_state_hash_sha256(director.state),
		"command_log": command_log,
	}
