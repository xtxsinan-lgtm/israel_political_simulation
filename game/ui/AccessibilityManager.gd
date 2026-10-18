extends Node

const SCALE_STEPS: Array[float] = [0.90, 1.0, 1.10, 1.25, 1.40]
const MIN_FONT_PX: int = 12

var scale_index: int = 1
var palette: String = "standard"
var reduce_motion: bool = false


func font_px(base_px: int) -> int:
	var scaled: float = float(base_px) * SCALE_STEPS[scale_index]
	var rounded: int = SimMath.round_half_up_int(scaled)
	return maxi(MIN_FONT_PX, rounded)


func set_palette(next: String) -> void:
	if next == "Deuteranopia" or next == "standard" or next == "monochrome":
		palette = next
	else:
		palette = "standard"


func set_scale_index(index: int) -> void:
	scale_index = clampi(index, 0, SCALE_STEPS.size() - 1)
