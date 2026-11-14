"""Masked-Exit Gauge — what would withholding τ from masked, unverifiable consequences cost? (R1a / rt-tool-1)

An agent that masks a command's exit status (``|| true``, ``; echo "exit: $?"``) makes the Bash tool exit 0,
so the hook judges the outcome from stdout/stderr alone. A fully silenced command (``2>/dev/null || true``)
leaves nothing to read and earns τ on no evidence. R1a would file such a consequence as ``unknown`` (no τ,
no scar). This gauge replays recorded audits and measures that rule's cost: the share of deposits withheld,
any goal-class it would starve, and whether the withheld consequences look BETTER than comparable kept ones
(a same-verb retry proxy, verb-stratified, with a session-cluster bootstrap CI).

Frozen protocol: ``results/masked_exit_v1/PREREG.md`` (the regexes, the variants, the metrics, the rule).
Read-only, pure stdlib, deterministic (fixed seed), fail-open on malformed rows. Emits aggregates and verb
names only — never command text. A run over a live repo is a labeled demonstration.

  python -m exocortex.gauge.masked_exit_gauge --audit .claude/exocortex/audit.jsonl
  python -m exocortex.gauge.masked_exit_gauge --audit A.jsonl --audit B.jsonl --label A --label B --json
"""
from __future__ import annotations

import argparse
import collections
import json
import random
import re
from pathlib import Path

from exocortex.colony import _working_verb as working_verb
from exocortex.hook import classify_outcome

# PREREG §3 — the masking forms, frozen.
MASK_RX = (
    re.compile(r"\|\|\s*(?:true|:)(?=\s*(?:$|[;&|)]))"),   # || true, || :
    re.compile(r"\|\|\s*echo\b"),                            # || echo …
    re.compile(r"\|\|\s*exit\s+0\b"),                        # || exit 0
    re.compile(r"\$\?"),                                     # echo "exit: $?"
    re.compile(r";\s*(?:true|:)\s*$"),                       # trailing ; true
)
PS_MASK_RX = re.compile(r"-ErrorAction\s+SilentlyContinue|2>\$null|Out-Null", re.I)   # PREREG §4 D1 (descriptive)
VARIANTS = ("silent", "masked")
LOSS_PASS, LOSS_FAIL = 0.05, 0.10          # PREREG §5
STARVE_MIN_ROWS, STARVE_SHARE = 5, 0.5     # PREREG §4 C
BOOT_N, BOOT_SEED = 1000, 20261026         # PREREG §4 R
_CONS = ("PostToolUse", "PostToolUseFailure")


def is_masked(cmd: str) -> bool:
    return any(rx.search(cmd or "") for rx in MASK_RX)


def is_silent(output: str) -> bool:
    return not str(output or "").strip()


def has_signature(output: str) -> bool:
    return classify_outcome({"tool_response": {"stdout": str(output or ""), "stderr": ""}}) == "fail"


def population(records) -> tuple:
    """PREREG §3: Bash `ok` rows that today's classifier keeps as ok, each annotated with its class, verb,
    variant membership and same-verb retry flag. Returns ``(rows, ps_descriptive)``."""
    classes: dict = collections.defaultdict(lambda: "_default")
    epoch: dict = collections.defaultdict(int)          # a prompt ends every stream of its session
    streams: dict = collections.defaultdict(list)       # stream key → consequence verbs, in order
    rows = []
    ps_ok = ps_masked = 0
    for r in records:
        s = str(r.get("session", r.get("session_id", "")))
        ev = r.get("event")
        if ev == "UserPromptSubmit":
            m = re.match(r"class=(.+)", str(r.get("reason") or ""))
            classes[s] = m.group(1) if m else "_default"
            epoch[s] += 1
            continue
        if ev not in _CONS:
            continue
        cmd = str(r.get("command") or "")
        if not cmd.strip():
            continue
        key = (s, str(r.get("agent_id") or ""), epoch[s])
        verb = working_verb(cmd)
        pos = len(streams[key])
        streams[key].append(verb)
        tool = r.get("tool")
        if ev != "PostToolUse" or r.get("outcome", "ok") != "ok":
            continue
        out = str(r.get("output") or "")
        if tool == "PowerShell":
            ps_ok += 1
            ps_masked += int(bool(PS_MASK_RX.search(cmd)))
            continue
        if tool != "Bash" or has_signature(out):
            continue
        masked, silent = is_masked(cmd), is_silent(out)
        rows.append({"session": s, "stream": key, "pos": pos, "cls": classes[s], "verb": verb,
                     "silent": masked and silent, "masked": masked})
    for row in rows:
        seq = streams[row.pop("stream")]
        pos = row.pop("pos")
        nxt = seq[pos + 1] if pos + 1 < len(seq) else None
        row["retry"] = int(nxt is not None and nxt == row["verb"])
    return rows, {"ps_ok_rows": ps_ok, "ps_mask_idiom_rows": ps_masked}


