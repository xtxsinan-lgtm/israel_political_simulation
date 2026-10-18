extends Node

signal snapshot_updated(snapshot: Variant)
signal day_advanced(day_index: int, date_str: String, is_week: bool, is_month: bool, is_quarter: bool, is_year: bool)
signal pause_state_changed(is_paused: bool, speed_level: int, pause_reasons: PackedStringArray)
signal event_modal_enqueued(event_payload: Dictionary)
signal drawer_requested(drawer_id: String, subtab_index: int, highlight_node_name: String)
signal map_mode_changed(map_layer_id: String)
