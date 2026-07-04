"""The community/commercial boundary AS DATA (ADR-011) — the single source of truth for what is public.

An **allowlist** (safer than a denylist: a new dir is private-by-default until explicitly added), plus the
commercial holdbacks, the never-public set, and the token/secret denylists the pre-push gate fails closed
on. Editing THIS file is how the boundary moves — nothing else decides what ships.

Paths are repo-relative, posix, prefix-matched: a trailing ``/`` = a directory subtree; otherwise an exact
file. A file is PUBLIC iff it is under some ``PUBLIC_INCLUDE`` prefix AND under no ``COMMERCIAL_EXCLUDE`` /
``NEVER_PUBLIC`` prefix AND is not always-skipped build cruft.
"""
from __future__ import annotations

import re

# ---- the open community core (Apache-2.0) — the whole local BODY -------------------------------------
PUBLIC_INCLUDE = [
    # the immune kernel + the C1–C7 evidence lock (never paywalled; defensively patented, freely granted)
    "sentaince/", "vendor/kernel/", "experiments/", "tests/",
    # the exocortex host: hooks, colony, audit, MCP memory server, deploy, integrity, gauges, testbed
    "exocortex/",                    # minus exocortex/tuner/ (commercial) — see COMMERCIAL_EXCLUDE
    # the read-only Cerebral Substrate slices (resurrection Governor + intent journal) — the free teaser
    "cerebral/",
    # proofs, demos, container stacks, gauge verdicts
    "battle/", "body/", "demo/", "docker/", "results/",
    # the whole-organism docs (some need scrubbing — the denylist gate flags them)
    "docs/",
    # the release toolchain itself is fine to publish (transparency of the boundary)
    "release/",
    # CI / release automation (ships so the public repo builds + publishes itself)
    ".github/",
    # top-level project files
    "README.md", "LICENSE", "NOTICE", "CONTRIBUTING.md", "pyproject.toml", "pyrightconfig.json", ".gitignore",
]

# ---- the paid tier — held OUT of the public tree even though under a public parent -------------------
# The Tuner is a clean leaf (nothing in the free body imports it): the deterministic policy table (the
# honest moat), the emulator, the client, and the client↔Tuner protocol. A monetized method lives here,
# outside Apache-2.0's patent grant. Future actuator (S3) / Consolidator daemon / cross-repo Alliance
# analytics land here too as they are built.
COMMERCIAL_EXCLUDE = [
    "exocortex/tuner/",
    # the reflect gauge's verdict validates a paid-tier method (the reflection lenses) and names it;
    # held with the leaf it gauges until the PI's IP review clears reflection for disclosure.
    "results/reflection_gauge_v1/",
]

# ---- never public under any circumstance ------------------------------------------------------------
NEVER_PUBLIC = [
    "patent/",                       # the provisional claim drafts — code IS disclosure; these never ship
    "docs/INVESTOR_SUMMARY.md",      # investor materials
    "exocortex_config.json",         # local activation — may point at a private vault
    "release/denylist_private.py",   # the identifying denylist tokens — publishing the list = the leak
    # raw resurrection-gauge labels: real private-vault intent text + maintainer name (summary RESULTS.md ships)
    "results/resurrection_gauge_v1/labels_completed.json",
    "results/resurrection_gauge_v1/labels_template.json",
    # ---- forward-looking IP: these describe UNFILED novel methods (whitespace/frontier candidates,
    # the FI-ledger, the model-independence arc) that the docs THEMSELVES flag "filing opportunities
    # before any disclosure" / "keep local until counsel clears". Code IS disclosure — and so is prose.
    # Held whole for v1 (fail-safe); the gate_no_ip_disclosure gate is the belt-and-braces backstop.
    "docs/ENHANCEMENTS.md",          # §F/§G whitespace + §H/§I frontier carry explicit **IP:** method pointers
    "docs/ROADMAP.md",               # §3 Frontier discloses the FI-ledger method (patent-before-disclosure)
    "exocortex/docs/INVESTOR_OVERVIEW.md",   # investor/strategy material (analogue of docs/INVESTOR_SUMMARY.md)
    "exocortex/docs/NEXT_PHASE_PLAN.md",     # the "grand arc" forward-design home (referenced by §F/§G)
    # the public-variant SOURCES: they publish UNDER the canonical name via PUBLIC_VARIANTS, never as ".public.md"
    "docs/ROADMAP.public.md",
    "docs/ENHANCEMENTS.public.md",
    "vendor/kernel/freqos/__init__.public.py",
    # ---- the vendored kernel: the organism imports only `freqos.tam` + `freqos.phase_router` (and their
    # capacity deps). The deep FreqOS research library ships for ZERO product benefit and is the least-
    # disclosed IP (several modules cite patent claims by number in-source). Held from the public tree; the
    # community build carries the ~22-file wired closure. The full kernel stays in this private monorepo.
    # The greedy `freqos/__init__.py` (which eager-imports the whole library) publishes as the empty
    # `__init__.public.py` variant so `import freqos.tam` does not drag the research modules in.
    "vendor/kernel/freqos/__init__.py",
] + [
    "vendor/kernel/freqos/%s.py" % m for m in (
        "active_veto", "age_tag", "calibration", "comma_ratchet", "continual_learning", "ctawe",
        "ctawe_gate", "ctawe_ssr", "democracy_diag", "discrete_continuous", "energy_veto",
        "episodic_memory", "epistemic_gate", "fast_order", "frame_packing", "governor_adapter",
        "holonomy_nav", "kinetic_z3", "layer_residual", "order_capacity", "order_ladder",
        "order_packing", "order_palimpsest", "organs", "p_order_capacity", "predictive_transfer",
        "quantum", "recall_observables", "ssr_rag", "stigmergic_sparsity_gate", "topology_audit",
        "whiten_capacity",
    )
] + [
    "vendor/kernel/core_physics/benchmark.py",   # wall-clock bench — not wired
    "vendor/kernel/core_physics/v039_audit.py",  # regression guard — not wired
]

