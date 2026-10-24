#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sim import (
    CausalNet,
    DataRegistry,
    DeterministicRNG,
    EffectExecutor,
    GameState,
    RngStream,
    SimulationEngine,
    compile_expr,
    eval_bool,
    eval_expr,
    eval_float,
    preview_layers,
)
from sim.state import civil_from_days, days_from_civil, weekday_from_days


def test_rng_determinism_and_serialization() -> None:
    rng1 = DeterministicRNG(19770620)
    rng2 = DeterministicRNG(19770620)

    seq1 = [rng1.stream("events").next_u32() for _ in range(10)]
    seq2 = [rng2.stream("events").next_u32() for _ in range(10)]
    assert seq1 == seq2

    # Save and restore rng1 state
    saved = rng1.to_dict()
    rng_restored = DeterministicRNG.from_dict(saved, default_seed=19770620)
    assert [rng1.stream("events").next_float() for _ in range(10)] == [
        rng_restored.stream("events").next_float() for _ in range(10)
    ]

    # Cosmetic stream must not be serialized in authoritative dict
    rng1.stream("cosmetic").next_u32()
    assert "cosmetic" not in rng1.to_dict()["streams"]


def test_calendar_and_parameter_aliases() -> None:
    assert days_from_civil(1977, 6, 20) == 2727
    assert civil_from_days(2727) == (1977, 6, 20)
    assert weekday_from_days(2727) == 0  # Monday

    state = GameState("begin_1977", master_seed=19770620)
    assert len(state.registry.param_defs) == 110
    assert abs(state.get_param("party_cohesion") - 57.04) < 1e-4
    assert abs(state.get_param("cynicism") - 20.0) < 1e-4
    assert abs(state.get_param("voter_cynicism") - 20.0) < 1e-4

    # Alias synchronization
    state.set_param("voter_cynicism", 33.5)
    assert state.get_param("cynicism") == 33.5

    # Office holder resolution in relation[key]
    assert state.holder_of("defense") == "weizman"
    weizman_rel = state.get_param("relation", "weizman")
    assert state.get_param("relation", "defense") == weizman_rel

    # Country relation routing
    assert state.get_param("country_relation", "usa") == state.get_param("us_admin_relation")
    assert abs(state.get_param("country_relation", "egypt") - (100.0 - state.get_param("regime_hostility", "egypt"))) < 1e-6


def test_expr_compiler_and_all_yaml_expressions() -> None:
    state = GameState("begin_1977", master_seed=19770620)
    assert eval_bool('flag("likud_in_government") and character_alive("dayan")', state) is True
    assert eval_bool("intl_legitimacy <= 60 and us_admin_relation <= 60 and relation[dayan] >= -20", state) is True
    assert eval_bool("party_in_coalition('likud') and not at_war()", state) is True
    assert eval_float("clamp(inflation, 0, 100)", state) == 35.0
    assert eval_expr("era()", state) == 4

    # Compile every expression across fixed_events, random_events, and actions
    reg = state.registry
    compiled_count = 0
    for ev in reg.fixed_events + reg.random_events:
        trig = ev.get("trigger", {})
        if isinstance(trig, dict):
            for field in ("prerequisites", "condition", "invalidation"):
                expr_s = trig.get(field)
                if expr_s:
                    compile_expr(str(expr_s))
                    eval_bool(str(expr_s), state)
                    compiled_count += 1
        for opt in ev.get("options", []) or []:
            req = opt.get("requires")
            if req:
                compile_expr(str(req))
                eval_bool(str(req), state)
                compiled_count += 1

    for act in reg.actions.values():
        pre = act.get("pre")
        if pre:
            compile_expr(str(pre))
            eval_bool(str(pre), state)
            compiled_count += 1

    assert compiled_count >= 150


def test_causal_net_day0_zero_drift() -> None:
    state = GameState("begin_1977", master_seed=19770620)
    cnet = CausalNet(state.registry)

    checked = 0
    max_drift = 0.0
    for node in cnet.nodes:
        if node.get("mode") != "level":
            continue
        param = node["param"]
        for k in cnet._iter_node_keys(state, node):
            if not cnet._is_node_key_active(state, node, k):
                continue
            x0 = state.get_param(param, k)
            _, t_val, _ = cnet.compute_target_value(state, param, k)
            drift = abs(t_val - x0)
            checked += 1
            max_drift = max(max_drift, drift)
            assert drift < 0.01, f"Day-0 drift on {param}[{k}]: |{t_val} - {x0}| = {drift}"

    assert checked >= 70
    assert max_drift < 0.01

    # Verify shock memory and explain()
    cnet.on_effect_applied(state, "party_standing", None, -10.0, "test_shock")
    assert abs(state.m02["shock_mem"]["party_standing"] - (-3.0)) < 1e-6
    exp = cnet.explain(state, "party_standing")
    assert exp["mode"] == "level"
    assert isinstance(exp["top_contributors"], list)


