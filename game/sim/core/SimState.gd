class_name SimState
extends RefCounted

class SimMeta extends RefCounted:
	var save_version: int = 1
	var game_version: String = "0.1.0"
	var scenario_id: String = "begin_1977"
	var master_seed: int = 19770620
	var ruleset_hash: String = ""
	var ironman: bool = false
	var modified: bool = false
	var created_real_time: String = ""
	var completed: bool = false

	func to_dict() -> Dictionary:
		return {
			"save_version": save_version,
			"game_version": game_version,
			"scenario_id": scenario_id,
			"master_seed": master_seed,
			"ruleset_hash": ruleset_hash,
			"ironman": ironman,
			"modified": modified,
			"created_real_time": created_real_time,
			"completed": completed,
		}


class SimClock extends RefCounted:
	var start_date: String = "1977-06-20"
	var date: String = "1977-06-20"
	var day_index: int = 0
	var abs_day: int = 2727
	var y: int = 1977
	var m: int = 6
	var d: int = 20
	var weekday: int = 0
	var is_week: bool = false
	var is_month: bool = false
	var is_quarter: bool = false
	var is_year: bool = false

	func to_dict() -> Dictionary:
		return {
			"start_date": start_date,
			"date": date,
			"day_index": day_index,
			"abs_day": abs_day,
			"y": y,
			"m": m,
			"d": d,
			"weekday": weekday,
			"is_week": is_week,
			"is_month": is_month,
			"is_quarter": is_quarter,
			"is_year": is_year,
		}


class SimCounters extends RefCounted:
	var next_modifier_uid: int = 1
	var next_popup_uid: int = 1
	var next_delayed_seq: int = 0
	var next_input_seq: int = 0
	var forced_popups_month: int = 0

	func to_dict() -> Dictionary:
		return {
			"next_modifier_uid": next_modifier_uid,
			"next_popup_uid": next_popup_uid,
			"next_delayed_seq": next_delayed_seq,
			"next_input_seq": next_input_seq,
			"forced_popups_month": forced_popups_month,
		}


var meta: SimMeta = SimMeta.new()
var clock: SimClock = SimClock.new()
var run: Dictionary = {"phase": "PAUSED", "speed": 2, "paused": true, "pause_reasons": ["AP00"], "headless": false}
var params: ParameterStore = ParameterStore.new()
var modifiers: ModifierEngine = ModifierEngine.new()
var param_status: Dictionary = {}
var flags: Dictionary = {}
var active_modifiers: Array[Dictionary] = []
var delayed_effects: Array[Dictionary] = []
var scheduled_events: Array[Dictionary] = []
var forced_events: PackedStringArray = PackedStringArray()
var ui_queue: Array[Dictionary] = []
var rng: SimRNG = SimRNG.new()
var player: Dictionary = {"leader_id": "begin", "party_id": "likud", "tenure_index": 0, "tenure_start_day": 0, "fictional": false}
var tenures: Array[Dictionary] = []
var history: Dictionary = {
	"series_ids": [],
	"series": {},
	"series_start_day": -1,
	"event_log": [],
	"event_last_day": {},
	"turning_points": [],
}
var contrib: Dictionary = {"month_key": "1977-06", "current": {}, "previous": {}}
var one_off_flows: Dictionary = {"budget_balance": 0.0}
var modules: Dictionary = {}
var counters: SimCounters = SimCounters.new()
var pending: Dictionary = {"tenure_end": {}, "vote_requests": [], "signals": []}
var input_log: Array[Dictionary] = []
var monthly_snapshots: Array[Dictionary] = []
var stats: Dictionary = {}
var errors: Array[Dictionary] = []
var policies: Dictionary = {}
var promises: Array = []
var offices: Dictionary = {}
var parliament: Dictionary = {}
var gov_axis_position: Dictionary = {}
var axis_impulse: Dictionary = {}


func _init() -> void:
	modifiers.active = active_modifiers


