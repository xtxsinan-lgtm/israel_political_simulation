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


func _ready() -> void:
	_resolve_parts()


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
	var bus: DeskEventBus = DeskEventBus.hub()
	if bus != null and not bus.region_selected.is_connected(_on_region):
		bus.region_selected.connect(_on_region)
		bus.sim_day_advanced.connect(_on_day)


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


func _on_region(region_id: String) -> void:
	if inspector == null:
		return
	inspector.present(region_id, _director_state())


func _director_state() -> SimState:
	var loop: MainLoop = Engine.get_main_loop()
	if not (loop is SceneTree) or not (loop as SceneTree).root.has_node("SimEngine"):
		return null
	var director: Variant = (loop as SceneTree).root.get_node("SimEngine").get("director")
	if director is SimDirector:
		return (director as SimDirector).state
	return null


func _on_day(snapshot: SimReadonlySnapshot) -> void:
	if top_bar != null and top_bar.bound_state != null:
		top_bar.refresh(top_bar.bound_state)
	if snapshot.day_index < 0:
		return
