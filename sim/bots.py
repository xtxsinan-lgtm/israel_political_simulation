#!/usr/bin/env python3
"""Strategy Bots for Israel Political Simulation (Phase 3B).

Implements a decoupled, duck-typed `StrategyBot` decision interface and 7 distinct
automated political personas for headless Monte Carlo balance testing (Phase 3C):
1. `HistoricalBot` ("历史还原"): Follows `historical: true` choices and historical policy corridors.
2. `RevisionistHawkBot` ("修正派铁壁"): Prioritizes deterrence, settlements, military readiness, and Greater Israel.
3. `PeaceDoveBot` ("和平鸽派"): Prioritizes diplomacy, peace treaties, rule of law, Arab civic equality, and restraint.
4. `PopulistWelfareBot` ("民粹福利派"): Prioritizes Mizrahi/Haredi/Labor welfare, subsidies, coalition patronage, and employment.
5. `NeoliberalTechnocratBot` ("新自由主义技术官僚"): Prioritizes inflation control, FX reserves, fiscal balance, privatization, and growth.
6. `AuthoritarianCaesarBot` ("强人集权派"): Prioritizes centralization, executive power, censorship, judicial curbing, and hardline control.
7. `RandomBot` ("均匀随机基线"): Deterministic seeded uniform random baseline across valid options and actions.

Compatible with Python 3.9+ and decoupled from `sim/state.py` / `sim/engine.py` via duck-typing
(supports both dataclass/object `GameState` and dictionary state representations).
"""
from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union


def _get_state_param(state: Any, name: str, key: Optional[str] = None, default: float = 50.0) -> float:
    """Safely extract a parameter value from either a GameState object or a dict."""
    if state is None:
        return default
    # Try helper method get_param(name, key) if present on GameState
    if hasattr(state, "get_param") and callable(getattr(state, "get_param")):
        try:
            val = state.get_param(name, key)
            if isinstance(val, (int, float)):
                return float(val)
        except Exception:
            pass

    container = None
    if isinstance(state, dict):
        container = state.get("params", state)
    elif hasattr(state, "params") and isinstance(getattr(state, "params"), dict):
        container = getattr(state, "params")

    if isinstance(container, dict):
        if key:
            dotted = f"{name}.{key}"
            if dotted in container and isinstance(container[dotted], (int, float)):
                return float(container[dotted])
            sub = container.get(name)
            if isinstance(sub, dict) and key in sub and isinstance(sub[key], (int, float)):
                return float(sub[key])
        val = container.get(name)
        if isinstance(val, (int, float)):
            return float(val)

    if hasattr(state, name):
        attr = getattr(state, name)
        if key and isinstance(attr, dict) and key in attr:
            return float(attr[key])
        if isinstance(attr, (int, float)):
            return float(attr)
    return default


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