func init_from_scenario_bundle(scenario_id: String, master_seed: int, is_ironman: bool) -> void:
	var bundle: Dictionary = GameData.current.get_scenario_bundle(scenario_id)
	var scenario: Dictionary = _as_dict(bundle.get("scenario", {}))
	var snapshot: Dictionary = _as_dict(bundle.get("snapshot", {}))
	meta.scenario_id = scenario_id
	meta.master_seed = master_seed
	meta.ruleset_hash = GameData.current.ruleset_hash
	meta.ironman = is_ironman
	meta.save_version = SimTypes.CURRENT_SAVE_VERSION
	meta.modified = false
	meta.completed = false
	var start_date: String = String(scenario.get("start_date", snapshot.get("start_date", "1977-06-20")))
	_set_clock(start_date, 0)
	rng.init_python_from_master_seed(master_seed)
	player = {
		"leader_id": String(scenario.get("leader_id", "begin")),
		"party_id": String(scenario.get("party_id", "likud")),
		"tenure_index": 0,
		"tenure_start_day": 0,
		"fictional": false,
		"role": "pm",
	}
	run = {
		"phase": "RUNNING",
		"speed": 1,
		"paused": false,
		"pause_reasons": [],
		"headless": false,
		"tenure_index": 0,
		"tenure_start_day": 0,
		"tenure_start_date": start_date,
		"government_start_date": start_date,
	}
	_load_default_params()
	_overlay_snapshot_params(_as_dict(snapshot.get("params", {})))
	_init_policies()
	_ensure_hash_params()
	_load_flags(snapshot.get("initial_flags", {}))
	_load_modifiers(snapshot.get("initial_modifiers", []))
	promises = _as_array(snapshot.get("promises", [])).duplicate(true)
	_init_modules(snapshot)
	_activate_era_params()
	_align_python_init_params()
	M05Actions.new().recompute_gov_axis_positions(self)


func push_delayed_effect_heap(item: Dictionary) -> void:
	SimContainers.heap_push(delayed_effects, item)


func push_scheduled_event_heap(item: Dictionary) -> void:
	SimContainers.heap_push(scheduled_events, item)


func process_pending_signals() -> void:
	var signals_v: Variant = pending.get("signals", [])
	if typeof(signals_v) != TYPE_ARRAY:
		return
	var pending_signals: Array = signals_v
	while not pending_signals.is_empty():
		var sig: Variant = pending_signals.pop_front()
		var name: String = String(sig)
		if typeof(sig) == TYPE_DICTIONARY:
			name = String((sig as Dictionary).get("name", ""))
		modifiers.remove_on_signal(name, self)
	pending["signals"] = pending_signals


func record_contrib(param_id: String, key: String, source_id: String, delta: float) -> void:
	var bucket: String = param_id if key == "" else "%s[%s]" % [param_id, key]
	var current: Dictionary = _as_dict(contrib.get("current", {}))
	var sources: Dictionary = _as_dict(current.get(bucket, {}))
	var prev: float = float(sources.get(source_id, 0.0))
	sources[source_id] = SimMath.quantize(prev + delta)
	current[bucket] = sources
	contrib["current"] = current


func record_error(code: String, msg: String) -> void:
	if errors.size() >= SimTypes.MAX_ERROR_LOG:
		errors.remove_at(0)
	errors.append({
		"code": code,
		"msg": msg,
		"day_index": clock.day_index,
	})


func python_hash_payload() -> Dictionary:
	var py_flags: Dictionary = {}
	var flag_ids: Array[String] = SimMath.sorted_keys(flags)
	for i: int in range(flag_ids.size()):
		var flag_id: String = flag_ids[i]
		var row: Dictionary = _as_dict(flags[flag_id])
		var expires: Variant = row.get("expires_day", null)
		py_flags[flag_id] = {
			"expires_day": expires,
			"set_day": int(floor(float(row.get("set_day", 0)))),
			"source": String(row.get("source", "scenario")),
			"value": int(floor(float(row.get("value", 1)))),
		}
	var py_mods: Array = []
	for i: int in range(active_modifiers.size()):
		var mod: Dictionary = active_modifiers[i]
		py_mods.append({
			"def_id": String(mod.get("def_id", "")),
			"end_day": int(floor(float(mod.get("end_day", -1)))),
			"scope_key": String(mod.get("scope_key", "")),
			"source": String(mod.get("source", "scenario")),
			"stacks": int(floor(float(mod.get("stacks", 1)))),
			"start_day": int(floor(float(mod.get("start_day", 0)))),
			"uid": int(floor(float(mod.get("uid", 0)))),
		})
	return {
		"date_str": clock.date,
		"day_index": clock.day_index,
		"flags": py_flags,
		"gov_axis_position": _python_axis_position(),
		"modifiers": py_mods,
		"params": _python_params(),
		"parliament_seats": params.get_val("coalition_seats", "", self),
		"player": {
			"leader_id": String(player.get("leader_id", "")),
			"party_id": String(player.get("party_id", "")),
			"role": String(player.get("role", "pm")),
		},
		"policies": policies.duplicate(true),
		"promises": _python_promises(),
		"rng": _python_rng(),
		"vision_progress": params.get_val("vision_progress", "", self),
	}


