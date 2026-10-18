#!/usr/bin/env python3
"""
Static validator for all compiled event YAML files in data/events/ and registries in docs/registry/:
  1. Global & per-file event ID format and uniqueness (V-01, V-02, V-03).
  2. M12 §4.4 EBNF expression grammar, lexical rules, AST type-checking, parameter scope/key
     validation, V-05 (fixed condition >= 1 param comparison), and V-11 (random prerequisites
     no param comparison).
  3. Effect `op` / `target` / `key` validity (V-06, V-07 no derived target, D-050
     `stance_shift_by_corridor`, V-14 predecision `risk_hint` vs `event_multiplier`).
  4. Flag & modifier existence in `docs/registry/flags.yaml` and `docs/registry/modifiers.yaml`,
     plus registry health checks (0 orphan flags, 0 empty-shell modifiers).
  5. M12 §4.8 anti-AI-tone 22 regex checks across all narrative fields (V-22).
"""

from __future__ import annotations
import re
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
EVENTS_DIR = ROOT / "data" / "events"
PARAMS_PATH = ROOT / "docs" / "registry" / "parameters.yaml"
FLAGS_PATH = ROOT / "docs" / "registry" / "flags.yaml"
MODS_PATH = ROOT / "docs" / "registry" / "modifiers.yaml"

EXPECTED_FILES = [
    "fixed_1948_1955.yaml",
    "fixed_1955_1967.yaml",
    "fixed_1967_1977.yaml",
    "fixed_1977_1992.yaml",
    "fixed_1992_2006.yaml",
    "random_events.yaml",
]

# M12 §4.8 Anti-AI-Tone Regexes (P01-P20, PZ1-PZ2)
AI_TONE_PATTERNS = {
    "P01": r"不是[^，。；！？\n]{1,20}而是[^，。；！？\n]{1,20}",
    "P02": r"与其说[^，。；\n]{1,20}不如说",
    "P03": r"换句话说|换言之|更准确地说",
    "P04": r"这正是[^，。；\n]{1,15}的原因|这就是为什么",
    "P05": r"讽刺的是|具有讽刺意味的是|耐人寻味的是|意味深长的是|吊诡的是",
    "P06": r"不可否认|毋庸置疑|显而易见|不言而喻|众所周知",
    "P07": r"总而言之|综上所述|归根结底|简而言之|一言以蔽之",
    "P08": r"历史将证明|时间会证明|后人将会|多年以后人们才会",
    "P09": r"在[^，。；\n]{2,12}的背景下|在[^，。；\n]{2,12}的框架下|在[^，。；\n]{2,12}的语境下",
    "P10": r"在某种程度上|从某种意义上说|某种意义上",
    "P11": r"正如[^，。；\n]{2,15}所言|正如人们常说的",
    "P12": r"一方面[^。；\n]{2,40}另一方面",
    "P13": r"既[^，。；\n]{2,12}又[^，。；\n]{2,12}，既[^，。；\n]{2,12}又",
    "P14": r"不仅[^，。；\n]{2,25}而且[^，。；\n]{2,25}更",
    "P15": r"首先[^。]{2,60}其次[^。]{2,60}(最后|再次)",
    "P16": r"政治光谱|叙事|博弈|赋能|抓手|底层逻辑|顶层设计|生态位|闭环|颗粒度|维度",
    "P17": r"撕裂了社会的伤口|历史的车轮|时代的洪流|命运的十字路口|潘多拉的魔盒|达摩克利斯之剑|多米诺骨牌",
    "P18": r"空气中弥漫着|气氛凝重得仿佛|沉默震耳欲聋|无声的控诉",
    "P19": r"复杂的感情|百感交集|五味杂陈|心情沉重",
    "P20": r"——[^\n—]{1,30}——[^\n—]{1,30}——",
    "PZ1": r"在历史的长河中|翻开新的一页|写下了浓墨重彩的一笔|拉开了[^，。]{1,10}的序幕|敲响了[^，。]{1,10}的警钟",
    "PZ2": r"何去何从|拭目以待|未完待续|且看下回",
}

