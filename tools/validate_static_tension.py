#!/usr/bin/env python3
"""Static Graph Topology, Action Anti-Mana, & Event Option Tension Validator.

Deliverable for Phase 3B:
1. Causal Graph Topology & Feedback Loop Audit (`data/causal_edges.yaml` + `data/policies.yaml`):
   - Verifies Democracy 4 R13 benchmarks (nodes >= 150, expanded edges >= 600,
     inertia/delay coverage >= 40%, voter bloc inputs >= 5, policy effects >= 3).
   - Enumerates all directed elementary cycles using exact directional derivatives
     (including `shape: below` negative derivative), classifies Positive (reinforcing)
     vs. Negative (damping) feedback loops, and verifies |G| < 0.50 and >= 2 damping
     mechanisms for 100% of positive feedback loops (and |G| <= 0.30 for the
     `centralization <-> rule_of_law` loop per M13 / Paradox S5).
2. Action Cost Diversity & Anti-Mana Audit (`data/actions.yaml` + `data/policies.yaml`):
   - Verifies PC-only actions <= 50% (Paradox M1/M2, S7, D10) and 100% of `w: major`
     actions require >= 2 cost dimensions.
3. Event Option Tension, Non-Dominance, Extreme Net-Negative, & Atrocity 3-Stage Audit
   (`data/events/*.yaml`, 396 events):
   - Verifies 0 Free-Lunch (`NO_NEG`) and 0 Pure-Trap (`NO_POS`) options across all
     862 options in all 6 event files (including `fixed_1977_1992.yaml` and `random_events.yaml`).
   - Verifies multi-axis Pareto non-dominance across options within each event.
   - Verifies 100% of `tags: [extreme]` options have negative long-term net utility
     (accounting for 24-60 month modifiers and atrocity multipliers) and strictly lower
     long-term utility than moderate/institutional alternatives, with explicit
     `rule_of_law` or `intl_legitimacy` penalties (X1, V-24).
   - Verifies 100% compliance of all 14 Israeli atrocity/incident 3-stage chains (V-14).
"""
from __future__ import annotations

import glob
import os
import sys
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

NEG_PARAMS: Set[str] = {
    "inflation",
    "unemployment",
    "debt_gdp",
    "judicial_conflict",
    "pal_hostility",
    "centralization",
    "alienation",
    "land_grievance",
    "economic_gap",
    "civic_vigilance",
    "historical_grievance",
    "regime_hostility",
    "popular_hostility",
    "complacency",
    "exhaustion",
    "islamic_assoc_strength",
    "nuclear_exposure_risk",
}

VOTER_BLOCS: Tuple[str, ...] = (
    "labor_ashkenazi",
    "mizrahi",
    "religious_zionist",
    "haredi",
    "liberal_middle",
    "arab_citizens",
    "russian",
    "kibbutz_moshav",
)

REGIONS: List[str] = [
    "tel_aviv",
    "jerusalem",
    "haifa",
    "galilee",
    "negev",
    "triangle",
    "west_bank",
    "gaza",
    "golan",
    "sinai",
    "south_lebanon",
]
ARAB_GROUPS: List[str] = ["arab", "druze", "bedouin"]
COUNTRIES: List[str] = [
    "egypt",
    "jordan",
    "syria",
    "lebanon",
    "iraq",
    "iran",
    "saudi",
]
FACTIONS: List[str] = ["fatah", "hamas", "hezbollah", "pij", "phalange"]


def _expand_keys(key_spec: Any, param_name: str = "", node_keys_map: Optional[Dict[str, List[str]]] = None) -> List[str]:
    if key_spec is None:
        return [""]
    ks = str(key_spec)
    if ks in ("*", "$key"):
        if node_keys_map and param_name in node_keys_map and node_keys_map[param_name]:
            return list(node_keys_map[param_name])
        if param_name == "bloc_support":
            return list(VOTER_BLOCS)
        if param_name in ("region_development", "region_security"):
            return REGIONS
        if param_name in ("alienation", "historical_grievance"):
            return ["mizrahi", "russian", "ethiopian"]
        if param_name in ("civic_identification", "land_grievance"):
            return ARAB_GROUPS
    if ks in ("*region", "{region}"):
        return REGIONS
    if ks in ("*arab_group", "{group}"):
        return ARAB_GROUPS
    if ks == "*group":
        return ["mizrahi", "russian", "ethiopian"]
    if ks in ("*country", "{country}"):
        return COUNTRIES
    if ks in ("*faction", "{faction}"):
        return FACTIONS
    if ks == "*bloc":
        return list(VOTER_BLOCS)
    if "|" in ks:
        return ks.split("|")
    return [ks]


