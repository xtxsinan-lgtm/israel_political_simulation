#!/usr/bin/env python3
"""Build-time YAML -> JSON compiler for the Godot runtime (WP-001, WP-002)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.expr import (  # noqa: E402
    BinaryNode,
    CallNode,
    ExprError,
    IdentNode,
    IndexNode,
    ListNode,
    LiteralNode,
    UnaryNode,
    compile_expr,
)

OUT_DIR = ROOT / "game" / "res" / "data"

CORE_FILES = [
    "parameters.json",
    "entities.json",
    "modifiers.json",
    "causal_edges.json",
    "policies.json",
    "actions.json",
    "characters.json",
    "world_tracks.json",
    "palestine_factions.json",
    "regions.json",
    "events.json",
    "ui_config.json",
    "codex_terms.json",
    "migrations.json",
]

EXPR_KEYS = {
    "remove_if",
    "scale",
    "condition",
    "trigger",
    "prob_modifiers",
    "prerequisites",
    "invalidation",
    "requires",
    "pre",
    "succ",
    "cond",
    "when",
}

INT_KEYS = [
    "save_version",
    "master_seed",
    "day_index",
    "abs_day",
    "y",
    "m",
    "d",
    "weekday",
    "s0",
    "s1",
    "s2",
    "s3",
    "draws",
    "uid",
    "start_day",
    "end_day",
    "stacks",
    "due_day",
    "seq",
    "bill_uid",
    "min_level",
    "max_level",
    "default_level",
    "duration_days",
    "cooldown_days",
    "birth_year",
    "death_year",
    "entry_year",
    "set_day",
    "tier_idx",
    "calls",
]


def load_yaml(path: Path) -> Any:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if data is not None else {}


def ast_to_json_list(node: Any) -> list:
    if isinstance(node, LiteralNode):
        return ["lit", node.value]
    if isinstance(node, IdentNode):
        return ["var", node.name]
    if isinstance(node, IndexNode):
        return ["idx", node.base_name, ast_to_json_list(node.key_node)]
    if isinstance(node, ListNode):
        return ["list", [ast_to_json_list(item) for item in node.items]]
    if isinstance(node, UnaryNode):
        return [node.op, ast_to_json_list(node.operand)]
    if isinstance(node, BinaryNode):
        op = "not_in" if node.op == "not in" else node.op
        return [op, ast_to_json_list(node.left), ast_to_json_list(node.right)]
    if isinstance(node, CallNode):
        return ["call", node.func_name, [ast_to_json_list(arg) for arg in node.args]]
    raise ExprError(f"Unsupported AST node: {type(node).__name__}")


def compile_expr_ast(expr: str) -> list:
    return ast_to_json_list(compile_expr(expr))


def _and_fold(parts: List[list]) -> list:
    if not parts:
        return ["lit", True]
    acc = parts[0]
    for part in parts[1:]:
        acc = ["and", acc, part]
    return acc


def _mutex_node(action_id: str) -> list:
    return ["not", ["call", "flag", [["lit", f"act.{action_id}"]]]]


def annotate_exprs(node: Any, ast_map: Dict[str, list], errors: List[str], path: str) -> None:
    if isinstance(node, dict):
        for raw_key in list(node.keys()):
            key = str(raw_key)
            if key.endswith("_ast"):
                continue
            value = node[raw_key]
            child_path = f"{path}.{key}"
            if key in EXPR_KEYS and isinstance(value, str):
                try:
                    ast = compile_expr_ast(value)
                except ExprError as exc:
                    errors.append(f"{child_path}: {exc} :: {value!r}")
                    continue
                node[f"{key}_ast"] = ast
                ast_map[value] = ast
            elif key in EXPR_KEYS and isinstance(value, (int, float, bool)) or value is None and key in EXPR_KEYS:
                lit = ["lit", True if value is None else value]
                node[f"{key}_ast"] = lit
            else:
                annotate_exprs(value, ast_map, errors, child_path)
        trigger = node.get("trigger")
        if isinstance(trigger, dict):
            parts: List[list] = []
            for sub in ("prerequisites", "condition"):
                ast = trigger.get(f"{sub}_ast")
                if isinstance(ast, list):
                    parts.append(ast)
            if parts:
                trigger["trigger_ast"] = _and_fold(parts)
        return
    if isinstance(node, list):
        for index, item in enumerate(node):
            annotate_exprs(item, ast_map, errors, f"{path}[{index}]")


def apply_action_mutex(events: List[dict], action_ids: set, ast_map: Dict[str, list]) -> None:
    for event in events:
        if not isinstance(event, dict):
            continue
        mutex_ids: List[str] = []
        raw_mutex = event.get("action_mutex")
        if isinstance(raw_mutex, str) and raw_mutex:
            mutex_ids.append(raw_mutex)
        elif isinstance(raw_mutex, list):
            mutex_ids.extend(str(item) for item in raw_mutex if item)
        event_id = str(event.get("id", ""))
        if event_id and event_id in action_ids and event_id not in mutex_ids:
            mutex_ids.append(event_id)
        if not mutex_ids:
            continue
        trigger = event.get("trigger")
        if isinstance(trigger, dict) and isinstance(trigger.get("trigger_ast"), list):
            base = trigger["trigger_ast"]
        elif isinstance(event.get("trigger_ast"), list):
            base = event["trigger_ast"]
        else:
            base = ["lit", True]
        for action_id in mutex_ids:
            base = ["and", base, _mutex_node(action_id)]
        event["trigger_ast"] = base
        if isinstance(trigger, dict):
            trigger["trigger_ast"] = base
        ast_map[f"mutex:{event_id}"] = base


def index_nodes_by_param(nodes: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(nodes, list):
        for item in nodes:
            if isinstance(item, dict):
                key = item.get("param") or item.get("id")
                if key:
                    out[str(key)] = item
    return out


def index_by_id(items: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and "id" in item:
                out[str(item["id"])] = item
    elif isinstance(items, dict):
        for key, item in items.items():
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("id", str(key))
                out[str(item.get("id", key))] = item
            else:
                out[str(key)] = item
    return out


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")


def merge_modifiers() -> Dict[str, Any]:
    primary = load_yaml(ROOT / "docs" / "registry" / "modifiers.yaml")
    extra = load_yaml(ROOT / "data" / "modifiers.yaml")
    merged: Dict[str, Any] = {}
    for source in (primary, extra):
        for item in source.get("modifiers", []) if isinstance(source, dict) else []:
            if isinstance(item, dict) and "id" in item:
                current = dict(merged.get(item["id"], {}))
                current.update(item)
                merged[str(item["id"])] = current
    return {
        "schema_version": 1,
        "modifiers": [merged[key] for key in sorted(merged.keys())],
        "by_id": merged,
    }


def compile_events(action_ids: set, ast_map: Dict[str, list], errors: List[str]) -> Dict[str, Any]:
    events_dir = ROOT / "data" / "events"
    events: List[dict] = []
    flags: List[Any] = []
    modifiers: List[Any] = []
    sources: List[str] = []
    if events_dir.exists():
        for path in sorted(events_dir.glob("*.yaml")):
            raw = load_yaml(path)
            sources.append(path.name)
            if isinstance(raw, dict):
                events.extend(raw.get("events", []) or [])
                flags.extend(raw.get("flags", []) or [])
                modifiers.extend(raw.get("modifiers", []) or [])
    annotate_exprs(events, ast_map, errors, "events")
    apply_action_mutex(events, action_ids, ast_map)
    by_id = index_by_id(events)
    return {
        "sources": sources,
        "events": events,
        "by_id": by_id,
        "flags": flags,
        "modifiers": modifiers,
    }


def compile_scenario(scenario_id: str, ast_map: Dict[str, list], errors: List[str]) -> Dict[str, Any]:
    base = ROOT / "data" / "scenarios" / scenario_id
    files: Dict[str, Any] = {}
    if base.exists():
        for path in sorted(base.rglob("*.yaml")):
            rel = path.relative_to(base).as_posix()
            files[rel] = load_yaml(path)
    annotate_exprs(files, ast_map, errors, scenario_id)
    modules: Dict[str, Any] = {}
    for rel, payload in files.items():
        if rel.startswith("modules/") and rel.endswith(".yaml"):
            modules[Path(rel).stem] = payload
    return {
        "scenario_id": scenario_id,
        "files": files,
        "scenario": files.get("scenario.yaml", {}),
        "snapshot": files.get("snapshot.yaml", {}),
        "modules": modules,
    }


def compile_all_yaml_to_json(root_dir: Path, out_dir: Path) -> Dict[str, list]:
    ast_map: Dict[str, list] = {}
    errors: List[str] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    params_path = root_dir / "data" / "parameters.yaml"
    if not params_path.exists():
        params_path = root_dir / "docs" / "registry" / "parameters.yaml"
    parameters = load_yaml(params_path)
    annotate_exprs(parameters, ast_map, errors, "parameters")
    param_list = parameters.get("parameters", []) if isinstance(parameters, dict) else []
    parameters_out = {
        "modules": parameters.get("modules", {}) if isinstance(parameters, dict) else {},
        "parameters": param_list,
        "by_id": index_by_id(param_list),
        "aliases": parameters.get("aliases", {}) if isinstance(parameters, dict) else {},
        "entities": parameters.get("entities", {}) if isinstance(parameters, dict) else {},
    }
    write_json(out_dir / "parameters.json", parameters_out)

    entities_src = load_yaml(root_dir / "docs" / "registry" / "entities.yaml")
    if not entities_src:
        entities_src = parameters_out["entities"]
    if isinstance(entities_src, dict) and "entities" not in entities_src and entities_src:
        entities_payload = {"entities": entities_src}
    else:
        entities_payload = entities_src if isinstance(entities_src, dict) else {"entities": {}}
    write_json(out_dir / "entities.json", entities_payload)

    modifiers = merge_modifiers()
    annotate_exprs(modifiers, ast_map, errors, "modifiers")
    write_json(out_dir / "modifiers.json", modifiers)

    causal = load_yaml(root_dir / "data" / "causal_edges.yaml")
    annotate_exprs(causal, ast_map, errors, "causal_edges")
    if isinstance(causal, dict):
        causal["by_param"] = index_nodes_by_param(causal.get("nodes", []))
        thresholds = load_yaml(root_dir / "data" / "thresholds.yaml")
        if isinstance(thresholds, dict):
            causal["thresholds"] = thresholds.get("thresholds", [])
    write_json(out_dir / "causal_edges.json", causal)

    policies = load_yaml(root_dir / "data" / "policies.yaml")
    annotate_exprs(policies, ast_map, errors, "policies")
    policy_list = policies.get("policies", []) if isinstance(policies, dict) else []
    write_json(out_dir / "policies.json", {"policies": policy_list, "by_id": index_by_id(policy_list)})

    actions = load_yaml(root_dir / "data" / "actions.yaml")
    annotate_exprs(actions, ast_map, errors, "actions")
    action_list = actions.get("actions", []) if isinstance(actions, dict) else []
    action_index = index_by_id(action_list)
    write_json(out_dir / "actions.json", {"actions": action_list, "by_id": action_index})

    characters = load_yaml(root_dir / "data" / "characters.yaml")
    annotate_exprs(characters, ast_map, errors, "characters")
    char_list = characters.get("characters", []) if isinstance(characters, dict) else []
    write_json(
        out_dir / "characters.json",
        {
            "scenario_defaults": characters.get("scenario_defaults", {}) if isinstance(characters, dict) else {},
            "characters": char_list,
            "by_id": index_by_id(char_list),
        },
    )

    world = load_yaml(root_dir / "data" / "world_tracks.yaml")
    annotate_exprs(world, ast_map, errors, "world_tracks")
    write_json(out_dir / "world_tracks.json", world)

    palestine = load_yaml(root_dir / "data" / "palestine_factions.yaml")
    annotate_exprs(palestine, ast_map, errors, "palestine_factions")
    write_json(out_dir / "palestine_factions.json", palestine)

    regions = load_yaml(root_dir / "data" / "regions.yaml")
    annotate_exprs(regions, ast_map, errors, "regions")
    write_json(out_dir / "regions.json", regions)

    events = compile_events(set(action_index.keys()), ast_map, errors)
    write_json(out_dir / "events.json", events)

    ui_config = load_yaml(root_dir / "data" / "ui_config.yaml")
    if not isinstance(ui_config, dict) or not ui_config:
        ui_config = {"slots": [], "alerts": [], "fuzzy_params": []}
    annotate_exprs(ui_config, ast_map, errors, "ui_config")
    write_json(out_dir / "ui_config.json", ui_config)

    codex = load_yaml(root_dir / "data" / "codex_terms.yaml")
    if not isinstance(codex, dict) or not codex:
        codex = {"terms": {}}
    annotate_exprs(codex, ast_map, errors, "codex_terms")
    write_json(out_dir / "codex_terms.json", codex)

    migrations = load_yaml(root_dir / "data" / "migrations.yaml")
    if not isinstance(migrations, dict) or not migrations:
        migrations = {"migrations": []}
    write_json(out_dir / "migrations.json", migrations)

    scenario = compile_scenario("begin_1977", ast_map, errors)
    write_json(out_dir / "scenarios" / "begin_1977.json", scenario)
    write_json(out_dir / "compiled_asts.json", {"asts": ast_map})

    if errors:
        for line in errors:
            print("AST_ERROR:", line, file=sys.stderr)
        raise SystemExit(1)
    return ast_map


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def generate_manifest(out_dir: Path, compiled_ast_map: dict) -> dict:
    rel_paths: List[str] = []
    for path in sorted(out_dir.rglob("*.json")):
        rel = path.relative_to(out_dir).as_posix()
        if rel == "manifest.json":
            continue
        rel_paths.append(rel)
    files: Dict[str, str] = {}
    lines: List[str] = []
    for rel in rel_paths:
        digest = file_sha256(out_dir / rel)
        files[rel] = digest
        lines.append(f"{rel}:{digest}\n")
    ruleset_hash = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest().lower()
    manifest = {
        "ruleset_hash": ruleset_hash,
        "files": files,
        "int_schema_paths": {"global_int_keys": INT_KEYS},
        "compiled_ast_count": len(compiled_ast_map),
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest


def verify_outputs(out_dir: Path) -> None:
    missing = [name for name in CORE_FILES if not (out_dir / name).exists()]
    if missing:
        raise SystemExit(f"missing core json: {missing}")
    if not (out_dir / "scenarios" / "begin_1977.json").exists():
        raise SystemExit("missing scenarios/begin_1977.json")
    if not (out_dir / "compiled_asts.json").exists():
        raise SystemExit("missing compiled_asts.json")
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    if len(manifest.get("ruleset_hash", "")) != 64:
        raise SystemExit("ruleset_hash is not 64 hex chars")
    if len(manifest.get("files", {})) < 14:
        raise SystemExit("manifest files < 14")
    asts = json.loads((out_dir / "compiled_asts.json").read_text(encoding="utf-8")).get("asts", {})
    for expr, ast in asts.items():
        if not isinstance(ast, list) or not ast:
            raise SystemExit(f"empty ast for {expr!r}")
    policies = json.loads((out_dir / "policies.json").read_text(encoding="utf-8"))
    actions = json.loads((out_dir / "actions.json").read_text(encoding="utf-8"))
    characters = json.loads((out_dir / "characters.json").read_text(encoding="utf-8"))
    parameters = json.loads((out_dir / "parameters.json").read_text(encoding="utf-8"))
    if len(policies["by_id"]) != 76 or len(actions["by_id"]) != 104 or len(characters["by_id"]) != 43:
        raise SystemExit(
            f"unexpected counts policies={len(policies['by_id'])} actions={len(actions['by_id'])} characters={len(characters['by_id'])}"
        )
    if len(parameters["by_id"]) < 110:
        raise SystemExit(f"parameters {len(parameters['by_id'])} < 110")


def check_up_to_date(out_dir: Path) -> None:
    """Compile into a temp dir and compare with out_dir without modifying it."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        ast_map = compile_all_yaml_to_json(ROOT, tmp_dir)
        manifest = generate_manifest(tmp_dir, ast_map)
        stale: List[str] = []
        for path in sorted(tmp_dir.rglob("*.json")):
            rel = path.relative_to(tmp_dir).as_posix()
            committed = out_dir / rel
            if not committed.exists() or file_sha256(committed) != file_sha256(path):
                stale.append(rel)
        for path in sorted(out_dir.rglob("*.json")):
            rel = path.relative_to(out_dir).as_posix()
            if not (tmp_dir / rel).exists():
                stale.append(f"{rel} (orphan)")
    if stale:
        raise SystemExit(
            "STALE runtime JSON (run tools/compile_runtime_json.py and commit): " + ", ".join(stale)
        )
    verify_outputs(out_dir)
    print(f"CHECK_OK {manifest['ruleset_hash']} files={len(manifest['files'])} asts={len(ast_map)}")


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Compile runtime YAML into Godot JSON")
    parser.add_argument("--verify", action="store_true", help="Compile, check outputs, and confirm a stable ruleset hash")
    parser.add_argument("--check", action="store_true", help="Fail if committed JSON differs from a fresh compile (does not write)")
    parser.add_argument("--out", default=str(OUT_DIR))
    args = parser.parse_args(argv)
    out_dir = Path(args.out)
    if args.check:
        check_up_to_date(out_dir)
        return
    ast_map = compile_all_yaml_to_json(ROOT, out_dir)
    manifest = generate_manifest(out_dir, ast_map)
    if args.verify:
        first_hash = manifest["ruleset_hash"]
        ast_map_2 = compile_all_yaml_to_json(ROOT, out_dir)
        manifest_2 = generate_manifest(out_dir, ast_map_2)
        if manifest_2["ruleset_hash"] != first_hash:
            raise SystemExit("ruleset_hash drifted between two compiles")
        verify_outputs(out_dir)
        print(f"VERIFY_OK {manifest_2['ruleset_hash']} files={len(manifest_2['files'])} asts={len(ast_map_2)}")
    else:
        print(f"WROTE {manifest['ruleset_hash']} files={len(manifest['files'])}")


if __name__ == "__main__":
    main()
