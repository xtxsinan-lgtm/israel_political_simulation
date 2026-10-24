from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import yaml

from sim.rng import DeterministicRNG

ROOT_DIR = Path(__file__).resolve().parent.parent


def quantize(x: float) -> float:
    """Quantize float to 1e-6 precision using floor(x * 1e6 + 0.5) / 1e6 (M01 §4.11.2, D-015)."""
    return math.floor(float(x) * 1_000_000.0 + 0.5) / 1_000_000.0


q = quantize


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x into [lo, hi]; follows M12 §4.4.5 min(max(x, lo), hi)."""
    return min(max(float(x), float(lo)), float(hi))


# ---------------------------------------------------------------------------
# Proleptic Gregorian Calendar Utilities (M01 §4.5.1, epoch 1970-01-01 = 0)
# ---------------------------------------------------------------------------

def is_leap_year(y: int) -> bool:
    return (y % 4 == 0 and y % 100 != 0) or (y % 400 == 0)


def days_in_month(y: int, m: int) -> int:
    if m in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if m in (4, 6, 9, 11):
        return 30
    if m == 2:
        return 29 if is_leap_year(y) else 28
    raise ValueError(f"Invalid month: {m}")


def days_from_civil(y: int, m: int, d: int) -> int:
    """Howard Hinnant's civil-to-days algorithm (1970-01-01 -> 0, 1977-06-20 -> 2727)."""
    y_adj = y - (1 if m <= 2 else 0)
    era = y_adj // 400
    yoe = y_adj - era * 400
    mp = m + (-3 if m > 2 else 9)
    doy = (153 * mp + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z: int) -> Tuple[int, int, int]:
    """Inverse of days_from_civil: returns (year, month, day)."""
    z_adj = z + 719468
    era = z_adj // 146097
    doe = z_adj - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    y += 1 if m <= 2 else 0
    return int(y), int(m), int(d)


def weekday_from_days(z: int) -> int:
    """Return weekday in 0..6 where 0=Monday .. 6=Sunday (2727 -> 0)."""
    return (z + 3) % 7


def parse_date(date_str: str) -> Tuple[int, int, int]:
    s = str(date_str).strip()
    parts = s.split("-")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1]), 1
    if len(parts) == 3:
        return int(parts[0]), int(parts[1]), int(parts[2])
    raise ValueError(f"Invalid date string: {date_str!r}")


def format_date(y: int, m: int, d: int) -> str:
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def date_to_abs_day(date_str: str) -> int:
    y, m, d = parse_date(date_str)
    return days_from_civil(y, m, d)


def abs_day_to_date(z: int) -> str:
    y, m, d = civil_from_days(z)
    return format_date(y, m, d)


def date_to_m12_day_index(date_str: str) -> int:
    """M12 §4.1 day_index(d) relative to 1948-01-01 = 0."""
    return date_to_abs_day(date_str) - days_from_civil(1948, 1, 1)


def add_months(date_str: str, months: int) -> str:
    """Add calendar months preserving day, clamped to end of target month (M12 §4.1)."""
    y, m, d = parse_date(date_str)
    total_m = (y * 12 + (m - 1)) + int(months)
    ny = total_m // 12
    nm = (total_m % 12) + 1
    nd = min(d, days_in_month(ny, nm))
    return format_date(ny, nm, nd)


def months_between(earlier_date: str, later_date: str) -> int:
    """M12 §4.4.5 months_since formula: (Y2 - Y1)*12 + (M2 - M1) - (1 if D2 < D1 else 0)."""
    y1, m1, d1 = parse_date(earlier_date)
    y2, m2, d2 = parse_date(later_date)
    return (y2 - y1) * 12 + (m2 - m1) - (1 if d2 < d1 else 0)


# ---------------------------------------------------------------------------
# Entity Alias Resolution Tables (M02 / M06 / M08 / M11 / parameters.yaml)
# ---------------------------------------------------------------------------

REGION_ALIAS_MAP: Dict[str, str] = {
    "north": "galilee",
    "galilee": "galilee",
    "haifa": "haifa",
    "tel_aviv": "tel_aviv",
    "central": "triangle",
    "triangle": "triangle",
    "jerusalem": "jerusalem",
    "south": "negev",
    "negev": "negev",
    "west_bank": "west_bank",
    "gaza": "gaza",
    "golan": "golan",
    "sinai": "sinai",
    "south_lebanon": "south_lebanon",
}

FACTION_ALIAS_MAP: Dict[str, str] = {
    "notables": "jordan_notables",
    "jordan_notables": "jordan_notables",
    "left_factions": "pflp",
    "pflp": "pflp",
    "islamic_jihad": "pij",
    "pij": "pij",
    "fatah": "fatah",
    "local_mayors": "local_mayors",
    "village_leagues": "village_leagues",
    "mujama": "mujama",
    "hamas": "hamas",
    "pa_security": "pa_security",
}

PARTY_ALIAS_MAP: Dict[str, str] = {
    "alignment": "labor",
    "labor": "labor",
    "agudat_yisrael": "agudat",
    "agudat": "agudat",
    "hadash": "rakah_hadash",
    "rakah_hadash": "rakah_hadash",
    "pm_new_party": "new_party_a",
    "new_party_a": "new_party_a",
}

OFFICE_ALIAS_MAP: Dict[str, str] = {
    "pm": "prime_minister",
    "prime_minister": "prime_minister",
    "defense": "defense",
    "defense_minister": "defense",
    "finance": "finance",
    "finance_minister": "finance",
    "foreign": "foreign",
    "foreign_minister": "foreign",
    "interior": "interior",
    "interior_minister": "interior",
    "justice": "justice",
    "justice_minister": "justice",
    "housing": "housing",
    "housing_minister": "housing",
    "religion": "religious_affairs",
    "religion_minister": "religious_affairs",
    "religious_affairs": "religious_affairs",
    "education": "education",
    "education_minister": "education",
    "absorption": "absorption",
    "absorption_minister": "absorption",
    "agriculture": "agriculture",
    "agriculture_minister": "agriculture",
    "industry_trade": "industry_trade",
    "energy": "energy",
    "transport": "transport",
    "transport_minister": "transport",
    "labor_welfare": "labor_welfare",
    "cos": "chief_of_staff",
    "chief_of_staff": "chief_of_staff",
    "mossad": "mossad_chief",
    "mossad_chief": "mossad_chief",
    "shin_bet": "shin_bet_chief",
    "shin_bet_chief": "shin_bet_chief",
    "ag": "attorney_general",
    "attorney_general": "attorney_general",
    "boi": "boi_governor",
    "boi_governor": "boi_governor",
    "central_bank_governor": "boi_governor",
    "supreme_court": "supreme_court_president",
    "supreme_court_president": "supreme_court_president",
    "opposition": "opposition_leader",
    "opposition_leader": "opposition_leader",
}

PROMISE_ALIAS_MAP: Dict[str, str] = {
    "peace_security": "peace_and_security",
    "peace_and_security": "peace_and_security",
    "settle_eretz_israel": "settle_eretz_israel",
    "economic_liberalization": "economic_liberalization",
    "social_justice": "social_justice",
}

PARAM_ALIAS_MAP: Dict[str, str] = {
    "voter_cynicism": "cynicism",
    "security_index": "public_security",
    "country_stability": "regime_stability",
    "country_nuclear_progress": "enemy_nuclear_progress",
    "annual_immigration": "immigration_inflow",
    "palestinian_hostility": "pal_hostility",
    "intifada_risk": "uprising_risk",
    "us_stance": "us_admin_relation",
    "policy": "policy_level",
}

BLOC_ALIAS_MAP: Dict[str, str] = {
    "mizrahi_working": "mizrahi",
    "haredi_orth": "haredi",
    "russian_immigrants": "russian",
}


def resolve_region_id(key: str) -> str:
    return REGION_ALIAS_MAP.get(key, key)


def resolve_faction_id(key: str) -> str:
    return FACTION_ALIAS_MAP.get(key, key)


def resolve_party_id(key: str) -> str:
    return PARTY_ALIAS_MAP.get(key, key)


def resolve_bloc_id(key: str) -> str:
    return BLOC_ALIAS_MAP.get(key, key)


# ---------------------------------------------------------------------------
# Static Data Registry (Cached across runs)
# ---------------------------------------------------------------------------

