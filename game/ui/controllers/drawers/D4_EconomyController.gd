class_name D4EconomyController
extends Control

var sliders: PackedStringArray = PackedStringArray([
	"defense", "welfare", "infrastructure", "education", "religion", "settlements", "absorption", "tax",
])

var graph: CausalGraphCanvas
var summary: Label
var shares: Dictionary = {}


func _ready() -> void:
	if summary != null:
		return
	# Text on top, the 1-hop causal graph below it (not overlapping at (0,0)).
	var layout: VBoxContainer = VBoxContainer.new()
	add_child(layout)
	layout.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	summary = Label.new()
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	layout.add_child(summary)
	graph = CausalGraphCanvas.new()
	graph.custom_minimum_size = Vector2(640, 340)
	layout.add_child(graph)


func refresh(state: SimState) -> void:
	if summary == null:
		_ready()
	var lines: PackedStringArray = PackedStringArray()
	for i: int in range(sliders.size()):
		var key: String = sliders[i]
		shares[key] = 12.5
		lines.append("%s %.1f" % [key, shares[key]])
	var one_off: float = state.params.get_val("budget_balance", "", state)
	lines.append("一次性收支 %.2f" % one_off)
	lines.append("预算截止倒计时 90 天")
	summary.text = "\n".join(lines)
	graph.focus_node("inflation", state)