# ---------------------------------------------------------------------------
# M12 §4.4 Expression Tokenizer & Recursive-Descent Parser + Static Type Checker
# ---------------------------------------------------------------------------
TOKEN_SPEC = [
    ("SKIP", r"[ \t\r\n]+"),
    ("NUMBER", r"\d+(?:\.\d+)?"),
    ("STRING", r'"[^"\n]*"'),
    ("SLOT", r"\{[a-z_][a-z0-9_]*\}"),
    ("OP", r"==|!=|<=|>=|<|>|\+|-|\*|/|\(|\)|\[|\]|,"),
    ("IDENT", r"[a-z_][a-z0-9_]*"),
]
TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in TOKEN_SPEC))


class ExprError(Exception):
    pass


def tokenize_expr(expr: str) -> list[tuple[str, str]]:
    if len(expr) > 512:
        raise ExprError(f"E_DEPTH: Expression exceeds 512 chars ({len(expr)})")
    tokens: list[tuple[str, str]] = []
    pos = 0
    while pos < len(expr):
        m = TOKEN_RE.match(expr, pos)
        if not m:
            raise ExprError(f"E_LEX: Illegal character at position {pos} in {expr!r}")
        kind = m.lastgroup
        val = m.group()
        pos = m.end()
        if kind == "SKIP":
            continue
        tokens.append((kind, val))
    return tokens