def test_m04_three_layer_goal_preview() -> None:
    eng = SimulationEngine("begin_1977", master_seed=19770620)
    # E-1977-06 Option A: Invite Moshe Dayan as Foreign Minister
    ev_dayan = eng.registry.events_by_id["E-1977-06"]
    opt_a_effects = ev_dayan["options"][0]["effects"]
    preview = eng.preview_layers(opt_a_effects)

    # Option A boosts promise_progress (Layer 1) and us_admin_relation/intl_legitimacy (Layer 3),
    # while penalizing party_standing & shifting territory stance away from corridor (Layer 2)
    assert preview["layer1_goals"]["net_delta"] > 0.0
    assert preview["layer2_corridors"]["net_delta"] < 0.0
    assert preview["layer3_survival"]["net_delta"] > 0.0
    assert preview["has_tension"] is True
    assert "vision_vs_party_corridor" in preview["tension_axes"]


def test_m05_actions_and_policies() -> None:
    eng = SimulationEngine("begin_1977", master_seed=19770620)
    pc_before = eng.state.get_param("political_capital")
    pol_id = next(iter(eng.state.policies.keys()))
    res = eng.adjust_policy_now(pol_id, direction="up")
    if res["ok"]:
        assert eng.state.get_param("political_capital") < pc_before

    act_res = eng.execute_action_now("coalition_whip")
    assert act_res["ok"] is True
    assert eng.state.has_modifier("confidence_linked")


def test_m10_hyperinflation_spiral_and_stabilization() -> None:
    eng = SimulationEngine("begin_1977", master_seed=19770620)
    eng.state.set_param("inflation", 140.0)
    eng.state.set_param("budget_balance", -12.0)

    from sim.modules import step_16_m10_macro_quarterly
    step_16_m10_macro_quarterly(eng.state, eng.executor)
    assert eng.state.get_param("inflation") > 140.0

    # Apply 1985-style stabilization plan
    eng.executor.apply_one(eng.state, {"op": "custom", "handler": "m10_apply_stabilization_plan"})
    assert eng.state.m10["stabilization_plan_active"] is True
    assert eng.state.get_param("inflation") < 100.0


def test_m08_intifada_and_m09_war() -> None:
    eng = SimulationEngine("begin_1977", master_seed=19770620)
    eng.executor.apply_one(eng.state, {"op": "custom", "handler": "m08_start_intifada"})
    assert eng.state.has_flag("intifada_active")
    assert eng.state.m08["uprising_state"]["active"] is True

    eng.executor.apply_one(eng.state, {"op": "custom", "handler": "m09_start_war", "value": {"front": "lebanon", "scope": "full"}})
    assert eng.state.at_war("lebanon") is True
    assert eng.state.get_param("mobilization") >= 65.0

    eng.executor.apply_one(eng.state, {"op": "custom", "handler": "m09_ceasefire", "value": {"front": "lebanon"}})
    assert eng.state.at_war("lebanon") is False


def test_m14_endings_and_final_evaluation() -> None:
    eng = SimulationEngine("begin_1977", master_seed=19770620)
    eval_report = eng.evaluate_tenure("resignation")
    assert len(eval_report["dimensions"]) == 8
    assert len(eval_report["historian_schools"]) == 3
    assert 0.0 <= eval_report["overall_score"] <= 100.0

    eng.executor.apply_one(eng.state, {"op": "custom", "handler": "end_tenure", "value": {"reason": "resignation"}})
    res = eng.step_day()
    assert res["ended"] is True
    assert res["ending_id"].startswith("END_")
    assert eng.state.pending["tenure_end"] == "resignation"


def test_365_day_determinism_save_load_and_performance(tmp_path: Path = None) -> None:
    if tmp_path is None:
        tmp_path = Path(tempfile.mkdtemp())
    t0 = time.perf_counter()
    eng1 = SimulationEngine("begin_1977", master_seed=19770620)
    eng1.run_days(365)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    hash1 = eng1.state_hash()

    eng2 = SimulationEngine("begin_1977", master_seed=19770620)
    eng2.run_days(180)
    save_file = tmp_path / "mid_run_180d.ipsave.json"
    eng2.state.save_json(save_file)

    loaded_state = GameState.load_json(save_file)
    assert loaded_state.state_hash() == eng2.state_hash()

    eng_resumed = SimulationEngine("begin_1977", master_seed=19770620, state=loaded_state)
    eng_resumed.run_days(185)
    assert eng_resumed.state.day_index == 365
    assert eng_resumed.state_hash() == hash1
    assert elapsed_ms < 5000.0


