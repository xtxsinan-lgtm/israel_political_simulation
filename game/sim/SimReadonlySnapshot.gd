class_name SimReadonlySnapshot
extends RefCounted

var day_index: int = 0
var date: String = ""
var state_hash: String = ""
var key_params: Dictionary = {}
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
	return snap


func read_param(param_id: String) -> float:
	return float(key_params.get(param_id, 0.0))
