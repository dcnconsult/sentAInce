"""A trivial 3-step stream to validate the stream-driver mechanics (persistent sandbox, per-step verify,
stats audit, recall capture) before investing in the full interpreter stream. Each step adds to the same
`calc.py` (recurrence); step 3 is recursive."""
from __future__ import annotations

from exocortex.streams import Step, Stream

_V = "python3 -c 'import calc; assert calc.{expr}; print(\"OK\")'"

SMOKE = Stream(
    name="smoke",
    steps=(
        Step(id="S1_add", goal_class="add_feature",
             prompt="Create a Python module `calc.py` in the current directory with a function "
                    "`add(a, b)` that returns a + b. Keep it minimal.",
             verify=_V.format(expr="add(2, 3) == 5"), expect="OK"),
        Step(id="S2_sub", goal_class="add_feature",
             prompt="Add a function `sub(a, b)` to `calc.py` that returns a - b. Keep the existing code.",
             verify=_V.format(expr="sub(5, 2) == 3"), expect="OK"),
        Step(id="S3_fact", goal_class="add_feature",
             prompt="Add a recursive function `fact(n)` to `calc.py` returning n factorial "
                    "(e.g. fact(5) == 120). Keep the existing code.",
             verify=_V.format(expr="fact(5) == 120"), expect="OK"),
    ),
)