def retry_excess(rows: list, variant: str) -> tuple:
    """PREREG §4 R: verb-stratified (withheld − kept) retry rate, weighted by withheld count per verb.
    Returns ``(R or None, dropped_withheld)``."""
    by = collections.defaultdict(lambda: [0, 0, 0, 0])   # verb → [n_w, retry_w, n_k, retry_k]
    for row in rows:
        c = by[row["verb"]]
        if row[variant]:
            c[0] += 1
            c[1] += row["retry"]
        else:
            c[2] += 1
            c[3] += row["retry"]
    num = den = dropped = 0
    for nw, rw, nk, rk in by.values():
        if not nw:
            continue
        if not nk:
            dropped += nw
            continue
        num += nw * (rw / nw - rk / nk)
        den += nw
    return (num / den if den else None), dropped


def bootstrap_ci(rows: list, variant: str, n: int = BOOT_N, seed: int = BOOT_SEED) -> tuple:
    """Session-cluster bootstrap (PREREG §4): resample sessions with replacement, recompute R."""
    by_s = collections.defaultdict(list)
    for row in rows:
        by_s[row["session"]].append(row)
    sessions = sorted(by_s)
    if not sessions:
        return None, None
    rng = random.Random(seed)
    vals = []
    for _ in range(n):
        sample = [row for s in rng.choices(sessions, k=len(sessions)) for row in by_s[s]]
        v, _ = retry_excess(sample, variant)
        if v is not None:
            vals.append(v)
    if not vals:
        return None, None
    vals.sort()
    return vals[int(0.025 * (len(vals) - 1))], vals[int(0.975 * (len(vals) - 1))]


def measure(rows: list, variant: str, boot: int = BOOT_N) -> dict:
    n = len(rows)
    withheld = [r for r in rows if r[variant]]
    per_cls = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        per_cls[r["cls"]][0] += 1
        per_cls[r["cls"]][1] += int(r[variant])
    starved = sum(1 for tot, w in per_cls.values() if tot >= STARVE_MIN_ROWS and w / tot > STARVE_SHARE)
    R, dropped = retry_excess(rows, variant)
    lo, hi = bootstrap_ci(rows, variant, n=boot)
    kept = [r for r in rows if not r[variant]]
    return {
        "population": n, "withheld": len(withheld),
        "L_loss_share": round(len(withheld) / max(1, n), 4),
        "C_starved_classes": starved,
        "R_retry_excess": None if R is None else round(R, 4),
        "R_ci95": [None if lo is None else round(lo, 4), None if hi is None else round(hi, 4)],
        "R_dropped_withheld": dropped,
        "D2_top_withheld_verbs": collections.Counter(r["verb"] for r in withheld).most_common(8),
        "D3_raw_retry": {"withheld": round(sum(r["retry"] for r in withheld) / max(1, len(withheld)), 4),
                         "kept": round(sum(r["retry"] for r in kept) / max(1, len(kept)), 4)},
    }


def verdict(per_store: dict, variant: str) -> dict:
    """PREREG §5, one variant across all stores."""
    ms = [res[variant] for res in per_store.values()]
    hi = [m["R_ci95"][1] for m in ms]
    if any(m["L_loss_share"] > LOSS_FAIL for m in ms) or all(h is not None and h < 0 for h in hi):
        return {"disposition": -1}
    ok = all(m["L_loss_share"] <= LOSS_PASS and m["C_starved_classes"] == 0 and h is not None and h >= 0
             for m, h in zip(ms, hi))
    return {"disposition": 1 if ok else 0}


def _read(path: Path) -> list:
    rows = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if isinstance(r, dict):
                rows.append(r)
    return rows


def run(audit: Path, boot: int = BOOT_N) -> dict:
    rows, ps = population(_read(audit))
    out = {v: measure(rows, v, boot=boot) for v in VARIANTS}
    out["D1_powershell"] = ps
    return out


def _fmt(per_store: dict, verdicts: dict) -> str:
    lines = ["Masked-Exit Gauge (R1a) — PREREG results/masked_exit_v1/PREREG.md"]
    for label, res in per_store.items():
        lines.append(f"[{label}]  PowerShell (descriptive): {res['D1_powershell']}")
        for v in VARIANTS:
            m = res[v]
            lines.append(f"  {v:7s} pop={m['population']} withheld={m['withheld']} L={m['L_loss_share']} "
                         f"C={m['C_starved_classes']} R={m['R_retry_excess']} CI95={m['R_ci95']} "
                         f"dropped={m['R_dropped_withheld']} raw={m['D3_raw_retry']}")
    for v in VARIANTS:
        lines.append(f"verdict[{v}]: {verdicts[v]['disposition']:+d}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Masked-Exit Gauge — the cost of withholding τ (R1a)")
    ap.add_argument("--audit", action="append", default=[], help="audit.jsonl (repeatable)")
    ap.add_argument("--label", action="append", default=[], help="label per --audit (default: stem)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    labels = a.label + [Path(p).parent.parent.parent.name for p in a.audit[len(a.label):]]
    per_store = {lab: run(Path(p)) for lab, p in zip(labels, a.audit)}
    verdicts = {v: verdict(per_store, v) for v in VARIANTS}
    if a.json:
        print(json.dumps({"stores": per_store, "verdicts": verdicts}, indent=1))
    else:
        print(_fmt(per_store, verdicts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