func _python_params() -> Dictionary:
	var merged: Dictionary = params.export_scalars().duplicate(true)
	var scoped: Dictionary = params.export_scoped()
	var scoped_ids: Array[String] = SimMath.sorted_keys(scoped)
	for i: int in range(scoped_ids.size()):
		merged[scoped_ids[i]] = scoped[scoped_ids[i]]
	merged["gov_axis_position"] = _python_axis_position()
	merged["voter_cynicism"] = params.get_val("cynicism", "", self)
	merged["islamic_assoc_strength"] = params.get_val("faction_strength", "mujama", self)
	return merged


func _python_axis_position() -> Dictionary:
	var axes: Array[String] = ["territory", "security", "economy", "religion", "foreign"]
	var out: Dictionary = {}
	for i: int in range(axes.size()):
		out[axes[i]] = float(gov_axis_position.get(axes[i], 0.0))
	return out


func _python_promises() -> Array:
	var out: Array = []
	for i: int in range(promises.size()):
		var row: Dictionary = _as_dict(promises[i]).duplicate(true)
		if row.has("boldness"):
			row["boldness"] = int(floor(float(row["boldness"]) + 0.5))
		if row.has("violation_penalty"):
			row["violation_penalty"] = int(floor(float(row["violation_penalty"]) + 0.5))
		if row.has("stance_hint") and row["stance_hint"] is Dictionary:
			var hint: Dictionary = row["stance_hint"]
			if hint.has("value"):
				hint["value"] = int(floor(float(hint["value"]) + 0.5))
			row["stance_hint"] = hint
		out.append(row)
	return out


func _python_rng() -> Dictionary:
	var contract: Dictionary = {
		"ai": true, "combat": true, "core": true, "economy": true, "elections": true,
		"events": true, "politics": true, "random_events": true, "world": true,
	}
	var out_streams: Dictionary = {}
	var keys: Array[String] = SimMath.sorted_keys(rng.streams)
	for i: int in range(keys.size()):
		var key: String = keys[i]
		var st: SimRNG.Stream = rng.streams[key] as SimRNG.Stream
		if st == null:
			continue
		if not contract.has(key) and st.draws <= 0:
			continue
		out_streams[key] = {
			"calls": st.draws,
			"s0": _u32(st.s0),
			"s1": _u32(st.s1),
			"s2": _u32(st.s2),
			"s3": _u32(st.s3),
		}
	return {"master_seed": _u32(rng.master_seed), "streams": out_streams}


func _u32(value: int) -> int:
	var word: int = value & 0xFFFFFFFF
	if word < 0:
		word += 4294967296
	return word


func to_raw_state_dict() -> Dictionary:
	return {
		"meta": meta.to_dict(),
		"clock": clock.to_dict(),
		"player": player.duplicate(true),
		"flags": flags.duplicate(true),
		"active_modifiers": _modifier_array(),
		"rng": rng.to_dict(),
		"params": {"scalars": params.export_scalars(), "scoped": params.export_scoped()},
		"modules": modules.duplicate(true),
		"counters": counters.to_dict(),
		"history": history.duplicate(true),
		"contrib": contrib.duplicate(true),
		"one_off_flows": one_off_flows.duplicate(true),
		"pending": pending.duplicate(true),
		"policies": policies.duplicate(true),
		"offices": offices.duplicate(true),
		"parliament": parliament.duplicate(true),
		"param_status": param_status.duplicate(true),
		"run": run.duplicate(true),
		"input_log": _dict_array_copy(input_log),
		"stats": stats.duplicate(true),
		"errors": _dict_array_copy(errors),
	}


