"""Local alerts — the organism taps you on the shoulder, from YOUR machine (nothing routes through us).

FREE tier engine + safety detectors (safety is never paywalled): a lethal action refused, the metabolic
tier entering HYPOXIA, the audit hash-chain breaking. Paid insight detectors (wiki credit decay, open
tuner-change regression, intent transitions) live in ``exocortex.tuner.alert_rules`` and are lazy-imported
IF PRESENT — in the public tree that module simply does not exist, so the engine runs safety-only.

Design: every detector is a PURE fold ``(prev_state, observation) -> (alerts, new_state)`` over an
observation built from the same stores the exporter reads. Pure folds make the backtest free: replaying an
audit prefix-by-prefix through the same functions is exactly the live behavior, deterministically.

Sinks: a self-hosted webhook (the guaranteed sink — urllib POST, e.g. your own Slack/Discord bridge) and a
best-effort desktop toast (PowerShell / notify-send / osascript). Anti-nag: per-fingerprint cooldown in
``~/.exocortex/notify_state.json``.

Run (cron/scheduled task):
    python -m exocortex.testbed.exporter.notify --scan-root <projects> [--webhook URL] [--desktop]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from exocortex.testbed.exporter import metrics as EXP
from exocortex.integrity import verify_audit

STATE_PATH_DEFAULT = Path.home() / ".exocortex" / "notify_state.json"
COOLDOWN_RUNS = 1          # identical fingerprint suppressed for this many subsequent runs


@dataclass
class Alert:
    repo: str
    kind: str                 # lethal_refused | tier_hypoxia | chain_broken | (paid kinds)
    severity: str             # critical | warning | info
    message: str
    fingerprint: str          # dedup key (stable for the SAME ongoing condition)
    evidence: dict

    def to_dict(self) -> dict:
        return asdict(self)


def observe(repo: dict) -> dict:
    """One repo's alert-relevant observation — the same stores the exporter scrapes, nothing more."""
    sd = Path(repo["state_dir"])
    genome = EXP.load_genome_for(repo.get("config_path"))
    v = EXP.repo_vitals(sd, genome)
    chain = verify_audit(sd / "audit.jsonl")
    return {"lethal_total": v.get("lethal_attempts", 0), "tier": (v.get("tier", {}) or {}).get("now", ""),
            "chain_ok": bool(chain.get("ok")), "chain_msg": chain.get("message", ""),
            "chain_records": chain.get("records", 0), "vitals": v}


# ------------------------------------------------------------- free safety detectors (pure folds)
def detect_lethal(prev: dict, obs: dict, repo: str) -> tuple[list, dict]:
    """New somatic refusals since the last look — each one is a story the operator should hear."""
    seen = int(prev.get("lethal_total", obs["lethal_total"]))
    new = obs["lethal_total"] - seen
    alerts = []
    if new > 0:
        alerts.append(Alert(repo, "lethal_refused", "critical",
                            f"{new} lethal action(s) refused by the somatic gate since last check "
                            f"(lifetime {obs['lethal_total']})",
                            f"lethal:{repo}:{obs['lethal_total']}",
                            {"new": new, "lifetime": obs["lethal_total"]}))
    return alerts, {"lethal_total": obs["lethal_total"]}


def detect_hypoxia(prev: dict, obs: dict, repo: str) -> tuple[list, dict]:
    """Alert on ENTERING hypoxia (the edge, not the level — anti-nag by construction)."""
    was = prev.get("tier", "")
    alerts = []
    if obs["tier"] == "HYPOXIA" and was != "HYPOXIA":
        alerts.append(Alert(repo, "tier_hypoxia", "warning",
                            "metabolic tier entered HYPOXIA — the organism is running on fumes "
                            "(deep repetition/failure pressure)",
                            f"hypoxia:{repo}", {"from": was or "?"}))
    return alerts, {"tier": obs["tier"]}


def detect_chain(prev: dict, obs: dict, repo: str) -> tuple[list, dict]:
    """A hash-chain break is a tamper/corruption signal on the medical record itself."""
    was_ok = prev.get("chain_ok", True)
    alerts = []
    if not obs["chain_ok"] and was_ok and obs["chain_records"] > 0:
        alerts.append(Alert(repo, "chain_broken", "critical",
                            f"audit hash-chain FAILED verification: {obs['chain_msg']}",
                            f"chain:{repo}:{obs['chain_msg']}", {"records": obs["chain_records"]}))
    return alerts, {"chain_ok": obs["chain_ok"]}


FREE_DETECTORS = (detect_lethal, detect_hypoxia, detect_chain)


def _paid_detectors():
    """The commercial insight rules, IF this tree carries them (the public tree does not)."""
    try:
        from exocortex.tuner.alert_rules import DETECTORS
        return tuple(DETECTORS)
    except Exception:
        return ()


