extends SceneTree


func _initialize() -> void:
	_run()


func _run() -> void:
	var failed: bool = false
	var data: GameData = GameData.new()
	if data.load_all_runtime_data() != OK:
		push_error("load failed")
		quit(1)
		return
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(state)
	var proc: EffectProcessor = EffectProcessor.new()
	proc.expr_engine = expr
	proc.causal_net = CausalNet.new()
	failed = failed or not _test_numeric(state, proc)
	failed = failed or not _test_modifiers(state)
	failed = failed or not _test_memory(state, proc)
	failed = failed or not _test_hysteresis(state)
	failed = failed or not _test_expr(expr, state)
	failed = failed or not _test_explain(state, expr)
	failed = failed or not _test_zero_drift()
	if failed:
		push_error("M2 tests failed")
		quit(1)
		return
	print("M2_CAUSAL_OK")
	quit(0)


func _test_numeric(state: SimState, proc: EffectProcessor) -> bool:
	var effects: Array[Dictionary] = [
		{"op": "set", "target": "public_security", "value": 40.0, "priority": 0},
		{"op": "set", "target": "public_security", "value": 50.0, "priority": 100},
		{"op": "mul", "target": "public_security", "value": 2.0, "scale": 0.5},
		{"op": "add", "target": "public_security", "value": 4.0, "scale": 0.5},
	]
	proc.apply_effects(effects, {"stream_name": "core"}, state, 0)
	var got: float = state.params.get_val("public_security", "", state)
	var expect: float = SimMath.quantize(50.0 * (1.0 + (2.0 - 1.0) * 0.5) + 4.0 * 0.5)
	if not is_equal_approx(got, expect):
		push_error("numeric got %s expect %s" % [got, expect])
		return false
	return true


func _test_modifiers(state: SimState) -> bool:
	var engine: ModifierEngine = state.modifiers
	engine.add_modifier("debt_hist", {"stack": "replace", "growth_per_month": 1.5, "strength": 2.0, "scope_key": "a"}, "test", state)
	var uid: int = int(engine.active[engine.active.size() - 1]["uid"])
	engine.add_modifier("debt_hist", {"stack": "refresh", "duration_days": 10, "scope_key": "a"}, "test", state)
	if int(engine.active[engine.active.size() - 1]["uid"]) != uid:
		push_error("refresh changed uid")
		return false
	engine.add_modifier("stack_mod", {"stack": "stack", "scope_key": "b"}, "test", state)
	engine.add_modifier("stack_mod", {"stack": "stack", "scope_key": "b"}, "test", state)
	if int(_find(engine, "stack_mod", "b").get("stacks", 0)) != 2:
		push_error("stack failed")
		return false
	var before: int = engine.active.size()
	engine.add_modifier("stack_mod", {"stack": "ignore", "scope_key": "b"}, "test", state)
	if engine.active.size() != before:
		push_error("ignore failed")
		return false
	state.clock.is_month = true
	var strength_before: float = float(_find(engine, "debt_hist", "a").get("strength", 0.0))
	engine.tick_debt_modifiers(state)
	var strength_after: float = float(_find(engine, "debt_hist", "a").get("strength", 0.0))
	if not is_equal_approx(strength_after, strength_before + 1.5):
		push_error("debt growth %s -> %s" % [strength_before, strength_after])
		return false
	return true


func _test_memory(state: SimState, proc: EffectProcessor) -> bool:
	var effects: Array[Dictionary] = [
		{"op": "add", "target": "alienation", "key": "mizrahi", "value": 10.0, "source": "evt.test", "priority": 0},
	]
	proc.apply_effects(effects, {"module_id": "M12"}, state, 0)
	var m02: Dictionary = state.modules["M02"]
	var memories: Dictionary = m02["shock_memories"]
	var bucket: Array = memories["alienation[mizrahi]"]
	var remaining: float = float((bucket[0] as Dictionary)["remaining"])
	if not is_equal_approx(remaining, 3.0):
		push_error("memory remaining %s" % remaining)
		return false
	proc.causal_net._decay_memories(state)
	m02 = state.modules["M02"]
	memories = m02["shock_memories"]
	bucket = memories["alienation[mizrahi]"]
	remaining = float((bucket[0] as Dictionary)["remaining"])
	if not is_equal_approx(remaining, 2.85):
		push_error("decayed memory %s" % remaining)
		return false
	return true


