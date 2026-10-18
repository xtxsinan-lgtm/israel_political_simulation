class_name CausalShapes
extends RefCounted


static func eval_shape(x: float, edge: Dictionary) -> float:
	var shape: String = String(edge.get("shape", "linear"))
	if shape == "linear" or shape == "":
		return float(edge.get("coef", edge.get("w", 1.0))) * (x - float(edge.get("pivot", edge.get("ref", 0.0))))
	var pivot: float = float(edge.get("pivot", edge.get("ref", 0.0)))
	var coef: float = float(edge.get("coef", edge.get("w", 1.0)))
	var width: float = float(edge.get("w", edge.get("scale", 20.0)))
	if absf(width) < 1.0e-9:
		width = 20.0
	var lo: float = float(edge.get("lo", 0.0))
	var hi: float = float(edge.get("hi", 100.0))
	var d: float = x - pivot
	match shape:
		"linear":
			return coef * d
		"threshold":
			var below: bool = String(edge.get("direction", "above")) == "below"
			if below:
				return coef * (pivot - x) if x < pivot else 0.0
			return coef * d if x > pivot else 0.0
		"above", "pos_excess":
			return coef * maxf(0.0, d)
		"below", "neg_excess":
			return coef * maxf(0.0, -d)
		"step":
			if String(edge.get("direction", "above")) == "below":
				return coef if x < pivot else 0.0
			return coef if x >= pivot else 0.0
		"flag":
			return coef if x >= 0.5 else 0.0
		"piecewise":
			return coef * _piecewise(x, edge)
		"quadratic", "quad":
			return coef * d * absf(d) / width
		"saturating":
			var half_sat: float = float(edge.get("half_sat", width))
			var max_val: float = float(edge.get("max_val", coef))
			return max_val * d / (absf(d) + half_sat)
		"sat", "sigmoid":
			return coef * width * tanh(d / width)
		"band", "band_outside":
			if x >= lo and x <= hi:
				return 0.0
			if x < lo:
				return float(edge.get("coef_lo", coef)) * (lo - x)
			return float(edge.get("coef_hi", coef)) * (x - hi)
		"diminishing":
			var gain: float = float(edge.get("gain", coef))
			return gain * d / (1.0 + absf(d) / width)
		"product":
			var other: float = float(edge.get("other", 0.0))
			return coef * (x - pivot) * (other - float(edge.get("other_ref", 0.0)))
		"habit":
			return 0.0
		_:
			return 0.0
	return 0.0


static func read_source_effective_val(state: SimState, edge: Dictionary, scope_key: String) -> float:
	var source: String = String(edge.get("source", edge.get("source_param", "")))
	var param_id: String = source
	if source.begins_with("param:"):
		param_id = source.substr(6)
	var key: String = scope_key
	if edge.get("source_key", null) != null:
		key = String(edge.get("source_key", ""))
	if not edge.has("lag_months") and not edge.has("delay") and not edge.has("smooth_months"):
		return state.params.get_val(param_id, key, state)
	var lag: int = int(edge.get("lag_months", edge.get("delay", 0)))
	var smooth: int = int(edge.get("smooth_months", 0))
	if lag <= 0 and smooth <= 0:
		return state.params.get_val(param_id, key, state)
	var hist: Array = _history(state, param_id, key)
	if smooth > 0:
		var total: float = 0.0
		var count: int = 0
		var start: int = maxi(0, hist.size() - smooth)
		for i: int in range(start, hist.size()):
			total += float(hist[i])
			count += 1
		if count == 0:
			return state.params.get_val(param_id, key, state)
		return total / float(count)
	var index: int = hist.size() - 1 - lag
	if index < 0 or index >= hist.size():
		return state.params.get_val(param_id, key, state)
	return float(hist[index])


static func _piecewise(x: float, edge: Dictionary) -> float:
	var points: Array = []
	var raw: Variant = edge.get("points", [])
	if typeof(raw) == TYPE_ARRAY:
		points = raw
	if points.size() < 2:
		return x
	var prev_x: float = float(_as_array(points[0])[0]) if typeof(points[0]) == TYPE_ARRAY else 0.0
	var prev_y: float = float(_as_array(points[0])[1]) if typeof(points[0]) == TYPE_ARRAY else 0.0
	if x <= prev_x:
		return prev_y
	for i: int in range(1, points.size()):
		var pair: Array = _as_array(points[i])
		if pair.size() < 2:
			continue
		var next_x: float = float(pair[0])
		var next_y: float = float(pair[1])
		if x <= next_x:
			var span: float = next_x - prev_x
			if absf(span) < 1.0e-9:
				return next_y
			var t: float = (x - prev_x) / span
			return prev_y + t * (next_y - prev_y)
		prev_x = next_x
		prev_y = next_y
	return prev_y


static func _history(state: SimState, param_id: String, key: String) -> Array:
	var m02: Dictionary = {}
	if typeof(state.modules.get("M02", {})) == TYPE_DICTIONARY:
		m02 = state.modules["M02"]
	var hist: Dictionary = {}
	if typeof(m02.get("hist", {})) == TYPE_DICTIONARY:
		hist = m02["hist"]
	var node_key: String = param_id if key == "" else "%s[%s]" % [param_id, key]
	var series: Variant = hist.get(node_key, [])
	if typeof(series) == TYPE_ARRAY:
		return series
	return []


static func _as_array(value: Variant) -> Array:
	if typeof(value) == TYPE_ARRAY:
		return value
	return []
