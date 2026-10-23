/* Port of game/ui/EventBus.gd (DeskEventBus autoload): named signals with connect/emit. */
export class EventBus {
  constructor() { this.handlers = new Map(); }

  connect(signal, fn) {
    if (!this.handlers.has(signal)) this.handlers.set(signal, new Set());
    this.handlers.get(signal).add(fn);
    return () => this.handlers.get(signal)?.delete(fn);
  }

  emit(signal, ...args) {
    for (const fn of [...(this.handlers.get(signal) || [])]) {
      try { fn(...args); } catch (err) { console.error(`[EventBus] ${signal}`, err); }
    }
  }
}

/* Signals used by the desk (same names as game/ui/EventBus.gd). */
export const SIGNALS = [
  "sim_day_advanced", "snapshot_updated", "day_advanced", "pause_state_changed", "sim_speed_changed",
  "sim_auto_paused", "event_modal_requested", "end_tenure_triggered", "drawer_requested", "drawer_toggled",
  "map_mode_changed", "map_layer_changed", "overlay_toggled", "region_selected", "codex_entry_requested",
  "tooltip_lock_toggled", "tooltip_requested",
];