func _test_hysteresis(state: SimState) -> bool:
	var net: CausalNet = CausalNet.new()
	state.params.set_val("settler_momentum", "", 70.0, state)
	var on_fx: Array[Dictionary] = net.evaluate_thresholds(state)
	if not _has_flag_op(on_fx, "set_flag", "thr.settler_autonomy"):
		push_error("threshold did not set")
		return false
	state.params.set_val("settler_momentum", "", 66.0, state)
	var hold_fx: Array[Dictionary] = net.evaluate_thresholds(state)
	if _has_flag_op(hold_fx, "clear_flag", "thr.settler_autonomy"):
		push_error("threshold cleared inside band")
		return false
	state.params.set_val("settler_momentum", "", 64.0, state)
	var off_fx: Array[Dictionary] = net.evaluate_thresholds(state)
	if not _has_flag_op(off_fx, "clear_flag", "thr.settler_autonomy"):
		push_error("threshold did not clear")
		return false
	return true


func _test_expr(expr: ExprEngine, state: SimState) -> bool:
	var before: int = state.errors.size()
	var shorted: bool = expr.eval_bool(["and", ["lit", false], ["/", ["lit", 1.0], ["lit", 0.0]]], {})
	if shorted or state.errors.size() != before:
		push_error("short circuit failed")
		return false
	var div: float = expr.eval_float(["/", ["lit", 10.0], ["lit", 0.0]], {})
	if div != 0.0:
		push_error("div0 value")
		return false
	var saw: bool = false
	for i: int in range(state.errors.size()):
		if String((state.errors[i] as Dictionary).get("code", "")) == "E_DIV0":
			saw = true
	if not saw:
		push_error("missing E_DIV0")
		return false
	return true


func _test_explain(state: SimState, expr: ExprEngine) -> bool:
	var m02: Dictionary = state.modules["M02"]
	var injected: Array[Dictionary] = []
	for i: int in range(1, 8):
		injected.append({
			"source_id": "e%02d" % i,
			"delta_per_tick": float(i),
			"raw_target_shift": float(i) / 0.1,
		})
	m02["injected_edges"] = {"explain_probe": injected}
	state.modules["M02"] = m02
	var net: CausalNet = CausalNet.new()
	var report: Dictionary = net.explain(state, "explain_probe", "", expr, {}, 5)
	var top: Array = report["top_contributions"]
	if top.size() != 6:
		push_error("explain size %s" % top.size())
		return false
	var first: float = float((top[0] as Dictionary)["delta_per_tick"])
	var fifth: float = float((top[4] as Dictionary)["delta_per_tick"])
	if first < fifth:
		push_error("explain order")
		return false
	if String((top[5] as Dictionary).get("source_id", "")) != "_others":
		push_error("explain others missing")
		return false
	var label: String = String((top[5] as Dictionary).get("source_label_zh", ""))
	if not label.contains("2"):
		push_error("explain rest count %s" % label)
		return false
	return true


func _test_zero_drift() -> bool:
	var fresh: SimState = SimState.new()
	fresh.init_from_scenario_bundle("begin_1977", 19770620, false)
	var expr: ExprEngine = ExprEngine.new()
	expr.bind(fresh)
	var net: CausalNet = CausalNet.new()
	net.init_zero_drift_offsets(fresh, expr, {})
	var report: Dictionary = net.verify_day0_zero_drift(fresh, expr, {})
	var err: float = float(report.get("max_drift_err", 1.0))
	if err >= 0.0001:
		push_error("day0 drift %s" % err)
		return false
	return true


func _find(engine: ModifierEngine, mod_id: String, scope_key: String) -> Dictionary:
	for i: int in range(engine.active.size()):
		var row: Dictionary = engine.active[i]
		if String(row.get("def_id", "")) == mod_id and String(row.get("scope_key", "")) == scope_key:
			return row
	return {}


func _has_flag_op(effects: Array[Dictionary], op: String, flag_id: String) -> bool:
	for i: int in range(effects.size()):
		if String(effects[i].get("op", "")) == op and String(effects[i].get("flag", "")) == flag_id:
			return true
	return false
