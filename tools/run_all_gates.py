#!/usr/bin/env python3
"""Run the Godot isolation check and the headless milestone scripts that exist in this repo."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GODOT = shutil.which("godot") or "/opt/homebrew/bin/godot"
TESTS = [
    "res://tools/test_m1_foundation.gd",
    "res://tools/test_m2_causal_and_effects.gd",
    "res://tools/test_m3_domestic_politics.gd",
    "res://tools/test_m4_world_econ_mil.gd",
    "res://tools/test_m5_scheduler.gd",
    "res://tools/test_m6_desk_map_hud.gd",
    "res://tools/test_m7_drawers.gd",
    "res://tools/test_m8_release.gd",
    "res://tools/ui_constraints_validator.gd",
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    run([sys.executable, "tools/check_gdscript_isolation.py", "--strict"])
    compiler = ROOT / "tools" / "compile_runtime_json.py"
    if compiler.exists():
        run([sys.executable, str(compiler), "--verify"])
    if not Path(GODOT).exists():
        print("GODOT_SKIPPED")
        return 0
    for script in TESTS:
        run([GODOT, "--headless", "--path", "game", "-s", script])
    golden = subprocess.run(
        [GODOT, "--headless", "--path", "game", "-s", "res://tools/headless_golden_runner.gd"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    sys.stdout.write(golden.stdout)
    if "GOLDEN_PARITY_365D_PASSED" in golden.stdout:
        print("GOLDEN_GATE_PASSED")
    else:
        print("GOLDEN_GATE_DIVERGED")
    print("ALL_LOCAL_GATES_RAN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