class ExprValidator:
    def __init__(
        self,
        tokens: list[tuple[str, str]],
        params_meta: dict[str, dict],
        valid_flags: set[str],
        valid_mods: set[str],
        valid_events: set[str],
        event_slots: set[str],
        is_random: bool,
    ):
        self.tokens = tokens
        self.pos = 0
        self.params_meta = params_meta
        self.valid_flags = valid_flags
        self.valid_mods = valid_mods
        self.valid_events = valid_events
        self.event_slots = event_slots
        self.is_random = is_random
        self.param_cmp_count = 0

    def peek(self) -> tuple[str, str] | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def consume(self, expected_val: str | None = None) -> tuple[str, str]:
        tok = self.peek()
        if tok is None:
            raise ExprError("E_PARSE: Unexpected end of expression")
        if expected_val is not None and tok[1] != expected_val:
            raise ExprError(f"E_PARSE: Expected {expected_val!r}, got {tok[1]!r}")
        self.pos += 1
        return tok

    def parse(self) -> str:
        if not self.tokens:
            raise ExprError("E_PARSE: Empty expression")
        typ = self.parse_or()
        if self.peek() is not None:
            raise ExprError(f"E_PARSE: Unexpected trailing token {self.peek()!r}")
        return typ

    def parse_or(self) -> str:
        t = self.parse_and()
        while self.peek() and self.peek()[1] == "or":
            self.consume("or")
            r = self.parse_and()
            if t != "bool" or r != "bool":
                raise ExprError(f"E_TYPE: 'or' requires bool operands, got {t} and {r}")
        return t

    def parse_and(self) -> str:
        t = self.parse_not()
        while self.peek() and self.peek()[1] == "and":
            self.consume("and")
            r = self.parse_not()
            if t != "bool" or r != "bool":
                raise ExprError(f"E_TYPE: 'and' requires bool operands, got {t} and {r}")
        return t

    def parse_not(self) -> str:
        if self.peek() and self.peek()[1] == "not":
            self.consume("not")
            t = self.parse_not()
            if t != "bool":
                raise ExprError(f"E_TYPE: 'not' requires bool operand, got {t}")
            return "bool"
        return self.parse_cmp()

    def parse_cmp(self) -> str:
        lhs_t, lhs_is_param = self.parse_add()
        tok = self.peek()
        if tok and tok[1] in ("==", "!=", "<", "<=", ">", ">="):
            op = self.consume()[1]
            rhs_t, rhs_is_param = self.parse_add()
            if op in ("<", "<=", ">", ">="):
                if lhs_t != "number" or rhs_t != "number":
                    raise ExprError(f"E_TYPE: Comparison {op} requires number operands, got {lhs_t} and {rhs_t}")
            else:
                if lhs_t != rhs_t:
                    raise ExprError(f"E_TYPE: Equality {op} requires matching types, got {lhs_t} and {rhs_t}")
            if lhs_is_param or rhs_is_param:
                self.param_cmp_count += 1
            return "bool"
        return lhs_t

    def parse_add(self) -> tuple[str, bool]:
        t, is_p = self.parse_mul()
        while self.peek() and self.peek()[1] in ("+", "-"):
            self.consume()
            rt, r_p = self.parse_mul()
            if t != "number" or rt != "number":
                raise ExprError(f"E_TYPE: Arithmetic +/- requires number, got {t} and {rt}")
            is_p = is_p or r_p
        return t, is_p

    def parse_mul(self) -> tuple[str, bool]:
        t, is_p = self.parse_unary()
        while self.peek() and self.peek()[1] in ("*", "/"):
            self.consume()
            rt, r_p = self.parse_unary()
            if t != "number" or rt != "number":
                raise ExprError(f"E_TYPE: Arithmetic */ requires number, got {t} and {rt}")
            is_p = is_p or r_p
        return t, is_p

    def parse_unary(self) -> tuple[str, bool]:
        if self.peek() and self.peek()[1] == "-":
            self.consume("-")
            t, is_p = self.parse_unary()
            if t != "number":
                raise ExprError(f"E_TYPE: Unary '-' requires number, got {t}")
            return "number", is_p
        return self.parse_primary()

    def parse_primary(self) -> tuple[str, bool]:
        tok = self.peek()
        if tok is None:
            raise ExprError("E_PARSE: Unexpected end in primary")
        kind, val = tok
        if kind == "NUMBER":
            self.consume()
            return "number", False
        if kind == "STRING":
            self.consume()
            return "string", False
        if kind == "SLOT":
            self.consume()
            slot_name = val[1:-1]
            if slot_name != "self" and slot_name not in self.event_slots:
                raise ExprError(f"E_SLOT: Undefined slot {val}")
            return "string", False
        if val in ("true", "false"):
            self.consume()
            return "bool", False
        if val == "(":
            self.consume("(")
            t = self.parse_or()
            self.consume(")")
            return t, False
        if kind == "IDENT":
            self.consume()
            # Function call?
            if self.peek() and self.peek()[1] == "(":
                self.consume("(")
                args: list[tuple[str, str]] = []
                if self.peek() and self.peek()[1] != ")":
                    while True:
                        arg_start = self.pos
                        arg_t = self.parse_or()
                        arg_raw = self.tokens[arg_start][1] if self.pos == arg_start + 1 else ""
                        args.append((arg_t, arg_raw))
                        if self.peek() and self.peek()[1] == ",":
                            self.consume(",")
                        else:
                            break
                self.consume(")")
                return self.check_call(val, args), False

            # Built-in variables
            if val in ("year", "month", "day"):
                return "number", False
            if val == "k":
                return "number", False

            # Parameter reference
            if val not in self.params_meta:
                raise ExprError(f"E_REF: Unknown identifier or parameter {val!r}")
            pmeta = self.params_meta[val]
            scope = pmeta["scope"]
            has_bracket = bool(self.peek() and self.peek()[1] == "[")
            if scope == "national" and has_bracket:
                raise ExprError(f"E_KEY: National parameter {val!r} must not take a key")
            if scope != "national" and not has_bracket:
                raise ExprError(f"E_KEY: Scoped parameter {val!r} (scope={scope}) requires a [key]")
            if has_bracket:
                self.consume("[")
                ktok = self.consume()
                self.consume("]")
                if ktok[0] == "SLOT":
                    sname = ktok[1][1:-1]
                    if sname not in self.event_slots:
                        raise ExprError(f"E_SLOT: Undefined slot {ktok[1]} in {val}[{ktok[1]}]")
                elif ktok[0] != "IDENT":
                    raise ExprError(f"E_KEY: Invalid key token {ktok} for {val}")
            return "number", True

        raise ExprError(f"E_PARSE: Unexpected token {tok!r}")

    def check_call(self, fn: str, args: list[tuple[str, str]]) -> str:
        if fn == "flag":
            if len(args) != 1 or args[0][0] != "string":
                raise ExprError("E_ARITY/E_TYPE: flag(s) expects 1 string")
            fid = args[0][1].strip('"')
            if fid not in self.valid_flags:
                raise ExprError(f"E_REF: Unknown flag {fid!r} in flag()")
            return "bool"
        if fn == "has_modifier":
            if len(args) not in (1, 2) or args[0][0] != "string":
                raise ExprError("E_ARITY/E_TYPE: has_modifier expects 1 or 2 strings")
            mid = args[0][1].strip('"')
            if mid not in self.valid_mods:
                raise ExprError(f"E_REF: Unknown modifier {mid!r} in has_modifier()")
            return "bool"
        if fn in ("event_done", "event", "event_choice"):
            if len(args) != 1 or args[0][0] != "string":
                raise ExprError(f"E_ARITY/E_TYPE: {fn}(s) expects 1 string")
            return "bool" if fn == "event_done" else ("number" if fn == "event" else "string")
        if fn in ("months_since", "days_since", "floor", "abs"):
            if len(args) != 1 or args[0][0] != "number":
                raise ExprError(f"E_ARITY/E_TYPE: {fn}(n) expects 1 number")
            return "number"
        if fn in ("character_in_office", "character_alive", "region_exists"):
            if len(args) != 1 or args[0][0] != "string":
                raise ExprError(f"E_ARITY/E_TYPE: {fn}(s) expects 1 string")
            return "bool"
        if fn == "at_war":
            if len(args) > 1 or (len(args) == 1 and args[0][0] != "string"):
                raise ExprError("E_ARITY/E_TYPE: at_war([s]) expects 0 or 1 string")
            return "bool"
        if fn == "scenario":
            if len(args) != 0:
                raise ExprError("E_ARITY: scenario() takes 0 args")
            return "string"
        if fn in ("era", "term_months"):
            if len(args) != 0:
                raise ExprError(f"E_ARITY: {fn}() takes 0 args")
            return "number"
        if fn == "repeat_count":
            if len(args) != 1 or args[0][0] != "string":
                raise ExprError("E_ARITY/E_TYPE: repeat_count(s) expects 1 string")
            return "number"
        if fn == "slot":
            if len(args) != 1 or args[0][0] != "string":
                raise ExprError("E_ARITY/E_TYPE: slot(s) expects 1 string")
            return "string"
        if fn == "party_has_tag":
            if len(args) != 2 or args[0][0] != "string" or args[1][0] != "string":
                raise ExprError("E_ARITY/E_TYPE: party_has_tag(p, t) expects 2 strings")
            return "bool"
        if fn in ("min", "max"):
            if len(args) < 2 or any(a[0] != "number" for a in args):
                raise ExprError(f"E_ARITY/E_TYPE: {fn} expects >=2 numbers")
            return "number"
        if fn == "clamp":
            if len(args) != 3 or any(a[0] != "number" for a in args):
                raise ExprError("E_ARITY/E_TYPE: clamp expects 3 numbers")
            return "number"
        raise ExprError(f"E_REF: Unknown function {fn!r}")


