extends Control


func _ready() -> void:
	if not SimRNG.verify_t01_golden_vectors():
		push_error("T01 golden vectors failed")
	if not SimCalendar.verify_t02_calendar_vectors():
		push_error("T02 calendar vectors failed")
