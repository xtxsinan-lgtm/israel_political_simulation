extends SceneTree


func _initialize() -> void:
	quit(_run())


func _run() -> int:
	var registry: GameData = GameData.new()
	if registry.load_all_runtime_data() != OK:
		return _fail("load")
	var state: SimState = SimState.new()
	state.init_from_scenario_bundle("begin_1977", 19770620, false)
	var drawer: DrawerContainerController = DrawerContainerController.new()
	root.add_child(drawer)
	drawer._ready()
	drawer.toggle_drawer(1)
	drawer.toggle_drawer(2)
	if drawer.visible_drawers_count() != 1 or drawer.open_index != 2:
		return _fail("exclusive")
	if drawer.mouse_filter != Control.MOUSE_FILTER_IGNORE:
		return _fail("drawer container blocks the map")
	if not (drawer.drawer_node(2) is D2KnessetController) or not drawer.drawer_node(2).visible:
		return _fail("drawer scene not instanced")
	if drawer.drawer_node(1) == null or drawer.drawer_node(1).visible:
		return _fail("previous drawer still shown")
	if drawer.panel.position.y < 25.0 or absf(drawer.panel.position.y + drawer.panel.size.y - 800.0) > 0.5:
		return _fail("drawer panel overlaps tabs %s" % drawer.panel.position)
	drawer.toggle_drawer(2)
	if drawer.visible_drawers_count() != 0:
		return _fail("close")
	var goals: D1GoalsController = D1GoalsController.new()
	goals.refresh(state)
	if goals.summary.text == "":
		return _fail("d1")
	var knesset: D2KnessetController = D2KnessetController.new()
	knesset.refresh(state)
	if knesset.seat_total() != 120:
		return _fail("seats %s" % knesset.seat_total())
	if knesset.coalition.is_empty() or knesset.dot_colors.size() != knesset.seat_total():
		return _fail("d2 coalition colours")
	var cabinet: D3CabinetController = D3CabinetController.new()
	cabinet.refresh(state)
	if cabinet.action_buttons.size() != GameData.current.actions_def.size() or cabinet.available_action_count() <= 0:
		return _fail("d3 actions %d" % cabinet.action_buttons.size())
	cabinet.execute_action(state, "inspect_budget")
	var economy: D4EconomyController = D4EconomyController.new()
	economy.refresh(state)
	if economy.graph.nodes.is_empty():
		return _fail("graph")
	if economy.graph.edges.is_empty() or economy.graph.nodes.has("param:inflation"):
		return _fail("graph edges")
	for edge: Dictionary in economy.graph.edges:
		if String(edge.get("src", "")) != "inflation" and String(edge.get("dst", "")) != "inflation":
			return _fail("graph edge off focus")
	if economy.graph.node_position(5) != Vector2(240.0, 180.0):
		return _fail("graph grid %s" % economy.graph.node_position(5))
	var pal: D6PalestiniansController = D6PalestiniansController.new()
	pal.refresh(state)
	if absf(pal.legitimacy_sum() - 100.0) > 0.02:
		return _fail("legitimacy %s" % pal.legitimacy_sum())
	if not pal.summary.text.contains("mujama"):
		return _fail("factions")
	if pal.summary.text.contains("%.1f" % float(pal.pal_legitimacy["mujama"])):
		return _fail("d6 leaks raw legitimacy")
	var ledger: LedgerController = LedgerController.new()
	ledger.set_hidden_rows([
		{"id": "b", "param_id": "coup_risk", "hidden": 12.5},
		{"id": "a", "param_id": "coup_risk", "hidden": 11.25},
		{"id": "c", "param_id": "coup_risk", "hidden": 91.75},
	])
	if String(ledger.rows[0].get("id", "")) != "a" or String(ledger.rows[2].get("id", "")) != "c":
		return _fail("fuzzy order")
	if ledger.display_hidden(ledger.rows[0]) != "轻微 (0%–20%)":
		return _fail("fuzzy badge %s" % ledger.display_hidden(ledger.rows[0]))
	if ledger.display_hidden(ledger.rows[2]) != "严峻 (80%–100%)":
		return _fail("fuzzy badge high %s" % ledger.display_hidden(ledger.rows[2]))
	for row: Dictionary in ledger.rows:
		if row.has("hidden"):
			return _fail("ledger keeps raw hidden")
		for key: Variant in row.keys():
			if typeof(row[key]) == TYPE_FLOAT:
				return _fail("ledger row has raw float %s" % String(key))
			var cell_text: String = str(row[key])
			if cell_text.contains("12.5") or cell_text.contains("11.25") or cell_text.contains("91.75"):
				return _fail("ledger leaks raw value in %s" % String(key))
	if FuzzyBand.band_index(19.99) != 0 or FuzzyBand.band_index(20.0) != 1 or FuzzyBand.band_index(100.0) != 4:
		return _fail("band edges")
	if not FuzzyBand.is_fuzzy("uprising_risk") or FuzzyBand.is_fuzzy("inflation"):
		return _fail("is_fuzzy")
	var linked: String = CodexAutoLinker.new().inject_codex_links("大转折改写了议会。")
	if not linked.contains("codex://mahapach"):
		return _fail("codex")
	var modal: EventModalController = EventModalController.new()
	modal.present({"id": "E-1977-06", "modal_class": "crisis", "title": "就职", "summary": "大转折"}, state)
	if modal.modal_class != "crisis":
		return _fail("modal")
	modal.present({"id": "E-1948-01", "modal_class": "major", "title": "建国与入侵"}, state)
	if modal.body.text.contains(EventModalController.DEFAULT_BODY):
		return _fail("event body falls back to default")
	var book: EndTenureBookController = EndTenureBookController.new()
	book.present(state)
	if book.chapters.size() != 5:
		return _fail("chapters")
	var first_page: String = book.page.text.get_slice("\n", 0)
	book.next_page()
	if book.chapter_index != 1 or book.page.text.get_slice("\n", 0) != first_page:
		return _fail("book page turn lost grade")
	var summit: SummitNegotiationView = SummitNegotiationView.new()
	summit._ready()
	if float(summit.acceptance(20.0).get("egypt", 0.0)) <= 0.0:
		return _fail("summit")
	print("M7_DRAWERS_ALL_PASSED")
	return 0


func _fail(message: String) -> int:
	push_error(message)
	print("M7_FAIL %s" % message)
	return 1
