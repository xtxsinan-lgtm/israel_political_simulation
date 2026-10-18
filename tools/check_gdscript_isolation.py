#!/usr/bin/env python3
"""Static isolation and arithmetic-whitelist scanner for game/sim (WP-003)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
SIM_ROOT = ROOT / "game" / "sim"

FORBIDDEN_API = re.compile(
    r"\bextends\s+(Node|Control|Node2D|CanvasItem)\b|"
    r"\bget_tree\s*\(|"
    r"\bInput\.|"
    r"\bRenderingServer\b|"
    r"\bAudioServer\b|"
    r"\bUIManager\b|"
    r"\bAudioManager\b"
)
FORBIDDEN_MATH = re.compile(
    r"(?<![A-Za-z0-9_])(round|roundf|pow|exp|log|sin|cos|tan|asin|acos|atan|atan2|randf|randi|randfn|randomize)\s*\("
)
NOLINT_ROUND = "NOLINT: round_restore"
ROUND_ALLOW_FILES = {"SimMath.gd", "SaveSystem.gd"}


def _code_without_comment(line: str) -> str:
    in_string = False
    quote = ""
    out = []
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < len(line):
                out.append(line[i + 1])
                i += 2
                continue
            if ch == quote:
                in_string = False
            i += 1
            continue
        if ch in ("'", '"'):
            in_string = True
            quote = ch
            out.append(ch)
            i += 1
            continue
        if ch == "#":
            break
        out.append(ch)
        i += 1
    return "".join(out)


def scan_text(rel: str, text: str) -> List[Tuple[int, str]]:
    violations: List[Tuple[int, str]] = []
    if "extends RefCounted" not in text and "extends SceneTree" not in text:
        violations.append((1, "missing extends RefCounted"))
    name = Path(rel).name
    for lineno, line in enumerate(text.splitlines(), start=1):
        code = _code_without_comment(line)
        api = FORBIDDEN_API.search(code)
        if api:
            violations.append((lineno, f"forbidden API {api.group(0)!r}"))
        math = FORBIDDEN_MATH.search(code)
        if math:
            if math.group(1) in ("round", "roundf") and name in ROUND_ALLOW_FILES and NOLINT_ROUND in line:
                continue
            violations.append((lineno, f"forbidden call {math.group(1)}("))
    return violations


def scan_tree(sim_root: Path) -> List[str]:
    if not sim_root.exists():
        return []
    reports: List[str] = []
    for path in sorted(sim_root.rglob("*.gd")):
        rel = path.relative_to(sim_root.parent.parent).as_posix() if sim_root.parent.parent in path.parents else path.name
        try:
            rel = path.relative_to(ROOT).as_posix()
        except ValueError:
            rel = path.as_posix()
        text = path.read_text(encoding="utf-8")
        for lineno, message in scan_text(rel, text):
            reports.append(f"{rel}:{lineno}: {message}")
    return reports


def self_test() -> None:
    bad_node = scan_text("game/sim/core/Bad.gd", "extends Node\nfunc f() -> void:\n\tget_tree()\n")
    bad_rand = scan_text("game/sim/core/Bad.gd", "extends RefCounted\nfunc f() -> float:\n\treturn randf()\n")
    ok_round = scan_text(
        "game/sim/core/SimMath.gd",
        "extends RefCounted\nfunc f(v: float) -> int:\n\treturn int(round(v)) # NOLINT: round_restore\n",
    )
    if not bad_node or not bad_rand or ok_round:
        raise SystemExit(
            f"self-test failed node={bad_node} rand={bad_rand} round={ok_round}"
        )
    print("ISOLATION_SELF_TEST_OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check game/sim GDScript isolation")
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any violation is found")
    parser.add_argument("--self-test", action="store_true", help="Check the scanner against synthetic samples")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    reports = scan_tree(SIM_ROOT)
    if reports:
        for line in reports:
            print(line, file=sys.stderr)
        if args.strict:
            raise SystemExit(1)
        raise SystemExit(1)
    print("ISOLATION_OK")


if __name__ == "__main__":
    main()
