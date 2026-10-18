class_name M02Contradictions
extends SimModuleBase
# Isolation: extends RefCounted through SimModuleBase.


func _init() -> void:
	module_id = "M02"


func monthly_step(step_no: int, state: SimState, ctx: Dictionary) -> Array[Dictionary]:
	if step_no != 10:
		return []
	var net: CausalNet = CausalNet.new()
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(state)
	var modules: Dictionary = {}
	if ctx.has("modules") and typeof(ctx["modules"]) == TYPE_DICTIONARY:
		modules = ctx["modules"]
	net.record_monthly_history(state)
	var effects: Array[Dictionary] = net.evaluate_thresholds(state)
	var steps: Array[Dictionary] = net.step_all_nodes(state, expr, modules)
	for i: int in range(steps.size()):
		effects.append(steps[i])
	return effects


func handle_custom_op(op_name: String, state: SimState, args: Dictionary, _ctx: Dictionary) -> Array[Dictionary]:
	if op_name != "m02_add_baseline_shift":
		return []
	var m02: Dictionary = {}
	if typeof(state.modules.get("M02", {})) == TYPE_DICTIONARY:
		m02 = state.modules["M02"]
	var shifts: Dictionary = {}
	if typeof(m02.get("baseline_shifts", {})) == TYPE_DICTIONARY:
		shifts = m02["baseline_shifts"]
	var param_id: String = String(args.get("param", args.get("target", "")))
	var key: String = String(args.get("key", ""))
	var node_key: String = param_id if key == "" else "%s[%s]" % [param_id, key]
	var delta: float = float(args.get("value", args.get("delta", 0.0)))
	shifts[node_key] = SimMath.quantize(float(shifts.get(node_key, 0.0)) + delta)
	m02["baseline_shifts"] = shifts
	state.modules["M02"] = m02
	return []
