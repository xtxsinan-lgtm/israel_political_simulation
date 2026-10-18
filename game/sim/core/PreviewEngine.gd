class_name PreviewEngine
extends RefCounted


static func format_effect_magnitude_zh(delta: float, is_inverted: bool = false) -> Dictionary:
	var d_int: int = SimMath.round_half_up_int(delta)
	var mag: int = absi(d_int)
	var tier_zh: String = ""
	if mag >= 1 and mag <= 3:
		tier_zh = "微幅"
	elif mag >= 4 and mag <= 8:
		tier_zh = "小幅"
	elif mag >= 9 and mag <= 15:
		tier_zh = "显著"
	elif mag >= 16:
		tier_zh = "剧烈"
	var good: bool = d_int < 0 if is_inverted else d_int > 0
	return {
		"delta_int": d_int,
		"tier_zh": tier_zh,
		"signed_str": "%+d" % d_int,
		"is_positive_good": good,
	}


static func preview_effects_on_three_layers(state: SimState, effects: Array, expr: ExprEngine) -> Dictionary:
	var immediate: Array[Dictionary] = []
	var layer1_promises: Array[String] = []
	var layer2_corridor: Array[Dictionary] = []
	var layer3_vision: Array[String] = []
	expr.bind(state)
	for i: int in range(effects.size()):
		if typeof(effects[i]) != TYPE_DICTIONARY:
			continue
		var eff: Dictionary = effects[i]
		if eff.has("display") and bool(eff["display"]) == false:
			continue
		var op: String = String(eff.get("op", ""))
		if op == "add" or op == "set" or op == "mul":
			var delta: float = float(eff.get("value", 0.0))
			if eff.has("scale") and eff["scale"] != null:
				delta *= expr.eval_float(eff["scale"], {})
			immediate.append({
				"param": String(eff.get("target", "")),
				"key": String(eff.get("key", "")),
				"op": op,
				"delta": SimMath.quantize(delta),
				"magnitude": format_effect_magnitude_zh(delta),
			})
		var tags: Variant = eff.get("promise_tags", [])
		if typeof(tags) == TYPE_ARRAY:
			var tag_arr: Array = tags
			for t: int in range(tag_arr.size()):
				layer1_promises.append(String(tag_arr[t]))
		if eff.has("axis"):
			layer2_corridor.append({
				"axis": String(eff.get("axis", "")),
				"delta": float(eff.get("value", 0.0)),
			})
		if String(eff.get("vision", "")) != "":
			layer3_vision.append(String(eff["vision"]))
		if op == "custom" and String(eff.get("key", "")).begins_with("m04_"):
			layer1_promises.append(String(eff.get("key", "")))
	return {
		"immediate": immediate,
		"layer1_promises": layer1_promises,
		"layer2_corridor": layer2_corridor,
		"layer3_vision": layer3_vision,
	}


static func compute_atrocity_or_overreach_risk_badge(effects: Array, state: SimState, expr: ExprEngine) -> Dictionary:
	expr.bind(state)
	var risk: float = 0.0
	var armed: bool = false
	for i: int in range(effects.size()):
		if typeof(effects[i]) != TYPE_DICTIONARY:
			continue
		var eff: Dictionary = effects[i]
		var op: String = String(eff.get("op", ""))
		if op == "schedule_event_window" or op == "random_branch" or eff.has("chance"):
			armed = true
			var p: float = 0.0
			if eff.has("chance") and eff["chance"] != null:
				p = float(eff["chance"])
			elif typeof(eff.get("value", null)) == TYPE_DICTIONARY:
				p = float((eff["value"] as Dictionary).get("p", (eff["value"] as Dictionary).get("chance", 0.0)))
			risk = 1.0 - (1.0 - risk) * (1.0 - clampf(p, 0.0, 1.0))
	var tier: String = "低"
	if risk >= 0.70:
		tier = "极高"
	elif risk >= 0.40:
		tier = "高"
	elif risk >= 0.15:
		tier = "中"
	return {
		"armed": armed,
		"p_risk": SimMath.quantize(risk),
		"tier_zh": tier,
	}
