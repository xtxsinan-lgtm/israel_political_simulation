/* Port of game/autoload/SimEngine.gd: real-time day tick, pause/speed, auto-pause,
 * snapshot publishing on the EventBus, quick save/load. The simulation itself runs in the
 * Pyodide worker (web/py/bridge.py), so stepping is asynchronous: at most one step request
 * is in flight and each request advances up to MAX_DAYS_PER_FRAME days. */
import { StateView, allReads } from "./StateView.js";

export const MIN_SPEED = 1;
export const MAX_SPEED = 5;
export const MAX_DAYS_PER_FRAME = 4;
const QUICKSAVE_KEY = "quicksave.ipsave.json";

/** Seconds of real time per simulated day for speed levels 1..5. */
export function secondsPerDay(level) {
  return [2.0, 1.0, 0.5, 0.25, 0.1][Math.min(MAX_SPEED, Math.max(MIN_SPEED, level)) - 1];
}

export class SimEngine {
  constructor(sim, bus) {
    this.sim = sim;
    this.bus = bus;
    this.paused = true;
    this.speedLevel = 2;
    this.pauseReason = "start";
    this.snapshot = null;
    this.accum = 0;
    this.busy = false;
    this.lastTs = null;
    this._raf = this._raf.bind(this);
  }

  view() { return this.snapshot ? new StateView(this.snapshot, this._engineState()) : null; }
  _engineState() { return { paused: this.paused, speed: this.speedLevel, pause_reason: this.pauseReason }; }

  async startNewGame(seed = 19770620, ironman = false) {
    await this.sim.setReads(allReads());
    this.snapshot = await this.sim.newGame(seed, ironman);
    this.paused = true;
    this.pauseReason = "start";
    this.accum = 0;
    this._emitPauseState();
    this.bus.emit("sim_day_advanced", this.view());
    if (!this.lastTs) requestAnimationFrame(this._raf);
    return this.snapshot;
  }

  _raf(ts) {
    const dt = this.lastTs === null ? 0 : Math.min(0.25, (ts - this.lastTs) / 1000);
    this.lastTs = ts;
    if (!this.paused && this.snapshot && !this.busy) {
      this.accum += dt;
      const interval = secondsPerDay(this.speedLevel);
      let days = 0;
      while (this.accum >= interval && days < MAX_DAYS_PER_FRAME) { this.accum -= interval; days += 1; }
      if (this.accum >= interval) this.accum = 0; // drop backlog like the Godot driver
      if (days > 0) this._advance(days);
    }
    requestAnimationFrame(this._raf);
  }

  async _advance(days) {
    this.busy = true;
    try {
      const res = await this.sim.step(days);
      this.snapshot = res.snapshot;
      if (res.ended || res.paused) {
        this.paused = true;
        this.pauseReason = res.ended ? "ended" : res.reason;
      }
      const view = this.view();
      this.bus.emit("sim_day_advanced", view);
      this.bus.emit("day_advanced", view.clock.day_index, view.clock.date, view.clock.is_week, view.clock.is_month);
      if (res.ended) {
        this.bus.emit("end_tenure_triggered", { day_index: view.clock.day_index, date: view.clock.date, ending_id: (view.modules.M14 || {}).ending_id || "" });
        this._emitPauseState();
      } else if (res.paused) {
        this.bus.emit("sim_auto_paused", this.pauseReason);
        this._emitPauseState();
        if (view.modules.M12.pending_events.length) this.bus.emit("event_modal_requested", view.modules.M12.pending_events[0]);
      }
    } catch (err) {
      console.error("[SimEngine] step failed", err);
      this.paused = true;
      this.pauseReason = "error";
      this._emitPauseState();
    } finally {
      this.busy = false;
    }
  }

  getSnapshot() { return this.view(); }

  setPaused(value) {
    if (!value && this.snapshot && this.snapshot.phase === "ENDED") value = true;
    if (this.paused === value) return;
    this.paused = value;
    this.pauseReason = value ? "player" : "";
    this.accum = 0;
    this._emitPauseState();
  }

  togglePause() { this.setPaused(!this.paused); }

  setSpeed(level) {
    this.speedLevel = Math.min(MAX_SPEED, Math.max(MIN_SPEED, level));
    this.accum = 0;
    this.bus.emit("sim_speed_changed", this.speedLevel);
    this._emitPauseState();
  }

  async submitCommand(cmd) {
    const res = await this.sim.command(cmd);
    this.snapshot = res.snapshot;
    if (res.ok) this.bus.emit("snapshot_updated", this.view());
    return res;
  }

  async quickSave() {
    const text = await this.sim.save();
    localStorage.setItem(QUICKSAVE_KEY, text);
    return text;
  }

  async quickLoad() {
    const text = localStorage.getItem(QUICKSAVE_KEY);
    if (!text) return { ok: false, error: "no quicksave" };
    const res = await this.sim.load(text);
    this.snapshot = res.snapshot;
    this.paused = true;
    this.pauseReason = "loaded";
    this.accum = 0;
    const view = this.view();
    this.bus.emit("sim_day_advanced", view);
    this._emitPauseState();
    if (view.modules.M12.pending_events.length) this.bus.emit("event_modal_requested", view.modules.M12.pending_events[0]);
    return res;
  }

  _emitPauseState() {
    const reasons = this.paused && this.pauseReason ? [this.pauseReason] : [];
    this.bus.emit("pause_state_changed", this.paused, this.speedLevel, reasons);
  }
}
