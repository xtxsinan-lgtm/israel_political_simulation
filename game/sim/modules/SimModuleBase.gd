class_name SimModuleBase
extends RefCounted

var module_id: String = "M00"


func init_scenario(_state: SimState, _scenario_bundle: Dictionary) -> void:
	pass


func daily_step(_step_no: int, _state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	return []


func weekly_step(_step_no: int, _state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	return []


func monthly_step(_step_no: int, _state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	return []


func quarterly_step(_step_no: int, _state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	return []


func annual_step(_step_no: int, _state: SimState, _ctx: Dictionary) -> Array[Dictionary]:
	return []


func handle_custom_op(_op_name: String, _state: SimState, _args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	return []


func provide_terms(_provider_name: String, _state: SimState, _param_id: String, _scope_key: String) -> Array[Dictionary]:
	return []