func from_raw_state_dict(d: Dictionary) -> void:
	var meta_d: Dictionary = _as_dict(d.get("meta", {}))
	meta.scenario_id = String(meta_d.get("scenario_id", meta.scenario_id))
	meta.master_seed = int(meta_d.get("master_seed", meta.master_seed))
	meta.ruleset_hash = String(meta_d.get("ruleset_hash", meta.ruleset_hash))
	meta.ironman = bool(meta_d.get("ironman", meta.ironman))
	meta.save_version = int(meta_d.get("save_version", meta.save_version))
	var clock_d: Dictionary = _as_dict(d.get("clock", {}))
	clock.day_index = int(clock_d.get("day_index", 0))
	clock.abs_day = int(clock_d.get("abs_day", clock.abs_day))
	clock.y = int(clock_d.get("y", clock.y))
	clock.m = int(clock_d.get("m", clock.m))
	clock.d = int(clock_d.get("d", clock.d))
	clock.weekday = int(clock_d.get("weekday", clock.weekday))
	clock.date = String(clock_d.get("date", clock.date))
	clock.start_date = String(clock_d.get("start_date", clock.start_date))
	if d.has("rng"):
		rng.from_dict(_as_dict(d.get("rng", {})), meta.master_seed)
	player = _as_dict(d.get("player", player))
	flags = _as_dict(d.get("flags", flags))
	modules = _as_dict(d.get("modules", modules))
	policies = _as_dict(d.get("policies", policies))
	offices = _as_dict(d.get("offices", offices))
	parliament = _as_dict(d.get("parliament", parliament))
	param_status = _as_dict(d.get("param_status", param_status))
	history = _as_dict(d.get("history", history))
	contrib = _as_dict(d.get("contrib", contrib))
	one_off_flows = _as_dict(d.get("one_off_flows", one_off_flows))
	pending = _as_dict(d.get("pending", pending))
	var params_d: Dictionary = _as_dict(d.get("params", {}))
	params._scalars = _as_dict(params_d.get("scalars", {}))
	params._scoped = _as_dict(params_d.get("scoped", {}))


func _set_clock(start_date: String, day_index: int) -> void:
	var start_abs: int = SimCalendar.date_to_abs_day(start_date)
	var abs_day: int = start_abs + day_index
	var ymd: Vector3i = SimCalendar.civil_from_days(abs_day)
	clock.start_date = start_date
	clock.day_index = day_index
	clock.abs_day = abs_day
	clock.y = ymd.x
	clock.m = ymd.y
	clock.d = ymd.z
	clock.weekday = SimCalendar.weekday_from_abs_day(abs_day)
	clock.date = SimCalendar.format_ymd(clock.y, clock.m, clock.d)
	clock.is_week = SimCalendar.is_week(clock.weekday)
	clock.is_month = SimCalendar.is_month(clock.d)
	clock.is_quarter = SimCalendar.is_quarter(clock.m, clock.d)
	clock.is_year = SimCalendar.is_year(clock.m, clock.d)


func _load_default_params() -> void:
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.parameters_def)
	for i: int in range(ids.size()):
		var pid: String = ids[i]
		var pdef: Dictionary = _as_dict(GameData.current.parameters_def[pid])
		var scope: String = String(pdef.get("scope", "national"))
		var init_v: Variant = pdef.get("init_1977", null)
		if init_v == null:
			if scope == "national":
				params.set_val(pid, "", 0.0, self)
			continue
		if typeof(init_v) == TYPE_DICTIONARY:
			_write_scoped(pid, init_v)
		elif typeof(init_v) == TYPE_FLOAT or typeof(init_v) == TYPE_INT:
			params.set_val(pid, "", float(init_v), self)
		elif typeof(init_v) == TYPE_BOOL:
			params.set_val(pid, "", 1.0 if bool(init_v) else 0.0, self)


func _overlay_snapshot_params(snap_params: Dictionary) -> void:
	var ids: Array[String] = SimMath.sorted_keys(snap_params)
	for i: int in range(ids.size()):
		var pid: String = ids[i]
		var value: Variant = snap_params[pid]
		if typeof(value) == TYPE_DICTIONARY:
			_write_scoped(pid, value)
		elif typeof(value) == TYPE_FLOAT or typeof(value) == TYPE_INT:
			params.set_val(pid, "", float(value), self)
		elif typeof(value) == TYPE_BOOL:
			params.set_val(pid, "", 1.0 if bool(value) else 0.0, self)


func _write_scoped(param_id: String, value: Variant) -> void:
	var src: Dictionary = _as_dict(value)
	var keys: Array[String] = SimMath.sorted_keys(src)
	for i: int in range(keys.size()):
		var key: String = keys[i]
		var cell: Variant = src[key]
		if cell == null:
			continue
		if typeof(cell) == TYPE_FLOAT or typeof(cell) == TYPE_INT or typeof(cell) == TYPE_BOOL:
			var number: float = float(cell) if typeof(cell) != TYPE_BOOL else (1.0 if bool(cell) else 0.0)
			params.set_val(param_id, key, number, self)


