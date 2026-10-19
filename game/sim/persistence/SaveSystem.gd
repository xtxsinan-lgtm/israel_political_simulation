class_name SaveSystem
extends RefCounted

## Saves are "seed + command log" envelopes: loading replays the log deterministically
## from the scenario start and verifies the recorded state hash. This avoids depending
## on a full state serializer (SimState.to_raw_state_dict does not cover every field).

const FORMAT_VERSION: String = "1.1.0"
const INT_KEYS: Dictionary = {
	"day_index": true, "seed": true, "master_seed": true, "seq": true,
	"draws": true, "tenure_index": true, "custom_seed": true, "target_day": true,
	"level": true, "days": true,
}


func compute_state_sha256(state: SimState) -> String:
	return CanonicalSerializer.compute_state_hash_sha256(state)


func build_envelope(state: SimState, command_log: Array) -> Dictionary:
	return {
		"save_format_version": FORMAT_VERSION,
		"game_version": "0.1.0",
		"scenario_id": state.meta.scenario_id,
		"master_seed": state.meta.master_seed,
		"ironman": state.meta.ironman,
		"headless": bool(state.run.get("headless", false)),
		"ruleset_hash": state.meta.ruleset_hash,
		"day_index": state.clock.day_index,
		"current_date": state.clock.date,
		"state_sha256": compute_state_sha256(state),
		"state_payload": {"day_index": state.clock.day_index, "date": state.clock.date},
		"command_log": command_log.duplicate(true),
		"file_suffix": "ipsave.json",
	}


func to_ipsave_json(envelope: Dictionary) -> String:
	return JSON.stringify(envelope)


func from_ipsave_json(text: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return migrate_save_dict(restore_int_types_recursive(parsed))


## Rebuilds a live game from an envelope. Returns OK only if the replayed state
## hash equals the hash stored in the save.
func load_into(director: SimDirector, envelope: Dictionary) -> Error:
	if envelope.is_empty():
		return ERR_INVALID_DATA
	var replay: Dictionary = ReplaySystem.new().replay_into(director, {
		"scenario_id": String(envelope.get("scenario_id", "begin_1977")),
		"seed": int(envelope.get("master_seed", envelope.get("seed", SimDirector.DEFAULT_SEED))),
		"ironman": bool(envelope.get("ironman", false)),
		"headless": bool(envelope.get("headless", false)),
		"target_day": int(envelope.get("day_index", 0)),
		"command_log": envelope.get("command_log", []),
	})
	if not bool(replay.get("ok", false)):
		return ERR_INVALID_DATA
	var expected: String = String(envelope.get("state_sha256", ""))
	if expected != "" and String(replay.get("state_sha256", "")) != expected:
		return ERR_FILE_CORRUPT
	return OK


func restore_int_types_recursive(value: Variant) -> Variant:
	if typeof(value) == TYPE_DICTIONARY:
		var restored: Dictionary = {}
		var source: Dictionary = value
		var keys: Array[String] = SimMath.sorted_keys(source)
		for i: int in range(keys.size()):
			var child: Variant = restore_int_types_recursive(source[keys[i]])
			if INT_KEYS.has(keys[i]) and (typeof(child) == TYPE_FLOAT or typeof(child) == TYPE_INT):
				restored[keys[i]] = SimMath.round_half_up_int(float(child))
			else:
				restored[keys[i]] = child
		return restored
	if typeof(value) == TYPE_ARRAY:
		var rows: Array = value
		var out: Array = []
		for i: int in range(rows.size()):
			out.append(restore_int_types_recursive(rows[i]))
		return out
	return value


func migrate_save_dict(raw_dict: Dictionary) -> Dictionary:
	var migrated: Dictionary = raw_dict.duplicate(true)
	if not migrated.has("save_format_version"):
		migrated["save_format_version"] = FORMAT_VERSION
	if not migrated.has("master_seed") and migrated.has("seed"):
		migrated["master_seed"] = migrated["seed"]
	if not migrated.has("master_seed"):
		migrated["master_seed"] = SimDirector.DEFAULT_SEED
	return migrated
