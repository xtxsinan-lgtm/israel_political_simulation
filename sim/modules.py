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
    if isinstance(state.params.get("stance_deviation"), dict):
        dev = sum(float(v) for v in state.params["stance_deviation"].values()) * 0.25
    if param == "party_standing":
        prestige = (10.0 if state.count_peace_treaties() >= 1 else 0.0) + max(0.0, state.get_param("public_security") - 60.0) * 0.2
        return prestige - 0.15 * max(0.0, dev - 5.0)
    if param == "faction_mood":
        return -0.15 * max(0.0, dev - 5.0)
    if param == "challenger_strength":
        return 0.12 * max(0.0, dev - 10.0)
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
        econ_mod = state.get_param("economic_model")
        # Post-1985 Stabilization Plan / New Shekel regime: anchor inflation into 15%-30% band
        if state.m10.get("stabilization_plan_active") or state.has_modifier("new_shekel") or state.m10.get("indexation_removed"):
            return max(-5.0, min(5.0, (-bb - 1.5) * 1.1 - max(0.0, econ_mod) * 0.08))
        deficit_stress = max(0.0, -bb - 1.5)
        war_stress = 16.0 if (state.at_war() or state.has_modifier("lebanon_quagmire")) else 0.0
        bailout_stress = 32.0 if state.has_flag("bank_nationalization") else 0.0
        corridor_by_year = {
            1977: 44.0,
            1978: 56.0,
            1979: 82.0,
            1980: 115.0,
            1981: 112.0,
            1982: 138.0,
            1983: 275.0,
            1984: 345.0,
        }
        base_corridor = corridor_by_year.get(state.year, 330.0 if state.year >= 1985 else 44.0)
        hist_corridor = base_corridor + deficit_stress * 5.5 + war_stress + bailout_stress
        if econ_mod >= 15.0 and bb >= -1.8:
            hist_corridor *= 0.62
        target_inf = clamp(hist_corridor, 25.0, 375.0)
        return (target_inf - 35.0) + 0.45 * (target_inf - inf)
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


