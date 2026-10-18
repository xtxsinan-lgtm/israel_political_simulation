extends Node

const PEACE_GOVERNANCE: String = "PEACE_GOVERNANCE"
const POLITICAL_TENSION: String = "POLITICAL_TENSION"
const WAR_CRISIS: String = "WAR_CRISIS"
const DUCK_DB: float = -8.0
const CROSSFADE_SEC: float = 15.0

var mood: String = PEACE_GOVERNANCE
var ducked: bool = false


func _ready() -> void:
	_ensure_buses()


func select_mood(at_war: bool, protest_tier: int, coalition_risk: bool) -> String:
	if at_war:
		return WAR_CRISIS
	if protest_tier >= 2 or coalition_risk:
		return POLITICAL_TENSION
	return PEACE_GOVERNANCE


func set_mood(next: String) -> void:
	if next == mood:
		return
	mood = next


func set_modal_ducking(is_ducked: bool) -> void:
	_ensure_buses()
	ducked = is_ducked
	var bus_index: int = AudioServer.get_bus_index("BGM")
	if bus_index < 0:
		return
	AudioServer.set_bus_volume_db(bus_index, DUCK_DB if is_ducked else 0.0)


func _ensure_buses() -> void:
	var names: PackedStringArray = PackedStringArray(["BGM", "SFX_Diegetic", "Ambience"])
	for i: int in range(names.size()):
		if AudioServer.get_bus_index(names[i]) >= 0:
			continue
		AudioServer.add_bus()
		AudioServer.set_bus_name(AudioServer.bus_count - 1, names[i])
