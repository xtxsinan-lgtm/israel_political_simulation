class_name EraSkinManager
extends Node

var era_id: String = "era_1970s"


func era_for_date(date_text: String) -> String:
	var year: int = 1977
	if date_text.length() >= 4:
		year = int(date_text.substr(0, 4))
	if year >= 1990:
		return "era_1990s"
	if year >= 1980:
		return "era_1980s"
	return "era_1970s"


func apply_date(date_text: String) -> bool:
	var next: String = era_for_date(date_text)
	if next == era_id:
		return false
	era_id = next
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.era_skin_changed.emit(era_id)
	return true
