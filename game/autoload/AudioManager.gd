extends Node

const TENSION_ENTER_THRESHOLD: float = 65.0
const TENSION_EXIT_THRESHOLD: float = 52.0
const MODAL_DUCKING_DB: float = -8.0

var current_mood: String = "PEACE_CALM"


func transition_to_mood(new_mood: String) -> void:
	current_mood = new_mood


func set_modal_ducking(is_ducked: bool) -> void:
	if is_ducked:
		current_mood = current_mood
