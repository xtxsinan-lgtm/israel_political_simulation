class_name ExprEngine
extends RefCounted

var _state: SimState = null


func bind(state: SimState) -> void:
	_state = state


func eval_bool(expr_or_ast: Variant, ctx: Dictionary = {}) -> bool:
	var v: Variant = eval_raw(expr_or_ast, ctx)
	if typeof(v) == TYPE_BOOL:
		return v
	if typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT:
		return float(v) != 0.0
	if typeof(v) == TYPE_STRING:
		return not String(v).is_empty()
	return false


func eval_float(expr_or_ast: Variant, ctx: Dictionary = {}) -> float:
	var v: Variant = eval_raw(expr_or_ast, ctx)
	if typeof(v) == TYPE_FLOAT or typeof(v) == TYPE_INT:
		var f: float = float(v)
		if is_nan(f) or is_inf(f):
			return 0.0
		return f
	if typeof(v) == TYPE_BOOL:
		return 1.0 if bool(v) else 0.0
	return 0.0


func eval_raw(expr_or_ast: Variant, ctx: Dictionary = {}) -> Variant:
	if expr_or_ast == null:
		return true
	if typeof(expr_or_ast) == TYPE_BOOL or typeof(expr_or_ast) == TYPE_FLOAT or typeof(expr_or_ast) == TYPE_INT:
		return expr_or_ast
	if typeof(expr_or_ast) == TYPE_STRING:
		var text: String = String(expr_or_ast)
		if text.is_empty():
			return true
		if ctx.has(text):
			return ctx[text]
		if GameData.current != null:
			var compiled: Array = GameData.current.get_compiled_ast(text)
			if not compiled.is_empty():
				return _eval_node(compiled, ctx)
		return 0.0
	if typeof(expr_or_ast) == TYPE_ARRAY:
		var ast: Array = expr_or_ast
		if ast.is_empty():
			return 0.0
		return _eval_node(ast, ctx)
	return 0.0


func _as_name(value: Variant) -> String:
	match typeof(value):
		TYPE_STRING, TYPE_STRING_NAME:
			return String(value)
		TYPE_INT:
			return str(value)
		TYPE_FLOAT:
			return str(int(value))
		TYPE_ARRAY:
			var nested: Array = value
			if nested.is_empty():
				return ""
			return _as_name(_eval_node(nested, {}))
		_:
			return ""


