class_name DeskMainController
extends Control

const VIEW_W: float = 1920.0
const VIEW_H: float = 1080.0
const MAP_X0: float = 240.0
const MAP_X1: float = 1680.0
const MAP_Y0: float = 52.0
const MAP_Y1: float = 994.0

var map_canvas: IsraelMapCanvas
var top_bar: TopBarController
var alerts: AlertOutlinerController
var tooltips: CausalTooltipManager
var inspector: RegionInspectorCard
var drawers: DrawerContainerController
var ledger: LedgerController
var codex: CodexController
var event_modal: EventModalController
var tenure_book: EndTenureBookController
var spotlight: OnboardingDirector


func _ready() -> void:
	_resolve_parts()
	var state: SimState = _director_state()
	if state != null:
		bind_game(state)


func _resolve_parts() -> void:
	var map_node: Node = get_node_or_null("MapDeskLayer/MapArea")
	if map_node is IsraelMapCanvas:
		map_canvas = map_node
	var top_node: Node = get_node_or_null("HUDLayer/TopBar")
	if top_node is TopBarController:
		top_bar = top_node
	var alert_node: Node = get_node_or_null("HUDLayer/AlertOutliner")
	if alert_node is AlertOutlinerController:
		alerts = alert_node
	var tip_node: Node = get_node_or_null("TooltipTutorialLayer/CausalTooltipManager")
	if tip_node is CausalTooltipManager:
		tooltips = tip_node
	var card_node: Node = get_node_or_null("MapDeskLayer/RegionInspectorCard")
	if card_node is RegionInspectorCard:
		inspector = card_node
	var drawer_node: Node = get_node_or_null("DrawerLayer/DrawerContainer")
	if drawer_node is DrawerContainerController:
		drawers = drawer_node
	var ledger_node: Node = get_node_or_null("LedgerCodexLayer/LedgerOverlay")
	if ledger_node is LedgerController:
		ledger = ledger_node
	var codex_node: Node = get_node_or_null("LedgerCodexLayer/CodexOverlay")
	if codex_node is CodexController:
		codex = codex_node
	var event_node: Node = get_node_or_null("ModalLayer/EventModal")
	if event_node is EventModalController:
		event_modal = event_node
	var book_node: Node = get_node_or_null("ModalLayer/EndTenureBookModal")
	if book_node is EndTenureBookController:
		tenure_book = book_node
	var spot_node: Node = get_node_or_null("TooltipTutorialLayer/SpotlightTutorialOverlay")
	if spot_node is OnboardingDirector:
		spotlight = spot_node
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus == null:
		return
	_connect(bus.region_selected, _on_region)
	_connect(bus.sim_day_advanced, _on_day)
	_connect(bus.snapshot_updated, _on_snapshot_updated)
	_connect(bus.event_modal_requested, _on_event_requested)
	_connect(bus.end_tenure_triggered, _on_end_tenure)
	_connect(bus.overlay_toggled, _on_overlay_toggled)
	_connect(bus.drawer_requested, _on_drawer_requested)
	_connect(bus.map_mode_changed, _on_map_mode)
	_connect(bus.pause_state_changed, _on_pause_state)


func _connect(sig: Signal, handler: Callable) -> void:
	if not sig.is_connected(handler):
		sig.connect(handler)


func map_area_ratio() -> float:
	var area: float = (MAP_X1 - MAP_X0) * (MAP_Y1 - MAP_Y0)
	return area / (VIEW_W * VIEW_H)


func layer_order() -> PackedInt32Array:
	var found: PackedInt32Array = PackedInt32Array()
	for child: Node in get_children():
		if child is CanvasLayer:
			found.append((child as CanvasLayer).layer)
	return found


func bind_game(state: SimState) -> void:
	_resolve_parts()
	if map_canvas != null:
		map_canvas.build_from_registry(state)
	if top_bar != null:
		top_bar.refresh(state)
	if alerts != null:
		alerts.refresh(state)


## Re-reads the live game into the map, alerts and top bar.
func refresh_views(state: SimState) -> void:
	if state == null:
		return
	if top_bar != null:
		top_bar.refresh(state)
	if map_canvas != null:
		if map_canvas.bound_state != state:
			map_canvas.build_from_registry(state)
		else:
			map_canvas.set_map_layer(map_canvas.layer_index)
	if alerts != null:
		alerts.refresh(state)
	if ledger != null and ledger.visible:
		ledger.refresh_from_snapshot(_engine_snapshot())


func _on_region(region_id: String) -> void:
	if inspector == null:
		return
	inspector.present(region_id, _director_state())


func _director_state() -> SimState:
	var engine: Node = _engine()
	if engine == null:
		return null
	var director: Variant = engine.get("director")
	if director is SimDirector:
		return (director as SimDirector).state
	return null


func _engine() -> Node:
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree) or not (loop as SceneTree).root.has_node("SimEngine"):
		return null
	return (loop as SceneTree).root.get_node("SimEngine")


func _engine_snapshot() -> SimReadonlySnapshot:
	var engine: Node = _engine()
	if engine == null:
		return null
	var snap: Variant = engine.call("get_snapshot")
	if snap is SimReadonlySnapshot:
		return snap
	return null


func _on_day(snapshot: SimReadonlySnapshot) -> void:
	if snapshot == null or snapshot.day_index < 0:
		return
	refresh_views(_director_state())


func _on_snapshot_updated(_snapshot: Variant) -> void:
	refresh_views(_director_state())


func _on_pause_state(_is_paused: bool, _speed_level: int, _pause_reasons: PackedStringArray) -> void:
	var state: SimState = _director_state()
	if top_bar != null and state != null:
		top_bar.refresh(state)


func _on_event_requested(event_data: Dictionary) -> void:
	var state: SimState = _director_state()
	if event_modal == null or state == null:
		return
	event_modal.present(event_data, state)
	event_modal.visible = true


func _on_end_tenure(_eval_data: Dictionary) -> void:
	var state: SimState = _director_state()
	if tenure_book == null or state == null:
		return
	if event_modal != null:
		event_modal.visible = false
	tenure_book.present(state)
	tenure_book.visible = true


func _on_overlay_toggled(overlay_id: String, is_open: bool) -> void:
	if overlay_id == "ledger" and ledger != null:
		ledger.visible = is_open
		if is_open:
			ledger.refresh_from_snapshot(_engine_snapshot())
	elif overlay_id == "codex" and codex != null:
		codex.visible = is_open


func _on_drawer_requested(drawer_id: String, _subtab_index: int, _highlight_node_name: String) -> void:
	if drawers == null or not drawer_id.begins_with("D"):
		return
	var target: int = clampi(int(drawer_id.substr(1)), 0, 7)
	if target == 0:
		if drawers.open_index != 0:
			drawers.toggle_drawer(drawers.open_index)
	elif drawers.open_index != target:
		drawers.toggle_drawer(target)


func _on_map_mode(map_layer_id: String) -> void:
	if map_canvas == null or not map_layer_id.begins_with("F"):
		return
	map_canvas.set_map_layer(int(map_layer_id.substr(1)))
