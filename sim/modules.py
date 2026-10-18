from __future__ import annotations

import copy
import math
from typing import Any, Dict, List, Optional, Tuple

from sim.expr import EffectExecutor, eval_bool, eval_float
from sim.state import clamp, quantize, resolve_party_id, resolve_region_id


# ============================================================================
# Term Providers for CausalNet (contracts.md §4.2.1 D-052)
# ============================================================================

def register_all_term_providers(causal_net: Any) -> None:
    causal_net.register_term_provider("m04_terms", term_m04)
    causal_net.register_term_provider("m07_us_admin_baseline", term_m07_us_admin)
    causal_net.register_term_provider("m07_power_baseline", term_m07_power)
    causal_net.register_term_provider("m10_monthly_terms", term_m10_monthly)
    causal_net.register_term_provider("m10_quarterly_terms", term_m10_quarterly)
    causal_net.register_term_provider("m11_settler_demography_term", term_m11_settler)


def term_m04(state: Any, param: str, key: Optional[str]) -> float:
    if state.day_index == 0:
        return 0.0
    dev = state.get_param("stance_deviation")
    if param == "party_standing":
        return -0.25 * max(0.0, dev - 5.0)
    if param == "faction_mood":
        return -0.20 * max(0.0, dev - 5.0)
    if param == "challenger_strength":
        return 0.15 * max(0.0, dev - 10.0)
    return 0.0


def term_m07_us_admin(state: Any, param: str, key: Optional[str]) -> float:
    if state.day_index == 0:
        return 0.0
    us_pol = state.m07.get("us_politics", {})
    base = float(us_pol.get("admin_baseline", 55.0))
    return (base - 55.0) * 0.5


def term_m07_power(state: Any, param: str, key: Optional[str]) -> float:
    return 0.0


def term_m10_monthly(state: Any, param: str, key: Optional[str]) -> float:
    if state.day_index == 0:
        return 0.0
    if param == "public_debt":
        bb = state.get_param("budget_balance")
        return max(-1.5, min(2.5, -bb * 0.12))
    if param == "fx_reserves":
        bb = state.get_param("budget_balance")
        us_rel = state.get_param("us_admin_relation")
        return (bb + 2.0) * 0.4 + (us_rel - 58.0) * 0.05
    return 0.0


def term_m10_quarterly(state: Any, param: str, key: Optional[str]) -> float:
    if state.day_index == 0:
        return 0.0
    if param == "inflation":
        bb = state.get_param("budget_balance")
        inf = state.get_param("inflation")
        if state.m10.get("stabilization_plan_active"):
            return -max(5.0, (inf - 20.0) * 0.35)
        if inf > 60.0 and bb < -4.0:
            return min(25.0, (inf - 60.0) * 0.12 + abs(bb + 4.0) * 1.5)
    elif param == "growth":
        mob = state.get_param("mobilization")
        if mob >= 80.0:
            return -0.75
        elif mob >= 50.0:
            return -0.25
        elif mob >= 25.0:
            return -0.08
    return 0.0


def term_m11_settler(state: Any, param: str, key: Optional[str]) -> float:
    if state.day_index == 0:
        return 0.0
    tot = state.settler_population_total()
    return min(15.0, max(0.0, (tot - 51500.0) / 10000.0))


# ============================================================================
# Step 1: M01 Calendar & Base Maintenance
# ============================================================================

def step_01_m01_maintenance(state: Any, executor: EffectExecutor) -> None:
    """Step 1 (M01): Advance date, expire flags & modifiers, release due delayed_effects."""
    # 1a. Advance calendar by 1 day
    state.update_calendar(state.day_index + 1)

    # 1b. Monthly reset of one_off_flows & forced_popups_month
    if state.is_month:
        state.m10["last_one_off_flow"] = float(state.m02["one_off_flows"].get("budget_balance", 0.0))
        state.m02["one_off_flows"]["budget_balance"] = 0.0
        state.m12["month_forced_count"] = 0
        state.m12["month_random_count"] = 0
        # Decay axis_impulse by 0.95 monthly (contracts.md §4.2 m05_add_axis_impulse)
        for ax in state.axis_impulse:
            state.axis_impulse[ax] = quantize(float(state.axis_impulse[ax]) * 0.95)
        state.recompute_gov_axis_position()

    if state.is_week:
        state.m05["weekly_slots_used"] = 0

    # 1d. Expire flags and modifiers
    expired_flags = [
        fid for fid, fdata in state.flags.items()
        if fdata.get("expires_day") is not None and int(fdata["expires_day"]) <= state.day_index
    ]
    for fid in expired_flags:
        state.flags.pop(fid, None)

    state.modifiers = [
        m for m in state.modifiers
        if int(m.get("end_day", -1)) < 0 or int(m.get("end_day", -1)) > state.day_index
    ]

    # 1f. Release due delayed_effects
    rem_delayed = []
    for item in state.pending.get("delayed_effects", []):
        if int(item.get("due_day", 0)) <= state.day_index:
            executor.apply_one(
                state,
                item["effect"],
                source=item.get("source", "delayed"),
                ctx=item.get("ctx", {}),
                rng_stream_name="core",
            )
        else:
            rem_delayed.append(item)
    state.pending["delayed_effects"] = rem_delayed


# ============================================================================
# Step 2 & Step 5: M05 Player Actions & Policies
# ============================================================================

