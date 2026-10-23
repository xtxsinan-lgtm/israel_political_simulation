#!/usr/bin/env python3
"""Build the browser bundle for the web prototype (web/).

The web prototype runs the *reference* Python simulation (sim/) inside the browser via
Pyodide, so the numbers on screen are exactly the numbers the Godot client is gated
against (data/golden/begin_1977_365d.json).

Outputs (all under web/build/, generated, not hand-edited):
  sim_bundle.json   sim/*.py sources + every YAML file the sim reads, pre-converted to JSON
                    (Pyodide has no fast C YAML loader; JSON parses ~100x faster).
  ui/*.json         copies of game/res/data JSON the UI needs (codex, regions, parameters, ...)
  web/py/bridge.py  is copied into the bundle as well.

Integer dict keys (e.g. policy tiers) are not representable in JSON, so they are encoded as
"__int__:<n>" and restored by the loader shim in web/py/yaml_shim.py.

`--verify` re-runs the 365-day golden comparison in-process using the converted data to prove
the conversion is lossless.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

import yaml

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = WEB / "build"
INT_KEY_PREFIX = "__int__:"
UI_JSON = [
    "codex_terms.json",
    "regions.json",
    "parameters.json",
    "ui_config.json",
    "characters.json",
    "palestine_factions.json",
    "policies.json",
    "actions.json",
    "world_tracks.json",
    "entities.json",
    "causal_edges.json",
]


def yaml_files() -> list:
    files = sorted(p for p in (ROOT / "data").rglob("*.yaml"))
    files += [ROOT / "docs/registry/flags.yaml", ROOT / "docs/registry/modifiers.yaml"]
    return files


def encode(obj: Any) -> Any:
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, bool) or not isinstance(k, (str, int)):
                raise SystemExit(f"unsupported YAML key type {type(k).__name__}: {k!r}")
            key = f"{INT_KEY_PREFIX}{k}" if isinstance(k, int) else k
            out[key] = encode(v)
        return out
    if isinstance(obj, list):
        return [encode(v) for v in obj]
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    raise SystemExit(f"unsupported YAML value type {type(obj).__name__}: {obj!r}")


def decode_pairs(pairs: list) -> dict:
    out = {}
    for k, v in pairs:
        if isinstance(k, str) and k.startswith(INT_KEY_PREFIX):
            k = int(k[len(INT_KEY_PREFIX):])
        out[k] = v
    return out


def build() -> Dict[str, Any]:
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    files: Dict[str, str] = {}
    for path in yaml_files():
        data = yaml.load(path.read_text(encoding="utf-8"), Loader=loader)
        files[path.relative_to(ROOT).as_posix()] = json.dumps(encode(data), ensure_ascii=False, separators=(",", ":"))
    sources = {p.relative_to(ROOT).as_posix(): p.read_text(encoding="utf-8") for p in sorted((ROOT / "sim").glob("*.py"))}
    for p in sorted((WEB / "py").glob("*.py")):
        sources[p.relative_to(WEB).as_posix()] = p.read_text(encoding="utf-8")
    bundle = {"version": 1, "int_key_prefix": INT_KEY_PREFIX, "files": files, "sources": sources}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sim_bundle.json").write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    ui_dir = OUT / "ui"
    ui_dir.mkdir(exist_ok=True)
    for name in UI_JSON:
        src = ROOT / "game/res/data" / name
        if src.exists():
            shutil.copyfile(src, ui_dir / name)
    shutil.copyfile(ROOT / "game/res/map/map_geo.json", ui_dir / "map_geo.json")
    golden = ROOT / "data/golden/begin_1977_365d.json"
    shutil.copyfile(golden, OUT / "golden_begin_1977_365d.json")
    return bundle


def verify(bundle: Dict[str, Any]) -> None:
    """Run the golden year with the sim reading the converted JSON instead of YAML."""
    import types

    files = bundle["files"]
    shim = types.ModuleType("yaml")

    class _Loader:  # noqa: D401 - placeholder for getattr(yaml, "CSafeLoader")
        pass

    def _load(stream: Any, Loader: Any = None) -> Any:  # noqa: N803 - mirrors yaml API
        name = getattr(stream, "name", "")
        rel = Path(name).resolve().relative_to(ROOT).as_posix()
        return json.loads(files[rel], object_pairs_hook=decode_pairs)

    shim.SafeLoader = _Loader
    shim.CSafeLoader = _Loader
    shim.load = _load
    shim.safe_load = lambda s: _load(s)
    real_yaml = sys.modules.get("yaml")
    sys.modules["yaml"] = shim
    for mod in [m for m in list(sys.modules) if m == "sim" or m.startswith("sim.")]:
        del sys.modules[mod]
    sys.path.insert(0, str(ROOT))
    try:
        from sim.engine import SimulationEngine
        from sim.state import DataRegistry

        DataRegistry._instance = None
        golden = json.loads((ROOT / "data/golden/begin_1977_365d.json").read_text(encoding="utf-8"))
        engine = SimulationEngine(scenario_id="begin_1977", master_seed=19770620)
        ok = 0
        for cp in golden["checkpoints"]:
            while engine.state.day_index < cp["day_index"]:
                engine.step_day()
            ok += engine.state_hash() == cp["state_hash"]
        total = len(golden["checkpoints"])
        print(f"WEB_BUNDLE_GOLDEN {ok}/{total}")
        if ok != total:
            raise SystemExit("converted data diverges from the golden trajectory")
    finally:
        if real_yaml is not None:
            sys.modules["yaml"] = real_yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--verify", action="store_true", help="re-run the golden year on the converted data")
    args = parser.parse_args()
    bundle = build()
    size = (OUT / "sim_bundle.json").stat().st_size
    print(f"WROTE web/build/sim_bundle.json files={len(bundle['files'])} sources={len(bundle['sources'])} bytes={size}")
    if args.verify:
        verify(bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
