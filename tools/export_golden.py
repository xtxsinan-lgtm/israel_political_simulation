#!/usr/bin/env python3
"""
Export deterministic 365-day golden baseline trajectory for `begin_1977`
to `data/golden/begin_1977_365d.json` (M01 §4.11 / Phase 3A).
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sim.engine import SimulationEngine
from sim.state import _canonicalize_value


def export_golden(
    scenario_id: str = "begin_1977",
    master_seed: int = 19770620,
    days: int = 365,
    output_path: Path = ROOT_DIR / "data" / "golden" / "begin_1977_365d.json",
) -> Dict[str, Any]:
    from sim.state import DataRegistry
    DataRegistry.instance().get_scenario_bundle(scenario_id)
    t0 = time.perf_counter()
    engine = SimulationEngine(scenario_id=scenario_id, master_seed=master_seed)
    day0_hash = engine.state_hash()

    checkpoints: List[Dict[str, Any]] = [
        {
            "day_index": 0,
            "date": engine.state.date_str,
            "state_hash": day0_hash,
            "key_params": {
                "party_standing": engine.state.get_param("party_standing"),
                "party_cohesion": engine.state.get_param("party_cohesion"),
                "coalition_seats": engine.state.get_param("coalition_seats"),
                "inflation": engine.state.get_param("inflation"),
                "fx_reserves": engine.state.get_param("fx_reserves"),
                "budget_balance": engine.state.get_param("budget_balance"),
                "public_security": engine.state.get_param("public_security"),
                "deterrence": engine.state.get_param("deterrence"),
                "us_admin_relation": engine.state.get_param("us_admin_relation"),
                "rule_of_law": engine.state.get_param("rule_of_law"),
            },
        }
    ]

    for d in range(1, days + 1):
        engine.step_day()
        if engine.state.is_month or d == days:
            checkpoints.append({
                "day_index": engine.state.day_index,
                "date": engine.state.date_str,
                "state_hash": engine.state_hash(),
                "key_params": {
                    "party_standing": engine.state.get_param("party_standing"),
                    "party_cohesion": engine.state.get_param("party_cohesion"),
                    "coalition_seats": engine.state.get_param("coalition_seats"),
                    "inflation": engine.state.get_param("inflation"),
                    "fx_reserves": engine.state.get_param("fx_reserves"),
                    "budget_balance": engine.state.get_param("budget_balance"),
                    "public_security": engine.state.get_param("public_security"),
                    "deterrence": engine.state.get_param("deterrence"),
                    "us_admin_relation": engine.state.get_param("us_admin_relation"),
                    "rule_of_law": engine.state.get_param("rule_of_law"),
                },
            })

    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    final_hash = engine.state_hash()

    golden_payload = {
        "schema_version": 1,
        "scenario_id": scenario_id,
        "master_seed": master_seed,
        "days_simulated": days,
        "start_date": "1977-06-20",
        "end_date": engine.state.date_str,
        "day0_state_hash": day0_hash,
        "final_state_hash": final_hash,
        "checkpoints": checkpoints,
        "final_params": _canonicalize_value(engine.state.params),
        "events_fired": _canonicalize_value(engine.state.m12.get("fired", {})),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(golden_payload, f, ensure_ascii=False, indent=2, sort_keys=True)

    print(
        f"[export_golden] Exported {days}d golden trajectory to {output_path.relative_to(ROOT_DIR)} "
        f"in {elapsed_ms:.2f} ms (final_hash={final_hash[:16]}...)"
    )
    return {"elapsed_ms": elapsed_ms, "final_hash": final_hash, "output_path": str(output_path)}


if __name__ == "__main__":
    export_golden()