func _eval_node(node: Variant, ctx: Dictionary) -> Variant:
	if typeof(node) != TYPE_ARRAY:
		return node
	var arr: Array = node
	if arr.is_empty():
		return 0.0
	var op: String = String(arr[0])
	match op:
		"lit":
			return arr[1] if arr.size() > 1 else null
		"var":
			return _resolve_variable(String(arr[1]), ctx)
		"idx":
			var param_name: String = _as_name(arr[1] if arr.size() > 1 else "")
			var key_node: Variant = arr[2] if arr.size() > 2 else ""
			var key_val: String = ""
			if typeof(key_node) == TYPE_ARRAY and (key_node as Array).size() > 1 and String((key_node as Array)[0]) == "var":
				key_val = String((key_node as Array)[1])
			else:
				key_val = _as_name(_eval_node(key_node, ctx))
			if _state == null or param_name == "":
				return 0.0
			return _state.params.get_val(param_name, key_val, _state)
		"list":
			var items: Array = arr[1] if arr.size() > 1 and typeof(arr[1]) == TYPE_ARRAY else []
			var out: Array = []
			for i: int in range(items.size()):
				out.append(_eval_node(items[i], ctx))
			return out
		"and":
			for i: int in range(1, arr.size()):
				if not eval_bool(arr[i], ctx):
					return false
			return true
		"or":
			for i: int in range(1, arr.size()):
				if eval_bool(arr[i], ctx):
					return true
			return false
		"not":
			return not eval_bool(arr[1], ctx)
		"+":
			if arr.size() == 2:
				return eval_float(arr[1], ctx)
			return eval_float(arr[1], ctx) + eval_float(arr[2], ctx)
		"-":
			if arr.size() == 2:
				return -eval_float(arr[1], ctx)
			return eval_float(arr[1], ctx) - eval_float(arr[2], ctx)
		"*":
			return eval_float(arr[1], ctx) * eval_float(arr[2], ctx)
		"/":
			var denom: float = eval_float(arr[2], ctx)
			if absf(denom) < 1.0e-12:
				if _state != null:
					_state.record_error("E_DIV0", "Division by zero in expression")
				return 0.0
			return eval_float(arr[1], ctx) / denom
		"**":
			return SimMath.ipow(eval_float(arr[1], ctx), int(eval_float(arr[2], ctx)))
		"==":
			return _compare("==", _eval_node(arr[1], ctx), _eval_node(arr[2], ctx))
		"!=":
			return _compare("!=", _eval_node(arr[1], ctx), _eval_node(arr[2], ctx))
		"<", "<=", ">", ">=":
			return _compare(op, _eval_node(arr[1], ctx), _eval_node(arr[2], ctx))
		"in", "not_in":
			var item: Variant = _eval_node(arr[1], ctx)
			var list_v: Variant = _eval_node(arr[2], ctx)
			var found: bool = false
			if typeof(list_v) == TYPE_ARRAY:
				found = (list_v as Array).has(item)
			elif typeof(list_v) == TYPE_STRING:
				found = String(list_v).contains(String(item))
			return found if op == "in" else not found
		"call":
			var fn_name: String = String(arr[1])
			var raw_args: Array = arr[2] if arr.size() > 2 and typeof(arr[2]) == TYPE_ARRAY else []
			var evaled: Array = []
			for i: int in range(raw_args.size()):
				evaled.append(_eval_node(raw_args[i], ctx))
			return _dispatch_builtin(fn_name, evaled, ctx)
		_:
			return 0.0
	return 0.0


func _resolve_variable(name: String, ctx: Dictionary) -> Variant:
	if ctx.has(name):
		return ctx[name]
	if _state == null:
		return 0.0
	match name:
		"year":
			return _state.clock.y
		"month":
			return _state.clock.m
		"day":
			return _state.clock.d
		"leader_id":
			return String(_state.player.get("leader_id", ""))
		"party_id":
			return String(_state.player.get("party_id", ""))
		_:
			return _state.params.get_val(name, "", _state)


func _compare(op: String, left: Variant, right: Variant) -> bool:
	if typeof(left) == TYPE_STRING or typeof(right) == TYPE_STRING:
		var ls: String = String(left)
		var rs: String = String(right)
		match op:
			"==":
				return ls == rs
			"!=":
				return ls != rs
			"<":
				return ls < rs
			"<=":
				return ls <= rs
			">":
				return ls > rs
			">=":
				return ls >= rs
	var lf: float = float(left) if left != null else 0.0
	var rf: float = float(right) if right != null else 0.0
	match op:
		"==":
			return is_equal_approx(lf, rf) or String(left) == String(right)
		"!=":
			return not is_equal_approx(lf, rf) and String(left) != String(right)
		"<":
			return lf < rf
		"<=":
			return lf <= rf
		">":
			return lf > rf
		">=":
			return lf >= rf
	return false


