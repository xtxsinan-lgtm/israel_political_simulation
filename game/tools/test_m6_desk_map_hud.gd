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
	# G2: approval / readiness / US slots read the real params; G13: inflation red is not sticky.
	var standing: float = state.params.get_val("party_standing", "", state)
	if controller.top_bar.slots[3].text != "支持率 %.1f" % standing:
		return _fail("top bar approval %s" % controller.top_bar.slots[3].text)
	var inflation_before: float = state.params.get_val("inflation", "", state)
	state.params.set_val("inflation", "", 150.0, state)
	controller.top_bar.refresh(state)
	if not controller.top_bar.inflation_alert_active():
		return _fail("inflation alert")
	state.params.set_val("inflation", "", 50.0, state)
	controller.top_bar.refresh(state)
	if controller.top_bar.inflation_alert_active():
		return _fail("inflation alert sticky")
	state.params.set_val("inflation", "", inflation_before, state)
	controller.top_bar.refresh(state)
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
	controller.map_canvas.set_zoom(8.0)
	if controller.map_canvas.zoom > 6.0:
		return _fail("zoom cap")
	controller.map_canvas.set_zoom(0.2)
	if controller.map_canvas.zoom < 0.8:
		return _fail("zoom floor")
	controller.map_canvas.reset_view()
	# Real geography (map_geo.json): multi-ring regions, real site positions, context layer.
	var sinai: RegionPolygonNode = controller.map_canvas.region_nodes["sinai"]
	if sinai.rings.size() < 2 or sinai.fills.is_empty() or sinai.borders.size() != sinai.rings.size():
		return _fail("sinai rings %s" % sinai.rings.size())
	var haifa_pin: Vector2 = controller.map_canvas.pin_position("site_haifa_port_refinery")
	if haifa_pin.distance_to(Vector2(782.01, 149.21)) > 0.01:
		return _fail("pin position %s" % haifa_pin)
	if controller.map_canvas.context_layer == null or controller.map_canvas.context_layer.get_child_count() == 0:
		return _fail("map context")
	if controller.map_canvas.region_labels.size() != 11:
		return _fail("region labels %s" % controller.map_canvas.region_labels.size())
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
	# G9: posture index 2 -> 80; absorption priority is accepted by SimDirector.
	card._on_posture(2)
	if absf(state.params.get_val("region_security_posture", "galilee", state) - 80.0) > 0.001:
		return _fail("posture mapping")
	card._submit("region_absorption_priority", 70.0)
	if absf(state.params.get_val("region_absorption_priority", "galilee", state) - 70.0) > 0.001:
		return _fail("absorption priority")
	# G6: reset keeps the desk offset; zoom keeps the anchor point fixed.
	var map: IsraelMapCanvas = controller.map_canvas
	map.reset_view()
	if map.position != Vector2(240.0, 52.0) or map.scale != Vector2.ONE:
		return _fail("map offset %s" % map.position)
	map.set_zoom(2.0, Vector2(450.0, 125.0))
	if map.to_world(Vector2(450.0, 125.0)).distance_to(Vector2(450.0, 125.0)) > 0.01:
		return _fail("zoom anchor")
	map.reset_view()
	# G5: click hit-test -> region_selected -> inspector; empty map hides it.
	card.close_card()
	if map.click_at(Vector2(828.0, 147.0)) != "galilee" or not card.visible or card.region_id != "galilee":
		return _fail("region click")
	if map.selected_region != "galilee":
		return _fail("region highlight")
	if map.click_at(Vector2(1400.0, 900.0)) != "" or card.visible:
		return _fail("empty click")
	if map.region_at(Vector2(695.0, 363.0)) != "gaza" or map.region_at(Vector2(760.0, 450.0)) != "negev":
		return _fail("region hit-test")
	# Hit-testing goes through the pan/zoom inverse transform.
	map.set_zoom(3.0, Vector2(100.0, 100.0))
	var galilee_screen: Vector2 = map.pan + Vector2(828.0, 147.0) * map.zoom
	if map.region_at(galilee_screen) != "galilee":
		return _fail("zoomed hit-test")
	map.reset_view()
	# Desk props: two-line labels, tooltips, live speed and open-drawer highlight.
	var props: DiegeticDeskPropsController = desk.find_child("DiegeticDeskPropsBar", true, false) as DiegeticDeskPropsController
	if props == null or props.buttons.size() != 7:
		return _fail("desk props")
	if props.buttons[0].text != "红电话\n国防与情报 D7 · Ctrl+7" or props.buttons[0].tooltip_text == "":
		return _fail("desk prop label %s" % props.buttons[0].text)
	props.set_speed_label(3)
	if props.buttons[3].text != "日历\n切换速度（当前 3 倍）":
		return _fail("calendar label %s" % props.buttons[3].text)
	props.set_active_drawer(3)
	if props.active_button_index() != 1:
		return _fail("prop highlight")
	props.set_active_drawer(0)
	if props.active_button_index() != -1:
		return _fail("prop highlight clear")
	# G10: tooltip_requested opens a (scoped) causal tooltip.
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null:
		bus.tooltip_requested.emit("region_security", "galilee")
		if not controller.tooltips.cards.has("region_security[galilee]"):
			return _fail("tooltip_requested")
	print("M6_DESK_MAP_HUD_ALL_PASSED")
	return 0


func _fail(message: String) -> int:
	push_error(message)
	print("M6_FAIL %s" % message)
	return 1
