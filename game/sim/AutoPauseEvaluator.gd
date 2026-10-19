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
	if typeof(votes) == TYPE_ARRAY:
		var vote_rows: Array = votes
		for v_i: int in range(vote_rows.size()):
			var due_day: int = int(_dict(vote_rows[v_i]).get("due_day", state.clock.day_index))
			if due_day <= state.clock.day_index:
				return true
	var alerts: Variant = state.history.get("active_alerts", [])
	var red_now: Array[String] = []
	if typeof(alerts) == TYPE_ARRAY:
		for i: int in range((alerts as Array).size()):
			var code: String = str((alerts as Array)[i])
			if code.ends_with("_red") or code == "coalition_minority":
				red_now.append(code)
	var seen_v: Variant = state.run.get("auto_pause_seen_alerts", [])
	var seen: Array = seen_v if typeof(seen_v) == TYPE_ARRAY else []
	state.run["auto_pause_seen_alerts"] = red_now
	for i: int in range(red_now.size()):
		if not seen.has(red_now[i]):
			return true
	return false


static func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
