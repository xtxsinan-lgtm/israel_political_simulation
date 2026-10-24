"""Browser bridge for the web prototype.

Runs the *reference* Python simulation (sim/) inside Pyodide and exposes the same surface the
Godot client uses through SimDirector / the SimEngine autoload:

  new_game(seed, ironman)        -> snapshot           (SimDirector.start_new_game)
  step(max_days)                 -> {snapshot, ...}     (SimEngine._advance_one_day, with
                                                         AutoPauseEvaluator semantics)
  command(cmd)                   -> {ok, error, snapshot}  (SimDirector.submit_command)
  save() / load(text)                                   (SaveSystem: seed + command log, plus
                                                         a full state dump for fast loading)
  explain(param, key), preview(effects), actions(), evaluate(reason), golden_check()

Every function takes/returns JSON strings so the JS side never touches Python objects.
Interactive play does NOT auto-resolve events (same as the Godot desk): queued events pause
the clock and are resolved through the `resolve_event` command.
"""

import copy
import json
import math
from typing import Any, Dict, List, Optional

from sim.engine import SimulationEngine
from sim.modules import (
    _resolve_default_action_args,
    approve_minister_proposal,
    continue_as_successor,
    get_available_actions,
    reject_minister_proposal,
    resolve_coalition_demand,
)
from sim.state import DataRegistry

SAVE_FORMAT = "web-1.0"
DEFAULT_SEED = 19770620
# Same thresholds as game/sim/modules/m01_core.gd _scan_alerts.
RED_ALERTS = ("coalition_minority", "inflation_red", "security_red")


