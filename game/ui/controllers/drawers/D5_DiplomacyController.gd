class_name D5DiplomacyController
extends Control

var summary: Label


func _ready() -> void:
	if summary != null:
		return
	summary = Label.new()
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(summary)


func refresh(state: SimState) -> void:
	if summary == null:
		_ready()
	summary.text = "白宫 %.0f  国会 %.0f\n苏联配额 / 埃塞俄比亚 / 欧美 / 中东\n埃及 约旦 叙利亚 黎巴嫩" % [
		state.params.get_val("us_wh_warmth", "", state),
		state.params.get_val("us_cong_support", "", state),
	]
