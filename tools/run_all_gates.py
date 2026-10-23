#!/usr/bin/env python3
"""Run the Godot isolation check and every headless milestone script in this repo.

Exit code is non-zero when any gate fails, including:
  * a Godot script exits non-zero, times out, prints a script/parse error,
    or never prints its success sentinel;
  * the 365-day golden comparison diverges;
  * Godot is not installed (unless --allow-no-godot is given).

Godot is resolved from $GODOT, then PATH (`godot`, `godot4`), then common install paths.
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]

# (script, success sentinel printed on stdout)
TESTS: List[Tuple[str, str]] = [
    ("res://tools/test_m1_foundation.gd", "M1_FOUNDATION_OK"),
    ("res://tools/test_m2_causal_and_effects.gd", "M2_CAUSAL_OK"),
    ("res://tools/test_m3_domestic.gd", "M3_DOMESTIC_OK"),
    ("res://tools/test_m3_domestic_politics.gd", "M3_DOMESTIC_POLITICS_OK"),
    ("res://tools/test_m4_world.gd", "M4_WORLD_OK"),
    ("res://tools/test_m4_world_econ_mil.gd", "M4_WORLD_ECON_MIL_ALL_PASSED"),
    ("res://tools/test_m5_scheduler.gd", "M5_SCHEDULER_OK"),
    ("res://tools/test_m6_desk_map_hud.gd", "M6_DESK_MAP_HUD_ALL_PASSED"),
    ("res://tools/test_m7_drawers.gd", "M7_DRAWERS_ALL_PASSED"),
    ("res://tools/test_m8_release.gd", "M8_RELEASE_OK"),
    ("res://tools/ui_constraints_validator.gd", "UI_CONSTRAINTS_ALL_PASSED"),
]
GOLDEN = ("res://tools/headless_golden_runner.gd", "GOLDEN_PARITY_365D_PASSED")
PERF = ("res://tools/headless_perf_bench.gd", "PERF_BENCH_30Y_PASSED")

ERROR_PATTERNS = re.compile(r"SCRIPT ERROR|Parse Error|Compile Error|Failed to load script|_FAIL\b|_FAIL:")
CANDIDATE_GODOTS = [
    "/opt/homebrew/bin/godot",
    "/usr/local/bin/godot",
    "/Applications/Godot.app/Contents/MacOS/Godot",
    str(Path.home() / ".local/godot/Godot.app/Contents/MacOS/Godot"),
]


def find_godot() -> Optional[str]:
    env = os.environ.get("GODOT")
    if env and Path(env).exists():
        return env
    for name in ("godot", "godot4"):
        found = shutil.which(name)
        if found:
            return found
    for cand in CANDIDATE_GODOTS:
        if Path(cand).exists():
            return cand
    return None


def run_py(cmd: List[str]) -> bool:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode == 0


def run_godot(godot: str, script: str, sentinel: str, timeout: int) -> bool:
    cmd = [godot, "--headless", "--path", "game", "-s", script]
    print("+", " ".join(cmd), flush=True)
    try:
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"GATE_FAIL {script}: timeout after {timeout}s")
        return False
    out = proc.stdout + proc.stderr
    sys.stdout.write(proc.stdout)
    if proc.stderr.strip():
        sys.stdout.write(proc.stderr)
    problems = []
    if proc.returncode != 0:
        problems.append(f"exit={proc.returncode}")
    if sentinel not in proc.stdout:
        problems.append(f"missing sentinel '{sentinel}'")
    err = ERROR_PATTERNS.search(out)
    if err:
        problems.append(f"error output '{err.group(0)}'")
    if problems:
        print(f"GATE_FAIL {script}: {', '.join(problems)}")
        return False
    print(f"GATE_OK {script}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--allow-no-godot", action="store_true", help="exit 0 if Godot is not installed")
    parser.add_argument("--perf", action="store_true", help="also run the 30-year performance bench")
    parser.add_argument("--timeout", type=int, default=900, help="per-script timeout in seconds")
    args = parser.parse_args()

    failures: List[str] = []
    if not run_py([sys.executable, "tools/check_gdscript_isolation.py", "--strict"]):
        failures.append("isolation")
    compiler = ROOT / "tools" / "compile_runtime_json.py"
    if compiler.exists() and not run_py([sys.executable, str(compiler), "--check"]):
        failures.append("compile_runtime_json --check (committed runtime JSON is stale)")
    if not run_py([sys.executable, "tools/check_gdscript_locals.py"]):
        failures.append("check_gdscript_locals (duplicate local declarations)")
    if (ROOT / "tools" / "build_web.py").exists() and not run_py([sys.executable, "tools/build_web.py", "--verify"]):
        failures.append("build_web --verify (web prototype bundle diverges from golden)")

    godot = find_godot()
    if godot is None:
        print("GODOT_NOT_FOUND (set $GODOT to the Godot 4.6 binary)")
        if args.allow_no_godot and not failures:
            print("GODOT_SKIPPED")
            return 0
        failures.append("godot missing")
    else:
        print("+", godot, "--headless --path game --import", flush=True)
        try:
            subprocess.run([godot, "--headless", "--path", "game", "--import"], cwd=ROOT, timeout=args.timeout)
        except subprocess.TimeoutExpired:
            failures.append("godot --import timeout")
        scripts = list(TESTS) + [GOLDEN] + ([PERF] if args.perf else [])
        for script, sentinel in scripts:
            if not run_godot(godot, script, sentinel, args.timeout):
                failures.append(script)

    if failures:
        print("GATES_FAILED: " + "; ".join(failures))
        print("See docs/reviews/2026-10-18_godot_milestone_review_handoff.md (risk table R1-R9) for likely causes.")
        return 1
    print("ALL_GATES_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
