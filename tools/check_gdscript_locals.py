#!/usr/bin/env python3
"""Flag GDScript locals re-declared while an outer declaration is still in scope.

Godot refuses to compile such scripts, but gdtoolkit's `gdparse` (syntax only) does not
catch it. Usage: python3 tools/check_gdscript_locals.py [files...]  (default: all game/**/*.gd)
"""
import re
import sys

VAR = re.compile(r"^(\t+)(?:var|const) ([A-Za-z_]\w*)\b")
FOR = re.compile(r"^(\t+)for ([A-Za-z_]\w*)\b")
FUNC = re.compile(r"^(\t*)(?:static )?func (\w+)\((.*?)\)")

bad = 0
import os
from pathlib import Path
files = sys.argv[1:] or [str(p) for p in sorted(Path(__file__).resolve().parents[1].joinpath("game").rglob("*.gd"))]
for path in files:
    if not os.path.exists(path):
        continue
    lines = open(path, encoding="utf-8").read().splitlines()
    func = None
    names = {}
    for no, line in enumerate(lines, 1):
        m = FUNC.match(line)
        if m:
            func = m.group(2)
            names = {}
            for p in m.group(3).split(","):
                p = p.strip().split(":")[0].split("=")[0].strip()
                if p:
                    names[p] = (no, 0)
            continue
        if func is None:
            continue
        if line and not line.startswith("\t") and not line.startswith("#"):
            func = None
            continue
        if not line.strip() or line.strip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip("\t"))
        names = {k: v for k, v in names.items() if v[1] <= indent}
        for rx, extra in ((VAR, 0), (FOR, 1)):
            mm = rx.match(line)
            if mm:
                n = mm.group(2)
                if n in names and not n.startswith("_"):
                    print(f"{path}:{no}: '{n}' already declared at line {names[n][0]} in {func}()")
                    bad += 1
                names[n] = (no, len(mm.group(1)) + extra)
print("LOCALS_OK" if not bad else f"LOCALS_FAIL {bad}")
sys.exit(1 if bad else 0)
