from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional, Tuple

from sim.expr import EffectExecutor, eval_bool
from sim.state import clamp, quantize


def eval_shape(
    shape: str,
    x: float,
    pivot: float = 0.0,
    w: float = 20.0,
    lo: float = 0.0,
    hi: float = 100.0,
) -> float:
    """Evaluate causal edge shape f(x; pivot, w, lo, hi) per M02 & data/causal_edges.yaml."""
    if shape == "linear":
        return x - pivot
    elif shape in ("above", "pos_excess"):
        return max(0.0, x - pivot)
    elif shape in ("below", "neg_excess"):
        return max(0.0, pivot - x)
    elif shape in ("sat", "sigmoid"):
        ww = w if w and abs(w) > 1e-9 else 20.0
        return ww * math.tanh((x - pivot) / ww)
    elif shape in ("quad", "quadratic"):
        ww = w if w and abs(w) > 1e-9 else 20.0
        d = max(0.0, x - pivot)
        return (d * d) / ww
    elif shape == "step":
        return 1.0 if x >= pivot else 0.0
    elif shape == "band":
        if lo <= x <= hi:
            return 0.0
        return (lo - x) if x < lo else (x - hi)
    elif shape == "habit":
        return 0.0
    elif shape == "flag":
        return 1.0 if x >= 0.5 else 0.0
    return 0.0


def soft_clamp(t_raw: float, lo_s: float, hi_s: float, w: float) -> float:
    """Apply soft-wall tanh compression per M02 & audit_implementability.py."""
    ww = w if w and w > 1e-9 else 13.0
    if t_raw < lo_s:
        return lo_s - ww * math.tanh((lo_s - t_raw) / ww)
    elif t_raw > hi_s:
        return hi_s + ww * math.tanh((t_raw - hi_s) / ww)
    return t_raw


