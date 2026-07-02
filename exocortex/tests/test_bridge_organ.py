"""Hippocampus bridge organ — slices 1-2: model + 0-well gate + persistence + sleep synthesis (Ticket 2)."""

import pytest

from exocortex.wiki import bridge as br
from exocortex.wiki.bridge import ProvisionalBridge
from exocortex.wiki.node import ExonNode, WikiGraph


def test_bridge_dormant_by_default(monkeypatch):
    monkeypatch.delenv("EXOCORTEX_BRIDGE", raising=False)
    from exocortex.config import bridge_enabled
    from exocortex.genome import GENOME
    assert bridge_enabled() is False
    assert GENOME["declarative"]["bridge"]["mode"] == "off"


def test_0well_gate_keeps_confident_basin_abstains_otherwise():
    assert br.bridge_gate(0.20, 0.10) is True                      # above wall + clear gap → keep
    assert br.bridge_gate(0.10, 0.00) is False                     # below 0.14 wall → 0-well abstain
    assert br.bridge_gate(0.20, 0.18) is False                     # gap 0.02 < 0.03 → ambiguous tie, abstain
    assert br.bridge_gate(0.50, 0.40, conf_floor=0.14, margin=0.2) is False   # explicit margin not met


def test_persistence_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    bridges = {}
    br.upsert_candidate(bridges, "a.md#1", "b.md#2", 0.31, stamp="t0")
    br.save_bridges(bridges)
    reloaded = br.load_bridges()
    assert set(reloaded) == set(bridges)
    b = reloaded["a.md#1\tb.md#2"]
    assert b.a == "a.md#1" and b.d == "b.md#2" and b.conf == 0.31 and b.status == br.PROPOSED


def test_upsert_dedups_refreshes_and_respects_verdicts():
    bridges = {}
    assert br.upsert_candidate(bridges, "a", "d", 0.2) is True     # new
    assert br.upsert_candidate(bridges, "a", "d", 0.4) is False    # dup → not re-added
    assert bridges["a\td"].conf == 0.4                             # ...but conf refreshed

    bridges["a\td"].status = br.SCARRED                            # an immortal verdict
    assert br.upsert_candidate(bridges, "a", "d", 0.9) is False
    assert bridges["a\td"].status == br.SCARRED                    # never resurrected
    assert bridges["a\td"].conf == 0.4                             # and not refreshed once scarred

    bridges["x\ty"] = ProvisionalBridge(a="x", d="y", conf=0.5, status=br.CONFIRMED)
    assert br.upsert_candidate(bridges, "x", "y", 0.9) is False
    assert bridges["x\ty"].status == br.CONFIRMED                  # confirmed undisturbed


def test_upsert_respects_max_provisional():
    bridges = {}
    assert br.upsert_candidate(bridges, "a", "b", 0.2, max_provisional=2) is True
    assert br.upsert_candidate(bridges, "a", "c", 0.2, max_provisional=2) is True
    assert br.upsert_candidate(bridges, "a", "e", 0.2, max_provisional=2) is False   # at the cap
    # a scarred/confirmed bridge does not count against the live cap
    bridges["a\tb"].status = br.SCARRED
    assert br.upsert_candidate(bridges, "a", "f", 0.2, max_provisional=2) is True


# --------------------------------------------------------------- slice 2: sleep synthesis
def _graph_with_bank(np, rows: dict, links=None, colony_tau=None):
    """A WikiGraph whose phasor_bank is set by hand (rows: id -> (M,) int8) — no MiniLM."""
    from exocortex.colony import Colony
    g = WikiGraph()
    for nid in rows:
        g.add(ExonNode(id=nid, text=nid, links=tuple((links or {}).get(nid, ()))))
    ordered = []
    for i, (nid, node) in enumerate(g.nodes.items()):
        node.phasor_ix = i
        ordered.append(rows[nid])
    g.phasor_bank = np.stack(ordered).astype(np.int8)
    if colony_tau is not None:
        g.colony = Colony(label="_t")
        g.colony.tau = colony_tau
    return g