class DataRegistry:
    """Singleton-cached loader for all YAML data and registries in data/ and docs/registry/."""

    _instance: Optional[DataRegistry] = None

    def __init__(self, root_dir: Path = ROOT_DIR) -> None:
        self.root_dir: Path = root_dir
        self.parameters_raw: Dict[str, Any] = self._load_yaml("data/parameters.yaml")
        self.entities: Dict[str, List[str]] = self.parameters_raw.get("entities", {})
        self.param_defs: Dict[str, Dict[str, Any]] = {}
        for p in self.parameters_raw.get("parameters", []):
            self.param_defs[p["id"]] = p

        self.thresholds_raw: Dict[str, Any] = self._load_yaml("data/thresholds.yaml")
        self.thresholds: List[Dict[str, Any]] = self.thresholds_raw.get("thresholds", [])

        self.causal_edges_raw: Dict[str, Any] = self._load_yaml("data/causal_edges.yaml")
        self.node_configs: Dict[str, Dict[str, Any]] = self.causal_edges_raw.get("node_configs", {})
        self.causal_edges: List[Dict[str, Any]] = self.causal_edges_raw.get("edges", [])

        self.policies_raw: Dict[str, Any] = self._load_yaml("data/policies.yaml")
        self.policies: Dict[str, Dict[str, Any]] = {}
        for pol in self.policies_raw.get("policies", []):
            self.policies[pol["id"]] = pol

        self.actions_raw: Dict[str, Any] = self._load_yaml("data/actions.yaml")
        self.actions: Dict[str, Dict[str, Any]] = {}
        for act in self.actions_raw.get("actions", []):
            self.actions[act["id"]] = act

        self.corridors_raw: Dict[str, Any] = self._load_yaml("data/parties/corridors.yaml")
        self.party_corridors: Dict[str, Any] = self.corridors_raw.get("parties", {})

        self.vision_begin_raw: Dict[str, Any] = self._load_yaml("data/visions/begin_peace_in_eretz_israel.yaml")

        self.world_tracks_raw: Dict[str, Any] = self._load_yaml("data/world_tracks.yaml")
        self.palestine_factions_raw: Dict[str, Any] = self._load_yaml("data/palestine_factions.yaml")
        self.regions_raw: Dict[str, Any] = self._load_yaml("data/regions.yaml")
        self.characters_raw: Dict[str, Any] = self._load_yaml("data/characters.yaml")

        self.flags_raw: Dict[str, Any] = self._load_yaml("docs/registry/flags.yaml")
        self.flag_defs: Dict[str, Dict[str, Any]] = {}
        for f in self.flags_raw.get("flags", []):
            self.flag_defs[f["id"]] = f

        self.modifiers_raw: Dict[str, Any] = self._load_yaml("docs/registry/modifiers.yaml")
        self.modifier_defs: Dict[str, Dict[str, Any]] = {}
        for m in self.modifiers_raw.get("modifiers", []):
            self.modifier_defs[m["id"]] = m

        self.fixed_events_raw: Dict[str, Any] = self._load_yaml("data/events/fixed_1977_1992.yaml")
        self.random_events_raw: Dict[str, Any] = self._load_yaml("data/events/random_events.yaml")

        # Also index any flags or modifiers declared inline in event files
        for ev_file in (self.fixed_events_raw, self.random_events_raw):
            for f in ev_file.get("flags", []) or []:
                if isinstance(f, dict) and "id" in f and f["id"] not in self.flag_defs:
                    self.flag_defs[f["id"]] = f
            for m in ev_file.get("modifiers", []) or []:
                if isinstance(m, dict) and "id" in m:
                    # Merge or register modifier definition
                    existing = self.modifier_defs.get(m["id"], {})
                    merged = dict(existing)
                    merged.update(m)
                    self.modifier_defs[m["id"]] = merged

        self.fixed_events: List[Dict[str, Any]] = self.fixed_events_raw.get("events", [])
        self.random_events: List[Dict[str, Any]] = self.random_events_raw.get("events", [])
        self.events_by_id: Dict[str, Dict[str, Any]] = {}
        for ev in self.fixed_events:
            self.events_by_id[ev["id"]] = ev
        for ev in self.random_events:
            self.events_by_id[ev["id"]] = ev

        self._scenarios_cache: Dict[str, Dict[str, Any]] = {}

    def _load_yaml(self, rel_path: str) -> Dict[str, Any]:
        p = self.root_dir / rel_path
        if not p.exists():
            return {}
        loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.load(f, Loader=loader)
        return data if isinstance(data, dict) else {}

    def get_scenario_bundle(self, scenario_id: str = "begin_1977") -> Dict[str, Any]:
        if scenario_id not in self._scenarios_cache:
            base = f"data/scenarios/{scenario_id}"
            self._scenarios_cache[scenario_id] = {
                "scenario": self._load_yaml(f"{base}/scenario.yaml"),
                "snapshot": self._load_yaml(f"{base}/snapshot.yaml"),
                "M03": self._load_yaml(f"{base}/modules/M03.yaml"),
                "M04": self._load_yaml(f"{base}/modules/M04.yaml"),
            }
        return copy.deepcopy(self._scenarios_cache[scenario_id])

    @classmethod
    def instance(cls, root_dir: Path = ROOT_DIR) -> DataRegistry:
        if cls._instance is None or cls._instance.root_dir != root_dir:
            cls._instance = DataRegistry(root_dir)
        return cls._instance


# ---------------------------------------------------------------------------
# Canonical JSON & State Hash (M01 §4.11.2)
# ---------------------------------------------------------------------------

def _canonicalize_value(val: Any) -> Any:
    if isinstance(val, dict):
        return {str(k): _canonicalize_value(val[k]) for k in sorted(val.keys(), key=lambda x: str(x))}
    if isinstance(val, (list, tuple)):
        return [_canonicalize_value(v) for v in val]
    if isinstance(val, bool) or val is None:
        return val
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        qv = quantize(val)
        return qv
    return val


def canonical_json(data: Any) -> str:
    """Serialize data into deterministic compact JSON with sorted keys and quantized floats."""
    canon = _canonicalize_value(data)
    return json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_sha256(data: Any) -> str:
    s = canonical_json(data)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# GameState Implementation
# ---------------------------------------------------------------------------

