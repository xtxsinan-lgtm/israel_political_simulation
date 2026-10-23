class_name D1GoalsController
extends Control

var summary: Label


func _ready() -> void:
	if summary != null:
		return
	summary = Label.new()
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(summary)
	# Span the drawer width so the autowrapped text does not collapse to one glyph per line.
	summary.set_anchors_and_offsets_preset(Control.PRESET_TOP_WIDE)


func refresh(state: SimState) -> void:
	if summary == null:
		_ready()
	var vision: float = state.params.get_val("vision_progress", "", state)
	var national_vision: String = "完整以色列地" if vision < 80.0 else "愿景里程碑"
	var trilemma: String = "犹太 %.0f / 民主 %.0f / 领土 %.0f" % [
		state.params.get_val("trilemma_jewish", "", state),
		state.params.get_val("trilemma_democratic", "", state),
		state.params.get_val("trilemma_territory", "", state),
	]
	var m13: Dictionary = _dict(state.modules.get("M13", {}))
	var centralization_stage: String = String(m13.get("centralization_stage", "C1"))
	var social_protest_tier: int = int(m13.get("protest_tier", m13.get("social_protest_tier", 0)))
	summary.text = "%s 进度 %.0f%%（80%% 终局 +8）\n不可能三角 %s\n集权 %s 抗议 %d" % [
		national_vision, vision, trilemma, centralization_stage, social_protest_tier,
	]


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
