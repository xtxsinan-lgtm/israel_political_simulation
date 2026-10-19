extends Node


func _ready() -> void:
	var err: Error = ensure_loaded()
	if err != OK:
		push_error("DataRegistry: runtime data failed to load (%s)" % error_string(err))


## Loads res://res/data/*.json once into GameData.current (no-op when already loaded).
func ensure_loaded() -> Error:
	return SimDirector.ensure_runtime_data()


func load_all_runtime_data() -> Error:
	if GameData.current == null:
		GameData.current = GameData.new()
	return GameData.current.load_all_runtime_data()


func get_scenario_bundle(scenario_id: String) -> Dictionary:
	return GameData.current.get_scenario_bundle(scenario_id)


func resolve_param_alias(raw_param_id: String) -> String:
	return GameData.current.resolve_param_alias(raw_param_id)


func resolve_region_id(raw_region_id: String) -> String:
	return GameData.current.resolve_region_id(raw_region_id)


func resolve_pal_faction_id(raw_faction_id: String) -> String:
	return GameData.current.resolve_pal_faction_id(raw_faction_id)


func resolve_party_id(raw_party_id: String) -> String:
	return GameData.current.resolve_party_id(raw_party_id)


func resolve_bloc_id(raw_bloc_id: String) -> String:
	return GameData.current.resolve_bloc_id(raw_bloc_id)


func resolve_office_id(raw_office_id: String) -> String:
	return GameData.current.resolve_office_id(raw_office_id)


func get_custom_handler_owner(custom_name: String) -> String:
	return GameData.current.get_custom_handler_owner(custom_name)


func get_compiled_ast(expr_str: String) -> Array:
	return GameData.current.get_compiled_ast(expr_str)
