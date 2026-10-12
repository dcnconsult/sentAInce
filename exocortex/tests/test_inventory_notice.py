"""Memory inventory notice (sibling UserPromptSubmit hook) — reconciliation law, modes, the never-writes
discipline, fail-open, and that the ADR-016-pinned control plane is untouched."""
import hashlib
import io
import subprocess
import sys
from pathlib import Path

import pytest

from exocortex.colony import _SEP, Colony
from exocortex.wiki import inventory as inv
from exocortex.wiki.digest import digest_document


# ----------------------------------------------------------------- pure reconciliation
def test_reconcile_classifies_removed_and_changed_exactly():
    anchors = ["a.md#111", "b.md#222", "c.md#333"]
    nodes = ["a.md#111", "b.md#999", "d.md#444"]                 # b edited, c deleted, d uncredited
    rec = inv.reconcile(anchors, nodes)
    assert rec == {"credited": 3, "present": 1, "removed": ["c.md"], "changed": ["b.md"]}


def test_reconcile_intact_is_clean():
    rec = inv.reconcile(["a.md#1", "b.md#2"], ["a.md#1", "b.md#2", "z.md#9"])
    assert rec["present"] == 2 and not rec["removed"] and not rec["changed"]


def test_credited_anchors_take_only_real_note_ids():
    col = Colony(label="x")
    col.tau = {f"cue:x{_SEP}a.md#1f": 1.0, f"a.md#1f{_SEP}sub/b.md#2e": 0.5, f"cue:x{_SEP}bash:pytest": 0.3,
               # the real-estate false positive: a PROCEDURAL verb node that merely mentions a .md file
               f"cue:x{_SEP}bash:BODY='GOVERNANCE.md": 0.4, f"cue:x{_SEP}Read:docs/README.md": 0.2}
    assert inv.credited_anchors(col) == ["a.md#1f", "sub/b.md#2e"]
    assert not inv.is_note_id("bash:BODY='GOVERNANCE.md") and inv.is_note_id("n01.md#02d93d4e7436")
    assert inv.is_note_id("n01.md#02d93d4e7436~1")                 # digest's duplicate-block suffix
    assert not inv.is_note_id("cue:x") and not inv.is_note_id("Read:docs/README.md")
    # every id the digest itself mints is a note id (the rule tracks the producer, not a guess)
    ids = [n.id for n in digest_document("sub/n.md", "alpha\n\nbeta\n\nalpha\n")]
    assert any("~" in i for i in ids) and all(inv.is_note_id(i) for i in ids)


# ----------------------------------------------------------------- notice modes
def test_notice_modes():
    gap = {"credited": 4, "present": 3, "removed": ["n02.md"], "changed": []}
    clean = {"credited": 4, "present": 4, "removed": [], "changed": []}
    assert inv.notice(gap, "off") is None
    assert inv.notice(clean, "gap") is None                             # silent when nothing is missing
    g = inv.notice(gap, "gap")
    assert "4 credited" in g and "Only 3 of 4" in g and "n02.md" in g and "removed from the vault" in g
    a = inv.notice(clean, "always")
    assert "4 credited" in a and "Only" not in a                        # semantics line, no gap claim
    assert inv.notice({"credited": 0, "present": 0, "removed": [], "changed": []}, "always") is None


def test_notice_is_budget_capped():
    many = {"credited": 400, "present": 0, "removed": [f"note_{i:04d}_with_a_long_name.md" for i in range(400)],
            "changed": []}
    t = inv.notice(many, "gap")
    assert len(t) <= inv.BUDGET_CHARS and "more" in t


# ----------------------------------------------------------------- end-to-end handle()
PROMPT = "add a parse helper following the project conventions"


def _vault(tmp: Path, notes: dict) -> Path:
    v = tmp / "vault"
    v.mkdir()
    for name, body in notes.items():
        (v / name).write_text(f"# Conventions — {name}\n\n{body}\n", encoding="utf-8")
    return v


def _credit(vault: Path, label: str) -> list:
    ids = []
    for p in sorted(vault.glob("*.md")):
        ids += [n.id for n in digest_document(p.name, p.read_text(encoding="utf-8"))]
    col = Colony.load(label)
    col.tau = {f"cue:{label}{_SEP}{i}": 1.0 for i in ids}
    col.save()
    return ids


@pytest.fixture
def organ(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv("EXOCORTEX_STATE_DIR", str(state))
    monkeypatch.setenv("EXOCORTEX_DECLARATIVE", "1")
    monkeypatch.setenv("EXOCORTEX_EMBED", "0")
    vault = _vault(tmp_path, {"n01.md": "Raise `SchemaError` on bad input.", "n02.md": "Register with `@tally`.",
                              "n03.md": "Export via `__all__`."})
    monkeypatch.setenv("EXOCORTEX_WIKI_VAULT", str(vault))
    from exocortex.cue_classifier import CueClassifier
    cc = CueClassifier.load()
    label = cc.classify(PROMPT)["label"]
    cc.save()
    _credit(vault, label)
    return {"state": state, "vault": vault, "label": label}


def _ctx(out):
    return (out or {}).get("hookSpecificOutput", {}).get("additionalContext", "")


def test_dormant_by_default(organ, monkeypatch):
    monkeypatch.delenv("EXOCORTEX_INVENTORY_NOTICE", raising=False)
    assert inv.handle({"prompt": PROMPT}) is None


def test_removed_note_is_reported(organ, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_INVENTORY_NOTICE", "gap")
    assert inv.handle({"prompt": PROMPT}) is None                       # intact → silent
    (organ["vault"] / "n02.md").unlink()
    t = _ctx(inv.handle({"prompt": PROMPT}))
    assert "Only 2 of 3" in t and "n02.md" in t and "removed" in t


def test_edited_note_is_reported_as_changed(organ, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_INVENTORY_NOTICE", "gap")
    (organ["vault"] / "n01.md").write_text("# Conventions — n01.md\n\nRaise `RecordError` on bad input.\n",
                                           encoding="utf-8")
    t = _ctx(inv.handle({"prompt": PROMPT}))
    assert "edited since they were credited" in t and "n01.md" in t


def test_always_mode_states_semantics_when_clean(organ, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_INVENTORY_NOTICE", "always")
    t = _ctx(inv.handle({"prompt": PROMPT}))
    assert "3 credited memory record" in t and "Only" not in t


def _tree_digest(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_never_writes_state_or_vault(organ, monkeypatch):
    monkeypatch.setenv("EXOCORTEX_INVENTORY_NOTICE", "gap")
    (organ["vault"] / "n03.md").unlink()                                # force a cache MISS path too
    before = (_tree_digest(organ["state"]), _tree_digest(organ["vault"]))
    assert _ctx(inv.handle({"prompt": PROMPT}))
    assert (_tree_digest(organ["state"]), _tree_digest(organ["vault"])) == before


def test_main_is_fail_open_and_silent(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", io.StringIO("{not json"))
    assert inv.main(["UserPromptSubmit"]) == 0
    assert capsys.readouterr().out == ""
    assert inv.main(["PreToolUse"]) == 0


def test_pinned_control_plane_untouched():
    """ADR-016: this organ is a sibling — the pinned files are byte-identical to HEAD."""
    root = Path(inv.__file__).resolve().parents[2]
    out = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "exocortex/hook.py", "exocortex/colony.py",
                          "exocortex/epistemic.py"], cwd=root)
    assert out.returncode == 0
