"""Unit tests for the FI_hat Decisive Gauge — the denominator-vs-τ instrument (Cerebral / FI ledger).

OUT of the deterministic 99-lock (``pyproject testpaths=["tests"]`` collects only ``tests/``): a beta
gauge, not part of the C1–C7 evidence lock. Run explicitly:

    python -m pytest cerebral/tests                 # from the repo root
    python cerebral/tests/test_fi_gauge.py          # standalone (no pytest needed)

Synthetic audit records (list of dicts) with FIXED seeds so the permutation test is byte-deterministic.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]   # tests -> cerebral -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cerebral.gauge import fi_gauge as fg       # noqa: E402


def _bash(cmd: str, outcome: str, key: str = "") -> dict:
    return {"tool": "Bash", "command": cmd, "command_key": key or cmd[:24], "outcome": outcome}


# ---- config building: only Bash w/ ok|fail; attempts/successes at the chosen altitude ----
def test_build_configs_verb_altitude():
    rows = [_bash("git status", "ok"), _bash("git add x", "ok"), _bash("git push", "fail"),
            _bash("python a.py", "ok"),
            {"tool": "Read", "outcome": "ok"},                 # non-Bash → ignored
            {"tool": "Bash", "command": "ls", "outcome": ""}]  # no outcome → ignored
    cfg = fg.build_configs(rows, "verb")
    assert cfg["bash:git"] == [3, 2]      # 3 attempts, 2 ok
    assert cfg["bash:python"] == [1, 1]
    assert "bash:ls" not in cfg           # the outcomeless ls never counts


def test_command_key_altitude_is_finer():
    rows = [_bash("git status", "ok", "git status"), _bash("git add x", "ok", "git add"),
            _bash("git status", "fail", "git status")]
    cfg = fg.build_configs(rows, "command_key")
    assert cfg["git status"] == [2, 1]
    assert cfg["git add"] == [1, 1]


# ---- FI math: KT smoothing keeps a single trial finite; monotone-inverse to reliability ----
def test_reliability_and_fi_smoothing():
    # a single success is NOT certainty: p̂ = 1.5/2 = 0.75, FI > 0
    assert fg.reliability(1, 1) == 0.75
    assert fg.fi_hat(1, 1) > 0
    # more evidence of reliability → p̂ ↑, FI ↓ (monotone-inverse)
    assert fg.reliability(20, 20) > fg.reliability(1, 1)
    assert fg.fi_hat(20, 20) < fg.fi_hat(1, 1)
    # a flaky route (low reliability) is HIGH FI (Szostak rarity)
    assert fg.fi_hat(10, 2) > fg.fi_hat(10, 9)


# ---- decisive statistic: a genuinely heterogeneous corpus BEATS the shuffle null (BUILD) ----
def test_permutation_detects_real_heterogeneity():
    rows = []
    for _ in range(20):                              # a rock-solid route
        rows.append(_bash("git ok", "ok"))
    for i in range(20):                              # a genuinely flaky route: 50/50, NOT a shared rate
        rows.append(_bash("make flaky", "ok" if i % 2 == 0 else "fail"))
    for _ in range(20):                              # a mostly-broken route
        rows.append(_bash("deploy bad", "fail"))
    for i in range(6):
        rows.append(_bash("deploy bad", "ok" if i == 0 else "fail"))
    res = fg.run(rows, altitude="verb", min_attempts=5, min_powered=3, r=500, seed=0)
    assert res["counts"]["powered"] >= 3
    assert res["permutation"]["p_value"] < 0.05           # heterogeneity beats the null
    assert res["verdict"]["label"] == "BUILD"
    assert res["verdict"]["signal"] is True


# ---- decisive statistic: a homogeneous corpus (one shared coin) does NOT beat the null (NULL) ----
def test_permutation_null_on_homogeneous():
    # every config drawn from the SAME ~85% coin → dispersion is pure sampling noise
    import random
    rng = random.Random(1)
    rows = []
    for v in range(10):
        for _ in range(12):
            rows.append(_bash(f"verb{v} x", "ok" if rng.random() < 0.85 else "fail"))
    res = fg.run(rows, altitude="verb", min_attempts=5, r=500, seed=0)
    assert res["counts"]["powered"] == 10
    assert res["permutation"]["p_value"] >= 0.05
    assert res["verdict"]["label"] == "NULL"
    assert res["verdict"]["signal"] is False


# ---- power gate: too few powered configs → UNDERPOWERED (signal None, never a false BUILD) ----
def test_underpowered_abstains():
    rows = [_bash("git a", "ok")] * 6 + [_bash("python b", "ok")] * 6   # only 2 powered configs
    res = fg.run(rows, altitude="verb", min_attempts=5, min_powered=6, r=200, seed=0)
    assert res["counts"]["powered"] == 2
    assert res["verdict"]["label"] == "UNDERPOWERED"
    assert res["verdict"]["signal"] is None


# ---- all-ok corpus → no denominator variance → NULL by construction (not BUILD) ----
def test_all_success_is_null():
    rows = [_bash(f"v{i%8} x", "ok") for i in range(80)]     # 8 configs, every attempt ok
    res = fg.run(rows, altitude="verb", min_attempts=5, min_powered=6, r=200, seed=0)
    assert res["permutation"]["p_value"] == 1.0
    assert res["verdict"]["label"] == "NULL"


# ---- noise readout: cd/echo/ls failures are flagged as mechanical, not route-quality ----
def test_noise_verb_readout():
    rows = [_bash("cd /bad/path", "fail")] * 3 + [_bash("cd /ok", "ok")] * 4 + [_bash("git x", "ok")] * 5
    res = fg.run(rows, altitude="verb", min_attempts=5, r=100, seed=0)
    assert res["counts"]["total_failures"] == 3
    assert res["counts"]["noise_failures"] == 3            # all on cd
    assert res["counts"]["noise_failure_frac"] == 1.0
    cd_row = next(x for x in res["powered_configs"] if x["config"] == "bash:cd")
    assert cd_row["noise_verb"] is True


# ---- determinism: same rows + same seed → byte-identical result ----
def test_determinism():
    rows = [_bash("git a", "ok"), _bash("git b", "fail"), _bash("python c", "ok")] * 10
    r1 = fg.run(rows, altitude="verb", r=300, seed=7)
    r2 = fg.run(rows, altitude="verb", r=300, seed=7)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)


# ---- read-only / fail-open: a missing audit file is a safe empty, never a crash ----
def test_missing_audit_is_empty():
    missing = str(Path(tempfile.gettempdir()) / "no_such_audit_cerebral.jsonl")
    res = fg.run([missing], altitude="verb", r=50, seed=0)
    assert res["records"] == 0
    assert res["counts"]["powered"] == 0
    assert res["verdict"]["label"] == "UNDERPOWERED"


# ---- Spearman: perfectly-correlated τ and reliability → ρ≈1 (FI redundant with τ) ----
def test_spearman_redundant_when_reliability_tracks_tau():
    # configs where more successes ↔ higher reliability monotonically → ρ = 1
    xs = [1, 2, 3, 4, 5]
    ys = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert fg._spearman(xs, ys) == 1.0
    assert fg._spearman([1, 2, 3], [3, 2, 1]) == -1.0
    assert fg._spearman([1, 1], [2, 3]) is None            # <3 points → None


if __name__ == "__main__":   # standalone runner (no pytest required)
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for f in fns:
        f()
    print(f"ok — {len(fns)} fi_gauge tests passed")