def get_available_actions(state: Any, ignore_pc: bool = False) -> List[Dict[str, Any]]:
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
        if not ignore_pc and pc_cost > pc:
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
                act_args[arg_k] = (state.promises[0].get("id") or state.promises[0].get("promise_id") or "peace_and_security") if state.promises else "peace_and_security"

    cost = adef.get("cost", {})
    pc_cost = 0.0
    if isinstance(cost, dict):
        pc_cost = float(cost.get("pc", 0.0)) * state.mod_factor("pc_cost")
        if free_slot:
            pc_cost *= 0.70
        cur_pc = state.get_param("political_capital")
        if cur_pc < pc_cost:
            # Allow IOU-backed execution if within 10 PC and IOU ledger has capacity (< 3)
            iou_list = state.m05.setdefault("iou_ledger", [])
            if cur_pc + 10.0 >= pc_cost and len(iou_list) < 3:
                iou_list.append({"day": state.day_index, "action_id": action_id, "amount": pc_cost - cur_pc})
                state.set_param("political_capital", 0.0)
                pc_cost = 0.0
            else:
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
    old_t = tiers[cur_idx] if 0 <= cur_idx < len(tiers) and isinstance(tiers[cur_idx], dict) else {}
    new_t = tiers[new_idx] if 0 <= new_idx < len(tiers) and isinstance(tiers[new_idx], dict) else {}
    em_delta = float(new_t.get("em", 0.0)) - float(old_t.get("em", 0.0))
    rsq_delta = float(new_t.get("rsq", 0.0)) - float(old_t.get("rsq", 0.0))
    if abs(em_delta) > 1e-6:
        state.add_param("economic_model", em_delta)
    if abs(rsq_delta) > 1e-6:
        state.add_param("religious_status_quo", rsq_delta)
    if new_t.get("flag"):
        state.set_flag(str(new_t["flag"]), source=f"policy:{policy_id}")
    if new_t.get("mod"):
        state.add_modifier(str(new_t["mod"]), duration_days=None, source=f"policy:{policy_id}")

    pstate["tier_idx"] = new_idx
    pstate["cooldown_until_day"] = state.day_index + int(pol_def.get("cd", 60))
    new_lv = tier_vals[new_idx]
    state.set_param("policy_level", new_lv, policy_id)
    if policy_id == "settlement_policy":
        for rk in ("west_bank", "gaza", "golan"):
            state.set_param("settlement_policy", new_lv, rk)
    elif policy_id == "region_land_policy":
        for rk in ("galilee", "triangle", "negev"):
            state.set_param("region_land_policy", new_lv, rk)
    elif policy_id in ("exemption_coverage", "outpost_enforcement"):
        state.set_param(policy_id, new_lv)
    state.recompute_gov_axis_position()
    return {"ok": True, "policy_id": policy_id, "tier_idx": new_idx, "level": new_lv}


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
            cas = rng.range_int(1, 5)
            aw["casualties"] = int(aw.get("casualties", 0)) + cas
            f["cumulative_casualties"] = int(f.get("cumulative_casualties", 0)) + cas
            state.m02["one_off_flows"]["budget_balance"] = float(state.m02["one_off_flows"].get("budget_balance", 0.0)) - 0.015
            if state.day_index - int(aw.get("start_day", 0)) > 60:
                f["quagmire_months"] = max(int(f.get("quagmire_months", 0)), (state.day_index - int(aw.get("start_day", 0))) // 30)
        elif fid == "lebanon" and state.has_modifier("lebanon_quagmire"):
            if state.day == 1:
                f["quagmire_months"] = int(f.get("quagmire_months", 0)) + 1
                f["cumulative_casualties"] = int(f.get("cumulative_casualties", 0)) + 18


def step_08_weekly_security(state: Any, executor: EffectExecutor) -> None:
    """Step 8 (M11 -> M09 -> M08): Weekly regional security & public_security update."""
    rng = state.rng.stream("combat")
    core_regions = ("galilee", "haifa", "tel_aviv", "triangle", "jerusalem", "negev")
    sec_sum = 0.0
    for r in core_regions:
        r_sec = state.get_param("region_security", r)
        # Soft mean reversion so region_security never pins at 0 or 100
        if r_sec < 35.0:
            state.add_param("region_security", 0.4, r)
        elif r_sec > 90.0:
            state.add_param("region_security", -0.3, r)
        sec_sum += state.get_param("region_security", r)
    avg_core_sec = sec_sum / len(core_regions)

    det = state.get_param("deterrence")
    pal_host = state.get_param("pal_hostility")
    quag_pen = 5.0 if state.has_modifier("lebanon_quagmire") else 0.0
    target_pub_sec = clamp(0.55 * avg_core_sec + 0.35 * det - 0.15 * max(0.0, pal_host - 50.0) - quag_pen, 18.0, 92.0)
    cur_pub_sec = state.get_param("public_security")
    state.set_param("public_security", cur_pub_sec + 0.15 * (target_pub_sec - cur_pub_sec))

    # M08 armed incident check when pal_hostility is high
    if pal_host > 65.0 and rng.chance((pal_host - 60.0) / 220.0):
        state.add_param("public_security", -1.2)
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

    # Historical world track progressions (Iraq Osirak reactor, Iran 1979 revolution, Ethiopia 1991)
    if state.date_str <= "1981-12-31" and "E-1981-06a" not in state.m12.get("fired", {}):
        cur_nuc = state.get_param("enemy_nuclear_progress", "iraq")
        if cur_nuc < 92.0:
            state.set_param("enemy_nuclear_progress", min(92.0, cur_nuc + 1.15), "iraq")

    if "1978-06-01" <= state.date_str <= "1979-03-01" and "E-1979-02" not in state.m12.get("fired", {}):
        state.set_param("regime_stability", 15.0, "iran")

    if state.year >= 1990 and "E-1991-05" not in state.m12.get("fired", {}):
        state.set_param("regime_stability", 12.0, "ethiopia")

    if state.year >= 1989:
        state.add_param("power_relation", 1.5, "ussr")
        state.set_param("regime_stability", min(38.0, state.get_param("regime_stability", "egypt")), "egypt")

    # Diplomatic spillover: if dovish territorial policy + autonomy_progress + US relations are strong, Jordan hostility declines
    autonomy = state.get_param("autonomy_progress")
    us_rel = state.get_param("us_admin_relation")
    settler_mom = state.get_param("settler_momentum")
    terr_axis = float(state.params.get("gov_axis_position", {}).get("territory", 25.0))
    if (state.has_flag("autonomy_framework_signed") or autonomy >= 20.0) and terr_axis <= 0.0 and us_rel >= 58.0 and settler_mom <= 46.0:
        state.add_param("autonomy_progress", 0.9)
        state.add_param("pal_living_standard", 0.4)
        state.add_param("pal_hostility", -0.5)
        state.add_param("regime_hostility", -1.0, "jordan")
        if state.get_param("regime_hostility", "jordan") <= 20.0:
            state.set_param("peace_treaty_state", 3.0, "jordan")
    elif state.year >= 1980 and terr_axis >= 10.0 and autonomy < 25.0:
        state.set_flag("autonomy_stagnant", source="M08")

    # 12b: M08 Palestinian uprising risk & Intifada progression
    pal_host = state.get_param("pal_hostility")
    autonomy = state.get_param("autonomy_progress")

    drift = 0.06 * max(0.0, pal_host - 46.0) + 0.04 * max(0.0, settler_mom - 42.0) - 0.03 * max(0.0, autonomy - 15.0)
    if state.year >= 1985 and terr_axis >= 5.0 and autonomy < 28.0:
        drift += 0.45
    state.add_param("uprising_risk", drift)

    up_state = state.m08.get("uprising_state", {})
    if state.get_param("uprising_risk") >= 75.0 and not up_state.get("active") and state.year >= 1987:
        up_state["active"] = True
        up_state["intensity"] = 60.0
        state.set_flag("intifada_active", source="M08")
        if not state.m08["faction_active"].get("hamas"):
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
            state.add_param("party_standing", -1.0)


# ============================================================================
# Step 7 & Step 19: M03 Parliament, Polls, Coalition & Elections
# ============================================================================

def step_07_m03_parliament_weekly(state: Any, executor: EffectExecutor) -> None:
    """Step 7 (M03): Weekly polls, bloc support, and monthly coalition fatigue."""
    rng = state.rng.stream("politics")
    # Small weekly PC drip so players/bots are not starved between months
    if state.get_param("political_capital") < 85.0:
        state.add_param("political_capital", 1.5)

    # 7a: First Sunday of the month -> monthly coalition maintenance
    if state.day <= 7:
        state.add_param("months_to_election", -1.0)
        elections_won = int(state.run.get("tenure_elections_won", 0))
        # Governing fatigue accelerates in later terms (Metric S1)
        fatigue_step = 0.22 + 0.22 * elections_won
        state.add_param("govt_fatigue", fatigue_step)
        if state.get_param("months_to_election") <= 0.0 and not state.m13.get("survival_mode_active"):
            state.pending["vote_requests"].append({
                "type": "election",
                "due_day": state.day_index + 7,
                "source": "scheduled_term_end",
            })

    # 7b: Weekly poll noise around bloc_support & governing fatigue
    standing = state.get_param("party_standing")
    pub_sec = state.get_param("public_security")
    inf = state.get_param("inflation")
    fatigue = state.get_param("govt_fatigue")
    elections_won = int(state.run.get("tenure_elections_won", 0))
    term_drag = max(0.0, (elections_won - 1) * 4.2) + fatigue * 0.14
    peace_div = (6.8 if state.count_peace_treaties() >= 1 else 0.0) + max(0.0, state.get_param("intl_legitimacy") - 55.0) * 0.18
    base_likud = clamp(
        41.5 + (standing - 60.0) * 0.22 + (pub_sec - 60.0) * 0.15 + peace_div - max(0.0, inf - 95.0) * 0.020 - term_drag,
        18.0,
        56.0,
    )
    poll_likud = clamp(base_likud + rng.uniform(-1.5, 1.5), 15.0, 60.0)
    poll_labor = clamp(40.0 - (poll_likud - 40.0) * 0.65 + term_drag * 0.35 + rng.uniform(-1.5, 1.5), 15.0, 58.0)
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
                elections_won = int(state.run.get("tenure_elections_won", 0))
                election_idx = int(state.run.get("elections_contested", 0)) + 1
                state.run["elections_contested"] = election_idx
                # Track election stats by term index for Metric S1
                el_hist = state.m03.setdefault("election_history", [])
                if election_idx == 1:
                    fatigue_pen = state.get_param("govt_fatigue") * 0.06
                elif election_idx == 2:
                    fatigue_pen = 2.8 + state.get_param("govt_fatigue") * 0.12
                else:
                    fatigue_pen = 7.5 + (election_idx - 2) * 3.8 + state.get_param("govt_fatigue") * 0.18
                lead = state.get_param("poll_lead") - fatigue_pen + rng.uniform(-2.8, 2.8)
                if state.has_flag("peace_decompression_mode") and election_idx <= 2:
                    lead = max(lead, 2.5)
                won = lead >= -2.5
                el_hist.append({
                    "election_index": election_idx,
                    "day_index": state.day_index,
                    "date": state.date_str,
                    "lead": quantize(lead),
                    "won": won,
                })
                if won:
                    new_seats = clamp(round(43.0 + lead * 0.5), 32.0, 55.0)
                    state.set_param("knesset_seats", new_seats, p_party)
                    state.set_param("coalition_seats", max(62.0, new_seats + 22.0))
                    state.set_param("months_to_election", 48.0)
                    # Retain cumulative governing fatigue floor on re-election (Metric S1)
                    state.set_param("govt_fatigue", min(68.0, 9.5 * (elections_won + 1)))
                    state.run["tenure_elections_won"] = elections_won + 1
                    state.history["turning_points"].append({
                        "day_index": state.day_index,
                        "date": state.date_str,
                        "title_zh": f"{state.year}年议会大选连任胜选",
                        "summary_zh": f"执政党赢得第{election_idx}次连任大选，获得{int(new_seats)}席。",
                        "weight": 80.0,
                        "category": "election",
                    })
                else:
                    state.set_param("months_to_election", 48.0)
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
    tanzi = max(0.0, (inf - 35.0) * 0.012)
    if state.m10.get("stabilization_plan_active") or state.has_modifier("new_shekel"):
        tanzi = 0.0
        pol_delta = max(pol_delta, 0.8)
    target_bb = clamp(-2.0 + pol_delta + one_off - tanzi, -18.0, 12.0)
    cur_bb = state.get_param("budget_balance")
    state.set_param("budget_balance", cur_bb + 0.25 * (target_bb - cur_bb))

    # Keep FX reserves away from hard 0/100 pinning via soft US aid / imports damping
    fx = state.get_param("fx_reserves")
    if fx < 12.0 and state.get_param("us_admin_relation") >= 40.0:
        state.add_param("fx_reserves", 2.2)
    elif fx > 88.0:
        state.add_param("fx_reserves", -1.8)

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
    # Post-1985 automatic stabilization fallback if E-1985-07 window passed or emergency stabilization enacted
    if state.date_str >= "1986-04-01" and inf >= 150.0 and not state.has_modifier("new_shekel") and state.get_param("centralization") < 55.0:
        state.add_modifier("new_shekel", duration_days=None, source="M10_stabilization")
        state.m10["stabilization_plan_active"] = True
        state.m10["stabilization_months_left"] = 24
        state.m02["shock_mem"].pop("inflation", None)
        state.set_param("inflation", 23.5)
        state.add_param("budget_balance", 3.5)
        state.add_param("fx_reserves", 10.0)
    elif state.has_modifier("new_shekel") or state.m10.get("stabilization_plan_active"):
        state.m02["shock_mem"].pop("inflation", None)
        # Smoothly guide post-1985 inflation into the 15%-30% historical band
        if inf > 27.5:
            state.set_param("inflation", max(19.5, 22.0 + (inf - 22.0) * 0.25))
        elif inf < 17.0:
            state.set_param("inflation", 19.5 + max(0.0, -bb) * 0.5)
    elif inf >= 120.0 and bb <= -8.0:
        state.add_param("inflation", max(2.0, (-bb - 6.0) * 0.8))


def step_17_yearly(state: Any, causal_net: Any, executor: EffectExecutor) -> None:
    """Step 17 (M10/M06/M11): Annual budget cycle, character aging, demographic growth, and yearly CausalNet nodes."""
    causal_net.step_nodes(state, tick_filter="yearly")
    state.m10["budget_cycle"]["fiscal_year"] = state.year


# ============================================================================
# Step 11: M04 Party Internal, Corridors, Promises & Three-Layer Preview
# ============================================================================

def _get_party_corridor_bounds(state: Any, axis: str) -> Tuple[float, float]:
    party = state.player.get("party_id", "likud")
    raw_corr = state.registry.corridors_raw
    parties_cfg = state.corridors.get("parties") or raw_corr.get("parties", {})
    factions_cfg = state.corridors.get("factions") or raw_corr.get("factions", {})
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
    """Step 11 (M04): Compute stance_deviation vs party corridor, PM health/stress, promises, and vision."""
    gov_pos = state.recompute_gov_axis_position()
    tenure_m = max(0, (state.day_index - int(state.run.get("tenure_start_day", 0))) // 30)
    grace_mult = 0.0 if tenure_m < 6 else (min(1.0, (tenure_m - 6) / 18.0))

    total_dev = 0.0
    eff_dev_sum = 0.0
    for ax in ("territory", "security", "economy", "religion", "foreign"):
        pos = float(gov_pos.get(ax, 0.0))
        lo, hi = _get_party_corridor_bounds(state, ax)
        dev_ax = 0.0
        if pos < lo:
            dev_ax = lo - pos
        elif pos > hi:
            dev_ax = pos - hi
        total_dev += dev_ax
        eff_ax = min(16.0, dev_ax * 0.32 * grace_mult)
        eff_dev_sum += eff_ax
        state.set_param("stance_deviation", eff_ax, ax)

    in_corr = (eff_dev_sum <= 7.5) and (total_dev <= 36.0)
    state.party_state["in_corridor"] = in_corr
    state.m14["corridor_months_total"] = int(state.m14.get("corridor_months_total", 0)) + 1
    if in_corr:
        state.m14["corridor_months_inside"] = int(state.m14.get("corridor_months_inside", 0)) + 1

    # Recompute party_cohesion as weighted faction_mood average
    fm = state.params.get("faction_mood", {})
    fw = state.params.get("faction_weight", {})
    if isinstance(fm, dict) and isinstance(fw, dict) and fm:
        w_sum = sum(float(fw.get(k, 25.0)) for k in fm) or 100.0
        coh = sum(float(fm[k]) * float(fw.get(k, 25.0)) for k in fm) / w_sum
        state.set_param("party_cohesion", clamp(coh, 15.0, 92.0))

    if state.get_param("party_standing") < 48.0:
        state.add_param("party_standing", 4.5 + (3.0 if state.count_peace_treaties() >= 1 else 0.0))
    elif state.get_param("party_standing") > 92.0:
        state.add_param("party_standing", -2.5)

    # Update PM stress and health trajectory (Begin 1983 high-stress exit vs post-1985 peace survival)
    leader = state.player.get("leader_id", "begin")
    cur_health = state.get_param("health", leader)
    cur_stress = state.get_param("character_stress", leader)
    sec_axis = float(gov_pos.get("security", 0.0))
    terr_axis = float(gov_pos.get("territory", 0.0))
    quag = (
        not state.has_flag("peace_decompression_mode")
        and (
            state.has_modifier("lebanon_quagmire")
            or state.has_modifier("sabra_shatila_stigma")
            or state.at_war()
            or ("E-1982-06a" in state.m12.get("fired", {}) and state.m12["fired"]["E-1982-06a"].get("choice") == "B")
            or (state.year >= 1982 and sec_axis >= 10.0)
        )
    )
    if leader == "begin" and state.date_str >= "1982-11-15" and not state.has_modifier("silent_pm") and quag:
        state.add_modifier("silent_pm", duration_days=None, source="E-1982-11")
    silent = state.has_modifier("silent_pm") or ("E-1982-11" in state.m12.get("fired", {}))
    inf = state.get_param("inflation")
    treaties = state.count_peace_treaties()
    peace_decompression = state.has_flag("peace_decompression_mode") or (
        not quag
        and sec_axis <= 6.0
        and (state.year < 1979 or treaties >= 1 or state.get_param("autonomy_progress") >= 10.0 or terr_axis <= -15.0)
    )

    target_stress = 18.0
    if quag:
        target_stress += 32.0
    if silent and leader == "begin" and quag:
        target_stress += 28.0
    if inf >= 110.0 and not peace_decompression:
        target_stress += 16.0
    if peace_decompression:
        target_stress = 15.0
    new_stress = clamp(cur_stress + 0.30 * (target_stress - cur_stress), 10.0, 96.0)
    state.set_param("character_stress", new_stress, leader)

    if leader == "begin":
        if peace_decompression:
            base_drain = 0.21
            stress_drain = 0.0
            if state.has_flag("peace_decompression_mode"):
                state.add_param("public_approval", 2.5)
                state.add_param("poll_lead", 2.0)
        else:
            base_drain = 0.36
            stress_drain = max(0.0, (new_stress - 48.0) * 0.032)
            if state.year >= 1982 and (quag or inf >= 120.0):
                stress_drain += 0.95
            if silent and quag:
                stress_drain += 0.65
    else:
        base_drain = 0.16
        stress_drain = max(0.0, (new_stress - 55.0) * 0.018)
    new_health = clamp(cur_health - (base_drain + stress_drain), 0.0, 95.0)
    state.set_param("health", new_health, leader)

    # Historical August 1983 Begin resignation trigger when health & stress reach breaking point
    if leader == "begin" and "1983-06-01" <= state.date_str <= "1983-11-30" and new_health <= 34.0 and not peace_decompression:
        state.pending["tenure_end"] = "resignation"
    elif leader == "begin" and state.year >= 1986 and new_health <= 35.0 and peace_decompression:
        state.pending["tenure_end"] = "resignation"

    # Update Campaign Promises Progress (Layer 1)
    wb_settlers = state.get_param("settler_population", "west_bank")
    if wb_settlers >= 6000 or state.get_param("settler_momentum") >= 48.0:
        state.add_param("promise_progress", 1.2, "settle_eretz_israel")
    if state.get_param("economic_model") >= -25.0 or state.has_modifier("new_shekel"):
        state.add_param("promise_progress", 1.4, "economic_liberalization")
    if state.get_param("alienation", "mizrahi") <= 38.0 or state.get_param("region_development", "negev") >= 35.0:
        state.add_param("promise_progress", 1.3, "social_justice")
    if treaties >= 1 or (state.get_param("public_security") >= 62.0 and not quag):
        state.add_param("promise_progress", 1.5, "peace_and_security")

    prom_map = state.params.get("promise_progress", {})
    for pr in state.promises:
        if isinstance(pr, dict):
            pk = pr.get("id") or pr.get("key") or pr.get("promise_id") or ""
            if pk:
                pr["id"] = pk
                prog_val = float(prom_map.get(pk, pr.get("progress", 0.0)))
                pr["progress"] = prog_val
                if prog_val >= 80.0:
                    pr["status"] = "fulfilled"

    # Update Begin's Grand Vision ("begin_peace_in_eretz_israel") Milestones (Layer 3, calibrated to 8%-25%)
    if state.vision and state.vision.get("id") == "begin_peace_in_eretz_israel" and state.vision.get("status") != "achieved":
        ms_held = state.m04.setdefault("vision_held_months", {})
        m1_done = (
            state.has_flag("egypt_peace_treaty_signed")
            or state.has_flag("camp_david_signed")
            or ("E-1977-11" in state.m12.get("fired", {}) and state.m12["fired"]["E-1977-11"].get("choice") == "A")
            or ("E-1978-09" in state.m12.get("fired", {}) and state.m12["fired"]["E-1978-09"].get("choice") == "A")
            or state.get_param("peace_treaty_state", "egypt") >= 2.0
        )
        if m1_done:
            ms_held["m1_cairo"] = 12
        if m1_done and not state.at_war("egypt") and state.get_param("regime_hostility", "egypt") <= 55.0:
            ms_held["m2_rooted"] = int(ms_held.get("m2_rooted", 0)) + 1
        auto_ok = (
            (state.has_flag("autonomy_framework_signed") or m1_done or state.get_param("autonomy_progress") >= 8.0)
            and state.get_param("pal_hostility") <= 72.0
            and not state.has_flag("first_intifada_active")
        )
        if auto_ok:
            ms_held["m3_autonomy"] = int(ms_held.get("m3_autonomy", 0)) + 1
        jordan_ok = (
            not state.at_war("jordan")
            and state.get_param("regime_hostility", "jordan") <= 65.0
            and state.region_exists("west_bank")
            and state.settler_population_total() >= 52000
        )
        if jordan_ok:
            ms_held["m4_jordan"] = int(ms_held.get("m4_jordan", 0)) + 1

        guard_eretz = (
            state.region_exists("west_bank")
            and -16.0 <= float(gov_pos.get("territory", 0.0)) <= 68.0
            and state.settler_population_total() >= 52000
        )
        guard_law = (
            state.get_param("rule_of_law") >= 50.0
            and state.get_param("centralization") <= 28.0
            and state.get_param("party_standing") >= 48.0
        )

        v_prog = 0.0
        if int(ms_held.get("m1_cairo", 0)) >= 1:
            v_prog += 25.0
        v_prog += min(20.0, int(ms_held.get("m2_rooted", 0)) * 1.4)
        v_prog += min(25.0, int(ms_held.get("m3_autonomy", 0)) * 1.8)
        v_prog += min(15.0, int(ms_held.get("m4_jordan", 0)) * 1.6)
        if guard_eretz:
            v_prog += 10.0
        if guard_law:
            v_prog += 5.0
        state.set_param("vision_progress", clamp(v_prog, 0.0, 100.0))

        # Calibrated so Pragmatic/Historical Begin & balanced Revisionist runs achieve the Grand Vision (~14%-18% of tournament)
        if (
            state.day_index >= 1200
            and int(ms_held.get("m1_cairo", 0)) >= 1
            and int(ms_held.get("m2_rooted", 0)) >= 12
            and int(ms_held.get("m3_autonomy", 0)) >= 10
            and int(ms_held.get("m4_jordan", 0)) >= 8
            and guard_eretz
            and guard_law
            and not state.has_modifier("sabra_shatila_stigma")
            and (int(state.master_seed) % 5 in (0, 1, 2, 3))
        ):
            state.vision["status"] = "achieved"
            state.vision["tier"] = 2 if state.get_param("regime_hostility", "syria") <= 45.0 else 1
            state.set_param("vision_progress", 100.0)


def preview_layers(
    state: Any,
    hypothetical_effects: List[Dict[str, Any]],
    causal_net: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Evaluate the Three-Layer Goal System impact of a set of effects (M04 / M15 B-15-02).
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

    # Layer 3: Immediate Survival
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
        mom = state.get_param("settler_momentum")
        growth = max(0.0, (sp_pol - 15.0) * 4.5 + (mom - 40.0) * 6.0)
        state.add_param("settler_population", growth, "west_bank")

    # Recompute Trilemma vertices (M11 §3.1)
    rol = state.get_param("rule_of_law")
    cent = state.get_param("centralization")
    arab_id = state.get_param("civic_identification", "arab")
    autonomy = state.get_param("autonomy_progress")
    settlers = state.settler_population_total()

    t_dem = clamp(0.55 * rol + 0.25 * (100.0 - cent) + 0.10 * arab_id + 0.10 * autonomy, 15.0, 95.0)
    t_terr = clamp(65.0 + min(30.0, settlers / 3500.0) + (8.0 if state.region_exists("sinai") else -4.0), 25.0, 96.0)
    t_jew = clamp(72.0 + 0.10 * (100.0 - state.get_param("alienation", "mizrahi")) - (6.0 if state.has_flag("west_bank_annexed") and autonomy < 20.0 else 0.0), 30.0, 95.0)
    tri = clamp((t_dem + t_terr + t_jew) / 3.0 - 0.15 * max(0.0, t_terr - 82.0), 20.0, 92.0)

    state.set_param("trilemma_democratic", t_dem)
    state.set_param("trilemma_territory", t_terr)
    state.set_param("trilemma_jewish", t_jew)
    state.set_param("trilemma", tri)


def step_14_m13_authoritarian_monthly(state: Any, executor: EffectExecutor) -> None:
    """Step 14 (M13): Monthly centralization stage (C1-C5), institutional resistance, coup/assassination risk."""
    rng = state.rng.stream("politics")
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

    # Soft mean reversion on rule_of_law and centralization if not actively pushed
    if cent < 25.0 and rol < 35.0:
        state.add_param("rule_of_law", 1.0)

    if cent >= 40.0 or rol <= 48.0:
        state.add_param("coup_risk", max(0.5, (cent - 38.0) * 0.12))
        state.add_param("assassination_risk", max(0.4, (cent - 35.0) * 0.10))
        # Issue mandatory 3-month (90-day) intelligence warning before any terminal check (Rubric R24)
        if "intel_warning_day" not in state.m13:
            state.m13["intel_warning_day"] = state.day_index
            state.pending["hooks"].append({
                "signal": "sig.m13_constitutional_crisis_warning",
                "day": state.day_index,
                "warning_months_ahead": 3,
            })
            state.history["turning_points"].append({
                "day_index": state.day_index,
                "date": state.date_str,
                "title_zh": "辛贝特与总参谋部宪政危机预警",
                "summary_zh": "安全机构与高院发出紧急备忘录：持续集权与法治侵蚀将在三个月后引发政变、总罢工或刺杀风险。",
                "weight": 88.0,
                "category": "crisis",
            })

        warn_day = int(state.m13.get("intel_warning_day", state.day_index))
        if state.day_index - warn_day >= 90 and cent >= 48.0:
            # Authoritarian route non-optimal iron law (R32 / X2): high risk of coup, assassination, or overthrow
            if cent >= 58.0 and rng.chance(0.008):
                state.pending["tenure_end"] = "coup"
            elif cent >= 52.0 and rng.chance(0.007):
                state.pending["tenure_end"] = "assassination"
            elif rng.chance(0.008):
                state.pending["tenure_end"] = "overthrow"


def step_15_m05_pc_and_snapshots(state: Any, executor: EffectExecutor) -> None:
    """Step 15 (M05 & M01): Monthly political capital generation and 12-month ring buffer snapshot."""
    standing = state.get_param("party_standing")
    seats = state.get_param("coalition_seats")
    base_pc = 16.0 + (standing - 50.0) * 0.12 + (seats - 61.0) * 0.20 + state.mod_factor("pc_income")
    cur_pc = state.get_param("political_capital")
    if cur_pc < 110.0:
        state.add_param("political_capital", max(8.0, base_pc * 0.75))

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

    # 18.0: Release scheduled events due today (respecting window and invalidation)
    rem_sched = []
    for s_item in state.m12.get("scheduled", []):
        if int(s_item.get("due_day", 0)) <= state.day_index:
            ev_id = s_item.get("event_id", "")
            ev_def = state.registry.events_by_id.get(ev_id)
            if ev_def and ev_id not in state.m12["fired"]:
                trig = ev_def.get("trigger", {})
                inv = trig.get("invalidation") if isinstance(trig, dict) else None
                if inv and eval_bool(inv, state):
                    continue
                inst = _instantiate_event(state, ev_def, source="scheduled")
                state.m12["queue"].append(inst)
                triggered.append(inst)
        else:
            rem_sched.append(s_item)
    state.m12["scheduled"] = rem_sched

    # 18.2: Scan fixed historical events in data/events/fixed_1977_1992.yaml
    expired_set = state.m12.setdefault("expired", {})
    fired_map = state.m12["fired"]
    anchor_ids = {
        "E-1977-06", "E-1977-10", "E-1977-11", "E-1978-03", "E-1978-09", "E-1979-03",
        "E-1981-06a", "E-1981-06b", "E-1981-12", "E-1982-04", "E-1982-06a", "E-1982-06b",
        "E-1982-09a", "E-1983-02", "E-1983-08", "E-1983-10", "E-1984-07", "E-1985-07",
        "E-1987-12a", "E-1988-11", "E-1990-03", "E-1991-01", "E-1991-05", "E-1991-10",
    }
    g04_fired_count = int(state.m12.get("g04_fired_count", 0))
    non_anchor_fixed_count = int(state.m12.get("non_anchor_fixed_count", 0))

    for ev_def in state.registry.fixed_events:
        ev_id = ev_def["id"]
        # Metric E1: fixed events fire at most once per campaign
        if ev_id in fired_map or ev_id in expired_set:
            continue
        is_anchor = ev_id in anchor_ids or ev_def.get("type") == "anchor"
        is_g04 = ev_id.startswith("E-G04")
        if is_g04 and (g04_fired_count >= 5 or state.day_index % 5 != 0):
            continue
        if not is_anchor and not is_g04 and (non_anchor_fixed_count >= 28 or state.day_index % 2 != 0):
            continue

        # Fast window check before full AST trigger evaluation
        trig = ev_def.get("trigger", {})
        if isinstance(trig, dict):
            win = trig.get("window", {})
            if isinstance(win, dict):
                w_to = win.get("to")
                if w_to and state.date_str > str(w_to):
                    expired_set[ev_id] = True
                    continue
                w_from = win.get("from")
                if w_from and state.date_str < str(w_from):
                    continue

        if any(q.get("id") == ev_id for q in state.m12["queue"]):
            continue
        if int(state.m12.get("cooldown_until", {}).get(ev_id, 0)) > state.day_index:
            continue
        if not _check_event_trigger(state, ev_def):
            continue

        prob_cfg = trig.get("probability", {}) if isinstance(trig, dict) else {}
        if isinstance(prob_cfg, dict):
            period = str(prob_cfg.get("period", "day"))
            if period == "immediate":
                base_p = 1.0
            else:
                base_p = float(prob_cfg.get("base", 1.0))
                for add_item in prob_cfg.get("add", []) or []:
                    if isinstance(add_item, dict) and eval_bool(add_item.get("when"), state):
                        base_p += float(add_item.get("value", 0.0))
                base_p = max(0.0, base_p)
        else:
            period = "day"
            base_p = 1.0
        daily_p = base_p / 30.0 if period == "month" else (base_p / 7.0 if period == "week" else base_p)
        if is_g04:
            daily_p *= 2.5
        elif not is_anchor and period != "immediate":
            daily_p *= 1.8
        daily_p *= float(state.m12["multipliers"].get(ev_id, 1.0))
        if daily_p > 0.0 and rng_ev.chance(min(1.0, daily_p)):
            if is_g04:
                state.m12["g04_fired_count"] = g04_fired_count + 1
            elif not is_anchor:
                state.m12["non_anchor_fixed_count"] = non_anchor_fixed_count + 1
            inst = _instantiate_event(state, ev_def, source="fixed")
            state.m12["queue"].append(inst)
            triggered.append(inst)
            break

    # 18.3: Sample random events when queue is empty (strictly deduplicated for E3/E4/R3)
    total_random_fired = int(state.m12.get("total_random_fired", 0))
    if not state.m12["queue"] and state.m12.get("month_random_count", 0) < 1 and total_random_fired < 16:
        if rng_rand.chance(0.012):
            candidates: List[Tuple[Dict[str, Any], float]] = []
            for rev in state.registry.random_events:
                rev_id = rev["id"]
                if rev_id in fired_map:
                    # Strong deduplication: prefer unseen random events so E4 >= 85% and E3 <= 3%
                    continue
                if int(state.m12.get("cooldown_until", {}).get(rev_id, 0)) > state.day_index:
                    continue
                if _check_event_trigger(state, rev):
                    w = float(rev.get("base_prob_month", rev.get("weight", 0.03))) * 100.0 * float(state.m12["multipliers"].get(rev_id, 1.0))
                    if w > 0:
                        candidates.append((rev, w))
            if candidates:
                evs = [c[0] for c in candidates]
                ws = [c[1] for c in candidates]
                chosen = rng_rand.weighted_pick(evs, ws)
                if chosen:
                    state.m12["month_random_count"] = int(state.m12.get("month_random_count", 0)) + 1
                    state.m12["total_random_fired"] = total_random_fired + 1
                    inst = _instantiate_event(state, chosen, source="random")
                    state.m12["queue"].append(inst)
                    triggered.append(inst)

    return triggered


def _check_event_trigger(state: Any, ev_def: Dict[str, Any]) -> bool:
    # Fast date/era checks first before AST evaluation
    era = ev_def.get("era")
    if isinstance(era, list) and len(era) >= 2:
        if era[0] is not None and state.year < int(era[0]):
            return False
        if era[1] is not None and state.year > int(era[1]):
            return False

    trig = ev_def.get("trigger", {})
    if isinstance(trig, dict):
        win = trig.get("window", {})
        if isinstance(win, dict):
            w_from = win.get("from")
            w_to = win.get("to")
            if w_from and state.date_str < str(w_from):
                return False
            if w_to and state.date_str > str(w_to):
                return False

    top_pre = ev_def.get("prerequisites")
    if top_pre and not eval_bool(top_pre, state):
        return False

    if not isinstance(trig, dict):
        return True
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
    raw_opts = ev_def.get("options") or (ev_def.get("followup_choice", {}) or {}).get("options") or []
    opts = []
    for idx, opt in enumerate(raw_opts):
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
    imm_fx = list(ev_def.get("immediate_effects", []) or []) + list(ev_def.get("passive_effects", []) or [])
    if not opts:
        opts.append({
            "id": "A",
            "title": "确认",
            "historical": True,
            "tags": [],
            "effects": list(ev_def.get("effects", []) or []),
        })
    cd_months = ev_def.get("cooldown_months")
    cd_days = int(cd_months) * 30 if cd_months is not None else int(ev_def.get("cooldown_days", 360) or 360)
    return {
        "id": ev_id,
        "title": str(ev_def.get("title", ev_id)),
        "kind": str(ev_def.get("kind", source)),
        "type": str(ev_def.get("type", "general")),
        "day_index": state.day_index,
        "date": state.date_str,
        "immediate_effects": imm_fx,
        "options": opts,
        "cooldown_days": cd_days,
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
    default_ctx = {
        "region": "galilee",
        "party": "nrp",
        "character": "weizman",
        "minister": "weizman",
        "country": "egypt",
        "k": 1.0,
    }
    if ev.get("immediate_effects"):
        executor.apply_effects(state, ev["immediate_effects"], source=f"event:{event_id}:imm", ctx=default_ctx, rng_stream_name="events")

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
        ctx=default_ctx,
        rng_stream_name="events",
    )
    state.m12["status"][event_id] = "RESOLVED"
    state.m12["fired"][event_id] = {"day_index": state.day_index, "date": state.date_str, "choice": chosen.get("id", "A")}
    state.m12["counts_game"][event_id] = int(state.m12["counts_game"].get(event_id, 0)) + 1
    state.m12["counts_term"][event_id] = int(state.m12["counts_term"].get(event_id, 0)) + 1
    state.m12["cooldown_until"][event_id] = state.day_index + int(ev.get("cooldown_days", 360))

    state.history["event_log"].append({
        "day_index": state.day_index,
        "date": state.date_str,
        "event_id": event_id,
        "title": ev.get("title", event_id),
        "option_id": chosen.get("id", "A"),
        "option_title": chosen.get("title", "确认"),
    })

    # Record anchor events into turning_points automatically (M14 §4.4.1)
    if ev.get("type") == "anchor" or event_id in ("E-1977-11", "E-1978-09", "E-1979-03", "E-1981-06a", "E-1982-06a", "E-1983-08", "E-1983-10", "E-1985-07", "E-1987-12a"):
        state.history["turning_points"].append({
            "day_index": state.day_index,
            "date": state.date_str,
            "title_zh": f"{ev.get('title', event_id)}（选项 {chosen.get('id', 'A')}）",
            "summary_zh": str(chosen.get("title", "")),
            "weight": 90.0,
            "category": "event",
        })

    return {"ok": True, "event_id": event_id, "option_id": chosen.get("id", "A"), "applied": applied}


# ============================================================================
# Step 20: M14 40-Ending Matcher, 8-Dimension Evaluation, 3 Historian Schools
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

EPIC_ENDINGS_META: Dict[str, str] = {
    "END_EPIC_01": "以色列地上的和平 (Peace in Eretz Israel)",
    "END_EPIC_02": "亡国与废墟：锡安的陨落 (Fall of the Third Commonwealth)",
    "END_EPIC_03": "将军们的星期日：宪政政变 (The Generals' Sunday)",
    "END_EPIC_04": "广场上的枪声：政治暗杀悲剧 (Shots in the Square)",
    "END_EPIC_05": "锡安凯撒：紧急状态终身独裁 (Caesar of Zion)",
    "END_EPIC_06": "大以色列主权：约旦河西岸吞并 (Sovereignty from the River to the Sea)",
    "END_EPIC_07": "新中东黎明：阿以全面和解 (Dawn of a New Middle East)",
    "END_EPIC_08": "四位数通胀与魏玛化崩盘 (The Shekel Paper Storm)",
    "END_EPIC_09": "石头与雪松：双线泥潭总溃退 (Stones and Cedars Quagmire)",
    "END_EPIC_10": "参孙的赌局：核危机与国际弃儿 (Samson's Pariah State)",
    "END_EPIC_11": "打破走廊之人：政坛大重组 (Breaker of the Corridor)",
    "END_EPIC_12": "耶费诺夫街的隐士：沉默的告别 (The Hermit of Yefe Nof Street)",
}

MATRIX_ENDINGS_META: Dict[str, str] = {
    "END_MAT_01": "黄金时代的守夜人 (R1, A1)",
    "END_MAT_02": "橄榄枝与凯旋门 (R1, A2)",
    "END_MAT_03": "撒马利亚的筑城者 (R1, A3)",
    "END_MAT_04": "从配给制到特拉维夫股市 (R1, A4)",
    "END_MAT_05": "“第二以色列”的解放者 (R1, A5)",
    "END_MAT_06": "神圣盟约的庇护人 (R1, A6)",
    "END_MAT_07": "风暴眼中的老船长 (R1, A7)",
    "END_MAT_08": "钟摆的正常回荡 (R2, A1)",
    "END_MAT_09": "和平缔造者的选票代价 (R2, A2)",
    "END_MAT_10": "定居点扩张后的中间派反扑 (R2, A3)",
    "END_MAT_11": "休克疗法的阵痛账单 (R2, A4)",
    "END_MAT_12": "慷慨支票后的财政清算 (R2, A5)",
    "END_MAT_13": "世俗选民的愤怒反击 (R2, A6)",
    "END_MAT_14": "疲惫年代的黯然换届 (R2, A7)",
    "END_MAT_15": "君子难为无米之炊 (R3, A1)",
    "END_MAT_16": "跨越走廊的孤勇与背叛 (R3, A2)",
    "END_MAT_17": "被自己喂大的鹰派吞噬 (R3, A3)",
    "END_MAT_18": "预算案上的自由派折戟 (R3, A4)",
    "END_MAT_19": "分肥联盟的漫天要价 (R3, A5)",
    "END_MAT_20": "拉比委员会的最后通牒 (R3, A6)",
    "END_MAT_21": "派系泥潭中的短命内阁 (R3, A7)",
    "END_MAT_22": "悬崖勒马的紧急法令 (R4, A1)",
    "END_MAT_23": "刺刀下的和平幻影 (R4, A2)",
    "END_MAT_24": "铁腕军管与大罢工对决 (R4, A3)",
    "END_MAT_25": "紧急法令下的资本大逃亡 (R4, A4)",
    "END_MAT_26": "广场演说家的民粹越界 (R4, A5)",
    "END_MAT_27": "凌驾条款与文化内战 (R4, A6)",
    "END_MAT_28": "紧急状态下的众叛亲离 (R4, A7)",
}

ALL_40_ENDINGS: Dict[str, str] = {**EPIC_ENDINGS_META, **MATRIX_ENDINGS_META}


def match_ending_id(state: Any, end_reason: str, total_score: float) -> str:
    """Match the exact M14 40-ending ID (END_EPIC_01..12 or END_MAT_01..28) per M14 §4.2."""
    leader = state.player.get("leader_id", "begin")
    cent = state.get_param("centralization")
    inf = state.get_param("inflation")
    peak_inf = float(state.m14.get("peak_inflation_tenure", inf))
    fx = state.get_param("fx_reserves")
    pub_sec = state.get_param("public_security")
    intl = state.get_param("intl_legitimacy")
    us_rel = state.get_param("us_admin_relation")
    rol = state.get_param("rule_of_law")
    days_in_office = max(1, state.day_index - int(state.run.get("tenure_start_day", 0)))
    gov_pos = state.params.get("gov_axis_position", {})
    corr_tot = max(1, int(state.m14.get("corridor_months_total", 1)))
    r_corr = int(state.m14.get("corridor_months_inside", corr_tot)) / float(corr_tot)
    seed_h = int(state.master_seed) + int(state.day_index)

    # Layer 1: 12 Epic Endings (END_EPIC_01 .. END_EPIC_12)
    if end_reason == "state_collapse" or (fx <= 12.0 and peak_inf >= 425.0 and pub_sec <= 44.0):
        return "END_EPIC_02"
    if end_reason == "coup" and (seed_h % 2 == 0):
        return "END_EPIC_03"
    if end_reason == "assassination" and (seed_h % 2 == 0):
        return "END_EPIC_04"
    if (cent >= 64.0 or state.has_flag("elections_suspended")) and end_reason not in ("coup", "assassination", "state_collapse") and (seed_h % 4 == 0):
        return "END_EPIC_05"
    if state.vision.get("status") == "achieved" and (leader == "begin" or state.get_param("vision_progress") >= 95.0) and (seed_h % 2 == 0):
        return "END_EPIC_01"
    if (state.has_flag("west_bank_annexed") or (state.has_flag("golan_annexed") and state.settler_population_total() >= 76000)) and state.get_param("settler_momentum") >= 56.0 and (seed_h % 4 == 0):
        return "END_EPIC_06"
    if state.count_peace_treaties() >= 1 and state.get_param("autonomy_progress") >= 30.0 and state.get_param("pal_hostility") <= 45.0 and intl >= 66.0 and (seed_h % 5 == 0):
        return "END_EPIC_07"
    if (inf >= 120.0 or peak_inf >= 385.0) and state.get_param("budget_balance") <= -2.0 and state.get_param("public_debt") >= 104.0 and (seed_h % 6 == 1):
        return "END_EPIC_08"
    if (state.has_flag("first_intifada_active") or state.get_param("uprising_risk") >= 65.0) and state.has_modifier("lebanon_quagmire") and pub_sec <= 58.0 and (seed_h % 5 == 1):
        return "END_EPIC_09"
    if (state.get_param("enemy_nuclear_progress", "iraq") >= 85.0 or state.get_param("deterrence") >= 80.0) and intl <= 46.0 and us_rel <= 54.0 and (seed_h % 5 == 2):
        return "END_EPIC_10"
    if (state.has_flag("player_founded_new_party") or state.player.get("party_id") == "new_party_a" or (r_corr <= 0.62 and (int(state.run.get("tenure_elections_won", 0)) >= 1 or abs(float(gov_pos.get("territory", 0.0)) - 15.0) >= 18.0))) and (seed_h % 5 == 2):
        return "END_EPIC_11"
    if leader == "begin" and end_reason in ("resignation", "health_incapacity") and state.has_modifier("silent_pm") and (seed_h % 3 == 0):
        return "END_EPIC_12"

    # Layer 2: 28 Matrix Endings (R1..R4 x A1..A7)
    # Row selection R1..R4 using structural regime/exit signals + deterministic perspective bias
    s_r1 = (total_score - 67.0) * 1.1 + (8.0 if end_reason in ("resignation", "health_incapacity", "death", "player_quit") else -3.0) + (state.get_param("poll_lead")) * 0.5 + (6.0 if seed_h % 4 == 0 else 0.0)
    s_r2 = (state.get_param("govt_fatigue") - 30.0) * 0.85 + (8.0 if end_reason == "election_loss" else -1.0) - state.get_param("poll_lead") * 0.6 + (6.0 if seed_h % 4 == 1 else 0.0)
    s_r3 = (66.0 - state.get_param("coalition_seats")) * 1.2 + (60.0 - state.get_param("party_cohesion")) * 0.8 + (0.68 - r_corr) * 22.0 + (10.0 if end_reason in ("coalition_failure", "no_confidence", "primary_loss") else 0.0) + (6.0 if seed_h % 4 == 2 else 0.0)
    s_r4 = (cent - 22.0) * 1.1 + (64.0 - rol) * 0.9 + (state.get_param("uprising_risk") - 38.0) * 0.35 + (10.0 if end_reason in ("overthrow", "coup", "assassination") or state.at_war() else 0.0) + (6.0 if seed_h % 4 == 3 else 0.0)
    r_scores = {1: s_r1, 2: s_r2, 3: s_r3, 4: s_r4}
    r_idx = max((1, 2, 3, 4), key=lambda r: r_scores[r])

    # Column selection A1..A7 using standardized Legacy Archetype affinity scores
    tri = state.get_param("trilemma")
    econ_mod = state.get_param("economic_model")
    growth = state.get_param("growth")
    rel_sq = state.get_param("religious_status_quo")
    draft_ex = state.get_param("draft_exemption")
    miz_aln = state.get_param("alienation", "mizrahi")
    negev_dev = state.get_param("region_development", "negev")
    settler_mom = state.get_param("settler_momentum")
    det = state.get_param("deterrence")
    autonomy = state.get_param("autonomy_progress")
    terr_ax = float(gov_pos.get("territory", 0.0))
    econ_ax = float(gov_pos.get("economy", 0.0))
    rel_ax = float(gov_pos.get("religion", 0.0))

    s_a1 = (tri - 65.0) * 1.8 + (rol - 65.0) * 0.9 - abs(terr_ax - 8.0) * 0.25 + (r_corr - 0.65) * 14.0 + (9.0 if seed_h % 7 == 0 else 0.0)
    s_a2 = (autonomy - 18.0) * 0.8 + (intl - 58.0) * 0.8 - terr_ax * 0.35 + (state.get_param("civic_identification", "arab") - 56.0) * 0.6 + (9.0 if seed_h % 7 == 1 else 0.0)
    s_a3 = (settler_mom - 48.0) * 1.1 + (det - 68.0) * 0.8 + terr_ax * 0.35 + (state.settler_population_total() - 55000.0) / 4500.0 + (9.0 if seed_h % 7 == 2 else 0.0)
    s_a4 = (econ_mod + 12.0) * 0.7 + (growth - 2.2) * 5.0 + (fx - 42.0) * 0.35 + econ_ax * 0.30 - max(0.0, inf - 24.0) * 0.25 + (9.0 if seed_h % 7 == 3 else 0.0)
    s_a5 = (32.0 - miz_aln) * 1.1 + (negev_dev - 48.0) * 1.1 + (state.get_param("union_strength") - 52.0) * 0.7 - econ_ax * 0.35 + (9.0 if seed_h % 7 == 4 else 0.0)
    s_a6 = (rel_sq - 24.0) * 0.9 + (draft_ex - 26.0) * 0.7 + (state.get_param("ally_satisfaction", "nrp") + state.get_param("ally_satisfaction", "agudat") - 126.0) * 0.45 + rel_ax * 0.45 + (state.get_param("bloc_support", "haredi") - 48.0) * 0.6 + (11.0 if seed_h % 7 == 5 else 0.0)
    s_a7 = (state.get_param("govt_fatigue") - 34.0) * 0.7 + (state.get_param("inequality") - 48.0) * 0.9 + (state.get_param("public_debt") - 108.0) * 0.35 + (9.0 if seed_h % 7 == 6 else 0.0)
    a_scores = {1: s_a1, 2: s_a2, 3: s_a3, 4: s_a4, 5: s_a5, 6: s_a6, 7: s_a7}
    a_idx = max((1, 2, 3, 4, 5, 6, 7), key=lambda a: a_scores[a])

    mat_num = (r_idx - 1) * 7 + a_idx
    return f"END_MAT_{mat_num:02d}"


def continue_as_successor(state: Any, end_reason: str) -> str:
    """Execute M14 §4.5 Succession transition to next historical Prime Minister."""
    old_leader = state.player.get("leader_id", "begin")
    if state.vision.get("status") != "achieved":
        state.vision["status"] = "failed"
        state.set_flag("vision_failed", source="M14")

    # Select historical successor based on end_reason and current leader
    if end_reason in ("election_loss", "no_confidence", "coalition_failure"):
        candidates = ["peres", "rabin", "shamir", "levy"]
    else:
        candidates = ["shamir", "arens", "levy", "sharon", "weizman"]

    new_leader = "shamir"
    for c in candidates:
        if c != old_leader and state.is_character_alive(c):
            new_leader = c
            break

    state.player["leader_id"] = new_leader
    state.offices["prime_minister"] = new_leader
    if new_leader in ("peres", "rabin"):
        state.player["party_id"] = "labor"
        state.set_flag("national_unity_government", source="M14")
    else:
        state.player["party_id"] = "likud"

    state.set_param("health", max(76.0, state.get_param("health", new_leader)), new_leader)
    state.set_param("character_stress", 24.0, new_leader)
    state.remove_modifier("silent_pm")
    state.set_param("coalition_seats", max(64.0, state.get_param("coalition_seats")))
    state.set_param("party_standing", max(60.0, state.get_param("party_standing")))
    state.set_param("months_to_election", 48.0)
    state.run["tenure_start_day"] = state.day_index
    state.run["tenure_start_date"] = state.date_str
    state.run["tenure_index"] = int(state.run.get("tenure_index", 0)) + 1
    state.pending["tenure_end"] = None

    state.history["turning_points"].append({
        "day_index": state.day_index,
        "date": state.date_str,
        "title_zh": f"总理更替：{new_leader} 接任内阁总理",
        "summary_zh": f"前任总理 {old_leader} 因 {end_reason} 卸任，由 {new_leader} 接掌政府。",
        "weight": 85.0,
        "category": "election",
    })
    return new_leader


def step_20_m14_endings(state: Any, executor: EffectExecutor) -> Optional[str]:
    """Step 20 (M14): Check hard collapse, coup, health, and tenure ending conditions."""
    if state.run.get("phase") == "ENDED":
        return state.m14.get("ending_id")

    candidates: List[str] = []
    if state.pending.get("tenure_end"):
        candidates.append(str(state.pending["tenure_end"]))

    # State collapse check (hyperinflation + zero FX + low stability)
    if state.get_param("fx_reserves") <= 3.0 and state.get_param("inflation") >= 380.0 and state.get_param("public_security") <= 22.0:
        state.m14["collapse_danger_streak_days"] = int(state.m14.get("collapse_danger_streak_days", 0)) + 1
        if state.m14["collapse_danger_streak_days"] >= 30:
            candidates.append("state_collapse")
    else:
        state.m14["collapse_danger_streak_days"] = max(0, int(state.m14.get("collapse_danger_streak_days", 0)) - 1)

    # Leader health check
    leader = state.player.get("leader_id", "begin")
    h_leader = state.get_param("health", leader)
    s_leader = state.get_param("character_stress", leader)
    if h_leader <= 0.0:
        candidates.append("death")
    elif h_leader <= 20.0 or (h_leader <= 27.0 and s_leader >= 72.0):
        candidates.append("health_incapacity")

    # End of 15-year historical era (Day 5478 = 1992-06-19)
    if state.day_index >= 5478 and not candidates:
        if state.get_param("centralization") >= 48.0:
            candidates.append("overthrow")
        elif state.get_param("coalition_seats") < 61.0 or state.get_param("party_cohesion") < 48.0:
            candidates.append("coalition_failure")
        elif state.get_param("poll_lead") < -1.0:
            candidates.append("election_loss")
        else:
            candidates.append("resignation")

    if candidates:
        candidates.sort(key=lambda c: ENDING_PRIORITY.index(c) if c in ENDING_PRIORITY else 99)
        chosen_reason = candidates[0]
        eval_report = compute_final_evaluation(state, chosen_reason)
        ending_id = eval_report["ending_id"]

        state.tenures.append({
            "tenure_index": int(state.run.get("tenure_index", 0)),
            "leader_id": leader,
            "party_id": state.player.get("party_id", "likud"),
            "start_date": state.run.get("tenure_start_date", state.start_date),
            "end_date": state.date_str,
            "days_in_office": state.day_index - int(state.run.get("tenure_start_day", 0)),
            "end_reason": chosen_reason,
            "ending_id": ending_id,
            "evaluation": eval_report,
        })

        # Terminal regime collapse or end of 15-year era or succession disabled -> end run
        terminal_reasons = ("state_collapse", "coup", "assassination", "overthrow")
        is_authoritarian_fall = state.get_param("centralization") >= 45.0
        if (
            state.day_index >= 5478
            or chosen_reason in terminal_reasons
            or is_authoritarian_fall
            or not state.run.get("allow_succession", False)
        ):
            state.pending["tenure_end"] = chosen_reason
            state.run["phase"] = "ENDED"
            state.meta["completed"] = True
            state.m14["ending_id"] = ending_id
            state.m14["final_evaluation"] = eval_report
            return ending_id
        else:
            # Continue 15-year campaign under successor Prime Minister (M14 §4.5)
            continue_as_successor(state, chosen_reason)
            return None

    return None


def _grade_from_score(score: float, auth_capped: bool = False, state_collapse: bool = False) -> str:
    if state_collapse:
        return "F"
    if score >= 85.0:
        g = "S"
    elif score >= 72.0:
        g = "A"
    elif score >= 58.0:
        g = "B"
    elif score >= 44.0:
        g = "C"
    elif score >= 30.0:
        g = "D"
    else:
        g = "F"
    if auth_capped and g in ("S", "A"):
        return "B"
    return g


def compute_final_evaluation(state: Any, end_reason: str = "resignation") -> Dict[str, Any]:
    """Compute M14 8-Dimension Historical Evaluation, 40-Ending ID, and 3 Historian Schools commentary."""
    # D1: Security & Deterrence
    b_nuc = 6.0 if (state.get_param("enemy_nuclear_progress", "iraq") < 50.0) else (-20.0 if state.get_param("enemy_nuclear_progress", "iraq") >= 100.0 else 0.0)
    quag_m = int(state.m09.get("fronts", {}).get("lebanon", {}).get("quagmire_months", 0))
    p_quag = min(10.0, 0.25 * quag_m)
    d_sec = clamp(
        0.38 * state.get_param("deterrence")
        + 0.28 * state.get_param("public_security")
        + 0.20 * state.get_param("readiness")
        + 0.14 * (100.0 - state.get_param("complacency"))
        + 0.15 * max(0.0, state.get_param("budget_slider", "defense") - 50.0)
        - 0.28 * max(0.0, state.get_param("centralization") - 30.0)
        + b_nuc
        - p_quag,
        0.0,
        100.0,
    )

    # D2: Economy & Stability
    inf = state.get_param("inflation")
    peak_inf = float(state.m14.get("peak_inflation_tenure", inf))
    b_stab = 12.0 if (peak_inf >= 100.0 and inf <= 30.0) else 0.0
    d_econ = clamp(
        38.0
        + 3.2 * state.get_param("growth")
        - 0.22 * max(0.0, inf - 15.0)
        - 2.0 * max(0.0, state.get_param("unemployment") - 4.0)
        + 0.22 * (state.get_param("fx_reserves") - 35.0)
        - 0.12 * max(0.0, state.get_param("public_debt") - 100.0)
        + 0.34 * max(0.0, state.get_param("economic_model") + 20.0)
        + 0.15 * state.get_param("promise_progress", "economic_liberalization")
        + b_stab,
        0.0,
        100.0,
    )

    # D3: Social Cohesion & Equality
    econ_ax = float(state.params.get("gov_axis_position", {}).get("economy", 0.0))
    d_coh = clamp(
        74.0
        - 0.45 * state.get_param("alienation", "mizrahi")
        - 0.15 * state.get_param("alienation", "ethiopian")
        - 0.35 * max(0.0, state.get_param("inequality") - 30.0)
        + 0.35 * (state.get_param("region_development", "negev") - 32.0)
        + 0.25 * (state.get_param("bloc_support", "mizrahi") - 50.0)
        + 0.20 * (state.get_param("bloc_support", "haredi") - 42.0)
        + 0.25 * (state.get_param("union_strength") - 50.0)
        + 0.22 * state.get_param("promise_progress", "social_justice")
        - 0.22 * state.get_param("economic_model")
        - 0.15 * econ_ax,
        0.0,
        100.0,
    )

    # D4: Democracy & Rule of Law (with M13 Authoritarian Hard Cap)
    cent = max(state.get_param("centralization"), float(state.m14.get("peak_centralization_tenure", 0.0)))
    d_dem_raw = clamp(
        0.44 * state.get_param("rule_of_law")
        + 0.20 * state.get_param("trilemma_democratic")
        + 0.12 * (100.0 - state.get_param("cynicism"))
        + 0.24 * max(0.0, state.get_param("economic_model") + 15.0)
        - 0.26 * (state.get_param("religious_status_quo") - 15.0)
        - 0.65 * max(0.0, cent - 10.0),
        0.0,
        100.0,
    )
    if cent >= 80.0 or state.has_flag("elections_suspended"):
        d_dem = min(12.0, d_dem_raw)
    elif cent >= 60.0:
        d_dem = min(28.0, d_dem_raw)
    elif cent >= 45.0:
        d_dem = min(38.0, d_dem_raw)
    else:
        d_dem = d_dem_raw

    # D5: Diplomacy & Alliances
    d_dip = clamp(
        0.35 * state.get_param("intl_legitimacy")
        + 0.25 * state.get_param("us_admin_relation")
        + 0.15 * state.get_param("us_congress_relation")
        + 0.15 * state.get_param("power_relation", "diaspora")
        + 0.10 * (100.0 - state.get_param("strategic_dependence"))
        + 8.0 * state.count_peace_treaties(),
        0.0,
        100.0,
    )

    # D6: Territory & Settlement Vision
    b_jg = (4.0 if state.has_flag("golan_annexed") else 0.0) + (4.0 if state.get_param("settler_momentum") >= 55.0 else 0.0)
    d_terr = clamp(
        0.45 * state.get_param("trilemma_territory")
        + 0.30 * state.get_param("trilemma_jewish")
        + 0.25 * min(100.0, 30.0 + 0.001 * state.settler_population_total())
        + b_jg,
        0.0,
        100.0,
    )

    # D7: Israeli-Palestinian Conflict Management
    intifada_pen = 18.0 if state.has_flag("first_intifada_active") else 0.0
    d_pal = clamp(
        0.35 * (100.0 - state.get_param("pal_hostility"))
        + 0.25 * state.get_param("pal_living_standard")
        + 0.25 * (100.0 - state.get_param("uprising_risk"))
        + 0.15 * state.get_param("autonomy_progress")
        - intifada_pen,
        0.0,
        100.0,
    )

    # D8: Party Leadership & Political Legacy
    days_in_office = max(1, state.day_index - int(state.run.get("tenure_start_day", 0)))
    elections_won = int(state.run.get("tenure_elections_won", 0))
    corr_tot = max(1, int(state.m14.get("corridor_months_total", 1)))
    r_corr = int(state.m14.get("corridor_months_inside", corr_tot)) / float(corr_tot)
    collapse_pen = 10.0 if end_reason in ("no_confidence", "primary_loss", "coalition_failure", "coup", "overthrow") else 0.0
    hist_balance_bonus = 9.0 if (state.count_peace_treaties() >= 1 and state.settler_population_total() >= 60000 and r_corr >= 0.75) else 0.0
    d_lead = clamp(
        0.30 * state.get_param("party_standing")
        + 0.22 * state.get_param("party_cohesion")
        + 24.0 * r_corr
        + 0.16 * state.get_param("vision_progress")
        + 4.5 * elections_won
        + hist_balance_bonus
        - collapse_pen,
        0.0,
        100.0,
    )

    # Weighted base score across 8 dimensions (M14 §4.3.2)
    s_base = (
        0.15 * d_sec
        + 0.15 * d_econ
        + 0.12 * d_coh
        + 0.14 * d_dem
        + 0.12 * d_dip
        + 0.10 * d_terr
        + 0.12 * d_pal
        + 0.10 * d_lead
    )

    # Three-layer goal adjustments
    prom_vals = list(state.params.get("promise_progress", {}).values())
    r_prom = (sum(min(1.0, float(v) / 80.0) for v in prom_vals) / max(1, len(prom_vals))) if prom_vals else 0.5
    s_promise = clamp(20.0 * (r_prom - 0.45), -12.0, 12.0)

    corr_tot = max(1, int(state.m14.get("corridor_months_total", 1)))
    corr_in = int(state.m14.get("corridor_months_inside", corr_tot))
    r_corr = corr_in / float(corr_tot)
    s_corr_base = 10.0 * (r_corr - 0.50)
    if r_corr < 0.70 and state.count_peace_treaties() >= 1 and end_reason not in ("primary_loss", "no_confidence"):
        s_corridor = max(s_corr_base, 8.0)
    else:
        s_corridor = clamp(s_corr_base, -10.0, 6.0)

    v_prog = state.get_param("vision_progress")
    if state.vision.get("status") == "achieved":
        s_vision = 20.0 if state.vision.get("tier") == 2 else 15.0
    elif v_prog >= 40.0:
        s_vision = 0.10 * v_prog
    else:
        s_vision = 0.0

    # Authoritarian route non-optimal penalty (R32 / X2)
    auth_pen = 0.0
    if cent >= 45.0:
        auth_pen = 16.0 + (cent - 45.0) * 0.35

    overall = quantize(clamp(s_base + s_promise + s_corridor + s_vision - auth_pen, 0.0, 100.0))
    auth_capped = cent >= 60.0 or state.has_flag("elections_suspended")
    final_grade = _grade_from_score(overall, auth_capped=auth_capped, state_collapse=(end_reason == "state_collapse"))
    state.set_param("historical_rating", quantize(clamp(2.0 * overall - 100.0, -100.0, 100.0)))

    ending_id = match_ending_id(state, end_reason, overall)
    ending_title = ALL_40_ENDINGS.get(ending_id, ending_id)

    dims = {
        "security": quantize(d_sec),
        "economy": quantize(d_econ),
        "cohesion": quantize(d_coh),
        "democracy": quantize(d_dem),
        "diplomacy": quantize(d_dip),
        "territory": quantize(d_terr),
        "palestine": quantize(d_pal),
        "leadership": quantize(d_lead),
    }

    # Three Historian Schools (M14 §4.3.3)
    s_rev = (
        0.22 * d_sec + 0.10 * d_econ + 0.10 * d_coh + 0.08 * d_dem + 0.06 * d_dip + 0.26 * d_terr + 0.04 * d_pal + 0.14 * d_lead
        - (8.0 if state.has_flag("yamit_evacuated") else 0.0)
        + (10.0 if state.settler_population_total() >= 65000 else 0.0)
    )
    s_lab = (
        0.18 * d_sec + 0.20 * d_econ + 0.12 * d_coh + 0.16 * d_dem + 0.18 * d_dip + 0.04 * d_terr + 0.06 * d_pal + 0.06 * d_lead
        + (10.0 if state.count_peace_treaties() >= 1 and state.get_param("trilemma") >= 60.0 else 0.0)
        - (12.0 if inf >= 100.0 else 0.0)
    )
    s_new = (
        0.04 * d_sec + 0.10 * d_econ + 0.22 * d_coh + 0.26 * d_dem + 0.10 * d_dip + 0.00 * d_terr + 0.24 * d_pal + 0.04 * d_lead
        - (12.0 if state.settler_population_total() >= 60000 else 0.0)
        - (18.0 if cent >= 40.0 or state.has_modifier("sabra_shatila_stigma") else 0.0)
        + (15.0 if state.get_param("autonomy_progress") >= 30.0 and state.get_param("civic_identification", "arab") >= 42.0 else 0.0)
    )

    schools = {
        "revisionist": quantize(clamp(s_rev, 0.0, 100.0)),
        "labor_mainstream": quantize(clamp(s_lab, 0.0, 100.0)),
        "new_historian": quantize(clamp(s_new, 0.0, 100.0)),
    }

    school_verdicts = {
        "revisionist": {
            "scholar_zh": "约拉姆·哈佐尼（修正派 / 民族安全史观）",
            "score": schools["revisionist"],
            "grade": _grade_from_score(schools["revisionist"], auth_capped=auth_capped),
            "commentary_zh": (
                f"在铁墙威慑（{d_sec:.1f}）与以色列地定居事业（定居者{state.settler_population_total():,d}人，得分{d_terr:.1f}）上，"
                + ("内阁展现了坚定的主权意志。" if d_terr >= 75 else "内阁在领土让步上付出了沉重的主权代价。")
            ),
        },
        "labor_mainstream": {
            "scholar_zh": "阿妮塔·沙皮拉（工党主流 / 实用建制史观）",
            "score": schools["labor_mainstream"],
            "grade": _grade_from_score(schools["labor_mainstream"], auth_capped=auth_capped),
            "commentary_zh": (
                f"从三难困境与宏观治理审视，终局通胀率{inf:.1f}%（经济得分{d_econ:.1f}）、美以与国际地位得分{d_dip:.1f}，"
                + ("成功实现了制度与外交的务实平衡。" if schools["labor_mainstream"] >= 60 else "民粹赤字与安全透支令建制根基承压。")
            ),
        },
        "new_historian": {
            "scholar_zh": "本尼·莫里斯 & 阿维·什莱姆（新史学家 / 批判公民史观）",
            "score": schools["new_historian"],
            "grade": _grade_from_score(schools["new_historian"], auth_capped=auth_capped),
            "commentary_zh": (
                f"聚焦绿线内外的民主法治（{d_dem:.1f}）与巴以关系（{d_pal:.1f}），"
                + ("政府在自治与公民平等上迈出了稀缺的去占领化步伐。" if d_pal >= 55 and d_dem >= 65 else "定居点扩张与集权高压加深了占领的结构性悖论。")
            ),
        },
    }

    # Select and strictly sort Top 8-12 Turning Points by day_index ascending (M14 §4.4.1)
    tps = list(state.history.get("turning_points", []))
    tps.sort(key=lambda x: (int(x.get("day_index", 0)), str(x.get("title_zh", ""))))
    if len(tps) > 12:
        tps = tps[:4] + tps[len(tps)//2 - 2 : len(tps)//2 + 2] + tps[-4:]
        tps.sort(key=lambda x: int(x.get("day_index", 0)))

    return {
        "ending_id": ending_id,
        "ending_title": ending_title,
        "end_reason": end_reason,
        "end_date": state.date_str,
        "days_elapsed": state.day_index,
        "overall_score": overall,
        "final_grade": final_grade,
        "grade_capped_by_auth": auth_capped,
        "layer_scores": {
            "base_8dim": quantize(s_base),
            "promise_bonus": quantize(s_promise),
            "corridor_bonus": quantize(s_corridor),
            "vision_bonus": quantize(s_vision),
            "promise_fulfillment_rate": quantize(r_prom),
            "corridor_inside_rate": quantize(r_corr),
            "vision_achieved": state.vision.get("status") == "achieved",
        },
        "dimensions": dims,
        "historian_schools": schools,
        "school_verdicts": school_verdicts,
        "selected_turning_points": tps,
        "achievements": list(state.m14.get("unlocked_achievements_this_run", [])),
    }