func _init_policies() -> void:
	policies = {}
	if GameData.current == null:
		return
	var levels: Dictionary = _as_dict(params.export_scoped().get("policy_level", {}))
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.policies_def)
	for i: int in range(ids.size()):
		var pol_id: String = ids[i]
		var pol: Dictionary = _as_dict(GameData.current.policies_def[pol_id])
		var tiers: Array = []
		var raw_tiers: Variant = pol.get("tiers", [])
		if typeof(raw_tiers) == TYPE_ARRAY:
			tiers = raw_tiers
		var level: float = 0.0
		if levels.has(pol_id):
			level = float(levels[pol_id])
		elif not tiers.is_empty():
			level = _tier_number(tiers[0])
		var tier_idx: int = 0
		for t: int in range(tiers.size()):
			if absf(_tier_number(tiers[t]) - level) < 1.0e-6:
				tier_idx = t
				break
		policies[pol_id] = {
			"id": pol_id,
			"level": level,
			"target_level": level,
			"tier_idx": tier_idx,
			"cooldown_until_day": 0,
			"PendingBillId": null,
		}


func _align_python_init_params() -> void:
	var scoped: Dictionary = params.export_scoped()
	var region_defaults: Dictionary = {
		"region_absorption_priority": 50.0,
		"region_investment_priority": 50.0,
		"region_security_posture": 50.0,
		"region_vote_share": 40.0,
	}
	var default_ids: Array[String] = SimMath.sorted_keys(region_defaults)
	for i: int in range(default_ids.size()):
		var param_id: String = default_ids[i]
		var table: Dictionary = _as_dict(scoped.get(param_id, {}))
		var region_ids: Array[String] = SimMath.sorted_keys(table)
		if not region_ids.has("south_lebanon"):
			region_ids.append("south_lebanon")
		for r: int in range(region_ids.size()):
			params.set_val(param_id, region_ids[r], float(region_defaults[param_id]), self)
	params.set_val("coup_risk", "", 0.0, self)
	params.set_val("assassination_risk", "", 2.0, self)
	var war_ids: Array[String] = ["egypt", "jordan", "syria", "lebanon", "iraq", "saudi", "iran"]
	var war: Dictionary = _as_dict(params.export_scoped().get("war_probability", {}))
	for i: int in range(war_ids.size()):
		if not war.has(war_ids[i]):
			params.set_val("war_probability", war_ids[i], 15.0, self)


func _ensure_hash_params() -> void:
	params.set_val("voter_cynicism", "", params.get_val("cynicism", "", self), self)
	if GameData.current == null:
		return
	var raw_parties: Variant = _as_dict(GameData.current.entity_aliases).get("parties", [])
	if typeof(raw_parties) != TYPE_ARRAY:
		return
	var party_rows: Array = raw_parties
	var existing: Dictionary = _as_dict(params.export_scoped().get("favor_party", {}))
	for i: int in range(party_rows.size()):
		var party_id: String = String(party_rows[i])
		if party_id != "" and not existing.has(party_id):
			params.set_val("favor_party", party_id, 0.0, self)


func _tier_number(tier: Variant) -> float:
	if typeof(tier) == TYPE_DICTIONARY:
		return float((tier as Dictionary).get("v", 0.0))
	if typeof(tier) == TYPE_INT or typeof(tier) == TYPE_FLOAT:
		return float(tier)
	return 0.0


func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []


func _load_flags(raw: Variant) -> void:
	flags = {}
	if typeof(raw) == TYPE_DICTIONARY:
		var fmap: Dictionary = raw
		var keys: Array[String] = SimMath.sorted_keys(fmap)
		for i: int in range(keys.size()):
			var fid: String = keys[i]
			var entry: Dictionary = _as_dict(fmap[fid])
			flags[fid] = {
				"set_day": int(entry.get("set_day", 0)),
				"expires_day": entry.get("expires_day", null),
				"source": String(entry.get("source", "scenario")),
				"value": int(floor(float(entry.get("value", 1)))),
			}
	elif typeof(raw) == TYPE_ARRAY:
		var items: Array = raw
		for i: int in range(items.size()):
			var entry: Dictionary = _as_dict(items[i])
			if not entry.has("id"):
				continue
			flags[String(entry["id"])] = {
				"set_day": int(entry.get("set_day", 0)),
				"expires_day": entry.get("expires_day", null),
				"source": String(entry.get("source", "scenario")),
				"value": int(floor(float(entry.get("value", 1)))),
			}
	if flags.has("likud_in_power") and not flags.has("likud_in_government"):
		flags["likud_in_government"] = _as_dict(flags["likud_in_power"]).duplicate(true)


