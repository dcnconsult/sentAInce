"""FI_hat Decisive Gauge — does the ATTEMPTS DENOMINATOR carry signal raw τ does not? (STATS)

The [[functional-information-ledger]]'s first instrument, and the decisive gauge the Cerebral Substrate
framing turns on. The colony's pheromone τ counts **successes** and is blind to **attempts** (it deposits
only on ``exit 0`` — ADR-001). Functional information adds the denominator:

    FI_hat(o,m) = -log2( successes-like-m / attempts-like-m )     (KT / Jeffreys add-1/2 smoothed)

So FI_hat's novelty over τ is *entirely* the denominator — the failure count the roadmap has parked for a
year ([[exocortex-hook-integration-roadmap]] W4; ADR-004 decaying τ⁻). This gauge asks the yes/no question
before we build the ledger that would carry it:

    Does knowing per-configuration RELIABILITY (attempts, not just successes) separate good routes from
    clutter in a way the success-count alone cannot?

**Data.** The only live denominator on disk is the **audit log** (``audit.jsonl``): every Bash consequence
is stamped ``outcome: ok|fail``. τ (``colony_*.json``) has no denominator; the intent register's −1/0
(falsified/inconclusive) valence is unparsed in v1 (all closed intents read +1) — so the *procedural*
audit is the sole denominator source. We read (attempts n, successes k) per configuration at a chosen
**altitude** (Amendment 1, the reference-class problem): ``verb`` (``bash:git``, coarser, better powered)
or ``command_key`` (the strategy-lock's verb+first-token unit, finer, sparser).

**The decisive statistic — the frequency-matched outcome-shuffle null** (the project's own discipline,
``gauge/analyze.py`` ``_run_policy`` shuffle). The denominator is informative iff configurations genuinely
differ in reliability *beyond* Bernoulli chance at one shared base rate. We compute the between-config
reliability dispersion T, then permute the pooled ok/fail outcomes across the same attempt-slots (n_c
preserved = frequency-matched) R times and read a permutation p-value. τ is invariant to *where* the
failures land; T is exactly about that — so T's excess-over-null is the denominator's marginal signal.

**Verdict.**
  · UNDERPOWERED — too few configs clear the attempt floor (the flagship single-dev regime; forces the
    failure-ledger into existence but cannot size it — [[oss-community-strategy]]'s population argument).
  · BUILD — reliability heterogeneity beats the shuffle null (p < ALPHA) → FI_hat is a genuine new organ.
  · NULL — reliabilities indistinguishable from one shared coin → FI_hat is a better *language* for what τ
    already does, not a new mechanism (still paper/moat value).

Read-only, pure-stdlib, deterministic (audit path(s) as args, seeded permutation, no wall clock), fail-open.
A run over a real audit is a **labeled demonstration, never evidence** (Live = demonstration; the C1–C7
lock rests on topology, not on this).

  python -m cerebral.gauge.fi_gauge --audit .claude/exocortex/audit.jsonl                 # verb altitude
  python -m cerebral.gauge.fi_gauge --audit A.jsonl --audit B.jsonl --altitude command_key
  python -m cerebral.gauge.fi_gauge --audit A.jsonl --json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
from pathlib import Path

# ship/no-ship thresholds (thin — the numbers drive it)
MIN_ATTEMPTS = 5        # a configuration is POWERED (enters the test) only at ≥ this many attempts
MIN_POWERED = 6         # …and the whole gauge abstains (UNDERPOWERED) below this many powered configs
ALPHA = 0.05            # permutation significance for reliability-heterogeneity beyond the shuffle null
PERM_R = 2000           # permutation replicates (seeded → deterministic)
SEED = 0                # fixed RNG seed (mirror analyze.py `random.Random(seed)`)

# verbs whose failures are mechanical noise (path typos / trivial), not "this route is a bad idea" signal —
# reported so a BUILD is never claimed on cd-slash-typo dispersion. Descriptive; does NOT gate the test.
NOISE_VERBS = frozenset({"cd", "echo", "ls", "cat", "pwd", "mkdir", "touch", "which", "export", "env"})


# ------------------------------------------------------------------ load + key
def _load_audit(paths: list) -> list:
    """All parseable JSONL records across the given audit files (fail-open: a missing/garbled file → skip)."""
    rows: list = []
    for p in paths:
        try:
            for line in Path(p).read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        except Exception:
            continue
    return rows


def _verb(command: str) -> str:
    tok = (command or "").strip().split()
    return os.path.basename(tok[0]) if tok else "?"


def _is_noise_verb(config_key: str) -> bool:
    """Is this config's leading verb mechanical noise (cd/echo/ls path-typos), not route-quality? Guarded
    against empty/degenerate keys (a command starting with ``/`` yields ``bash:`` with no verb)."""
    toks = config_key.replace("bash:", "").strip().split()
    verb = toks[0].split("=")[0] if toks else ""
    return verb in NOISE_VERBS


def _config_key(rec: dict, altitude: str) -> str:
    """The configuration ``m`` this Bash consequence belongs to, at the chosen reference-class altitude."""
    if altitude == "command_key":
        return rec.get("command_key") or (rec.get("command", "")[:24]) or "?"
    return f"bash:{_verb(rec.get('command', ''))}"          # 'verb' (default)


def build_configs(rows: list, altitude: str) -> dict:
    """{config_key: [attempts, successes]} over Bash records carrying an ``ok|fail`` outcome."""
    cfg: dict = {}
    for r in rows:
        if r.get("tool") != "Bash" or r.get("outcome") not in ("ok", "fail"):
            continue
        k = _config_key(r, altitude)
        rec = cfg.setdefault(k, [0, 0])
        rec[0] += 1
        if r.get("outcome") == "ok":
            rec[1] += 1
    return cfg


# ------------------------------------------------------------------ FI math
def reliability(n: int, k: int) -> float:
    """KT / Jeffreys add-1/2 smoothed success rate p̂ = (k+½)/(n+1). Bounded off {0,1} so FI_hat is finite
    on a single trial (the small-n discipline: never report an un-smoothed 0/1 as certainty)."""
    return (k + 0.5) / (n + 1.0)


def fi_hat(n: int, k: int) -> float:
    """Functional information in bits: -log2(p̂). Monotone-DECREASING in reliability — a route that always
    works is low-FI ('easy'); a rarely-succeeding one is high-FI (Szostak rarity). Same denominator either
    polarity; curation reads p̂ (keep-reliable), the landscape reads FI_hat (rarity)."""
    return -math.log2(reliability(n, k))


# ------------------------------------------------------------------ decisive statistic
def _dispersion(powered: list) -> tuple:
    """Between-config reliability dispersion on RAW proportions (the homogeneity statistic the permutation
    preserves): T = Σ n_c (k_c/n_c − p̄)² / N, p̄ = ΣK/ΣN. Returns (T, N, K). Smoothing is for display/rank
    only — the *test* is on raw rates so the null (a shuffle of raw outcomes) is exactly matched."""
    N = sum(n for n, _ in powered)
    K = sum(k for _, k in powered)
    if N == 0:
        return 0.0, 0, 0
    pbar = K / N
    T = sum(n * ((k / n) - pbar) ** 2 for n, k in powered) / N
    return T, N, K


def permutation_p(powered: list, r: int = PERM_R, seed: int = SEED) -> dict:
    """Frequency-matched outcome-shuffle null. Pool the ΣK successes + (ΣN−ΣK) failures, repeatedly deal
    them at random into the same per-config attempt-slots (n_c preserved), recompute T. p = (#{T*≥T_obs}+1)/
    (R+1). Degenerate pool (all ok or all fail) → no heterogeneity possible → p=1.0."""
    T_obs, N, K = _dispersion(powered)
    ns = [n for n, _ in powered]
    if N == 0 or K == 0 or K == N:                 # no denominator variance at all
        return {"T_obs": round(T_obs, 6), "p_value": 1.0, "n_perm": 0, "N": N, "K": K, "base_rate": None}
    pool = [1] * K + [0] * (N - K)
    rng = random.Random(seed)
    ge = 0
    for _ in range(r):
        rng.shuffle(pool)
        i = 0
        Tp = 0.0
        pbar = K / N
        for n in ns:
            k = sum(pool[i:i + n])
            i += n
            Tp += n * ((k / n) - pbar) ** 2
        Tp /= N
        if Tp >= T_obs - 1e-12:
            ge += 1
    return {"T_obs": round(T_obs, 6), "p_value": round((ge + 1) / (r + 1), 5),
            "n_perm": r, "N": N, "K": K, "base_rate": round(K / N, 4)}


def _spearman(xs: list, ys: list) -> "float | None":
    """Spearman rank correlation (avg-rank ties). None if <3 points or a constant vector. Descriptive:
    how much the denominator (reliability) RE-RANKS configs vs the τ-analog (success count)."""
    n = len(xs)
    if n < 3:
        return None

    def ranks(v):
        order = sorted(range(n), key=lambda i: v[i])
        rk = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for t in range(i, j + 1):
                rk[order[t]] = avg
            i = j + 1
        return rk

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((ry[i] - my) ** 2 for i in range(n)))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


# ------------------------------------------------------------------ analysis
def analyze(cfg: dict, min_attempts: int, r: int, seed: int) -> dict:
    """Powered configs + FI/τ table, the permutation verdict, τ↔reliability disagreement, and the honest
    noise readout. Pure function of (cfg, thresholds) → deterministic."""
    rows = []
    for key, (n, k) in cfg.items():
        rows.append({
            "config": key, "attempts": n, "successes": k, "failures": n - k,
            "tau_analog": k,                                  # the colony's numerator (ignores attempts)
            "reliability": round(reliability(n, k), 4),       # p̂ — the denominator's contribution
            "fi_hat_bits": round(fi_hat(n, k), 4),
            "powered": n >= min_attempts,
            "noise_verb": _is_noise_verb(key),
        })
    rows.sort(key=lambda x: (-x["attempts"], x["config"]))
    powered_rows = [x for x in rows if x["powered"]]
    powered = [(x["attempts"], x["successes"]) for x in powered_rows]

    perm = permutation_p(powered, r=r, seed=seed)
    rho = _spearman([x["tau_analog"] for x in powered_rows],
                    [x["reliability"] for x in powered_rows])

    # τ↔FI disagreement: high-τ (many successes) but low reliability = 'busy but flaky' — what FI demotes.
    flaky = sorted([x for x in powered_rows if x["failures"] > 0],
                   key=lambda x: (x["reliability"], -x["attempts"]))[:8]

    # honest noise readout — do the failures live on route-quality verbs or on cd/echo path-typo noise?
    tot_fail = sum(x["failures"] for x in rows)
    noise_fail = sum(x["failures"] for x in rows if x["noise_verb"])
    return {
        "counts": {
            "configs": len(rows), "powered": len(powered_rows),
            "attempts_powered": perm["N"], "successes_powered": perm["K"],
            "total_failures": tot_fail, "noise_failures": noise_fail,
            "noise_failure_frac": round(noise_fail / tot_fail, 3) if tot_fail else None,
        },
        "permutation": perm,
        "spearman_tau_vs_reliability": rho,
        "powered_configs": powered_rows,
        "flaky_disagreements": flaky,
    }


def verdict(a: dict, min_powered: int, alpha: float) -> dict:
    """UNDERPOWERED / BUILD / NULL from the powered count + the permutation p-value."""
    c = a["counts"]
    perm = a["permutation"]
    powered = c["powered"]
    p = perm["p_value"]
    if powered < min_powered:
        return {"signal": None, "label": "UNDERPOWERED", "p_value": p, "powered": powered,
                "note": f"UNDERPOWERED — {powered} powered configs < {min_powered}; the denominator instrument "
                        f"is too thin at this traffic to size (single-dev regime). Forces the failure-ledger "
                        f"into existence but cannot gauge it here → needs the population/OSS regime."}
    if perm["K"] in (0, perm["N"]) or perm["base_rate"] is None:
        return {"signal": False, "label": "NULL", "p_value": p, "powered": powered,
                "note": "NULL — no denominator variance (all-ok or all-fail across powered configs); FI_hat "
                        "collapses to a constant → strictly redundant with τ."}
    if p < alpha:
        nf = c["noise_failure_frac"]
        caveat = (f" CAVEAT: {int((nf or 0) * 100)}% of failures are on mechanical-noise verbs "
                  f"(cd/echo/ls path-typos) — inspect flaky_disagreements before trusting the signal."
                  if (nf or 0) >= 0.5 else "")
        return {"signal": True, "label": "BUILD", "p_value": p, "powered": powered,
                "note": f"BUILD — reliability heterogeneity beats the shuffle null (p={p} < {alpha}) on "
                        f"{powered} powered configs → the denominator carries signal τ lacks; FI_hat is a "
                        f"genuine new organ.{caveat}"}
    return {"signal": False, "label": "NULL", "p_value": p, "powered": powered,
            "note": f"NULL — per-config reliabilities are indistinguishable from one shared base rate "
                    f"(p={p} ≥ {alpha}) on {powered} powered configs → the denominator adds nothing here; "
                    f"FI_hat is a better *language* for what τ already does, not a new mechanism."}


def run(audit, altitude: str = "verb", min_attempts: int = MIN_ATTEMPTS,
        min_powered: int = MIN_POWERED, alpha: float = ALPHA, r: int = PERM_R, seed: int = SEED) -> dict:
    """``audit`` is either audit-file path(s) (str/Path or a list of them — the CLI) or an in-memory list of
    record-dicts (tests). Polymorphic so a caller can gauge a live log OR a synthetic corpus deterministically."""
    if altitude not in ("verb", "command_key"):
        raise SystemExit(f"--altitude must be verb|command_key (got {altitude!r})")
    if isinstance(audit, (str, Path)):
        paths, rows = [str(audit)], _load_audit([audit])
    elif audit and isinstance(audit[0], dict):
        paths, rows = ["<in-memory>"], list(audit)          # already-loaded records (tests / a live feed)
    else:
        paths, rows = [str(p) for p in audit], _load_audit(list(audit))
    cfg = build_configs(rows, altitude)
    a = analyze(cfg, min_attempts, r, seed)
    return {
        "audit_paths": [str(p) for p in paths], "altitude": altitude,
        "records": len(rows), "counts": a["counts"], "permutation": a["permutation"],
        "spearman_tau_vs_reliability": a["spearman_tau_vs_reliability"],
        "powered_configs": a["powered_configs"], "flaky_disagreements": a["flaky_disagreements"],
        "verdict": verdict(a, min_powered, alpha),
        "thresholds": {"MIN_ATTEMPTS": min_attempts, "MIN_POWERED": min_powered,
                       "ALPHA": alpha, "PERM_R": r, "SEED": seed},
    }


# ------------------------------------------------------------------ text output
def _fmt(res: dict, top: int = 15) -> str:
    c = res["counts"]
    perm = res["permutation"]
    L = ["FI_hat DECISIVE GAUGE  (does the ATTEMPTS denominator carry signal raw τ does not?)",
         f"  audit={', '.join(Path(p).name for p in res['audit_paths'])}  altitude={res['altitude']}  "
         f"records={res['records']}", "",
         f"  configs={c['configs']}  powered(n≥{res['thresholds']['MIN_ATTEMPTS']})={c['powered']}  "
         f"(attempts={c['attempts_powered']}  successes={c['successes_powered']})",
         f"  failures: total={c['total_failures']}  on-noise-verbs={c['noise_failures']}  "
         f"(noise_frac={c['noise_failure_frac']})",
         f"  base success rate (powered) = {perm['base_rate']}", ""]
    if res["powered_configs"]:
        L.append(f"  POWERED configs  [succ/att  reliability p̂  FI_hat bits]:")
        for x in res["powered_configs"][:top]:
            flag = "NOISE" if x["noise_verb"] else ("flaky" if x["failures"] else "")
            L.append(f"    {x['config']:<30} {x['successes']:>4}/{x['attempts']:<4}  "
                     f"p̂={x['reliability']:.2f}  FI={x['fi_hat_bits']:.2f}  {flag}")
    L += ["",
          f"  DECISIVE — reliability-heterogeneity vs the frequency-matched shuffle null:",
          f"    dispersion T_obs={perm['T_obs']}  permutation p={perm['p_value']}  "
          f"(R={perm['n_perm']}, seed={res['thresholds']['SEED']})",
          f"    Spearman(τ-analog k, reliability p̂) on powered = {res['spearman_tau_vs_reliability']}  "
          f"(≈1 → FI redundant with τ)"]
    if res["flaky_disagreements"]:
        L.append("    what FI would DEMOTE (high-τ but low reliability):")
        for x in res["flaky_disagreements"]:
            L.append(f"      {x['config']:<30} {x['successes']}/{x['attempts']} ok  p̂={x['reliability']:.2f}"
                     f"{'  (mechanical noise)' if x['noise_verb'] else ''}")
    v = res["verdict"]
    L += ["", "VERDICT:",
          f"  label={v['label']}  signal={v['signal']}  p_value={v['p_value']}  powered={v['powered']}",
          f"  => {v['note']}",
          "  NOTE: the audit is the SOLE live denominator (τ has none; intent −1/0 valence unparsed in v1).",
          "        Live = demonstration, never evidence — the C1–C7 lock rests on topology, not on this."]
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="FI_hat Decisive Gauge — does the attempts denominator beat τ?")
    ap.add_argument("--audit", action="append", required=True, metavar="PATH",
                    help="path to an audit.jsonl (repeatable — pool several corpora)")
    ap.add_argument("--altitude", default="verb", choices=["verb", "command_key"],
                    help="reference-class altitude for 'configurations like m' (Amendment 1; default verb)")
    ap.add_argument("--min-attempts", type=int, default=MIN_ATTEMPTS,
                    help=f"a config enters the test at ≥ this many attempts (default {MIN_ATTEMPTS})")
    ap.add_argument("--min-powered", type=int, default=MIN_POWERED,
                    help=f"abstain (UNDERPOWERED) below this many powered configs (default {MIN_POWERED})")
    ap.add_argument("--alpha", type=float, default=ALPHA, help=f"permutation significance (default {ALPHA})")
    ap.add_argument("--perm", type=int, default=PERM_R, help=f"permutation replicates (default {PERM_R})")
    ap.add_argument("--seed", type=int, default=SEED, help=f"RNG seed (default {SEED} — deterministic)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    res = run(args.audit, args.altitude, args.min_attempts, args.min_powered,
              args.alpha, args.perm, args.seed)
    print(json.dumps(res, indent=2) if args.json else _fmt(res), end="" if args.json else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
