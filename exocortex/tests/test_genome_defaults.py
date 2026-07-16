"""The Genome has TWO sources of default truth, and they must not drift.

`exocortex/genome.py:DEFAULTS` is the code default; `exocortex/exocortex_config.json` is the SHIPPED
default file (`_locate()`'s last candidate — it wins whenever no project config is found, and it ships
inside the wheel). Its own header calls itself "every tuning knob in one place", i.e. a full mirror.

Two-of-anything drifts silently — the estate has paid for this lesson before (the rc2-vs-rag kernel-lock
hashes). It was paid again on 2026-07-16: `epistemic_classifier.mode` was changed to `lexical` in
genome.py while the shipped config still said `semantic`, and the config silently won — the code fix
looked applied and did nothing. These tests make that class of drift a failing test instead of a
mystery.
"""
from __future__ import annotations

import json
from pathlib import Path

from exocortex.genome import DEFAULTS, GENOME

_CONFIG = Path(__file__).resolve().parents[1] / "exocortex_config.json"


def _shipped() -> dict:
    return json.loads(_CONFIG.read_text(encoding="utf-8"))


def _drift(code: dict, shipped: dict, path: str = "") -> list[str]:
    """Every key the shipped config sets that disagrees with the code default. Comment keys (`_`-prefixed)
    and keys absent from the code defaults are ignored — `_deep_merge` ignores unknown keys too."""
    out = []
    for k, v in (shipped or {}).items():
        if k.startswith("_") or k not in code:
            continue
        if isinstance(v, dict) and isinstance(code[k], dict):
            out += _drift(code[k], v, f"{path}{k}.")
        elif code[k] != v:
            out.append(f"{path}{k}: genome.py={code[k]!r} != exocortex_config.json={v!r}")
    return out


def test_shipped_config_does_not_drift_from_the_code_defaults():
    drift = _drift(DEFAULTS, _shipped())
    assert not drift, (
        "exocortex/exocortex_config.json disagrees with genome.py DEFAULTS. The shipped config WINS "
        "when no project config is present, so a code-only edit silently does nothing:\n  "
        + "\n  ".join(drift)
    )


def test_semantic_classifier_is_opt_in_not_the_shipped_default():
    """`sentence-transformers` is an EXTRA, not a runtime dep — so a `semantic` default is a promise the
    shipped package cannot keep: `available()` is False and the hook silently falls back to lexical.
    Worse, it turns MiniLM on for anyone who happens to have torch installed for unrelated work, at a
    MEASURED ~10s per prompt vs 0.15s lexical (issue #4; not a cold-start artifact — each hook is a fresh
    process, so the model reloads every turn). Semantic stays available and gauge-backed; it is opt-in.

    This is NOT issue #4 option B (the cold->lexical/warm->semantic promotion rule), which stays
    gauge-gated on issue #11: this is a static declared default, not a dynamic switch.
    """
    assert DEFAULTS["epistemic_classifier"]["mode"] == "lexical"
    assert _shipped()["epistemic_classifier"]["mode"] == "lexical"


def test_the_embed_extra_is_declared_so_semantic_can_actually_be_opted_into():
    """A default nobody can reach is worse than an honest one. If semantic is opt-in, the opt-in has to
    exist: `pip install sentaince[embed]`."""
    pyproject = (Path(__file__).resolve().parents[2] / "pyproject.toml").read_text(encoding="utf-8")
    assert "embed = [" in pyproject and "sentence-transformers" in pyproject


def test_genome_resolves_to_the_lexical_default_at_import():
    """The end-to-end read: whatever _locate() picked, the hot path must not silently be semantic."""
    assert GENOME["epistemic_classifier"]["mode"] in ("lexical", "semantic")   # a real value, not a typo
    assert DEFAULTS["epistemic_classifier"]["model"] == "all-MiniLM-L6-v2"     # still offered when opted in


# ----------------------------------------------------------------------------- version: THREE sources
def test_all_three_version_sources_agree():
    """Version lives in THREE places and nothing enforced agreement — so it drifted:
    `oasf-record.json` sat at 0.1.3 while pyproject said 0.1.4 (found 2026-07-16). The publish routine
    lists only TWO files to bump and admits no test guards parity; pyproject and __init__ agreed by luck.

    This is the same class as the genome/config mirror: two-of-anything drifts silently. A mismatch here
    ships a wheel whose metadata and `import sentaince; sentaince.__version__` disagree — and PyPI is
    immutable, so the bump is the point of no return.
    """
    import json
    import re
    root = Path(__file__).resolve().parents[2]
    pyproject = re.search(r'^version = "([^"]+)"',
                          (root / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)
    dunder = re.search(r'__version__ = "([^"]+)"',
                       (root / "sentaince" / "__init__.py").read_text(encoding="utf-8")).group(1)
    oasf = json.loads((root / "oasf-record.json").read_text(encoding="utf-8"))["version"]
    assert pyproject == dunder == oasf, (
        f"version drift: pyproject.toml={pyproject} __init__.py={dunder} oasf-record.json={oasf}")


def test_changelog_ships_publicly():
    """CHANGELOG.md is the returning user's only diffable record, and it can vanish from the public tree
    via TWO independent silent paths — both hit while adding it (2026-07-16):

    1. The manifest's top-level allowlist is an explicit list, so a new ROOT file is simply not public;
       the gates pass either way.
    2. `build_public` scans **git-tracked files only** — so an untracked file is skipped even when
       `is_public()` says True. This is why (1) alone is not enough: the allowlist test passed while the
       file did not ship.

    Assert both, because either alone is a false green.
    """
    import subprocess
    from release.manifest import is_public
    root = Path(__file__).resolve().parents[2]
    assert is_public("CHANGELOG.md"), "CHANGELOG.md must be in PUBLIC_INCLUDE or it silently won't ship"
    assert (root / "CHANGELOG.md").is_file()
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "CHANGELOG.md"],
                             capture_output=True, cwd=root)
    assert tracked.returncode == 0, "CHANGELOG.md is untracked — build_public scans git-tracked files only"