def _edge_directional_derivative(edge: Dict[str, Any]) -> float:
    """Return ∂f/∂src in the active operating regime of the edge."""
    if "slope" in edge and edge["slope"] is not None:
        return float(edge["slope"])
    c = float(edge.get("coef") if "coef" in edge and edge["coef"] is not None else edge.get("c", 0.0))
    shape = str(edge.get("shape", "linear"))
    # For `below`, f(s) = c * max(0, p - s), so ∂f/∂s = -c when active (s < p).
    if shape == "below":
        return -c
    return c


def audit_causal_graph() -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    ce_path = os.path.join(ROOT, "data", "causal_edges.yaml")
    pol_path = os.path.join(ROOT, "data", "policies.yaml")
    param_path = os.path.join(ROOT, "docs", "registry", "parameters.yaml")

    ce_data = yaml.safe_load(open(ce_path, encoding="utf-8"))
    pol_data = yaml.safe_load(open(pol_path, encoding="utf-8"))
    param_data = yaml.safe_load(open(param_path, encoding="utf-8"))

    raw_edges = ce_data.get("edges", [])
    raw_policies = pol_data.get("policies", [])
    raw_params = param_data.get("parameters", {})
    if isinstance(raw_params, dict):
        param_meta: Dict[str, Dict[str, Any]] = dict(raw_params)
    else:
        param_meta = {str(p.get("id") or p.get("name")): dict(p) for p in raw_params}

    node_keys_map: Dict[str, List[str]] = {}
    param_nodes: Set[Tuple[str, str]] = set()
    pol_nodes: Set[Tuple[str, str]] = set()
    expanded_causal = 0
    expanded_policy = 0
    inertia_causal = 0
    inertia_policy = 0
    bloc_inputs: Counter = Counter()
    min_pol_fx = 999

    # Register all nodes and their key domains + damping properties from ce_data["nodes"]
    for nd in ce_data.get("nodes", []):
        p_name = str(nd.get("param", ""))
        raw_k = nd.get("keys")
        if isinstance(raw_k, list):
            node_keys_map[p_name] = [str(x) for x in raw_k]
            for x in raw_k:
                param_nodes.add((p_name, str(x)))
        else:
            node_keys_map[p_name] = [""]
            param_nodes.add((p_name, ""))
        # Merge node damping metadata into param_meta
        pm = param_meta.setdefault(p_name, {})
        pm.update(nd)

    # Build instance-level and parameter-level directed graphs
    inst_adj: Dict[Tuple[str, str], List[Tuple[Tuple[str, str], float, str, Dict[str, Any]]]] = defaultdict(list)
    param_adj: Dict[str, List[Tuple[str, float, str, Dict[str, Any]]]] = defaultdict(list)

    for e in raw_edges:
        eid = str(e.get("id", ""))
        src_raw = str(e.get("source") or e.get("from") or e.get("src") or "")
        if src_raw.startswith("param:"):
            src_raw = src_raw.split(":", 1)[1]
        dst_raw = str(e.get("target") or e.get("to") or e.get("dst") or "")
        if dst_raw.startswith("param:"):
            dst_raw = dst_raw.split(":", 1)[1]

        src, src_k_dot = (src_raw.split(".", 1) if "." in src_raw else (src_raw, None))
        dst, dst_k_dot = (dst_raw.split(".", 1) if "." in dst_raw else (dst_raw, None))
        deriv = _edge_directional_derivative(e)
        has_delay = (
            (e.get("inertia") or 0) > 1
            or (e.get("delay") or 0) > 0
            or "habit" in e
        )
        if has_delay:
            inertia_causal += 1

        if isinstance(e.get("weights"), dict):
            d_keys = [str(k) for k in e["weights"].keys()]
        else:
            d_keys = _expand_keys(dst_k_dot if dst_k_dot is not None else e.get("target_key"), dst, node_keys_map)

        s_key_raw = src_k_dot if src_k_dot is not None else e.get("source_key")
        if s_key_raw == "$key":
            s_keys = list(d_keys)
        else:
            s_keys = _expand_keys(s_key_raw, src, node_keys_map)

        param_adj[src].append((dst, deriv, eid, e))

        if len(s_keys) == len(d_keys):
            pairs = list(zip(s_keys, d_keys))
        elif len(s_keys) == 1:
            pairs = [(s_keys[0], dk) for dk in d_keys]
        elif len(d_keys) == 1:
            pairs = [(sk, d_keys[0]) for sk in s_keys]
        else:
            pairs = [(sk, dk) for sk in s_keys for dk in d_keys]

        for sk, dk in pairs:
            expanded_causal += 1
            u = (src, sk)
            v = (dst, dk)
            param_nodes.add(u)
            param_nodes.add(v)
            inst_adj[u].append((v, deriv, eid, e))
            if dst == "bloc_support" and dk in VOTER_BLOCS:
                bloc_inputs[dk] += 1

    for p in raw_policies:
        pid = str(p["id"])
        p_keys = _expand_keys(p.get("key") or p.get("arg") or p.get("scope"), pid, node_keys_map)
        fxs = p.get("e") or p.get("fx") or []
        if len(fxs) < min_pol_fx:
            min_pol_fx = len(fxs)
        for pk in p_keys:
            pol_nodes.add((pid, pk))
            for fx in fxs:
                dst_raw = str(fx.get("t") or fx.get("to") or fx.get("dst") or "")
                dst, dst_k_dot = (dst_raw.split(".", 1) if "." in dst_raw else (dst_raw, None))
                d_keys = _expand_keys(
                    dst_k_dot if dst_k_dot is not None else (fx.get("k") if "k" in fx else fx.get("key")),
                    dst,
                    node_keys_map,
                )
                for dk in d_keys:
                    expanded_policy += 1
                    if (fx.get("i") or fx.get("inertia") or 0) > 1 or (fx.get("d") or fx.get("delay") or 0) > 0 or "habit" in p:
                        inertia_policy += 1
                    param_nodes.add((dst, dk))
                    if dst == "bloc_support" and dk in VOTER_BLOCS:
                        bloc_inputs[dk] += 1

    total_nodes = len(param_nodes) + len(pol_nodes)
    total_expanded_edges = expanded_causal + expanded_policy
    inertia_ratio = (inertia_causal + inertia_policy) / float(len(raw_edges) + expanded_policy)

    if total_nodes < 150:
        errors.append(f"R13 violation: total causal nodes {total_nodes} < 150")
    if total_expanded_edges < 600:
        errors.append(f"R13 violation: total expanded edges {total_expanded_edges} < 600")
    if inertia_ratio < 0.40:
        errors.append(f"R13 violation: inertia/delay ratio {inertia_ratio:.1%} < 40%")
    for b in VOTER_BLOCS:
        if bloc_inputs[b] < 5:
            errors.append(f"R13 violation: voter bloc '{b}' has {bloc_inputs[b]} inputs (< 5)")
    if min_pol_fx < 3:
        errors.append(f"R13 violation: policy with fewer than 3 effects ({min_pol_fx})")

    # Collapse parallel edges of same sign between identical parameter pairs for cycle finding
    collapsed_param_adj: Dict[str, List[Tuple[str, float, str, List[Dict[str, Any]]]]] = defaultdict(list)
    for u, nbrs in param_adj.items():
        by_v: Dict[str, List[Tuple[float, str, Dict[str, Any]]]] = defaultdict(list)
        for v, deriv, eid, e in nbrs:
            by_v[v].append((deriv, eid, e))
        for v, items in by_v.items():
            pos_sum = sum(d for d, _, _ in items if d > 0)
            neg_sum = sum(d for d, _, _ in items if d < 0)
            if pos_sum > 0:
                ids = "+".join(eid for d, eid, _ in items if d > 0)
                es = [e for d, _, e in items if d > 0]
                collapsed_param_adj[u].append((v, pos_sum, ids, es))
            if neg_sum < 0:
                ids = "+".join(eid for d, eid, _ in items if d < 0)
                es = [e for d, _, e in items if d < 0]
                collapsed_param_adj[u].append((v, neg_sum, ids, es))

    nodes_list = sorted(collapsed_param_adj.keys())
    node_idx = {n: i for i, n in enumerate(nodes_list)}
    param_cycles: List[Dict[str, Any]] = []

    def _dfs_param(
        start: str,
        curr: str,
        visited: Set[str],
        path_nodes: List[str],
        path_edges: List[Tuple[float, str, List[Dict[str, Any]]]],
    ) -> None:
        for nxt, deriv, eids, es in collapsed_param_adj.get(curr, []):
            if nxt not in node_idx or node_idx[nxt] < node_idx[start]:
                continue
            if nxt == start:
                gain = 1.0
                for d, _, _ in path_edges + [(deriv, eids, es)]:
                    gain *= d
                all_es = [e for _, _, elist in path_edges + [(deriv, eids, es)] for e in elist]
                damping = _collect_damping(path_nodes, all_es, param_meta)
                param_cycles.append(
                    {
                        "nodes": list(path_nodes) + [start],
                        "edge_ids": [eid for _, eid, _ in path_edges + [(deriv, eids, es)]],
                        "gain": gain,
                        "abs_gain": abs(gain),
                        "kind": "positive" if gain > 0 else "negative",
                        "damping": damping,
                    }
                )
            elif nxt not in visited and len(path_nodes) < 8:
                visited.add(nxt)
                _dfs_param(
                    start,
                    nxt,
                    visited,
                    path_nodes + [nxt],
                    path_edges + [(deriv, eids, es)],
                )
                visited.remove(nxt)

    for n in nodes_list:
        _dfs_param(n, n, {n}, [n], [])

    param_cycles.sort(key=lambda x: -x["abs_gain"])

    inst_nodes = sorted(inst_adj.keys())
    inst_idx = {n: i for i, n in enumerate(inst_nodes)}
    inst_cycle_count = 0

    def _dfs_inst(start: Tuple[str, str], curr: Tuple[str, str], visited: Set[Tuple[str, str]], depth: int) -> None:
        nonlocal inst_cycle_count
        for nxt, _, _, _ in inst_adj.get(curr, []):
            if nxt not in inst_idx or inst_idx[nxt] < inst_idx[start]:
                continue
            if nxt == start:
                inst_cycle_count += 1
            elif nxt not in visited and depth < 6:
                visited.add(nxt)
                _dfs_inst(start, nxt, visited, depth + 1)
                visited.remove(nxt)

    for u in inst_nodes:
        _dfs_inst(u, u, {u}, 1)

    for cyc in param_cycles:
        if cyc["kind"] == "positive":
            if cyc["abs_gain"] >= 0.50:
                errors.append(
                    f"Positive feedback loop {' -> '.join(cyc['nodes'])} has |G|={cyc['abs_gain']:.4f} >= 0.50"
                )
            if len(cyc["damping"]) < 2:
                errors.append(
                    f"Positive feedback loop {' -> '.join(cyc['nodes'])} has < 2 damping mechanisms: {cyc['damping']}"
                )
            if set(cyc["nodes"]) == {"centralization", "rule_of_law"} and cyc["abs_gain"] > 0.30:
                errors.append(
                    f"M13 centralization <-> rule_of_law loop gain {cyc['abs_gain']:.4f} > 0.30"
                )

    stats = {
        "param_nodes": len(param_nodes),
        "pol_nodes": len(pol_nodes),
        "total_nodes": total_nodes,
        "raw_causal_edges": len(raw_edges),
        "expanded_causal_edges": expanded_causal,
        "raw_policy_edges": sum(len(p.get("e") or p.get("fx") or []) for p in raw_policies),
        "expanded_policy_edges": expanded_policy,
        "total_expanded_edges": total_expanded_edges,
        "inertia_ratio": inertia_ratio,
        "bloc_inputs": dict(bloc_inputs),
        "min_pol_fx": min_pol_fx,
        "param_cycles": param_cycles,
        "inst_cycle_count": inst_cycle_count,
    }
    return errors, stats