func _dispatch_builtin(fn_name: String, args: Array, ctx: Dictionary) -> Variant:
	match fn_name:
		"min":
			return _math_min(args)
		"max":
			return _math_max(args)
		"clamp":
			if args.size() < 3:
				return _farg(args, 0)
			return clampf(_farg(args, 0), _farg(args, 1), _farg(args, 2))
		"floor":
			return floor(_farg(args, 0))
		"abs":
			return absf(_farg(args, 0))
		"flag":
			return _flag_on(_sarg(args, 0))
		"has_modifier":
			return _has_modifier(_sarg(args, 0), _sarg(args, 1))
		"event_done":
			return _event_day(_sarg(args, 0)) >= 0
		"event":
			return _event_day(_sarg(args, 0))
		"event_choice":
			return _event_choice(_sarg(args, 0))
		"months_since":
			return SimCalendar.months_since(_day_index(), _iarg(args, 0))
		"days_since":
			return SimCalendar.days_since(_day_index(), _iarg(args, 0))
		"scenario":
			return _state.meta.scenario_id if _state != null else ""
		"era":
			return SimCalendar.compute_era(_state.clock.y, _state.clock.m) if _state != null else 0
		"repeat_count":
			return _repeat_count(_sarg(args, 0))
		"slot":
			return String(ctx.get("slot", ""))
		"arg":
			return ctx.get(_sarg(args, 0), 0.0)
		"term_months":
			return SimMath.idiv_floor(maxi(0, _day_index() - int(_state.player.get("tenure_start_day", 0))), 30) if _state != null else 0
		"days_to_election":
			return int(_m03().get("days_to_election", 9999))
		"party_seats":
			return float(_seat_map().get(_sarg(args, 0), 0.0))
		"party_in_coalition":
			return _coalition().has(_sarg(args, 0))
		"party_has_tag":
			return _party_has_tag(_sarg(args, 0), _sarg(args, 1))
		"party_stage":
			return int(_m04().get("party_stage", 0))
		"promise_active":
			return float(_scoped("promise_progress").get(_sarg(args, 0), -1.0)) >= 0.0
		"vision_milestone_done":
			return _milestone_done(_sarg(args, 0))
		"corridor_lo":
			return _corridor(_sarg(args, 0)).x
		"corridor_hi":
			return _corridor(_sarg(args, 0)).y
		"m05_iou_total":
			return float(_m05().get("iou_incurred_total", 0))
		"action_running":
			return _action_running(_sarg(args, 0))
		"action_done_count":
			return int(_as_dict(_m05().get("completed_actions", {})).get(_sarg(args, 0), 0))
		"character_in_office":
			return _character_in_office(_sarg(args, 0))
		"character_alive":
			return _char_alive(_sarg(args, 0))
		"holder_of":
			return _holder_of(_sarg(args, 0))
		"ambition":
			return float(_as_dict(_characters().get(_sarg(args, 0), {})).get("ambition", 0.0))
		"peace_treaty":
			return _treaty_tier(_sarg(args, 0)) >= 2
		"treaty_tier":
			return _treaty_tier(_sarg(args, 0))
		"secret_channel":
			return bool(_as_dict(_countries().get(_sarg(args, 0), {})).get("secret_channel_open", false))
		"nuclear_progress":
			return float(_as_dict(_countries().get(_sarg(args, 0), {})).get("nuclear_progress", 0.0))
		"at_war":
			return _at_war(_sarg(args, 0))
		"last_ceasefire_date":
			return String(_m09().get("last_ceasefire_date", ""))
		"front_phase":
			return String(_as_dict(_as_dict(_m09().get("fronts", {})).get(_sarg(args, 0), {})).get("status", "PEACE"))
		"casualties_total":
			return _casualties(_sarg(args, 0))
		"region_exists", "legal_status", "region_legal_status":
			return _region_query(fn_name, _sarg(args, 0))
		"site_status":
			return String(_as_dict(_m11().get("key_sites", {})).get(_sarg(args, 0), ""))
		"settler_pop":
			return _state.params.get_val("settler_population", GameData.current.resolve_region_id(_sarg(args, 0)), _state) if _state != null and GameData.current != null else 0.0
		"active_plan":
			return String(_m11().get("active_overlay", ""))
		"region_pop_group_total":
			return 0.0
		"m13_stage":
			return int(_m13().get("stage", 0))
		"m13_actor_posture":
			return String(_as_dict(_as_dict(_m13().get("resist_actors", {})).get(_sarg(args, 0), {})).get("stance", "dormant"))
		"m13_protest_tier":
			return int(_m13().get("protest_tier", 0))
		"m13_in_survival_mode":
			return bool(_m13().get("survival_mode_active", false))
		"tenure_months":
			return SimMath.idiv_floor(maxi(0, _day_index() - int(_state.run.get("tenure_start_day", 0))), 30) if _state != null else 0
		"tenure_index":
			return int(_state.player.get("tenure_index", 0)) if _state != null else 0
		"count_peace_treaties":
			return _count_treaties()
		"settler_population_total":
			return _sum_scoped("settler_population")
		"casualties_total_all_fronts":
			return _casualties("")
		"front_quagmire_months":
			return int(_as_dict(_as_dict(_m09().get("fronts", {})).get(_sarg(args, 0), {})).get("quagmire_months", 0))
		_:
			if _state != null:
				_state.record_error("E_UNKNOWN_FUNC", fn_name)
			return 0.0
	return 0.0


