extends Node

var ui_state: Dictionary = {
	"active_drawer": "NONE",
	"active_map_layer": "F1_POLITICAL",
	"selected_region_id": "",
}


func open_drawer(drawer_id: String, subtab: int = 0, highlight_target: String = "") -> void:
	ui_state["active_drawer"] = drawer_id
	ui_state["active_drawer_subtab"] = subtab
	ui_state["highlight_target"] = highlight_target


func close_active_drawer() -> void:
	ui_state["active_drawer"] = "NONE"