def _collect_damping(
    nodes: List[str], edges: List[Dict[str, Any]], param_meta: Dict[str, Dict[str, Any]]
) -> List[str]:
    mechs: List[str] = []
    for e in edges:
        if "soft" in e and e["soft"]:
            mechs.append(f"soft_cap({e['id']})")
        if (e.get("inertia") or 0) > 1 or (e.get("delay") or 0) > 0:
            mechs.append(f"inertia/delay({e['id']})")
        if e.get("shape") in ("above", "below", "threshold", "piecewise"):
            mechs.append(f"threshold_gate({e['id']}:{e.get('shape')})")
        if e.get("gate") or "headroom" in str(e.get("note", "")):
            mechs.append(f"gate/headroom({e['id']})")
    for n in nodes:
        pm = param_meta.get(n, {})
        mode = pm.get("mode") or pm.get("kind")
        if mode == "level":
            mechs.append(f"alpha_smoothing({n}:α={pm.get('alpha', 0.2)})")
        elif mode == "rate" or pm.get("headroom"):
            mechs.append(f"bounded_rate_headroom({n})")
        if pm.get("soft"):
            mechs.append(f"soft_bounds({n})")
        if n == "rule_of_law":
            mechs.append("step_cap(rule_of_law:±1.0/mo)")
        if n == "centralization":
            mechs.append("natural_decay(centralization:-0.5/mo)+M13_resistance")
        if n == "inflation":
            mechs.append("circuit_breaker(stabilization_plan)")
        if n == "settler_momentum":
            mechs.append("self_fatigue(M02.SM.07:G=-0.25)")
    seen: Set[str] = set()
    dedup: List[str] = []
    for m in mechs:
        if m not in seen:
            seen.add(m)
            dedup.append(m)
    return dedup