def main() -> int:
    errors: list[str] = []

    # 1. Load registries
    params_doc = yaml.safe_load(PARAMS_PATH.read_text(encoding="utf-8"))
    flags_doc = yaml.safe_load(FLAGS_PATH.read_text(encoding="utf-8"))
    mods_doc = yaml.safe_load(MODS_PATH.read_text(encoding="utf-8"))

    params_meta: dict[str, dict] = {}
    for p in params_doc.get("parameters", []):
        params_meta[p["id"]] = p

    valid_flags: set[str] = set()
    for f in flags_doc.get("flags", []):
        if "id" not in f or not re.match(r"^[a-z0-9_]+$", f["id"]):
            errors.append(f"[REGISTRY] Invalid or missing snake_case id in flags.yaml: {f}")
        else:
            valid_flags.add(f["id"])
        if not f.get("set_by") or not f.get("read_by"):
            errors.append(f"[REGISTRY] Orphan flag in flags.yaml: {f.get('id')} ({f.get('name_zh')})")
    for alias, target in flags_doc.get("flag_aliases", {}).items():
        valid_flags.add(alias)
        if target not in valid_flags:
            errors.append(f"[REGISTRY] flag_alias {alias!r} points to unknown flag {target!r}")

    valid_mods: set[str] = set()
    for m in mods_doc.get("modifiers", []):
        if "id" not in m or not re.match(r"^[a-z0-9_]+$", m["id"]):
            errors.append(f"[REGISTRY] Invalid or missing snake_case id in modifiers.yaml: {m.get('name_zh')}")
        else:
            valid_mods.add(m["id"])
        has_effect = bool(
            m.get("edges")
            or m.get("factors")
            or m.get("monthly_effects")
            or m.get("option_tag_effects")
            or m.get("event_prob_add")
        )
        if not has_effect:
            errors.append(f"[REGISTRY] Empty-shell modifier in modifiers.yaml: {m.get('id')} ({m.get('name_zh')})")
    for alias, target in mods_doc.get("modifier_aliases", {}).items():
        valid_mods.add(alias)

    # 2. Load all 6 event YAML files & check global ID uniqueness
    all_events: list[tuple[str, dict]] = []
    seen_ids: dict[str, str] = {}

    for fname in EXPECTED_FILES:
        fpath = EVENTS_DIR / fname
        if not fpath.exists():
            errors.append(f"[FILE] Missing compiled YAML file: {fpath}")
            continue
        doc = yaml.safe_load(fpath.read_text(encoding="utf-8"))
        for ev in doc.get("events", []):
            eid = ev.get("id", "")
            if not eid:
                errors.append(f"[{fname}] Event missing id")
                continue
            if eid in seen_ids:
                errors.append(f"[V-03] Duplicate event ID {eid} in {fname} and {seen_ids[eid]}")
            seen_ids[eid] = fname
            all_events.append((fname, ev))

    valid_events = set(seen_ids.keys())

    # 3. Validate each event
    def check_expr(
        expr_str: str,
        expected_type: str,
        ctx: str,
        event_slots: set[str],
        is_random: bool,
        require_param_cmp: bool = False,
        forbid_param_cmp: bool = False,
    ) -> None:
        try:
            tokens = tokenize_expr(str(expr_str))
            v = ExprValidator(tokens, params_meta, valid_flags, valid_mods, valid_events, event_slots, is_random)
            actual_type = v.parse()
            if actual_type != expected_type:
                errors.append(f"[{ctx}] E_TYPE: Expected {expected_type}, got {actual_type} in {expr_str!r}")
            if require_param_cmp and v.param_cmp_count < 1:
                errors.append(f"[{ctx}] V-05: Fixed event condition must contain >=1 parameter comparison: {expr_str!r}")
            if forbid_param_cmp and v.param_cmp_count > 0:
                errors.append(f"[{ctx}] V-11: Random event prerequisites must not compare parameters: {expr_str!r}")
        except ExprError as exc:
            errors.append(f"[{ctx}] {exc} in {expr_str!r}")

    def check_effects(eff_list: list[dict], ctx: str, event_slots: set[str]) -> None:
        if not isinstance(eff_list, list) or not eff_list:
            errors.append(f"[{ctx}] Effects list must be non-empty")
            return
        for idx, eff in enumerate(eff_list):
            op = eff.get("op")
            ectx = f"{ctx}.effects[{idx}]"
            if op in ("add", "set", "mul"):
                target = eff.get("target")
                if target not in params_meta:
                    errors.append(f"[{ectx}] V-06: Unknown target parameter {target!r}")
                    continue
                pmeta = params_meta[target]
                if pmeta.get("type") == "derived":
                    errors.append(f"[{ectx}] V-07: Derived parameter {target!r} cannot be an effect target")
                scope = pmeta.get("scope")
                has_key = "key" in eff and eff["key"] is not None
                if scope == "national" and has_key:
                    errors.append(f"[{ectx}] National parameter {target!r} must not have key")
                if scope != "national" and not has_key:
                    errors.append(f"[{ectx}] Scoped parameter {target!r} (scope={scope}) missing key")
                if has_key and isinstance(eff["key"], str) and eff["key"].startswith("{"):
                    sname = eff["key"][1:-1]
                    if sname not in event_slots:
                        errors.append(f"[{ectx}] Undefined slot {eff['key']} in effect key")
            elif op in ("set_flag", "clear_flag"):
                flg = eff.get("flag")
                if flg not in valid_flags:
                    errors.append(f"[{ectx}] V-08: Unknown flag {flg!r} not in flags.yaml")
            elif op in ("add_modifier", "remove_modifier"):
                mod = eff.get("modifier")
                if mod not in valid_mods:
                    errors.append(f"[{ectx}] V-08: Unknown modifier {mod!r} not in modifiers.yaml")
            elif op in ("trigger_event", "schedule_event", "event_multiplier"):
                ev_ref = eff.get("event")
                if not ev_ref:
                    errors.append(f"[{ectx}] Missing event field for op={op}")
            elif op == "custom":
                handler = eff.get("handler")
                if not handler:
                    errors.append(f"[{ectx}] Missing handler for op=custom")
                if handler == "stance_shift_by_corridor":
                    if eff.get("key") not in ("territory", "security", "economy", "religion", "foreign"):
                        errors.append(f"[{ectx}] Invalid axis key {eff.get('key')!r} for stance_shift_by_corridor")
            elif op == "random_branch":
                for b in eff.get("branches", []):
                    check_effects(b.get("effects", []), f"{ectx}.branch", event_slots)
            elif op == "if":
                check_expr(eff.get("cond", ""), "bool", f"{ectx}.cond", event_slots, False)
                check_effects(eff.get("then", []), f"{ectx}.then", event_slots)
            else:
                errors.append(f"[{ectx}] Unknown effect op {op!r}")

    def check_ai_tone(text: str, ctx: str) -> None:
        if not text:
            return
        for pid, pat in AI_TONE_PATTERNS.items():
            m = re.search(pat, text)
            if m:
                errors.append(f"[{ctx}] V-22 Anti-AI-Tone violation ({pid}): {m.group(0)!r}")

    for fname, ev in all_events:
        eid = ev["id"]
        kind = ev.get("kind")
        ctx = f"{fname}:{eid}"

        if kind == "fixed":
            if not re.match(r"^E-(\d{4}-\d{2}[a-z]?|G0[1-5]-\d{2})$", eid):
                errors.append(f"[{ctx}] V-02: Invalid FixedEvent ID format {eid!r}")
            trig = ev.get("trigger", {})
            check_expr(trig.get("prerequisites", "true"), "bool", f"{ctx}.prerequisites", set(), False)
            check_expr(trig.get("condition", ""), "bool", f"{ctx}.condition", set(), False, require_param_cmp=True)
            check_expr(trig.get("invalidation", "false"), "bool", f"{ctx}.invalidation", set(), False)
            prob = trig.get("probability", {})
            for add_item in prob.get("add", []):
                if "when" in add_item:
                    check_expr(add_item["when"], "bool", f"{ctx}.prob.when", set(), False)
                if "expr" in add_item:
                    check_expr(add_item["expr"], "number", f"{ctx}.prob.expr", set(), False)
            if "on_miss" in trig and trig["on_miss"].get("effects"):
                check_effects(trig["on_miss"]["effects"], f"{ctx}.on_miss", set())

            if ev.get("major") and len(ev.get("perspectives", [])) < 3:
                errors.append(f"[{ctx}] V-09: Major event must have >=3 perspectives")

            form = ev.get("form")
            if form in ("choice", "predecision"):
                opts = ev.get("options", [])
                if not opts:
                    errors.append(f"[{ctx}] Choice/predecision event has no options")
                for opt in opts:
                    octx = f"{ctx}.opt[{opt.get('id')}]"
                    check_expr(opt.get("requires", "true"), "bool", f"{octx}.requires", set(), False)
                    check_effects(opt.get("effects", []), octx, set())
                    check_ai_tone(opt.get("title", ""), f"{octx}.title")
                    check_ai_tone(opt.get("label", ""), f"{octx}.label")
                    if form == "predecision":
                        rh = opt.get("risk_hint")
                        mult_effs = [e for e in opt.get("effects", []) if e.get("op") == "event_multiplier"]
                        if not mult_effs or rh not in ("低", "中", "高"):
                            errors.append(f"[{octx}] V-14: predecision option missing event_multiplier or risk_hint")
                        else:
                            mv = mult_effs[0]["value"]
                            expected_rh = "低" if mv <= 0.25 else ("中" if mv <= 0.60 else "高")
                            if rh != expected_rh:
                                errors.append(f"[{octx}] V-14: risk_hint {rh!r} mismatches multiplier {mv}")
            else:
                check_effects(ev.get("passive_effects", []), f"{ctx}.passive", set())

        elif kind == "random":
            if not re.match(r"^R-\d{2}[a-z]?$", eid):
                errors.append(f"[{ctx}] V-02: Invalid RandomEvent ID format {eid!r}")
            slots_set = set(ev.get("slots", {}).keys())
            check_expr(ev.get("prerequisites", "true"), "bool", f"{ctx}.prerequisites", slots_set, True, forbid_param_cmp=True)
            scale_obj = ev.get("scale", {})
            check_expr(scale_obj.get("expr", "1"), "number", f"{ctx}.scale.expr", slots_set, True)
            for term in scale_obj.get("terms", []):
                check_expr(term.get("when", "true"), "bool", f"{ctx}.scale.term", slots_set, True)
            if len(ev.get("variants", [])) < 3:
                errors.append(f"[{ctx}] V-12: Random event must have >=3 variants")
            for v in ev.get("variants", []):
                check_expr(v.get("when", "true"), "bool", f"{ctx}.variant.when", slots_set, True)
                check_ai_tone(v.get("background", ""), f"{ctx}.variant.background")
            if len(ev.get("repeat_changes", [])) < 1:
                errors.append(f"[{ctx}] V-13: Random event must have >=1 repeat_changes")
            for rc in ev.get("repeat_changes", []):
                check_ai_tone(rc.get("background_prefix", ""), f"{ctx}.repeat.bg")
                check_effects(rc.get("extra_effects", []), f"{ctx}.repeat", slots_set)
            for evar in ev.get("era_variants", []):
                check_expr(evar.get("when", "true"), "bool", f"{ctx}.era_variant.when", slots_set, True)
                check_ai_tone(evar.get("background_suffix", ""), f"{ctx}.era_variant.bg")

            if ev.get("form") == "choice":
                for opt in ev.get("options", []):
                    octx = f"{ctx}.opt[{opt.get('id')}]"
                    check_effects(opt.get("effects", []), octx, slots_set)
                    check_ai_tone(opt.get("title", ""), f"{octx}.title")
                    check_ai_tone(opt.get("label", ""), f"{octx}.label")
            else:
                check_effects(ev.get("passive_effects", []), f"{ctx}.passive", slots_set)

            if "followup_choice" in ev and ev["followup_choice"]:
                fu = ev["followup_choice"]
                check_expr(fu.get("condition", "true"), "bool", f"{ctx}.followup.cond", slots_set, True)
                for opt in fu.get("options", []):
                    check_effects(opt.get("effects", []), f"{ctx}.followup.opt[{opt.get('id')}]", slots_set)
                    check_ai_tone(opt.get("label", ""), f"{ctx}.followup.opt.label")

        check_ai_tone(ev.get("title", ""), f"{ctx}.title")
        check_ai_tone(ev.get("background", ""), f"{ctx}.background")
        check_ai_tone(ev.get("narrative", ""), f"{ctx}.narrative")
        check_ai_tone(ev.get("summary", ""), f"{ctx}.summary")
        for p in ev.get("perspectives", []):
            check_ai_tone(p.get("label", ""), f"{ctx}.persp.label")
            check_ai_tone(p.get("text", ""), f"{ctx}.persp.text")

    if errors:
        print(f"VALIDATION FAILED with {len(errors)} errors:")
        for e in errors[:50]:
            print("  ERROR:", e)
        return 1

    print("============================================================")
    print("ALL STATIC VALIDATIONS PASSED (0 ERRORS)!")
    print(f"  - Validated {len(all_events)} compiled events across {len(EXPECTED_FILES)} YAML files")
    print(f"  - Validated {len(flags_doc.get('flags', []))} flags in flags.yaml (0 orphans)")
    print(f"  - Validated {len(mods_doc.get('modifiers', []))} modifiers in modifiers.yaml (0 empty shells)")
    print("  - All M12 §4.4 expressions, V-05/V-07/V-11/V-14 rules, D-050 custom handlers, and §4.8 anti-AI-tone checks passed.")
    print("============================================================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
