class_name SaveSystem
extends RefCounted

const FORMAT_VERSION: String = "1.0.0"
const INT_KEYS: Dictionary = {
	"day_index": true, "seed": true, "master_seed": true, "seq": true,
	"draws": true, "tenure_index": true, "custom_seed": true,
}


func compute_state_sha256(state: SimState) -> String:
	return CanonicalSerializer.compute_state_hash_sha256(state)


func build_envelope(state: SimState, command_log: Array) -> Dictionary:
	return {
		"save_format_version": FORMAT_VERSION,
		"game_version": "0.1.0",
		"scenario_id": "begin_1977",
		"day_index": state.clock.day_index,
		"current_date": state.clock.date,
		"state_sha256": compute_state_sha256(state),
		"state_payload": {"day_index": state.clock.day_index, "date": state.clock.date},
		"command_log": command_log,
		"file_suffix": "ipsave.json",
	}


func to_ipsave_json(envelope: Dictionary) -> String:
	return JSON.stringify(envelope)


func from_ipsave_json(text: String) -> Dictionary:
	var parsed: Variant = JSON.parse_string(text)
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return migrate_save_dict(restore_int_types_recursive(parsed))


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
	return migrated