def step_02_m05_enqueue_actions(state: Any, executor: EffectExecutor) -> None:
    """Step 2 (M05): Move queued player operations into active execution."""
    ops = state.pending.get("player_ops", [])
    state.pending["player_ops"] = []
    for op_req in ops:
        kind = op_req.get("kind")
        if kind == "action":
            execute_player_action(
                state,
                op_req["action_id"],
                executor,
                args=op_req.get("args", {}),
                free_slot=bool(op_req.get("free_slot", False)),
            )
        elif kind == "policy":
            adjust_policy(
                state,
                op_req["policy_id"],
                executor,
                to_tier=op_req.get("to_tier"),
                direction=op_req.get("direction"),
            )


def step_05_m05_advance_actions(state: Any, executor: EffectExecutor) -> None:
    """Step 5 (M05): Advance running actions and settle completed ones."""
    still_active = []
    for act_inst in state.m05.get("active_actions", []):
        act_inst["remaining_days"] = int(act_inst.get("remaining_days", 1)) - 1
        if act_inst["remaining_days"] <= 0:
            aid = act_inst["id"]
            adef = state.registry.actions.get(aid, {})
            fx = adef.get("fx") or adef.get("effects") or []
            executor.apply_effects(
                state,
                fx,
                source=f"action:{aid}",
                ctx=act_inst.get("args", {}),
                rng_stream_name="politics",
            )
            state.set_flag(f"act.{aid}", source=f"action:{aid}")
            comp = state.m05.setdefault("completed_actions", {})
            comp[aid] = int(comp.get(aid, 0)) + 1
            state.history["action_log"].append({
                "day_index": state.day_index,
                "date": state.date_str,
                "action_id": aid,
                "args": act_inst.get("args", {}),
            })
        else:
            still_active.append(act_inst)
    state.m05["active_actions"] = still_active


def get_available_actions(state: Any) -> List[Dict[str, Any]]:
    """Return all actions from data/actions.yaml that are off cooldown and meet prerequisites."""
    avail: List[Dict[str, Any]] = []
    pc = state.get_param("political_capital")
    cd_map = state.m05.get("action_cooldowns", {})
    for aid, adef in state.registry.actions.items():
        if aid == "change_policy":
            continue
        if int(cd_map.get(aid, 0)) > state.day_index:
            continue
        cost = adef.get("cost", {})
        pc_cost = float(cost.get("pc", 0.0)) if isinstance(cost, dict) else 0.0
        if pc_cost > pc:
            continue
        pre = adef.get("pre") or adef.get("condition")
        if pre and not eval_bool(pre, state):
            continue
        avail.append(adef)
    return avail


def execute_player_action(
    state: Any,
    action_id: str,
    executor: EffectExecutor,
    args: Optional[Dict[str, Any]] = None,
    free_slot: bool = False,
) -> Dict[str, Any]:
    """Execute or start a player action from data/actions.yaml."""
    adef = state.registry.actions.get(action_id)
    if not adef:
        return {"ok": False, "error": f"Unknown action: {action_id}"}
    cd_map = state.m05.setdefault("action_cooldowns", {})
    if int(cd_map.get(action_id, 0)) > state.day_index:
        return {"ok": False, "error": "cooldown"}

    # Supply default entity arguments if not provided
    act_args = dict(args or {})
    for arg_k, arg_type in (adef.get("args") or {}).items():
        if arg_k not in act_args:
            if arg_type == "party":
                act_args[arg_k] = "nrp"
            elif arg_type == "character":
                act_args[arg_k] = "weizman"
            elif arg_type == "axis":
                act_args[arg_k] = "territory"
            elif arg_type == "party_faction":
                act_args[arg_k] = "herut_hawks"
            elif arg_type == "region":
                act_args[arg_k] = "west_bank"
            elif arg_type == "promise":
                act_args[arg_k] = state.promises[0]["id"] if state.promises else "peace_and_security"

    cost = adef.get("cost", {})
    pc_cost = 0.0
    if isinstance(cost, dict):
        pc_cost = float(cost.get("pc", 0.0)) * state.mod_factor("pc_cost")
        if free_slot:
            pc_cost *= 0.70
        if state.get_param("political_capital") < pc_cost:
            return {"ok": False, "error": "insufficient_pc"}
        if pc_cost > 0:
            state.add_param("political_capital", -pc_cost)
        if "standing" in cost:
            state.add_param("party_standing", float(cost["standing"]))
        if "rol" in cost:
            state.add_param("rule_of_law", float(cost["rol"]))
        if "fiscal" in cost:
            state.m02["one_off_flows"]["budget_balance"] = float(state.m02["one_off_flows"].get("budget_balance", 0.0)) - float(cost["fiscal"])

    cd_days = int(adef.get("cd", adef.get("cooldown_days", 30)) or 0)
    if cd_days > 0:
        cd_map[action_id] = state.day_index + cd_days

    if not free_slot:
        state.m05["weekly_slots_used"] = int(state.m05.get("weekly_slots_used", 0)) + 1

    dur = int(adef.get("dur", 0) or 0)
    if dur > 0:
        state.m05["active_actions"].append({
            "id": action_id,
            "remaining_days": dur,
            "args": act_args,
        })
        return {"ok": True, "action_id": action_id, "status": "running", "duration": dur}
    else:
        fx = adef.get("fx") or adef.get("effects") or []
        applied = executor.apply_effects(state, fx, source=f"action:{action_id}", ctx=act_args, rng_stream_name="politics")
        state.set_flag(f"act.{action_id}", source=f"action:{action_id}")
        comp = state.m05.setdefault("completed_actions", {})
        comp[action_id] = int(comp.get(action_id, 0)) + 1
        state.history["action_log"].append({
            "day_index": state.day_index,
            "date": state.date_str,
            "action_id": action_id,
            "args": act_args,
        })
        return {"ok": True, "action_id": action_id, "status": "completed", "applied": applied}


