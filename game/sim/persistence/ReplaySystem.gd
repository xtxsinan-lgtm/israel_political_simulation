class_name ReplaySystem
extends RefCounted


func run_headless_replay(replay_data: Dictionary) -> Dictionary:
	var director: SimDirector = SimDirector.new()
	return replay_into(director, replay_data)


## Replays a command log into `director` from the scenario start up to `target_day`.
## Commands are applied on the day they were logged, in `seq` order, including
## commands logged on the target day itself (submitted after the last step).
func replay_into(director: SimDirector, replay_data: Dictionary) -> Dictionary:
	var scenario_id: String = String(replay_data.get("scenario_id", "begin_1977"))
	var seed: int = SimMath.round_half_up_int(float(replay_data.get("seed", SimDirector.DEFAULT_SEED)))
	if director.start_new_game(scenario_id, seed, bool(replay_data.get("ironman", false))) != OK:
		return {"ok": false}
	var was_recording: bool = director.recording
	director.recording = true
	# Replays must run in the same mode as the original game: headless games auto-resolve
	# events, interactive games resolve them through logged `resolve_event` commands.
	var headless: bool = bool(replay_data.get("headless", true))
	director.state.run["headless"] = headless
	var command_log: Array[Dictionary] = _sorted_log(replay_data.get("command_log", []))
	var target: int = SimMath.round_half_up_int(float(replay_data.get("target_day", 0)))
	var cursor: int = 0
	var rejected: int = 0
	while true:
		while cursor < command_log.size():
			var row: Dictionary = command_log[cursor]
			var row_day: int = SimMath.round_half_up_int(float(row.get("day_index", -1)))
			if row_day > director.state.clock.day_index:
				break
			var payload: Dictionary = {}
			if typeof(row.get("payload", {})) == TYPE_DICTIONARY:
				payload = row["payload"]
			if row_day < director.state.clock.day_index or director.submit_command(payload) != OK:
				rejected += 1
			cursor += 1
		if director.state.clock.day_index >= target:
			break
		var stepped: Dictionary = director.step_one_day()
		if bool(stepped.get("ended", false)) and director.state.clock.day_index < target:
			break
	director.recording = was_recording
	return {
		"ok": rejected == 0 and director.state.clock.day_index == target,
		"rejected": rejected,
		"day_index": director.state.clock.day_index,
		"state_sha256": CanonicalSerializer.compute_state_hash_sha256(director.state),
		"command_log": director.command_log,
	}


func _sorted_log(raw: Variant) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	if typeof(raw) != TYPE_ARRAY:
		return rows
	var source: Array = raw
	for i: int in range(source.size()):
		if typeof(source[i]) == TYPE_DICTIONARY:
			rows.append(source[i])
	rows.sort_custom(_row_before)
	return rows


func _row_before(a: Dictionary, b: Dictionary) -> bool:
	var ad: int = SimMath.round_half_up_int(float(a.get("day_index", 0)))
	var bd: int = SimMath.round_half_up_int(float(b.get("day_index", 0)))
	if ad != bd:
		return ad < bd
	return SimMath.round_half_up_int(float(a.get("seq", 0))) < SimMath.round_half_up_int(float(b.get("seq", 0)))