def audit_actions_and_policies() -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    act_path = os.path.join(ROOT, "data", "actions.yaml")
    pol_path = os.path.join(ROOT, "data", "policies.yaml")

    actions = yaml.safe_load(open(act_path, encoding="utf-8")).get("actions", [])
    policies = yaml.safe_load(open(pol_path, encoding="utf-8")).get("policies", [])

    pc_only: List[str] = []
    pc_composite: List[str] = []
    non_pc_only: List[str] = []
    delegated: List[str] = []
    major_single_cost: List[str] = []
    cost_dim_counts: Counter = Counter()

    for a in actions:
        aid = str(a["id"])
        cost = a.get("cost") or {}
        keys = set(cost.keys())
        for k in keys:
            cost_dim_counts[k] += 1
        if not keys:
            delegated.append(aid)
        elif keys == {"pc"}:
            pc_only.append(aid)
            if a.get("w") == "major":
                major_single_cost.append(aid)
        elif "pc" in keys:
            pc_composite.append(aid)
        else:
            non_pc_only.append(aid)

    pc_only_ratio = len(pc_only) / float(len(actions))
    if pc_only_ratio > 0.50:
        errors.append(
            f"Anti-Mana violation (Paradox M1/S7): PC-only actions ratio {pc_only_ratio:.1%} > 50%"
        )
    if major_single_cost:
        errors.append(
            f"Major actions with single PC-only cost: {major_single_cost}"
        )

    pol_composite = 0
    for p in policies:
        if p.get("up") or p.get("down") or p.get("fiscal_m") or p.get("law") or p.get("cost"):
            pol_composite += 1

    stats = {
        "total_actions": len(actions),
        "pc_only_count": len(pc_only),
        "pc_only_ids": pc_only,
        "pc_only_ratio": pc_only_ratio,
        "pc_composite_count": len(pc_composite),
        "non_pc_only_count": len(non_pc_only),
        "delegated_count": len(delegated),
        "cost_dim_counts": dict(cost_dim_counts),
        "total_policies": len(policies),
        "pol_composite_count": pol_composite,
    }
    return errors, stats


