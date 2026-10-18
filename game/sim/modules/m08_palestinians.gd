extends RefCounted
# Isolation: extends RefCounted. Filename alias used by the cross-module reason gate.

func build_ai_reason_breakdown(actor_id: String, param_id: String, current_val: float, threshold_val: float) -> Dictionary:
	var module: M08Palestine = M08Palestine.new()
	return module.build_ai_reason_breakdown(actor_id, param_id, current_val, threshold_val)
