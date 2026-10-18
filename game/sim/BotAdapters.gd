class_name BotAdapters
extends RefCounted


class HistoricalBeginBot extends RefCounted:
	func choose_event_option(_state: SimState, event: Dictionary, options: Array) -> String:
		for i: int in range(options.size()):
			var opt: Dictionary = {}
			if typeof(options[i]) == TYPE_DICTIONARY:
				opt = options[i]
			if bool(opt.get("historical", false)):
				return String(opt.get("id", "A"))
		if options.is_empty():
			return String(event.get("ai_default_option", "A"))
		if typeof(options[0]) == TYPE_DICTIONARY:
			return String((options[0] as Dictionary).get("id", "A"))
		return "A"

	func on_week(_state: SimState) -> void:
		pass


class RandomBot extends RefCounted:
	var cursor: int = 0

	func choose_event_option(_state: SimState, _event: Dictionary, options: Array) -> String:
		if options.is_empty():
			return "A"
		var idx: int = cursor % options.size()
		cursor += 1
		if typeof(options[idx]) == TYPE_DICTIONARY:
			return String((options[idx] as Dictionary).get("id", "A"))
		return "A"

	func on_week(_state: SimState) -> void:
		pass


class GreedyBot extends RefCounted:
	func choose_event_option(state: SimState, _event: Dictionary, options: Array) -> String:
		var best: String = "A"
		var best_pc: float = -1.0e18
		for i: int in range(options.size()):
			if typeof(options[i]) != TYPE_DICTIONARY:
				continue
			var opt: Dictionary = options[i]
			var gain: float = _pc_delta(opt) + state.params.get_val("party_standing", "", state) * 0.0
			if gain > best_pc:
				best_pc = gain
				best = String(opt.get("id", "A"))
		return best

	func on_week(_state: SimState) -> void:
		pass

	func _pc_delta(opt: Dictionary) -> float:
		var effects: Variant = opt.get("effects", [])
		var total: float = 0.0
		if typeof(effects) != TYPE_ARRAY:
			return total
		for i: int in range((effects as Array).size()):
			if typeof((effects as Array)[i]) != TYPE_DICTIONARY:
				continue
			var row: Dictionary = (effects as Array)[i]
			if String(row.get("target", row.get("param", ""))) == "political_capital":
				total += float(row.get("value", 0.0))
		return total
