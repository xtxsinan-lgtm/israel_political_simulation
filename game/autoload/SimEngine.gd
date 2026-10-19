extends Node

## Node autoload wrapping SimDirector. Drives the real-time day tick for the desk UI,
## publishes SimReadonlySnapshot via the EventBus, and owns quick save / quick load.

const QUICKSAVE_PATH: String = "user://quicksave.ipsave.json"
const MIN_SPEED: int = 1
const MAX_SPEED: int = 5
## Upper bound on days simulated in one frame so a long frame hitch cannot spiral.
const MAX_DAYS_PER_FRAME: int = 4

var director: SimDirector = null
var paused: bool = true
var speed_level: int = 2
var pause_reason: String = "start"
var _accum: float = 0.0
var _snapshot: SimReadonlySnapshot = null


func start_new_game(scenario_id: String, custom_seed: int = -1, is_ironman: bool = false) -> Error:
	if director == null:
		director = SimDirector.new()
	var err: Error = director.start_new_game(scenario_id, custom_seed, is_ironman)
	if err != OK:
		return err
	_accum = 0.0
	paused = true
	pause_reason = "start"
	speed_level = clampi(int(director.state.run.get("speed", speed_level)), MIN_SPEED, MAX_SPEED)
	_sync_run_flags()
	_snapshot = null
	_emit_pause_state()
	return OK


## Seconds of real time per simulated day for speed levels 1..5.
static func seconds_per_day(level: int) -> float:
	match clampi(level, MIN_SPEED, MAX_SPEED):
		1:
			return 2.0
		2:
			return 1.0
		3:
			return 0.5
		4:
			return 0.25
		_:
			return 0.1


func _process(delta: float) -> void:
	if paused or not _can_tick():
		return
	speed_level = clampi(int(director.state.run.get("speed", speed_level)), MIN_SPEED, MAX_SPEED)
	_accum += delta
	var interval: float = seconds_per_day(speed_level)
	var steps: int = 0
	while _accum >= interval and steps < MAX_DAYS_PER_FRAME and not paused:
		_accum -= interval
		steps += 1
		_advance_one_day()
	if _accum >= interval:
		_accum = 0.0


func _can_tick() -> bool:
	if director == null or director.state == null:
		return false
	return not bool(director.state.run.get("headless", false))


func _advance_one_day() -> void:
	var result: Dictionary = director.step_one_day()
	var ended: bool = bool(result.get("ended", false))
	var auto_paused: bool = bool(result.get("paused", false))
	_snapshot = director.capture_snapshot()
	if ended or auto_paused:
		paused = true
		pause_reason = "ended" if ended else _auto_pause_reason(_snapshot)
	_sync_run_flags()
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus == null:
		return
	bus.sim_day_advanced.emit(_snapshot)
	var clock: SimState.SimClock = director.state.clock
	bus.day_advanced.emit(clock.day_index, clock.date, clock.is_week, clock.is_month, clock.is_quarter, clock.is_year)
	if ended:
		bus.end_tenure_triggered.emit({
			"day_index": clock.day_index,
			"date": clock.date,
			"ending_id": String(result.get("ending_id", "")),
		})
		_emit_pause_state()
	elif auto_paused:
		bus.sim_auto_paused.emit(pause_reason)
		_emit_pause_state()
		if not _snapshot.pending_events.is_empty():
			bus.event_modal_requested.emit(_snapshot.pending_events[0])


func _auto_pause_reason(snap: SimReadonlySnapshot) -> String:
	if not snap.pending_events.is_empty():
		return "event"
	var m03: Variant = director.state.modules.get("M03", {})
	if typeof(m03) == TYPE_DICTIONARY and bool((m03 as Dictionary).get("vote_modal_open", false)):
		return "vote"
	var votes: Variant = director.state.pending.get("vote_requests", [])
	if typeof(votes) == TYPE_ARRAY and not (votes as Array).is_empty():
		return "vote"
	return "alert"


func get_snapshot() -> SimReadonlySnapshot:
	if director == null or director.state == null:
		return null
	if _snapshot == null or _snapshot.day_index != director.state.clock.day_index:
		_snapshot = director.capture_snapshot()
	return _snapshot


func set_paused(value: bool) -> void:
	if director != null and director.state != null and value == false:
		if String(director.state.run.get("phase", "")) == "ENDED":
			value = true
	if paused == value:
		return
	paused = value
	pause_reason = "player" if paused else ""
	_accum = 0.0
	_sync_run_flags()
	_emit_pause_state()


func toggle_pause() -> void:
	set_paused(not paused)


func set_speed(level: int) -> void:
	speed_level = clampi(level, MIN_SPEED, MAX_SPEED)
	_accum = 0.0
	_sync_run_flags()
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.sim_speed_changed.emit(speed_level)
	_emit_pause_state()


func submit_command(cmd: Dictionary) -> Error:
	if director == null:
		return ERR_UNCONFIGURED
	var err: Error = director.submit_command(cmd)
	if err == OK and director.state != null:
		_snapshot = director.capture_snapshot()
		var bus: DeskEventBus = DeskEventBus.hub()
		if bus != null:
			bus.snapshot_updated.emit(_snapshot)
	return err


func quick_save() -> Error:
	if director == null or director.state == null:
		return ERR_UNCONFIGURED
	var saver: SaveSystem = SaveSystem.new()
	var text: String = saver.to_ipsave_json(saver.build_envelope(director.state, director.command_log))
	var file: FileAccess = FileAccess.open(QUICKSAVE_PATH, FileAccess.WRITE)
	if file == null:
		return FileAccess.get_open_error()
	file.store_string(text)
	file.close()
	return OK


func quick_load() -> Error:
	if not FileAccess.file_exists(QUICKSAVE_PATH):
		return ERR_FILE_NOT_FOUND
	var file: FileAccess = FileAccess.open(QUICKSAVE_PATH, FileAccess.READ)
	if file == null:
		return FileAccess.get_open_error()
	var text: String = file.get_as_text()
	file.close()
	var saver: SaveSystem = SaveSystem.new()
	var envelope: Dictionary = saver.from_ipsave_json(text)
	if envelope.is_empty():
		return ERR_FILE_CORRUPT
	var load_err: Error = SimDirector.ensure_runtime_data()
	if load_err != OK:
		return load_err
	var loaded: SimDirector = SimDirector.new()
	var err: Error = saver.load_into(loaded, envelope)
	if err != OK:
		return err
	director = loaded
	paused = true
	pause_reason = "loaded"
	_accum = 0.0
	_sync_run_flags()
	_snapshot = director.capture_snapshot()
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.sim_day_advanced.emit(_snapshot)
	_emit_pause_state()
	return OK


func advance_single_day_headless() -> void:
	if director == null or director.state == null:
		return
	director.state.run["headless"] = true
	director.step_one_day()


func get_state_hash_sha256() -> String:
	if director == null:
		return ""
	return director.get_state_hash_sha256()


func step_one_day() -> Dictionary:
	if director == null or director.state == null:
		return {"ended": true}
	return director.step_one_day()


## Mirrors the wrapper's pause / speed into state.run (excluded from the state hash)
## so HUD widgets that read run["paused"] / run["speed"] stay consistent.
func _sync_run_flags() -> void:
	if director == null or director.state == null:
		return
	director.state.run["paused"] = paused
	director.state.run["speed"] = speed_level


func _emit_pause_state() -> void:
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus == null:
		return
	var reasons: PackedStringArray = PackedStringArray()
	if paused and pause_reason != "":
		reasons.append(pause_reason)
	bus.pause_state_changed.emit(paused, speed_level, reasons)