# ------------------------------------------------------------------ engine
def run_detectors(prev_repo_state: dict, obs: dict, repo: str, detectors=None) -> tuple[list, dict]:
    """Fold every detector over one repo's observation. Pure given (state, obs)."""
    alerts: list = []
    new_state: dict = {}
    for det in (detectors if detectors is not None else FREE_DETECTORS + _paid_detectors()):
        a, s = det(prev_repo_state, obs, repo)
        alerts.extend(a)
        new_state.update(s)
    return alerts, new_state


def dedup(alerts: list, state: dict) -> list:
    """Suppress fingerprints already fired within the cooldown; count runs, not wall-clock."""
    fired: dict = state.setdefault("fingerprints", {})
    out = []
    for a in alerts:
        if a.fingerprint in fired and fired[a.fingerprint] <= COOLDOWN_RUNS:
            continue
        fired[a.fingerprint] = 0
        out.append(a)
    for fp in list(fired):
        fired[fp] += 1
        if fired[fp] > COOLDOWN_RUNS + 1:
            del fired[fp]                      # forgotten — the condition may alert again
    return out


# ------------------------------------------------------------------ sinks
def sink_webhook(alerts: list, url: str) -> bool:
    body = json.dumps({"source": "sentaince-notify", "alerts": [a.to_dict() for a in alerts]}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except Exception as e:
        print(f"[notify] webhook failed: {e}", file=sys.stderr)
        return False


def desktop_command(alert: Alert) -> list[str]:
    """The toast command per platform — returned (not run) so tests assert construction, not popups."""
    title = f"SentAInce · {alert.repo}"
    if sys.platform == "win32":
        script = ("[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                  "ContentType = WindowsRuntime] > $null; "
                  "$x = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                  "[Windows.UI.Notifications.ToastTemplateType]::ToastText02); "
                  "$t = $x.GetElementsByTagName('text'); "
                  f"$t.Item(0).AppendChild($x.CreateTextNode('{title}')) > $null; "
                  f"$t.Item(1).AppendChild($x.CreateTextNode('{alert.message[:180]}')) > $null; "
                  "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("
                  "'SentAInce').Show([Windows.UI.Notifications.ToastNotification]::new($x))")
        return ["powershell", "-NoProfile", "-Command", script]
    if sys.platform == "darwin":
        return ["osascript", "-e",
                f'display notification "{alert.message[:180]}" with title "{title}"']
    return ["notify-send", title, alert.message[:180]]


def sink_desktop(alerts: list) -> None:
    for a in alerts:
        try:
            subprocess.run(desktop_command(a), timeout=10, capture_output=True)
        except Exception as e:                 # best-effort by contract
            print(f"[notify] desktop toast failed: {e}", file=sys.stderr)


# ------------------------------------------------------------------ CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="SentAInce local alerts (safety free; nothing leaves your machine)")
    ap.add_argument("--scan-root", action="append", default=[])
    ap.add_argument("--registry", default=None)
    ap.add_argument("--root", action="append", default=[], help="explicit repo root (repeatable)")
    ap.add_argument("--webhook", default=None, help="self-hosted webhook URL (the guaranteed sink)")
    ap.add_argument("--desktop", action="store_true", help="best-effort desktop toast")
    ap.add_argument("--state", default=str(STATE_PATH_DEFAULT))
    ap.add_argument("--dry-run", action="store_true", help="print alerts, save no state, fire no sinks")
    args = ap.parse_args(argv)

    repos = EXP.discover_repos([Path(p) for p in args.scan_root],
                               Path(args.registry) if args.registry else None, None)
    for r in args.root:
        rec = EXP._repo_record(Path(r))
        if rec["name"] not in {x["name"] for x in repos}:
            repos.append(rec)
    if not repos:
        print("no repos discovered — pass --root or --scan-root", file=sys.stderr)
        return 2

    state_path = Path(args.state)
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        state = {}

    all_alerts: list = []
    for rec in sorted(repos, key=lambda r: r["name"]):
        obs = observe(rec)
        slot = state.setdefault("repos", {}).setdefault(rec["name"], {})
        alerts, new_slot = run_detectors(slot, obs, rec["name"])
        slot.update(new_slot)
        all_alerts.extend(alerts)

    fresh = dedup(all_alerts, state)
    for a in fresh:
        print(f"[{a.severity.upper():8}] {a.repo} · {a.kind}: {a.message}")
    if not fresh:
        print("[notify] all quiet.")

    if not args.dry_run:
        if fresh and args.webhook:
            sink_webhook(fresh, args.webhook)
        if fresh and args.desktop:
            sink_desktop(fresh)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