func _math_min(args: Array) -> float:
	if args.is_empty():
		return 0.0
	var best: float = _farg(args, 0)
	for i: int in range(1, args.size()):
		best = minf(best, float(args[i]))
	return best


func _math_max(args: Array) -> float:
	if args.is_empty():
		return 0.0
	var best: float = _farg(args, 0)
	for i: int in range(1, args.size()):
		best = maxf(best, float(args[i]))
	return best


func _farg(args: Array, idx: int) -> float:
	if idx >= args.size() or args[idx] == null:
		return 0.0
	return float(args[idx])


func _sarg(args: Array, idx: int) -> String:
	if idx >= args.size() or args[idx] == null:
		return ""
	return String(args[idx])


func _iarg(args: Array, idx: int) -> int:
	return int(_farg(args, idx))


func _day_index() -> int:
	return _state.clock.day_index if _state != null else 0


func _flag_on(flag_id: String) -> bool:
	if _state == null:
		return false
	if _state.flags.has(flag_id):
		var entry: Dictionary = _as_dict(_state.flags[flag_id])
		return float(entry.get("value", 1.0)) != 0.0
	if flag_id == "likud_in_government" and _state.flags.has("likud_in_power"):
		return true
	if flag_id == "likud_in_power" and _state.flags.has("likud_in_government"):
		return true
	if flag_id == "bank_shares_manipulation" and _state.flags.has("bank_shares_regulation"):
		return true
	if flag_id == "liberals_hold_finance":
		var finance_holder: String = _holder_of("finance")
		return finance_holder == "ehrlich" or finance_holder == "modai" or finance_holder == "patt"
	if flag_id == "dayan_foreign_minister":
		var choice_a: bool = _event_choice("E-1977-06") == "A"
		return choice_a or (_state.clock.day_index >= 30 and _holder_of("foreign") == "dayan")
	if flag_id == "settlers_momentum_high":
		return _state.params.get_val("settler_momentum", "", _state) >= 50.0
	if flag_id == "lakam_us_operation":
		return bool(_as_dict(_as_dict(_m09()).get("nuclear", {})).get("lakam_active", true))
	if flag_id == "first_intifada_active":
		return _state.flags.has("intifada_active") or _has_modifier("first_intifada", "") or bool(_as_dict(_as_dict(_m08()).get("uprising_state", {})).get("active", false))
	if flag_id == "world_iran_iraq_war":
		return _state.clock.date >= "1980-09-22" and _state.clock.date <= "1988-08-20"
	if flag_id == "world_us_refugee_quota_tightened":
		return _state.clock.date >= "1989-06-01"
	if flag_id == "world_gulf_war":
		return _state.clock.date >= "1990-08-02" and _state.clock.date <= "1991-04-30"
	if flag_id == "national_unity_government":
		var seats: float = _state.params.get_val("coalition_seats", "", _state)
		var parties_v: Variant = _as_dict(_as_dict(_state.modules.get("M03", {})).get("parliament", {})).get("coalition_parties", [])
		var labor_in: bool = false
		if typeof(parties_v) == TYPE_ARRAY:
			var parties: Array = parties_v
			for i: int in range(parties.size()):
				if String(parties[i]) == "labor":
					labor_in = true
		return _state.clock.y >= 1984 and (seats >= 75.0 or labor_in)
	return false


func _has_modifier(mod_id: String, scope_key: String) -> bool:
	if _state == null:
		return false
	for i: int in range(_state.active_modifiers.size()):
		var mod: Dictionary = _state.active_modifiers[i]
		if String(mod.get("def_id", "")) == mod_id and (scope_key == "" or String(mod.get("scope_key", "")) == scope_key):
			return true
	return false