class StrategyBot:
    """Base class for all automated political strategy bots."""

    bot_id: str = "base"
    name_zh: str = "基础策略Bot"
    description: str = "Base strategy bot"

    def __init__(
        self,
        seed: int = 1948,
        weights: Optional[Dict[str, float]] = None,
        tag_bonuses: Optional[Dict[str, float]] = None,
        cat_bonuses: Optional[Dict[str, float]] = None,
        modifier_weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self.seed = int(seed)
        self._rng = random.Random(self.seed)
        self.weights: Dict[str, float] = dict(weights or {})
        self.tag_bonuses: Dict[str, float] = dict(tag_bonuses or {})
        self.cat_bonuses: Dict[str, float] = dict(cat_bonuses or {})
        self.modifier_weights: Dict[str, float] = dict(modifier_weights or {})

    def reset(self, seed: Optional[int] = None) -> None:
        if seed is not None:
            self.seed = int(seed)
        self._rng = random.Random(self.seed)

    # ------------------------------------------------------------------
    # Event Option Selection
    # ------------------------------------------------------------------
    def choose_event_option(
        self,
        state: Any,
        event: Any,
        options: Optional[Sequence[Any]] = None,
    ) -> str:
        """Return the chosen option ID (e.g. 'A', 'B', 'C') for an event."""
        opts = list(options if options is not None else (_get_field(event, "options") or []))
        if not opts:
            return "A"
        best_id = str(_get_field(opts[0], "id", "A"))
        best_score = float("-inf")
        for idx, opt in enumerate(opts):
            oid = str(_get_field(opt, "id", chr(ord("A") + idx)))
            score = self.score_option(state, event, opt)
            # Deterministic tiny tie-breaker preferring earlier options unless outscored
            tie_break = -idx * 1e-6
            if score + tie_break > best_score:
                best_score = score + tie_break
                best_id = oid
        return best_id

    def choose_followup_option(
        self,
        state: Any,
        event: Any,
        options: Optional[Sequence[Any]] = None,
    ) -> str:
        """Return the chosen option ID for an event's `followup_choice`."""
        if options is None:
            fc = _get_field(event, "followup_choice")
            if isinstance(fc, dict):
                options = fc.get("options", [])
        return self.choose_event_option(state, event, options)

    def score_option(self, state: Any, event: Any, option: Any) -> float:
        """Compute scalar utility of an event option under this bot's persona."""
        score = 0.0
        tags = _get_field(option, "tags") or []
        for t in tags:
            score += self.tag_bonuses.get(str(t), 0.0)

        risk_hint = _get_field(option, "risk_hint")
        if risk_hint == "高":
            score += self.weights.get("_risk_high", 0.0)
        elif risk_hint == "中":
            score += self.weights.get("_risk_mid", 0.0)
        elif risk_hint == "低":
            score += self.weights.get("_risk_low", 0.0)

        effects = _get_field(option, "effects") or []
        score += self._score_effects_list(state, effects)
        return score

    def _score_effects_list(self, state: Any, effects: Iterable[Any]) -> float:
        total = 0.0
        for ef in effects:
            op = str(_get_field(ef, "op", "add"))
            target = str(_get_field(ef, "target", ""))
            key = str(_get_field(ef, "key") or "")
            val = _get_field(ef, "value", 0.0)

            if op == "add" and isinstance(val, (int, float)):
                fval = float(val)
                w = self._lookup_param_weight(state, target, key)
                total += fval * w
            elif op == "event_multiplier":
                mult = float(val) if isinstance(val, (int, float)) else 1.0
                # mult > 1 increases atrocity/incident probability; mult < 1 reduces it
                total += (1.0 - mult) * self.weights.get("_atrocity_avoidance", 0.0)
            elif op == "custom":
                handler = str(_get_field(ef, "handler") or key)
                if handler == "stance_shift_by_corridor":
                    direction = str(_get_field(ef, "direction", "away"))
                    mag = float(val) if isinstance(val, (int, float)) else 5.0
                    if direction == "away":
                        total += mag * self.weights.get("_corridor_away", -0.5)
                    else:
                        total += mag * self.weights.get("_corridor_toward", 0.5)
                elif handler == "apply_stabilization_plan":
                    total += self.weights.get("_stabilization_plan", 0.0)
            elif op == "add_modifier":
                mod_id = str(_get_field(ef, "modifier") or key)
                total += self._score_modifier(mod_id)
            elif op == "remove_modifier":
                mod_id = str(_get_field(ef, "modifier") or key)
                total -= 0.7 * self._score_modifier(mod_id)
        return total

    def _lookup_param_weight(self, state: Any, target: str, key: str) -> float:
        if key:
            dotted = f"{target}.{key}"
            if dotted in self.weights:
                return self.weights[dotted]
            if target in ("faction_strength", "faction_legitimacy"):
                if key == "phalange":
                    return self.weights.get("faction_strength.phalange", 0.2)
                return self.weights.get("hostile_faction", -1.0)
        return self.weights.get(target, 0.0)

    def _score_modifier(self, mod_id: str) -> float:
        if mod_id in self.modifier_weights:
            return self.modifier_weights[mod_id]
        # Heuristic keyword matching on modifier IDs for general coverage
        score = 0.0
        if any(k in mod_id for k in ("unit_101", "nuclear", "iron_wall", "settlement", "outpost", "deterrence", "full_mobilization")):
            score += self.weights.get("_mod_military_hawk", 0.0)
        if any(k in mod_id for k in ("peace", "status_quo", "armistice", "inquiry", "oversight", "protection")):
            score += self.weights.get("_mod_peace_inst", 0.0)
        if any(k in mod_id for k in ("oral_authorization", "censorship", "emergency", "sealed", "underground", "diarchy", "curb")):
            score += self.weights.get("_mod_authoritarian", 0.0)
        if any(k in mod_id for k in ("subsidy", "welfare", "haredi", "yeshiva", "histadrut", "housing")):
            score += self.weights.get("_mod_welfare", 0.0)
        if any(k in mod_id for k in ("trauma", "scandal", "crisis", "exhaustion", "depression", "friction", "risk", "leaky", "unfinished")):
            score += self.weights.get("_mod_crisis_penalty", -4.0)
        return score

    # ------------------------------------------------------------------
    # Action & Policy Selection
    # ------------------------------------------------------------------
    def choose_actions(
        self,
        state: Any,
        available_actions: Sequence[Any],
        policies: Optional[Sequence[Any]] = None,
        max_actions: int = 2,
    ) -> List[Dict[str, Any]]:
        """Rank and select up to `max_actions` affordable actions for the current turn."""
        pc_avail = _get_state_param(state, "political_capital", default=60.0)
        scored: List[Tuple[float, Dict[str, Any]]] = []

        for idx, act in enumerate(available_actions or []):
            aid = str(_get_field(act, "id", f"act_{idx}"))
            if aid == "adjust_policy":
                continue
            cost = _get_field(act, "cost") or {}
            pc_cost = float(cost.get("pc", 0.0)) if isinstance(cost, dict) else 0.0
            if pc_cost > pc_avail:
                continue
            s = self.score_action(state, act)
            if s > 0.0:
                scored.append((s - idx * 1e-6, {"id": aid, "score": s, "pc_cost": pc_cost, "action": act}))

        scored.sort(key=lambda x: -x[0])
        chosen: List[Dict[str, Any]] = []
        rem_pc = pc_avail
        for _, item in scored:
            if len(chosen) >= max_actions:
                break
            if item["pc_cost"] <= rem_pc:
                chosen.append(item)
                rem_pc -= item["pc_cost"]
        return chosen

    def score_action(self, state: Any, action: Any) -> float:
        cat = str(_get_field(action, "cat", ""))
        score = self.cat_bonuses.get(cat, 0.0)
        tags = _get_field(action, "tags") or []
        for t in tags:
            score += self.tag_bonuses.get(str(t), 0.0)

        fx = _get_field(action, "fx") or []
        score += self._score_effects_list(state, fx)

        # Evaluate explicit action costs
        cost = _get_field(action, "cost") or {}
        if isinstance(cost, dict):
            pc = float(cost.get("pc", 0.0))
            score += pc * self.weights.get("_cost_pc", -0.15)
            fiscal = float(cost.get("fiscal", 0.0)) + float(cost.get("fiscal_m", 0.0)) * 6.0
            score -= fiscal * self.weights.get("budget_balance", 1.0)
            rol = float(cost.get("rol", 0.0))
            score += rol * self.weights.get("rule_of_law", 0.5)
            standing = float(cost.get("standing", 0.0))
            score += standing * self.weights.get("party_standing", 0.5)
            par_cost = cost.get("par")
            if isinstance(par_cost, dict):
                for pk, pv in par_cost.items():
                    if isinstance(pv, (int, float)):
                        p_name, p_k = (pk.split(".", 1) if "." in pk else (pk, ""))
                        score += float(pv) * self._lookup_param_weight(state, p_name, p_k)
            bloc_cost = cost.get("bloc")
            if isinstance(bloc_cost, dict):
                for bk, bv in bloc_cost.items():
                    if isinstance(bv, (int, float)):
                        score += float(bv) * self._lookup_param_weight(state, "bloc_support", bk)
            ally_cost = cost.get("ally")
            if isinstance(ally_cost, dict):
                for ak, av in ally_cost.items():
                    if isinstance(av, (int, float)):
                        score += float(av) * self._lookup_param_weight(state, "ally_satisfaction", ak)

        # Axis preference alignment
        ax = _get_field(action, "ax") or {}
        if isinstance(ax, dict):
            for axis_name, axis_shift in ax.items():
                if isinstance(axis_shift, (int, float)):
                    score += float(axis_shift) * self.weights.get(f"_axis_{axis_name}", 0.0)

        return score

    def choose_policy_adjustments(
        self,
        state: Any,
        policies: Sequence[Any],
        max_adjustments: int = 1,
    ) -> List[Dict[str, Any]]:
        """Choose desired policy lever direction ('up' or 'down') based on policy effects."""
        recs: List[Tuple[float, Dict[str, Any]]] = []
        state_pols = getattr(state, "policies", None) if state is not None else None
        cur_day = int(getattr(state, "day_index", 0)) if state is not None else 0
        for idx, pol in enumerate(policies or []):
            pid = str(_get_field(pol, "id", f"pol_{idx}"))
            es = _get_field(pol, "e") or _get_field(pol, "fx") or []
            marginal_utility = 0.0
            for ef in es:
                t = str(_get_field(ef, "t") or _get_field(ef, "to") or _get_field(ef, "dst") or "")
                k = str(_get_field(ef, "k") or _get_field(ef, "key") or "")
                c = float(_get_field(ef, "c", 0.0) or 0.0)
                marginal_utility += 45.0 * c * self._lookup_param_weight(state, t, k)
            tiers = _get_field(pol, "tiers") or []
            if len(tiers) >= 2 and isinstance(tiers[0], dict) and isinstance(tiers[-1], dict):
                em_span = float(tiers[-1].get("em", 0.0)) - float(tiers[0].get("em", 0.0))
                f_span = float(tiers[-1].get("f", 0.0)) - float(tiers[0].get("f", 0.0))
                marginal_utility += 0.25 * em_span * self.weights.get("economic_model", self.weights.get("_axis_economy", 0.0))
                marginal_utility -= 0.40 * f_span * self.weights.get("budget_balance", 0.0)
            ax = _get_field(pol, "ax") or {}
            if isinstance(ax, dict):
                for axis_name, axis_val in ax.items():
                    if isinstance(axis_val, (int, float)):
                        marginal_utility += 0.15 * float(axis_val) * self.weights.get(f"_axis_{axis_name}", 0.0)

            if abs(marginal_utility) > 0.05:
                direction = "up" if marginal_utility > 0 else "down"
                if isinstance(state_pols, dict) and pid in state_pols:
                    p_st = state_pols[pid]
                    if int(p_st.get("cooldown_until_day", 0)) > cur_day:
                        continue
                    cur_idx = int(p_st.get("tier_idx", 0))
                    if direction == "up" and cur_idx >= len(tiers) - 1:
                        continue
                    if direction == "down" and cur_idx <= 0:
                        continue
                    cat = str(_get_field(pol, "cat", ""))
                    if direction == "down" and cur_idx <= 1 and cat in ("sec", "occ", "terr", "media") and self.bot_id not in ("peace_dove", "neoliberal_technocrat"):
                        continue
                    if direction == "up" and pid in ("emergency_regs_use", "press_ordinance", "military_government", "military_censorship") and self.bot_id != "authoritarian_caesar":
                        continue
                    if pid == "settlement_policy" and direction == "down" and cur_idx <= 1 and self.weights.get("_axis_territory", 0.0) > -0.5:
                        continue
                    if pid == "bank_regulation" and direction == "up" and self.bot_id == "historical" and getattr(state, "date_str", "1999") < "1983-11-01":
                        continue
                recs.append(
                    (
                        abs(marginal_utility) - idx * 1e-6,
                        {"policy_id": pid, "direction": direction, "utility": abs(marginal_utility)},
                    )
                )
        recs.sort(key=lambda x: -x[0])
        return [item for _, item in recs[:max_adjustments]]

    def choose_budget(self, state: Any) -> Dict[str, float]:
        """Return target budget allocation shares summing to 1.0 plus fiscal stance."""
        return {
            "defense": 0.30,
            "welfare": 0.28,
            "infrastructure": 0.20,
            "settlements": 0.07,
            "education_tech": 0.15,
            "target_surplus": 0.0,
        }

    def choose_coalition_offer(
        self,
        state: Any,
        candidate_parties: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        """Return preferred coalition partner ordering and concession willingness."""
        candidates = list(candidate_parties or ["nrp", "agudat", "shas", "liberal", "mapam", "meretz", "tehiya"])
        scored = sorted(
            candidates,
            key=lambda p: -self.weights.get(f"ally_satisfaction.{p}", self.weights.get("ally_satisfaction", 0.5)),
        )
        return {"preferred_partners": scored[:3], "max_portfolios_offered": 4}

    def choose_summit_stance(self, state: Any, summit_context: Optional[Dict[str, Any]] = None) -> str:
        """Return summit negotiation posture ('concede_land_for_peace', 'autonomy_only', 'hardline_reject')."""
        if self.weights.get("_axis_territory", 0.0) <= -0.5:
            return "concede_land_for_peace"
        if self.weights.get("_axis_territory", 0.0) >= 0.6:
            return "hardline_reject"
        return "autonomy_only"


# ======================================================================
# 1. HistoricalBot ("历史还原")
# ======================================================================
class HistoricalBot(StrategyBot):
    bot_id = "historical"
    name_zh = "历史还原派 (Historical)"
    description = "Strictly selects historical=True options; falls back to corridor-preserving institutional choices."

    def __init__(self, seed: int = 1948) -> None:
        super().__init__(
            seed=seed,
            weights={
                "party_standing": 1.2,
                "political_capital": 0.4,
                "public_security": 1.2,
                "deterrence": 1.4,
                "readiness": 1.1,
                "settler_momentum": 1.6,
                "us_admin_relation": 0.9,
                "intl_legitimacy": 0.6,
                "rule_of_law": 0.8,
                "centralization": -1.5,
                "growth": 1.0,
                "fx_reserves": 0.6,
                "budget_balance": 0.8,
                "inflation": -0.6,
                "unemployment": -0.8,
                "pal_hostility": -0.4,
                "promise_progress": 0.9,
                "vision_progress": 1.2,
                "ally_satisfaction": 0.8,
                "bloc_support": 0.5,
                "relation": 0.25,
                "hostile_faction": -0.8,
                "_axis_territory": 0.9,
                "_axis_security": 0.8,
                "_corridor_away": -4.0,
                "_corridor_toward": 3.0,
                "_atrocity_avoidance": 2.0,
                "_mod_crisis_penalty": -5.0,
            },
            tag_bonuses={"economic": 1.0, "restraint": 0.5, "authoritarian": -15.0, "extreme": -25.0},
            cat_bonuses={"econ": 2.0, "mil": 1.5, "dip": 1.5, "parl": 1.0, "soc": 1.0},
        )

    def score_option(self, state: Any, event: Any, option: Any) -> float:
        if bool(_get_field(option, "historical", False)):
            return 10000.0 + super().score_option(state, event, option)
        return super().score_option(state, event, option)


# ======================================================================
# 2. RevisionistHawkBot ("修正派铁壁")
# ======================================================================
class RevisionistHawkBot(StrategyBot):
    bot_id = "revisionist_hawk"
    name_zh = "修正派铁壁 (Revisionist Hawk)"
    description = "Jabotinsky/Shamir/Sharon Iron Wall strategy: maximizes deterrence, settlements, security, and territory."

    def __init__(self, seed: int = 1948) -> None:
        super().__init__(
            seed=seed,
            weights={
                "deterrence": 3.2,
                "readiness": 2.6,
                "public_security": 2.8,
                "region_security": 2.2,
                "settler_momentum": 3.5,
                "promise_progress.cat_territory": 2.5,
                "promise_progress.cat_security": 2.5,
                "promise_progress": 0.8,
                "vision_progress": 1.0,
                "bloc_support.religious_zionist": 2.2,
                "bloc_support.mizrahi": 1.4,
                "bloc_support.russian": 1.2,
                "bloc_support.liberal_middle": 0.2,
                "ally_satisfaction.nrp": 1.8,
                "ally_satisfaction.tehiya": 2.2,
                "ally_satisfaction.gahal": 2.0,
                "ally_satisfaction.likud": 2.0,
                "ally_satisfaction": 0.4,
                "relation.sharon": 1.2,
                "relation.begin": 1.2,
                "relation.shamir": 1.2,
                "relation.dayan": 0.8,
                "relation.chief_of_staff": 1.0,
                "hostile_faction": -2.8,
                "faction_strength.phalange": 1.2,
                "islamic_assoc_strength": -1.5,
                "intl_legitimacy": 0.1,
                "us_admin_relation": 0.25,
                "us_congress_relation": 0.8,
                "rule_of_law": 1.2,
                "centralization": -2.8,
                "pal_hostility": -0.15,
                "regime_hostility": -0.15,
                "popular_hostility": -0.1,
                "party_standing": 0.9,
                "political_capital": 0.3,
                "_corridor_away": -1.5,
                "_atrocity_avoidance": -1.0,
                "_mod_military_hawk": 12.0,
                "_mod_peace_inst": -4.0,
                "_mod_crisis_penalty": -2.0,
                "_axis_security": 1.8,
                "_axis_territory": 3.2,
                "_axis_foreign": 1.0,
            },
            tag_bonuses={
                "hardline": 18.0,
                "settlement": 18.0,
                "authoritarian": -12.0,
                "peace": -15.0,
                "restraint": -12.0,
                "extreme": -5.0,
            },
            cat_bonuses={"mil": 8.0, "terr": 10.0, "intel": 5.0, "opin": 2.0},
        )

    def choose_budget(self, state: Any) -> Dict[str, float]:
        return {
            "defense": 0.42,
            "welfare": 0.20,
            "infrastructure": 0.15,
            "settlements": 0.15,
            "education_tech": 0.08,
            "target_surplus": -1.0,
        }


# ======================================================================
# 3. PeaceDoveBot ("和平鸽派")
# ======================================================================
class PeaceDoveBot(StrategyBot):
    bot_id = "peace_dove"
    name_zh = "和平鸽派 (Peace Dove)"
    description = "Sharett/Rabin-Peres-Beilin/Meretz strategy: prioritizes peace agreements, international legitimacy, rule of law, and restraint."

    def __init__(self, seed: int = 1948) -> None:
        super().__init__(
            seed=seed,
            weights={
                "intl_legitimacy": 3.0,
                "us_admin_relation": 2.6,
                "us_congress_relation": 1.6,
                "power_relation": 1.5,
                "rule_of_law": 2.8,
                "civic_identification": 2.5,
                "pal_living_standard": 2.2,
                "autonomy_progress": 2.5,
                "promise_progress.cat_peace": 3.0,
                "promise_progress": 0.8,
                "vision_progress": 1.2,
                "pal_hostility": -2.4,
                "regime_hostility": -2.2,
                "popular_hostility": -1.8,
                "regime_stability": 1.8,
                "land_grievance": -2.2,
                "alienation": -1.5,
                "settler_momentum": -2.8,
                "centralization": -2.0,
                "judicial_conflict": -2.0,
                "bloc_support.liberal_middle": 2.4,
                "bloc_support.arab_citizens": 2.6,
                "bloc_support.kibbutz_moshav": 2.0,
                "bloc_support.labor_ashkenazi": 1.8,
                "bloc_support.religious_zionist": -0.8,
                "ally_satisfaction.mapam": 2.2,
                "ally_satisfaction.meretz": 2.5,
                "ally_satisfaction.labor": 2.0,
                "ally_satisfaction.nrp": -0.5,
                "relation.sharett": 1.5,
                "relation.peres": 1.5,
                "relation.rabin": 1.2,
                "relation.sharon": -1.2,
                "deterrence": 0.2,
                "readiness": 0.3,
                "public_security": 0.8,
                "party_standing": 0.5,
                "political_capital": 0.2,
                "hostile_faction": -0.6,
                "_corridor_away": 0.8,  # Willing to break hawkish corridors for peace
                "_atrocity_avoidance": 25.0,
                "_risk_low": 12.0,
                "_risk_mid": 2.0,
                "_risk_high": -15.0,
                "_mod_peace_inst": 14.0,
                "_mod_military_hawk": -10.0,
                "_mod_authoritarian": -15.0,
                "_mod_crisis_penalty": -8.0,
                "_axis_territory": -3.0,
                "_axis_security": -2.0,
                "_axis_foreign": -2.5,
                "_axis_religion": -1.5,
            },
            tag_bonuses={
                "peace": 22.0,
                "restraint": 18.0,
                "social": 6.0,
                "hardline": -16.0,
                "authoritarian": -20.0,
                "extreme": -50.0,
            },
            cat_bonuses={"dip": 10.0, "soc": 6.0, "inst": 5.0, "mil": -6.0, "terr": -4.0},
        )

    def choose_budget(self, state: Any) -> Dict[str, float]:
        return {
            "defense": 0.22,
            "welfare": 0.32,
            "infrastructure": 0.22,
            "settlements": 0.01,
            "education_tech": 0.23,
            "target_surplus": 0.5,
        }


# ======================================================================
# 4. PopulistWelfareBot ("民粹福利派")
# ======================================================================
class PopulistWelfareBot(StrategyBot):
    bot_id = "populist_welfare"
    name_zh = "民粹福利派 (Populist Welfare)"
    description = "David Levy / Shas / Histadrut welfare strategy: maximizes Mizrahi/Haredi/worker support, subsidies, and development towns."

    def __init__(self, seed: int = 1948) -> None:
        super().__init__(
            seed=seed,
            weights={
                "bloc_support.mizrahi": 3.5,
                "bloc_support.haredi": 3.0,
                "bloc_support.labor_ashkenazi": 2.2,
                "bloc_support.kibbutz_moshav": 1.6,
                "bloc_support": 1.8,
                "ally_satisfaction.shas": 3.2,
                "ally_satisfaction.agudat": 2.8,
                "ally_satisfaction.nrp": 2.2,
                "ally_satisfaction.mapam": 1.5,
                "ally_satisfaction": 2.0,
                "alienation": -3.2,
                "economic_gap": -3.0,
                "historical_grievance": -2.5,
                "unemployment": -3.0,
                "union_strength": 2.4,
                "absorption_capacity": 2.2,
                "region_development": 2.5,
                "religious_status_quo": 1.8,
                "promise_progress.social_justice": 3.5,
                "promise_progress.absorb_immigration": 2.5,
                "promise_progress": 1.5,
                "party_standing": 2.2,
                "political_capital": 0.6,
                # Tolerates fiscal deficits and inflation to fund social programs
                "budget_balance": 0.1,
                "inflation": -0.15,
                "fx_reserves": 0.2,
                "debt_gdp": -0.1,
                "public_security": 1.0,
                "deterrence": 0.8,
                "intl_legitimacy": 0.4,
                "rule_of_law": 1.0,
                "centralization": -2.5,
                "_mod_welfare": 15.0,
                "_mod_crisis_penalty": -3.0,
                "_axis_economy": -2.5,  # Socialist / welfare direction
                "_axis_religion": 1.5,
            },
            tag_bonuses={
                "social": 20.0,
                "economic": 4.0,
                "restraint": 3.0,
                "authoritarian": -15.0,
                "extreme": -15.0,
            },
            cat_bonuses={"soc": 12.0, "opin": 8.0, "coal": 8.0, "econ": 5.0},
        )

    def choose_budget(self, state: Any) -> Dict[str, float]:
        return {
            "defense": 0.24,
            "welfare": 0.44,
            "infrastructure": 0.18,
            "settlements": 0.04,
            "education_tech": 0.10,
            "target_surplus": -2.5,
        }


# ======================================================================
# 5. NeoliberalTechnocratBot ("新自由主义技术官僚")
# ======================================================================
class NeoliberalTechnocratBot(StrategyBot):
    bot_id = "neoliberal_technocrat"
    name_zh = "新自由主义技术官僚 (Neoliberal Technocrat)"
    description = "1985 Stabilization / Bank of Israel / Silicon Wadi strategy: prioritizes disinflation, FX reserves, fiscal surplus, privatization, and tech growth."

    def __init__(self, seed: int = 1948) -> None:
        super().__init__(
            seed=seed,
            weights={
                "inflation": -3.5,
                "budget_balance": 3.5,
                "fx_reserves": 3.2,
                "growth": 3.5,
                "economic_model": 3.8,
                "debt_gdp": -3.0,
                "union_strength": -2.5,
                "absorption_capacity": 2.0,
                "region_development": 1.8,
                "us_admin_relation": 2.2,
                "us_congress_relation": 2.0,
                "power_relation": 1.8,
                "intl_legitimacy": 1.6,
                "rule_of_law": 2.8,
                "judicial_conflict": -1.8,
                "centralization": -2.8,
                "bloc_support.liberal_middle": 3.0,
                "bloc_support.russian": 2.0,
                "bloc_support.haredi": -1.0,
                "ally_satisfaction.liberal": 2.5,
                "ally_satisfaction.shinui": 2.5,
                "ally_satisfaction.agudat": -1.2,
                "ally_satisfaction.shas": -1.0,
                "religious_status_quo": -1.5,
                "settler_momentum": -1.5,
                "deterrence": 0.8,
                "readiness": 0.8,
                "public_security": 1.2,
                "party_standing": 0.6,
                "political_capital": 0.5,
                "_stabilization_plan": 45.0,
                "_atrocity_avoidance": 10.0,
                "_mod_welfare": -12.0,
                "_mod_peace_inst": 6.0,
                "_mod_crisis_penalty": -8.0,
                "_axis_economy": 3.5,  # Market liberalization direction
                "_axis_religion": -2.0,
                "_axis_territory": -1.0,
            },
            tag_bonuses={
                "economic": 16.0,
                "restraint": 8.0,
                "peace": 6.0,
                "social": -8.0,
                "hardline": -6.0,
                "authoritarian": -10.0,
                "extreme": -35.0,
            },
            cat_bonuses={"econ": 14.0, "dip": 6.0, "inst": 5.0, "terr": -5.0},
        )

    def score_option(self, state: Any, event: Any, option: Any) -> float:
        base = super().score_option(state, event, option)
        # Dynamic macro-crisis awareness: amplify disinflation and FX rescue when inflation > 60 or FX < 25
        inf = _get_state_param(state, "inflation", default=15.0)
        fx = _get_state_param(state, "fx_reserves", default=50.0)
        if inf > 60.0 or fx < 25.0:
            for ef in _get_field(option, "effects") or []:
                op = str(_get_field(ef, "op", ""))
                t = str(_get_field(ef, "target", ""))
                v = _get_field(ef, "value", 0.0)
                if op == "add" and isinstance(v, (int, float)):
                    if t == "inflation" and v < 0:
                        base += abs(float(v)) * 4.0
                    elif t in ("fx_reserves", "budget_balance") and v > 0:
                        base += float(v) * 4.0
                elif op == "custom" and str(_get_field(ef, "handler", "")) == "apply_stabilization_plan":
                    base += 80.0
        return base

    def choose_budget(self, state: Any) -> Dict[str, float]:
        return {
            "defense": 0.24,
            "welfare": 0.18,
            "infrastructure": 0.26,
            "settlements": 0.02,
            "education_tech": 0.30,
            "target_surplus": 2.0,
        }


# ======================================================================
# 6. AuthoritarianCaesarBot ("强人集权派")
# ======================================================================
class AuthoritarianCaesarBot(StrategyBot):
    bot_id = "authoritarian_caesar"
    name_zh = "强人集权派 (Authoritarian Caesar)"
    description = "Executive concentration strategy: maximizes centralization, political capital, censorship, Shin Bet internal powers, and judicial curbing."

    def __init__(self, seed: int = 1948) -> None:
        super().__init__(
            seed=seed,
            weights={
                "centralization": 3.8,
                "political_capital": 2.5,
                "party_standing": 2.5,
                "deterrence": 2.2,
                "public_security": 2.4,
                "region_security": 2.0,
                "readiness": 1.8,
                "settler_momentum": 1.2,
                "rule_of_law": -2.5,
                "judicial_conflict": 1.2,
                "intl_legitimacy": -0.8,
                "us_admin_relation": -0.3,
                "civic_identification": -0.8,
                "relation.shin_bet_chief": 2.5,
                "relation.mossad_chief": 2.0,
                "relation.chief_of_staff": 2.0,
                "relation.sharon": 1.8,
                "relation.dayan": 1.5,
                "hostile_faction": -2.5,
                "bloc_support.mizrahi": 1.2,
                "bloc_support.russian": 1.5,
                "bloc_support.religious_zionist": 1.5,
                "bloc_support.liberal_middle": -1.5,
                "bloc_support.arab_citizens": -1.5,
                "_corridor_away": 0.5,
                "_atrocity_avoidance": -8.0,
                "_risk_high": 8.0,
                "_risk_low": -6.0,
                "_mod_authoritarian": 22.0,
                "_mod_military_hawk": 10.0,
                "_mod_peace_inst": -14.0,
                "_mod_crisis_penalty": -1.0,
                "_axis_security": 2.5,
                "_axis_territory": 1.8,
            },
            tag_bonuses={
                "authoritarian": 28.0,
                "extreme": 18.0,
                "hardline": 12.0,
                "restraint": -18.0,
                "peace": -18.0,
            },
            cat_bonuses={"inst": 12.0, "intel": 12.0, "parl": 8.0, "mil": 8.0},
        )

    def choose_budget(self, state: Any) -> Dict[str, float]:
        return {
            "defense": 0.40,
            "welfare": 0.22,
            "infrastructure": 0.18,
            "settlements": 0.12,
            "education_tech": 0.08,
            "target_surplus": -0.5,
        }


# ======================================================================
# 7. RandomBot ("均匀随机基线")
# ======================================================================
class RandomBot(StrategyBot):
    bot_id = "random"
    name_zh = "均匀随机基线 (Random Baseline)"
    description = "Uniformly samples options and valid actions using a deterministic PRNG for Monte Carlo baseline comparisons."

    def __init__(self, seed: int = 1948) -> None:
        super().__init__(seed=seed)

    def choose_event_option(
        self,
        state: Any,
        event: Any,
        options: Optional[Sequence[Any]] = None,
    ) -> str:
        opts = list(options if options is not None else (_get_field(event, "options") or []))
        if not opts:
            return "A"
        eid = str(_get_field(event, "id", "ev"))
        # Deterministic per-event hash combined with bot seed so order of event evaluation never causes drift
        h = int(hashlib.sha256(f"{self.seed}:{eid}:{len(opts)}".encode("utf-8")).hexdigest()[:8], 16)
        chosen = opts[h % len(opts)]
        return str(_get_field(chosen, "id", "A"))

    def choose_actions(
        self,
        state: Any,
        available_actions: Sequence[Any],
        policies: Optional[Sequence[Any]] = None,
        max_actions: int = 2,
    ) -> List[Dict[str, Any]]:
        pc_avail = _get_state_param(state, "political_capital", default=60.0)
        affordable: List[Dict[str, Any]] = []
        for idx, act in enumerate(available_actions or []):
            aid = str(_get_field(act, "id", f"act_{idx}"))
            if aid == "adjust_policy":
                continue
            cost = _get_field(act, "cost") or {}
            pc_cost = float(cost.get("pc", 0.0)) if isinstance(cost, dict) else 0.0
            if pc_cost <= pc_avail:
                affordable.append({"id": aid, "score": 1.0, "pc_cost": pc_cost, "action": act})
        if not affordable:
            return []
        self._rng.shuffle(affordable)
        chosen: List[Dict[str, Any]] = []
        rem_pc = pc_avail
        for item in affordable:
            if len(chosen) >= max_actions:
                break
            if item["pc_cost"] <= rem_pc:
                chosen.append(item)
                rem_pc -= item["pc_cost"]
        return chosen

    def score_action(self, state: Any, action: Any) -> float:
        return 1.0

    def choose_policy_adjustments(
        self,
        state: Any,
        policies: Sequence[Any],
        max_adjustments: int = 1,
    ) -> List[Dict[str, Any]]:
        pol_list = list(policies or [])
        if not pol_list:
            return []
        self._rng.shuffle(pol_list)
        out: List[Dict[str, Any]] = []
        state_pols = getattr(state, "policies", None) if state is not None else None
        cur_day = int(getattr(state, "day_index", 0)) if state is not None else 0
        for pol in pol_list:
            pid = str(_get_field(pol, "id", ""))
            if not pid:
                continue
            direction = "up" if self._rng.random() < 0.5 else "down"
            if isinstance(state_pols, dict) and pid in state_pols:
                p_st = state_pols[pid]
                if int(p_st.get("cooldown_until_day", 0)) > cur_day:
                    continue
                tiers = _get_field(pol, "tiers") or []
                cur_idx = int(p_st.get("tier_idx", 0))
                if direction == "up" and cur_idx >= len(tiers) - 1:
                    direction = "down"
                elif direction == "down" and cur_idx <= 0:
                    direction = "up"
            out.append({"policy_id": pid, "direction": direction, "utility": 1.0})
            if len(out) >= max_adjustments:
                break
        return out


def get_all_bots(seed: int = 1948) -> List[StrategyBot]:
    """Instantiate and return all 7 canonical Strategy Bots."""
    return [
        HistoricalBot(seed=seed),
        RevisionistHawkBot(seed=seed),
        PeaceDoveBot(seed=seed),
        PopulistWelfareBot(seed=seed),
        NeoliberalTechnocratBot(seed=seed),
        AuthoritarianCaesarBot(seed=seed),
        RandomBot(seed=seed),
    ]


def evaluate_bot_differentiation() -> Dict[str, Any]:
    """Run all 7 bots across all 396 events and 104 actions to verify persona differentiation."""
    import glob
    import os
    import yaml

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bots = get_all_bots(seed=1948)
    event_files = sorted(glob.glob(os.path.join(root, "data", "events", "*.yaml")))
    actions = yaml.safe_load(open(os.path.join(root, "data", "actions.yaml"), encoding="utf-8")).get("actions", [])
    policies = yaml.safe_load(open(os.path.join(root, "data", "policies.yaml"), encoding="utf-8")).get("policies", [])

    dummy_state = {
        "political_capital": 60.0,
        "inflation": 45.0,
        "fx_reserves": 32.0,
        "budget_balance": -1.5,
        "public_security": 55.0,
        "rule_of_law": 65.0,
    }

    choices_by_bot: Dict[str, List[str]] = {b.bot_id: [] for b in bots}
    option_freq_by_bot: Dict[str, Dict[str, int]] = {
        b.bot_id: {"A": 0, "B": 0, "C": 0, "D": 0} for b in bots
    }
    unanimous_events = 0
    total_choice_events = 0

    for f in event_files:
        evs = yaml.safe_load(open(f, encoding="utf-8")).get("events", [])
        for ev in evs:
            opts = ev.get("options") or []
            if not opts:
                continue
            total_choice_events += 1
            picks: Set[str] = set()
            for b in bots:
                c = b.choose_event_option(dummy_state, ev, opts)
                choices_by_bot[b.bot_id].append(f"{ev['id']}:{c}")
                option_freq_by_bot[b.bot_id][c] = option_freq_by_bot[b.bot_id].get(c, 0) + 1
                picks.add(c)
            if len(picks) == 1:
                unanimous_events += 1

    # Compute pairwise disagreement rates among the 7 bots
    pairwise_diff: Dict[Tuple[str, str], float] = {}
    for i, b1 in enumerate(bots):
        for j, b2 in enumerate(bots):
            if j <= i:
                continue
            c1 = choices_by_bot[b1.bot_id]
            c2 = choices_by_bot[b2.bot_id]
            diffs = sum(1 for x, y in zip(c1, c2) if x != y)
            pairwise_diff[(b1.bot_id, b2.bot_id)] = diffs / float(len(c1))

    top_actions_by_bot: Dict[str, List[str]] = {}
    for b in bots:
        chosen = b.choose_actions(dummy_state, actions, policies, max_actions=5)
        top_actions_by_bot[b.bot_id] = [item["id"] for item in chosen]

    return {
        "total_choice_events": total_choice_events,
        "unanimous_events": unanimous_events,
        "option_freq_by_bot": option_freq_by_bot,
        "pairwise_diff": pairwise_diff,
        "top_actions_by_bot": top_actions_by_bot,
    }


if __name__ == "__main__":
    report = evaluate_bot_differentiation()
    print("=" * 72)
    print(f"7 STRATEGY BOTS DIFFERENTIATION SELF-TEST ({report['total_choice_events']} choice events)")
    print("=" * 72)
    print(f"Unanimous events across all 7 bots: {report['unanimous_events']}/{report['total_choice_events']} ({report['unanimous_events']/report['total_choice_events']:.1%})")
    print("\nOption Distribution (A / B / C) per Bot:")
    for bid, freqs in report["option_freq_by_bot"].items():
        print(f"  - {bid:<22}: A={freqs.get('A',0):>3}, B={freqs.get('B',0):>3}, C={freqs.get('C',0):>3}")
    print("\nTop 5 Preferred Actions per Bot:")
    for bid, acts in report["top_actions_by_bot"].items():
        print(f"  - {bid:<22}: {', '.join(acts)}")
    print("\nKey Pairwise Disagreement Rates:")
    for (b1, b2), rate in sorted(report["pairwise_diff"].items(), key=lambda x: -x[1])[:8]:
        print(f"  - {b1} vs {b2}: {rate:.1%} disagreement")