def test_synthesize_proposes_confident_bridge_and_applies_filters(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    rng = np.random.default_rng(0)
    M = 64
    base = rng.integers(0, 3, M).astype(np.int8)
    rows = {
        "A.md#1": base,
        "D.md#1": base.copy(),                              # identical to A → familiarity 1.0 (confident)
        "C.md#1": rng.integers(0, 3, M).astype(np.int8),    # random → below the 0-well wall
        "ldoc.md#1": base.copy(),                           # also ≈A, but A already [[links]] it → excluded
    }
    g = _graph_with_bank(np, rows, links={"A.md#1": ("ldoc",)})
    bridges = br.synthesize(g, bridges={}, stamp="t")

    assert "A.md#1\tD.md#1" in bridges                      # near + eligible → proposed
    assert bridges["A.md#1\tD.md#1"].conf >= 0.9
    assert "A.md#1\tldoc.md#1" not in bridges               # already linked → filtered
    assert "A.md#1\tC.md#1" not in bridges                  # random → 0-well abstain
    # D sees A AND ldoc equally near (a tie) → no confident distinct basin → D abstains
    assert "D.md#1\tA.md#1" not in bridges


def test_synthesize_skips_cowalked_pairs(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    rng = np.random.default_rng(1)
    M = 64
    base = rng.integers(0, 3, M).astype(np.int8)
    rows = {"A.md#1": base, "X.md#1": base.copy(), "Z.md#1": rng.integers(0, 3, M).astype(np.int8)}
    g = _graph_with_bank(np, rows, colony_tau={"A.md#1\tX.md#1": 0.5})   # A and X already co-walked
    bridges = br.synthesize(g, bridges={}, stamp="t")
    assert "A.md#1\tX.md#1" not in bridges and "X.md#1\tA.md#1" not in bridges


def test_synthesize_without_phasor_bank_is_noop(tmp_path, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    g = WikiGraph()
    g.add(ExonNode(id="a#1", text="a"))
    assert br.synthesize(g, bridges={}) == {}


# --------------------------------------------------------------- slice 3: offer channel
def _graph(nodes):
    g = WikiGraph()
    for nid, text in nodes:
        g.add(ExonNode(id=nid, text=text, heading_path=(nid.split("#")[0],)))
    return g


def test_offer_surfaces_bridge_for_raised_source_and_marks_attribution():
    g = _graph([("a.md#1", "source note"), ("d.md#1", "DESTINATION TEXT")])
    bridges = {"a.md#1\td.md#1": ProvisionalBridge(a="a.md#1", d="d.md#1", conf=0.9, status=br.PROPOSED)}
    payload, endpoints = offer_call(g, bridges, candidate_ids=["a.md#1"])
    assert "DESTINATION TEXT" in payload and "PROVISIONAL" in payload and "⇢" in payload
    assert endpoints == ["a.md#1", "d.md#1"]                 # both endpoints → attribution surface
    assert bridges["a.md#1\td.md#1"].status == br.OFFERED    # marked offered


def test_offer_skips_unraised_scarred_and_confirmed():
    g = _graph([("a.md#1", "s"), ("d.md#1", "d"), ("x.md#1", "x")])
    bridges = {
        "a.md#1\td.md#1": ProvisionalBridge(a="a.md#1", d="d.md#1", conf=0.9, status=br.PROPOSED),
        "x.md#1\td.md#1": ProvisionalBridge(a="x.md#1", d="d.md#1", conf=0.9, status=br.SCARRED),
    }
    # source a is NOT in candidates → nothing surfaced
    assert offer_call(g, bridges, candidate_ids=["zzz"]) == ("", [])
    # x is raised but its bridge is scarred → still nothing
    assert offer_call(g, bridges, candidate_ids=["x.md#1"]) == ("", [])


def test_offer_skips_scarred_destination_and_respects_cap():
    g = _graph([("a.md#1", "s"), ("d.md#1", "d"), ("e.md#1", "e"), ("f.md#1", "f")])
    g.scar("d.md#1")
    bridges = {
        "a.md#1\td.md#1": ProvisionalBridge(a="a.md#1", d="d.md#1", conf=0.9, status=br.PROPOSED),
        "a.md#1\te.md#1": ProvisionalBridge(a="a.md#1", d="e.md#1", conf=0.8, status=br.PROPOSED),
        "a.md#1\tf.md#1": ProvisionalBridge(a="a.md#1", d="f.md#1", conf=0.7, status=br.PROPOSED),
    }
    payload, endpoints = offer_call(g, bridges, candidate_ids=["a.md#1"], offer_cap=1)
    assert "d.md#1" not in endpoints                          # scarred destination vetoed
    assert endpoints == ["a.md#1", "e.md#1"]                  # cap=1 → only the top-conf eligible (e > f)


def offer_call(g, bridges, candidate_ids, **kw):
    return br.offer(g, bridges, candidate_ids, **kw)


# --------------------------------------------------------------- slice 4: verify (crystallize / scar)
def _graph_with_colony(tmp_path, monkeypatch, nodes):
    from exocortex.colony import Colony
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    g = _graph(nodes)
    g.colony = Colony(label="_t")
    return g


def test_verify_crystallizes_walked_bridge_on_exit0(tmp_path, monkeypatch):
    g = _graph_with_colony(tmp_path, monkeypatch, [("a.md#1", "A"), ("d.md#1", "D")])
    bridges = {"a.md#1\td.md#1": ProvisionalBridge(a="a.md#1", d="d.md#1", conf=0.9, status=br.OFFERED)}
    n_cryst, n_scar = br.verify(g, bridges, used=["a.md#1", "d.md#1"], exit_code=0, label="_t")
    assert (n_cryst, n_scar) == (1, 0)
    assert bridges["a.md#1\td.md#1"].status == br.CONFIRMED
    assert g.colony.tau.get("a.md#1\td.md#1", 0) > 0          # crystallized as a real, earned colony edge


def test_verify_no_crystallize_if_not_walked(tmp_path, monkeypatch):
    g = _graph_with_colony(tmp_path, monkeypatch, [("a.md#1", "A"), ("d.md#1", "D")])
    bridges = {"a.md#1\td.md#1": ProvisionalBridge(a="a.md#1", d="d.md#1", conf=0.9, status=br.OFFERED)}
    # only A used, not D → not a walk
    assert br.verify(g, bridges, used=["a.md#1"], exit_code=0, label="_t") == (0, 0)
    assert bridges["a.md#1\td.md#1"].status == br.OFFERED
    assert g.colony.tau == {}


def test_verify_scars_only_after_k_nopay_walks(tmp_path, monkeypatch):
    g = _graph_with_colony(tmp_path, monkeypatch, [("a.md#1", "A"), ("d.md#1", "D")])
    b = ProvisionalBridge(a="a.md#1", d="d.md#1", conf=0.9, status=br.OFFERED)
    bridges = {b.key(): b}
    for i in range(br.SCAR_AFTER_K_WALKS - 1):               # patience: failed walks below K don't scar
        assert br.verify(g, bridges, used=["a.md#1", "d.md#1"], exit_code=1, label="_t") == (0, 0)
        assert b.status == br.OFFERED and b.walks == i + 1
    assert br.verify(g, bridges, used=["a.md#1", "d.md#1"], exit_code=1, label="_t") == (0, 1)
    assert b.status == br.SCARRED                            # K-th failed walk → immortal scar


def test_verify_ignores_non_offered_bridges(tmp_path, monkeypatch):
    g = _graph_with_colony(tmp_path, monkeypatch, [("a.md#1", "A"), ("d.md#1", "D")])
    bridges = {"a.md#1\td.md#1": ProvisionalBridge(a="a.md#1", d="d.md#1", conf=0.9, status=br.CONFIRMED)}
    assert br.verify(g, bridges, used=["a.md#1", "d.md#1"], exit_code=0, label="_t") == (0, 0)
    assert bridges["a.md#1\td.md#1"].status == br.CONFIRMED  # a confirmed bridge is never re-crystallized


# --------------------------------------------------------------- the loop closes (e2e via real hooks)
def test_bridge_loop_e2e_synthesize_offer_walk_crystallize(tmp_path, monkeypatch):
    """Through the actual handlers: sleep SYNTHESIZES alpha⇢delta (geometrically near), the next prompt
    OFFERS it, the model WALKS both endpoints, and the exit-0 CRYSTALLIZES the bridge. No MiniLM (the
    embedder is monkeypatched to deterministic vectors)."""
    np = pytest.importorskip("numpy")

    from exocortex.wiki import digest as digest_mod
    rng = np.random.default_rng(0)
    v1 = rng.standard_normal(64); v1 /= np.linalg.norm(v1)        # alpha & delta share this → near
    v2 = rng.standard_normal(64); v2 /= np.linalg.norm(v2)        # zeta → far
    monkeypatch.setattr(digest_mod, "_dense_embed",
                        lambda t: v1 if ("alphacmd" in t or "deltacmd" in t) else v2)

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "alpha.md").write_text("# Alpha task\n\nRun `alphacmd --build` to start.\n", encoding="utf-8")
    (vault / "delta.md").write_text("# Delta task\n\nThen `deltacmd --ship` to finish.\n", encoding="utf-8")
    (vault / "zeta.md").write_text("# Zeta\n\nUnrelated prose about turtles.\n", encoding="utf-8")
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("EXOCORTEX_WIKI_VAULT", str(vault))
    monkeypatch.setenv("EXOCORTEX_DECLARATIVE", "1")
    monkeypatch.setenv("EXOCORTEX_BRIDGE", "1")
    monkeypatch.setenv("EXOCORTEX_COLONY", "0")                   # stable goal_class=_default

    from exocortex import hook
    from exocortex.config import Mode
    from exocortex.wiki import bridge as bridge_mod
    sid = "be2e"

    # 1) SLEEP — geometry proposes alpha⇢delta (near; zeta far)
    hook.handle_precompact({"session_id": sid}, Mode.OBSERVE)
    proposed = bridge_mod.load_bridges()
    assert any(b.a.startswith("alpha") and b.d.startswith("delta") for b in proposed.values()), \
        "sleep should propose the alpha⇢delta bridge"

    # 2) PROMPT raises alpha → the bridge is OFFERED (alpha⇢delta), endpoints enter the attribution surface
    out = hook.handle_userpromptsubmit({"session_id": sid, "prompt": "do the alpha build"}, Mode.OBSERVE)
    assert out and "PROVISIONAL" in out["hookSpecificOutput"]["additionalContext"]

    # 3) WALK both endpoints + exit-0 → CRYSTALLIZE
    cmd = "alphacmd --build && deltacmd --ship"
    hook._buffer_action(sid, "Bash", {"tool_input": {"command": cmd}})
    hook.handle_consequence(
        {"session_id": sid, "tool_name": "Bash", "tool_input": {"command": cmd},
         "tool_response": {"stdout": "ok"}}, Mode.OBSERVE, "ok")

    after = bridge_mod.load_bridges()
    assert any(b.status == bridge_mod.CONFIRMED and b.a.startswith("alpha") and b.d.startswith("delta")
               for b in after.values()), "walking the bridge to exit-0 should crystallize it"
