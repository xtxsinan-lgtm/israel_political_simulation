class_name D3CabinetController
extends Control

var summary: Label
var minister_proposals: Array[Dictionary] = []
var active_policies: Array[String] = []


func _ready() -> void:
	if summary != null:
		return
	summary = Label.new()
	summary.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	add_child(summary)


func refresh(state: SimState) -> void:
	if summary == null:
		_ready()
	minister_proposals.clear()
	active_policies.clear()
	var offices: Dictionary = _dict(_dict(state.modules.get("M06", {})).get("offices", {}))
	if offices.is_empty():
		offices = state.offices
	var ids: Array[String] = SimMath.sorted_keys(offices)
	for i: int in range(mini(6, ids.size())):
		minister_proposals.append({
			"office": ids[i],
			"holder": String(offices[ids[i]]),
			"discount": 0.30,
		})
	if GameData.current != null:
		var policies: Array[String] = SimMath.sorted_keys(GameData.current.policies_def)
		for i: int in range(mini(76, policies.size())):
			active_policies.append(policies[i])
	summary.text = "部长提案 %d（批准可享 30%% 政治资本折扣）\n政策 %d" % [minister_proposals.size(), active_policies.size()]


func execute_action(state: SimState, action_id: String) -> void:
	var loop: MainLoop = Engine.get_main_loop()
	var cmd: Dictionary = {"op": "execute_action", "action": action_id}
	if loop is SceneTree and (loop as SceneTree).root.has_node("SimEngine"):
		(loop as SceneTree).root.get_node("SimEngine").call("submit_command", cmd)
	else:
		var queue: Array = []
		var m05: Dictionary = _dict(state.modules.get("M05", {}))
		if typeof(m05.get("action_queue", [])) == TYPE_ARRAY:
			queue = m05["action_queue"]
		queue.append({"id": action_id, "days_left": 7})
		m05["action_queue"] = queue
		state.modules["M05"] = m05


func _dict(value: Variant) -> Dictionary:
	if typeof(value) == TYPE_DICTIONARY:
		return value
	return {}
