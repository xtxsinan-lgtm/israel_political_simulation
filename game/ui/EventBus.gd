class_name DeskEventBus
extends Node

signal sim_day_advanced(snapshot: SimReadonlySnapshot)
signal sim_speed_changed(new_speed: int)
signal sim_auto_paused(reason: String)
signal event_modal_requested(event_data: Dictionary)
signal summit_modal_requested(summit_data: Dictionary)
signal election_modal_requested(election_data: Dictionary)
signal end_tenure_triggered(eval_data: Dictionary)
signal achievement_unlocked(ach_id: String)
signal drawer_toggled(drawer_index: int)
signal map_layer_changed(layer_index: int)
signal region_selected(region_id: String)
signal tooltip_lock_toggled(tooltip_id: String, locked: bool)
signal codex_entry_requested(entry_id: String)
signal era_skin_changed(era_id: String)
signal overlay_toggled(overlay_id: String, is_open: bool)

signal snapshot_updated(snapshot: Variant)
signal day_advanced(day_index: int, date_str: String, is_week: bool, is_month: bool, is_quarter: bool, is_year: bool)
signal pause_state_changed(is_paused: bool, speed_level: int, pause_reasons: PackedStringArray)
signal event_modal_enqueued(event_payload: Dictionary)
signal drawer_requested(drawer_id: String, subtab_index: int, highlight_node_name: String)
signal map_mode_changed(map_layer_id: String)


static func hub() -> DeskEventBus:
	var loop: MainLoop = Engine.get_main_loop()
	if loop is SceneTree and (loop as SceneTree).root.has_node("EventBus"):
		return (loop as SceneTree).root.get_node("EventBus") as DeskEventBus
	return null
