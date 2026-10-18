from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union


class ExprError(Exception):
    pass


# Tokenizer regex supporting numbers, strings, 2-char operators, brackets, and identifiers
_TOKEN_SPEC = [
    ("NUMBER", r"\d+(?:\.\d+)?"),
    ("STRING", r"'[^']*'|\"[^\"]*\""),
    ("OP2", r"==|!=|<=|>=|\*\*"),
    ("OP1", r"[+\-*/(),<>\[\]!]"),
    ("IDENT", r"\{?[A-Za-z_][A-Za-z0-9_.]*\}?"),
    ("SKIP", r"[ \t\r\n]+"),
]
_TOKEN_RE = re.compile("|".join(f"(?P<{name}>{pat})" for name, pat in _TOKEN_SPEC))


class Token:
    __slots__ = ("kind", "value", "pos")

    def __init__(self, kind: str, value: Any, pos: int) -> None:
        self.kind = kind
        self.value = value
        self.pos = pos

    def __repr__(self) -> str:
        return f"Token({self.kind!r}, {self.value!r})"


def tokenize(expr_str: str) -> List[Token]:
    tokens: List[Token] = []
    pos = 0
    n = len(expr_str)
    while pos < n:
        m = _TOKEN_RE.match(expr_str, pos)
        if not m:
            raise ExprError(f"Unexpected character at pos {pos} in {expr_str!r}: {expr_str[pos:pos+12]!r}")
        kind = m.lastgroup
        val = m.group()
        if kind == "SKIP":
            pos = m.end()
            continue
        elif kind == "NUMBER":
            tokens.append(Token("NUMBER", float(val) if "." in val else int(val), pos))
        elif kind == "STRING":
            tokens.append(Token("STRING", val[1:-1], pos))
        elif kind == "IDENT":
            if val in ("true", "True"):
                tokens.append(Token("BOOL", True, pos))
            elif val in ("false", "False"):
                tokens.append(Token("BOOL", False, pos))
            elif val in ("null", "None"):
                tokens.append(Token("NULL", None, pos))
            elif val in ("and", "or", "not", "in"):
                tokens.append(Token("KW", val, pos))
            else:
                tokens.append(Token("IDENT", val, pos))
        else:
            if val == "!":
                tokens.append(Token("KW", "not", pos))
            else:
                tokens.append(Token("OP", val, pos))
        pos = m.end()
    tokens.append(Token("EOF", None, pos))
    return tokens


class ASTNode:
    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        raise NotImplementedError


class LiteralNode(ASTNode):
    __slots__ = ("value",)

    def __init__(self, value: Any) -> None:
        self.value = value

    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        if isinstance(self.value, str) and "{" in self.value and ctx:
            return _interpolate_str(self.value, ctx)
        return self.value


class IdentNode(ASTNode):
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        return _resolve_ident(self.name, None, state, ctx)


class IndexNode(ASTNode):
    __slots__ = ("base_name", "key_node")

    def __init__(self, base_name: str, key_node: ASTNode) -> None:
        self.base_name = base_name
        self.key_node = key_node

    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        if isinstance(self.key_node, IdentNode):
            # In `relation[dayan]` or `alienation[mizrahi]`, unquoted ident inside brackets is a key literal unless in ctx
            k_name = self.key_node.name
            key_val = str(ctx.get(k_name, k_name))
        else:
            key_val = str(self.key_node.eval(state, ctx))
        key_val = _interpolate_str(key_val, ctx)
        return _resolve_ident(self.base_name, key_val, state, ctx)


class ListNode(ASTNode):
    __slots__ = ("items",)

    def __init__(self, items: List[ASTNode]) -> None:
        self.items = items

    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        res = []
        for item in self.items:
            if isinstance(item, IdentNode) and item.name not in ctx:
                res.append(item.name)
            else:
                res.append(item.eval(state, ctx))
        return res


class UnaryNode(ASTNode):
    __slots__ = ("op", "operand")

    def __init__(self, op: str, operand: ASTNode) -> None:
        self.op = op
        self.operand = operand

    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        val = self.operand.eval(state, ctx)
        if self.op == "not":
            return not bool(val)
        elif self.op == "-":
            return -float(val or 0.0)
        elif self.op == "+":
            return float(val or 0.0)
        raise ExprError(f"Unknown unary op: {self.op}")


class BinaryNode(ASTNode):
    __slots__ = ("op", "left", "right")

    def __init__(self, op: str, left: ASTNode, right: ASTNode) -> None:
        self.op = op
        self.left = left
        self.right = right

    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        op = self.op
        if op == "and":
            return bool(self.left.eval(state, ctx)) and bool(self.right.eval(state, ctx))
        if op == "or":
            return bool(self.left.eval(state, ctx)) or bool(self.right.eval(state, ctx))

        lval = self.left.eval(state, ctx)
        rval = self.right.eval(state, ctx)

        if op == "in":
            if isinstance(rval, (list, tuple, set, dict, str)):
                return lval in rval
            return False
        if op == "not in":
            if isinstance(rval, (list, tuple, set, dict, str)):
                return lval not in rval
            return True
        if op == "==":
            return lval == rval or str(lval) == str(rval)
        if op == "!=":
            return lval != rval and str(lval) != str(rval)

        if op in ("<", "<=", ">", ">="):
            if lval is None or rval is None:
                return False
            try:
                lf = float(lval)
                rf = float(rval)
                if op == "<":
                    return lf < rf
                if op == "<=":
                    return lf <= rf
                if op == ">":
                    return lf > rf
                if op == ">=":
                    return lf >= rf
            except (TypeError, ValueError):
                return str(lval) < str(rval) if op == "<" else False

        lf = float(lval or 0.0)
        rf = float(rval or 0.0)
        if op == "+":
            return lf + rf
        if op == "-":
            return lf - rf
        if op == "*":
            return lf * rf
        if op == "/":
            return lf / rf if abs(rf) > 1e-12 else 0.0
        if op == "**":
            return math.pow(lf, rf)
        raise ExprError(f"Unknown binary op: {op}")