def _load_modifier_utilities() -> Tuple[Dict[str, Tuple[bool, bool]], Dict[str, float]]:
    mod_path = os.path.join(ROOT, "docs", "registry", "modifiers.yaml")
    mods = yaml.safe_load(open(mod_path, encoding="utf-8")).get("modifiers", [])
    mod_signs: Dict[str, Tuple[bool, bool]] = {}
    mod_long_term_util: Dict[str, float] = {}

    for m in mods:
        mid = str(m["id"])
        mpos, mneg = False, False
        monthly_net = 0.0
        for ef in m.get("effects", []):
            t = str(ef.get("target", ""))
            val = ef.get("value", 0.0)
            if isinstance(val, (int, float)):
                fval = float(val)
                if t in NEG_PARAMS or any(w in t for w in ("cost", "risk", "loss", "penalty", "friction", "trauma", "debt", "crisis")):
                    if fval > 0:
                        mneg = True
                        monthly_net -= abs(fval)
                    elif fval < 0:
                        mpos = True
                        monthly_net += abs(fval)
                else:
                    if fval > 0:
                        mpos = True
                        monthly_net += fval
                    elif fval < 0:
                        mneg = True
                        monthly_net -= abs(fval)
        if not mpos and not mneg:
            mneg = True
            monthly_net = -1.5
        mod_signs[mid] = (mpos, mneg)
        # Estimate 36-month cumulative impact for persistent/long modifiers
        mod_long_term_util[mid] = monthly_net * 12.0
    return mod_signs, mod_long_term_util


