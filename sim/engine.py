from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from sim.causal import CausalNet
from sim.expr import EffectExecutor, eval_bool, eval_expr, eval_float
from sim.modules import (
    adjust_policy,
    compute_final_evaluation,
    execute_player_action,
    get_available_actions,
    preview_layers,
    register_all_term_providers,
    resolve_event_option,
    step_01_m01_maintenance,
    step_02_m05_enqueue_actions,
    step_03_m09_military_daily,
    step_04_m07_diplomacy_daily,
    step_05_m05_advance_actions,
    step_06_m06_characters_weekly,
    step_07_m03_parliament_weekly,
    step_08_weekly_security,
    step_09_m10_fiscal_monthly,
    step_11_m04_party_monthly,
    step_12_m07_m08_monthly,
    step_13_m11_regions_monthly,
    step_14_m13_authoritarian_monthly,
    step_15_m05_pc_and_snapshots,
    step_16_m10_macro_quarterly,
    step_17_yearly,
    step_18_m12_events_daily,
    step_19_m03_votes_and_elections,
    step_20_m14_endings,
)
from sim.state import DataRegistry, GameState


class SimulationEngine:
    """
    Deterministic Headless Reference Simulation Engine (M01-M14).
    Implements the 20-step daily settlement pipeline defined in docs/contracts.md §3.
    """

    def __init__(
        self,
        scenario_id: str = "begin_1977",
        master_seed: int = 19770620,
        state: Optional[GameState] = None,
        bot: Optional[Any] = None,
        auto_resolve_events: bool = True,
        allow_succession: bool = False,
    ) -> None:
        self.registry: DataRegistry = DataRegistry.instance()
        self.state: GameState = state or GameState(scenario_id=scenario_id, master_seed=master_seed, registry=self.registry)
        self.state.run["allow_succession"] = bool(allow_succession)
        self.causal_net: CausalNet = CausalNet(self.registry)
        register_all_term_providers(self.causal_net)
        self.executor: EffectExecutor = EffectExecutor(self.causal_net)
        self.bot: Optional[Any] = bot
        self.auto_resolve_events: bool = auto_resolve_events

    def step_day(self, bot: Optional[Any] = None) -> Dict[str, Any]:
        """Advance the simulation by 1 game day through all 20 settlement steps."""
        st = self.state
        if st.run.get("phase") == "ENDED":
            return {"day_index": st.day_index, "date": st.date_str, "ended": True, "ending_id": st.m14.get("ending_id")}

        active_bot = bot or self.bot

        # Pause phase P: If a bot is attached, let it queue weekly actions/policy adjustments on Sundays
        if active_bot is not None and st.is_week:
            self._run_bot_weekly_decisions(active_bot)

        # Step 1: M01 Date advancement & maintenance
        step_01_m01_maintenance(st, self.executor)

        # Step 2: M05 Player actions enter execution queue
        step_02_m05_enqueue_actions(st, self.executor)

        # Step 3: M09 Military & active war fronts daily step
        step_03_m09_military_daily(st, self.executor)

        # Step 4: M07 World diplomacy & summit daily step
        step_04_m07_diplomacy_daily(st, self.executor)

        # Step 5: M05 Advance running actions & settle completions
        step_05_m05_advance_actions(st, self.executor)

        # Steps 6, 7, 8: Weekly settlement (Sundays: weekday == 6)
        if st.is_week:
            step_06_m06_characters_weekly(st, self.executor)
            step_07_m03_parliament_weekly(st, self.executor)
            step_08_weekly_security(st, self.executor)

        # Steps 9, 10, 11, 12, 13, 14, 15: Monthly settlement (1st of month)
        if st.is_month:
            step_09_m10_fiscal_monthly(st, self.executor)
            # Step 10: M02 CausalNet (10a history -> 10b thresholds -> 10c node drift)
            self.causal_net.record_monthly_history(st)
            self.causal_net.evaluate_thresholds(st, self.executor)
            self.causal_net.step_nodes(st, tick_filter="monthly")

            step_11_m04_party_monthly(st, self.executor)
            step_12_m07_m08_monthly(st, self.executor)
            step_13_m11_regions_monthly(st, self.executor)
            step_14_m13_authoritarian_monthly(st, self.executor)
            step_15_m05_pc_and_snapshots(st, self.executor)

        # Step 16: Quarterly macroeconomic settlement (Jan 1, Apr 1, Jul 1, Oct 1)
        if st.is_quarter:
            self.causal_net.step_nodes(st, tick_filter="quarterly")
            step_16_m10_macro_quarterly(st, self.executor)

        # Step 17: Yearly settlement (Jan 1)
        if st.is_year:
            step_17_yearly(st, self.causal_net, self.executor)

        # Step 18: M12 Event engine daily check
        triggered_events = step_18_m12_events_daily(st, self.executor)

        # Auto-resolve queued events if bot or auto_resolve_events is enabled
        if st.m12.get("queue") and (active_bot is not None or self.auto_resolve_events):
            for ev in list(st.m12["queue"]):
                ev_id = ev["id"]
                if active_bot is not None and hasattr(active_bot, "choose_event_option"):
                    opt_id = active_bot.choose_event_option(st, ev, ev.get("options", []))
                else:
                    # Default to historical option if marked, else first option
                    opts = ev.get("options", [])
                    hist_opt = next((o["id"] for o in opts if o.get("historical")), None)
                    opt_id = hist_opt or (opts[0]["id"] if opts else "A")
                resolve_event_option(st, ev_id, opt_id, self.executor)

        # Step 19: M03 Elections, no-confidence votes & coalition formation
        step_19_m03_votes_and_elections(st, self.executor)

        # Step 20: M14 Tenure & ending condition check
        ending_id = step_20_m14_endings(st, self.executor)

        return {
            "day_index": st.day_index,
            "date": st.date_str,
            "triggered_events": [e["id"] for e in triggered_events],
            "ended": ending_id is not None,
            "ending_id": ending_id,
        }

    def _run_bot_weekly_decisions(self, bot: Any) -> None:
        st = self.state
        # Monthly Political Capital audit & decision cycle on first Sunday of each month (st.day <= 7)
        if st.day <= 7:
            all_pre_acts = get_available_actions(st, ignore_pc=True)
            avail_acts = get_available_actions(st, ignore_pc=False)
            # Check if bot wants any action ignoring PC
            wants_any = False
            if hasattr(bot, "score_action") and all_pre_acts:
                wants_any = any(bot.score_action(st, a) > 0.0 for a in all_pre_acts)
            elif all_pre_acts:
                wants_any = True

            if wants_any:
                st.m05["months_action_desired"] = int(st.m05.get("months_action_desired", 0)) + 1
                chosen_acts = bot.choose_actions(st, avail_acts, max_actions=1) if hasattr(bot, "choose_actions") and avail_acts else []
                if not chosen_acts:
                    st.m05["months_pc_blocked"] = int(st.m05.get("months_pc_blocked", 0)) + 1
                else:
                    for item in chosen_acts:
                        aid = item.get("id") if isinstance(item, dict) else str(item)
                        if aid:
                            self.queue_action(aid)

            if st.month % 2 == 1 and hasattr(bot, "choose_policy_adjustments"):
                pol_defs = list(self.registry.policies.values())
                recs = bot.choose_policy_adjustments(st, pol_defs, max_adjustments=1)
                for rec in recs:
                    pid = rec.get("policy_id")
                    direction = rec.get("direction")
                    if pid and direction:
                        self.queue_policy_change(pid, direction=direction)
        elif 15 <= st.day <= 21 and st.get_param("political_capital") >= 38.0:
            avail_acts = get_available_actions(st, ignore_pc=False)
            if hasattr(bot, "choose_actions") and avail_acts:
                chosen_acts = bot.choose_actions(st, avail_acts, max_actions=1)
                for item in chosen_acts:
                    aid = item.get("id") if isinstance(item, dict) else str(item)
                    if aid:
                        self.queue_action(aid)

    def run_days(
        self,
        days: int,
        bot: Optional[Any] = None,
        stop_on_end: bool = True,
    ) -> GameState:
        """Run the simulation for `days` daily ticks."""
        for _ in range(int(days)):
            res = self.step_day(bot=bot)
            if stop_on_end and res.get("ended"):
                break
        return self.state

    def queue_action(self, action_id: str, args: Optional[Dict[str, Any]] = None, free_slot: bool = False) -> None:
        self.state.pending["player_ops"].append({
            "kind": "action",
            "action_id": action_id,
            "args": args or {},
            "free_slot": free_slot,
        })

    def execute_action_now(self, action_id: str, args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return execute_player_action(self.state, action_id, self.executor, args=args)

    def queue_policy_change(
        self,
        policy_id: str,
        to_tier: Optional[int] = None,
        direction: Optional[str] = None,
    ) -> None:
        self.state.pending["player_ops"].append({
            "kind": "policy",
            "policy_id": policy_id,
            "to_tier": to_tier,
            "direction": direction,
        })

    def adjust_policy_now(
        self,
        policy_id: str,
        to_tier: Optional[int] = None,
        direction: Optional[str] = None,
    ) -> Dict[str, Any]:
        return adjust_policy(self.state, policy_id, self.executor, to_tier=to_tier, direction=direction)

    def choose_event_option(self, event_id: str, option_id: str) -> Dict[str, Any]:
        return resolve_event_option(self.state, event_id, option_id, self.executor)

    def preview_layers(self, hypothetical_effects: List[Dict[str, Any]]) -> Dict[str, Any]:
        return preview_layers(self.state, hypothetical_effects, causal_net=self.causal_net)

    def explain(self, param: str, key: Optional[str] = None) -> Dict[str, Any]:
        return self.causal_net.explain(self.state, param, key)

    def evaluate_tenure(self, end_reason: str = "resignation") -> Dict[str, Any]:
        return compute_final_evaluation(self.state, end_reason=end_reason)

    def state_hash(self) -> str:
        return self.state.state_hash()


SimEngine = SimulationEngine