class CallNode(ASTNode):
    __slots__ = ("func_name", "args")

    def __init__(self, func_name: str, args: List[ASTNode]) -> None:
        self.func_name = func_name
        self.args = args

    def eval(self, state: Any, ctx: Dict[str, Any]) -> Any:
        eval_args: List[Any] = []
        for a in self.args:
            # In functions likecharacter_in_office(dayan) or party_in_coalition(nrp), unquoted ident is an entity ID string if not a numeric param
            if isinstance(a, IdentNode) and self.func_name not in ("min", "max", "clamp", "floor", "abs", "round", "ceil", "sqrt", "pow", "months_since", "days_since"):
                if a.name in ctx:
                    eval_args.append(ctx[a.name])
                else:
                    eval_args.append(a.name)
            else:
                eval_args.append(a.eval(state, ctx))
        return _eval_builtin(self.func_name, eval_args, state, ctx)


class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.pos = 0

    def peek(self, offset: int = 0) -> Token:
        idx = min(len(self.tokens) - 1, self.pos + offset)
        return self.tokens[idx]

    def consume(self, expected_kind: Optional[str] = None, expected_val: Optional[Any] = None) -> Token:
        tok = self.tokens[self.pos]
        if expected_kind and tok.kind != expected_kind:
            raise ExprError(f"Expected {expected_kind}, got {tok}")
        if expected_val is not None and tok.value != expected_val:
            raise ExprError(f"Expected {expected_val}, got {tok}")
        self.pos += 1
        return tok

    def parse(self) -> ASTNode:
        if self.peek().kind == "EOF":
            return LiteralNode(True)
        node = self.parse_or()
        if self.peek().kind != "EOF":
            raise ExprError(f"Unexpected trailing token: {self.peek()}")
        return node

    def parse_or(self) -> ASTNode:
        node = self.parse_and()
        while self.peek().kind == "KW" and self.peek().value == "or":
            self.consume()
            right = self.parse_and()
            node = BinaryNode("or", node, right)
        return node

    def parse_and(self) -> ASTNode:
        node = self.parse_not()
        while self.peek().kind == "KW" and self.peek().value == "and":
            self.consume()
            right = self.parse_not()
            node = BinaryNode("and", node, right)
        return node

    def parse_not(self) -> ASTNode:
        if self.peek().kind == "KW" and self.peek().value == "not":
            if self.peek(1).kind == "KW" and self.peek(1).value == "in":
                return self.parse_comparison()
            self.consume()
            return UnaryNode("not", self.parse_not())
        return self.parse_comparison()

    def parse_comparison(self) -> ASTNode:
        node = self.parse_additive()
        while True:
            tok = self.peek()
            if tok.kind == "OP" and tok.value in ("==", "!=", "<", "<=", ">", ">="):
                self.consume()
                right = self.parse_additive()
                node = BinaryNode(tok.value, node, right)
            elif tok.kind == "KW" and tok.value == "in":
                self.consume()
                right = self.parse_additive()
                node = BinaryNode("in", node, right)
            elif tok.kind == "KW" and tok.value == "not" and self.peek(1).kind == "KW" and self.peek(1).value == "in":
                self.consume()
                self.consume()
                right = self.parse_additive()
                node = BinaryNode("not in", node, right)
            else:
                break
        return node

    def parse_additive(self) -> ASTNode:
        node = self.parse_multiplicative()
        while self.peek().kind == "OP" and self.peek().value in ("+", "-"):
            op = self.consume().value
            right = self.parse_multiplicative()
            node = BinaryNode(op, node, right)
        return node

    def parse_multiplicative(self) -> ASTNode:
        node = self.parse_power()
        while self.peek().kind == "OP" and self.peek().value in ("*", "/"):
            op = self.consume().value
            right = self.parse_power()
            node = BinaryNode(op, node, right)
        return node

    def parse_power(self) -> ASTNode:
        node = self.parse_unary()
        if self.peek().kind == "OP" and self.peek().value == "**":
            self.consume()
            right = self.parse_power()
            node = BinaryNode("**", node, right)
        return node

    def parse_unary(self) -> ASTNode:
        if self.peek().kind == "OP" and self.peek().value in ("+", "-"):
            op = self.consume().value
            return UnaryNode(op, self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        tok = self.peek()
        if tok.kind == "OP" and tok.value == "(":
            self.consume()
            node = self.parse_or()
            self.consume("OP", ")")
            return node
        if tok.kind == "OP" and tok.value == "[":
            self.consume()
            items: List[ASTNode] = []
            if not (self.peek().kind == "OP" and self.peek().value == "]"):
                items.append(self.parse_or())
                while self.peek().kind == "OP" and self.peek().value == ",":
                    self.consume()
                    items.append(self.parse_or())
            self.consume("OP", "]")
            return ListNode(items)
        if tok.kind in ("NUMBER", "STRING", "BOOL", "NULL"):
            self.consume()
            return LiteralNode(tok.value)
        if tok.kind == "IDENT":
            ident = self.consume().value
            if self.peek().kind == "OP" and self.peek().value == "(":
                self.consume()
                args: List[ASTNode] = []
                if not (self.peek().kind == "OP" and self.peek().value == ")"):
                    args.append(self.parse_or())
                    while self.peek().kind == "OP" and self.peek().value == ",":
                        self.consume()
                        args.append(self.parse_or())
                self.consume("OP", ")")
                return CallNode(ident, args)
            if self.peek().kind == "OP" and self.peek().value == "[":
                self.consume()
                key_node = self.parse_or()
                self.consume("OP", "]")
                return IndexNode(ident, key_node)
            return IdentNode(ident)
        raise ExprError(f"Unexpected token in primary: {tok}")


_AST_CACHE: Dict[str, ASTNode] = {}


def _interpolate_str(s: str, ctx: Dict[str, Any]) -> str:
    if "{" not in s or not ctx:
        return s
    out = s
    for k, v in ctx.items():
        if f"{{{k}}}" in out:
            out = out.replace(f"{{{k}}}", str(v))
    return out


def compile_expr(expr_str: str) -> ASTNode:
    s = (expr_str or "").strip()
    if not s:
        return LiteralNode(True)
    cached = _AST_CACHE.get(s)
    if cached is not None:
        return cached
    tokens = tokenize(s)
    ast = Parser(tokens).parse()
    _AST_CACHE[s] = ast
    return ast


def eval_expr(expr_str: Union[str, bool, int, float, None], state: Any, ctx: Optional[Dict[str, Any]] = None) -> Any:
    if expr_str is None or expr_str == "":
        return True
    if isinstance(expr_str, (bool, int, float)):
        return expr_str
    s = _interpolate_str(str(expr_str), ctx or {})
    ast = compile_expr(s)
    return ast.eval(state, ctx or {})


def eval_bool(expr_str: Union[str, bool, int, float, None], state: Any, ctx: Optional[Dict[str, Any]] = None) -> bool:
    try:
        return bool(eval_expr(expr_str, state, ctx))
    except Exception:
        return False


def eval_float(expr_str: Union[str, bool, int, float, None], state: Any, ctx: Optional[Dict[str, Any]] = None) -> float:
    val = eval_expr(expr_str, state, ctx)
    if val is None:
        return 0.0
    return float(val)


def _resolve_ident(name: str, key: Optional[str], state: Any, ctx: Dict[str, Any]) -> Any:
    if key is None and name in ctx:
        return ctx[name]
    if state is None:
        return 0.0 if key is not None else name

    # Built-in read-only variables (contracts.md §5.1)
    if key is None:
        if name == "year":
            return state.year
        if name == "month":
            return state.month
        if name == "day":
            return state.day
        if name == "day_index":
            return state.day_index
        if name == "leader_id":
            return state.player.get("leader_id", "begin")
        if name == "party_id":
            return state.player.get("party_id", "likud")
        if name == "k":
            return float(ctx.get("k", 1.0))
        if name == "end_reason":
            return str(ctx.get("end_reason", state.pending.get("tenure_end", "") or ""))

    # Dotted syntax e.g. bloc_support.mizrahi
    if key is None and "." in name:
        parts = name.split(".", 1)
        return state.get_param(parts[0], parts[1])

    # Parameter lookup via state.get_param
    if key is not None:
        return state.get_param(name, key)

    if name in state.params or name in ("voter_cynicism", "security_index", "country_stability", "country_nuclear_progress", "annual_immigration", "palestinian_hostility", "intifada_risk", "us_stance", "islamic_assoc_strength"):
        val = state.get_param(name)
        return val

    return name


def _eval_builtin(func_name: str, args: List[Any], state: Any, ctx: Dict[str, Any]) -> Any:
    # Math functions (contracts.md §5.2)
    if func_name == "min":
        return min(float(a or 0.0) for a in args) if args else 0.0
    if func_name == "max":
        return max(float(a or 0.0) for a in args) if args else 0.0
    if func_name == "clamp":
        if len(args) < 3:
            return float(args[0] if args else 0.0)
        return max(float(args[1] or 0.0), min(float(args[2] or 0.0), float(args[0] or 0.0)))
    if func_name == "floor":
        return float(math.floor(float(args[0] or 0.0))) if args else 0.0
    if func_name == "ceil":
        return float(math.ceil(float(args[0] or 0.0))) if args else 0.0
    if func_name == "round":
        return float(round(float(args[0] or 0.0))) if args else 0.0
    if func_name == "abs":
        return abs(float(args[0] or 0.0)) if args else 0.0
    if func_name == "sqrt":
        return math.sqrt(max(0.0, float(args[0] or 0.0))) if args else 0.0
    if func_name == "pow":
        return math.pow(float(args[0] or 0.0), float(args[1] or 0.0)) if len(args) >= 2 else 0.0

    if state is None:
        return False

    # Flag & Modifier queries
    if func_name == "flag":
        f_id = str(args[0]) if args else ""
        if f_id.startswith("thr."):
            t_id = f_id[4:]
            thr = state.m02.get("thresholds", {}).get(t_id, {})
            if thr.get("state") == "on":
                return True
        return state.has_flag(f_id)

    if func_name == "has_modifier":
        m_id = str(args[0]) if args else ""
        k = str(args[1]) if len(args) >= 2 else None
        return state.has_modifier(m_id, k)

    # Event queries (M12)
    if func_name in ("event_done", "event_fired"):
        ev_id = str(args[0]) if args else ""
        return ev_id in state.m12.get("fired", {}) or state.m12.get("status", {}).get(ev_id) == "RESOLVED"

    if func_name == "event":
        ev_id = str(args[0]) if args else ""
        fired = state.m12.get("fired", {})
        if ev_id in fired:
            info = fired[ev_id]
            return int(info.get("day_index", info)) if isinstance(info, dict) else int(info)
        return -1

    if func_name == "event_choice":
        ev_id = str(args[0]) if args else ""
        fired = state.m12.get("fired", {})
        if ev_id in fired and isinstance(fired[ev_id], dict):
            return str(fired[ev_id].get("choice", ""))
        return ""

    if func_name == "months_since":
        d = int(args[0]) if args else -1
        if d < 0:
            return 9999
        return max(0, (state.day_index - d) // 30)

    if func_name in ("days_since", "days_since_event"):
        if not args:
            return 999999
        if isinstance(args[0], str) and not args[0].lstrip("-").isdigit():
            ev_id = args[0]
            fired = state.m12.get("fired", {})
            if ev_id not in fired:
                return 999999
            info = fired[ev_id]
            d = int(info.get("day_index", info)) if isinstance(info, dict) else int(info)
        else:
            d = int(args[0])
        if d < 0:
            return 999999
        return max(0, state.day_index - d)

    if func_name == "scenario":
        return state.scenario_id

    if func_name == "era":
        return state.era_number()

    if func_name == "repeat_count":
        ev_id = str(args[0]) if args else ""
        return int(state.m12.get("counts_term", {}).get(ev_id, 0))

    if func_name in ("slot", "arg"):
        k = str(args[0]) if args else ""
        return str(ctx.get(k, ""))

    # M03 Parliament queries
    if func_name == "term_months":
        start_d = int(state.run.get("tenure_start_day", 0))
        return max(0, (state.day_index - start_d) // 30)

    if func_name in ("days_to_election", "days_until_election"):
        months_left = float(state.get_param("months_to_election"))
        next_day = int(state.parliament.get("next_election_day", state.day_index + int(months_left * 30)))
        return max(0, next_day - state.day_index)

    if func_name == "party_seats":
        pid = str(args[0]) if args else ""
        return int(round(state.get_param("knesset_seats", pid)))

    if func_name in ("party_in_coalition", "in_coalition"):
        pid = str(args[0]) if args else ""
        from sim.state import resolve_party_id
        canon = resolve_party_id(pid)
        coal = state.parliament.get("coalition_parties", ["likud", "nrp", "agudat"])
        if isinstance(coal, list) and canon in coal:
            return True
        p_obj = state.parliament.get("parties", {}).get(canon, {})
        return bool(p_obj.get("in_coalition", canon == state.player.get("party_id")))

    if func_name == "party_has_tag":
        pid = str(args[0]) if args else ""
        tag = str(args[1]) if len(args) >= 2 else ""
        return state.party_has_tag(pid, tag)

    # M04 Party & Corridor queries
    if func_name == "party_stage":
        return int(state.party_state.get("crisis_stage", 0))

    if func_name == "promise_active":
        pr_id = str(args[0]) if args else ""
        for p in state.promises:
            if p.get("id") == pr_id:
                return bool(p.get("active", True)) and not bool(p.get("renounced", False))
        return False

    if func_name == "vision_milestone_done":
        ms_id = str(args[0]) if args else ""
        ms_list = state.vision.get("milestones", [])
        for m in ms_list:
            if isinstance(m, dict) and m.get("id") == ms_id:
                return bool(m.get("done", m.get("completed", False)))
        return state.has_flag(f"vision_ms_{ms_id}")

    if func_name == "corridor_lo":
        ax = str(args[0]) if args else "territory"
        party = state.player.get("party_id", "likud")
        p_corr = state.corridors.get(party, state.corridors)
        ax_corr = p_corr.get("axes", p_corr).get(ax, {})
        if isinstance(ax_corr, list) and len(ax_corr) >= 2:
            return float(ax_corr[0])
        return float(ax_corr.get("lo", ax_corr.get("min", -50.0)))

    if func_name == "corridor_hi":
        ax = str(args[0]) if args else "territory"
        party = state.player.get("party_id", "likud")
        p_corr = state.corridors.get(party, state.corridors)
        ax_corr = p_corr.get("axes", p_corr).get(ax, {})
        if isinstance(ax_corr, list) and len(ax_corr) >= 2:
            return float(ax_corr[1])
        return float(ax_corr.get("hi", ax_corr.get("max", 80.0)))

    # M05 Action & Policy queries
    if func_name == "m05_iou_total":
        return len(state.m05.get("iou_ledger", []))

    if func_name == "action_running":
        aid = str(args[0]) if args else ""
        return any(a.get("id") == aid for a in state.m05.get("active_actions", []))

    if func_name == "action_done_count":
        aid = str(args[0]) if args else ""
        return int(state.m05.get("completed_actions", {}).get(aid, 0))

    if func_name in ("policy_level", "policy_active"):
        pol_id = str(args[0]) if args else ""
        lev = state.get_param("policy_level", pol_id)
        if func_name == "policy_active":
            return lev > 0.0
        return lev

    # M06 Character queries
    if func_name == "character_in_office":
        cid = str(args[0]) if args else ""
        return state.is_character_in_office(cid)

    if func_name in ("character_alive", "char_alive"):
        cid = str(args[0]) if args else ""
        return state.is_character_alive(cid)

    if func_name == "holder_of":
        oid = str(args[0]) if args else ""
        return state.holder_of(oid) or ""

    if func_name == "ambition":
        cid = str(args[0]) if args else ""
        ch = state.characters.get(cid, {})
        return float(ch.get("ambition", 50.0))

    # M07 World & Diplomacy queries
    if func_name == "peace_treaty":
        cid = str(args[0]) if args else ""
        return state.get_param("peace_treaty_state", cid) >= 2.0

    if func_name == "treaty_tier":
        cid = str(args[0]) if args else ""
        return int(round(state.get_param("peace_treaty_state", cid)))

    if func_name == "secret_channel":
        cid = str(args[0]) if args else ""
        c_obj = state.m07.get("countries", {}).get(cid, {})
        return bool(c_obj.get("secret_channel_open", False))

    if func_name == "nuclear_progress":
        cid = str(args[0]) if args else "iraq"
        return state.get_param("enemy_nuclear_progress", cid)

    # M09 Military queries
    if func_name in ("at_war", "war_active"):
        arg0 = str(args[0]) if args else None
        return state.at_war(arg0)

    if func_name == "last_ceasefire_date":
        return int(state.m09.get("peace_months_streak", 44)) * 30

    if func_name == "front_phase":
        fid = str(args[0]) if args else "lebanon"
        f = state.m09.get("fronts", {}).get(fid, {})
        aw = f.get("active_war")
        if isinstance(aw, dict):
            return int(aw.get("phase", 1))
        return 0

    if func_name in ("casualties_total", "casualties_total_all_fronts"):
        fid = str(args[0]) if args and func_name == "casualties_total" else ""
        total = 0
        for fk, f in state.m09.get("fronts", {}).items():
            if not fid or fk == fid:
                aw = f.get("active_war")
                if isinstance(aw, dict):
                    total += int(aw.get("casualties", 0))
                total += int(f.get("cumulative_casualties", 0))
        return total

    # M11 Region queries
    if func_name == "region_exists":
        rid = str(args[0]) if args else ""
        return state.region_exists(rid)

    if func_name in ("legal_status", "region_legal_status"):
        from sim.state import resolve_region_id
        rid = resolve_region_id(str(args[0]) if args else "")
        r = state.m11.get("regions", {}).get(rid, {})
        return str(r.get("legal_status", "sovereign"))

    if func_name == "site_status":
        sid = str(args[0]) if args else ""
        sites = state.m11.get("key_sites", {})
        if isinstance(sites, dict) and sid in sites:
            return str(sites[sid].get("status", "active"))
        return "active"

    if func_name == "settler_pop":
        rid = str(args[0]) if args else ""
        if not state.region_exists(rid):
            return 0
        return int(round(state.get_param("settler_population", rid)))

    if func_name == "active_plan":
        return str(state.m11.get("active_overlay", ""))

    # M13 Authoritarian queries
    if func_name == "m13_stage":
        st_num = int(state.m13.get("stage", 0))
        return f"C{max(1, min(5, st_num + 1))}"

    if func_name == "m13_actor_posture":
        aid = str(args[0]) if args else ""
        act = state.m13.get("resist_actors", {}).get(aid, {})
        return str(act.get("stance", "compliant"))

    if func_name == "m13_protest_tier":
        return int(round(state.get_param("social_protest_tier")))

    if func_name == "m13_in_survival_mode":
        return bool(state.m13.get("survival_mode_active", False))

    # M14 Endings & Tenure queries
    if func_name == "tenure_months":
        start_d = int(state.run.get("tenure_start_day", 0))
        return max(0, (state.day_index - start_d) // 30)

    if func_name == "tenure_index":
        return int(state.run.get("tenure_index", 0))

    if func_name == "count_peace_treaties":
        return state.count_peace_treaties()

    if func_name == "settler_population_total":
        return state.settler_population_total()

    if func_name == "front_quagmire_months":
        fid = str(args[0]) if args else "lebanon"
        f = state.m09.get("fronts", {}).get(fid, {})
        return int(f.get("quagmire_months", 0))

    if func_name == "region_pop_group_total":
        return int(sum(state.params.get("region_population", {}).values()))

    return False


class EffectExecutor:
    """Executes declarative effect instructions (contracts.md §4.1 & §4.2) against GameState."""

    def __init__(self, causal_net: Optional[Any] = None) -> None:
        self.causal_net = causal_net

    def apply_effects(
        self,
        state: Any,
        effects: Optional[List[Dict[str, Any]]],
        source: str = "unknown",
        ctx: Optional[Dict[str, Any]] = None,
        rng_stream_name: str = "events",
    ) -> List[Dict[str, Any]]:
        if not effects:
            return []
        applied: List[Dict[str, Any]] = []
        eval_ctx = dict(ctx or {})
        for eff in effects:
            if not isinstance(eff, dict):
                continue
            res = self.apply_one(state, eff, source=source, ctx=eval_ctx, rng_stream_name=rng_stream_name)
            if res is not None:
                applied.append(res)
        return applied

    def apply_one(
        self,
        state: Any,
        eff: Dict[str, Any],
        source: str = "unknown",
        ctx: Optional[Dict[str, Any]] = None,
        rng_stream_name: str = "events",
    ) -> Optional[Dict[str, Any]]:
        eval_ctx = dict(ctx or {})

        # 1. Delayed effect scheduling (contracts.md §4.1: delay_days > 0 enters delayed_effects)
        delay_days = int(eff.get("delay_days", eff.get("delay", 0)) or 0)
        if delay_days > 0 and not eff.get("_released"):
            eff_copy = dict(eff)
            eff_copy.pop("delay_days", None)
            eff_copy.pop("delay", None)
            eff_copy["_released"] = True
            state.pending["delayed_effects"].append({
                "due_day": state.day_index + delay_days,
                "effect": eff_copy,
                "source": source,
                "ctx": eval_ctx,
            })
            return {"op": "delayed", "due_day": state.day_index + delay_days, "source": source}

        # 2. Conditional guard
        cond = eff.get("condition") or eff.get("when")
        if cond and not eval_bool(cond, state, eval_ctx):
            return None

        # 3. Chance check (consumes 1 draw from current stream whenever 'chance' field is present)
        if "chance" in eff and eff["chance"] is not None:
            prob = eval_float(eff["chance"], state, eval_ctx)
            if not state.rng.stream(rng_stream_name).chance(prob):
                return None

        # 4. Scale multiplier
        scale = 1.0
        if "scale" in eff and eff["scale"] is not None:
            scale = eval_float(eff["scale"], state, eval_ctx)

        op = str(eff.get("op", "add"))
        target = _interpolate_str(str(eff.get("target") or eff.get("param") or ""), eval_ctx)
        key_raw = eff.get("key")
        key = _interpolate_str(str(key_raw), eval_ctx) if key_raw is not None else None
        raw_val = eff.get("value")

        if op in ("add", "clamp_add"):
            if not target:
                return None
            delta = (eval_float(raw_val, state, eval_ctx) if isinstance(raw_val, str) else float(raw_val or 0.0)) * scale

            # Debt-type parameter decrease protection (contracts.md §4.1 D-015 B-8)
            if delta < 0 and target in ("draft_exemption", "historical_grievance", "land_grievance"):
                if not (source.startswith("action:") or source.startswith("owner:")):
                    return None

            # Flow parameter budget_balance one-off routing (contracts.md §4.1 D-010)
            if target == "budget_balance" and not source.startswith("owner:"):
                state.m02["one_off_flows"]["budget_balance"] = float(state.m02["one_off_flows"].get("budget_balance", 0.0)) + delta

            old_v = state.get_param(target, key)
            new_v = state.add_param(target, delta, key)
            actual_delta = new_v - old_v
            if self.causal_net is not None and not source.startswith("owner:"):
                self.causal_net.on_effect_applied(state, target, key, actual_delta, source)
            return {"op": "add", "target": target, "key": key, "delta": actual_delta, "new_value": new_v, "source": source}

        elif op == "set":
            if not target:
                return None
            val = eval_float(raw_val, state, eval_ctx) if isinstance(raw_val, str) else float(raw_val or 0.0)
            new_v = state.set_param(target, val, key)
            return {"op": "set", "target": target, "key": key, "value": new_v, "source": source}

        elif op == "mul":
            if not target:
                return None
            base_f = eval_float(raw_val, state, eval_ctx) if isinstance(raw_val, str) else float(raw_val if raw_val is not None else 1.0)
            factor = 1.0 + (base_f - 1.0) * scale
            new_v = state.mul_param(target, factor, key)
            return {"op": "mul", "target": target, "key": key, "factor": factor, "new_value": new_v, "source": source}

        elif op == "add_relation":
            char_key = _interpolate_str(str(eff.get("character") or key or target), eval_ctx)
            delta = float(raw_val or 0.0) * scale
            new_v = state.add_param("relation", delta, char_key)
            return {"op": "add_relation", "character": char_key, "delta": delta, "new_value": new_v}

        elif op == "change_seat":
            party = _interpolate_str(str(eff.get("party") or key or target), eval_ctx)
            delta = int(round(float(raw_val or 0.0) * scale))
            cur = int(round(state.get_param("knesset_seats", party)))
            state.set_param("knesset_seats", max(0, cur + delta), party)
            return {"op": "change_seat", "party": party, "delta": delta}

        elif op == "set_flag":
            flag_id = _interpolate_str(str(eff.get("flag") or eff.get("id") or key or target or raw_val or ""), eval_ctx)
            dur = eff.get("duration_days", eff.get("duration"))
            if flag_id:
                state.set_flag(flag_id, duration_days=int(dur) if dur is not None else None, source=source)
            return {"op": "set_flag", "flag": flag_id}

        elif op == "clear_flag":
            flag_id = _interpolate_str(str(eff.get("flag") or eff.get("id") or key or target or raw_val or ""), eval_ctx)
            if flag_id:
                state.clear_flag(flag_id)
            return {"op": "clear_flag", "flag": flag_id}

        elif op == "add_modifier":
            mod_id = _interpolate_str(str(eff.get("modifier") or eff.get("id") or key or target or raw_val or ""), eval_ctx)
            dur = eff.get("duration_days", eff.get("duration"))
            scope_k = eff.get("scope_key", key if eff.get("modifier") else None)
            if mod_id:
                state.add_modifier(
                    mod_id,
                    duration_days=int(dur) if dur is not None else None,
                    key=_interpolate_str(str(scope_k), eval_ctx) if scope_k else None,
                    source=source,
                )
            return {"op": "add_modifier", "modifier": mod_id}

        elif op == "remove_modifier":
            mod_id = _interpolate_str(str(eff.get("modifier") or eff.get("id") or key or target or raw_val or ""), eval_ctx)
            if mod_id:
                state.remove_modifier(mod_id)
            return {"op": "remove_modifier", "modifier": mod_id}

        elif op in ("trigger_event", "schedule_event"):
            ev_id = _interpolate_str(str(eff.get("event") or eff.get("event_id") or key or target or raw_val or ""), eval_ctx)
            ev_delay = int(eff.get("delay_days", eff.get("delay", 0)) or 0)
            if ev_id:
                state.m12["scheduled"].append({
                    "event_id": ev_id,
                    "due_day": state.day_index + ev_delay,
                    "source": source,
                })
            return {"op": op, "event": ev_id, "due_day": state.day_index + ev_delay}

        elif op == "event_multiplier":
            ev_id = _interpolate_str(str(eff.get("event") or key or target or ""), eval_ctx)
            mult = float(raw_val if raw_val is not None else 1.0)
            if ev_id:
                cur_m = float(state.m12["multipliers"].get(ev_id, 1.0))
                state.m12["multipliers"][ev_id] = cur_m * mult
            return {"op": "event_multiplier", "event": ev_id, "multiplier": mult}

        elif op == "if":
            val_dict = raw_val if isinstance(raw_val, dict) else eff
            c_expr = val_dict.get("cond") or val_dict.get("condition") or "true"
            branch = val_dict.get("then", []) if eval_bool(c_expr, state, eval_ctx) else val_dict.get("else", [])
            sub_res = self.apply_effects(state, branch, source=source, ctx=eval_ctx, rng_stream_name=rng_stream_name)
            return {"op": "if", "applied": sub_res}

        elif op == "random_branch":
            val_dict = raw_val if isinstance(raw_val, dict) else eff
            branches = val_dict.get("branches", [])
            if branches:
                weights = [float(b.get("weight", 1.0)) for b in branches]
                chosen = state.rng.stream(rng_stream_name).weighted_pick(branches, weights)
                if chosen:
                    sub_res = self.apply_effects(state, chosen.get("effects", []), source=source, ctx=eval_ctx, rng_stream_name=rng_stream_name)
                    return {"op": "random_branch", "applied": sub_res}
            return None

        elif op == "custom":
            return self._execute_custom(state, eff, source=source, ctx=eval_ctx, rng_stream_name=rng_stream_name)

        return None

    def _execute_custom(
        self,
        state: Any,
        eff: Dict[str, Any],
        source: str = "unknown",
        ctx: Optional[Dict[str, Any]] = None,
        rng_stream_name: str = "events",
    ) -> Dict[str, Any]:
        eval_ctx = dict(ctx or {})
        raw_val = eff.get("value")
        val_dict = raw_val if isinstance(raw_val, dict) else {}

        # Determine custom handler name across all conventions used in actions.yaml and events/*.yaml
        handler = (
            eff.get("custom")
            or eff.get("handler")
            or eff.get("fn")
            or val_dict.get("handler")
            or val_dict.get("fn")
            or (eff.get("key") if eff.get("target") == "custom" else None)
            or eff.get("id")
            or ""
        )
        if not handler and eff.get("target") and eff.get("key"):
            handler = "add_all_keys"

        # Interpolate string values inside val_dict
        args: Dict[str, Any] = {}
        for k, v in val_dict.items():
            args[k] = _interpolate_str(v, eval_ctx) if isinstance(v, str) else v

        if handler == "if_then":
            c_expr = args.get("cond") or eff.get("cond") or "true"
            branch = args.get("then", []) if eval_bool(c_expr, state, eval_ctx) else args.get("else", [])
            self.apply_effects(state, branch, source=source, ctx=eval_ctx, rng_stream_name=rng_stream_name)
            return {"op": "custom", "handler": handler}

        elif handler == "random_branch":
            branches = args.get("branches", eff.get("branches", []))
            if branches:
                weights = [float(b.get("weight", 1.0)) for b in branches]
                chosen = state.rng.stream(rng_stream_name).weighted_pick(branches, weights)
                if chosen:
                    self.apply_effects(state, chosen.get("effects", []), source=source, ctx=eval_ctx, rng_stream_name=rng_stream_name)
            return {"op": "custom", "handler": handler}

        elif handler == "add_all_keys":
            t_param = str(args.get("target") or eff.get("target") or "bloc_support")
            delta = float(args.get("value", eff.get("value", 0.0)) if not isinstance(eff.get("value"), dict) else args.get("value", 0.0))
            exclude = set(args.get("exclude", []))
            store = state.params.get(t_param)
            if isinstance(store, dict):
                keys = args.get("keys") or list(store.keys())
                if keys == ["cabinet"]:
                    keys = [cid for cid in state.offices.values() if cid]
                for k in keys:
                    if k not in exclude:
                        state.add_param(t_param, delta, str(k))
            return {"op": "custom", "handler": handler, "target": t_param, "delta": delta}

        elif handler == "schedule_event_window":
            ev_id = str(args.get("event") or eff.get("event") or "")
            prob = float(args.get("chance", 1.0))
            rng = state.rng.stream(rng_stream_name)
            if ev_id and rng.chance(prob):
                min_d = int(args.get("min_days", 7))
                max_d = int(args.get("max_days", 30))
                d = rng.range_int(min_d, max_d)
                state.m12["scheduled"].append({"event_id": ev_id, "due_day": state.day_index + d, "source": source})
            return {"op": "custom", "handler": handler, "event": ev_id}

        elif handler in ("end_tenure", "m01_trigger_tenure_end"):
            reason = str(args.get("reason") or eff.get("reason") or raw_val or "resignation")
            state.pending["tenure_end"] = reason
            return {"op": "custom", "handler": handler, "reason": reason}

        elif handler == "m01_raise_signal":
            sig = str(args.get("signal") or eff.get("signal") or "generic")
            state.pending["hooks"].append({"signal": sig, "day": state.day_index, "payload": args.get("payload", {})})
            return {"op": "custom", "handler": handler, "signal": sig}

        elif handler == "m01_force_pause":
            state.pending["pause_signals"].append(str(args.get("reason_zh", "重大事态暂停")))
            return {"op": "custom", "handler": handler}

        elif handler == "m01_set_player_party":
            party = str(args.get("party") or "new_party_a")
            state.player["party_id"] = party
            return {"op": "custom", "handler": handler, "party": party}

        elif handler in ("activate_key", "deactivate_key"):
            p = str(args.get("param") or "")
            k = str(args.get("key") or "")
            if p and k and handler == "activate_key":
                state.set_param(p, float(args.get("value", 35.0)), k)
            return {"op": "custom", "handler": handler}

        elif handler == "m02_add_baseline_shift":
            p = str(args.get("param") or "")
            k = args.get("key")
            delta = float(args.get("delta", 0.0))
            node_key = f"{p}[{k}]" if k else p
            shifts = state.m02.setdefault("baseline_shifts", {})
            shifts[node_key] = float(shifts.get(node_key, 0.0)) + delta
            return {"op": "custom", "handler": handler, "node": node_key, "delta": delta}

        elif handler in ("stance_shift_by_corridor", "m04_add_stance_by_corridor"):
            axis = str(args.get("axis") or eff.get("key") or "territory")
            amt = float(args.get("amount", eff.get("value", 5.0)) if not isinstance(eff.get("value"), dict) else args.get("amount", 5.0))
            direction = str(args.get("direction") or eff.get("direction") or "away")
            sign = 1.0 if direction in ("away", "toward_right", "right") else -1.0
            if axis in state.axis_impulse:
                state.axis_impulse[axis] = float(state.axis_impulse.get(axis, 0.0)) + sign * amt
                state.recompute_gov_axis_position()
            return {"op": "custom", "handler": handler, "axis": axis, "delta": sign * amt}

        elif handler in ("m04_push_corridor", "m04_shift_corridor"):
            axis = str(args.get("axis") or "territory")
            amt = float(args.get("amount", 5.0))
            direction = str(args.get("direction", "right"))
            sign = -1.0 if direction in ("left", "dove", "down") else 1.0
            party = state.player.get("party_id", "likud")
            p_corr = state.corridors.setdefault(party, {}).setdefault("axes", {})
            if axis in p_corr and isinstance(p_corr[axis], list) and len(p_corr[axis]) >= 2:
                p_corr[axis][0] = max(-100.0, min(100.0, float(p_corr[axis][0]) + sign * amt))
                p_corr[axis][1] = max(-100.0, min(100.0, float(p_corr[axis][1]) + sign * amt))
            return {"op": "custom", "handler": handler, "axis": axis}

        elif handler == "m04_party_convention":
            state.add_param("party_standing", 6.0)
            state.add_param("party_cohesion", 5.0)
            return {"op": "custom", "handler": handler}

        elif handler == "m04_faction_deal":
            f = str(args.get("faction") or "herut_hawks")
            if f in state.params.get("faction_mood", {}):
                state.add_param("faction_mood", 10.0, f)
            state.add_param("party_cohesion", 4.0)
            return {"op": "custom", "handler": handler}

        elif handler in ("m04_faction_exit", "m04_party_split", "m04_found_new_party"):
            if handler == "m04_found_new_party":
                state.player["party_id"] = "new_party_a"
                state.set_param("knesset_seats", 18.0, "new_party_a")
                state.add_param("knesset_seats", -18.0, "likud")
            else:
                state.add_param("coalition_seats", -3.0)
                state.add_param("party_cohesion", 5.0)
            return {"op": "custom", "handler": handler}

        elif handler in ("m04_leadership_vote", "m04_force_challenge"):
            standing = state.get_param("party_standing")
            chall = state.get_param("challenger_strength")
            if standing >= chall:
                state.add_param("party_standing", 10.0)
                state.add_param("challenger_strength", -20.0)
            else:
                state.pending["tenure_end"] = "primary_loss"
            return {"op": "custom", "handler": handler}

        elif handler in ("m03_add_to_coalition", "m03_remove_from_coalition"):
            from sim.state import resolve_party_id
            party = resolve_party_id(str(args.get("party") or eff.get("party") or "dash"))
            coal = state.parliament.setdefault("coalition_parties", ["likud", "nrp", "agudat"])
            seats = state.get_param("knesset_seats", party)
            if handler == "m03_add_to_coalition":
                if party not in coal:
                    coal.append(party)
                    state.add_param("coalition_seats", seats)
                state.add_param("ally_satisfaction", 10.0, party)
            else:
                if party in coal:
                    coal.remove(party)
                    state.add_param("coalition_seats", -seats)
            return {"op": "custom", "handler": handler, "party": party}

        elif handler == "m03_delay_demand":
            party = str(args.get("party") or "nrp")
            state.add_param("ally_satisfaction", -3.0, party)
            return {"op": "custom", "handler": handler, "party": party}

        elif handler == "m03_force_support":
            party = str(args.get("party") or "nrp")
            state.add_param("ally_satisfaction", -8.0, party)
            return {"op": "custom", "handler": handler, "party": party}

        elif handler == "m03_postpone_election":
            months = int(args.get("months", eff.get("value", 6)) if not isinstance(eff.get("value"), dict) else args.get("months", 6))
            state.add_param("months_to_election", float(months))
            state.m13["postpone_election_count"] = int(state.m13.get("postpone_election_count", 0)) + 1
            return {"op": "custom", "handler": handler, "months": months}

        elif handler in ("m03_request_vote", "m03_submit_bill", "m03_dissolve_knesset"):
            vtype = str(args.get("type") or args.get("vote") or ("early_election" if handler == "m03_dissolve_knesset" else "confidence"))
            due = state.day_index + int(args.get("due_day", 7))
            state.pending["vote_requests"].append({"type": vtype, "due_day": due, "source": source, "args": args})
            return {"op": "custom", "handler": handler, "type": vtype}

        elif handler == "m05_change_policy":
            pol_id = str(args.get("policy") or eff.get("policy") or "")
            if pol_id in state.policies and pol_id in state.registry.policies:
                pol_def = state.registry.policies[pol_id]
                tiers = [float(t["v"] if isinstance(t, dict) else t) for t in pol_def.get("tiers", [])]
                cur_idx = int(state.policies[pol_id].get("tier_idx", 0))
                if "to" in args and args["to"] is not None:
                    new_idx = max(0, min(len(tiers) - 1, int(args["to"])))
                else:
                    steps = int(args.get("steps", 1))
                    new_idx = max(0, min(len(tiers) - 1, cur_idx + steps))
                if tiers:
                    state.policies[pol_id]["tier_idx"] = new_idx
                    state.set_param("policy_level", tiers[new_idx], pol_id)
                    state.recompute_gov_axis_position()
            return {"op": "custom", "handler": handler, "policy": pol_id}

        elif handler in ("m05_grant_favor", "m05_incur_favor"):
            ent = str(args.get("entity") or "nrp")
            kind = str(args.get("kind") or "party")
            n = float(args.get("n", 1.0))
            param_name = "favor_party" if kind == "party" else "favor_character"
            state.add_param(param_name, n if handler == "m05_grant_favor" else -n, ent)
            return {"op": "custom", "handler": handler, "entity": ent}

        elif handler in ("m06_appoint", "m06_dismiss", "m06_open_reshuffle"):
            char_id = str(args.get("character") or "")
            office = str(args.get("office") or "")
            if handler == "m06_appoint" and char_id:
                if office:
                    state.offices[office] = char_id
                if char_id in state.characters:
                    state.characters[char_id]["office"] = office or "minister"
                state.add_param("relation", 15.0, char_id)
            elif handler == "m06_dismiss" and char_id:
                for k_off, holder in list(state.offices.items()):
                    if holder == char_id:
                        state.offices[k_off] = None
                if char_id in state.characters:
                    state.characters[char_id]["office"] = None
                state.add_param("relation", -25.0, char_id)
            return {"op": "custom", "handler": handler, "character": char_id}

        elif handler == "m06_add_relation_cabinet":
            delta = float(args.get("delta", args.get("value", eff.get("value", 5.0))) if not isinstance(eff.get("value"), dict) else args.get("delta", 5.0))
            seen = set()
            for holder in state.offices.values():
                if holder and holder not in seen:
                    seen.add(holder)
                    state.add_param("relation", delta, holder)
            return {"op": "custom", "handler": handler, "delta": delta}

        elif handler == "m06_promote_group":
            state.add_param("appointment_gap", -8.0)
            return {"op": "custom", "handler": handler}

        elif handler == "m08_activate_delegation":
            state.m08["autonomy_track"]["stage"] = "ACTIVE"
            state.add_param("autonomy_progress", 10.0)
            return {"op": "custom", "handler": handler}

        elif handler == "m08_spawn_hamas":
            state.m08["faction_active"]["hamas"] = True
            state.set_param("faction_strength", 25.0, "hamas")
            return {"op": "custom", "handler": handler}

        elif handler == "m08_start_intifada":
            state.m08["uprising_state"]["active"] = True
            state.m08["uprising_state"]["intensity"] = 65.0
            state.set_flag("intifada_active")
            return {"op": "custom", "handler": handler}

        elif handler in ("m09_start_war", "m09_ceasefire"):
            front = str(args.get("front") or "lebanon")
            f_obj = state.m09.get("fronts", {}).get(front)
            if f_obj is not None:
                if handler == "m09_start_war":
                    f_obj["status"] = "FULL_WAR" if args.get("scope") == "full" else "LIMITED_OP"
                    f_obj["active_war"] = {"phase": 1, "start_day": state.day_index, "casualties": 0}
                    state.set_param("mobilization", max(state.get_param("mobilization"), 65.0))
                else:
                    f_obj["status"] = "PEACE"
                    f_obj["active_war"] = None
                    state.m09["peace_months_streak"] = 0
            return {"op": "custom", "handler": handler, "front": front}

        elif handler == "m09_set_mobilization":
            lvl = float(args.get("level", eff.get("value", 1)) if not isinstance(eff.get("value"), dict) else args.get("level", 1))
            tier_map = {0: 10.0, 1: 35.0, 2: 65.0, 3: 95.0}
            target_mob = tier_map.get(int(lvl), lvl)
            state.m09["mobilization_target"] = target_mob
            state.set_param("mobilization", target_mob)
            return {"op": "custom", "handler": handler, "mobilization": target_mob}

        elif handler in ("m10_pass_budget", "m10_budget_result"):
            state.m10["budget_cycle"]["status"] = "PASSED"
            state.add_param("party_standing", 3.0)
            return {"op": "custom", "handler": handler}

        elif handler in ("m10_apply_stabilization_plan", "apply_stabilization_plan"):
            state.m10["stabilization_plan_active"] = True
            state.m10["stabilization_months_left"] = 18
            state.set_flag("stabilization_plan_active")
            state.mul_param("inflation", 0.45)
            state.add_param("budget_balance", 4.0)
            state.add_param("fx_reserves", 12.0)
            return {"op": "custom", "handler": handler}

        elif handler in ("m11_activate_region", "m11_remove_region"):
            from sim.state import resolve_region_id
            rid = resolve_region_id(str(args.get("region") or eff.get("region") or "sinai"))
            if rid in state.m11.get("regions", {}):
                exists = handler == "m11_activate_region"
                state.m11["regions"][rid]["exists"] = exists
                state.m11["regions"][rid]["legal_status"] = "occupied_military" if exists else "returned"
                if not exists:
                    state.set_param("settler_population", 0.0, rid)
            return {"op": "custom", "handler": handler, "region": rid}

        elif handler == "m14_record_turning_point":
            state.history["turning_points"].append({
                "day_index": state.day_index,
                "date": state.date_str,
                "title_zh": str(args.get("title_zh", source)),
                "summary_zh": str(args.get("summary_zh", "")),
                "weight": float(args.get("weight", 5.0)),
                "category": str(args.get("category", "politics")),
            })
            return {"op": "custom", "handler": handler}

        elif handler == "m14_grant_achievement":
            ach_id = str(args.get("id") or "")
            ach_list = state.m14.setdefault("unlocked_achievements_this_run", [])
            if ach_id and ach_id not in ach_list:
                ach_list.append(ach_id)
            return {"op": "custom", "handler": handler, "id": ach_id}

        return {"op": "custom", "handler": handler, "source": source}
