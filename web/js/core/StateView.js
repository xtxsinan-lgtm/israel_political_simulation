/* StateView: read-only view of a bridge snapshot with the same access shape the Godot
 * controllers use on SimState (clock / run / params.get_val / modules / history).
 *
 * The bridge snapshot carries the full Python GameState.to_dict() under `state`, plus
 * `vals` resolved with GameState.get_param for every (param, key) a component registered
 * through registerReads(). Godot-only names are mapped onto the Python reference names here.
 */

/* Godot TopBar/D5 read params that do not exist in parameters.yaml (they always show 0 in
 * the Godot build). The web prototype maps them to the reference names the code intends. */
export const PARAM_ALIASES = {
  government_approval: "party_standing",
  idf_readiness: "readiness",
  us_wh_warmth: "us_admin_relation",
  us_cong_support: "us_congress_relation",
};

const READS = new Map();

/** Components call this at import time with [[param, key], ...] they will display. */
export function registerReads(pairs) {
  for (const [p, k] of pairs) {
    const param = PARAM_ALIASES[p] || p;
    READS.set(`${param}|${k || ""}`, [param, k || ""]);
  }
}
export function allReads() { return [...READS.values()]; }

export class StateView {
  constructor(snapshot, engineState = {}) {
    this.snap = snapshot;
    const st = snapshot.state || {};
    this.raw = st;
    this.clock = {
      date: snapshot.date,
      day_index: snapshot.day_index,
      year: snapshot.year, month: snapshot.month, day: snapshot.day,
      weekday: snapshot.weekday,
      is_week: !!snapshot.is_week,
      is_month: !!snapshot.is_month,
    };
    this.run = {
      phase: snapshot.phase,
      paused: !!engineState.paused,
      speed: engineState.speed ?? 2,
      pause_reason: engineState.pause_reason ?? "",
    };
    const m = st.modules || {};
    const regions = (m.M11 && m.M11.regions) || {};
    const stage = Number((m.M13 && m.M13.stage) || 0);
    // Godot module field names -> Python reference locations.
    this.modules = {
      M03: {
        knesset_seats: (st.params && st.params.knesset_seats) || (st.parliament && st.parliament.knesset_seats) || {},
        vote_modal_open: !!(m.M03 && m.M03.vote_modal_open),
        coalition_demands: (m.M03 && m.M03.coalition_demands) || [],
      },
      M06: {
        offices: st.offices || {},
        minister_proposals: (m.M06 && m.M06.minister_proposals) || [],
      },
      M09: { fronts: (m.M09 && m.M09.fronts) || {} },
      M11: { regions, key_sites: (m.M11 && m.M11.key_sites) || [] },
      M12: { pending_events: snapshot.pending_events || [] },
      M13: {
        centralization_stage: `C${Math.min(5, stage + 1)}`,
        protest_tier: Number((m.M13 && m.M13.protest_tier) || 0),
        raw: m.M13 || {},
      },
      M14: m.M14 || {},
    };
    this.history = { active_alerts: snapshot.alerts || [] };
    this.pending = st.pending || {};
    this.offices = st.offices || {};
    this.parliament = st.parliament || {};
    this.characters = st.characters || {};
    this.policies = st.policies || {};
    this.flags = st.flags || {};
    this.params = { get_val: (p, k = "") => this.param(p, k) };
  }

  /** Same contract as ParameterStore.get_val(param, key): float, 0.0 when unknown. */
  param(p, k = "") {
    const param = PARAM_ALIASES[p] || p;
    const key = k || "";
    const hit = this.snap.vals ? this.snap.vals[`${param}|${key}`] : undefined;
    if (hit !== undefined && hit !== null) return Number(hit);
    const store = (this.raw.params || {})[param];
    if (store === undefined || store === null) return 0.0;
    if (typeof store === "number") return store;
    if (key && typeof store === "object" && store[key] !== undefined) return Number(store[key]);
    return 0.0;
  }

  /** Keys of a scoped param (e.g. knesset_seats parties), sorted like SimMath.sorted_keys. */
  keys(p) {
    const store = (this.raw.params || {})[PARAM_ALIASES[p] || p];
    return store && typeof store === "object" ? Object.keys(store).sort() : [];
  }

  get ended() { return this.snap.phase === "ENDED"; }
}