def _clean(obj: Any) -> Any:
    """Make a value JSON-safe (NaN/inf -> None, tuples -> lists, non-str keys -> str)."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if obj is None or isinstance(obj, (str, int, bool)):
        return obj
    return str(obj)


class Bridge:
    def __init__(self) -> None:
        self.registry = DataRegistry.instance()
        self.engine: Optional[SimulationEngine] = None
        self.command_log: List[Dict[str, Any]] = []
        self.seen_alerts: List[str] = []
        self.reads: List[List[Any]] = []
        # Daily ring of every national scalar param (Godot history.daily_ring, <= 365 days)
        # so sparklines can plot any node, not just the 3 fields Godot records.
        self.daily_ring: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------ lifecycle
    def new_game(self, seed: int = DEFAULT_SEED, ironman: bool = False) -> Dict[str, Any]:
        self.engine = SimulationEngine(scenario_id="begin_1977", master_seed=int(seed), auto_resolve_events=False)
        self.engine.state.meta["ironman"] = bool(ironman)
        self.command_log = []
        self.seen_alerts = []
        self.daily_ring = []
        self._record_day()
        return self.snapshot()

    def _record_day(self) -> None:
        st = self.engine.state
        row: Dict[str, Any] = {"day_index": st.day_index, "date": st.date_str}
        for pid, val in st.params.items():
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                row[pid] = float(val)
            elif isinstance(val, dict):
                for k, v in val.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        row[f"{pid}|{k}"] = float(v)
        self.daily_ring.append(row)
        if len(self.daily_ring) > 365:
            del self.daily_ring[0]

    def history(self, param: str, key: Optional[str] = None, days: int = 30) -> List[Dict[str, Any]]:
        """Last `days` daily values of a param (scoped params resolved through get_param only
        for the current day; earlier days use the ring, which stores national scalars)."""
        field = f"{param}|{key}" if key else param
        out = []
        for row in self.daily_ring[-int(days):]:
            if field in row:
                out.append({"day_index": row["day_index"], "date": row["date"], "value": row[field]})
        if not out:
            out = [{"day_index": self.engine.state.day_index, "date": self.engine.state.date_str,
                    "value": self.engine.state.get_param(param, key)}]
        return out

    def set_reads(self, reads: List[List[Any]]) -> None:
        """UI components declare the (param, key) pairs they display; values are resolved with
        GameState.get_param so aliases and scope rules match the simulation exactly."""
        self.reads = [[str(r[0]), (None if len(r) < 2 or r[1] in (None, "") else str(r[1]))] for r in reads]

    # ------------------------------------------------------------------ alerts / auto pause
    def _alerts(self) -> List[str]:
        st = self.engine.state
        out: List[str] = []
        if st.get_param("coalition_seats") < 61.0:
            out.append("coalition_minority")
        infl = st.get_param("inflation")
        if infl >= 100.0:
            out.append("inflation_red")
        elif infl >= 50.0:
            out.append("inflation_yellow")
        if st.get_param("public_security") <= 35.0:
            out.append("security_red")
        return out

    def _auto_pause_reason(self) -> str:
        """Mirror of game/sim/AutoPauseEvaluator.gd (event > vote > new red alert)."""
        st = self.engine.state
        if st.m12.get("queue"):
            return "event"
        if st.m03.get("vote_modal_open"):
            return "vote"
        for req in st.pending.get("vote_requests", []) or []:
            if isinstance(req, dict) and int(req.get("due_day", st.day_index)) <= st.day_index:
                return "vote"
        red_now = [a for a in self._alerts() if a in RED_ALERTS]
        fresh = [a for a in red_now if a not in self.seen_alerts]
        self.seen_alerts = red_now
        return "alert" if fresh else ""

    # ------------------------------------------------------------------ stepping
    def step(self, max_days: int = 1) -> Dict[str, Any]:
        st = self.engine.state
        stepped = 0
        reason = ""
        ended = st.run.get("phase") == "ENDED"
        triggered: List[str] = []
        while stepped < int(max_days) and not ended:
            res = self.engine.step_day()
            self._record_day()
            stepped += 1
            triggered.extend(res.get("triggered_events", []) or [])
            ended = bool(res.get("ended")) or st.run.get("phase") == "ENDED"
            if ended:
                reason = "ended"
                break
            reason = self._auto_pause_reason()
            if reason:
                break
        return {"days": stepped, "paused": bool(reason), "reason": reason, "ended": ended,
                "triggered": triggered, "snapshot": self.snapshot()}

    # ------------------------------------------------------------------ commands
    def command(self, cmd: Dict[str, Any]) -> Dict[str, Any]:
        st = self.engine.state
        op = str(cmd.get("op", ""))
        res: Dict[str, Any] = {"ok": False, "error": f"unknown op {op}"}
        if op == "continue_succession":
            end_r = str((st.m14.get("final_evaluation") or {}).get("end_reason") or st.pending.get("tenure_end") or "resignation")
            new_leader = continue_as_successor(st, end_r)
            res = {"ok": True, "leader_id": new_leader}
        elif st.run.get("phase") == "ENDED":
            res = {"ok": False, "error": "ended"}
        elif op == "resolve_event":
            res = self.engine.choose_event_option(str(cmd.get("event", "")), str(cmd.get("option", "A")))
        elif op == "adjust_policy":
            tier = cmd.get("tier")
            res = self.engine.adjust_policy_now(str(cmd.get("policy", "")), to_tier=None if tier is None else int(tier),
                                                direction=cmd.get("direction"))
        elif op in ("execute_action", "enqueue_action"):
            aid = str(cmd.get("action", ""))
            if aid not in self.registry.actions:
                res = {"ok": False, "error": f"unknown action {aid}"}
            elif op == "enqueue_action":
                self.engine.queue_action(aid, args=cmd.get("args") or {})
                res = {"ok": True, "queued": aid}
            else:
                res = self.engine.execute_action_now(aid, args=cmd.get("args") or {})
        elif op == "approve_minister_proposal":
            res = approve_minister_proposal(st, str(cmd.get("proposal_id", "")), self.engine.executor)
        elif op == "reject_minister_proposal":
            res = reject_minister_proposal(st, str(cmd.get("proposal_id", "")))
        elif op == "resolve_coalition_demand":
            res = resolve_coalition_demand(st, str(cmd.get("demand_id", "")), str(cmd.get("decision", "concede")), self.engine.executor)
        elif op == "set_budget_slider":
            key = str(cmd.get("slider", ""))
            valid_sliders = ("defense", "absorption", "religion", "dev_towns", "education", "welfare", "infrastructure", "settlements")
            if key not in valid_sliders:
                res = {"ok": False, "error": f"bad budget slider {key}"}
            else:
                old_val = float(st.get_param("budget_slider", key))
                val = max(0.0, min(100.0, float(cmd.get("value", 50.0))))
                st.set_param("budget_slider", val, key)
                delta = val - old_val
                st.add_param("budget_balance", -delta * 0.015)
                if key == "defense":
                    st.add_param("readiness", delta * 0.08)
                elif key == "welfare":
                    st.add_param("inequality", -delta * 0.08)
                elif key == "religion":
                    st.add_param("ally_satisfaction", delta * 0.12, "nrp")
                    st.add_param("ally_satisfaction", delta * 0.15, "agudat")
                elif key == "settlements":
                    st.add_param("settler_momentum", delta * 0.10)
                elif key == "absorption":
                    st.add_param("absorption_capacity", delta * 0.12)
                elif key == "infrastructure":
                    st.add_param("growth", delta * 0.015)
                elif key == "education":
                    st.add_param("growth", delta * 0.01)
                elif key == "dev_towns":
                    st.add_param("alienation", -delta * 0.08, "mizrahi")
                ledger = st.m10.setdefault("last_fiscal_ledger", {})
                tot_s = sum(float(st.get_param("budget_slider", k)) for k in valid_sliders)
                ledger["slider_expenditure"] = round(tot_s * (8.712 / 380.0), 3)
                ledger["net_balance"] = round(float(st.get_param("budget_balance")), 3)
                res = {"ok": True, "slider": key, "value": val}
        elif op == "set_mobilization":
            val = max(0.0, min(100.0, float(cmd.get("value", 10.0))))
            st.m09["mobilization_target"] = val
            cur = float(st.get_param("mobilization"))
            st.set_param("mobilization", cur + 0.5 * (val - cur))
            res = {"ok": True, "mobilization_target": val}
        elif op == "set_roe":
            front = str(cmd.get("front", ""))
            fronts = st.m09.get("fronts", {})
            if front not in fronts:
                res = {"ok": False, "error": f"unknown front {front}"}
            else:
                roe = max(0, min(2, int(cmd.get("roe", 1))))
                fronts[front]["roe_level"] = roe
                res = {"ok": True, "front": front, "roe": roe}
        elif op == "set_region_priority":
            region = str(cmd.get("region", ""))
            field = str(cmd.get("param", "region_investment_priority"))
            if not region or field not in ("region_absorption_priority", "region_investment_priority", "region_security_posture"):
                res = {"ok": False, "error": "bad region command"}
            else:
                st.set_param(field, max(0.0, min(100.0, float(cmd.get("value", 0.0)))), region)
                res = {"ok": True}
        ok = bool(res.get("ok", True)) if isinstance(res, dict) else True
        if ok:
            self.command_log.append({"day_index": st.day_index, "seq": len(self.command_log), "payload": copy.deepcopy(cmd)})
        return {"ok": ok, "result": _clean(res), "snapshot": self.snapshot()}

    # ------------------------------------------------------------------ queries
    def actions(self) -> List[Dict[str, Any]]:
        st = self.engine.state
        avail = {a.get("id") for a in get_available_actions(st, ignore_pc=False)}
        completed = st.m05.get("completed_counts", {})
        out = []
        for aid, adef in self.registry.actions.items():
            if aid == "change_policy":
                continue
            row = {k: adef.get(k) for k in ("id", "zh", "cat", "cost", "dur", "cd", "w", "note", "args", "tags", "once", "era", "econ_gate", "succ")}
            row["available"] = aid in avail
            row["cooldown_until"] = int(st.m05.get("action_cooldowns", {}).get(aid, 0))
            row["completed_count"] = int(completed.get(aid, 0))
            row["default_args"] = _resolve_default_action_args(st, adef)
            out.append(row)
        return _clean(out)

    def explain(self, param: str, key: Optional[str] = None) -> Dict[str, Any]:
        return _clean(self.engine.explain(param, key or None))

    def preview(self, effects: List[Dict[str, Any]]) -> Dict[str, Any]:
        return _clean(self.engine.preview_layers(effects))

    def evaluate(self, reason: str = "resignation") -> Dict[str, Any]:
        """Side-effect-free alias of final_evaluation (the raw engine call mutates state)."""
        return self.final_evaluation(reason)

    def event_def(self, event_id: str) -> Dict[str, Any]:
        return _clean(self.registry.events_by_id.get(event_id, {}))

    def event_options(self, event_id: str) -> List[Dict[str, Any]]:
        """Mirror of M12Events.evaluate_event_options_for_ui (Godot) on the Python data:
        rows {id, title, historical, available, lock_reasons[], preview_l1, risk_hint}.
        Availability uses the same option `requires`/`condition` expression that
        modules._instantiate_event filters with, plus the Godot `pc_cost` gate; options that
        were filtered out of the queued instance cannot be resolved and are reported locked."""
        from sim.expr import eval_bool

        st = self.engine.state
        defn = self.registry.events_by_id.get(event_id, {}) or {}
        raw = defn.get("options") or (defn.get("followup_choice", {}) or {}).get("options") or []
        queued = next((e for e in st.m12.get("queue", []) or [] if e.get("id") == event_id), None)
        queued_ids = {str(o.get("id")) for o in (queued or {}).get("options", [])}
        pc_have = float(st.get_param("political_capital"))
        out: List[Dict[str, Any]] = []
        for idx, opt in enumerate(raw):
            oid = str(opt.get("id", chr(ord("A") + idx)))
            available = True
            reasons: List[str] = []
            req = opt.get("requires") or opt.get("condition")
            if req and not eval_bool(req, st):
                available = False
                reasons.append(str(opt.get("locked_reason_zh", "条件未满足")))
            elif queued is not None and oid not in queued_ids:
                available = False
                reasons.append(str(opt.get("locked_reason_zh", "条件未满足")))
            pc_need = float(opt.get("pc_cost", 0.0) or 0.0)
            if pc_need > pc_have:
                available = False
                reasons.append("需要政治资本 ≥ %d，当前 %d" % (int(pc_need), int(pc_have)))
            out.append({
                "id": oid,
                "title": str(opt.get("title", opt.get("label", f"Option {idx+1}"))),
                "historical": bool(opt.get("historical", False)),
                "available": available,
                "lock_reasons": reasons,
                "preview_l1": str(opt.get("summary", opt.get("title", ""))),
                "risk_hint": opt.get("risk_hint"),
            })
        if not out and queued is not None:
            for o in queued.get("options", []):
                out.append({"id": str(o.get("id", "A")), "title": str(o.get("title", "")), "historical": bool(o.get("historical", False)),
                            "available": True, "lock_reasons": [], "preview_l1": str(o.get("title", "")), "risk_hint": None})
        return _clean(out)

    def final_evaluation(self, reason: str = "resignation") -> Dict[str, Any]:
        """Side-effect-free M14 evaluation for the end book: the stored final evaluation when the
        run has ended, else compute_final_evaluation on a clone (it writes historical_rating)."""
        st = self.engine.state
        stored = st.m14.get("final_evaluation")
        if st.run.get("phase") == "ENDED" and isinstance(stored, dict) and stored:
            return _clean(stored)
        from sim.modules import compute_final_evaluation

        return _clean(compute_final_evaluation(st.clone(), end_reason=str(reason or "resignation")))

    # ------------------------------------------------------------------ snapshot
    def snapshot(self) -> Dict[str, Any]:
        st = self.engine.state
        full = st.to_dict()
        m02 = full["modules"].get("M02", {})
        full["modules"]["M02"] = {"thresholds": m02.get("thresholds", {}), "baseline_shifts": m02.get("baseline_shifts", {})}
        queue = []
        for ev in st.m12.get("queue", []) or []:
            defn = self.registry.events_by_id.get(ev.get("id"), {})
            item = copy.deepcopy(ev)
            for k in ("background", "narrative", "summary", "perspectives", "form", "major", "title"):
                if k in defn and k not in item:
                    item[k] = defn[k]
            queue.append(item)
        vals = {}
        for param, key in self.reads:
            try:
                vals[f"{param}|{key or ''}"] = st.get_param(param, key)
            except Exception:  # noqa: BLE001 - unknown params read as None, like a missing node
                vals[f"{param}|{key or ''}"] = None
        snap = {
            "day_index": st.day_index,
            "date": st.date_str,
            "year": st.year,
            "month": st.month,
            "day": st.day,
            "weekday": st.weekday,
            "is_week": st.is_week,
            "is_month": st.is_month,
            "phase": st.run.get("phase"),
            "alerts": self._alerts(),
            "pending_events": queue,
            "vals": vals,
            "state": full,
            "state_hash": st.state_hash(),
        }
        return _clean(snap)

    # ------------------------------------------------------------------ persistence
    def save(self) -> str:
        st = self.engine.state
        return json.dumps(_clean({
            "save_format_version": SAVE_FORMAT,
            "scenario_id": st.scenario_id,
            "master_seed": st.master_seed,
            "ironman": bool(st.meta.get("ironman", False)),
            "day_index": st.day_index,
            "current_date": st.date_str,
            "state_sha256": st.state_hash(),
            "command_log": self.command_log,
            "seen_alerts": self.seen_alerts,
            "file_suffix": "ipsave.json",
        }), ensure_ascii=False)

    def load(self, text: str) -> Dict[str, Any]:
        """Deterministic replay of seed + command log (same contract as Godot SaveSystem.load_into)."""
        env = json.loads(text)
        self.new_game(int(env.get("master_seed", DEFAULT_SEED)), bool(env.get("ironman", False)))
        log = sorted(env.get("command_log", []), key=lambda r: (int(r.get("day_index", 0)), int(r.get("seq", 0))))
        target = int(env.get("day_index", 0))
        st = self.engine.state
        cursor = 0
        while True:
            while cursor < len(log) and int(log[cursor].get("day_index", 0)) <= st.day_index:
                self.command(log[cursor].get("payload", {}))
                cursor += 1
            if st.day_index >= target or st.run.get("phase") == "ENDED":
                break
            self.engine.step_day()
            self._record_day()
        self.seen_alerts = list(env.get("seen_alerts", []))
        ok = st.state_hash() == env.get("state_sha256", st.state_hash())
        return {"ok": ok, "snapshot": self.snapshot()}

    # ------------------------------------------------------------------ self test
    def golden_check(self, golden_text: str) -> Dict[str, Any]:
        golden = json.loads(golden_text)
        eng = SimulationEngine(scenario_id="begin_1977", master_seed=DEFAULT_SEED)
        ok = 0
        rows = []
        for cp in golden["checkpoints"]:
            while eng.state.day_index < cp["day_index"]:
                eng.step_day()
            match = eng.state_hash() == cp["state_hash"]
            ok += match
            rows.append({"day_index": cp["day_index"], "date": cp["date"], "match": match})
        return {"matches": ok, "total": len(golden["checkpoints"]), "rows": rows}


BRIDGE = Bridge()


def call(name: str, args_json: str) -> str:
    """Single entry point used by the web worker: call("step", "[5]") -> '{"r": ...}'."""
    args = json.loads(args_json) if args_json else []
    result = getattr(BRIDGE, name)(*args)
    return json.dumps({"r": _clean(result)}, ensure_ascii=False)
