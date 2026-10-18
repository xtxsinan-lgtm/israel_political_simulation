class_name AutoPauseEvaluator
extends RefCounted


static func should_auto_pause(state: SimState) -> bool:
	if bool(state.run.get("headless", false)):
		return false
	if String(state.run.get("phase", "")) == "ENDED":
		return false
	var m12: Dictionary = _dict(state.modules.get("M12", {}))
	var pending: Variant = m12.get("pending_events", [])
	if typeof(pending) == TYPE_ARRAY and not (pending as Array).is_empty():
		return true
	var m03: Dictionary = _dict(state.modules.get("M03", {}))
	if bool(m03.get("vote_modal_open", false)):
		return true
	var votes: Variant = state.pending.get("vote_requests", [])
	if typeof(votes) == TYPE_ARRAY and not (votes as Array).is_empty():
		return true
	var alerts: Variant = state.history.get("active_alerts", [])
	if typeof(alerts) == TYPE_ARRAY:
		for i: int in range((alerts as Array).size()):
			var code: String = String((alerts as Array)[i])
			if code.ends_with("_red") or code == "coalition_minority":
				return true
	return false


static func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