func _event_day(event_id: String) -> int:
	if _state == null:
		return -1
	var last: Dictionary = _as_dict(_state.history.get("event_last_day", {}))
	return int(last.get(event_id, -1))


func _event_choice(event_id: String) -> String:
	var log_v: Variant = _state.history.get("event_log", []) if _state != null else []
	if typeof(log_v) != TYPE_ARRAY:
		return ""
	var log: Array = log_v
	for i: int in range(log.size() - 1, -1, -1):
		var row: Dictionary = _as_dict(log[i])
		if String(row.get("event_id", "")) == event_id:
			return String(row.get("choice", ""))
	return ""


func _repeat_count(event_id: String) -> int:
	return int(_as_dict(_m12().get("counts_game", {})).get(event_id, 0))


func _m02() -> Dictionary:
	return _mod("M02")


func _m03() -> Dictionary:
	return _mod("M03")


func _m04() -> Dictionary:
	return _mod("M04")


func _milestone_done(milestone_id: String) -> bool:
	var milestones: Dictionary = _as_dict(_m04().get("milestones", {}))
	return milestones.get(milestone_id, false) == true


func _m05() -> Dictionary:
	return _mod("M05")


func _m06() -> Dictionary:
	return _mod("M06")


func _m07() -> Dictionary:
	return _mod("M07")


func _m08() -> Dictionary:
	return _mod("M08")


func _m09() -> Dictionary:
	return _mod("M09")


func _m11() -> Dictionary:
	return _mod("M11")


func _m12() -> Dictionary:
	return _mod("M12")


func _m13() -> Dictionary:
	return _mod("M13")


func _mod(module_id: String) -> Dictionary:
	if _state == null:
		return {}
	return _as_dict(_state.modules.get(module_id, {}))


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}


func _scoped(param_id: String) -> Dictionary:
	if _state == null:
		return {}
	return _as_dict(_state.params.export_scoped().get(param_id, {}))


func _seat_map() -> Dictionary:
	return _as_dict(_m03().get("knesset_seats", {}))


func _coalition() -> Dictionary:
	var parties: Variant = _m03().get("coalition_parties", [])
	var out: Dictionary = {}
	if typeof(parties) == TYPE_ARRAY:
		var arr: Array = parties
		for i: int in range(arr.size()):
			out[String(arr[i])] = true
	return out


func _party_has_tag(party_id: String, tag: String) -> bool:
	var tags: Variant = _as_dict(_m03().get("party_tags", {})).get(party_id, [])
	if typeof(tags) != TYPE_ARRAY:
		return false
	return (tags as Array).has(tag)


func _corridor(axis: String) -> Vector2:
	var bounds: Dictionary = _as_dict(_m04().get("corridors", {}))
	var row: Dictionary = _as_dict(bounds.get(axis, {}))
	return Vector2(float(row.get("lo", -100.0)), float(row.get("hi", 100.0)))


func _action_running(action_id: String) -> bool:
	var running: Variant = _m05().get("active_actions", [])
	if typeof(running) != TYPE_ARRAY:
		return false
	var arr: Array = running
	for i: int in range(arr.size()):
		if String(_as_dict(arr[i]).get("id", "")) == action_id:
			return true
	return false


func _characters() -> Dictionary:
	return _as_dict(_m06().get("characters", {}))


func _offices() -> Dictionary:
	return _as_dict(_m06().get("offices", {}))


func _holder_of(office_or_char: String) -> String:
	var offices: Dictionary = _offices()
	if offices.has(office_or_char):
		return String(offices[office_or_char])
	if GameData.current != null:
		var canon: String = GameData.current.resolve_office_id(office_or_char)
		if offices.has(canon):
			return String(offices[canon])
	return ""


