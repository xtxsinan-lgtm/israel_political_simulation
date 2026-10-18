class_name SimMath
extends RefCounted

const QUANT_SCALE: float = 1000000.0
const INV_QUANT_SCALE: float = 1.0 / 1000000.0


static func quantize(x: float) -> float:
	if is_nan(x) or is_inf(x):
		return 0.0
	return floor(x * QUANT_SCALE + 0.5) * INV_QUANT_SCALE


static func to_canonical_int(x: Variant) -> int:
	if x == null:
		return 0
	var f: float = float(x)
	if is_nan(f) or is_inf(f):
		return 0
	return int(floor(f * QUANT_SCALE + 0.5))


static func round_half_up_int(x: float) -> int:
	return int(floor(x + 0.5))


static func idiv_floor(a: int, b: int) -> int:
	if b == 0:
		return 0
	return int(floor(float(a) / float(b)))


static func imod_pos(a: int, b: int) -> int:
	return posmod(a, b)


static func ipow(base: float, exp_n: int) -> float:
	if exp_n <= 0:
		return 1.0
	var result: float = 1.0
	for _i: int in range(exp_n):
		result *= base
	return result


static func sorted_keys(d: Dictionary) -> Array[String]:
	var raw: Array = d.keys()
	var k_list: Array[String] = []
	k_list.resize(raw.size())
	for i: int in range(raw.size()):
		k_list[i] = String(raw[i])
	k_list.sort()
	return k_list


static func piecewise_linear(x: float, xs: PackedFloat64Array, ys: PackedFloat64Array) -> float:
	var n: int = xs.size()
	if n == 0 or ys.size() == 0:
		return 0.0
	if x <= xs[0]:
		return ys[0]
	if x >= xs[n - 1]:
		return ys[n - 1]
	for i: int in range(n - 1):
		if x >= xs[i] and x <= xs[i + 1]:
			var span: float = xs[i + 1] - xs[i]
			if absf(span) < 1.0e-12:
				return ys[i]
			var t: float = (x - xs[i]) / span
			return ys[i] + t * (ys[i + 1] - ys[i])
	return ys[n - 1]


static func soft_clamp(x: float, lo: float, hi: float, margin: float = 5.0) -> float:
	var w: float = margin
	if w <= 1.0e-9:
		w = 13.0
	if x < lo:
		return lo - w * tanh((lo - x) / w)
	if x > hi:
		return hi + w * tanh((x - hi) / w)
	return x
