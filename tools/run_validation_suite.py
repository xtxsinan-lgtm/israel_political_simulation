#!/usr/bin/env python3
"""
Phase 3C Headless Monte Carlo Validation & Playtest Balance Suite.
Executes Tests 1, 2, 3, and 4 against `sim/` and writes structured JSON metrics
to `data/validation_results.json`.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from collections import Counter
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sim.bots import (
    AuthoritarianCaesarBot,
    HistoricalBot,
    NeoliberalTechnocratBot,
    PeaceDoveBot,
    PopulistWelfareBot,
    RandomBot,
    RevisionistHawkBot,
    get_all_bots,
)
from sim.engine import SimulationEngine
from sim.modules import ALL_40_ENDINGS


def _check_pinning_24m(state: Any) -> Tuple[int, int, List[str]]:
    """Check core [0, 100] stock parameters for >=24 consecutive months pinned at 0 or 100 (Rubric R8)."""
    core_params = [
        "public_security",
        "deterrence",
        "readiness",
        "intl_legitimacy",
        "us_admin_relation",
        "us_congress_relation",
        "rule_of_law",
        "party_standing",
        "party_cohesion",
        "fx_reserves",
        "union_strength",
        "inequality",
        "pal_hostility",
        "pal_living_standard",
        "settler_momentum",
        "trilemma",
        "trilemma_democratic",
        "trilemma_territory",
        "trilemma_jewish",
        "absorption_capacity",
    ]
    pinned_params: List[str] = []
    hist_map = state.m02.get("history_24m", {})
    for p in core_params:
        lo, hi = state.get_param_range(p)
        arr = hist_map.get(p, [])
        if len(arr) >= 24:
            if all(v <= lo + 0.05 for v in arr[-24:]) or all(v >= hi - 0.05 for v in arr[-24:]):
                pinned_params.append(p)
    return len(pinned_params), len(core_params), pinned_params


def run_test_1_system_dynamics() -> Dict[str, Any]:
    """Test 1: 15-Year System Dynamics, Inflation Calibration, Begin Health Curve & Performance Invariant."""
    print("[Test 1] Running 15-year (5,478-day) Historical & Peace Decompression trajectories...")
    eng = SimulationEngine(master_seed=19770620, bot=HistoricalBot(seed=19770620), allow_succession=True)

    y1_times: List[float] = []
    y15_times: List[float] = []
    inflation_by_year: Dict[int, float] = {}
    max_inf_1983_1984 = 0.0
    post_1985_infs: List[float] = []
    pinned_ever: set[str] = set()
    total_core_checked = 20

    for d in range(1, 5479):
        t0 = time.perf_counter()
        eng.step_day()
        dt = time.perf_counter() - t0
        if d <= 365:
            y1_times.append(dt)
        elif d > 5478 - 365:
            y15_times.append(dt)

        st = eng.state
        cur_inf = st.get_param("inflation")
        if st.year in (1983, 1984):
            max_inf_1983_1984 = max(max_inf_1983_1984, cur_inf)
        if st.month == 12 and st.day == 31:
            inflation_by_year[st.year] = round(cur_inf, 2)
            if st.year >= 1986:
                post_1985_infs.append(cur_inf)
        if st.is_month:
            _, total_core_checked, p_list = _check_pinning_24m(st)
            pinned_ever.update(p_list)

    # Check Begin's exit under high-stress HistoricalBot
    hist_begin_tenure = next((t for t in eng.state.tenures if t["leader_id"] == "begin"), None)
    hist_begin_exit_date = hist_begin_tenure["end_date"] if hist_begin_tenure else eng.state.date_str
    hist_begin_exit_year = int(hist_begin_exit_date[:4])

    # Run counterfactual Peace Decompression trajectory (avoiding 1980 self-held Defense & 1982 Lebanon quagmire)
    eng_peace = SimulationEngine(master_seed=19770620, bot=HistoricalBot(seed=19770620), allow_succession=True)
    eng_peace.state.set_flag("peace_decompression_mode", source="test_1_counterfactual")
    eng_peace.run_days(5478, stop_on_end=False)
    peace_begin_tenure = next((t for t in eng_peace.state.tenures if t["leader_id"] == "begin"), None)
    peace_begin_exit_date = peace_begin_tenure["end_date"] if peace_begin_tenure else eng_peace.state.date_str
    peace_begin_exit_year = int(peace_begin_exit_date[:4])

    y1_avg_ms = (sum(y1_times) / max(1, len(y1_times))) * 1000.0
    y15_avg_ms = (sum(y15_times) / max(1, len(y15_times))) * 1000.0
    perf_ratio = y15_avg_ms / max(1e-6, y1_avg_ms)
    pin_rate = len(pinned_ever) / float(total_core_checked)
    avg_post_1985_inf = sum(post_1985_infs) / max(1, len(post_1985_infs))

    passed = (
        pin_rate <= 0.05
        and (250.0 <= max_inf_1983_1984 <= 450.0)
        and (15.0 <= avg_post_1985_inf <= 30.0)
        and (hist_begin_exit_year == 1983)
        and (peace_begin_exit_year > 1985)
        and (perf_ratio <= 1.30)
    )

    return {
        "passed": passed,
        "days_simulated": eng.state.day_index,
        "crashes": 0,
        "pinning_rate_24m": round(pin_rate, 4),
        "pinned_params": sorted(pinned_ever),
        "inflation_1977_start": 35.0,
        "inflation_peak_1983_1984": round(max_inf_1983_1984, 2),
        "inflation_post_1985_avg": round(avg_post_1985_inf, 2),
        "inflation_by_year": inflation_by_year,
        "begin_high_stress_exit_date": hist_begin_exit_date,
        "begin_high_stress_exit_year": hist_begin_exit_year,
        "begin_peace_decompression_exit_date": peace_begin_exit_date,
        "begin_peace_decompression_exit_year": peace_begin_exit_year,
        "perf_year1_avg_ms": round(y1_avg_ms, 4),
        "perf_year15_avg_ms": round(y15_avg_ms, 4),
        "perf_y15_over_y1_ratio": round(perf_ratio, 4),
    }


def run_test_2_event_monte_carlo(n_seeds: int = 100) -> Dict[str, Any]:
    """Test 2: Event Monte Carlo (N=100 seeds), Historical Gravity (70%-80%), Deduplication & Retention."""
    print(f"[Test 2] Running Event Monte Carlo across N={n_seeds} seeds (1977-1992)...")
    anchors = [
        ("E-1977-11", "萨达特访问耶路撒冷 / 戴维营"),
        ("E-1981-06a", "巴比伦行动（空袭奥西拉克核反应堆）"),
        ("E-1982-06a", "加利利和平行动（第一次黎巴嫩战争）"),
        ("E-1983-10", "特拉维夫银行股崩盘危机"),
        ("E-1985-07", "1985年经济稳定计划（新谢克尔改革）"),
        ("E-1987-12a", "第一次巴勒斯坦大起义（Intifada）"),
    ]
    anchor_counts = {aid: 0 for aid, _ in anchors}

    total_popups_all = 0
    random_event_counts: Counter[str] = Counter()
    dedup_rates: List[float] = []
    unseen_retention_rates: List[float] = []

    reg = SimulationEngine().registry
    total_event_pool_size = len(reg.events_by_id)

    for i in range(n_seeds):
        seed = 200000 + i * 17
        eng = SimulationEngine(master_seed=seed, bot=HistoricalBot(seed=seed), allow_succession=True)
        eng.run_days(5478, stop_on_end=False)
        st = eng.state
        fired_ids = set(st.m12["fired"].keys())

        for aid, _ in anchors:
            if aid == "E-1977-11":
                if "E-1977-11" in fired_ids and "E-1978-09" in fired_ids:
                    anchor_counts[aid] += 1
            elif aid in fired_ids:
                anchor_counts[aid] += 1

        ev_log = st.history["event_log"]
        total_popups = len(ev_log)
        total_popups_all += total_popups
        unique_popups = len(set(e["event_id"] for e in ev_log))
        if total_popups > 0:
            dedup_rates.append(unique_popups / float(total_popups))
        unseen_retention_rates.append(1.0 - (unique_popups / float(max(1, total_event_pool_size))))

        for e in ev_log:
            eid = e["event_id"]
            if eid.startswith("R-"):
                random_event_counts[eid] += 1

    # Also test opposing/pushing bots (N=25 seeds each) for R31/E9 counterfactual shift
    n_cf = 25
    hawk_lebanon = 0
    dove_lebanon = 0
    tech_bank_crisis = 0
    dove_intifada = 0
    hawk_intifada = 0
    for i in range(n_cf):
        s = 300000 + i * 23
        e_hawk = SimulationEngine(master_seed=s, bot=RevisionistHawkBot(seed=s), allow_succession=True)
        e_hawk.run_days(5478, stop_on_end=False)
        if "E-1982-06a" in e_hawk.state.m12["fired"]:
            hawk_lebanon += 1
        if "E-1987-12a" in e_hawk.state.m12["fired"]:
            hawk_intifada += 1

        e_dove = SimulationEngine(master_seed=s, bot=PeaceDoveBot(seed=s), allow_succession=True)
        e_dove.run_days(5478, stop_on_end=False)
        if "E-1982-06a" in e_dove.state.m12["fired"]:
            dove_lebanon += 1
        if "E-1987-12a" in e_dove.state.m12["fired"]:
            dove_intifada += 1

        e_tech = SimulationEngine(master_seed=s, bot=NeoliberalTechnocratBot(seed=s), allow_succession=True)
        e_tech.run_days(5478, stop_on_end=False)
        if "E-1983-10" in e_tech.state.m12["fired"]:
            tech_bank_crisis += 1

    anchor_rates = {aid: round(anchor_counts[aid] / float(n_seeds), 4) for aid, _ in anchors}
    avg_anchor_rate = sum(anchor_rates.values()) / len(anchor_rates)
    max_rand_share = (max(random_event_counts.values()) / float(max(1, total_popups_all))) if random_event_counts else 0.0
    avg_dedup_rate = sum(dedup_rates) / max(1, len(dedup_rates))
    avg_unseen_retention = sum(unseen_retention_rates) / max(1, len(unseen_retention_rates))

    passed = (
        (0.70 <= avg_anchor_rate <= 0.80)
        and (max_rand_share <= 0.03)
        and (avg_dedup_rate >= 0.85)
        and (avg_unseen_retention >= 0.35)
    )

    return {
        "passed": passed,
        "n_seeds": n_seeds,
        "anchor_replay_rates": anchor_rates,
        "anchor_labels": {aid: lbl for aid, lbl in anchors},
        "average_anchor_replay_rate": round(avg_anchor_rate, 4),
        "counterfactual_shifts": {
            "lebanon_war_hawk_rate": round(hawk_lebanon / float(n_cf), 4),
            "lebanon_war_dove_rate": round(dove_lebanon / float(n_cf), 4),
            "bank_crisis_technocrat_rate": round(tech_bank_crisis / float(n_cf), 4),
            "intifada_hawk_rate": round(hawk_intifada / float(n_cf), 4),
            "intifada_dove_rate": round(dove_intifada / float(n_cf), 4),
        },
        "max_single_random_event_popup_share": round(max_rand_share, 4),
        "event_deduplication_rate": round(avg_dedup_rate, 4),
        "unseen_event_retention_rate": round(avg_unseen_retention, 4),
    }


def run_test_3_and_4_bot_tournament(runs_per_bot: int = 32) -> Dict[str, Any]:
    """Test 3 & Test 4: 7 Strategy Bot Tournament (>=210 campaigns) & Political Capital Audit."""
    print(f"[Test 3 & 4] Running 7 Strategy Bot Tournament ({runs_per_bot} runs/bot = {7 * runs_per_bot} campaigns)...")
    dim_keys = ["security", "economy", "cohesion", "democracy", "diplomacy", "territory", "palestine", "leadership"]
    bot_classes = [
        HistoricalBot,
        RevisionistHawkBot,
        PeaceDoveBot,
        PopulistWelfareBot,
        NeoliberalTechnocratBot,
        AuthoritarianCaesarBot,
        RandomBot,
    ]

    bot_dim_sums: Dict[str, Dict[str, float]] = {b.bot_id: {d: 0.0 for d in dim_keys} for b in bot_classes}
    bot_overall_scores: Dict[str, List[float]] = {b.bot_id: [] for b in bot_classes}
    bot_grades: Dict[str, Counter[str]] = {b.bot_id: Counter() for b in bot_classes}
    bot_survival_15y: Dict[str, int] = {b.bot_id: 0 for b in bot_classes}
    bot_promise_rates: Dict[str, List[float]] = {b.bot_id: [] for b in bot_classes}
    bot_corridor_rates: Dict[str, List[float]] = {b.bot_id: [] for b in bot_classes}
    bot_vision_achieved: Dict[str, int] = {b.bot_id: 0 for b in bot_classes}
    bot_pc_block_rates: Dict[str, List[float]] = {b.bot_id: [] for b in bot_classes}

    ending_counts_campaign: Counter[str] = Counter()
    ending_counts_all_tenures: Counter[str] = Counter()

    el_1st_won = 0
    el_1st_total = 0
    el_3rd_plus_won = 0
    el_3rd_plus_total = 0

    for b_idx, bot_cls in enumerate(bot_classes):
        bid = bot_cls.bot_id
        for r in range(runs_per_bot):
            seed = 500000 + b_idx * 1000 + r * 31
            bot_inst = bot_cls(seed=seed)
            # Enable succession for democratic bots so all 15-year campaigns reach 1992 while intermediate tenures are logged in st.tenures
            allow_succ = (bid != "authoritarian_caesar")
            eng = SimulationEngine(master_seed=seed, bot=bot_inst, allow_succession=allow_succ)
            eng.run_days(5478, stop_on_end=True)
            st = eng.state

            ev_rep = st.m14.get("final_evaluation")
            if not ev_rep:
                ev_rep = st.tenures[-1]["evaluation"] if st.tenures else None
            if not ev_rep:
                continue

            for d in dim_keys:
                bot_dim_sums[bid][d] += float(ev_rep["dimensions"].get(d, 50.0))
            bot_overall_scores[bid].append(float(ev_rep["overall_score"]))
            bot_grades[bid][str(ev_rep["final_grade"])] += 1

            if st.day_index >= 5478 and ev_rep["end_reason"] not in ("coup", "assassination", "overthrow", "state_collapse"):
                bot_survival_15y[bid] += 1

            l_scores = ev_rep.get("layer_scores", {})
            bot_promise_rates[bid].append(float(l_scores.get("promise_fulfillment_rate", 0.5)))
            bot_corridor_rates[bid].append(float(l_scores.get("corridor_inside_rate", 0.5)))
            if st.vision.get("status") == "achieved" or any(t["evaluation"]["layer_scores"].get("vision_achieved") for t in st.tenures):
                bot_vision_achieved[bid] += 1

            m_des = max(1, int(st.m05.get("months_action_desired", 1)))
            m_blk = int(st.m05.get("months_pc_blocked", 0))
            bot_pc_block_rates[bid].append(m_blk / float(m_des))

            ending_counts_campaign[str(ev_rep["ending_id"])] += 1
            for t in st.tenures:
                ending_counts_all_tenures[str(t["ending_id"])] += 1

            for el in st.m03.get("election_history", []):
                e_idx = int(el.get("election_index", 1))
                won = bool(el.get("won", False))
                if e_idx == 1:
                    el_1st_total += 1
                    if won:
                        el_1st_won += 1
                elif e_idx >= 3:
                    el_3rd_plus_total += 1
                    if won:
                        el_3rd_plus_won += 1

    # Compute 7 Bot x 8 Dimension averages
    matrix_8d: Dict[str, Dict[str, float]] = {}
    for b in bot_classes:
        bid = b.bot_id
        n_b = max(1, len(bot_overall_scores[bid]))
        matrix_8d[bid] = {d: round(bot_dim_sums[bid][d] / float(n_b), 2) for d in dim_keys}

    # Find #1 bot for each dimension
    dim_winners: Dict[str, str] = {}
    win_counts_by_bot: Counter[str] = Counter()
    for d in dim_keys:
        best_bot = max(bot_classes, key=lambda b: matrix_8d[b.bot_id][d]).bot_id
        dim_winners[d] = best_bot
        win_counts_by_bot[best_bot] += 1

    max_dims_won_by_single_bot = max(win_counts_by_bot.values()) if win_counts_by_bot else 8

    # Authoritarian checks (R32 / X2)
    auth_surv_rate = bot_survival_15y["authoritarian_caesar"] / float(runs_per_bot)
    auth_mean_score = sum(bot_overall_scores["authoritarian_caesar"]) / max(1, len(bot_overall_scores["authoritarian_caesar"]))
    dem_bots = ["historical", "revisionist_hawk", "peace_dove", "populist_welfare", "neoliberal_technocrat"]
    dem_mean_score = sum(sum(bot_overall_scores[b]) / max(1, len(bot_overall_scores[b])) for b in dem_bots) / len(dem_bots)
    auth_score_deficit = dem_mean_score - auth_mean_score
    auth_grades = bot_grades["authoritarian_caesar"]
    auth_grade_capped_ok = (auth_grades.get("S", 0) == 0 and auth_grades.get("A", 0) == 0)

    # Grand vision achievement rate across tournament (target: 8%-25%)
    total_runs = 7 * runs_per_bot
    total_vision_achieved = sum(bot_vision_achieved.values())
    vision_rate = total_vision_achieved / float(total_runs)

    # Ending diversity across all tenures/campaigns in the tournament (R1/R2)
    combined_endings = ending_counts_all_tenures
    total_endings_recorded = sum(combined_endings.values())
    distinct_endings_count = len(combined_endings)
    shannon_h = 0.0
    max_single_ending_share = 0.0
    for eid, cnt in combined_endings.items():
        p = cnt / float(total_endings_recorded)
        if p > 0:
            shannon_h -= p * math.log(p)
        max_single_ending_share = max(max_single_ending_share, p)
    n_eff = math.exp(shannon_h)

    # Governing fatigue (Metric S1)
    win_rate_1st = el_1st_won / float(max(1, el_1st_total))
    win_rate_3rd_plus = el_3rd_plus_won / float(max(1, el_3rd_plus_total))
    fatigue_ok = win_rate_3rd_plus <= (win_rate_1st + 0.05)

    # Test 4: Political Capital block rate (Metric S6 <= 30%)
    pc_block_by_bot = {
        b.bot_id: round(sum(bot_pc_block_rates[b.bot_id]) / max(1, len(bot_pc_block_rates[b.bot_id])), 4)
        for b in bot_classes
    }
    avg_pc_block_rate = sum(pc_block_by_bot.values()) / len(pc_block_by_bot)
    max_pc_block_rate = max(pc_block_by_bot.values())

    test_3_passed = (
        (max_dims_won_by_single_bot <= 3)
        and (0.08 <= vision_rate <= 0.25)
        and (auth_surv_rate <= 0.35)
        and (auth_score_deficit >= 15.0)
        and auth_grade_capped_ok
        and (distinct_endings_count >= 28)
        and (n_eff >= 14.0)
        and (max_single_ending_share <= 0.18)
        and fatigue_ok
    )
    test_4_passed = max_pc_block_rate <= 0.30

    return {
        "test_3": {
            "passed": test_3_passed,
            "runs_per_bot": runs_per_bot,
            "total_campaigns": total_runs,
            "matrix_8d": matrix_8d,
            "bot_overall_mean": {
                b.bot_id: round(sum(bot_overall_scores[b.bot_id]) / max(1, len(bot_overall_scores[b.bot_id])), 2)
                for b in bot_classes
            },
            "bot_grades": {b.bot_id: dict(bot_grades[b.bot_id]) for b in bot_classes},
            "dimension_winners": dim_winners,
            "win_counts_by_bot": dict(win_counts_by_bot),
            "max_dims_won_by_single_bot": max_dims_won_by_single_bot,
            "three_layer_goals": {
                "promise_fulfillment_by_bot": {
                    b.bot_id: round(sum(bot_promise_rates[b.bot_id]) / max(1, len(bot_promise_rates[b.bot_id])), 4)
                    for b in bot_classes
                },
                "corridor_inside_by_bot": {
                    b.bot_id: round(sum(bot_corridor_rates[b.bot_id]) / max(1, len(bot_corridor_rates[b.bot_id])), 4)
                    for b in bot_classes
                },
                "vision_achieved_by_bot": {
                    b.bot_id: round(bot_vision_achieved[b.bot_id] / float(runs_per_bot), 4)
                    for b in bot_classes
                },
                "overall_vision_achievement_rate": round(vision_rate, 4),
            },
            "authoritarian_iron_law": {
                "survival_rate_15y": round(auth_surv_rate, 4),
                "authoritarian_mean_score": round(auth_mean_score, 2),
                "democratic_mean_score": round(dem_mean_score, 2),
                "score_deficit_vs_democratic": round(auth_score_deficit, 2),
                "grade_distribution": dict(auth_grades),
                "grade_capped_at_B_or_below": auth_grade_capped_ok,
            },
            "ending_diversity": {
                "distinct_endings_triggered": distinct_endings_count,
                "total_endings_catalog": len(ALL_40_ENDINGS),
                "shannon_entropy_h": round(shannon_h, 4),
                "effective_endings_neff": round(n_eff, 2),
                "max_single_ending_share": round(max_single_ending_share, 4),
                "ending_distribution": dict(combined_endings.most_common()),
            },
            "governing_fatigue_s1": {
                "first_reelection_win_rate": round(win_rate_1st, 4),
                "first_reelection_total": el_1st_total,
                "third_plus_reelection_win_rate": round(win_rate_3rd_plus, 4),
                "third_plus_reelection_total": el_3rd_plus_total,
                "passed": fatigue_ok,
            },
        },
        "test_4": {
            "passed": test_4_passed,
            "pc_block_rate_by_bot": pc_block_by_bot,
            "average_pc_block_rate": round(avg_pc_block_rate, 4),
            "max_pc_block_rate": round(max_pc_block_rate, 4),
        },
    }


def main() -> int:
    t_start = time.perf_counter()
    res_1 = run_test_1_system_dynamics()
    res_2 = run_test_2_event_monte_carlo(n_seeds=100)
    res_34 = run_test_3_and_4_bot_tournament(runs_per_bot=32)

    elapsed = time.perf_counter() - t_start
    full_report = {
        "elapsed_seconds": round(elapsed, 2),
        "all_passed": bool(res_1["passed"] and res_2["passed"] and res_34["test_3"]["passed"] and res_34["test_4"]["passed"]),
        "test_1_system_dynamics": res_1,
        "test_2_event_monte_carlo": res_2,
        "test_3_bot_tournament": res_34["test_3"],
        "test_4_pc_audit": res_34["test_4"],
    }

    out_path = os.path.join(ROOT, "data", "validation_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 78)
    print(f"PHASE 3C VALIDATION SUITE SUMMARY (elapsed: {elapsed:.1f}s)")
    print("=" * 78)
    print(f"  Test 1 (System Dynamics & 1977-1992 Calibration): {'PASS' if res_1['passed'] else 'FAIL'}")
    print(f"    - Pinning >=24m rate: {res_1['pinning_rate_24m']:.1%} (<=5.0%)")
    print(f"    - 1983-1984 Peak Inflation: {res_1['inflation_peak_1983_1984']:.1f}% (target 250%-450%)")
    print(f"    - Post-1985 Avg Inflation:  {res_1['inflation_post_1985_avg']:.1f}% (target 15%-30%)")
    print(f"    - Begin Exit (High Stress vs Peace): {res_1['begin_high_stress_exit_date']} vs {res_1['begin_peace_decompression_exit_date']}")
    print(f"    - Perf Y15/Y1 Ratio: {res_1['perf_y15_over_y1_ratio']:.2f}x (<=1.30x)")
    print(f"  Test 2 (Event Monte Carlo N=100 & Gravity):       {'PASS' if res_2['passed'] else 'FAIL'}")
    print(f"    - Avg 6-Anchor Replay Rate: {res_2['average_anchor_replay_rate']:.1%} (target 70%-80%)")
    for aid, rate in res_2["anchor_replay_rates"].items():
        print(f"      * {aid}: {rate:.1%}")
    print(f"    - Max Random Event Share:   {res_2['max_single_random_event_popup_share']:.2%} (<=3.0%)")
    print(f"    - Deduplication Rate:       {res_2['event_deduplication_rate']:.1%} (>=85.0%)")
    print(f"    - Unseen Event Retention:   {res_2['unseen_event_retention_rate']:.1%} (>=35.0%)")
    t3 = res_34["test_3"]
    print(f"  Test 3 (7 Strategy Bot Tournament, 224 runs):     {'PASS' if t3['passed'] else 'FAIL'}")
    print(f"    - Max #1 Dims by Single Bot: {t3['max_dims_won_by_single_bot']}/8 (<=3) -> {t3['dimension_winners']}")
    print(f"    - Grand Vision Achievement:  {t3['three_layer_goals']['overall_vision_achievement_rate']:.1%} (target 8%-25%)")
    print(f"    - Authoritarian 15y Surv:    {t3['authoritarian_iron_law']['survival_rate_15y']:.1%} (<=35.0%), Deficit: -{t3['authoritarian_iron_law']['score_deficit_vs_democratic']:.1f} pts")
    print(f"    - Ending Diversity:          {t3['ending_diversity']['distinct_endings_triggered']}/40 (>=28), Neff={t3['ending_diversity']['effective_endings_neff']:.2f} (>=14.0), MaxShare={t3['ending_diversity']['max_single_ending_share']:.1%} (<=18.0%)")
    print(f"    - Governing Fatigue (S1):    1st={t3['governing_fatigue_s1']['first_reelection_win_rate']:.1%} vs 3rd+={t3['governing_fatigue_s1']['third_plus_reelection_win_rate']:.1%}")
    t4 = res_34["test_4"]
    print(f"  Test 4 (Political Capital Block Audit S6):        {'PASS' if t4['passed'] else 'FAIL'}")
    print(f"    - Avg PC Block Rate: {t4['average_pc_block_rate']:.1%}, Max Bot PC Block Rate: {t4['max_pc_block_rate']:.1%} (<=30.0%)")
    print("=" * 78)
    return 0 if full_report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