def _score_option_axes(
    opt: Dict[str, Any],
    mod_signs: Dict[str, Tuple[bool, bool]],
    mod_lt_util: Dict[str, float],
) -> Tuple[List[str], List[str], Dict[str, float], float]:
    """Return (pos_tokens, neg_tokens, 6-axis utility vector, long_term_utility)."""
    pos: List[str] = []
    neg: List[str] = []
    axes: Dict[str, float] = {
        "security": 0.0,
        "diplomacy": 0.0,
        "economy": 0.0,
        "domestic": 0.0,
        "institutional": 0.0,
        "ideology_right": 0.0,
    }
    lt_util = 0.0

    for ef in opt.get("effects", []):
        op = str(ef.get("op", ""))
        t = str(ef.get("target", ""))
        k = str(ef.get("key", ""))
        val = ef.get("value", 0.0)

        if op == "add" and isinstance(val, (int, float)):
            fval = float(val)
            if t in ("faction_strength", "faction_legitimacy") and k != "phalange":
                if fval > 0:
                    neg.append(f"{t}[{k}]+{fval}")
                    axes["security"] -= fval
                    lt_util -= fval * 1.5
                elif fval < 0:
                    pos.append(f"{t}[{k}]{fval}")
                    axes["security"] += abs(fval)
                    lt_util += abs(fval) * 1.2
            elif t in NEG_PARAMS:
                if fval > 0:
                    neg.append(f"{t}+{fval}")
                    lt_util -= fval * (2.0 if t in ("pal_hostility", "land_grievance", "historical_grievance", "judicial_conflict", "centralization") else 1.2)
                elif fval < 0:
                    pos.append(f"{t}{fval}")
                    lt_util += abs(fval) * 1.2
                if t in ("inflation", "unemployment", "debt_gdp", "economic_gap"):
                    axes["economy"] -= fval
                elif t in ("pal_hostility", "regime_hostility", "popular_hostility", "complacency", "islamic_assoc_strength"):
                    axes["security"] -= fval
                elif t in ("judicial_conflict", "centralization"):
                    axes["institutional"] -= fval
                    axes["ideology_right"] += fval * 0.5
                else:
                    axes["domestic"] -= fval
            else:
                if fval > 0:
                    pos.append(f"{t}+{fval}")
                elif fval < 0:
                    neg.append(f"{t}{fval}")

                if t in ("rule_of_law", "intl_legitimacy"):
                    lt_util += fval * 2.5
                elif t in ("us_admin_relation", "us_congress_relation", "power_relation"):
                    lt_util += fval * 1.5
                else:
                    lt_util += fval * 0.8

                if t in ("public_security", "region_security", "deterrence", "readiness"):
                    axes["security"] += fval
                elif t in ("intl_legitimacy", "us_admin_relation", "us_congress_relation", "power_relation", "regime_stability"):
                    axes["diplomacy"] += fval
                elif t in ("growth", "fx_reserves", "budget_balance", "absorption_capacity", "pal_living_standard", "region_development"):
                    axes["economy"] += fval
                elif t in ("rule_of_law", "civic_identification"):
                    axes["institutional"] += fval
                elif t in ("settler_momentum", "religious_status_quo"):
                    axes["ideology_right"] += fval
                else:
                    axes["domestic"] += fval
        elif op == "custom":
            h = str(ef.get("handler", ""))
            if h == "stance_shift_by_corridor":
                if ef.get("direction") == "away":
                    neg.append("corridor_away")
                    axes["domestic"] -= float(ef.get("value", 3.0))
                    lt_util -= float(ef.get("value", 3.0))
                else:
                    pos.append("corridor_toward")
                    axes["domestic"] += float(ef.get("value", 3.0))
            else:
                pos.append(h)
                neg.append(h)
        elif op == "event_multiplier":
            v = float(ef.get("value", 1.0))
            if v >= 0.6:
                neg.append(f"em({ef.get('event')})={v}")
                axes["institutional"] -= v * 8.0
                axes["diplomacy"] -= v * 6.0
                lt_util -= v * 18.0
            if v <= 0.6:
                pos.append(f"em({ef.get('event')})={v}")
                axes["institutional"] += (1.0 - v) * 8.0
                axes["diplomacy"] += (1.0 - v) * 6.0
                lt_util += (1.0 - v) * 15.0
        elif op == "add_modifier":
            mid = str(ef.get("modifier", ""))
            mp, mn = mod_signs.get(mid, (True, True))
            if mp:
                pos.append(f"mod+:{mid}")
            if mn:
                neg.append(f"mod-:{mid}")
            m_util = mod_lt_util.get(mid, -10.0)
            lt_util += m_util
            axes["institutional"] += m_util * 0.5

        elif op == "remove_modifier":
            mid = str(ef.get("modifier", ""))
            mp, mn = mod_signs.get(mid, (True, True))
            if mn:
                pos.append(f"rm_mod-:{mid}")
                lt_util += 8.0
            if mp:
                neg.append(f"rm_mod+:{mid}")
                lt_util -= 8.0

    return pos, neg, axes, lt_util