# ---- public variants: a private doc is held whole, but a COMMUNITY-SAFE variant ships under its canonical
# name (IP-method sections removed / generalized to purely conceptual — counsel's preference). The build
# copies the variant SOURCE's content to the canonical published path; the gates scan the variant content.
# Map: canonical published path -> the ".public.md" source whose content to publish.
PUBLIC_VARIANTS = {
    "docs/ROADMAP.md": "docs/ROADMAP.public.md",
    "docs/ENHANCEMENTS.md": "docs/ENHANCEMENTS.public.md",
    # the community kernel gets an empty freqos package init (no eager research-module imports)
    "vendor/kernel/freqos/__init__.py": "vendor/kernel/freqos/__init__.public.py",
}


def variant_source(rel: str) -> str:
    """The file to READ for a published path: the ``.public.md`` variant if one is mapped, else ``rel``
    itself. Everything that materializes or scans the public tree resolves content through this."""
    return PUBLIC_VARIANTS.get(rel, rel)

# ---- always-skip build cruft (independent of the boundary) ------------------------------------------
SKIP_SUFFIXES = (".pyc", ".pyo", ".log")
SKIP_DIR_PARTS = frozenset({".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
                            "node_modules", ".venv", "venv", ".idea", ".vscode"})

# ---- tokens that must NOT appear anywhere in the public tree (fail-closed) ---------------------------
# False positives are ACCEPTABLE (they force a human look); a false negative is the real danger. Only the
# GENERIC dev-path tokens live here — the identifying tokens (crucible names, patent ids, maintainer PII)
# live in ``release/denylist_private.py`` (NEVER_PUBLIC: publishing that list would publish the secrets).
# Forks: add your own private tokens there; the gate extends automatically when the module is importable.
DENYLIST_TOKENS = [
    "C:\\Users", "C:/Users", "/c/Users/",                              # absolute dev paths (any machine)
]
try:                                                                    # private monorepo: extend; public tree: absent
    from release.denylist_private import PRIVATE_TOKENS as _PRIVATE_TOKENS
    DENYLIST_TOKENS = DENYLIST_TOKENS + _PRIVATE_TOKENS
except ImportError:
    pass

# ---- secret patterns (a light net; layer gitleaks/trufflehog for depth) -----------------------------
SECRET_PATTERNS = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                               # AWS access key id
    re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}"),                       # Anthropic key
    re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),                           # OpenAI-style key
    re.compile(r"\bghp_[A-Za-z0-9]{36}\b"),                           # GitHub PAT
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd|token)\b\s*[=:]\s*['\"][A-Za-z0-9_\-]{16,}['\"]"),
]

# ---- the hard patent gate: no push until the provisionals are filed (code IS disclosure) ------------
PATENT_GATE_FLAG = "release/PROVISIONALS_FILED"    # a committed marker file whose presence clears the gate


def _under(rel: str, prefixes) -> bool:
    """True if ``rel`` (posix) equals or is under any prefix (trailing ``/`` = subtree; else exact file)."""
    for pre in prefixes:
        if pre.endswith("/"):
            if rel == pre.rstrip("/") or rel.startswith(pre):
                return True
        elif rel == pre:
            return True
    return False


def is_skipped(rel: str) -> bool:
    parts = set(rel.split("/"))
    return bool(parts & SKIP_DIR_PARTS) or rel.endswith(SKIP_SUFFIXES)


def is_public(rel: str) -> bool:
    """The one predicate: does this repo-relative file ship to the public community repo?"""
    rel = rel.replace("\\", "/")
    if is_skipped(rel):
        return False
    if _under(rel, NEVER_PUBLIC) or _under(rel, COMMERCIAL_EXCLUDE):
        return False
    return _under(rel, PUBLIC_INCLUDE)
