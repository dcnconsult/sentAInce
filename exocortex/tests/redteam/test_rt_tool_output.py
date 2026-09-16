"""Red-team 3 — misleading tool output on the MASKED-failure path.

Scope: a real non-zero exit fires ``PostToolUseFailure`` and never deposits. This file covers the case
where the agent masked the failure (``|| true``, ``; echo "exit: $?"``), so the Bash tool exited 0 and
``classify_outcome`` must read the observed stdout/stderr. That heuristic is a small signature list.
The misses pinned below are failures that read as ``ok`` and would therefore earn τ.
"""
import pytest

from exocortex.colony import Colony
from exocortex.hook import classify_outcome

from .conftest import run_turn


def _cls(stdout="", stderr=""):
    return classify_outcome({"tool_response": {"stdout": stdout, "stderr": stderr}})


CAUGHT = [
    ("echoed exit", "exit: 1", ""),
    ("Exit code", "Exit code 1", ""),
    ("pytest FAILED line", "FAILED tests/test_x.py::test_a - assert 1 == 2", ""),
    ("traceback", "", "Traceback (most recent call last):"),
    ("command not found", "", "bash: foo: command not found"),
    # R1c (2026-09-16, results/outcome_signatures_v1): these were strict xfails under rt-tool-1
    ("lowercase exit code", "Process finished with exit code 1", ""),
    ("exit status", "returned non-zero exit status 2", ""),
    ("pytest summary only", "==== 1 failed, 3 passed in 0.2s ====", ""),
    ("npm", "", "npm ERR! code ELIFECYCLE"),
    ("make", "", "make: *** [all] Error 2"),
    ("compiler error", "", "error: could not compile `foo`"),
    ("permission denied", "", "bash: ./x: Permission denied"),
    ("bare exception line", "", "ModuleNotFoundError: No module named 'x'"),
]

MISSED = [
    ("fully silenced", "", ""),
]


@pytest.mark.parametrize("name,out,err", CAUGHT, ids=[c[0] for c in CAUGHT])
def test_masked_failure_signature_is_caught(name, out, err):
    assert _cls(out, err) == "fail"


@pytest.mark.xfail(strict=True, reason="GAP rt-tool-1 (remaining after R1c): a fully silenced command "
                   "(2>/dev/null || true) has no output to read, so it reads as ok and earns τ. Closing it "
                   "needs the command text inspected (R1a).")
@pytest.mark.parametrize("name,out,err", MISSED, ids=[c[0] for c in MISSED])
def test_masked_failure_signature_is_missed(name, out, err):
    assert _cls(out, err) == "fail"


def test_fake_success_banner_is_classified_ok():
    """Characterization: output text is trusted when no failure signature is present. A lying banner is
    indistinguishable from a real one on this path."""
    assert _cls("ALL TESTS PASSED") == "ok"


FALSE_POSITIVES = [
    ("grep hit on the word FAILED", "docs/notes.md: FAILED builds are retried", ""),
    ("prose containing 'exit 3'", "see section exit 3 of the manual", ""),
    ("prose containing 'exit code 1' (R1c)", "the exit code 1 means the lint step found issues", ""),
]

BENIGN_KEPT_OK = [
    ("git permission warning", "warning: could not open directory 'x/': Permission denied", ""),
    ("prose mentioning errors", "see errors in the log", ""),
    ("zero failures", "0 failed", ""),
    ("pytest all green", "12 passed in 0.31s", ""),
    ("echoed exit 0", "RESULT: 42\nexit: 0", ""),
]


@pytest.mark.parametrize("name,out,err", BENIGN_KEPT_OK, ids=[c[0] for c in BENIGN_KEPT_OK])
def test_benign_output_is_not_flipped_by_the_widened_signatures(name, out, err):
    assert _cls(out, err) == "ok"


@pytest.mark.parametrize("name,out,err", FALSE_POSITIVES, ids=[c[0] for c in FALSE_POSITIVES])
def test_conservative_false_positive_withholds_tau(name, out, err):
    """The heuristic errs toward 'fail' on these successes. That costs τ (under-credit), never integrity."""
    assert _cls(out, err) == "fail"


def test_masked_failure_with_summary_line_no_longer_deposits(state):
    """End-to-end (closed by R1c): a masked pytest failure whose output carries only the summary line used to
    earn τ; it is now read as a failure and deposits nothing."""
    out = "==== 1 failed, 3 passed in 0.2s ===="
    label = run_turn("s", "fix the failing build and run the tests", ["pytest -q || true"],
                     outcome=_cls(out), stdout=out)
    assert Colony.load(label).deposits == 0


def test_fully_silenced_failure_still_deposits(state):
    """End-to-end characterization of what remains open (R1a): no output, so nothing to read, so τ is earned."""
    label = run_turn("s", "fix the failing build and run the tests", ["pytest -q 2>/dev/null || true"],
                     outcome=_cls(""), stdout="")
    assert Colony.load(label).deposits == 1