func _character_in_office(char_id: String) -> bool:
	var date: String = "" if _state == null else _state.clock.date
	var fired: Dictionary = {}
	if _state != null:
		fired = _as_dict(_as_dict(_state.modules.get("M12", {})).get("fired", {}))
	if char_id == "sadat":
		return date <= "1981-10-06" and not _flag_on("sadat_assassinated") and not fired.has("E-1981-10")
	if char_id == "mubarak":
		return date > "1981-10-06" or _flag_on("sadat_assassinated") or fired.has("E-1981-10")
	if char_id == "hussein_king" or char_id == "hussein" or char_id == "assad_hafez" or char_id == "arafat" or char_id == "saddam":
		return true
	if char_id == "mengistu":
		return date <= "1991-05-28"
	if char_id == "shah_pahlavi":
		return date <= "1979-03-01" and not fired.has("E-1979-02")
	if char_id == "bashir_gemayel":
		return date >= "1982-01-01" and date <= "1983-12-31" and not fired.has("E-1982-09a")
	if char_id == "numayri":
		return date <= "1985-06-30"
	if char_id == "carter" or char_id == "reagan" or char_id == "bush_sr" or char_id == "clinton":
		var president: String = String(_as_dict(_as_dict(_m07()).get("us_politics", {})).get("president_id", ""))
		return president == char_id
	if _holder_of(char_id) != "":
		return true
	if _state != null and String(_state.player.get("leader_id", "")) == char_id:
		return true
	return _char_holds(char_id)


func _char_holds(char_id: String) -> bool:
	var offices: Dictionary = _offices()
	var keys: Array[String] = SimMath.sorted_keys(offices)
	for i: int in range(keys.size()):
		if String(offices[keys[i]]) == char_id:
			return true
	return false


func _char_alive(char_id: String) -> bool:
	var row: Dictionary = _as_dict(_characters().get(char_id, {}))
	if row.is_empty():
		return false
	if row.has("alive"):
		return bool(row["alive"])
	return bool(row.get("alive_1977", true))


func _countries() -> Dictionary:
	return _as_dict(_m07().get("countries", {}))


func _treaty_tier(country_id: String) -> int:
	return int(_as_dict(_countries().get(country_id, {})).get("peace_treaty_state", 0))


func _at_war(front_id: String) -> bool:
	var fronts: Dictionary = _as_dict(_m09().get("fronts", {}))
	if front_id == "":
		var keys: Array[String] = SimMath.sorted_keys(fronts)
		for i: int in range(keys.size()):
			if String(_as_dict(fronts[keys[i]]).get("status", "")) == "WAR":
				return true
		return false
	return String(_as_dict(fronts.get(front_id, {})).get("status", "")) == "WAR"


func _casualties(front_id: String) -> float:
	var fronts: Dictionary = _as_dict(_m09().get("fronts", {}))
	if front_id != "":
		return float(_as_dict(fronts.get(front_id, {})).get("casualties", 0.0))
	var total: float = 0.0
	var keys: Array[String] = SimMath.sorted_keys(fronts)
	for i: int in range(keys.size()):
		total += float(_as_dict(fronts[keys[i]]).get("casualties", 0.0))
	return total


func _region_query(fn_name: String, region_id: String) -> Variant:
	var canon: String = region_id
	if GameData.current != null:
		canon = GameData.current.resolve_region_id(region_id)
	var regions: Dictionary = _as_dict(_m11().get("regions", {}))
	var row: Dictionary = _as_dict(regions.get(canon, {}))
	if fn_name == "region_exists":
		return bool(row.get("exists", false)) if not row.is_empty() else false
	return String(row.get("legal_status", ""))


func _count_treaties() -> int:
	var countries: Dictionary = _countries()
	var keys: Array[String] = SimMath.sorted_keys(countries)
	var n: int = 0
	for i: int in range(keys.size()):
		if int(_as_dict(countries[keys[i]]).get("peace_treaty_state", 0)) >= 2:
			n += 1
	return n


func _sum_scoped(param_id: String) -> float:
	var table: Dictionary = _scoped(param_id)
	var keys: Array[String] = SimMath.sorted_keys(table)
	var total: float = 0.0
	for i: int in range(keys.size()):
		total += float(table[keys[i]])
	return total
