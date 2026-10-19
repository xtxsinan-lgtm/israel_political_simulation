extends SceneTree


func _initialize() -> void:
	quit(_run())


func _run() -> int:
	var packed: PackedScene = load("res://ui/scenes/DeskMain.tscn")
	if packed == null:
		return _fail("desk scene")
	var desk: Node = packed.instantiate()
	root.add_child(desk)
	var controller: DeskMainController = desk as DeskMainController
	if controller == null:
		return _fail("controller")
	var layers: PackedInt32Array = controller.layer_order()
	var expect: PackedInt32Array = PackedInt32Array([0, 10, 20, 30, 40, 50])
	if layers != expect:
		return _fail("layers %s" % layers)
	if controller.map_area_ratio() < 0.60:
		return _fail("map ratio %s" % controller.map_area_ratio())
	var registry: GameData = GameData.new()
	if registry.load_all_runtime_data() != OK:
		return _fail("load")
	var started: int = int(root.get_node("SimEngine").call("start_new_game", "begin_1977", 19770620, false))
	if started != OK:
		return _fail("start")
	var director: Variant = root.get_node("SimEngine").get("director")
	if not (director is SimDirector) or (director as SimDirector).state == null:
		return _fail("director")
	var state: SimState = (director as SimDirector).state
	controller.bind_game(state)
	if controller.top_bar == null or not controller.top_bar.texts_filled():
		return _fail("top bar")
	if controller.map_canvas == null:
		return _fail("map")
	if controller.map_canvas.region_nodes.size() != 11:
		return _fail("regions %s" % controller.map_canvas.region_nodes.size())
	var lebanon: RegionPolygonNode = controller.map_canvas.region_nodes["south_lebanon"]
	if lebanon.visible:
		return _fail("south_lebanon visible")
	if controller.map_canvas.visible_region_count() != 10:
		return _fail("visible %s" % controller.map_canvas.visible_region_count())
	if controller.map_canvas.pin_nodes.size() < 25:
		return _fail("pins %s" % controller.map_canvas.pin_nodes.size())
	for layer: int in range(1, 8):
		controller.map_canvas.set_map_layer(layer)
	if controller.map_canvas.layer_index != 7:
		return _fail("F7")
	controller.map_canvas.set_zoom(4.0)
	if controller.map_canvas.zoom > 3.0:
		return _fail("zoom cap")
	if controller.tooltips == null:
		return _fail("tooltips")
	if not controller.tooltips.lock_tooltip("inflation"):
		return _fail("lock 1")
	controller.tooltips.lock_tooltip("security")
	controller.tooltips.lock_tooltip("seats")
	if controller.tooltips.lock_tooltip("fourth"):
		return _fail("lock cap")
	if controller.tooltips.locked.size() != 3:
		return _fail("stack")
	controller.tooltips.handle_escape()
	controller.tooltips.handle_escape()
	controller.tooltips.handle_escape()
	if not controller.tooltips.locked.is_empty():
		return _fail("escape stack")
	var explained: Dictionary = controller.tooltips.explain_node(state, "inflation")
	if not explained.has("top_contributions"):
		return _fail("explain")
	var coup_raw: float = state.params.get_val("coup_risk", "", state)
	controller.tooltips.explain_node(state, "coup_risk")
	if controller.tooltips.body.text.contains("%.2f" % coup_raw) or not controller.tooltips.body.text.contains("%)"):
		return _fail("fuzzy tooltip leak %s" % controller.tooltips.body.text)
	var card: RegionInspectorCard = controller.inspector
	card.present("galilee", state)
	card._submit("region_investment_priority", 40.0)
	if absf(state.params.get_val("region_investment_priority", "galilee", state) - 40.0) > 0.001:
		return _fail("priority")
	print("M6_DESK_MAP_HUD_ALL_PASSED")
	return 0


func _fail(message: String) -> int:
	push_error(message)
	print("M6_FAIL %s" % message)
	return 1
