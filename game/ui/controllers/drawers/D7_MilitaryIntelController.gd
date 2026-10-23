class_name D7MilitaryIntelController
extends Control

var mobilization_level: int = 0
var front_status: Dictionary = {}
var nuclear_ambiguity: String = "opaque"
var intel_quality: float = 0.0
var summary: Label


func _ready() -> void:
	if summary != null:
		return
	summary = Label.new()
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	var material: ShaderMaterial = ShaderMaterial.new()
	material.shader = load("res://ui/shaders/crt_scanline.gdshader")
	summary.material = material
	add_child(summary)
	# Span the drawer width so the autowrapped text does not collapse to one glyph per line.
	summary.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)


func refresh(state: SimState) -> void:
	if summary == null:
		_ready()
	mobilization_level = SimMath.round_half_up_int(state.params.get_val("mobilization", "", state))
	intel_quality = state.params.get_val("intel_accuracy", "", state)
	nuclear_ambiguity = "opaque"
	var m09: Dictionary = _dict(state.modules.get("M09", {}))
	var fronts: Dictionary = _dict(m09.get("fronts", {}))
	var ids: Array[String] = SimMath.sorted_keys(fronts)
	front_status.clear()
	for i: int in range(ids.size()):
		front_status[ids[i]] = String(_dict(fronts[ids[i]]).get("status", "PEACE"))
	summary.text = "动员 %d  情报 %.1f  核模糊 %s  战线 %d" % [
		mobilization_level, intel_quality, nuclear_ambiguity, front_status.size(),
	]


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
