"""Free-tier alert engine tests (P1.2). OUT of the 99-lock; run explicitly:

    python -m pytest exocortex/tests/test_notify.py

The detectors are pure folds, so the backtest IS the live behavior: replaying the real audit record by
record through the same functions must produce alert counts that match an independent count of the
underlying events — deterministically.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from exocortex.testbed.exporter import notify as N

# this repo's own live store — machine-independent, and skipped cleanly where hooks aren't deployed
LIVE_AUDIT = Path(__file__).resolve().parents[2] / ".claude" / "exocortex" / "audit.jsonl"


def _records(path: Path) -> list:
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def _backtest(records: list) -> dict:
    """Replay chronologically: after each record, poll the lethal + hypoxia folds."""
    state: dict = {}
    counts = {"lethal_refused": 0, "tier_hypoxia": 0}
    lethal_total = 0
    tier = ""
    for r in records:
        if r.get("event") == "PreToolUse" and r.get("somatic_permitted") is False:
            lethal_total += 1
        tier = r.get("tier") or tier
        obs = {"lethal_total": lethal_total, "tier": tier, "chain_ok": True,
               "chain_msg": "", "chain_records": 1, "vitals": {}}
        alerts, s = N.run_detectors(state, obs, "bt", detectors=(N.detect_lethal, N.detect_hypoxia))
        state.update(s)
        for a in alerts:
            counts[a.kind] += 1
    return counts


@pytest.mark.skipif(not LIVE_AUDIT.exists(), reason="live store not on this machine")
def test_backtest_matches_independent_counts_on_the_real_audit():
    records = _records(LIVE_AUDIT)
    counts = _backtest(records)
    lethal_truth = sum(1 for r in records
                      if r.get("event") == "PreToolUse" and r.get("somatic_permitted") is False)
    # HYPOXIA *entries*: transitions of the tier sequence into HYPOXIA (the edge, not the level)
    seq = [r.get("tier") for r in records if r.get("tier")]
    entries_truth = sum(1 for i, t in enumerate(seq)
                        if t == "HYPOXIA" and (i == 0 or seq[i - 1] != "HYPOXIA"))
    assert counts["lethal_refused"] == lethal_truth
    assert counts["tier_hypoxia"] == entries_truth
    assert _backtest(records) == counts                       # deterministic


def test_lethal_detector_fires_on_increment_only():
    alerts, s = N.detect_lethal({}, {"lethal_total": 5}, "r")
    assert alerts == [] and s == {"lethal_total": 5}          # first look = baseline, no retro-alarm
    alerts, s = N.detect_lethal(s, {"lethal_total": 7}, "r")
    assert len(alerts) == 1 and alerts[0].evidence["new"] == 2
    alerts, _ = N.detect_lethal(s, {"lethal_total": 7}, "r")
    assert alerts == []


def test_hypoxia_alerts_on_the_edge_not_the_level():
    a1, s = N.detect_hypoxia({}, {"tier": "HYPOXIA"}, "r")
    assert len(a1) == 1
    a2, s2 = N.detect_hypoxia(s, {"tier": "HYPOXIA"}, "r")
    assert a2 == []                                           # still hypoxic — no nag
    _, s3 = N.detect_hypoxia(s2, {"tier": "SATED"}, "r")
    a4, _ = N.detect_hypoxia(s3, {"tier": "HYPOXIA"}, "r")
    assert len(a4) == 1                                       # re-entry alerts again


def test_chain_break_alerts_once_and_missing_store_is_silent():
    obs_bad = {"chain_ok": False, "chain_msg": "link broken", "chain_records": 10}
    a, s = N.detect_chain({}, obs_bad, "r")
    assert len(a) == 1 and a[0].severity == "critical"
    a2, _ = N.detect_chain(s, obs_bad, "r")
    assert a2 == []                                           # already known-broken
    a3, _ = N.detect_chain({}, {"chain_ok": False, "chain_msg": "unreadable", "chain_records": 0}, "r")
    assert a3 == []                                           # no store yet != tamper


def test_dedup_cooldown_suppresses_identical_fingerprints():
    state: dict = {}
    mk = lambda: [N.Alert("r", "k", "info", "m", "fp1", {})]
    assert len(N.dedup(mk(), state)) == 1
    assert len(N.dedup(mk(), state)) == 0                     # cooldown run
    assert len(N.dedup([], state)) == 0
    assert len(N.dedup(mk(), state)) == 1                     # forgotten -> fires again


def test_webhook_sink_posts_json():
    got = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            got.update(json.loads(self.rfile.read(n)))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        ok = N.sink_webhook([N.Alert("r", "lethal_refused", "critical", "msg", "fp", {"new": 1})],
                            f"http://127.0.0.1:{srv.server_address[1]}/hook")
        assert ok and got["source"] == "sentaince-notify"
        assert got["alerts"][0]["kind"] == "lethal_refused"
    finally:
        srv.shutdown()


def test_desktop_command_is_constructed_not_run():
    cmd = N.desktop_command(N.Alert("r", "k", "info", 'a "quiet" message', "fp", {}))
    assert isinstance(cmd, list) and cmd and any("SentAInce" in part for part in cmd)
