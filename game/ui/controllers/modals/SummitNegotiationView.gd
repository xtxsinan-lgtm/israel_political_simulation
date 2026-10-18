class_name SummitNegotiationView
extends Control

var issues: PackedStringArray = PackedStringArray([
	"西奈撤军", "定居点", "巴勒斯坦自治", "关系正常化",
])

var concessions: Dictionary = {}
var summary: Label


func _ready() -> void:
	summary = Label.new()
	add_child(summary)
	for i: int in range(issues.size()):
		concessions[issues[i]] = 1


func acceptance(right_wing_risk: float) -> Dictionary:
	var score: float = 0.0
	var ids: Array = concessions.keys()
	for i: int in range(ids.size()):
		score += float(concessions[ids[i]])
	return {
		"egypt": clampf(score * 20.0, 0.0, 100.0),
		"israel": clampf(100.0 - right_wing_risk, 0.0, 100.0),
		"us": clampf(50.0 + score * 5.0, 0.0, 100.0),
		"ally_exit_risk": right_wing_risk,
	}
