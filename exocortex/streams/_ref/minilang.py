"""Reference implementation of the `minilang` the interp_v1 stream builds. Used ONLY to validate that
the stream's `verify` commands are objectively achievable — a FAIL on a real agent run then means the
agent failed, not that the stream is incoherent. The agent builds its OWN `interp.py`; this is a hidden
oracle, never shown to it. Implements the FINAL (post-refactor / typed) spec; every interp_v1 verify is
chosen to pass against it.

Spec: int/float/bool/string values; `+ - * / ^` (`/` of ints -> float; `^` right-assoc); unary `-`;
comparisons `< > == != <= >=` -> bool; `if c then a else b`; variables `x = e`; string literals with `+`
concat; builtins abs/max/min/len/str/int; user functions `fn f(a,b) = expr` (recursion ok); programs are
`;`/newline-separated statements, value = last expression.
"""
from __future__ import annotations

import re

_TOK = re.compile(r"""
    (?P<FLOAT>\d+\.\d+)
  | (?P<INT>\d+)
  | (?P<STR>"[^"]*")
  | (?P<OP><=|>=|==|!=|[-+*/^<>=(),])
  | (?P<SEMI>[;\n]+)
  | (?P<NAME>[A-Za-z_]\w*)
  | (?P<WS>[ \t\r]+)
""", re.VERBOSE)

_KW = {"if", "then", "else", "fn", "true", "false"}


def _tokenize(s: str):
    toks = []
    for m in _TOK.finditer(s):
        k = m.lastgroup
        if k == "WS":
            continue
        v = m.group()
        if k == "NAME" and v in _KW:
            toks.append((v, v))
        else:
            toks.append((k, v))
    toks.append(("EOF", ""))
    return toks


class _Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def accept(self, val):
        if self.t[self.i][1] == val or self.t[self.i][0] == val:
            return self.next()
        return None

    def expect(self, val):
        tok = self.accept(val)
        if tok is None:
            raise SyntaxError(f"expected {val!r} got {self.t[self.i]!r}")
        return tok

    # program := (stmt (SEMI stmt)*)
    def program(self):
        stmts = []
        while self.peek()[0] != "EOF":
            while self.peek()[0] == "SEMI":
                self.next()
            if self.peek()[0] == "EOF":
                break
            stmts.append(self.stmt())
            while self.peek()[0] == "SEMI":
                self.next()
        return ("prog", stmts)

    def stmt(self):
        if self.peek()[1] == "fn":
            self.next()
            name = self.expect("NAME")[1]
            self.expect("(")
            params = []
            if self.peek()[1] != ")":
                params.append(self.expect("NAME")[1])
                while self.accept(","):
                    params.append(self.expect("NAME")[1])
            self.expect(")")
            self.expect("=")
            body = self.expr()
            return ("fndef", name, params, body)
        # assignment:  NAME '=' expr   (but not '==')
        if self.peek()[0] == "NAME" and self.t[self.i + 1][1] == "=":
            name = self.next()[1]
            self.next()  # '='
            return ("assign", name, self.expr())
        return ("expr", self.expr())

    def expr(self):
        return self.comparison()

    def comparison(self):
        left = self.add()
        while self.peek()[1] in ("<", ">", "==", "!=", "<=", ">="):
            op = self.next()[1]
            left = ("binop", op, left, self.add())
        return left

    def add(self):
        left = self.mul()
        while self.peek()[1] in ("+", "-"):
            op = self.next()[1]
            left = ("binop", op, left, self.mul())
        return left

    def mul(self):
        left = self.power()
        while self.peek()[1] in ("*", "/"):
            op = self.next()[1]
            left = ("binop", op, left, self.power())
        return left

    def power(self):
        left = self.unary()
        if self.peek()[1] == "^":
            self.next()
            return ("binop", "^", left, self.power())  # right-assoc
        return left

    def unary(self):
        if self.peek()[1] == "-":
            self.next()
            return ("neg", self.unary())
        return self.atom()

    def atom(self):
        tok = self.peek()
        if tok[1] == "if":
            self.next()
            c = self.expr()
            self.expect("then")
            a = self.expr()
            self.expect("else")
            b = self.expr()
            return ("if", c, a, b)
        if tok[1] == "(":
            self.next()
            e = self.expr()
            self.expect(")")
            return e
        if tok[0] == "INT":
            self.next()
            return ("int", int(tok[1]))
        if tok[0] == "FLOAT":
            self.next()
            return ("float", float(tok[1]))
        if tok[0] == "STR":
            self.next()
            return ("str", tok[1][1:-1])
        if tok[1] in ("true", "false"):
            self.next()
            return ("bool", tok[1] == "true")
        if tok[0] == "NAME":
            self.next()
            if self.peek()[1] == "(":
                self.next()
                args = []
                if self.peek()[1] != ")":
                    args.append(self.expr())
                    while self.accept(","):
                        args.append(self.expr())
                self.expect(")")
                return ("call", tok[1], args)
            return ("var", tok[1])
        raise SyntaxError(f"unexpected {tok!r}")


_BUILTINS = {
    "abs": abs, "max": max, "min": min, "len": len, "str": str, "int": int,
}


def _eval(node, env):
    k = node[0]
    if k == "prog":
        val = None
        for s in node[1]:
            val = _eval(s, env)
        return val
    if k == "expr":
        return _eval(node[1], env)
    if k == "assign":
        env[node[1]] = _eval(node[2], env)
        return env[node[1]]
    if k == "fndef":
        env[node[1]] = ("func", node[2], node[3])
        return None
    if k in ("int", "float", "str", "bool"):
        return node[1]
    if k == "var":
        if node[1] not in env:
            raise NameError(node[1])
        return env[node[1]]
    if k == "neg":
        return -_eval(node[1], env)
    if k == "if":
        return _eval(node[2] if _eval(node[1], env) else node[3], env)
    if k == "binop":
        op, a, b = node[1], _eval(node[2], env), _eval(node[3], env)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if op == "/":
            return a / b            # typed spec: int/int -> float
        if op == "^":
            return a ** b
        if op == "<":
            return a < b
        if op == ">":
            return a > b
        if op == "==":
            return a == b
        if op == "!=":
            return a != b
        if op == "<=":
            return a <= b
        if op == ">=":
            return a >= b
    if k == "call":
        name, argnodes = node[1], node[2]
        args = [_eval(a, env) for a in argnodes]
        if name in _BUILTINS:
            return _BUILTINS[name](*args)
        fn = env.get(name)
        if not (isinstance(fn, tuple) and fn[0] == "func"):
            raise NameError(name)
        _, params, body = fn
        local = dict(env)
        for p, v in zip(params, args):
            local[p] = v
        return _eval(body, local)
    raise RuntimeError(f"bad node {node!r}")


def run(program: str):
    """Evaluate a minilang program string; return the value of the last expression."""
    return _eval(_Parser(_tokenize(program)).program(), {})