func _load_modifiers(raw: Variant) -> void:
	active_modifiers.clear()
	modifiers.active = active_modifiers
	if typeof(raw) != TYPE_ARRAY:
		return
	var items: Array = raw
	for i: int in range(items.size()):
		var entry: Dictionary = _as_dict(items[i])
		var def_id: String = String(entry.get("def_id", entry.get("id", "")))
		if def_id == "":
			continue
		var uid: int = int(entry.get("uid", counters.next_modifier_uid))
		counters.next_modifier_uid = maxi(counters.next_modifier_uid, uid + 1)
		active_modifiers.append({
			"uid": uid,
			"def_id": def_id,
			"scope_key": String(entry.get("scope_key", "")),
			"stacks": int(entry.get("stacks", 1)),
			"start_day": int(entry.get("start_day", 0)),
			"end_day": int(entry.get("end_day", -1)),
			"source": String(entry.get("source", "scenario")),
		})


func _activate_era_params() -> void:
	var era: int = SimCalendar.compute_era(clock.y, clock.m)
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.parameters_def)
	for i: int in range(ids.size()):
		var pid: String = ids[i]
		var pdef: Dictionary = _as_dict(GameData.current.parameters_def[pid])
		var era_v: Variant = pdef.get("era", null)
		var active: bool = true
		if typeof(era_v) == TYPE_ARRAY:
			active = false
			var era_arr: Array = era_v
			for j: int in range(era_arr.size()):
				var cell: Variant = era_arr[j]
				if typeof(cell) != TYPE_INT and typeof(cell) != TYPE_FLOAT:
					continue
				if int(cell) == era:
					active = true
		elif typeof(era_v) == TYPE_FLOAT or typeof(era_v) == TYPE_INT:
			active = int(era_v) == era
		param_status[pid] = "active" if active else "inactive"


func _init_modules(snapshot: Dictionary) -> void:
	offices = {
		"prime_minister": "begin",
		"foreign": "dayan",
		"defense": "weizman",
		"finance": "ehrlich",
		"deputy_pm": "ehrlich",
		"agriculture": "sharon",
		"interior": "burg",
		"education": "hammer",
		"religious_affairs": "abuhatzeira",
		"housing": "patt",
		"absorption": "levy",
		"energy": "modai",
		"chief_of_staff": "gur",
		"mossad_chief": "hofi",
		"shin_bet_chief": "shalom",
		"attorney_general": "barak_aharon",
		"supreme_court_president": "kahan",
		"boi_governor": "gafni",
		"opposition_leader": "peres",
	}
	parliament = _as_dict(snapshot.get("parliament", {}))
	var coalition_members: Array = _coalition_members()
	modules = {
		"M02": {
			"shock_mem": {},
			"history_24m": {},
			"thresholds": {},
			"one_off_flows": {"budget_balance": 0.0},
			"last_contribs": {},
			"baseline_shifts": {},
			"shock_memories": {},
			"thr_states": {},
		},
		"M03": {"coalition_parties": coalition_members, "knesset_seats": _as_dict(parliament.get("knesset_seats", {}))},
		"M04": {},
		"M05": {
			"weekly_slots_used": 0,
			"weekly_slots_max": 2,
			"action_cooldowns": {},
			"active_actions": [],
			"completed_actions": {},
			"iou_ledger": [],
			"iou_incurred_total": 0,
		},
		"M06": {"offices": offices.duplicate(true), "characters": {}},
		"M07": _m07_block(),
		"M08": {
			"faction_active": {
				"fatah": true, "pflp": true, "jordan_notables": true, "local_mayors": true,
				"village_leagues": false, "mujama": true, "hamas": false, "pij": false, "pa_security": false,
			},
			"faction_meta": {},
			"autonomy_track": {"stage": "NONE", "modality": "NONE", "stagnation_months": 0, "implementation_hold_months": 0, "delegation_active_days": 0},
			"uprising_state": {"active": false, "intensity": 0.0, "duration_months": 0, "calm_streak_months": 0, "cumulative_repression_impulse": 0.0, "unlu_formed": false},
			"ai_action_log": [],
		},
		"M09": {
			"mobilization_target": 10.0,
			"intel_accuracy": 79.65,
			"peace_months_streak": 44,
			"last_ceasefire_date": "1974-05-31",
			"fronts": {
				"egypt": {"front_id": "egypt", "status": "PEACE", "active_war": null},
				"jordan": {"front_id": "jordan", "status": "PEACE", "active_war": null},
				"syria": {"front_id": "syria", "status": "PEACE", "active_war": null},
				"lebanon": {"front_id": "lebanon", "status": "BORDER_FRICTION", "active_war": null},
				"gaza": {"front_id": "gaza", "status": "PEACE", "active_war": null},
				"internal": {"front_id": "internal", "status": "PEACE", "active_war": null},
			},
			"nuclear": {"arsenal_tier": 2, "alert_active": false, "lakam_active": true},
		},
		"M10": {
			"expected_inflation": 35.0,
			"budget_cycle": {"fiscal_year": 1977, "status": "PASSED", "opened_day": 0, "deadline_day": 90},
		},
		"M11": {"regions": {}, "key_sites": GameData.current.sites_def, "planning_overlays": GameData.current.plans_def, "active_overlay": "allon_plan"},
		"M12": {"status": {}, "fired": {}, "scheduled": [], "queue": [], "month_forced_count": 0, "advisor_handles_minor": true},
		"M13": {"stage": 0, "survival_mode_active": false, "protest_tier": 0, "resist_actors": {}},
		"M14": {"scenario_id": meta.scenario_id, "world_variant_mode": "historical_gravity", "fictional_leader_counter": 0},
	}
	_fill_regions()
	_fill_characters()
	for axis: String in SimTypes.STANCE_AXES:
		gov_axis_position[axis] = 0.0
		axis_impulse[axis] = 0.0


