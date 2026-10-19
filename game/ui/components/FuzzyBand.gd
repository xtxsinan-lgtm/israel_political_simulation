class_name FuzzyBand
extends RefCounted

## Single UI-side helper for fog-of-war rendering (D-088, iron rule 9).
## A `visible: fuzzy` value is shown only as one of five qualitative Chinese words
## plus a coarse estimate range, e.g. `严峻 (80%–100%)`. Band edges come from
## SimReadonlySnapshot so the sim and UI agree on the same five bands.

const BAND_COUNT: int = SimReadonlySnapshot.FUZZY_BAND_COUNT
const UNKNOWN_TEXT: String = "情报不足"


static func band_index(value: float) -> int:
	return SimReadonlySnapshot.band_of(value)


static func is_fuzzy(param_id: String) -> bool:
	return SimReadonlySnapshot.is_fuzzy_param(param_id)


static func band_low(band: int) -> int:
	return clampi(band, 0, BAND_COUNT - 1) * int(SimReadonlySnapshot.FUZZY_BAND_WIDTH)


static func band_high(band: int) -> int:
	return band_low(band) + int(SimReadonlySnapshot.FUZZY_BAND_WIDTH)


## Integer centre of a band (10, 30, 50, 70, 90); used for sorting, never a raw value.
static func band_centre(band: int) -> int:
	var half: int = SimMath.idiv_floor(int(SimReadonlySnapshot.FUZZY_BAND_WIDTH), 2)
	return band_low(band) + half


static func band_word(band: int, param_id: String = "") -> String:
	var b: int = clampi(band, 0, BAND_COUNT - 1)
	if _is_risk_like(param_id):
		match b:
			0:
				return "轻微"
			1:
				return "可控"
			2:
				return "值得警惕"
			3:
				return "高企"
			_:
				return "严峻"
	if param_id == "health":
		match b:
			0:
				return "垂危"
			1:
				return "欠佳"
			2:
				return "一般"
			3:
				return "良好"
			_:
				return "硬朗"
	match b:
		0:
			return "极弱"
		1:
			return "偏弱"
		2:
			return "中等"
		3:
			return "偏强"
		_:
			return "极强"


static func range_text(band: int) -> String:
	return "%d%%–%d%%" % [band_low(band), band_high(band)]


## `word (lo%–hi%)` for an already-banded value.
static func describe_band(band: int, param_id: String = "") -> String:
	if band < 0:
		return UNKNOWN_TEXT
	return "%s (%s)" % [band_word(band, param_id), range_text(band)]


## `word (lo%–hi%)` for a raw 0..100 value. The raw value never appears in the output.
static func describe(value: float, param_id: String = "") -> String:
	return describe_band(band_index(value), param_id)


## Renders any parameter value: fuzzy params as a band, others with `fmt`.
static func display(param_id: String, value: float, fmt: String = "%.1f") -> String:
	if is_fuzzy(param_id):
		return describe(value, param_id)
	return fmt % value


static func _is_risk_like(param_id: String) -> bool:
	if param_id == "":
		return true
	for needle: String in ["risk", "probability", "readiness", "progress", "complacency", "exposure"]:
		if param_id.contains(needle):
			return true
	return false