class GameState:
    """Authoritative simulation state container for all modules M01-M14."""

    def __init__(
        self,
        scenario_id: str = "begin_1977",
        master_seed: int = 19770620,
        world_variant_mode: str = "historical_gravity",
        ironman: bool = False,
        registry: Optional[DataRegistry] = None,
    ) -> None:
        self.registry: DataRegistry = registry or DataRegistry.instance()
        self.scenario_id: str = scenario_id
        self.master_seed: int = int(master_seed)
        self.rng: DeterministicRNG = DeterministicRNG(self.master_seed)

        # Meta & Run state (M01 §3.2)
        self.meta: Dict[str, Any] = {
            "save_version": 1,
            "scenario_id": scenario_id,
            "master_seed": self.master_seed,
            "ironman": bool(ironman),
            "modified": False,
            "completed": False,
        }
        self.run: Dict[str, Any] = {
            "phase": "RUNNING",  # PAUSED | RUNNING | RESOLVING | TENURE_SUMMARY | SUCCESSION_SETUP | EPILOGUE | ENDED
            "speed": 1,
            "tenure_index": 0,
            "tenure_start_day": 0,
            "tenure_start_date": "1977-06-20",
            "government_start_date": "1977-06-20",
            "tenure_elections_won": 0,
        }
        self.player: Dict[str, Any] = {
            "leader_id": "begin",
            "party_id": "likud",
            "role": "pm",
        }

        # Calendar state
        self.start_date: str = "1977-06-20"
        self.start_abs_day: int = days_from_civil(1977, 6, 20)
        self.day_index: int = 0
        self.abs_day: int = self.start_abs_day
        self.date_str: str = self.start_date
        self.year: int = 1977
        self.month: int = 6
        self.day: int = 20
        self.weekday: int = 0

        # Core Parameter Store (national floats & scoped dicts)
        self.params: Dict[str, Any] = {}

        # Flags & Modifiers
        self.flags: Dict[str, Dict[str, Any]] = {}
        self.modifiers: List[Dict[str, Any]] = []
        self.next_modifier_uid: int = 1

        # Policies & Actions (M05)
        self.policies: Dict[str, Dict[str, Any]] = {}
        self.gov_axis_position: Dict[str, float] = {
            "territory": 0.0,
            "security": 0.0,
            "economy": 0.0,
            "religion": 0.0,
            "foreign": 0.0,
        }
        self.axis_impulse: Dict[str, float] = {
            "territory": 0.0,
            "security": 0.0,
            "economy": 0.0,
            "religion": 0.0,
            "foreign": 0.0,
        }
        self.m05: Dict[str, Any] = {}

        # Characters & Cabinet (M06)
        self.characters: Dict[str, Dict[str, Any]] = {}
        self.offices: Dict[str, Optional[str]] = {}
        self.m06: Dict[str, Any] = {}

        # Parliament (M03) & Party/Promises/Vision (M04)
        self.parliament: Dict[str, Any] = {}
        self.corridors: Dict[str, Any] = {}
        self.party_state: Dict[str, Any] = {}
        self.promises: List[Dict[str, Any]] = []
        self.leader_goal_packs: Dict[str, Any] = {}
        self.vision: Dict[str, Any] = {}
        self.m03: Dict[str, Any] = {}
        self.m04: Dict[str, Any] = {}

        # World (M07), Palestine (M08), Military (M09), Economy (M10), Regions (M11), Events (M12), Auth (M13), Endings (M14)
        self.m07: Dict[str, Any] = {}
        self.m08: Dict[str, Any] = {}
        self.m09: Dict[str, Any] = {}
        self.m10: Dict[str, Any] = {}
        self.m11: Dict[str, Any] = {}
        self.m12: Dict[str, Any] = {}
        self.m13: Dict[str, Any] = {}
        self.m14: Dict[str, Any] = {}

        # CausalNet runtime state (M02): shock memory, 24-month history, threshold states, one-off flows, explanations
        self.m02: Dict[str, Any] = {
            "shock_mem": {},
            "history_24m": {},
            "thresholds": {},
            "one_off_flows": {"budget_balance": 0.0},
            "last_contribs": {},
        }

        # Pending queues & History (M01)
        self.pending: Dict[str, Any] = {
            "player_ops": [],
            "effect_queue": [],
            "delayed_effects": [],
            "hooks": [],
            "vote_requests": [],
            "popups": [],
            "pause_signals": [],
            "tenure_end": None,
        }
        self.history: Dict[str, Any] = {
            "series": {"dates": [], "metrics": {}},
            "turning_points": [],
            "event_log": [],
            "action_log": [],
            "contrib_ledger": {},
        }
        self.tenures: List[Dict[str, Any]] = []

        self._init_from_scenario(scenario_id, world_variant_mode)

    # ------------------------------------------------------------------
    # Calendar Properties
    # ------------------------------------------------------------------

    def update_calendar(self, new_day_index: int) -> None:
        self.day_index = int(new_day_index)
        self.abs_day = self.start_abs_day + self.day_index
        self.year, self.month, self.day = civil_from_days(self.abs_day)
        self.date_str = format_date(self.year, self.month, self.day)
        self.weekday = weekday_from_days(self.abs_day)

    @property
    def is_week(self) -> bool:
        """True on Sunday (weekday == 6, M01 §4.5.1)."""
        return self.weekday == 6

    @property
    def is_month(self) -> bool:
        """True on 1st of every month."""
        return self.day == 1

    @property
    def is_quarter(self) -> bool:
        """True on Jan 1, Apr 1, Jul 1, Oct 1."""
        return self.day == 1 and self.month in (1, 4, 7, 10)

    @property
    def is_half_year(self) -> bool:
        """True on Jan 1 and Jul 1."""
        return self.day == 1 and self.month in (1, 7)

    @property
    def is_year(self) -> bool:
        """True on Jan 1."""
        return self.day == 1 and self.month == 1

    def era_number(self) -> int:
        """M12 §4.4.5 era() -> 1..5."""
        d = self.date_str
        if d <= "1955-12-31":
            return 1
        if d <= "1967-06-04":
            return 2
        if d <= "1977-06-19":
            return 3
        if d <= "1992-07-12":
            return 4
        return 5

    # ------------------------------------------------------------------
    # Scenario Initialization
    # ------------------------------------------------------------------

    def _init_from_scenario(self, scenario_id: str, world_variant_mode: str) -> None:
        bundle = self.registry.get_scenario_bundle(scenario_id)
        scen = bundle.get("scenario", {})
        snap = bundle.get("snapshot", {})

        self.start_date = str(scen.get("start_date", snap.get("start_date", "1977-06-20")))
        self.start_abs_day = date_to_abs_day(self.start_date)
        self.update_calendar(0)

        self.run["tenure_start_day"] = 0
        self.run["tenure_start_date"] = self.start_date
        self.run["government_start_date"] = self.start_date
        self.player["leader_id"] = str(scen.get("leader_id", "begin"))
        self.player["party_id"] = str(scen.get("party_id", "likud"))

        # 1. Initialize all parameters from parameters.yaml defaults, then overlay snapshot.yaml
        for pid, pdef in self.registry.param_defs.items():
            scope = pdef.get("scope", "national")
            init_val = pdef.get("init_1977")
            if scope == "national":
                self.params[pid] = float(init_val) if isinstance(init_val, (int, float)) else 0.0
            else:
                if isinstance(init_val, dict):
                    self.params[pid] = {str(k): float(v) for k, v in init_val.items() if v is not None}
                else:
                    self.params[pid] = {}

        snap_params = snap.get("params", {})
        for pid, val in snap_params.items():
            if isinstance(val, dict):
                if pid not in self.params or not isinstance(self.params[pid], dict):
                    self.params[pid] = {}
                for k, v in val.items():
                    if v is not None:
                        self.params[pid][str(k)] = float(v)
            elif isinstance(val, (int, float)):
                self.params[pid] = float(val)

        # Ensure synchronized alias pairs at Day 0
        self.params["voter_cynicism"] = float(self.params.get("cynicism", 20.0))
        self.params["cynicism"] = float(self.params.get("cynicism", 20.0))
        if "faction_strength" in self.params and "mujama" in self.params["faction_strength"]:
            self.params["islamic_assoc_strength"] = float(self.params["faction_strength"]["mujama"])

        # 2. Initialize Policies (M05) from data/policies.yaml and snapshot policy_level
        snap_pol_levels = self.params.get("policy_level", {}) if isinstance(self.params.get("policy_level"), dict) else {}
        for pol_id, pol_def in self.registry.policies.items():
            start_map = pol_def.get("start", {})
            sval = start_map.get(scenario_id, start_map.get("begin_1977", 0))
            if isinstance(sval, dict):
                sval = next(iter(sval.values()), 0)
            tiers = pol_def.get("tiers", [])
            tier_vals = [float(t["v"] if isinstance(t, dict) else t) for t in tiers]
            if pol_id in snap_pol_levels:
                level = float(snap_pol_levels[pol_id])
                tier_idx = tier_vals.index(level) if level in tier_vals else 0
            elif isinstance(sval, bool):
                level = 100.0 if sval else 0.0
                tier_idx = 1 if sval else 0
            elif isinstance(sval, (int, float)):
                if 0 <= int(sval) < len(tier_vals):
                    tier_idx = int(sval)
                    level = float(tier_vals[tier_idx])
                elif float(sval) in tier_vals:
                    level = float(sval)
                    tier_idx = tier_vals.index(level)
                else:
                    level = float(sval)
                    tier_idx = 0
            else:
                level = float(tier_vals[0]) if tier_vals else 0.0
                tier_idx = 0
            self.policies[pol_id] = {
                "id": pol_id,
                "level": level,
                "target_level": level,
                "tier_idx": tier_idx,
                "cooldown_until_day": 0,
                "PendingBillId": None,
            }

        # Populate policy_level in params for uniform parameter access
        if not isinstance(self.params.get("policy_level"), dict):
            self.params["policy_level"] = {}
        for pid, p in self.policies.items():
            self.params["policy_level"].setdefault(pid, p["level"])
        self.recompute_gov_axis_position()

        # 3. Initialize Characters & Offices (M06) from data/characters.yaml
        chars_list = self.registry.characters_raw.get("characters", [])
        self.offices = {
            "prime_minister": "begin",
            "foreign": "dayan",
            "defense": "weizman",
            "finance": "ehrlich",
            "deputy_pm": "ehrlich",
            "agriculture": "sharon",
            "interior": "burg",
            "police": "burg",
            "education": "hammer",
            "religious_affairs": "abuhatzeira",
            "industry_trade": "hurvitz",
            "housing": "patt",
            "absorption": "levy",
            "energy": "modai",
            "communications": "modai",
            "justice": None,
            "transport": None,
            "labor_welfare": None,
            "chief_of_staff": "gur",
            "mossad_chief": "hofi",
            "shin_bet_chief": "shalom",
            "attorney_general": "barak_aharon",
            "supreme_court_president": "kahan",
            "boi_governor": "gafni",
            "opposition_leader": "peres",
        }
        if "relation" not in self.params or not isinstance(self.params["relation"], dict):
            self.params["relation"] = {}
        if "health" not in self.params or not isinstance(self.params["health"], dict):
            self.params["health"] = {}
        if "character_stress" not in self.params or not isinstance(self.params["character_stress"], dict):
            self.params["character_stress"] = {}

        for ch in chars_list:
            cid = ch["id"]
            c_copy = copy.deepcopy(ch)
            c_copy.setdefault("alive", bool(ch.get("alive_1977", True)))
            c_copy.setdefault("active", bool(ch.get("active_1977", True)))
            c_copy.setdefault("office", ch.get("initial_office_1977"))
            self.characters[cid] = c_copy
            if cid not in self.params["relation"]:
                self.params["relation"][cid] = float(ch.get("initial_relation", 50.0))
            if cid not in self.params["health"]:
                self.params["health"][cid] = float(ch.get("initial_health", 80.0))
            if cid not in self.params["character_stress"]:
                self.params["character_stress"][cid] = float(ch.get("initial_stress", 20.0))
            if c_copy.get("office") and c_copy["office"] not in self.offices:
                self.offices[c_copy["office"]] = cid

        self.params["favor_character"] = {cid: 0.0 for cid in self.characters}

        # 4. Initialize Parliament (M03) & Party/Promises/Vision (M04)
        self.parliament = copy.deepcopy(snap.get("parliament", bundle.get("M03", {}).get("parliament", {})))
        self.corridors = copy.deepcopy(snap.get("corridors", self.registry.party_corridors))
        self.party_state = copy.deepcopy(snap.get("party_state", bundle.get("M04", {}).get("party_state", {})))
        self.promises = copy.deepcopy(snap.get("promises", bundle.get("M04", {}).get("promises", [])))
        self.leader_goal_packs = copy.deepcopy(
            snap.get("leader_goal_packs", bundle.get("M04", {}).get("leader_goal_packs", {}))
        )
        self.vision = copy.deepcopy(snap.get("vision", self.registry.vision_begin_raw.get("vision", {})))
        if not self.vision and "id" in self.registry.vision_begin_raw:
            self.vision = copy.deepcopy(self.registry.vision_begin_raw)

        # Ensure coalition_seats and favor_party are synced
        if "coalition_seats" in self.parliament:
            self.params["coalition_seats"] = float(self.parliament["coalition_seats"])
        self.params.setdefault("favor_party", {})
        for p in self.registry.entities.get("parties", []):
            self.params["favor_party"].setdefault(p, 0.0)

        # 5. Initialize Flags & Modifiers from snapshot
        init_flags_raw = snap.get("initial_flags", {})
        if isinstance(init_flags_raw, dict):
            for fid, f_entry in init_flags_raw.items():
                f_dict = f_entry if isinstance(f_entry, dict) else {}
                self.flags[str(fid)] = {
                    "set_day": int(f_dict.get("set_day", 0)),
                    "expires_day": f_dict.get("expires_day"),
                    "source": str(f_dict.get("source", "scenario")),
                    "value": int(f_dict.get("value", 1)),
                }
        elif isinstance(init_flags_raw, list):
            for f_entry in init_flags_raw:
                if isinstance(f_entry, dict) and "id" in f_entry:
                    self.flags[f_entry["id"]] = {
                        "set_day": int(f_entry.get("set_day", 0)),
                        "expires_day": f_entry.get("expires_day"),
                        "source": str(f_entry.get("source", "scenario")),
                        "value": int(f_entry.get("value", 1)),
                    }
        # Also set likud_in_government alias flag if likud_in_power is set
        if "likud_in_power" in self.flags and "likud_in_government" not in self.flags:
            self.flags["likud_in_government"] = copy.deepcopy(self.flags["likud_in_power"])

        for m_entry in snap.get("initial_modifiers", []):
            if isinstance(m_entry, dict):
                def_id = m_entry.get("def_id") or m_entry.get("id")
                if def_id:
                    uid = int(m_entry.get("uid", self.next_modifier_uid))
                    self.next_modifier_uid = max(self.next_modifier_uid, uid + 1)
                    self.modifiers.append({
                        "uid": uid,
                        "def_id": str(def_id),
                        "scope_key": str(m_entry.get("scope_key", "")),
                        "stacks": int(m_entry.get("stacks", 1)),
                        "start_day": int(m_entry.get("start_day", 0)),
                        "end_day": int(m_entry.get("end_day", -1)),
                        "source": str(m_entry.get("source", "scenario")),
                    })

        # 6. Initialize Regions (M11) from data/regions.yaml
        self._init_m11_regions()

        # 7. Initialize World Diplomacy (M07) from data/world_tracks.yaml
        self._init_m07_world()

        # 8. Initialize Palestine Factions (M08) from data/palestine_factions.yaml
        self._init_m08_palestine()

        # 9. Initialize Military (M09), Economy (M10), Events (M12), Authoritarian (M13), Endings (M14)
        self._init_m05_actions()
        self._init_m09_military()
        self._init_m10_economy()
        self._init_m12_events()
        self._init_m13_authoritarian()
        self._init_m14_endings(world_variant_mode)

        # 10. Initialize CausalNet 24-month history & thresholds (M02)
        self._init_m02_causal_state()

    def _init_m11_regions(self) -> None:
        regions_data = self.registry.regions_raw.get("regions", {})
        key_sites_data = self.registry.regions_raw.get("key_sites", {})
        overlays_data = self.registry.regions_raw.get("planning_overlays", {})

        regions_state: Dict[str, Dict[str, Any]] = {}
        self.params.setdefault("region_population", {})
        self.params.setdefault("settler_population", {})
        self.params.setdefault("region_absorption_priority", {})
        self.params.setdefault("region_investment_priority", {})
        self.params.setdefault("region_security_posture", {})
        self.params.setdefault("region_vote_share", {})

        if isinstance(regions_data, list):
            r_iter = [(r["id"], r) for r in regions_data if isinstance(r, dict) and "id" in r]
        elif isinstance(regions_data, dict):
            r_iter = list(regions_data.items())
        else:
            r_iter = []

        for rid, rdef in r_iter:
            canon_id = resolve_region_id(rid)
            r_copy = copy.deepcopy(rdef)
            r_copy["region_id"] = canon_id
            r_copy.setdefault("exists", bool(rdef.get("exists_1977", canon_id != "south_lebanon")))
            pop_groups = rdef.get("pop_by_group_1977", rdef.get("pop_by_group", {}))
            if isinstance(pop_groups, dict) and pop_groups:
                total_pop = int(sum(int(v) for v in pop_groups.values()))
            else:
                total_pop = int(rdef.get("region_population", rdef.get("population_1977", 250000)))
            settler_pop = int(rdef.get("settler_population_1977", rdef.get("settler_population", 0)))
            r_copy["region_population"] = total_pop
            r_copy["settler_population"] = settler_pop
            regions_state[canon_id] = r_copy

            self.params["region_population"][canon_id] = float(total_pop)
            self.params["settler_population"][canon_id] = float(settler_pop)
            self.params["region_absorption_priority"][canon_id] = float(
                rdef.get("region_absorption_priority", 50.0)
            )
            self.params["region_investment_priority"][canon_id] = float(
                rdef.get("region_investment_priority", 50.0)
            )
            self.params["region_security_posture"][canon_id] = float(
                rdef.get("region_security_posture", 50.0)
            )
            self.params["region_vote_share"][canon_id] = float(
                rdef.get("region_vote_share", 40.0)
            )

        # Ensure all 11 canonical regions exist in state.m11
        default_pops = {
            "galilee": 560000,
            "haifa": 540000,
            "tel_aviv": 1220000,
            "triangle": 510000,
            "jerusalem": 420000,
            "negev": 410000,
            "west_bank": 705000,
            "gaza": 450000,
            "golan": 15000,
            "sinai": 65000,
            "south_lebanon": 120000,
        }
        default_settlers = {
            "galilee": 0,
            "haifa": 0,
            "tel_aviv": 0,
            "triangle": 0,
            "jerusalem": 42000,
            "negev": 0,
            "west_bank": 5000,
            "gaza": 500,
            "golan": 2500,
            "sinai": 3500,
            "south_lebanon": 0,
        }
        for rid, dpop in default_pops.items():
            if rid not in regions_state:
                regions_state[rid] = {
                    "region_id": rid,
                    "exists": rid != "south_lebanon",
                    "region_type": "dynamic" if rid in ("west_bank", "gaza", "golan", "sinai", "south_lebanon") else "fixed",
                    "is_border": rid in ("galilee", "golan", "west_bank", "gaza", "sinai", "south_lebanon", "jerusalem"),
                    "legal_status": "occupied_military" if rid in ("west_bank", "gaza", "golan", "sinai") else "sovereign",
                    "region_population": dpop,
                    "settler_population": default_settlers.get(rid, 0),
                }
            self.params["region_population"].setdefault(rid, float(dpop))
            self.params["settler_population"].setdefault(rid, float(default_settlers.get(rid, 0)))
            self.params["region_absorption_priority"].setdefault(rid, 50.0)
            self.params["region_investment_priority"].setdefault(rid, 50.0)
            self.params["region_security_posture"].setdefault(rid, 50.0)
            self.params["region_vote_share"].setdefault(rid, 40.0)

        self.m11 = {
            "regions": regions_state,
            "key_sites": copy.deepcopy(key_sites_data) if isinstance(key_sites_data, (dict, list)) else {},
            "planning_overlays": copy.deepcopy(overlays_data) if isinstance(overlays_data, (dict, list)) else {},
            "active_overlay": "allon_plan",
        }

    def _init_m07_world(self) -> None:
        wt = self.registry.world_tracks_raw
        country_tracks = wt.get("country_tracks", wt.get("countries", {}))
        countries_state: Dict[str, Dict[str, Any]] = {}

        default_countries = {
            "usa": {"relation": 58.0, "stability": 78.0, "war_readiness": 85.0, "nuclear_progress": 100.0, "peace_treaty_state": 3, "category": "superpower"},
            "ussr": {"relation": 15.0, "stability": 82.0, "war_readiness": 90.0, "nuclear_progress": 100.0, "peace_treaty_state": 0, "category": "superpower"},
            "egypt": {"relation": 42.0, "stability": 52.0, "war_readiness": 62.0, "nuclear_progress": 0.0, "peace_treaty_state": 1, "category": "arab_frontline"},
            "jordan": {"relation": 45.0, "stability": 64.0, "war_readiness": 48.0, "nuclear_progress": 0.0, "peace_treaty_state": 1, "category": "arab_frontline"},
            "syria": {"relation": 15.0, "stability": 68.0, "war_readiness": 76.0, "nuclear_progress": 0.0, "peace_treaty_state": 1, "category": "arab_frontline"},
            "lebanon": {"relation": 40.0, "stability": 25.0, "war_readiness": 20.0, "nuclear_progress": 0.0, "peace_treaty_state": 1, "category": "arab_frontline"},
            "iraq": {"relation": 10.0, "stability": 72.0, "war_readiness": 70.0, "nuclear_progress": 35.0, "peace_treaty_state": 0, "category": "arab_frontline"},
            "iran": {"relation": 90.0, "stability": 48.0, "war_readiness": 65.0, "nuclear_progress": 5.0, "peace_treaty_state": 2, "category": "peripheral"},
            "saudi": {"relation": 20.0, "stability": 80.0, "war_readiness": 45.0, "nuclear_progress": 0.0, "peace_treaty_state": 0, "category": "arab_gulf"},
            "france": {"relation": 45.0, "stability": 76.0, "war_readiness": 72.0, "nuclear_progress": 100.0, "peace_treaty_state": 3, "category": "great_power"},
            "uk": {"relation": 52.0, "stability": 72.0, "war_readiness": 70.0, "nuclear_progress": 100.0, "peace_treaty_state": 3, "category": "great_power"},
            "un": {"relation": 38.0, "stability": 80.0, "war_readiness": 0.0, "nuclear_progress": 0.0, "peace_treaty_state": 1, "category": "international_org"},
            "west_germany": {"relation": 65.0, "stability": 82.0, "war_readiness": 68.0, "nuclear_progress": 0.0, "peace_treaty_state": 3, "category": "great_power"},
            "diaspora": {"relation": 72.0, "stability": 85.0, "war_readiness": 0.0, "nuclear_progress": 0.0, "peace_treaty_state": 3, "category": "diaspora"},
            "turkey": {"relation": 55.0, "stability": 50.0, "war_readiness": 60.0, "nuclear_progress": 0.0, "peace_treaty_state": 2, "category": "peripheral"},
            "ethiopia": {"relation": 48.0, "stability": 38.0, "war_readiness": 55.0, "nuclear_progress": 0.0, "peace_treaty_state": 1, "category": "peripheral"},
            "sudan": {"relation": 35.0, "stability": 46.0, "war_readiness": 35.0, "nuclear_progress": 0.0, "peace_treaty_state": 0, "category": "peripheral"},
            "morocco": {"relation": 62.0, "stability": 70.0, "war_readiness": 45.0, "nuclear_progress": 0.0, "peace_treaty_state": 1, "category": "peripheral"},
        }

        for cid, dvals in default_countries.items():
            tdef = country_tracks.get(cid, {}) if isinstance(country_tracks, dict) else {}
            countries_state[cid] = {
                "id": cid,
                "category": tdef.get("category", dvals["category"]),
                "relation": float(dvals["relation"]),
                "stability": float(dvals["stability"]),
                "war_readiness": float(dvals["war_readiness"]),
                "nuclear_progress": float(dvals["nuclear_progress"]),
                "peace_treaty_state": int(dvals["peace_treaty_state"]),
                "delta_perm": {"relation": 0.0, "stability": 0.0, "war_readiness": 0.0, "nuclear_progress": 0.0},
                "reversion_lambda": copy.deepcopy(
                    tdef.get("reversion_lambda", {"relation": 0.02, "stability": 0.03, "war_readiness": 0.04, "nuclear_progress": 0.0})
                ),
                "secret_channel_open": cid == "morocco",
                "embargo_active": False,
            }

        self.m07 = {
            "version": 1,
            "countries": countries_state,
            "us_politics": {
                "president_id": "carter",
                "president_party": "democrat",
                "admin_archetype": "human_rights_mediator",
                "admin_baseline": 55.0,
                "congress_baseline": 65.0,
                "aipac_leverage": 62.0,
                "arms_license_tier": 2,
                "arms_suspension_days": 0,
                "annual_military_aid": 1.80,
                "annual_economic_aid": 0.80,
                "loan_guarantee_state": "none",
                "strategic_memo_active": False,
            },
            "active_negotiation": None,
            "crisis_timers": [],
            "immigration_breakdown": {
                "ussr": 8500.0,
                "ethiopia": 120.0,
                "western": 6800.0,
                "mena_latam": 5580.0,
                "pulse_bonus": 0.0,
            },
            "nuclear_intel": {
                "iraq": {"country": "iraq", "true_progress": 35.0, "reported_band": "early_research", "estimated_months_to_100": 45, "strike_window_open": False},
                "iran": {"country": "iran", "true_progress": 5.0, "reported_band": "dormant", "estimated_months_to_100": 120, "strike_window_open": False},
            },
            "ai_action_log": [],
        }

        # Populate war_probability in params
        self.params.setdefault("war_probability", {})
        for c in ("egypt", "jordan", "syria", "lebanon", "iraq", "saudi", "iran"):
            self.params["war_probability"].setdefault(c, 15.0)

    def _init_m08_palestine(self) -> None:
        self.m08 = {
            "faction_active": {
                "fatah": True,
                "pflp": True,
                "jordan_notables": True,
                "local_mayors": True,
                "village_leagues": False,
                "mujama": True,
                "hamas": False,
                "pij": False,
                "pa_security": False,
            },
            "faction_meta": {},
            "autonomy_track": {
                "stage": "NONE",
                "modality": "NONE",
                "stagnation_months": 0,
                "implementation_hold_months": 0,
                "delegation_active_days": 0,
            },
            "uprising_state": {
                "active": False,
                "intensity": 0.0,
                "duration_months": 0,
                "calm_streak_months": 0,
                "cumulative_repression_impulse": 0.0,
                "unlu_formed": False,
            },
            "ai_action_log": [],
        }
        for fid in self.m08["faction_active"]:
            self.m08["faction_meta"][fid] = {
                "overt_support_level": 0.0,
                "covert_funding_months": 0,
                "patron_flow_last": 0.0,
                "last_ai_action": "",
                "last_ai_reason_zh": "",
                "ai_cooldowns": {},
            }

    def _init_m05_actions(self) -> None:
        self.m05 = {
            "weekly_slots_used": 0,
            "weekly_slots_max": 2,
            "action_cooldowns": {},
            "active_actions": [],
            "completed_actions": {},
            "iou_ledger": [],
            "iou_incurred_total": 0,
        }

    def _init_m09_military(self) -> None:
        self.m09 = {
            "mobilization_target": 10.0,
            "intel_accuracy": 79.65,
            "peace_months_streak": 44,
            "last_ceasefire_date": "1974-05-31",
            "wartime_fiscal_acc": 0.0,
            "atrocity_risk_multipliers": {},
            "fronts": {
                "egypt": {"front_id": "egypt", "status": "PEACE", "border_friction": 15.0, "roe_level": 1, "local_militia_allied": None, "security_zone_active": False, "quagmire_months": 0, "active_war": None},
                "jordan": {"front_id": "jordan", "status": "PEACE", "border_friction": 10.0, "roe_level": 1, "local_militia_allied": None, "security_zone_active": False, "quagmire_months": 0, "active_war": None},
                "syria": {"front_id": "syria", "status": "PEACE", "border_friction": 25.0, "roe_level": 1, "local_militia_allied": None, "security_zone_active": False, "quagmire_months": 0, "active_war": None},
                "lebanon": {"front_id": "lebanon", "status": "BORDER_FRICTION", "border_friction": 55.0, "roe_level": 1, "local_militia_allied": "sla", "security_zone_active": False, "quagmire_months": 0, "active_war": None},
                "gaza": {"front_id": "gaza", "status": "PEACE", "border_friction": 22.0, "roe_level": 1, "local_militia_allied": None, "security_zone_active": False, "quagmire_months": 0, "active_war": None},
                "internal": {"front_id": "internal", "status": "PEACE", "border_friction": 18.0, "roe_level": 1, "local_militia_allied": None, "security_zone_active": False, "quagmire_months": 0, "active_war": None},
            },
            "intel_reports": {},
            "nuclear": {
                "arsenal_tier": 2,
                "alert_active": False,
                "alert_cooldown_days": 0,
                "vanunu_leaked": False,
                "lakam_active": True,
            },
        }
        self.params["intel_accuracy"] = 79.65

    def _init_m10_economy(self) -> None:
        enacted = copy.deepcopy(self.params.get("budget_slider", {
            "defense": 65.0,
            "absorption": 45.0,
            "religion": 40.0,
            "dev_towns": 40.0,
            "education": 50.0,
            "welfare": 55.0,
            "infrastructure": 50.0,
            "settlements": 35.0,
        }))
        self.m10 = {
            "expected_inflation": 35.0,
            "real_gdp_index": 100.0,
            "cumulative_deficit_stock": 40.0,
            "external_inflation_shock": 0.0,
            "wage_erosion_index": 20.0,
            "strike_cooldown_months": 0,
            "active_strike_tier": 0,
            "stabilization_plan_active": False,
            "stabilization_months_left": 0,
            "bank_bailout_committed": False,
            "last_fiscal_ledger": {
                "tax_revenue": 7.828,
                "us_aid_grant": 0.600,
                "slider_expenditure": 8.712,
                "debt_service": 0.960,
                "tanzi_erosion": 0.700,
                "m05_policy_delta": -0.056,
                "one_off_flow": 0.000,
                "net_balance": -2.000,
            },
            "budget_cycle": {
                "fiscal_year": 1977,
                "status": "PASSED",
                "opened_day": 0,
                "deadline_day": 90,
                "active_bill_uid": None,
                "warning_60d_emitted": False,
                "enacted_sliders": enacted,
                "draft_sliders": copy.deepcopy(enacted),
                "rejection_count_this_year": 0,
            },
            "aliyah_cohorts": [],
        }

    def _init_m12_events(self) -> None:
        status_map: Dict[str, str] = {}
        for ev in self.registry.fixed_events:
            status_map[ev["id"]] = "LOCKED"
        self.m12 = {
            "status": status_map,
            "fired": {},
            "counts_game": {},
            "counts_term": {},
            "cooldown_until": {},
            "blocked_until": {},
            "multipliers": {},
            "variant_history": {},
            "window_extended": {},
            "scheduled": [],
            "queue": [],
            "cabinet_folder": [],
            "month_plan": [],
            "month_forced_count": 0,
            "month_random_count": 0,
            "month_had_war": False,
            "last_major_date": None,
            "popup_total": 0,
            "days_since_last_popup": 0,
            "seq_counter": 0,
            "advisor_handles_minor": True,
        }

    def _init_m13_authoritarian(self) -> None:
        self.m13 = {
            "stage": 0,
            "months_since_auth_action": 12,
            "auth_actions_taken_total": 0,
            "postpone_election_count": 0,
            "override_clause_enacted": False,
            "judicial_committee_packed": False,
            "ag_subordinated": False,
            "security_chiefs_purged": False,
            "survival_mode_active": False,
            "survival_months": 0,
            "regime_control": 100.0,
            "sanction_tier": 0,
            "protest_tier": 0,
            "protest_tier_months": 0,
            "reservist_refusal_rate": 0.0,
            "right_extremism_heat": 10.0,
            "anti_regime_heat": 0.0,
            "coup_warning_issued": False,
            "assassination_warning_issued": False,
            "resist_actors": {
                "supreme_court": {"id": "supreme_court", "zh": "最高法院", "tension": 10.0, "autonomy": 85.0, "threshold": 45.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "attorney_general": {"id": "attorney_general", "zh": "总检察长", "tension": 12.0, "autonomy": 88.0, "threshold": 40.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "idf_command": {"id": "idf_command", "zh": "国防军总参谋部", "tension": 8.0, "autonomy": 85.0, "threshold": 55.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "reservists": {"id": "reservists", "zh": "预备役军官团", "tension": 5.0, "autonomy": 90.0, "threshold": 50.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "histadrut": {"id": "histadrut", "zh": "劳工总联合会", "tension": 25.0, "autonomy": 80.0, "threshold": 48.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "independent_media": {"id": "independent_media", "zh": "独立报刊", "tension": 15.0, "autonomy": 78.0, "threshold": 42.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "coalition_allies": {"id": "coalition_allies", "zh": "执政联盟温和伙伴", "tension": 14.0, "autonomy": 75.0, "threshold": 46.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "us_institutions": {"id": "us_institutions", "zh": "美国国会与白宫", "tension": 10.0, "autonomy": 100.0, "threshold": 52.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
                "party_constitutionalists": {"id": "party_constitutionalists", "zh": "党内宪政派", "tension": 10.0, "autonomy": 72.0, "threshold": 44.0, "stance": "dormant", "cooldown_months": 0, "strikes_count": 0},
            },
        }
        self.params["coup_risk"] = 0.0
        self.params["assassination_risk"] = 2.0
        self.params["social_protest_tier"] = 0.0

    def _init_m14_endings(self, world_variant_mode: str) -> None:
        self.m14 = {
            "version": 1,
            "scenario_id": self.scenario_id,
            "world_variant_mode": world_variant_mode,
            "fictional_leader_counter": 0,
            "collapse_danger_streak_days": 0,
            "tenure_start_snapshot": {
                "deterrence": float(self.get_param("deterrence")),
                "inflation": float(self.get_param("inflation")),
                "rule_of_law": float(self.get_param("rule_of_law")),
                "economic_model": float(self.get_param("economic_model")),
                "settler_total": float(self.settler_population_total()),
            },
            "corridor_months_total": 0,
            "corridor_months_inside": 0,
            "peak_inflation_tenure": float(self.get_param("inflation")),
            "peak_centralization_tenure": float(self.get_param("centralization")),
            "min_fx_tenure": float(self.get_param("fx_reserves")),
            "consecutive_months_61_seats": 0,
            "sharon_in_cabinet_months": 0,
            "overreach_count_sharon": 0,
            "wars_fought_tenure": [],
            "treaties_signed_tenure": [],
            "unlocked_achievements_this_run": [],
            "tenure_reports": [],
            "cross_era_summary": None,
        }

    def _init_m02_causal_state(self) -> None:
        # Initialize 24-month history for every node to its initial value (zero-drift guarantee)
        hist: Dict[str, List[float]] = {}
        for node_key in self.registry.node_configs:
            val = self.read_node_value(node_key)
            hist[node_key] = [val] * 24
        # Also initialize key parameters that edges may reference with lag
        for pid, pval in self.params.items():
            if isinstance(pval, (int, float)):
                hist.setdefault(pid, [float(pval)] * 24)
            elif isinstance(pval, dict):
                for k, v in pval.items():
                    hist.setdefault(f"{pid}[{k}]", [float(v)] * 24)
        self.m02["history_24m"] = hist

        # Initialize threshold states from data/thresholds.yaml
        thr_states: Dict[str, Dict[str, Any]] = {}
        for tdef in self.registry.thresholds:
            tid = tdef["id"]
            thr_states[tid] = {
                "id": tid,
                "state": "off",
                "hold_Counter": 0,
                "cooldown_months": 0,
                "times_activated": 0,
            }
        self.m02["thresholds"] = thr_states

    def recompute_gov_axis_position(self) -> Dict[str, float]:
        """Compute 5-axis gov_axis_position from current policy levels and axis_impulse (M05 §4.9.4)."""
        axes = ("territory", "security", "economy", "religion", "foreign")
        totals = {ax: 0.0 for ax in axes}
        for pol_id, pol_def in self.registry.policies.items():
            ax_map = pol_def.get("ax", {})
            if not isinstance(ax_map, dict) or not ax_map:
                continue
            v = float(self.policies.get(pol_id, {}).get("level", 0.0))
            tiers = pol_def.get("tiers", [])
            tier_vals = [float(t["v"] if isinstance(t, dict) else t) for t in tiers] if tiers else [0.0, 100.0]
            min_v = min(tier_vals) if tier_vals else 0.0
            max_v = max(tier_vals) if tier_vals else 100.0
            default_n = 0.0 if min_v < 0.0 else 50.0
            n = float(pol_def.get("n", default_n))
            if v >= n:
                denom = max(1.0, max_v - n)
                rel = (v - n) / denom
            else:
                denom = max(1.0, n - min_v)
                rel = (v - n) / denom
            for ax, weight in ax_map.items():
                if ax in totals:
                    totals[ax] += float(weight) * rel
        for ax in axes:
            imp = clamp(float(self.axis_impulse.get(ax, 0.0)), -18.0, 18.0)
            self.axis_impulse[ax] = quantize(imp)
            self.gov_axis_position[ax] = quantize(clamp(totals[ax] + imp, -100.0, 100.0))
        self.params["gov_axis_position"] = dict(self.gov_axis_position)
        return self.gov_axis_position

    def m05_policy_fiscal_delta(self) -> float:
        """Compute monthly structural fiscal delta from active policy tiers vs 1977 baseline (M10 §4.2.1)."""
        delta_annual = 0.0
        for pol_id, pol_def in self.registry.policies.items():
            tiers = pol_def.get("tiers", [])
            if not tiers:
                continue
            start_raw = pol_def.get("start", {}).get("begin_1977", 0)
            if isinstance(start_raw, dict):
                start_raw = next(iter(start_raw.values()), 0)
            if isinstance(start_raw, bool):
                start_idx = 1 if start_raw else 0
            elif isinstance(start_raw, (int, float)):
                start_idx = int(start_raw)
            else:
                start_idx = 0
            cur_idx = int(self.policies.get(pol_id, {}).get("tier_idx", start_idx))
            f0 = float(tiers[start_idx].get("f", 0.0)) if 0 <= start_idx < len(tiers) and isinstance(tiers[start_idx], dict) else 0.0
            f_cur = float(tiers[cur_idx].get("f", 0.0)) if 0 <= cur_idx < len(tiers) and isinstance(tiers[cur_idx], dict) else 0.0
            delta_annual -= (f_cur - f0)
        return quantize(-0.056 + delta_annual / 12.0)

    # ------------------------------------------------------------------
    # Office / Character / Region / Entity Queries
    # ------------------------------------------------------------------

    def holder_of(self, office_id: str) -> Optional[str]:
        canon_off = OFFICE_ALIAS_MAP.get(office_id, office_id)
        if canon_off == "prime_minister":
            return self.player.get("leader_id", "begin")
        holder = self.offices.get(canon_off)
        if holder:
            return holder
        # Fallback search in characters
        for cid, ch in self.characters.items():
            if ch.get("office") == canon_off and ch.get("alive", True):
                return cid
        return None

    def is_character_in_office(self, char_id: str) -> bool:
        # Foreign heads of state
        if char_id == "sadat":
            return self.date_str <= "1981-10-06" and not self.has_flag("sadat_assassinated") and not ("E-1981-10" in self.m12.get("fired", {}))
        if char_id == "mubarak":
            return self.date_str > "1981-10-06" or self.has_flag("sadat_assassinated") or ("E-1981-10" in self.m12.get("fired", {}))
        if char_id in ("hussein_king", "hussein"):
            return True
        if char_id == "assad_hafez":
            return True
        if char_id == "arafat":
            return True
        if char_id == "saddam":
            return True
        if char_id == "mengistu":
            return self.date_str <= "1991-05-28"
        if char_id == "shah_pahlavi":
            return self.date_str <= "1979-03-01" and not ("E-1979-02" in self.m12.get("fired", {}))
        if char_id == "bashir_gemayel":
            return "1982-01-01" <= self.date_str <= "1983-12-31" and not ("E-1982-09a" in self.m12.get("fired", {}))
        if char_id == "numayri":
            return self.date_str <= "1985-06-30"
        if char_id == "carter":
            return self.m07.get("us_politics", {}).get("president_id") == "carter"
        if char_id == "reagan":
            return self.m07.get("us_politics", {}).get("president_id") == "reagan"
        if char_id == "bush_sr":
            return self.m07.get("us_politics", {}).get("president_id") == "bush_sr"
        if char_id == "clinton":
            return self.m07.get("us_politics", {}).get("president_id") == "clinton"

        # Office alias check
        if char_id in OFFICE_ALIAS_MAP:
            return self.holder_of(char_id) is not None

        if self.player.get("leader_id") == char_id:
            return True
        if char_id in self.offices.values():
            return True
        ch = self.characters.get(char_id)
        if ch and ch.get("alive", True) and ch.get("office"):
            return True
        return False

    def is_character_alive(self, char_id: str) -> bool:
        if char_id == "sadat":
            return self.date_str <= "1981-10-06" and not self.has_flag("sadat_assassinated") and not ("E-1981-10" in self.m12.get("fired", {}))
        if char_id == "aliza_begin":
            return not ("E-1982-11" in self.m12.get("fired", {}))
        ch = self.characters.get(char_id)
        if ch is not None:
            return bool(ch.get("alive", True))
        return True

    def region_exists(self, region_id: str) -> bool:
        canon = resolve_region_id(region_id)
        r = self.m11.get("regions", {}).get(canon)
        if r is not None:
            return bool(r.get("exists", True))
        return canon != "south_lebanon"

    def at_war(self, country_or_front: Optional[str] = None) -> bool:
        fronts = self.m09.get("fronts", {})
        if not country_or_front:
            for f in fronts.values():
                if f.get("status") in ("FULL_WAR", "LIMITED_OP") or f.get("active_war") is not None:
                    return True
            return False
        f = fronts.get(country_or_front)
        if f is not None:
            return f.get("status") in ("FULL_WAR", "LIMITED_OP") or f.get("active_war") is not None
        return False

    def count_peace_treaties(self) -> int:
        pts = self.params.get("peace_treaty_state", {})
        count = 0
        for c in ("egypt", "jordan", "syria", "lebanon", "saudi"):
            if int(pts.get(c, 0)) >= 3:
                count += 1
        return count

    def settler_population_total(self) -> int:
        sp = self.params.get("settler_population", {})
        total = 0
        for r in ("jerusalem", "west_bank", "gaza", "golan", "sinai"):
            if self.region_exists(r):
                total += int(sp.get(r, 0))
        return total

    def party_has_tag(self, party_id: str, tag: str) -> bool:
        canon = resolve_party_id(party_id)
        p_info = self.parliament.get("parties", {}).get(canon, {})
        tags = p_info.get("tags", [])
        if tag in tags:
            return True
        # Static fallback tags for Israeli parties
        static_tags = {
            "labor": ["labor_union", "secular", "dovish", "zionist"],
            "mapam": ["labor_union", "secular", "dovish", "left", "zionist"],
            "likud": ["right", "hawkish", "zionist"],
            "nrp": ["religious", "religious_zionist", "zionist"],
            "agudat": ["religious", "haredi", "non_zionist"],
            "shas": ["religious", "haredi", "mizrahi"],
            "dash": ["centrist", "secular", "liberal", "zionist"],
            "shinui": ["centrist", "secular", "liberal", "zionist"],
            "ratz": ["left", "secular", "dovish", "civil_rights", "zionist"],
            "tehiya": ["far_right", "hawkish", "settler", "zionist"],
            "rakah_hadash": ["arab", "communist", "non_zionist"],
        }
        return tag in static_tags.get(canon, [])

    # ------------------------------------------------------------------
    # Parameter Access & Alias Resolution
    # ------------------------------------------------------------------

    def _normalize_param_and_key(self, param_id: str, key: Optional[str] = None) -> Tuple[str, Optional[str]]:
        # Check bracket syntax if caller passed "param[key]" as param_id
        if key is None and "[" in param_id and param_id.endswith("]"):
            idx = param_id.index("[")
            key = param_id[idx + 1 : -1].strip()
            param_id = param_id[:idx].strip()

        canon_param = PARAM_ALIAS_MAP.get(param_id, param_id)
        if key is None:
            return canon_param, None

        k = str(key).strip()
        if canon_param in ("region_security", "region_development", "region_population", "settler_population",
                           "region_land_policy", "settlement_policy", "region_absorption_priority",
                           "region_investment_priority", "region_security_posture", "region_vote_share"):
            k = resolve_region_id(k)
        elif canon_param in ("faction_strength", "faction_legitimacy", "faction_moderation",
                             "faction_cohesion", "collaborator_stigma"):
            k = resolve_faction_id(k)
        elif canon_param in ("ally_satisfaction", "favor_party", "knesset_seats"):
            k = resolve_party_id(k)
        elif canon_param == "bloc_support" or canon_param == "promise_credit":
            k = resolve_bloc_id(k)
        elif canon_param == "promise_progress":
            k = PROMISE_ALIAS_MAP.get(k, k)
        elif canon_param in ("relation", "health", "character_stress", "favor_character"):
            if k in OFFICE_ALIAS_MAP and k not in self.characters:
                holder = self.holder_of(k)
                k = holder if holder else k
        return canon_param, k

    def get_param_range(self, param_id: str) -> Tuple[float, float]:
        canon_param = PARAM_ALIAS_MAP.get(param_id, param_id)
        pdef = self.registry.param_defs.get(canon_param)
        if pdef and "range" in pdef:
            r = pdef["range"]
            return float(r[0]), float(r[1])
        if canon_param in ("economic_model", "religious_status_quo", "historical_rating"):
            return -100.0, 100.0
        if canon_param == "relation":
            return -100.0, 100.0
        if canon_param == "budget_balance":
            return -50.0, 50.0
        if canon_param == "public_debt":
            return 0.0, 300.0
        if canon_param == "inflation":
            return -5.0, 500.0
        if canon_param == "growth":
            return -15.0, 20.0
        if canon_param == "unemployment":
            return 0.0, 40.0
        if canon_param == "political_capital":
            return 0.0, 200.0
        if canon_param == "coalition_seats":
            return 0.0, 120.0
        if canon_param in ("immigration_inflow", "region_population", "settler_population"):
            return 0.0, 10_000_000.0
        return 0.0, 100.0

    def get_param(self, param_id: str, key: Optional[str] = None) -> float:
        canon_param, k = self._normalize_param_and_key(param_id, key)

        # Special routing for country_relation[c]
        if canon_param == "country_relation":
            if k == "usa":
                return float(self.params.get("us_admin_relation", 58.0))
            powers = self.params.get("power_relation", {})
            if k in powers:
                return float(powers[k])
            rh = self.params.get("regime_hostility", {})
            if k in rh:
                return 100.0 - float(rh[k])
            c_obj = self.m07.get("countries", {}).get(k or "")
            if c_obj:
                return float(c_obj.get("relation", 50.0))
            return 50.0

        # Special routing for policy_level[pol]
        if canon_param == "policy_level":
            if k and k in self.policies:
                return float(self.policies[k]["level"])
            pl = self.params.get("policy_level", {})
            if isinstance(pl, dict) and k in pl:
                return float(pl[k])
            return 0.0

        # Special routing for gov_axis_position[axis]
        if canon_param == "gov_axis_position":
            return float(self.gov_axis_position.get(k or "territory", 0.0))

        # Special routing for promise_progress category keys (cat_economy etc.)
        if canon_param == "promise_progress" and k and k.startswith("cat_"):
            cat_name = k[4:]
            prom_map = self.params.get("promise_progress", {})
            matching = [
                float(prom_map.get(p.get("id", ""), 0.0))
                for p in self.promises
                if p.get("category") == cat_name or (cat_name == "peace" and p.get("category") == "security")
            ]
            if matching:
                return sum(matching) / len(matching)
            return 0.0

        # Special routing for peripheral_states in arab_state params
        if k == "peripheral_states" and canon_param in ("regime_hostility", "regime_stability"):
            vals = [self.get_param(canon_param, c) for c in ("iran", "turkey", "ethiopia", "morocco")]
            return sum(vals) / len(vals)

        store = self.params.get(canon_param)
        if k is None:
            if isinstance(store, (int, float)):
                return float(store)
            return 0.0
        else:
            if isinstance(store, dict):
                if k in store:
                    return float(store[k])
                # Check if character office was empty (M12 §8.1: relation is 0 when office is vacant)
                if canon_param == "relation" and key in OFFICE_ALIAS_MAP and self.holder_of(key) is None:
                    return 0.0
            # Fallback to M07 countries dict if querying stability/readiness/nuclear for peripheral/power
            if canon_param == "regime_stability":
                c_obj = self.m07.get("countries", {}).get(k)
                if c_obj:
                    return float(c_obj.get("stability", 50.0))
            if canon_param == "regime_hostility":
                c_obj = self.m07.get("countries", {}).get(k)
                if c_obj:
                    return 100.0 - float(c_obj.get("relation", 50.0))
            return 0.0

    get = get_param

    def set_param(
        self,
        param_id: str,
        value: float,
        key: Optional[str] = None,
        clamp_to_range: bool = True,
    ) -> float:
        canon_param, k = self._normalize_param_and_key(param_id, key)

        # Special routing for country_relation[c]
        if canon_param == "country_relation" and k:
            v_clamped = clamp(value, 0.0, 100.0) if clamp_to_range else float(value)
            v_clamped = quantize(v_clamped)
            if k == "usa":
                self.set_param("us_admin_relation", v_clamped, clamp_to_range=clamp_to_range)
                self.set_param("power_relation", v_clamped, key="usa", clamp_to_range=clamp_to_range)
            elif k in self.params.get("power_relation", {}):
                self.params["power_relation"][k] = v_clamped
            else:
                self.params.setdefault("regime_hostility", {})[k] = quantize(100.0 - v_clamped)
            if k in self.m07.get("countries", {}):
                self.m07["countries"][k]["relation"] = v_clamped
            return v_clamped

        # Special routing for policy_level[pol]
        if canon_param == "policy_level" and k:
            v_clamped = clamp(value, 0.0, 100.0) if clamp_to_range else float(value)
            v_clamped = quantize(v_clamped)
            if k in self.policies:
                self.policies[k]["level"] = v_clamped
                self.policies[k]["target_level"] = v_clamped
            self.params.setdefault("policy_level", {})[k] = v_clamped
            return v_clamped

        # Special routing for gov_axis_position[axis]
        if canon_param == "gov_axis_position" and k:
            v_clamped = clamp(value, -100.0, 100.0) if clamp_to_range else float(value)
            v_clamped = quantize(v_clamped)
            self.gov_axis_position[k] = v_clamped
            return v_clamped

        lo, hi = self.get_param_range(canon_param)
        v = clamp(value, lo, hi) if clamp_to_range else float(value)
        v = quantize(v)

        if k is None:
            self.params[canon_param] = v
            if canon_param == "cynicism":
                self.params["voter_cynicism"] = v
            elif canon_param == "islamic_assoc_strength":
                self.params.setdefault("faction_strength", {})["mujama"] = v
            elif canon_param == "us_admin_relation":
                self.params.setdefault("power_relation", {})["usa"] = v
                if "usa" in self.m07.get("countries", {}):
                    self.m07["countries"]["usa"]["relation"] = v
            elif canon_param == "coalition_seats":
                self.parliament["coalition_seats"] = int(round(v))
        else:
            if canon_param not in self.params or not isinstance(self.params[canon_param], dict):
                self.params[canon_param] = {}
            self.params[canon_param][k] = v

            # Synchronize invariants
            if canon_param == "faction_strength" and k == "mujama":
                self.params["islamic_assoc_strength"] = v
            elif canon_param == "power_relation" and k == "usa":
                self.params["us_admin_relation"] = v
            elif canon_param == "regime_hostility" and k in self.m07.get("countries", {}):
                self.m07["countries"][k]["relation"] = quantize(100.0 - v)
            elif canon_param == "regime_stability" and k in self.m07.get("countries", {}):
                self.m07["countries"][k]["stability"] = v
            elif canon_param == "country_war_readiness" and k in self.m07.get("countries", {}):
                self.m07["countries"][k]["war_readiness"] = v
            elif canon_param == "enemy_nuclear_progress" and k in self.m07.get("countries", {}):
                self.m07["countries"][k]["nuclear_progress"] = v
            elif canon_param == "peace_treaty_state" and k in self.m07.get("countries", {}):
                self.m07["countries"][k]["peace_treaty_state"] = int(round(v))
            elif canon_param == "budget_slider":
                self.m10.get("budget_cycle", {}).get("enacted_sliders", {})[k] = v
                self.m10.get("budget_cycle", {}).get("draft_sliders", {})[k] = v
        return v

    def add_param(self, param_id: str, delta: float, key: Optional[str] = None) -> float:
        canon_param, k = self._normalize_param_and_key(param_id, key)

        # Promise category fan-out (e.g., promise_progress[cat_economy] += delta)
        if canon_param == "promise_progress" and k and k.startswith("cat_"):
            cat_name = k[4:]
            cat_to_key = {
                "economy": "economic_liberalization",
                "peace": "peace_and_security",
                "security": "peace_and_security",
                "territory": "settle_eretz_israel",
                "social": "social_justice",
            }
            prom_map = self.params.get("promise_progress", {})
            target_k = cat_to_key.get(cat_name, "peace_and_security")
            cur = float(prom_map.get(target_k, 0.0))
            last_v = self.set_param("promise_progress", cur + delta, key=target_k)
            for p in self.promises:
                if isinstance(p, dict) and (p.get("id") == target_k or p.get("promise_id") == target_k):
                    p["progress"] = last_v
            return last_v

        if k == "peripheral_states" and canon_param in ("regime_hostility", "regime_stability"):
            last_v = 0.0
            for c in ("iran", "turkey", "ethiopia", "morocco"):
                cur = self.get_param(canon_param, c)
                last_v = self.set_param(canon_param, cur + delta, key=c)
            return last_v

        cur = self.get_param(canon_param, k)
        new_v = self.set_param(canon_param, cur + float(delta), key=k)
        if canon_param == "promise_progress" and k:
            for p in self.promises:
                if isinstance(p, dict) and (p.get("id") == k or p.get("promise_id") == k):
                    p["progress"] = new_v
        return new_v

    def mul_param(self, param_id: str, factor: float, key: Optional[str] = None) -> float:
        cur = self.get_param(param_id, key)
        return self.set_param(param_id, cur * float(factor), key=key)

    def read_node_value(self, node_key: str) -> float:
        """Read a CausalNet node key such as 'inflation' or 'alienation[mizrahi]'."""
        if "[" in node_key and node_key.endswith("]"):
            idx = node_key.index("[")
            p = node_key[:idx]
            k = node_key[idx + 1 : -1]
            return self.get_param(p, k)
        return self.get_param(node_key)

    def write_node_value(self, node_key: str, val: float) -> float:
        if "[" in node_key and node_key.endswith("]"):
            idx = node_key.index("[")
            p = node_key[:idx]
            k = node_key[idx + 1 : -1]
            return self.set_param(p, val, k)
        return self.set_param(node_key, val)

    # ------------------------------------------------------------------
    # Flags & Modifiers Management
    # ------------------------------------------------------------------

    def has_flag(self, flag_id: str) -> bool:
        if flag_id in self.flags:
            return True
        # Alias support between likud_in_power and likud_in_government
        if flag_id == "likud_in_government" and "likud_in_power" in self.flags:
            return True
        if flag_id == "likud_in_power" and "likud_in_government" in self.flags:
            return True
        if flag_id == "bank_shares_manipulation" and "bank_shares_regulation" in self.flags:
            return True
        if flag_id == "liberals_hold_finance":
            return self.holder_of("finance") in ("ehrlich", "modai", "patt")
        if flag_id == "dayan_foreign_minister":
            return ("E-1977-06" in self.m12.get("fired", {}) and self.m12["fired"]["E-1977-06"].get("choice") == "A") or (self.day_index >= 30 and self.holder_of("foreign") == "dayan")
        if flag_id == "settlers_momentum_high":
            return self.get_param("settler_momentum") >= 50.0
        if flag_id == "lakam_us_operation":
            return bool(self.m09.get("nuclear", {}).get("lakam_active", True))
        if flag_id == "first_intifada_active":
            return "intifada_active" in self.flags or self.has_modifier("first_intifada") or bool(self.m08.get("uprising_state", {}).get("active"))
        if flag_id == "world_iran_iraq_war":
            return "1980-09-22" <= self.date_str <= "1988-08-20"
        if flag_id == "world_us_refugee_quota_tightened":
            return self.date_str >= "1989-06-01"
        if flag_id == "world_gulf_war":
            return "1990-08-02" <= self.date_str <= "1991-04-30"
        if flag_id == "national_unity_government":
            return self.year >= 1984 and (self.get_param("coalition_seats") >= 75.0 or "labor" in self.parliament.get("coalition_parties", []))
        return False

    def set_flag(
        self,
        flag_id: str,
        duration_days: Optional[int] = None,
        source: str = "event",
        value: int = 1,
    ) -> None:
        exp = (self.day_index + int(duration_days)) if duration_days is not None and duration_days > 0 else None
        self.flags[str(flag_id)] = {
            "set_day": self.day_index,
            "expires_day": exp,
            "source": str(source),
            "value": int(value),
        }

    def clear_flag(self, flag_id: str) -> None:
        self.flags.pop(str(flag_id), None)

    def has_modifier(self, mod_id: str, key: Optional[str] = None) -> bool:
        for m in self.modifiers:
            if m.get("def_id") == mod_id:
                if key is None or m.get("scope_key", "") == str(key):
                    return True
        if mod_id == "indexation_spiral":
            return not self.m10.get("indexation_removed", False) and not self.m10.get("stabilization_plan_active", False) and not self.has_modifier("new_shekel")
        return False

    def add_modifier(
        self,
        mod_id: str,
        duration_days: Optional[int] = None,
        key: Optional[str] = None,
        source: str = "event",
        stacks: int = 1,
    ) -> None:
        if mod_id == "indexation_spiral":
            self.m10["indexation_removed"] = False
        if mod_id == "new_shekel":
            self.m10["indexation_removed"] = True
        scope_key = str(key) if key is not None else ""
        mdef = self.registry.modifier_defs.get(mod_id, {})
        stack_mode = mdef.get("stack_mode", mdef.get("stack", "refresh"))
        max_stacks = int(mdef.get("max_stacks", 3 if stack_mode == "stack" else 1))
        if duration_days is None:
            default_dur = mdef.get("default_duration_days")
            end_day = (self.day_index + int(default_dur)) if isinstance(default_dur, int) and default_dur > 0 else -1
        elif int(duration_days) <= 0:
            end_day = -1
        else:
            end_day = self.day_index + int(duration_days)

        for existing in self.modifiers:
            if existing.get("def_id") == mod_id and existing.get("scope_key", "") == scope_key:
                if stack_mode == "stack":
                    existing["stacks"] = min(max_stacks, int(existing.get("stacks", 1)) + int(stacks))
                existing["end_day"] = end_day
                existing["source"] = str(source)
                return

        uid = self.next_modifier_uid
        self.next_modifier_uid += 1
        self.modifiers.append({
            "uid": uid,
            "def_id": str(mod_id),
            "scope_key": scope_key,
            "stacks": min(max_stacks, max(1, int(stacks))),
            "start_day": self.day_index,
            "end_day": end_day,
            "source": str(source),
        })

    def remove_modifier(self, mod_id: str, key: Optional[str] = None) -> None:
        if mod_id == "indexation_spiral":
            self.m10["indexation_removed"] = True
        if key is None:
            self.modifiers = [m for m in self.modifiers if m.get("def_id") != mod_id]
        else:
            sk = str(key)
            self.modifiers = [
                m for m in self.modifiers
                if not (m.get("def_id") == mod_id and m.get("scope_key", "") == sk)
            ]

    def mod_factor(self, factor_key: str) -> float:
        """Compute aggregate modifier factor: (1 + sum(add_pct)) * prod(mul), clamped to [0, 5] (M01 §4.6.2)."""
        sum_add = 0.0
        prod_mul = 1.0
        for inst in self.modifiers:
            mdef = self.registry.modifier_defs.get(inst.get("def_id", ""), {})
            stacks = int(inst.get("stacks", 1))
            for f in mdef.get("factors", []) or []:
                if f.get("factor_key") == factor_key:
                    op = f.get("op", "add_pct")
                    val = float(f.get("value", 0.0))
                    if op in ("add_pct", "add_flat"):
                        sum_add += val * stacks
                    elif op == "mul":
                        prod_mul *= (val ** stacks)
        if factor_key in ("pc_income", "exec_slots"):
            # pc_income / exec_slots returns flat bonus when queried as flat or factor
            return quantize(sum_add)
        return quantize(clamp((1.0 + sum_add) * prod_mul, 0.0, 5.0))

    def mod_add(self, factor_key: str) -> float:
        """Compute aggregate additive modifier bonus for `factor_key`."""
        sum_add = 0.0
        for inst in self.modifiers:
            mdef = self.registry.modifier_defs.get(inst.get("def_id", ""), {})
            stacks = int(inst.get("stacks", 1))
            for f in mdef.get("factors", []) or []:
                if f.get("factor_key") == factor_key and f.get("op", "add_pct") in ("add_pct", "add_flat", "add"):
                    sum_add += float(f.get("value", 0.0)) * stacks
            mod_dict = mdef.get("mod", {})
            if isinstance(mod_dict, dict) and factor_key in mod_dict:
                sum_add += float(mod_dict[factor_key]) * stacks
        return quantize(sum_add)

    # ------------------------------------------------------------------
    # Serialization & Hashing
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "meta": copy.deepcopy(self.meta),
            "run": copy.deepcopy(self.run),
            "player": copy.deepcopy(self.player),
            "calendar": {
                "start_date": self.start_date,
                "start_abs_day": self.start_abs_day,
                "day_index": self.day_index,
                "abs_day": self.abs_day,
                "date_str": self.date_str,
                "year": self.year,
                "month": self.month,
                "day": self.day,
                "weekday": self.weekday,
            },
            "rng": self.rng.to_dict(),
            "params": copy.deepcopy(self.params),
            "flags": copy.deepcopy(self.flags),
            "modifiers": copy.deepcopy(self.modifiers),
            "next_modifier_uid": self.next_modifier_uid,
            "policies": copy.deepcopy(self.policies),
            "gov_axis_position": copy.deepcopy(self.gov_axis_position),
            "axis_impulse": copy.deepcopy(self.axis_impulse),
            "characters": copy.deepcopy(self.characters),
            "offices": copy.deepcopy(self.offices),
            "parliament": copy.deepcopy(self.parliament),
            "corridors": copy.deepcopy(self.corridors),
            "party_state": copy.deepcopy(self.party_state),
            "promises": copy.deepcopy(self.promises),
            "leader_goal_packs": copy.deepcopy(self.leader_goal_packs),
            "vision": copy.deepcopy(self.vision),
            "modules": {
                "M02": copy.deepcopy(self.m02),
                "M03": copy.deepcopy(self.m03),
                "M04": copy.deepcopy(self.m04),
                "M05": copy.deepcopy(self.m05),
                "M06": copy.deepcopy(self.m06),
                "M07": copy.deepcopy(self.m07),
                "M08": copy.deepcopy(self.m08),
                "M09": copy.deepcopy(self.m09),
                "M10": copy.deepcopy(self.m10),
                "M11": copy.deepcopy(self.m11),
                "M12": copy.deepcopy(self.m12),
                "M13": copy.deepcopy(self.m13),
                "M14": copy.deepcopy(self.m14),
            },
            "pending": copy.deepcopy(self.pending),
            "history": copy.deepcopy(self.history),
            "tenures": copy.deepcopy(self.tenures),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], registry: Optional[DataRegistry] = None) -> GameState:
        meta = data.get("meta", {})
        scen_id = str(meta.get("scenario_id", "begin_1977"))
        seed = int(meta.get("master_seed", 19770620))
        st = cls(scenario_id=scen_id, master_seed=seed, registry=registry)

        st.meta = copy.deepcopy(meta)
        st.run = copy.deepcopy(data.get("run", st.run))
        st.player = copy.deepcopy(data.get("player", st.player))

        cal = data.get("calendar", {})
        st.start_date = str(cal.get("start_date", st.start_date))
        st.start_abs_day = int(cal.get("start_abs_day", st.start_abs_day))
        st.update_calendar(int(cal.get("day_index", 0)))

        if "rng" in data:
            st.rng = DeterministicRNG.from_dict(data["rng"], default_seed=seed)

        if "params" in data:
            st.params = copy.deepcopy(data["params"])
        if "flags" in data:
            st.flags = copy.deepcopy(data["flags"])
        if "modifiers" in data:
            st.modifiers = copy.deepcopy(data["modifiers"])
        st.next_modifier_uid = int(data.get("next_modifier_uid", st.next_modifier_uid))
        if "policies" in data:
            st.policies = copy.deepcopy(data["policies"])
        if "gov_axis_position" in data:
            st.gov_axis_position = copy.deepcopy(data["gov_axis_position"])
        if "axis_impulse" in data:
            st.axis_impulse = copy.deepcopy(data["axis_impulse"])
        if "characters" in data:
            st.characters = copy.deepcopy(data["characters"])
        if "offices" in data:
            st.offices = copy.deepcopy(data["offices"])
        if "parliament" in data:
            st.parliament = copy.deepcopy(data["parliament"])
        if "corridors" in data:
            st.corridors = copy.deepcopy(data["corridors"])
        if "party_state" in data:
            st.party_state = copy.deepcopy(data["party_state"])
        if "promises" in data:
            st.promises = copy.deepcopy(data["promises"])
        if "leader_goal_packs" in data:
            st.leader_goal_packs = copy.deepcopy(data["leader_goal_packs"])
        if "vision" in data:
            st.vision = copy.deepcopy(data["vision"])

        mods = data.get("modules", {})
        for m_name, attr in (
            ("M02", "m02"),
            ("M03", "m03"),
            ("M04", "m04"),
            ("M05", "m05"),
            ("M06", "m06"),
            ("M07", "m07"),
            ("M08", "m08"),
            ("M09", "m09"),
            ("M10", "m10"),
            ("M11", "m11"),
            ("M12", "m12"),
            ("M13", "m13"),
            ("M14", "m14"),
        ):
            if m_name in mods:
                setattr(st, attr, copy.deepcopy(mods[m_name]))

        if "pending" in data:
            st.pending = copy.deepcopy(data["pending"])
        if "history" in data:
            st.history = copy.deepcopy(data["history"])
        if "tenures" in data:
            st.tenures = copy.deepcopy(data["tenures"])
        return st

    def clone(self) -> GameState:
        """Fast deep clone for preview() without mutating live state."""
        return GameState.from_dict(self.to_dict(), registry=self.registry)

    def state_hash(self) -> str:
        """Compute canonical SHA-256 hash of authoritative state (M01 §4.11.2)."""
        hash_payload = {
            "day_index": self.day_index,
            "date_str": self.date_str,
            "player": self.player,
            "rng": self.rng.to_dict(),
            "params": self.params,
            "flags": self.flags,
            "modifiers": self.modifiers,
            "policies": self.policies,
            "gov_axis_position": self.gov_axis_position,
            "parliament_seats": self.parliament.get("CoalitionSeats", self.params.get("coalition_seats", 61)),
            "promises": self.promises,
            "vision_progress": self.params.get("vision_progress", 0.0),
        }
        return compute_sha256(hash_payload)

    def save_json(self, path: Union[str, Path]) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        h = self.state_hash()
        payload["state_hash"] = h
        with open(p, "w", encoding="utf-8") as f:
            json.dump(_canonicalize_value(payload), f, ensure_ascii=False, indent=2, sort_keys=True)
        return h

    @classmethod
    def load_json(cls, path: Union[str, Path], registry: Optional[DataRegistry] = None) -> GameState:
        with open(Path(path), "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data, registry=registry)