func _coalition_members() -> Array:
	var government: Dictionary = _as_dict(parliament.get("government", {}))
	var members: Variant = government.get("members", [])
	if typeof(members) == TYPE_ARRAY:
		return (members as Array).duplicate()
	return ["likud", "nrp", "agudat"]


func _fill_regions() -> void:
	var m11: Dictionary = _as_dict(modules.get("M11", {}))
	var regions: Dictionary = {}
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.regions_def)
	for i: int in range(ids.size()):
		var rid: String = GameData.current.resolve_region_id(ids[i])
		var src: Dictionary = _as_dict(GameData.current.regions_def[ids[i]])
		var exists: bool = true
		if src.has("exists"):
			exists = bool(src["exists"])
		elif rid == "south_lebanon":
			exists = false
		regions[rid] = {
			"region_id": rid,
			"exists": exists,
			"legal_status": String(src.get("legal_status", "sovereign")),
		}
	m11["regions"] = regions
	modules["M11"] = m11


func _fill_characters() -> void:
	var m06: Dictionary = _as_dict(modules.get("M06", {}))
	var characters: Dictionary = {}
	var ids: Array[String] = SimMath.sorted_keys(GameData.current.characters_def)
	for i: int in range(ids.size()):
		var cid: String = ids[i]
		characters[cid] = _as_dict(GameData.current.characters_def[cid]).duplicate(true)
	m06["characters"] = characters
	m06["offices"] = offices.duplicate(true)
	modules["M06"] = m06


func _m07_block() -> Dictionary:
	return {
		"version": 1,
		"countries": {},
		"us_politics": {
			"president_id": "carter",
			"president_party": "democrat",
			"admin_archetype": "human_rights_mediator",
			"admin_baseline": 55.0,
		},
		"active_negotiation": null,
		"crisis_timers": [],
		"immigration_breakdown": {"ussr": 8500.0, "ethiopia": 120.0, "western": 6800.0, "mena_latam": 5580.0, "pulse_bonus": 0.0},
		"nuclear_intel": {},
		"ai_action_log": [],
	}


func _modifier_array() -> Array:
	var out: Array = []
	for i: int in range(active_modifiers.size()):
		out.append(active_modifiers[i].duplicate(true))
	return out


func _dict_array_copy(src: Array[Dictionary]) -> Array:
	var out: Array = []
	for i: int in range(src.size()):
		out.append(src[i].duplicate(true))
	return out


func _as_dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