def adjust_policy(
    state: Any,
    policy_id: str,
    executor: EffectExecutor,
    to_tier: Optional[int] = None,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    """Adjust a persistent policy lever in state.policies (M05)."""
    if policy_id not in state.policies or policy_id not in state.registry.policies:
        return {"ok": False, "error": f"Unknown policy {policy_id}"}
    pstate = state.policies[policy_id]
    if int(pstate.get("cooldown_until_day", 0)) > state.day_index:
        return {"ok": False, "error": "cooldown"}

    pol_def = state.registry.policies[policy_id]
    tiers = pol_def.get("tiers", [])
    tier_vals = [float(t["v"] if isinstance(t, dict) else t) for t in tiers]
    if not tier_vals:
        return {"ok": False, "error": "no_tiers"}

    cur_idx = int(pstate.get("tier_idx", 0))
    if to_tier is not None:
        new_idx = max(0, min(len(tier_vals) - 1, int(to_tier)))
    elif direction == "up":
        new_idx = min(len(tier_vals) - 1, cur_idx + 1)
    elif direction == "down":
        new_idx = max(0, cur_idx - 1)
    else:
        new_idx = cur_idx

    if new_idx == cur_idx:
        return {"ok": False, "error": "unchanged"}

    pc_cost = float(pol_def.get("pc", 8.0)) * state.mod_factor("pc_cost")
    if state.get_param("political_capital") < pc_cost:
        return {"ok": False, "error": "insufficient_pc"}

    state.add_param("political_capital", -pc_cost)
    pstate["tier_idx"] = new_idx
    pstate["cooldown_until_day"] = state.day_index + int(pol_def.get("cd", 60))
    state.set_param("policy_level", tier_vals[new_idx], policy_id)
    state.recompute_gov_axis_position()
    return {"ok": True, "policy_id": policy_id, "tier_idx": new_idx, "level": tier_vals[new_idx]}


# ============================================================================
# Step 3 & Step 8: M09 Military, M11 Regions & M08 Palestine Weekly
# ============================================================================

def step_03_m09_military_daily(state: Any, executor: EffectExecutor) -> None:
    """Step 3 (M09): Daily mobilization convergence, active war fronts, war fiscal drain."""
    rng = state.rng.stream("combat")
    cur_mob = state.get_param("mobilization")
    tgt_mob = float(state.m09.get("mobilization_target", 10.0))
    if abs(cur_mob - tgt_mob) > 0.1:
        step_dir = 2.5 if tgt_mob > cur_mob else -1.5
        new_mob = clamp(cur_mob + step_dir, min(cur_mob, tgt_mob), max(cur_mob, tgt_mob))
        state.set_param("mobilization", new_mob)

    for fid, f in state.m09.get("fronts", {}).items():
        aw = f.get("active_war")
        if isinstance(aw, dict):
            # Active war combat attrition & fiscal cost
            cas = rng.range_int(1, 8)
            aw["casualties"] = int(aw.get("casualties", 0)) + cas
            f["cumulative_casualties"] = int(f.get("cumulative_casualties", 0)) + cas
            state.m02["one_off_flows"]["budget_balance"] = float(state.m02["one_off_flows"].get("budget_balance", 0.0)) - 0.02
            if state.day_index - int(aw.get("start_day", 0)) > 90:
                f["quagmire_months"] = (state.day_index - int(aw.get("start_day", 0))) // 30


def step_08_weekly_security(state: Any, executor: EffectExecutor) -> None:
    """Step 8 (M11 -> M09 -> M08): Weekly regional security & public_security update."""
    rng = state.rng.stream("combat")
    # 8a: M11 region security
    core_regions = ("galilee", "haifa", "tel_aviv", "triangle", "jerusalem", "negev")
    sec_sum = 0.0
    for r in core_regions:
        r_sec = state.get_param("region_security", r)
        sec_sum += r_sec
    avg_core_sec = sec_sum / len(core_regions)

    # 8b: M09 public_security & M08 armed incident check
    det = state.get_param("deterrence")
    pal_host = state.get_param("pal_hostility")
    target_pub_sec = clamp(0.55 * avg_core_sec + 0.35 * det - 0.15 * max(0.0, pal_host - 50.0), 10.0, 95.0)
    cur_pub_sec = state.get_param("public_security")
    state.set_param("public_security", cur_pub_sec + 0.15 * (target_pub_sec - cur_pub_sec))

    # M08 armed incident check when pal_hostility is high
    if pal_host > 65.0 and rng.chance((pal_host - 60.0) / 200.0):
        state.add_param("public_security", -1.5)
        state.pending["hooks"].append({"signal": "sig.m08_armed_incident", "day": state.day_index})


# ============================================================================
# Step 4 & Step 12: M07 World Diplomacy & M08 Palestine Monthly
# ============================================================================

def step_04_m07_diplomacy_daily(state: Any, executor: EffectExecutor) -> None:
    """Step 4 (M07): Daily summit progression & crisis countdowns."""
    neg = state.m07.get("active_negotiation")
    if isinstance(neg, dict):
        neg["days_elapsed"] = int(neg.get("days_elapsed", 0)) + 1


def step_12_m07_m08_monthly(state: Any, executor: EffectExecutor) -> None:
    """Step 12 (M07 & M08): Monthly world tracks & Palestinian faction dynamics."""
    # 12a: US presidency historical transition
    us_pol = state.m07.get("us_politics", {})
    if state.year >= 1989:
        us_pol["president_id"] = "bush_sr"
        us_pol["president_party"] = "republican"
        us_pol["admin_baseline"] = 50.0
    elif state.year >= 1981:
        us_pol["president_id"] = "reagan"
        us_pol["president_party"] = "republican"
        us_pol["admin_baseline"] = 66.0

    # 12b: M08 Palestinian uprising risk & Intifada progression
    up_risk = state.get_param("uprising_risk")
    pal_host = state.get_param("pal_hostility")
    settler_mom = state.get_param("settler_momentum")
    autonomy = state.get_param("autonomy_progress")

    drift = 0.04 * max(0.0, pal_host - 50.0) + 0.03 * max(0.0, settler_mom - 45.0) - 0.04 * autonomy
    state.add_param("uprising_risk", drift)

    up_state = state.m08.get("uprising_state", {})
    if state.get_param("uprising_risk") >= 75.0 and not up_state.get("active"):
        up_state["active"] = True
        up_state["intensity"] = 60.0
        state.set_flag("intifada_active", source="M08")
        if state.year >= 1987 and not state.m08["faction_active"].get("hamas"):
            state.m08["faction_active"]["hamas"] = True
            state.set_param("faction_strength", 25.0, "hamas")
            state.set_param("faction_legitimacy", 30.0, "hamas")


# ============================================================================
# Step 6: M06 AI Ministers & Characters Weekly
# ============================================================================

def step_06_m06_characters_weekly(state: Any, executor: EffectExecutor) -> None:
    """Step 6 (M06): Weekly cabinet minister behavior checks."""
    rng = state.rng.stream("ai")
    for off, cid in state.offices.items():
        if not cid or cid == state.player.get("leader_id"):
            continue
        rel = state.get_param("relation", cid)
        if rel < -35.0 and rng.chance(0.05):
            # Disgruntled minister leaks to press
            state.add_param("party_standing", -1.0)


# ============================================================================
# Step 7 & Step 19: M03 Parliament, Polls, Coalition & Elections
# ============================================================================

def step_07_m03_parliament_weekly(state: Any, executor: EffectExecutor) -> None:
    """Step 7 (M03): Weekly polls, bloc support, and monthly coalition fatigue."""
    rng = state.rng.stream("politics")
    # 7a: First Sunday of the month -> monthly coalition maintenance
    if state.day <= 7:
        state.add_param("months_to_election", -1.0)
        state.add_param("govt_fatigue", 0.35)
        if state.get_param("months_to_election") <= 0.0 and not state.m13.get("survival_mode_active"):
            state.pending["vote_requests"].append({
                "type": "election",
                "due_day": state.day_index + 7,
                "source": "scheduled_term_end",
            })

    # 7b: Weekly poll noise around bloc_support
    standing = state.get_param("party_standing")
    pub_sec = state.get_param("public_security")
    inf = state.get_param("inflation")
    base_likud = clamp(38.0 + (standing - 60.0) * 0.25 + (pub_sec - 60.0) * 0.15 - max(0.0, inf - 45.0) * 0.05, 18.0, 56.0)
    poll_likud = clamp(base_likud + rng.uniform(-1.5, 1.5), 15.0, 60.0)
    poll_labor = clamp(42.0 - (poll_likud - 40.0) * 0.65 + rng.uniform(-1.5, 1.5), 15.0, 58.0)
    state.set_param("poll_seats", round(poll_likud), state.player.get("party_id", "likud"))
    state.set_param("poll_seats", round(poll_labor), "labor")
    state.set_param("poll_lead", poll_likud - poll_labor)


def step_19_m03_votes_and_elections(state: Any, executor: EffectExecutor) -> None:
    """Step 19 (M03): Process due elections and no-confidence votes."""
    if state.m13.get("survival_mode_active"):
        return
    rng = state.rng.stream("elections")
    rem_reqs = []
    for req in state.pending.get("vote_requests", []):
        if int(req.get("due_day", 0)) <= state.day_index:
            vtype = req.get("type", "confidence")
            if vtype in ("election", "early_election"):
                p_party = state.player.get("party_id", "likud")
                lead = state.get_param("poll_lead") + rng.uniform(-2.0, 2.0)
                if lead >= -3.0:
                    # Won re-election
                    new_seats = clamp(round(43.0 + lead * 0.5), 32.0, 55.0)
                    state.set_param("knesset_seats", new_seats, p_party)
                    state.set_param("coalition_seats", max(62.0, new_seats + 22.0))
                    state.set_param("months_to_election", 48.0)
                    state.set_param("govt_fatigue", 5.0)
                    state.run["tenure_elections_won"] = int(state.run.get("tenure_elections_won", 0)) + 1
                else:
                    state.pending["tenure_end"] = "election_loss"
            elif vtype == "no_confidence":
                if state.get_param("coalition_seats") < 61.0 and rng.chance(0.5):
                    state.pending["tenure_end"] = "no_confidence"
        else:
            rem_reqs.append(req)
    state.pending["vote_requests"] = rem_reqs


# ============================================================================
# Step 9, Step 16 & Step 17a: M10 Economy (Monthly, Quarterly, Yearly)
# ============================================================================

def step_09_m10_fiscal_monthly(state: Any, executor: EffectExecutor) -> None:
    """Step 9 (M10): Monthly fiscal balance, debt, FX reserves, and strike risk."""
    pol_delta = state.m05_policy_fiscal_delta()
    one_off = float(state.m10.get("last_one_off_flow", 0.0))
    inf = state.get_param("inflation")
    # Tanzi effect erosion under high inflation
    tanzi = max(0.0, (inf - 35.0) * 0.015)
    target_bb = clamp(-2.0 + pol_delta + one_off - tanzi, -25.0, 15.0)
    cur_bb = state.get_param("budget_balance")
    state.set_param("budget_balance", cur_bb + 0.25 * (target_bb - cur_bb))

    if state.m10.get("stabilization_plan_active"):
        left = int(state.m10.get("stabilization_months_left", 0)) - 1
        state.m10["stabilization_months_left"] = max(0, left)
        if left <= 0:
            state.m10["stabilization_plan_active"] = False
            state.clear_flag("stabilization_plan_active")

    # Track peak inflation and min FX for M14 tenure report
    state.m14["peak_inflation_tenure"] = max(float(state.m14.get("peak_inflation_tenure", 0.0)), state.get_param("inflation"))
    state.m14["min_fx_tenure"] = min(float(state.m14.get("min_fx_tenure", 100.0)), state.get_param("fx_reserves"))


def step_16_m10_macro_quarterly(state: Any, executor: EffectExecutor) -> None:
    """Step 16 (M10): Quarterly macroeconomic adjustments."""
    inf = state.get_param("inflation")
    bb = state.get_param("budget_balance")
    if inf > 80.0 and bb < -5.0 and not state.m10.get("stabilization_plan_active"):
        # Indexation wage-price spiral
        spiral = (inf - 80.0) * 0.08 + abs(bb + 5.0) * 0.6
        state.add_param("inflation", spiral)


def step_17_yearly(state: Any, causal_net: Any, executor: EffectExecutor) -> None:
    """Step 17 (M10/M06/M11): Annual budget cycle, character aging, demographic growth, and yearly CausalNet nodes."""
    # Step yearly CausalNet nodes (e.g. draft_exemption)
    causal_net.step_nodes(state, tick_filter="yearly")
    state.m10["budget_cycle"]["fiscal_year"] = state.year


# ============================================================================
# Step 11: M04 Party Internal, Corridors, Promises & Three-Layer Preview
# ============================================================================

def _get_party_corridor_bounds(state: Any, axis: str) -> Tuple[float, float]:
    party = state.player.get("party_id", "likud")
    parties_cfg = state.corridors.get("parties", {})
    factions_cfg = state.corridors.get("factions", {})
    p_factions = parties_cfg.get(party, {}).get("factions", [])
    if p_factions and isinstance(factions_cfg, dict):
        w_sum = 0.0
        lo_sum = 0.0
        hi_sum = 0.0
        for fid in p_factions:
            fdef = factions_cfg.get(fid, {})
            w = float(state.params.get("faction_weight", {}).get(fid, fdef.get("weight", 25.0)))
            home = fdef.get("home", {}).get(axis, [-30.0, 70.0])
            if isinstance(home, list) and len(home) >= 2:
                lo_sum += w * float(home[0])
                hi_sum += w * float(home[1])
                w_sum += w
        if w_sum > 0:
            return lo_sum / w_sum, hi_sum / w_sum
    return -30.0, 70.0


def step_11_m04_party_monthly(state: Any, executor: EffectExecutor) -> None:
    """Step 11 (M04): Compute stance_deviation vs party corridor, party cohesion, and vision progress."""
    gov_pos = state.recompute_gov_axis_position()
    tenure_m = max(0, (state.day_index - int(state.run.get("tenure_start_day", 0))) // 30)
    grace_mult = 0.0 if tenure_m < 6 else (min(1.0, (tenure_m - 6) / 18.0))

    total_dev = 0.0
    for ax in ("territory", "security", "economy", "religion", "foreign"):
        pos = float(gov_pos.get(ax, 0.0))
        lo, hi = _get_party_corridor_bounds(state, ax)
        dev_ax = 0.0
        if pos < lo:
            dev_ax = lo - pos
        elif pos > hi:
            dev_ax = pos - hi
        total_dev += dev_ax
        state.set_param("stance_deviation", dev_ax * grace_mult, ax)

    state.m14["corridor_months_total"] = int(state.m14.get("corridor_months_total", 0)) + 1
    if total_dev <= 5.0:
        state.m14["corridor_months_inside"] = int(state.m14.get("corridor_months_inside", 0)) + 1

    # Recompute party_cohesion as weighted faction_mood average
    fm = state.params.get("faction_mood", {})
    fw = state.params.get("faction_weight", {})
    if isinstance(fm, dict) and isinstance(fw, dict) and fm:
        w_sum = sum(float(fw.get(k, 25.0)) for k in fm) or 100.0
        coh = sum(float(fm[k]) * float(fw.get(k, 25.0)) for k in fm) / w_sum
        state.set_param("party_cohesion", coh)


def preview_layers(
    state: Any,
    hypothetical_effects: List[Dict[str, Any]],
    causal_net: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Evaluate the Three-Layer Goal System impact of a set of effects (M04 / M15 B-15-02).
    Returns deltas across:
      - layer1_goals (Grand Vision & Campaign Promises)
      - layer2_corridors (Party Ideological Corridor, Standing & Faction Cohesion)
      - layer3_survival (Immediate Coalition Stability, Budget/FX & Public Security)
      - tension_axes (List of opposing layer pairs)
    """
    sim_after = state.clone()
    executor = EffectExecutor(causal_net)
    executor.apply_effects(sim_after, hypothetical_effects, source="preview_layers")
    step_11_m04_party_monthly(sim_after, executor)

    # Layer 1: Vision & Promises
    v_delta = sim_after.get_param("vision_progress") - state.get_param("vision_progress")
    pr_before = sum(float(v) for v in state.params.get("promise_progress", {}).values())
    pr_after = sum(float(v) for v in sim_after.params.get("promise_progress", {}).values())
    pr_delta = pr_after - pr_before
    terr_delta = (sim_after.settler_population_total() - state.settler_population_total()) / 2000.0
    l1_net = v_delta + pr_delta * 0.5 + terr_delta

    # Layer 2: Party Corridor, Standing & Cohesion
    st_delta = sim_after.get_param("party_standing") - state.get_param("party_standing")
    coh_delta = sim_after.get_param("party_cohesion") - state.get_param("party_cohesion")
    dev_before = sum(float(v) for v in state.params.get("stance_deviation", {}).values()) if isinstance(state.params.get("stance_deviation"), dict) else state.get_param("stance_deviation")
    dev_after = sum(float(v) for v in sim_after.params.get("stance_deviation", {}).values()) if isinstance(sim_after.params.get("stance_deviation"), dict) else sim_after.get_param("stance_deviation")
    dev_delta = dev_after - dev_before
    l2_net = st_delta + coh_delta * 0.5 - dev_delta * 0.8

    # Layer 3: Immediate Survival (Coalition satisfaction, Voter support, Security, US relations, Economy)
    ally_before = sum(float(v) for v in state.params.get("ally_satisfaction", {}).values()) / max(1, len(state.params.get("ally_satisfaction", {})))
    ally_after = sum(float(v) for v in sim_after.params.get("ally_satisfaction", {}).values()) / max(1, len(sim_after.params.get("ally_satisfaction", {})))
    sec_delta = sim_after.get_param("public_security") - state.get_param("public_security")
    us_delta = sim_after.get_param("us_admin_relation") - state.get_param("us_admin_relation")
    intl_delta = sim_after.get_param("intl_legitimacy") - state.get_param("intl_legitimacy")
    fx_delta = sim_after.get_param("fx_reserves") - state.get_param("fx_reserves")
    inf_delta = sim_after.get_param("inflation") - state.get_param("inflation")
    l3_net = (ally_after - ally_before) * 0.4 + sec_delta * 0.35 + us_delta * 0.25 + intl_delta * 0.20 + fx_delta * 0.2 - inf_delta * 0.15

    tensions: List[str] = []
    if l1_net * l3_net < -0.05:
        tensions.append("vision_vs_survival")
    if l1_net * l2_net < -0.05:
        tensions.append("vision_vs_party_corridor")
    if l2_net * l3_net < -0.05:
        tensions.append("party_corridor_vs_survival")

    return {
        "layer1_goals": {"net_delta": quantize(l1_net), "vision_delta": quantize(v_delta), "promise_delta": quantize(pr_delta)},
        "layer2_corridors": {"net_delta": quantize(l2_net), "standing_delta": quantize(st_delta), "deviation_delta": quantize(dev_delta)},
        "layer3_survival": {"net_delta": quantize(l3_net), "ally_delta": quantize(ally_after - ally_before), "security_delta": quantize(sec_delta), "us_delta": quantize(us_delta)},
        "tension_axes": tensions,
        "has_tension": len(tensions) > 0,
    }


# ============================================================================
# Step 13, Step 14 & Step 15: M11 Trilemma, M13 Authoritarian, M05 PC Income
# ============================================================================

def step_13_m11_regions_monthly(state: Any, executor: EffectExecutor) -> None:
    """Step 13 (M11): Monthly regional settler population growth and Trilemma vertices."""
    if state.region_exists("west_bank"):
        sp_pol = state.get_param("settlement_policy", "west_bank")
        growth = max(0.0, (sp_pol - 20.0) * 4.5)
        state.add_param("settler_population", growth, "west_bank")


def step_14_m13_authoritarian_monthly(state: Any, executor: EffectExecutor) -> None:
    """Step 14 (M13): Monthly centralization stage (C1-C5), institutional resistance, coup/assassination risk."""
    cent = state.get_param("centralization")
    rol = state.get_param("rule_of_law")
    state.m14["peak_centralization_tenure"] = max(float(state.m14.get("peak_centralization_tenure", 0.0)), cent)

    if cent >= 80.0:
        stage = 4  # C5
        state.m13["survival_mode_active"] = True
    elif cent >= 65.0:
        stage = 3  # C4
    elif cent >= 50.0:
        stage = 2  # C3
    elif cent >= 35.0:
        stage = 1  # C2
    else:
        stage = 0  # C1
    state.m13["stage"] = stage

    if cent > 55.0 and rol < 45.0:
        state.add_param("coup_risk", (cent - 55.0) * 0.08)
        state.add_param("assassination_risk", (cent - 50.0) * 0.05)


def step_15_m05_pc_and_snapshots(state: Any, executor: EffectExecutor) -> None:
    """Step 15 (M05 & M01): Monthly political capital generation and 12-month ring buffer snapshot."""
    standing = state.get_param("party_standing")
    seats = state.get_param("coalition_seats")
    base_pc = 12.0 + (standing - 50.0) * 0.1 + (seats - 61.0) * 0.15 + state.mod_factor("pc_income")
    cur_pc = state.get_param("political_capital")
    if cur_pc < 92.0:
        state.add_param("political_capital", max(2.0, base_pc * 0.35))

    # Append monthly snapshot to history.series
    dates = state.history["series"].setdefault("dates", [])
    dates.append(state.date_str)
    metrics = state.history["series"].setdefault("metrics", {})
    for k_metric in ("inflation", "fx_reserves", "budget_balance", "public_security", "deterrence", "party_standing", "coalition_seats", "rule_of_law"):
        arr = metrics.setdefault(k_metric, [])
        arr.append(state.get_param(k_metric))


# ============================================================================
# Step 18: M12 Event Engine (Fixed Historical, Scheduled & Random Events)
# ============================================================================

def step_18_m12_events_daily(state: Any, executor: EffectExecutor) -> List[Dict[str, Any]]:
    """Step 18 (M12): Scan scheduled events, fixed historical events, and random events."""
    rng_ev = state.rng.stream("events")
    rng_rand = state.rng.stream("random_events")
    triggered: List[Dict[str, Any]] = []

    # 18.0: Release scheduled events due today
    rem_sched = []
    for s_item in state.m12.get("scheduled", []):
        if int(s_item.get("due_day", 0)) <= state.day_index:
            ev_id = s_item.get("event_id", "")
            ev_def = state.registry.events_by_id.get(ev_id)
            if ev_def and ev_id not in state.m12["fired"]:
                inst = _instantiate_event(state, ev_def, source="scheduled")
                state.m12["queue"].append(inst)
                triggered.append(inst)
        else:
            rem_sched.append(s_item)
    state.m12["scheduled"] = rem_sched

    # 18.2: Scan fixed historical events in data/events/fixed_1977_1992.yaml
    for ev_def in state.registry.fixed_events:
        ev_id = ev_def["id"]
        if ev_id in state.m12["fired"] and not bool(ev_def.get("repeatable", False)):
            continue
        if any(q.get("id") == ev_id for q in state.m12["queue"]):
            continue
        if not _check_event_trigger(state, ev_def):
            continue
        trig = ev_def.get("trigger", {})
        prob_cfg = trig.get("probability", {}) if isinstance(trig, dict) else {}
        base_p = float(prob_cfg.get("base", 1.0)) if isinstance(prob_cfg, dict) else 1.0
        period = str(prob_cfg.get("period", "day")) if isinstance(prob_cfg, dict) else "day"
        daily_p = base_p / 30.0 if period == "month" else (base_p / 7.0 if period == "week" else base_p)
        daily_p *= float(state.m12["multipliers"].get(ev_id, 1.0))
        if rng_ev.chance(min(1.0, daily_p)):
            inst = _instantiate_event(state, ev_def, source="fixed")
            state.m12["queue"].append(inst)
            triggered.append(inst)
            break

    # 18.3: Sample random events when queue is empty
    if not state.m12["queue"] and state.m12.get("month_random_count", 0) < 2:
        if rng_rand.chance(0.05):
            candidates: List[Tuple[Dict[str, Any], float]] = []
            for rev in state.registry.random_events:
                rev_id = rev["id"]
                if int(state.m12.get("cooldown_until", {}).get(rev_id, 0)) > state.day_index:
                    continue
                if _check_event_trigger(state, rev):
                    w = float(rev.get("weight", 10.0)) * float(state.m12["multipliers"].get(rev_id, 1.0))
                    if w > 0:
                        candidates.append((rev, w))
            if candidates:
                evs = [c[0] for c in candidates]
                ws = [c[1] for c in candidates]
                chosen = rng_rand.weighted_pick(evs, ws)
                if chosen:
                    state.m12["month_random_count"] = int(state.m12.get("month_random_count", 0)) + 1
                    inst = _instantiate_event(state, chosen, source="random")
                    state.m12["queue"].append(inst)
                    triggered.append(inst)

    return triggered


def _check_event_trigger(state: Any, ev_def: Dict[str, Any]) -> bool:
    trig = ev_def.get("trigger", {})
    if not isinstance(trig, dict):
        return True
    win = trig.get("window", {})
    if isinstance(win, dict):
        w_from = win.get("from")
        w_to = win.get("to")
        if w_from and state.date_str < str(w_from):
            return False
        if w_to and state.date_str > str(w_to):
            return False
    inv = trig.get("invalidation")
    if inv and eval_bool(inv, state):
        return False
    pre = trig.get("prerequisites")
    if pre and not eval_bool(pre, state):
        return False
    cond = trig.get("condition")
    if cond and not eval_bool(cond, state):
        return False
    return True


def _instantiate_event(state: Any, ev_def: Dict[str, Any], source: str = "fixed") -> Dict[str, Any]:
    ev_id = ev_def["id"]
    state.m12["status"][ev_id] = "ACTIVE"
    opts = []
    for idx, opt in enumerate(ev_def.get("options", []) or []):
        req = opt.get("requires") or opt.get("condition")
        if req and not eval_bool(req, state):
            continue
        opts.append({
            "id": str(opt.get("id", chr(ord("A") + idx))),
            "title": str(opt.get("title", opt.get("label", f"Option {idx+1}"))),
            "historical": bool(opt.get("historical", False)),
            "tags": list(opt.get("tags", [])),
            "effects": list(opt.get("effects", [])),
        })
    if not opts:
        opts.append({
            "id": "A",
            "title": "确认",
            "historical": True,
            "tags": [],
            "effects": list(ev_def.get("immediate_effects", ev_def.get("effects", [])) or []),
        })
    return {
        "id": ev_id,
        "title": str(ev_def.get("title", ev_id)),
        "kind": str(ev_def.get("kind", source)),
        "day_index": state.day_index,
        "date": state.date_str,
        "immediate_effects": list(ev_def.get("immediate_effects", []) or []),
        "options": opts,
        "cooldown_days": int(ev_def.get("cooldown_days", 180) or 180),
    }


def resolve_event_option(
    state: Any,
    event_id: str,
    option_id: Optional[str],
    executor: EffectExecutor,
) -> Dict[str, Any]:
    """Resolve an active event in `state.m12['queue']` with `option_id`."""
    queue = state.m12.get("queue", [])
    idx = next((i for i, e in enumerate(queue) if e.get("id") == event_id), -1)
    if idx < 0:
        return {"ok": False, "error": f"Event {event_id} not in queue"}

    ev = queue.pop(idx)
    if ev.get("immediate_effects"):
        executor.apply_effects(state, ev["immediate_effects"], source=f"event:{event_id}:imm", rng_stream_name="events")

    opts = ev.get("options", [])
    chosen = opts[0] if opts else {"id": "A", "effects": []}
    if option_id is not None:
        for o in opts:
            if str(o.get("id")) == str(option_id):
                chosen = o
                break

    applied = executor.apply_effects(
        state,
        chosen.get("effects", []),
        source=f"event:{event_id}:{chosen.get('id')}",
        rng_stream_name="events",
    )
    state.m12["status"][event_id] = "RESOLVED"
    state.m12["fired"][event_id] = {"day_index": state.day_index, "date": state.date_str, "choice": chosen.get("id", "A")}
    state.m12["counts_game"][event_id] = int(state.m12["counts_game"].get(event_id, 0)) + 1
    state.m12["counts_term"][event_id] = int(state.m12["counts_term"].get(event_id, 0)) + 1
    state.m12["cooldown_until"][event_id] = state.day_index + int(ev.get("cooldown_days", 180))

    state.history["event_log"].append({
        "day_index": state.day_index,
        "date": state.date_str,
        "event_id": event_id,
        "option_id": chosen.get("id", "A"),
    })
    return {"ok": True, "event_id": event_id, "option_id": chosen.get("id", "A"), "applied": applied}


# ============================================================================
# Step 20: M14 Tenure & Ending Conditions + 8-Dimension Evaluation
# ============================================================================

ENDING_PRIORITY = [
    "state_collapse",
    "assassination",
    "coup",
    "death",
    "overthrow",
    "health_incapacity",
    "primary_loss",
    "no_confidence",
    "coalition_failure",
    "election_loss",
    "resignation",
    "player_quit",
]


def step_20_m14_endings(state: Any, executor: EffectExecutor) -> Optional[str]:
    """Step 20 (M14): Check hard collapse, coup, health, and tenure ending conditions."""
    if state.run.get("phase") == "ENDED":
        return state.m14.get("ending_id")

    candidates: List[str] = []
    if state.pending.get("tenure_end"):
        candidates.append(str(state.pending["tenure_end"]))

    # State collapse check (hyperinflation + zero FX + low stability)
    if state.get_param("fx_reserves") <= 1.0 and state.get_param("inflation") >= 400.0 and state.get_param("public_security") <= 15.0:
        state.m14["collapse_danger_streak_days"] = int(state.m14.get("collapse_danger_streak_days", 0)) + 1
        if state.m14["collapse_danger_streak_days"] >= 30:
            candidates.append("state_collapse")
    else:
        state.m14["collapse_danger_streak_days"] = 0

    # Leader health check
    leader = state.player.get("leader_id", "begin")
    if state.get_param("health", leader) <= 0.0:
        candidates.append("health_incapacity")

    if candidates:
        candidates.sort(key=lambda c: ENDING_PRIORITY.index(c) if c in ENDING_PRIORITY else 99)
        chosen_reason = candidates[0]
        state.pending["tenure_end"] = chosen_reason
        state.run["phase"] = "ENDED"
        state.meta["completed"] = True
        state.m14["ending_id"] = chosen_reason
        state.m14["final_evaluation"] = compute_final_evaluation(state, chosen_reason)
        return chosen_reason

    return None


def compute_final_evaluation(state: Any, end_reason: str = "resignation") -> Dict[str, Any]:
    """Compute M14 8-Dimension Historical Evaluation and 3 Historian Schools commentary."""
    d_sec = clamp(0.45 * state.get_param("public_security") + 0.35 * state.get_param("deterrence") + 0.20 * state.get_param("readiness"), 0.0, 100.0)
    d_econ = clamp(0.40 * max(0.0, 100.0 - state.get_param("inflation") * 0.4) + 0.30 * state.get_param("fx_reserves") + 0.30 * min(100.0, (state.get_param("growth") + 5.0) * 8.0), 0.0, 100.0)
    d_dip = clamp(0.45 * state.get_param("us_admin_relation") + 0.35 * state.get_param("intl_legitimacy") + 0.20 * (state.count_peace_treaties() * 35.0), 0.0, 100.0)
    d_dem = clamp(0.65 * state.get_param("rule_of_law") + 0.35 * (100.0 - state.get_param("centralization")), 0.0, 100.0)
    d_coh = clamp(100.0 - 0.5 * state.get_param("alienation", "mizrahi") - 0.5 * state.get_param("judicial_conflict"), 0.0, 100.0)
    d_terr = clamp(min(100.0, state.settler_population_total() / 1200.0), 0.0, 100.0)
    d_gov = clamp(0.55 * state.get_param("party_standing") + 0.45 * state.get_param("party_cohesion"), 0.0, 100.0)
    d_leg = clamp(0.50 * state.get_param("vision_progress") + 0.50 * (d_sec + d_dip) * 0.5, 0.0, 100.0)

    dims = {
        "security": quantize(d_sec),
        "economy": quantize(d_econ),
        "diplomacy": quantize(d_dip),
        "democracy": quantize(d_dem),
        "social_cohesion": quantize(d_coh),
        "territory": quantize(d_terr),
        "governance": quantize(d_gov),
        "legacy": quantize(d_leg),
    }
    overall = quantize(sum(dims.values()) / len(dims))
    state.set_param("historical_rating", overall)

    schools = {
        "traditional_zionist": quantize(0.40 * d_sec + 0.35 * d_terr + 0.25 * d_leg),
        "critical_new_historians": quantize(0.40 * d_dem + 0.35 * d_dip + 0.25 * d_coh),
        "institutional_realpolitik": quantize(0.40 * d_econ + 0.35 * d_gov + 0.25 * d_dip),
    }

    return {
        "end_reason": end_reason,
        "end_date": state.date_str,
        "days_elapsed": state.day_index,
        "overall_score": overall,
        "dimensions": dims,
        "historian_schools": schools,
        "achievements": list(state.m14.get("unlocked_achievements_this_run", [])),
    }
