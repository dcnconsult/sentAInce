"""interp_v1 — the controlled evolving-app stream: build a recursive `minilang` interpreter over 16
steps, with a controlled BREAKING SPEC CHANGE at step 10 (typed values) that forces a refactor — the
staleness inducer. The agent builds its own `interp.py` (entry point `run(program: str)`); every step's
`verify` is an objective ground-truth check (passes against `_ref/minilang.py`, never shown to the agent).

Goal-class structure (we control it, so the gauge stats are interpretable):
  add_feature  ×12 (A+B+D) — the RECURRING class where the colony should converge
  refactor     ×1  (C10)   — the singleton staleness inducer
  recall_probe ×3  (E)     — revisit earlier goal-classes AFTER the spec drift
"""
from __future__ import annotations

import json

from exocortex.streams import Step, Stream


def _v(prog: str, check: str) -> str:
    """A verify: run `prog`, bind result to `r`, assert `check`, print OK. (bash single-quoted -c;
    json.dumps gives a safe double-quoted Python literal — no single quotes, so no bash conflict.)"""
    return ("python3 -c 'import interp; r = interp.run(" + json.dumps(prog)
            + "); assert " + check + "; print(\"OK\")'")


def _v2(p1: str, c1: str, p2: str, c2: str) -> str:
    return ("python3 -c 'import interp; "
            "assert (lambda r: " + c1 + ")(interp.run(" + json.dumps(p1) + ")); "
            "assert (lambda r: " + c2 + ")(interp.run(" + json.dumps(p2) + ")); "
            "print(\"OK\")'")


_STEPS = (
    # ---- A · Bootstrap ----
    Step("A1_scaffold", "add_feature",
         "Create `interp.py` with a function `run(program: str)` that evaluates a 'minilang' program and "
         "returns its value. Start with integer arithmetic: `+ - *` and parentheses with normal "
         "precedence. Use a real recursive-descent parser — do NOT use Python's eval().",
         _v("2 + 3 * 4", "r == 14"), "OK"),
    Step("A2_power", "add_feature",
         "Add a `^` exponentiation operator that is RIGHT-associative (so `2^3^2` is 512), plus unary "
         "minus, to `interp.py`.",
         _v("2 ^ 3 ^ 2", "r == 512"), "OK"),
    Step("A3_program", "add_feature",
         "Make `run` accept a multi-statement program: statements separated by newlines or `;`, returning "
         "the value of the LAST expression.",
         _v("1 + 1\n2 * 3", "r == 6"), "OK"),
    # ---- B · Feature growth (the recurring add_feature class) ----
    Step("B4_variables", "add_feature",
         "Add variables: `x = expr` assigns, and a bare name evaluates to its value.",
         _v("x = 5\nx * 2", "r == 10"), "OK"),
    Step("B5_if", "add_feature",
         "Add conditional expressions: `if cond then a else b` (a non-zero number is truthy).",
         _v("if 1 then 10 else 20", "r == 10"), "OK"),
    Step("B6_compare", "add_feature",
         "Add comparison operators `<`, `>`, `==` that return a boolean.",
         _v("if 5 > 3 then 1 else 0", "r == 1"), "OK"),
    Step("B7_builtins", "add_feature",
         "Add built-in functions `abs`, `max`, `min`, e.g. `abs(-3)`, `max(2, 7)`.",
         _v("max(2, 7) + abs(-3)", "r == 10"), "OK"),
    Step("B8_userfn", "add_feature",
         "Add user-defined functions: `fn square(x) = x * x`, callable as `square(6)`.",
         _v("fn square(x) = x * x\nsquare(6)", "r == 36"), "OK"),
    Step("B9_recursion", "add_feature",
         "Ensure user functions can RECURSE, e.g. `fn fact(n) = if n < 2 then 1 else n * fact(n - 1)`.",
         _v("fn fact(n) = if n < 2 then 1 else n * fact(n - 1)\nfact(5)", "r == 120"), "OK"),
    # ---- C · Breaking spec change (the staleness inducer) ----
    Step("C10_typed", "refactor",
         "SPEC CHANGE — refactor the evaluator to TYPED values (int, float, bool, string). Two new "
         "observable behaviors: (1) division `/` of two ints now yields a FLOAT (`7/2` is `3.5`); "
         "(2) add double-quoted string literals with `+` for concatenation (`\"ab\" + \"cd\"` is "
         "`\"abcd\"`). Update your code and your own tests accordingly.",
         _v2("7 / 2", "r == 3.5", "\"ab\" + \"cd\"", "r == \"abcd\""), "OK"),
    # ---- D · Post-refactor growth (reconverge under the new spec) ----
    Step("D11_strlen", "add_feature",
         "Add built-ins `len` and `str` under the typed spec (e.g. `len(\"hello\")` is 5, `str(42)` is "
         "`\"42\"`).",
         _v2("len(\"hello\")", "r == 5", "str(42)", "r == \"42\""), "OK"),
    Step("D12_floatops", "add_feature",
         "Ensure float arithmetic works (`2.5 * 2` is `5.0`) and add `int(x)` truncation (`int(3.7)` is 3).",
         _v2("2.5 * 2", "r == 5.0", "int(3.7)", "r == 3"), "OK"),
    Step("D13_strfn", "add_feature",
         "Support user functions with string arguments, e.g. `fn greet(name) = \"hi \" + name`.",
         _v("fn greet(name) = \"hi \" + name\ngreet(\"bob\")", "r == \"hi bob\""), "OK"),
    # ---- E · Recall probes (revisit earlier goal-classes AFTER the drift) ----
    Step("E14_morecompare", "recall_probe",
         "Add the comparison operators `!=`, `<=`, `>=` (returning booleans), consistent with the existing "
         "`<`, `>`, `==`.",
         _v2("if 3 <= 3 then 1 else 0", "r == 1", "if 4 != 5 then 1 else 0", "r == 1"), "OK"),
    Step("E15_fib", "recall_probe",
         "Add a recursive `fn fib(n) = if n < 2 then n else fib(n - 1) + fib(n - 2)`; confirm `fib(10)` is 55.",
         _v("fn fib(n) = if n < 2 then n else fib(n - 1) + fib(n - 2)\nfib(10)", "r == 55"), "OK"),
    Step("E16_strrec", "recall_probe",
         "Add a recursive `fn rep(s, n) = if n <= 0 then \"\" else s + rep(s, n - 1)` repeating a string n "
         "times; confirm `rep(\"ab\", 3)` is `\"ababab\"`.",
         _v("fn rep(s, n) = if n <= 0 then \"\" else s + rep(s, n - 1)\nrep(\"ab\", 3)", "r == \"ababab\""), "OK"),
)

INTERP_V1 = Stream(name="interp_v1", steps=_STEPS)
