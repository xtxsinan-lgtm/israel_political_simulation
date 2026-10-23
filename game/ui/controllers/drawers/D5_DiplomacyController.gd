class_name D5DiplomacyController
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
	summary.text = "白宫 %.0f  国会 %.0f\n苏联配额 / 埃塞俄比亚 / 欧美 / 中东\n埃及 约旦 叙利亚 黎巴嫩" % [
		state.params.get_val("us_admin_relation", "", state),
		state.params.get_val("us_congress_relation", "", state),
	]