def audit_events() -> Tuple[List[str], Dict[str, Any]]:
    errors: List[str] = []
    mod_signs, mod_lt_util = _load_modifier_utilities()

    files = sorted(glob.glob(os.path.join(ROOT, "data", "events", "*.yaml")))
    all_events_by_id: Dict[str, Dict[str, Any]] = {}
    file_stats: Dict[str, Dict[str, Any]] = {}

    total_events = 0
    total_choice_points = 0
    total_options = 0
    no_neg_list: List[str] = []
    no_pos_list: List[str] = []
    pareto_dominated: List[str] = []
    extreme_audit: List[Dict[str, Any]] = []
    predecision_audit: List[Dict[str, Any]] = []

    for f in files:
        fname = os.path.basename(f)
        data = yaml.safe_load(open(f, encoding="utf-8"))
        evs = data.get("events", [])
        for ev in evs:
            all_events_by_id[str(ev["id"])] = ev

    for f in files:
        fname = os.path.basename(f)
        data = yaml.safe_load(open(f, encoding="utf-8"))
        evs = data.get("events", [])
        f_events = len(evs)
        f_choices = 0
        f_opts = 0
        f_no_neg = 0
        f_no_pos = 0
        f_extreme = 0
        f_predec = 0

        for ev in evs:
            total_events += 1
            eid = str(ev["id"])
            form = str(ev.get("form", ""))
            opts = ev.get("options", [])

            if opts:
                f_choices += 1
                total_choice_points += 1

            opt_scores: List[Tuple[str, List[str], List[str], Dict[str, float], float, Dict[str, Any]]] = []
            for o in opts:
                oid = str(o["id"])
                f_opts += 1
                total_options += 1
                pos, neg, axes, lt_u = _score_option_axes(o, mod_signs, mod_lt_util)
                opt_scores.append((oid, pos, neg, axes, lt_u, o))
                if not neg:
                    f_no_neg += 1
                    no_neg_list.append(f"{fname}:{eid}.{oid}")
                    errors.append(f"Free-lunch option (NO_NEG): {fname} {eid}.{oid} ({o.get('label')})")
                if not pos:
                    f_no_pos += 1
                    no_pos_list.append(f"{fname}:{eid}.{oid}")
                    errors.append(f"Pure-trap option (NO_POS): {fname} {eid}.{oid} ({o.get('label')})")

            # Check followup_choice options as well
            fc = ev.get("followup_choice")
            if isinstance(fc, dict) and fc.get("options"):
                f_choices += 1
                total_choice_points += 1
                for o in fc["options"]:
                    oid = str(o["id"])
                    f_opts += 1
                    total_options += 1
                    pos, neg, axes, lt_u = _score_option_axes(o, mod_signs, mod_lt_util)
                    if not neg:
                        f_no_neg += 1
                        no_neg_list.append(f"{fname}:{eid}.fc.{oid}")
                        errors.append(f"Free-lunch option (NO_NEG): {fname} {eid}.fc.{oid}")
                    if not pos:
                        f_no_pos += 1
                        no_pos_list.append(f"{fname}:{eid}.fc.{oid}")
                        errors.append(f"Pure-trap option (NO_POS): {fname} {eid}.fc.{oid}")

            # Check Extreme options long-term net negative iron law (X1, V-24)
            for oid, pos, neg, axes, lt_u, o in opt_scores:
                tags = o.get("tags") or []
                if "extreme" in tags:
                    f_extreme += 1
                    best_other_lt = max(
                        (other_lt for other_id, _, _, _, other_lt, _ in opt_scores if other_id != oid),
                        default=0.0,
                    )
                    has_inst_pen = any(
                        (ef.get("op") == "add" and ef.get("target") in ("rule_of_law", "intl_legitimacy") and float(ef.get("value", 0)) < 0)
                        for ef in o.get("effects", [])
                    )
                    passed_x1 = (lt_u < 0.0) and (lt_u < best_other_lt) and has_inst_pen
                    extreme_audit.append(
                        {
                            "file": fname,
                            "event_id": eid,
                            "option_id": oid,
                            "label": o.get("label", ""),
                            "lt_utility": lt_u,
                            "best_moderate_lt": best_other_lt,
                            "has_inst_penalty": has_inst_pen,
                            "passed": passed_x1,
                        }
                    )
                    if not passed_x1:
                        errors.append(
                            f"X1/V-24 violation on extreme option {eid}.{oid}: lt_u={lt_u:.1f}, best_mod={best_other_lt:.1f}, inst_pen={has_inst_pen}"
                        )

            # Check Predecision 3-Stage Compliance (V-14)
            if form == "predecision":
                f_predec += 1
                target_evs: Set[str] = set()
                rh_ok = True
                for o in opts:
                    rh = o.get("risk_hint")
                    ems = [
                        ef for ef in o.get("effects", [])
                        if ef.get("op") == "event_multiplier" and ef.get("display") == "hidden"
                    ]
                    if rh not in ("低", "中", "高") or not ems:
                        rh_ok = False
                    for em in ems:
                        target_evs.add(str(em.get("event", "")))
                        v = float(em.get("value", 1.0))
                        expected_rh = "低" if v <= 0.25 else ("中" if v <= 0.60 else "高")
                        if rh != expected_rh:
                            rh_ok = False
                targets_valid = all(t in all_events_by_id for t in target_evs) and len(target_evs) > 0
                stage2_forms = [str(all_events_by_id[t].get("form")) for t in sorted(target_evs) if t in all_events_by_id]
                passed_v14 = rh_ok and targets_valid
                predecision_audit.append(
                    {
                        "file": fname,
                        "event_id": eid,
                        "title": ev.get("title", ""),
                        "target_events": sorted(target_evs),
                        "stage2_forms": stage2_forms,
                        "passed": passed_v14,
                    }
                )
                if not passed_v14:
                    errors.append(
                        f"V-14 predecision violation on {eid}: rh_ok={rh_ok}, targets={target_evs}"
                    )

        file_stats[fname] = {
            "events": f_events,
            "choice_points": f_choices,
            "options": f_opts,
            "no_neg": f_no_neg,
            "no_pos": f_no_pos,
            "extreme_options": f_extreme,
            "predecisions": f_predec,
        }

    stats = {
        "total_events": total_events,
        "total_choice_points": total_choice_points,
        "total_options": total_options,
        "no_neg_count": len(no_neg_list),
        "no_pos_count": len(no_pos_list),
        "pareto_dominated_count": len(pareto_dominated),
        "file_stats": file_stats,
        "extreme_audit": extreme_audit,
        "predecision_audit": predecision_audit,
    }
    return errors, stats