class CausalNet:
    """M02 Continuous Parameter Dynamics, Threshold Hysteresis & Causal Explanation Engine."""

    def __init__(self, registry: Any) -> None:
        self.registry = registry
        self.ce_raw: Dict[str, Any] = registry.causal_edges_raw
        self.defaults: Dict[str, Any] = self.ce_raw.get("defaults", {})
        self.nodes: List[Dict[str, Any]] = self.ce_raw.get("nodes", [])
        self.nodes_by_param: Dict[str, Dict[str, Any]] = {n["param"]: n for n in self.nodes if "param" in n}
        self.edges: List[Dict[str, Any]] = [
            e for e in self.ce_raw.get("edges", []) if e.get("status", "active") == "active"
        ]

        # Group causal edges by target param
        self.edges_by_target: Dict[str, List[Dict[str, Any]]] = {}
        for e in self.edges:
            tgt = e.get("target") or e.get("to")
            if tgt:
                self.edges_by_target.setdefault(tgt, []).append(e)

        # Index policy lever edges by target param
        self.policy_edges_by_target: Dict[str, List[Tuple[str, Dict[str, Any], float]]] = {}
        for pol_id, pol_def in registry.policies.items():
            default_pv = self._get_pol_init_val(pol_def)
            for pe in pol_def.get("e", []) or []:
                t_param = pe.get("t") or pe.get("p") or pe.get("to")
                if t_param:
                    pv = float(pe.get("p") if ("t" in pe and "p" in pe) else pe.get("pv", default_pv))
                    self.policy_edges_by_target.setdefault(t_param, []).append((pol_id, pe, pv))

        # Registered term_provider callbacks: provider_name -> callable(state, param, key) -> float
        self.term_providers: Dict[str, Callable[[Any, str, Optional[str]], float]] = {}

    @staticmethod
    def _get_pol_init_val(pol: Dict[str, Any]) -> float:
        st = pol.get("start", {}).get("begin_1977")
        if isinstance(st, int) and "tiers" in pol and 0 <= st < len(pol["tiers"]):
            t_item = pol["tiers"][st]
            return float(t_item["v"] if isinstance(t_item, dict) else t_item)
        elif isinstance(st, (int, float)):
            return float(st)
        return 50.0

    def register_term_provider(
        self,
        provider_name: str,
        fn: Callable[[Any, str, Optional[str]], float],
    ) -> None:
        self.term_providers[provider_name] = fn

    def _get_source_val(self, state: Any, src_str: str, src_key: Optional[str], lag_months: int = 0) -> float:
        if src_str.startswith("flag:"):
            return 1.0 if state.has_flag(src_str.split(":", 1)[1]) else 0.0
        if src_str.startswith("modifier:"):
            return 1.0 if state.has_modifier(src_str.split(":", 1)[1]) else 0.0
        if src_str.startswith("param:"):
            pname = src_str.split(":", 1)[1]
        elif src_str.startswith("lever:"):
            lname = src_str.split(":", 1)[1]
            if lname in state.params and src_key is not None and isinstance(state.params[lname], dict):
                return float(state.params[lname].get(src_key, 0.0))
            if lname in state.params.get("policy_level", {}):
                return float(state.params["policy_level"][lname])
            if lname in state.params.get("budget_slider", {}):
                return float(state.params["budget_slider"][lname])
            pname = lname
        else:
            pname = src_str

        if lag_months > 0:
            node_k = f"{pname}[{src_key}]" if src_key is not None else pname
            hist = state.m02.get("history_24m", {}).get(node_k)
            if hist and len(hist) >= lag_months:
                return float(hist[-lag_months])

        return state.get_param(pname, src_key)

    def _is_node_key_active(self, state: Any, node: Dict[str, Any], key: Optional[str]) -> bool:
        p = node["param"]
        pdef = self.registry.param_defs.get(p, {})
        p_era = pdef.get("era")
        if p_era and p_era[0] is not None and state.year < int(p_era[0]):
            return False
        active_map = node.get("active", {})
        if key in active_map and not eval_bool(active_map[key], state):
            return False
        if key == "south_lebanon" and not state.region_exists("south_lebanon"):
            return False
        if key is not None:
            p_store = state.params.get(p)
            if not isinstance(p_store, dict) or key not in p_store:
                return False
        return True

    def _iter_node_keys(self, state: Any, node: Dict[str, Any]) -> List[Optional[str]]:
        p = node["param"]
        keys = node.get("keys")
        if keys is None:
            return [None]
        elif keys == "*":
            store = state.params.get(p, {})
            return [str(k) for k in store.keys()] if isinstance(store, dict) else [None]
        elif isinstance(keys, list):
            return [str(k) for k in keys]
        return [None]

    def on_effect_applied(
        self,
        state: Any,
        param: str,
        key: Optional[str],
        delta_actual: float,
        source_id: str = "effect",
    ) -> None:
        """Record discrete effect shock into shock_mem for level nodes (contracts.md §4.1 D-003: rho = 0.30)."""
        node = self.nodes_by_param.get(param)
        if not node or node.get("mode") != "level":
            return
        rho = float(node.get("memory_rho", self.defaults.get("memory_rho_level", 0.30)))
        cap = float(self.defaults.get("memory_cap", 30.0))
        node_key = f"{param}[{key}]" if key is not None else param
        cur_mem = float(state.m02["shock_mem"].get(node_key, 0.0))
        state.m02["shock_mem"][node_key] = clamp(cur_mem + rho * delta_actual, -cap, cap)

    def compute_target_value(
        self,
        state: Any,
        param: str,
        key: Optional[str] = None,
    ) -> Tuple[float, float, List[Dict[str, Any]]]:
        """Compute (T_raw, T_clamped, contribs) for a level node `(param, key)`."""
        node = self.nodes_by_param.get(param)
        if not node:
            cur = state.get_param(param, key)
            return cur, cur, []

        b_raw = node.get("baseline", 0.0)
        if isinstance(b_raw, dict):
            b_val = float(b_raw.get(key, 0.0))
        else:
            b_val = float(b_raw or 0.0)

        node_key = f"{param}[{key}]" if key is not None else param
        b_shift = float(state.m02.get("baseline_shifts", {}).get(node_key, 0.0))
        b_val += b_shift

        contribs: List[Dict[str, Any]] = []
        ce_sum = 0.0

        # 1. Causal edges from data/causal_edges.yaml
        for e in self.edges_by_target.get(param, []):
            tk = e.get("target_key")
            if not (tk == key or (tk == "*" and key is not None)):
                continue
            gate = e.get("gate")
            if gate and not eval_bool(gate, state):
                continue
            src_k = key if e.get("source_key") == "*" else e.get("source_key")
            lag_m = int(e.get("lag_months", 0) or 0)
            sx = self._get_source_val(state, e["source"], src_k, lag_months=lag_m)
            pv = e.get("pivot", 0.0)
            if isinstance(pv, dict):
                pv = pv.get(key, 0.0)
            sh_val = eval_shape(
                e.get("shape", "linear"),
                sx,
                pivot=float(pv or 0.0),
                w=float(e.get("w") or 20.0),
                lo=float(e.get("lo") or 0.0),
                hi=float(e.get("hi") or 100.0),
            )
            coef = float(e["coef"]) if "coef" in e else float(e.get("coef_map", {}).get(key, 0.0))
            val = coef * sh_val
            if abs(val) > 1e-9:
                ce_sum += val
                contribs.append({
                    "edge_id": e.get("id", f"{e['source']}->{node_key}"),
                    "source": e["source"],
                    "source_key": src_k,
                    "value": quantize(val),
                })

        # 2. Policy lever edges from data/policies.yaml
        pe_sum = 0.0
        for pol_id, pe, default_pv in self.policy_edges_by_target.get(param, []):
            if pe.get("k") != key:
                continue
            plev = state.get_param("policy_level", pol_id)
            sh_val = eval_shape(
                pe.get("s") or pe.get("sh") or "linear",
                plev,
                pivot=default_pv,
                w=float(pe.get("w") or 20.0),
            )
            val = float(pe.get("c", 0.0)) * sh_val
            if abs(val) > 1e-9:
                pe_sum += val
                contribs.append({
                    "edge_id": f"policy:{pol_id}",
                    "source": f"policy:{pol_id}",
                    "source_key": pol_id,
                    "value": quantize(val),
                })

        # 3. Term provider dynamic contribution if registered
        tp_sum = 0.0
        tp_name = node.get("term_provider")
        if tp_name and tp_name in self.term_providers:
            try:
                tp_val = float(self.term_providers[tp_name](state, param, key))
                if abs(tp_val) > 1e-9:
                    tp_sum += tp_val
                    contribs.append({
                        "edge_id": f"term:{tp_name}",
                        "source": tp_name,
                        "source_key": key,
                        "value": quantize(tp_val),
                    })
            except Exception:
                pass

        # 4. Shock memory M_i(t)
        mem_val = float(state.m02["shock_mem"].get(node_key, 0.0))
        if abs(mem_val) > 1e-9:
            contribs.append({
                "edge_id": "shock_memory",
                "source": "shock_memory",
                "source_key": key,
                "value": quantize(mem_val),
            })

        t_raw = b_val + ce_sum + pe_sum + tp_sum + mem_val
        soft_cfg = node.get("soft", self.defaults.get("soft_stock", {"lo_s": 15.0, "hi_s": 85.0, "w": 13.0}))
        lo_s = float(soft_cfg.get("lo_s", 15.0))
        hi_s = float(soft_cfg.get("hi_s", 85.0))
        w = float(soft_cfg.get("w", 13.0))
        t_val = soft_clamp(t_raw, lo_s, hi_s, w)
        return t_raw, t_val, contribs

    def compute_rate_flow(
        self,
        state: Any,
        param: str,
        key: Optional[str] = None,
    ) -> Tuple[float, List[Dict[str, Any]]]:
        """Compute net flow rate R for a rate node `(param, key)`."""
        node = self.nodes_by_param.get(param)
        if not node:
            return 0.0, []

        b_raw = node.get("baseline", 0.0)
        b_val = float(b_raw.get(key, 0.0)) if isinstance(b_raw, dict) else float(b_raw or 0.0)
        contribs: List[Dict[str, Any]] = []
        flow = b_val

        for e in self.edges_by_target.get(param, []):
            tk = e.get("target_key")
            if not (tk == key or (tk == "*" and key is not None)):
                continue
            gate = e.get("gate")
            if gate and not eval_bool(gate, state):
                continue
            src_k = key if e.get("source_key") == "*" else e.get("source_key")
            sx = self._get_source_val(state, e["source"], src_k, lag_months=int(e.get("lag_months", 0) or 0))
            pv = e.get("pivot", 0.0)
            if isinstance(pv, dict):
                pv = pv.get(key, 0.0)
            sh_val = eval_shape(
                e.get("shape", "linear"),
                sx,
                pivot=float(pv or 0.0),
                w=float(e.get("w") or 20.0),
                lo=float(e.get("lo") or 0.0),
                hi=float(e.get("hi") or 100.0),
            )
            coef = float(e["coef"]) if "coef" in e else float(e.get("coef_map", {}).get(key, 0.0))
            val = coef * sh_val
            if abs(val) > 1e-9:
                flow += val
                contribs.append({"edge_id": e.get("id", e["source"]), "source": e["source"], "value": quantize(val)})

        for pol_id, pe, default_pv in self.policy_edges_by_target.get(param, []):
            if pe.get("k") != key:
                continue
            plev = state.get_param("policy_level", pol_id)
            sh_val = eval_shape(
                pe.get("s") or pe.get("sh") or "linear",
                plev,
                pivot=default_pv,
                w=float(pe.get("w") or 20.0),
            )
            val = float(pe.get("c", 0.0)) * sh_val
            if abs(val) > 1e-9:
                flow += val
                contribs.append({"edge_id": f"policy:{pol_id}", "source": f"policy:{pol_id}", "value": quantize(val)})

        tp_name = node.get("term_provider")
        if tp_name and tp_name in self.term_providers:
            try:
                tp_val = float(self.term_providers[tp_name](state, param, key))
                if abs(tp_val) > 1e-9:
                    flow += tp_val
                    contribs.append({"edge_id": f"term:{tp_name}", "source": tp_name, "value": quantize(tp_val)})
            except Exception:
                pass

        return flow, contribs

    def record_monthly_history(self, state: Any) -> None:
        """Step 10a: Record 24-month rolling history for all parameters and policy levers."""
        hist_map = state.m02.setdefault("history_24m", {})
        max_len = int(self.defaults.get("hist_length", 24))
        for pid, pval in state.params.items():
            if isinstance(pval, (int, float)):
                arr = hist_map.setdefault(pid, [float(pval)] * max_len)
                arr.append(float(pval))
                if len(arr) > max_len:
                    del arr[:-max_len]
            elif isinstance(pval, dict):
                for k, v in pval.items():
                    nk = f"{pid}[{k}]"
                    arr = hist_map.setdefault(nk, [float(v)] * max_len)
                    arr.append(float(v))
                    if len(arr) > max_len:
                        del arr[:-max_len]

    def evaluate_thresholds(self, state: Any, executor: Optional[EffectExecutor] = None) -> List[str]:
        """Step 10b: Evaluate threshold hysteresis state machine from data/thresholds.yaml."""
        t_defaults = self.registry.thresholds_raw.get("defaults", {})
        thr_states = state.m02.setdefault("thresholds", {})
        newly_activated: List[str] = []

        for tdef in self.registry.thresholds:
            tid = tdef["id"]
            ttype = tdef.get("type", t_defaults.get("type", "level"))
            k_spec = tdef.get("key")
            param = tdef.get("param") or tdef.get("parameter")

            # Expand wildcard keys if key == "*"
            if k_spec == "*" and param and isinstance(state.params.get(param), dict):
                keys_to_check: List[Optional[str]] = [str(k) for k in state.params[param].keys()]
            elif k_spec == "*":
                keys_to_check = ["arab", "druze", "bedouin"]
            else:
                keys_to_check = [str(k_spec) if k_spec is not None else None]

            for k in keys_to_check:
                full_id = f"{tid}[{k}]" if (k_spec == "*" and k is not None) else tid
                t_st = thr_states.setdefault(full_id, {
                    "id": full_id,
                    "state": "off",
                    "hold_counter": 0,
                    "on_months": 0,
                    "cooldown_months": 0,
                    "times_activated": 0,
                })

                gate = tdef.get("gate", t_defaults.get("gate"))
                gate_ok = eval_bool(gate, state) if gate else True

                direction = tdef.get("direction", t_defaults.get("direction", "up"))
                confirm_req = int(tdef.get("confirm", t_defaults.get("confirm", 2)))
                min_on_req = int(tdef.get("min_on", t_defaults.get("min_on", 3)))
                cd_req = int(tdef.get("cooldown", t_defaults.get("cooldown", 6)))
                latch = bool(tdef.get("latch", t_defaults.get("latch", False)))

                cur_state = t_st.get("state", "off")
                if cur_state == "on" and latch:
                    continue

                # Determine if enter/exit condition met
                enter_cond = False
                exit_cond = False
                if ttype == "compound":
                    sub_ids = tdef.get("all_of", [])
                    enter_cond = all(
                        thr_states.get(f"{sid}[{k}]" if k else sid, thr_states.get(sid, {})).get("state") == "on"
                        for sid in sub_ids
                    )
                    exit_cond = not enter_cond
                elif ttype == "drop" and param:
                    cur_v = state.get_param(param, k)
                    nk = f"{param}[{k}]" if k else param
                    hist = state.m02.get("history_24m", {}).get(nk, [cur_v])
                    win = min(len(hist), int(tdef.get("drop_window", 6)))
                    peak = max(hist[-win:]) if hist else cur_v
                    drop_sz = float(tdef.get("drop_size", 10.0))
                    enter_cond = (peak - cur_v) >= drop_sz
                    exit_cond = (peak - cur_v) < (drop_sz * 0.6)
                elif param:
                    cur_v = state.get_param(param, k)
                    on_at = float(tdef.get("on_at", 70.0))
                    off_at = float(tdef.get("off_at", 60.0))
                    if direction == "up":
                        enter_cond = cur_v >= on_at
                        exit_cond = cur_v <= off_at
                    else:
                        enter_cond = cur_v <= on_at
                        exit_cond = cur_v >= off_at

                if cur_state == "cooldown":
                    t_st["cooldown_months"] = max(0, int(t_st.get("cooldown_months", 0)) - 1)
                    if t_st["cooldown_months"] == 0:
                        t_st["state"] = "off"
                        cur_state = "off"

                if cur_state == "off":
                    if gate_ok and enter_cond:
                        t_st["hold_counter"] = int(t_st.get("hold_counter", 0)) + 1
                        if t_st["hold_counter"] >= confirm_req:
                            t_st["state"] = "on"
                            t_st["on_months"] = 0
                            t_st["hold_counter"] = 0
                            t_st["times_activated"] = int(t_st.get("times_activated", 0)) + 1
                            state.set_flag(f"thr.{tid}", source="M02_threshold")
                            newly_activated.append(full_id)
                    else:
                        t_st["hold_counter"] = 0

                elif cur_state == "on":
                    t_st["on_months"] = int(t_st.get("on_months", 0)) + 1
                    if t_st["on_months"] >= min_on_req and exit_cond:
                        t_st["state"] = "cooldown" if cd_req > 0 else "off"
                        t_st["cooldown_months"] = cd_req
                        state.clear_flag(f"thr.{tid}")

        return newly_activated

    def step_nodes(self, state: Any, tick_filter: str = "monthly") -> Dict[str, float]:
        """Step 10c: Advance CausalNet level and rate nodes matching tick_filter."""
        deltas: Dict[str, float] = {}
        new_values: List[Tuple[str, Optional[str], float]] = []

        for node in self.nodes:
            mode = node.get("mode", "none")
            if mode not in ("level", "rate"):
                continue
            node_tick = node.get("tick", "monthly")
            if tick_filter != "all" and node_tick != tick_filter:
                continue

            param = node["param"]
            for k in self._iter_node_keys(state, node):
                if not self._is_node_key_active(state, node, k):
                    continue
                node_key = f"{param}[{k}]" if k is not None else param
                x_cur = state.get_param(param, k)

                if mode == "level":
                    alpha = float(node.get("alpha", 0.1))
                    _, t_val, contribs = self.compute_target_value(state, param, k)
                    x_next = x_cur + alpha * (t_val - x_cur)
                    state.m02["last_contribs"][node_key] = contribs
                    # Decay shock memory
                    mu = float(node.get("memory_mu", self.defaults.get("memory_mu", 0.05)))
                    cur_mem = float(state.m02["shock_mem"].get(node_key, 0.0))
                    if abs(cur_mem) > 1e-6:
                        state.m02["shock_mem"][node_key] = quantize(cur_mem * (1.0 - mu))
                    else:
                        state.m02["shock_mem"].pop(node_key, None)

                else:  # mode == "rate"
                    flow, contribs = self.compute_rate_flow(state, param, k)
                    lo, hi = state.get_param_range(param)
                    if node.get("headroom", False) and flow > 0 and hi > lo:
                        flow = flow * max(0.0, (hi - x_cur) / (hi - lo))
                    x_next = x_cur + flow
                    state.m02["last_contribs"][node_key] = contribs

                new_values.append((param, k, x_next))
                deltas[node_key] = quantize(x_next - x_cur)

        # Commit all node updates synchronously
        for param, k, x_next in new_values:
            state.set_param(param, x_next, k)

        return deltas

    def explain(self, state: Any, param: str, key: Optional[str] = None) -> Dict[str, Any]:
        """Return causal explanation breakdown (Top-5 contributors + target) for UI tooltips (M02/M15)."""
        node = self.nodes_by_param.get(param)
        cur_val = state.get_param(param, key)
        if not node:
            return {"param": param, "key": key, "current": cur_val, "mode": "external", "top_contributors": []}

        mode = node.get("mode", "none")
        if mode == "level":
            t_raw, t_val, contribs = self.compute_target_value(state, param, key)
            alpha = float(node.get("alpha", 0.1))
            contribs_sorted = sorted(contribs, key=lambda c: abs(c["value"]), reverse=True)
            return {
                "param": param,
                "key": key,
                "mode": "level",
                "current": cur_val,
                "target_raw": quantize(t_raw),
                "target": quantize(t_val),
                "alpha": alpha,
                "expected_step_delta": quantize(alpha * (t_val - cur_val)),
                "top_contributors": contribs_sorted[:5],
                "all_contributors": contribs_sorted,
            }
        elif mode == "rate":
            flow, contribs = self.compute_rate_flow(state, param, key)
            contribs_sorted = sorted(contribs, key=lambda c: abs(c["value"]), reverse=True)
            return {
                "param": param,
                "key": key,
                "mode": "rate",
                "current": cur_val,
                "expected_step_delta": quantize(flow),
                "top_contributors": contribs_sorted[:5],
                "all_contributors": contribs_sorted,
            }
        return {"param": param, "key": key, "mode": mode, "current": cur_val, "top_contributors": []}

    def preview(
        self,
        state: Any,
        hypothetical_effects: List[Dict[str, Any]],
        horizon_months: int = 1,
    ) -> Dict[str, float]:
        """Simulate hypothetical_effects on a cloned state over horizon_months and return national param deltas."""
        sim_copy = state.clone()
        executor = EffectExecutor(self)
        executor.apply_effects(sim_copy, hypothetical_effects, source="preview")
        for _ in range(max(1, horizon_months)):
            self.step_nodes(sim_copy, tick_filter="monthly")
        out: Dict[str, float] = {}
        for pid, pval in sim_copy.params.items():
            if isinstance(pval, (int, float)):
                out[pid] = quantize(float(pval) - float(state.params.get(pid, 0.0)))
        return out
