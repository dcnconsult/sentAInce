"""F3 provenance / non-stationarity organ — per-edge (ts, model) stamping + recency/version readout decay.

Ships DORMANT (PROV_MODE 'off'): recording is inert unless a caller passes `ts`, and the readout uses raw τ.
These tests drive the live behavior by monkeypatching the module mode, mirroring the eligibility-trace tests.
"""
import json
import time

from exocortex import colony as C

SEP = C._SEP


def test_dormant_by_default_no_ts_no_meta_and_save_omits_lane(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    col = C.Colony(label="noprov")
    col.deposit([("a", "b"), ("b", "c")])        # no ts → no provenance recorded
    assert col.meta == {}
    col.save()
    d = json.loads((tmp_path / "colony_noprov.json").read_text(encoding="utf-8"))
    assert "meta" not in d                       # byte-identical to the pre-F3 colony shape
    assert set(d) == {"label", "tau", "deposits"}


def test_off_mode_readout_is_raw_tau():
    col = C.Colony(tau={f"a{SEP}b": 1.0, f"c{SEP}d": 1.0},
                   meta={f"a{SEP}b": {"ts": 1.0, "model": ""}})
    assert C.PROV_MODE == "off"                  # genome default
    assert col._eff_tau(now=1e9) is col.tau      # no copy, no decay → identical object


def test_recency_decays_readout_and_spares_legacy_edges(monkeypatch):
    monkeypatch.setattr(C, "PROV_MODE", "recency")
    monkeypatch.setattr(C, "PROV_HALFLIFE_S", 10.0)      # 10-second half-life for a sharp assertion
    col = C.Colony(tau={f"a{SEP}b": 1.0, f"c{SEP}d": 1.0, f"e{SEP}f": 1.0},
                   meta={f"a{SEP}b": {"ts": 100.0, "model": ""},   # age 0  → ×1.0
                         f"c{SEP}d": {"ts": 90.0, "model": ""}})    # age 10 → ×0.5 ; e→f unstamped → ×1.0
    eff = col._eff_tau(now=100.0)
    assert abs(eff[f"a{SEP}b"] - 1.0) < 1e-9
    assert abs(eff[f"c{SEP}d"] - 0.5) < 1e-9             # exactly one half-life older
    assert abs(eff[f"e{SEP}f"] - 1.0) < 1e-9             # legacy/unstamped edge is NEVER penalized (fail-open)


def test_recency_can_flip_the_dominant_route(monkeypatch):
    monkeypatch.setattr(C, "PROV_MODE", "recency")
    monkeypatch.setattr(C, "PROV_HALFLIFE_S", 10.0)
    now = time.time()
    # raw τ favors the STALE edge (1.5 > 1.0), but it is ancient → recency demotes it below the fresh one.
    col = C.Colony(tau={f"a{SEP}stale": 1.5, f"a{SEP}fresh": 1.0},
                   meta={f"a{SEP}stale": {"ts": now - 1e6}, f"a{SEP}fresh": {"ts": now}})
    assert col.dominant_path()[:2] == ["a", "fresh"]


def test_full_mode_applies_version_penalty(monkeypatch):
    monkeypatch.setattr(C, "PROV_MODE", "full")
    monkeypatch.setattr(C, "PROV_HALFLIFE_S", 1e12)      # neutralize recency → isolate the version term
    monkeypatch.setattr(C, "PROV_VERSION_PENALTY", 0.5)
    monkeypatch.setenv("EXOCORTEX_MODEL", "claude-opus-4-8")
    now = time.time()
    col = C.Colony(tau={f"a{SEP}same": 1.0, f"a{SEP}diff": 1.0, f"a{SEP}none": 1.0},
                   meta={f"a{SEP}same": {"ts": now, "model": "claude-opus-4-8"},
                         f"a{SEP}diff": {"ts": now, "model": "old-model"},
                         f"a{SEP}none": {"ts": now, "model": ""}})
    eff = col._eff_tau(now=now)
    assert abs(eff[f"a{SEP}same"] - 1.0) < 1e-6          # current model → no penalty
    assert abs(eff[f"a{SEP}diff"] - 0.5) < 1e-6          # stale model → penalized
    assert abs(eff[f"a{SEP}none"] - 1.0) < 1e-6          # unknown stamped model → fail-open (no penalty)


def test_deposit_stamps_and_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    col = C.Colony(label="prov")
    col.deposit([("a", "b"), ("b", "c")], ts=123.0, model="claude-opus-4-8")
    assert col.meta[f"a{SEP}b"] == {"ts": 123.0, "model": "claude-opus-4-8"}
    col.save()
    col2 = C.Colony.load("prov")
    assert col2.meta[f"b{SEP}c"]["ts"] == 123.0 and col2.meta[f"b{SEP}c"]["model"] == "claude-opus-4-8"


def test_meta_is_pruned_in_lockstep_with_tau():
    col = C.Colony()
    col.deposit([("a", "b")], ts=1.0)                    # a→b stamped
    assert f"a{SEP}b" in col.meta
    for _ in range(60):
        col.deposit([("c", "d")], ts=2.0)                # a→b decays past the prune floor → its meta goes too
    assert f"a{SEP}b" not in col.tau and f"a{SEP}b" not in col.meta
    assert f"c{SEP}d" in col.meta                        # the live edge keeps its stamp


def test_consolidate_prunes_meta_in_lockstep_with_tau(tmp_path, monkeypatch):
    """consolidate() must sync meta to the pruned/capped τ, exactly as deposit() does.
    Without it, a consolidated colony carries ORPHANED provenance on disk (meta keys with
    no τ edge) — an on-disk break of the meta ⊆ tau invariant, cleaned only on the next
    load()/deposit(). Regression guard for that gap (deposit was covered; consolidate was not)."""
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path))
    ab = C.PRUNE / C.DECAY * 0.99                         # one decay pass drops it just below the prune floor
    col = C.Colony(label="cons",
                   tau={f"a{SEP}b": ab, f"c{SEP}d": 5.0},
                   meta={f"a{SEP}b": {"ts": 1.0, "model": "m"},
                         f"c{SEP}d": {"ts": 2.0, "model": "m"}})
    col.consolidate()                                    # a→b decays below the floor → pruned; c→d survives
    assert f"a{SEP}b" not in col.tau
    assert f"a{SEP}b" not in col.meta                    # provenance pruned in lockstep (no orphan)
    assert f"c{SEP}d" in col.tau and f"c{SEP}d" in col.meta   # the survivor keeps its stamp
    col.save()                                           # and the on-disk file satisfies meta ⊆ tau
    d = json.loads((tmp_path / "colony_cons.json").read_text(encoding="utf-8"))
    assert set(d.get("meta", {})) <= set(d.get("tau", {}))