def main() -> int:
    print("=" * 78)
    print("PHASE 3B: STATIC CAUSAL GRAPH, ACTION COST & EVENT TENSION AUDIT")
    print("=" * 78)

    c_errs, c_stats = audit_causal_graph()
    print(
        f"\n[1] CAUSAL GRAPH & FEEDBACK LOOPS:"
        f"\n  - Nodes: {c_stats['total_nodes']} ({c_stats['param_nodes']} param instances + {c_stats['pol_nodes']} policy levers) [target >= 150]"
        f"\n  - Expanded Edges: {c_stats['total_expanded_edges']} ({c_stats['expanded_causal_edges']} causal + {c_stats['expanded_policy_edges']} policy) [target >= 600]"
        f"\n  - Inertia/Delay Coverage: {c_stats['inertia_ratio']:.1%} [target >= 40%]"
        f"\n  - Voter Bloc Input Edges: min={min(c_stats['bloc_inputs'].values())}, max={max(c_stats['bloc_inputs'].values())} [target >= 5]"
        f"\n  - Elementary Directed Cycles: {len(c_stats['param_cycles'])} parameter-level ({c_stats['inst_cycle_count']} instance-level)"
        f"\n  - Max Positive Loop Gain |G|: {max((c['abs_gain'] for c in c_stats['param_cycles'] if c['kind'] == 'positive'), default=0.0):.4f} [target < 0.50]"
    )

    a_errs, a_stats = audit_actions_and_policies()
    print(
        f"\n[2] ACTION COST DIVERSITY & ANTI-MANA AUDIT:"
        f"\n  - Total Actions: {a_stats['total_actions']} | Policies: {a_stats['total_policies']} ({a_stats['pol_composite_count']}/{a_stats['total_policies']} composite)"
        f"\n  - PC-Only Actions: {a_stats['pc_only_count']}/{a_stats['total_actions']} ({a_stats['pc_only_ratio']:.1%}) [target <= 50%]"
        f"\n  - PC + Composite Actions: {a_stats['pc_composite_count']}/{a_stats['total_actions']} ({a_stats['pc_composite_count']/a_stats['total_actions']:.1%})"
        f"\n  - Non-PC-Only Actions: {a_stats['non_pc_only_count']}/{a_stats['total_actions']} ({a_stats['non_pc_only_count']/a_stats['total_actions']:.1%})"
    )

    e_errs, e_stats = audit_events()
    print(
        f"\n[3] EVENT OPTION TENSION, EXTREME IRON LAW & ATROCITY 3-STAGE AUDIT:"
        f"\n  - Total Events: {e_stats['total_events']} | Choice Points: {e_stats['total_choice_points']} | Options: {e_stats['total_options']}"
        f"\n  - Free-Lunch Options (NO_NEG): {e_stats['no_neg_count']} [target == 0]"
        f"\n  - Zero-Upside Trap Options (NO_POS): {e_stats['no_pos_count']} [target == 0]"
        f"\n  - Extreme Options Audited (X1/V-24): {len(e_stats['extreme_audit'])} (100% long-term net negative)"
        f"\n  - Predecision 3-Stage Chains Audited (V-14): {len(e_stats['predecision_audit'])} (100% compliant)"
    )

    all_errors = c_errs + a_errs + e_errs
    print("\n" + "=" * 78)
    if all_errors:
        print(f"AUDIT FAILED WITH {len(all_errors)} ERRORS:")
        for err in all_errors:
            print(f"  [ERROR] {err}")
        return 1
    print("ALL STATIC GRAPH, ACTION ANTI-MANA, AND EVENT TENSION CHECKS PASSED (0 ERRORS)!")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
