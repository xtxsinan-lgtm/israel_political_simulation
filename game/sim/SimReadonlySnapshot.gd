class_name SimReadonlySnapshot
extends RefCounted

## Fog-of-war bands (D-088): a `visible: fuzzy` value in [0, 100] is only ever
## exposed to the UI as one of FUZZY_BAND_COUNT coarse bands of FUZZY_BAND_WIDTH.
const FUZZY_BAND_COUNT: int = 5
const FUZZY_BAND_WIDTH: float = 20.0

var day_index: int = 0
var date: String = ""
var state_hash: String = ""
var key_params: Dictionary = {}
## param_id -> int band index (0..4) for national `visible: fuzzy` params. Never raw floats.
var fuzzy_bands: Dictionary = {}
var pending_events: Array[Dictionary] = []
var ended: bool = false
var _sealed: bool = true


static func capture(state: SimState) -> SimReadonlySnapshot:
	var snap: SimReadonlySnapshot = SimReadonlySnapshot.new()
	snap.day_index = state.clock.day_index
	snap.date = state.clock.date
	snap.state_hash = CanonicalSerializer.compute_state_hash_sha256(state)
	snap.key_params = {
		"public_security": state.params.get_val("public_security", "", state),
		"inflation": state.params.get_val("inflation", "", state),
		"political_capital": state.params.get_val("political_capital", "", state),
		"coalition_seats": state.params.get_val("coalition_seats", "", state),
		"party_standing": state.params.get_val("party_standing", "", state),
		"budget_balance": state.params.get_val("budget_balance", "", state),
	}
	snap.fuzzy_bands = {}
	if GameData.current != null:
		var ids: Array[String] = SimMath.sorted_keys(GameData.current.parameters_def)
		for i: int in range(ids.size()):
			var pdef: Variant = GameData.current.parameters_def[ids[i]]
			if typeof(pdef) != TYPE_DICTIONARY:
				continue
			var row: Dictionary = pdef
			if String(row.get("visible", "")) != "fuzzy" or String(row.get("scope", "national")) != "national":
				continue
			snap.fuzzy_bands[ids[i]] = band_of(state.params.get_val(ids[i], "", state))
	snap.pending_events = []
	var m12_v: Variant = state.modules.get("M12", {})
	if typeof(m12_v) == TYPE_DICTIONARY:
		var pending_v: Variant = (m12_v as Dictionary).get("pending_events", [])
		if typeof(pending_v) == TYPE_ARRAY:
			var pending: Array = pending_v
			for p_i: int in range(pending.size()):
				if typeof(pending[p_i]) == TYPE_DICTIONARY:
					snap.pending_events.append((pending[p_i] as Dictionary).duplicate(true))
	snap.ended = String(state.run.get("phase", "")) == "ENDED"
	return snap


func read_param(param_id: String) -> float:
	return float(key_params.get(param_id, 0.0))


## Band index (0..4) of a fuzzy national param, or -1 if it is not captured.
func read_band(param_id: String) -> int:
	if not fuzzy_bands.has(param_id):
		return -1
	return int(fuzzy_bands[param_id])


## Maps a 0..100 value to its fog-of-war band index 0..FUZZY_BAND_COUNT-1.
static func band_of(value: float) -> int:
	var v: float = clampf(value, 0.0, 100.0)
	var band: int = 0
	while band < FUZZY_BAND_COUNT - 1 and v >= float(band + 1) * FUZZY_BAND_WIDTH:
		band += 1
	return band


## True when the parameter registry marks the param `visible: fuzzy`.
static func is_fuzzy_param(param_id: String) -> bool:
	if GameData.current == null:
		return false
	var resolved: String = param_id
	if not GameData.current.param_aliases.is_empty():
		resolved = GameData.current.resolve_param_alias(param_id)
	var pdef: Variant = GameData.current.parameters_def.get(resolved, {})
	if typeof(pdef) != TYPE_DICTIONARY:
		return false
	return String((pdef as Dictionary).get("visible", "")) == "fuzzy"