def test_new_gameplay_mechanics_proposals_demands_gates_and_succession() -> None:
    from sim.modules import (
        approve_minister_proposal,
        continue_as_successor,
        get_available_actions,
        refresh_coalition_demands,
        refresh_minister_proposals,
        reject_minister_proposal,
        resolve_coalition_demand,
    )

    eng = SimulationEngine("begin_1977", master_seed=19770620)
    st = eng.state
    st.set_param("political_capital", 80.0)

    # 1. Era & Econ gates on actions
    avail_ids = {a["id"] for a in get_available_actions(st, ignore_pc=True)}
    assert "second_tv_channel_law" not in avail_ids  # min_year: 1986
    assert "tv_franchise_auction" not in avail_ids   # econ_gate: >= 15 (starts at -32)

    # 2. Action template arg resolution (no literal "{bloc}" key pollution)
    res_outreach = eng.execute_action_now("rally_bloc")
    assert res_outreach["ok"] is True
    assert "{bloc}" not in st.params.get("bloc_support", {})

    # 3. Minister proposals (30% PC discount, 0 slot cost, +8 relation)
    props = refresh_minister_proposals(st)
    assert len(props) >= 1
    p0 = props[0]
    slots_before = int(st.m05.get("weekly_slots_used", 0))
    rel_before = st.get_param("relation", p0["minister_id"])
    res_prop = approve_minister_proposal(st, p0["id"], eng.executor)
    assert res_prop["ok"] is True
    assert int(st.m05.get("weekly_slots_used", 0)) == slots_before
    assert st.get_param("relation", p0["minister_id"]) > rel_before

    # 4. Coalition partner demands (concede / delay / refuse)
    st.set_param("ally_satisfaction", 45.0, "nrp")
    demands = refresh_coalition_demands(st)
    assert len(demands) >= 1
    d0 = demands[0]
    sat_before = st.get_param("ally_satisfaction", d0["party_id"])
    res_dem = resolve_coalition_demand(st, d0["id"], "concede", eng.executor)
    assert res_dem["ok"] is True
    assert st.get_param("ally_satisfaction", d0["party_id"]) > sat_before

    # 5. Trial balloon 30% policy PC discount & statutory law minority gate
    st.add_modifier("trial_balloon", 14, {"policy_pc_cost": -0.30})
    pc_pre_pol = st.get_param("political_capital")
    res_pol = eng.adjust_policy_now("fx_regime", direction="up")
    assert res_pol["ok"] is True
    assert not st.has_modifier("trial_balloon")  # consumed on policy change
    assert (pc_pre_pol - st.get_param("political_capital")) < 18.0

    # Statutory law policy blocked when minority government (< 58 seats)
    st.set_param("coalition_seats", 55.0)
    st.policies["sabbath_transport"]["cooldown_until_day"] = 0
    res_law = eng.adjust_policy_now("sabbath_transport", direction="down")
    assert res_law["ok"] is False
    assert res_law["error"] == "minority_blocked_law"

    # 6. Campaign succession after end_tenure
    st.set_param("coalition_seats", 65.0)
    eng.executor.apply_one(st, {"op": "custom", "handler": "end_tenure", "value": {"reason": "resignation"}})
    eng.step_day()
    assert st.run["phase"] == "ENDED"
    new_leader = continue_as_successor(st, "resignation")
    assert new_leader != "begin"
    assert st.run["phase"] == "PLAYING"
    assert st.player["leader_id"] == new_leader


class TestSimCore(unittest.TestCase):
    def test_01_rng_determinism_and_serialization(self) -> None:
        test_rng_determinism_and_serialization()

    def test_02_calendar_and_parameter_aliases(self) -> None:
        test_calendar_and_parameter_aliases()

    def test_03_expr_compiler_and_all_yaml_expressions(self) -> None:
        test_expr_compiler_and_all_yaml_expressions()

    def test_04_causal_net_day0_zero_drift(self) -> None:
        test_causal_net_day0_zero_drift()

    def test_05_m04_three_layer_goal_preview(self) -> None:
        test_m04_three_layer_goal_preview()

    def test_06_m05_actions_and_policies(self) -> None:
        test_m05_actions_and_policies()

    def test_07_m10_hyperinflation_spiral_and_stabilization(self) -> None:
        test_m10_hyperinflation_spiral_and_stabilization()

    def test_08_m08_intifada_and_m09_war(self) -> None:
        test_m08_intifada_and_m09_war()

    def test_09_m14_endings_and_final_evaluation(self) -> None:
        test_m14_endings_and_final_evaluation()

    def test_10_365_day_determinism_save_load_and_performance(self) -> None:
        test_365_day_determinism_save_load_and_performance()

    def test_11_new_gameplay_mechanics_proposals_demands_gates_and_succession(self) -> None:
        test_new_gameplay_mechanics_proposals_demands_gates_and_succession()


if __name__ == "__main__":
    unittest.main(verbosity=2)
