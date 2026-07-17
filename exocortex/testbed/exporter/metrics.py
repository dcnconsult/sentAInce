"""Exocortex metrics exporter — stdlib `http.server`, zero new Python deps.

Serves, for EVERY discovered repo, Prometheus text on ``/metrics`` computed read-only from that repo's
live artifacts (each series carries a ``repo="<name>"`` label):
  - ``<repo>/.claude/exocortex/audit.jsonl``   -> events, consequences, deposits, seg_len, energy, tier
  - ``<repo>/.claude/exocortex/colony_*.json`` -> per-class convergence (entropy), edges, deposits
  - the repo Genome (``<repo>/exocortex_config.json`` deep-merged over DEFAULTS) -> organ flags + knobs

Repo discovery (multi-repo, native or containerized):
  - ``--scan-root <dir>`` (repeatable) -> auto-scan ``<dir>/*/.claude/exocortex`` (the easy path)
  - ``--registry <file>`` -> a central JSON list ``[{"name","root"}]`` (or ``{"repos":[...]}``) — the
    OVERRIDE/extension path: name a repo OUTSIDE the scan roots, or pin a custom display name.
  - ``--state-dir <dir>`` -> single-repo back-compat (the original behaviour; used by ``--once``/CI).

Control plane (Phase 2 — tweak each repo from the browser):
  - ``GET  /``               -> the BODY page: one SVG organism per repo, organ regions colored by live
    vitals (thresholded raw numbers — the rule is printed beside every color; see docs/COLOR_DOCTRINE.md)
  - ``GET  /control``        -> the knobs page (one row per repo; tunable knobs as inputs)
  - ``GET  /api/repos``      -> JSON: each repo's current tunable values + the (read-only) frozen safety values
  - ``POST /api/config/<repo>`` body ``{"key","value"}`` -> patch ``<repo>/exocortex_config.json``
    The write surface is bounded by a server-side ALLOWLIST (``TUNABLE_SCHEMA``): only organ/thermodynamic
    knobs. The SAFETY genome — ``integrity.*``, ``somatic_gate.*``, ``audit_chain`` — is NEVER web-writable
    (a browser kill-switch on the immune system is a self-inflicted hole). Writing the config does NOT trip
    kernel-lock apoptosis: the go-live JSON is not in the frozen-DNA baseline.

Run:
  python -m exocortex.testbed.exporter.metrics --scan-root /projects     # multi-repo (containerized)
  python -m exocortex.testbed.exporter.metrics --state-dir <dir> --once  # single-repo smoke / CI
  python -m exocortex.testbed.exporter.metrics                           # single-repo default (<repo>/.claude/exocortex)
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote

_ROOT = Path(__file__).resolve().parents[3]   # exporter -> testbed -> exocortex -> repo root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.gauge.analyze import _entropy                        # noqa: E402  (canonical convergence maths)
from exocortex.genome import DEFAULTS, _deep_merge, _SOMATIC_ALIAS  # noqa: E402  (single source of truth)

SEG_LEN_BUCKETS = [1, 2, 3, 4, 5, 8, 16]                # +Inf appended implicitly
DEFAULT_STATE_DIR = _ROOT / ".claude" / "exocortex"
# The ESTATE FILE — the first-class, file-based multi-repo registry (docs/ESTATE.md). Used by default when
# present; --registry overrides. Contract: {"version": 1, "repos": [{"name","root","tags"?,"display"?}]}
# (a bare list is the accepted legacy form). Readers MUST ignore unknown keys — the file is a shared
# contract that downstream consumers may extend; the web editor preserves keys it doesn't know verbatim.
ESTATE_DEFAULT = Path.home() / ".exocortex" / "repos.json"
ESTATE_ENTRY_KEYS = ("name", "root", "tags", "display")   # the keys the web editor itself writes
CONSEQUENCE_EVENTS = ("PostToolUse", "PostToolUseFailure")
STATE_SUBPATH = (".claude", "exocortex")
CONFIG_FILENAME = "exocortex_config.json"

# The OFFLINE simulation gauges (eligibility/endocrine/bridge) produce a one-time SYNTHETIC verdict, not a
# live per-repo series — so their board entry is the shipped verdict (static; re-run the gauge to change it).
# 1 = prize real (build the organ) · 0 = park / null. Sources = results/*/RESULTS.md.
OFFLINE_GAUGE_VERDICTS = {
    "attribution": (1, "precision 1.0 @ mo=2 (results/attribution_layer2)"),
    "eligibility": (0, "dormant — γ-trace proven but no-op on short (median-2) segments"),
    "endocrine":   (0, "dormant — allostatic prune SAFE but modest over static decay"),
    "bridge":      (0, "dormant — mechanism sound, prize MARGINAL (shallow declarative tail)"),
}


# ----------------------------------------------------------------------------- control-plane allowlist
# The ONLY knobs writable from the browser. Anything not here is refused (403). The safety genome
# (integrity.*, somatic_gate.*, audit_chain) is intentionally absent — never web-writable.
TUNABLE_SCHEMA = [
    {"key": "declarative.mode",                  "kind": "enum",  "choices": ["off", "live"]},
    {"key": "declarative.explore_budget",        "kind": "int",   "min": 0,   "max": 50},
    {"key": "declarative.explore_block_cap",     "kind": "int",   "min": 0,   "max": 200},
    {"key": "eligibility_trace.mode",            "kind": "enum",  "choices": ["off", "trace"]},
    {"key": "eligibility_trace.gamma",           "kind": "float", "min": 0.0, "max": 1.0},
    {"key": "endocrine.mode",                    "kind": "enum",  "choices": ["off", "tier"]},
    {"key": "thermodynamics.prune_floor",        "kind": "float", "min": 0.0, "max": 1.0},
    {"key": "thermodynamics.max_edges_per_class","kind": "int",   "min": 1,   "max": 1024},
    {"key": "thermodynamics.decay",              "kind": "float", "min": 0.0, "max": 1.0},
]
# Surfaced read-only on the control page so the operator can SEE the safety posture (but not change it).
FROZEN_KEYS = ["integrity.mode", "somatic_gate.mode", "integrity.audit_chain"]


def _coerce(entry: dict, value):
    k = entry["kind"]
    if k == "enum":
        return value if value in entry["choices"] else None
    try:
        v = int(value) if k == "int" else float(value)
    except (TypeError, ValueError):
        return None
    return v if entry["min"] <= v <= entry["max"] else None


# ----------------------------------------------------------------------------- text format
class Prom:
    """Minimal Prometheus exposition-format builder. ``base_labels`` (e.g. {"repo": ...}) are merged into
    EVERY series; HELP/TYPE are emitted once per metric name across the whole document (so one shared Prom
    can serve many repos)."""

    def __init__(self, base_labels: dict | None = None) -> None:
        self.lines: list[str] = []
        self._declared: set[str] = set()
        self.base_labels: dict = dict(base_labels or {})

    def _decl(self, name: str, mtype: str, help_: str) -> None:
        if name not in self._declared:
            self.lines.append(f"# HELP {name} {help_}")
            self.lines.append(f"# TYPE {name} {mtype}")
            self._declared.add(name)

    def _labels(self, labels: dict | None = None) -> str:
        merged = {**self.base_labels, **(labels or {})}
        if not merged:
            return ""
        inner = ",".join(f'{k}="{_esc(str(v))}"' for k, v in merged.items())
        return "{" + inner + "}"

    def gauge(self, name: str, value, help_: str = "", labels: dict | None = None) -> None:
        self._decl(name, "gauge", help_ or name)
        self.lines.append(f"{name}{self._labels(labels)} {_num(value)}")

    def histogram(self, name: str, values: list, buckets: list, help_: str = "") -> None:
        self._decl(name, "histogram", help_ or name)
        total = len(values)
        ssum = sum(values)
        for b in buckets:
            c = sum(1 for v in values if v <= b)
            self.lines.append(f'{name}_bucket{self._labels({"le": b})} {c}')
        self.lines.append(f'{name}_bucket{self._labels({"le": "+Inf"})} {total}')
        self.lines.append(f"{name}_sum{self._labels()} {_num(ssum)}")
        self.lines.append(f"{name}_count{self._labels()} {total}")

    def render(self) -> str:
        return "\n".join(self.lines) + "\n"


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _num(v) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        return repr(v)
    return str(v)


# ----------------------------------------------------------------------------- genome (per-repo)
def load_genome_for(config_path: Path | None) -> dict:
    """The verified DEFAULTS deep-merged with a specific repo's config (if any). Mirrors
    ``genome.load_genome`` but takes an explicit path instead of the env/CLAUDE_PROJECT_DIR locator, so one
    process can load many repos. Fail-safe: any error -> DEFAULTS."""
    g = copy.deepcopy(DEFAULTS)
    if config_path is not None and Path(config_path).is_file():
        try:
            _deep_merge(g, json.loads(Path(config_path).read_text(encoding="utf-8")))
        except Exception:
            pass   # a malformed config must never break the exporter — fall back to defaults
    sm = str(g["somatic_gate"].get("mode", "observe")).lower()
    g["somatic_gate"]["mode"] = _SOMATIC_ALIAS.get(sm, sm)
    return g


def _get_nested(d: dict, dotted: str):
    cur = d
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


# ----------------------------------------------------------------------------- discovery
def _repo_record(root: Path, name: str | None = None) -> dict:
    root = Path(root).resolve()
    return {
        "name": name or root.name,
        "root": root,
        "state_dir": root.joinpath(*STATE_SUBPATH),
        "config_path": root / CONFIG_FILENAME,
    }


def discover_repos(scan_roots: list[Path], registry_path: Path | None,
                   state_dir: Path | None) -> list[dict]:
    """Resolve the repo set FRESH (called per request, so newly-deployed repos appear with no restart).
    Precedence: explicit --state-dir (single) > auto-scan > registry override (registry wins on name)."""
    repos: dict[str, dict] = {}

    if state_dir is not None:                                  # single-repo back-compat
        sd = Path(state_dir).resolve()
        try:
            root = sd.parents[1]                              # <root>/.claude/exocortex -> <root>
        except IndexError:
            root = sd
        rec = _repo_record(root)
        rec["state_dir"] = sd                                 # honour the explicit state dir verbatim
        repos[rec["name"]] = rec
        return list(repos.values())

    for sr in scan_roots or []:                               # auto-scan: a repo "counts" once deployed
        sr = Path(sr)
        if not sr.is_dir():
            continue
        for child in sorted(sr.iterdir()):
            if child.joinpath(*STATE_SUBPATH).is_dir():
                rec = _repo_record(child)
                repos.setdefault(rec["name"], rec)

    if registry_path is not None and Path(registry_path).is_file():   # central registry / estate file
        try:
            data = json.loads(Path(registry_path).read_text(encoding="utf-8"))
            entries = data.get("repos", []) if isinstance(data, dict) else data
            for e in entries:
                root = e.get("root")
                if not root:
                    continue
                rec = _repo_record(Path(root), e.get("name"))
                repos[rec["name"]] = rec                       # registry wins (custom name / outside scan)
        except Exception:
            pass

    return list(repos.values())


def discover_dormant(scan_roots: list[Path], deployed_names: set[str]) -> list[dict]:
    """Scan-root siblings that are git repos but have NO deployed organism — the onboarding
    surface. The body page renders them asleep with a COPY-PASTE deploy command; deploying stays
    a deliberate CLI act (the web plane never executes it)."""
    out = []
    for sr in scan_roots or []:
        sr = Path(sr)
        if not sr.is_dir():
            continue
        for child in sorted(sr.iterdir()):
            try:
                if (child.is_dir() and not child.name.startswith(".")
                        and (child / ".git").exists()
                        and not child.joinpath(*STATE_SUBPATH).is_dir()
                        and child.name not in deployed_names):
                    out.append({"name": child.name, "root": str(child.resolve()),
                                "deploy_cmd": f"python -m exocortex.deploy install {child.resolve()}"})
            except OSError:
                continue
    return out


# ----------------------------------------------------------------------------- readers
def read_jsonl(path: Path) -> list:
    out = []
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    return out


def read_attribution_gauge(state_dir: Path) -> dict:
    """A planted attribution-gauge result (``attribution_gauge.json``), if present — the per-repo OVERRIDE
    for a real-data run. Empty when absent (the global synthetic gauge then stands in)."""
    p = state_dir / "attribution_gauge.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


_ATTR_GAUGE_CACHE: dict | None = None


def computed_attribution_gauge() -> dict:
    """The offline attribution-precision gauge, computed IN-PROCESS (deterministic + synthetic, so it is
    always available without a planted file or a cron job). It is REPO-INDEPENDENT — emitted once, globally,
    NOT per-repo (stamping a synthetic 1.0 on a never-measured repo would be a false claim). Cached per
    process; a code/threshold change is picked up on the next restart. Fail-open -> {}."""
    global _ATTR_GAUGE_CACHE
    if _ATTR_GAUGE_CACHE is None:
        try:
            from exocortex.gauge.attribution_gauge import run as _attr_run
            _ATTR_GAUGE_CACHE = _attr_run()
        except Exception:
            _ATTR_GAUGE_CACHE = {}
    return _ATTR_GAUGE_CACHE or {}


def read_colonies(state_dir: Path) -> dict:
    """label -> {tau: dict, deposits: int, consolidations: int, last_consolidated: float}.
    Filenames are colony_<label>.json. ``consolidations`` is the circadian-sleep stamp (Q1 provenance:
    the one deposit-free τ writer, made attributable from the store)."""
    colonies = {}
    for p in sorted(state_dir.glob("colony_*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        label = d.get("label") or p.stem[len("colony_"):]
        tau = d.get("tau") if isinstance(d.get("tau"), dict) else {}
        colonies[label] = {"tau": tau, "deposits": d.get("deposits", 0),
                           "consolidations": int(d.get("consolidations", 0) or 0),
                           "last_consolidated": float(d.get("last_consolidated", 0.0) or 0.0)}
    return colonies


# ----------------------------------------------------------------------------- per-repo collection
def collect_repo(p: Prom, state_dir: Path, genome: dict) -> None:
    """Append one repo's series to a shared Prom (which already carries this repo's base label)."""
    p.gauge("exocortex_state_dir_present", 1 if state_dir.exists() else 0,
            "1 if the state directory exists.", {"path": str(state_dir)})

    audit = read_jsonl(state_dir / "audit.jsonl")
    p.gauge("exocortex_audit_records", len(audit), "Total audit records read.")

    # --- event / consequence / deposit counts -------------------------------------------
    events: dict = {}
    consequences = {"ok": 0, "fail": 0}
    seg_lens: list = []
    deposits = 0
    wiki_injected_total = 0
    wiki_used_total = 0
    lethal_attempts = 0
    strategy_lock_max = 0
    latest_energy = None
    latest_tier = ""
    per_session_energy: dict = {}
    for r in audit:
        ev = r.get("event") or "unknown"
        events[ev] = events.get(ev, 0) + 1
        if ev in CONSEQUENCE_EVENTS:
            oc = r.get("outcome") or ""
            if oc in consequences:
                consequences[oc] += 1
            sl = r.get("seg_len")
            if isinstance(sl, int) and sl > 0:
                seg_lens.append(sl)
                deposits += 1
            wiki_injected_total += int(r.get("wiki_injected", 0) or 0)
            wiki_used_total += int(r.get("wiki_used", 0) or 0)
        if ev == "PreToolUse" and r.get("somatic_permitted") is False:
            lethal_attempts += 1
        sl_lock = r.get("strategy_lock")
        if isinstance(sl_lock, int):
            strategy_lock_max = max(strategy_lock_max, sl_lock)
        e = r.get("energy")
        if isinstance(e, (int, float)):
            latest_energy = e
            sess = r.get("session") or "?"
            per_session_energy[sess] = e
        t = r.get("tier")
        if t:
            latest_tier = t

    for ev, c in sorted(events.items()):
        p.gauge("exocortex_events", c, "Audit records per event type.", {"event": ev})
    for oc, c in consequences.items():
        p.gauge("exocortex_consequences", c, "Bash consequence records by outcome.", {"outcome": oc})
    p.gauge("exocortex_deposits", deposits, "Successful colony deposits (consequence with seg_len>0).")
    p.gauge("exocortex_lethal_attempts", lethal_attempts,
            "PreToolUse records the somatic failsafe blocked (somatic_permitted=false).")
    p.gauge("exocortex_strategy_lock_max", strategy_lock_max,
            "Max consecutive-failure (strategy-lock) count seen.")
    if latest_energy is not None:
        p.gauge("exocortex_energy_latest", latest_energy, "Most recent session energy (0..e0).")
    for sess, e in per_session_energy.items():
        p.gauge("exocortex_energy", e, "Latest energy per session.", {"session": sess})
    for tier in ("SATED", "STARVING", "HYPOXIA"):
        p.gauge("exocortex_tier", 1 if latest_tier == tier else 0,
                "Most recent metabolic tier (1=current).", {"tier": tier})

    # --- seg_len histogram (the live 3D prize-sizer) ------------------------------------
    p.histogram("exocortex_seg_len", seg_lens, SEG_LEN_BUCKETS,
                "Deposit-window length (#edges) per successful Bash consequence. Compare the >=4 tail "
                "to the flagship baseline (median 2, 26% >=4) to size organ 3D's eligibility-trace prize.")

    # --- per-class colony convergence ---------------------------------------------------
    colonies = read_colonies(state_dir)
    p.gauge("exocortex_colony_classes", len(colonies), "Number of per-class colonies on disk.")
    for label, c in colonies.items():
        tau = c["tau"]
        p.gauge("exocortex_colony_entropy", _entropy(tau),
                "Pheromone entropy per class (lower = more converged/peaked).", {"class": label})
        p.gauge("exocortex_colony_edges", len(tau),
                "Edges retained per class (governed by max_edges_per_class CAP).", {"class": label})
        p.gauge("exocortex_colony_deposits", c["deposits"],
                "Lifetime successful deposits per class.", {"class": label})
        p.gauge("exocortex_colony_tau_max", max(tau.values()) if tau else 0.0,
                "Peak pheromone weight per class (convergence crest).", {"class": label})
        p.gauge("exocortex_colony_consolidations", c["consolidations"],
                "Circadian sleeps applied per class (PreCompact consolidation — the one deposit-free "
                "tau writer; each sleep decays all edges x0.9 and prunes the weakest).", {"class": label})
    p.gauge("exocortex_colony_last_consolidated_timestamp",
            max((c["last_consolidated"] for c in colonies.values()), default=0.0),
            "Epoch of the repo's most recent circadian sleep (0 = never consolidated).")

    # --- declarative wiki: live attribution telemetry -----------------------------------
    p.gauge("exocortex_wiki_injected_total", wiki_injected_total,
            "Wiki exons injected across exit-0 consequences (the attribution surface).")
    p.gauge("exocortex_wiki_used_total", wiki_used_total,
            "Wiki exons credited (content echoed in the action) across exit-0 consequences.")
    p.gauge("exocortex_wiki_credit_rate", (wiki_used_total / wiki_injected_total) if wiki_injected_total else 0.0,
            "Live used/injected ratio — how much injected declarative memory the consequence actually credits.")
    p.gauge("exocortex_config_declarative_mode", 1 if genome.get("declarative", {}).get("mode") == "live" else 0,
            "Declarative wiki organ mode (0=off/dormant, 1=live).")
    p.gauge("exocortex_config_attribution_min_overlap",
            genome.get("declarative", {}).get("attribution", {}).get("min_overlap",
                       DEFAULTS["declarative"]["attribution"]["min_overlap"]),
            "Attribution echo threshold (distinct salient tokens that must echo to credit a note).")

    # per-repo attribution gauge ONLY if a real-data result is planted for THIS repo (else the global
    # synthetic gauge, emitted once in render(), stands in — we never fabricate a per-repo precision).
    planted = read_attribution_gauge(state_dir)
    if planted:
        for row in planted.get("sweep", []):
            mo = {"min_overlap": str(row.get("min_overlap"))}
            p.gauge("exocortex_attribution_precision", row.get("precision", 0.0),
                    "Attribution precision by min_overlap.", mo)
            p.gauge("exocortex_attribution_recall", row.get("recall", 0.0),
                    "Attribution recall by min_overlap.", mo)
            p.gauge("exocortex_attribution_f05", row.get("f05", 0.0),
                    "Attribution F0.5 by min_overlap.", mo)

    # --- effective Genome (organ flags + thermodynamic knobs) ---------------------------
    therm = genome.get("thermodynamics", {})
    endo = genome.get("endocrine", {})
    elig = genome.get("eligibility_trace", {})
    som = genome.get("somatic_gate", {})
    p.gauge("exocortex_config_endocrine_mode", 1 if endo.get("mode") == "tier" else 0,
            "Organ 3A endocrine mode (0=off/static, 1=tier/allostatic).")
    p.gauge("exocortex_config_eligibility_trace_mode", 1 if elig.get("mode") == "trace" else 0,
            "Organ 3D eligibility-trace mode (0=off/uniform, 1=trace/gamma-credit).")
    p.gauge("exocortex_config_eligibility_gamma", elig.get("gamma", DEFAULTS["eligibility_trace"]["gamma"]),
            "Eligibility-trace gamma (credit ~ gamma^steps-before-exit-0).")
    p.gauge("exocortex_config_prune_floor", therm.get("prune_floor", DEFAULTS["thermodynamics"]["prune_floor"]),
            "Static prune floor (edges below are evicted).")
    p.gauge("exocortex_config_max_edges_per_class",
            therm.get("max_edges_per_class", DEFAULTS["thermodynamics"]["max_edges_per_class"]),
            "Per-class leanness CAP.")
    p.gauge("exocortex_config_decay", therm.get("decay", DEFAULTS["thermodynamics"]["decay"]),
            "Pheromone decay multiplier per deposit.")
    p.gauge("exocortex_config_somatic_mode", 1,
            "Active somatic-gate mode (label).", {"mode": som.get("mode", "observe")})


def _emit_global_attribution(p: Prom) -> None:
    """The repo-independent synthetic gauge — emitted ONCE, no repo label."""
    gauge = computed_attribution_gauge()
    if not gauge:
        return
    p.gauge("exocortex_attribution_gauge_source", 1,
            "1 if the in-process synthetic attribution gauge was served (global, repo-independent).")
    for row in gauge.get("sweep", []):
        mo = {"min_overlap": str(row.get("min_overlap"))}
        p.gauge("exocortex_attribution_precision", row.get("precision", 0.0),
                "Attribution precision by min_overlap (offline synthetic gauge; crown-jewel metric).", mo)
        p.gauge("exocortex_attribution_recall", row.get("recall", 0.0),
                "Attribution recall by min_overlap (offline synthetic gauge).", mo)
        p.gauge("exocortex_attribution_f05", row.get("f05", 0.0),
                "Attribution F0.5 (precision-weighted) by min_overlap (offline synthetic gauge).", mo)
    rec = gauge.get("recommended", {})
    if rec:
        p.gauge("exocortex_attribution_recommended_min_overlap", rec.get("min_overlap", 0),
                "Gauge-recommended min_overlap (precision-first).")


# ----------------------------------------------------------------------------- live gauges (wired in-process)
def _collect_gauges(repos: list[dict]) -> dict:
    """Run the LIVE, stdlib (numpy-free) gauges ONCE per scrape over the exporter's repo set → per-repo
    metrics + a verdict signal per candidate organ. Each gauge is wrapped fail-open (a broken gauge can't
    sink the scrape). The offline/simulation (numpy) gauges are NOT run here — their static verdicts live in
    ``OFFLINE_GAUGE_VERDICTS``. Returns ``{"per_repo": {repo: {metric: value}}, "signals": {gauge: (0|1, note)}}``."""
    state_dirs = [str(r["state_dir"]) for r in repos]
    audit_paths = [str(Path(r["state_dir"]) / "audit.jsonl") for r in repos]
    per_repo: dict = {r["name"]: {} for r in repos}
    signals: dict = {}

    def _rows(res, fn):
        for row in res.get("per_repo", []):
            if row.get("repo") in per_repo:
                fn(per_repo[row["repo"]], row)

    try:   # uncertainty (audit) — G1 abstain hand-off · F2 veto-sourced demotion
        from exocortex.gauge import uncertainty_gauge as ug
        r = ug.run(audit_paths=audit_paths)
        _rows(r, lambda d, row: d.update({"gauge_abstain_rate": row.get("abstain_rate") or 0.0,
                                          "gauge_veto_rate": row.get("veto_rate") or 0.0}))
        v = r.get("verdict", {})
        signals["G1_uncertainty"] = (1 if v.get("G1_handoff", {}).get("signal") else 0, "abstain hand-off (OOD)")
        signals["F2_veto_demotion"] = (1 if v.get("F2_veto_demotion", {}).get("signal") else 0, "veto-sourced demotion")
    except Exception:
        pass

    try:   # credit-hygiene (colony+audit) — W5 τ-noise reclaim · W4 failure recurrence
        from exocortex.gauge import credit_hygiene_gauge as ch
        r = ch.run(state_dirs=state_dirs)
        _rows(r, lambda d, row: d.update({
            "gauge_credit_reclaim_frac": (row.get("credit") or {}).get("reclaim_frac_mass") or 0.0,
            "gauge_failure_plasticity": (row.get("failure") or {}).get("plasticity_rate") or 0.0}))
        v = r.get("verdict", {})
        signals["W5_credit_filter"] = (1 if v.get("W5_credit_filter", {}).get("signal") else 0, "credit-pollution filter")
        signals["W4_failure_ledger"] = (1 if v.get("W4_failure_ledger", {}).get("signal") else 0, "failure-recurrence ledger")
    except Exception:
        pass

    try:   # D'Ambrogio VoI (colony+audit) — Q1 dep↔τ ρ · Q2 β4 directed-exploration (DEI)
        from exocortex.gauge import dambrogio_gauge as dg
        r = dg.run(state_dirs=state_dirs)
        _rows(r, lambda d, row: d.update({"gauge_dep_tau_rho": row.get("dep_tau_spearman") or 0.0,
                                          "gauge_dei_seen": (row.get("dei") or {}).get("dei_seen") or 0.0}))
        signals["D4_directed_exploration"] = (1 if r.get("verdict", {}).get("beta4_signal") else 0,
                                              "β4 exploration bonus")
    except Exception:
        pass

    try:   # non-stationarity (colony+audit) — F3 provenance coverage + excess within-class drift
        from exocortex.gauge import nonstationarity_gauge as ns
        r = ns.run(state_dirs=state_dirs)
        _rows(r, lambda d, row: d.update({
            "gauge_model_coverage": (row.get("provenance") or {}).get("model_coverage") or 0.0,
            "gauge_drift_excess": (row.get("stationarity_by_class") or {}).get("mean_excess_drift") or 0.0}))
        v = r.get("verdict", {}).get("F3_nonstationarity", {})
        signals["F3_nonstationarity"] = (1 if v.get("signal") else 0, "non-stationarity drift")
    except Exception:
        pass

    return {"per_repo": per_repo, "signals": signals}


def _emit_gauge_board(p: Prom, gauges: dict) -> None:
    """Global verdict board — 1=prize real (build) / 0=park-null. Live gauges from this scrape; offline
    simulation gauges from their shipped static verdicts (they don't change per scrape)."""
    for g, (sig, note) in sorted(gauges.get("signals", {}).items()):
        p.gauge("exocortex_gauge_signal", sig,
                "Gauge verdict — 1=prize real (build the organ) / 0=park-null.",
                {"gauge": g, "kind": "live", "note": note})
    for g, (sig, note) in sorted(OFFLINE_GAUGE_VERDICTS.items()):
        p.gauge("exocortex_gauge_signal", sig,
                "Gauge verdict — 1=prize real / 0=park-null (offline simulation gauge; static shipped verdict).",
                {"gauge": g, "kind": "offline", "note": note})


# ----------------------------------------------------------------------------- render
def render(repos: list[dict]) -> str:
    """One Prometheus document covering every repo. Global series (exporter health, synthetic gauge) carry
    no repo label; everything else is labelled ``repo``."""
    p = Prom()
    p.gauge("exocortex_exporter_up", 1, "1 if the exporter served this scrape.")
    p.gauge("exocortex_repos_discovered", len(repos), "Number of repos the exporter is reporting on.")
    _emit_global_attribution(p)
    gauges = _collect_gauges(repos)                  # live stdlib gauges, once over the whole repo set
    _emit_gauge_board(p, gauges)                     # global verdict board (live signals + offline static)
    for r in repos:
        p.base_labels = {"repo": r["name"]}
        genome = r.get("genome")
        if not isinstance(genome, dict):
            genome = load_genome_for(r.get("config_path"))
        try:
            collect_repo(p, Path(r["state_dir"]), genome)
        except Exception as e:                       # one bad repo must not sink the whole scrape
            p.gauge("exocortex_repo_error", 1, "1 if this repo failed to collect.", {"error": str(e)[:120]})
        for mname, val in (gauges["per_repo"].get(r["name"]) or {}).items():   # per-repo live gauge metrics
            p.gauge("exocortex_" + mname, val, "Live gauge metric (per-repo, computed in-process this scrape).")
        p.base_labels = {}
    return p.render()


def collect(state_dir: Path, genome: dict) -> str:
    """Back-compat single-repo render (used by --once / tests)."""
    sd = Path(state_dir).resolve()
    try:
        name = sd.parents[1].name
    except IndexError:
        name = sd.name
    return render([{"name": name, "state_dir": sd, "genome": genome}])


# ----------------------------------------------------------------------------- control plane
def apply_config(root: Path, key, value) -> tuple[int, dict]:
    """Patch ``<root>/exocortex_config.json`` with a single ALLOWLISTED knob. Refuses anything outside
    TUNABLE_SCHEMA (the safety genome is never web-writable). Preserves all other keys verbatim."""
    if not isinstance(key, str):
        return 400, {"error": "missing 'key'"}
    entry = next((e for e in TUNABLE_SCHEMA if e["key"] == key), None)
    if entry is None:
        return 403, {"error": f"'{key}' is not a tunable knob — the safety genome "
                              f"(integrity/somatic) is never web-writable"}
    coerced = _coerce(entry, value)
    if coerced is None:
        return 400, {"error": f"invalid value for {key}: {value!r}"}
    cfg = Path(root) / CONFIG_FILENAME
    data: dict = {}
    if cfg.is_file():
        try:
            loaded = json.loads(cfg.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}
    section, leaf = key.split(".", 1)
    if not isinstance(data.get(section), dict):
        data[section] = {}
    data[section][leaf] = coerced
    try:
        cfg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        return 500, {"error": f"write failed: {e}"}
    return 200, {"ok": True, "key": key, "value": coerced, "path": str(cfg)}


def estate_view(registry_path: Path | None) -> dict:
    """The estate file as JSON for the control page. ``path: null`` when no estate file is in
    play (scan-root-only setups). Unknown top-level and entry keys pass through untouched."""
    if registry_path is None or not Path(registry_path).is_file():
        return {"path": str(registry_path) if registry_path else None, "version": 1, "repos": []}
    try:
        data = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    except Exception as e:
        return {"path": str(registry_path), "error": f"unreadable: {e}", "version": 1, "repos": []}
    if isinstance(data, list):                                 # legacy bare-list form
        return {"path": str(registry_path), "version": 1, "repos": data}
    return {"path": str(registry_path), "version": data.get("version", 1),
            "repos": data.get("repos", []),
            **{k: v for k, v in data.items() if k not in ("version", "repos")}}


def estate_apply(registry_path: Path | None, action, entry) -> tuple[int, dict]:
    """Bounded estate-file edit: ``add`` (name+root, optional tags/display) or ``remove`` (by
    name). The FILE stays the source of truth — this is just an editor for it. Round-trip
    safety: top-level keys and entry keys this editor doesn't know are preserved verbatim
    (the estate file is a shared contract downstream consumers may extend)."""
    if registry_path is None:
        return 400, {"error": "no estate file in play — start the exporter with --registry "
                              f"(default {ESTATE_DEFAULT})"}
    if action not in ("add", "remove") or not isinstance(entry, dict):
        return 400, {"error": "body must be {\"action\": \"add\"|\"remove\", \"entry\": {...}}"}
    rp = Path(registry_path)
    data: dict = {"version": 1, "repos": []}
    if rp.is_file():
        try:
            loaded = json.loads(rp.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                data["repos"] = loaded
            elif isinstance(loaded, dict):
                data = loaded
                data.setdefault("version", 1)
                if not isinstance(data.get("repos"), list):
                    data["repos"] = []
        except Exception as e:
            return 409, {"error": f"estate file unreadable — refusing to overwrite: {e}"}
    if action == "add":
        root = entry.get("root")
        if not root or not isinstance(root, str):
            return 400, {"error": "add requires a non-empty 'root'"}
        new = {k: entry[k] for k in ESTATE_ENTRY_KEYS if k in entry and entry[k] is not None}
        new.setdefault("name", Path(root).name)
        data["repos"] = [e for e in data["repos"]
                         if not (isinstance(e, dict) and e.get("name") == new["name"])] + [new]
    else:
        name = entry.get("name")
        if not name:
            return 400, {"error": "remove requires 'name'"}
        before = len(data["repos"])
        data["repos"] = [e for e in data["repos"]
                         if not (isinstance(e, dict) and e.get("name") == name)]
        if len(data["repos"]) == before:
            return 404, {"error": f"no estate entry named '{name}'"}
    try:
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    except Exception as e:
        return 500, {"error": f"write failed: {e}"}
    return 200, {"ok": True, "path": str(rp), "repos": data["repos"]}


def _orientation_view(r: dict, log: dict) -> dict:
    """The ADR-019 orientation slice for one repo: DECLARED capsule fields + the READER-computed
    credibility grade (never stored, never web-writable — capsule.json is deliberately absent from
    TUNABLE_SCHEMA). Fail-open to {} — orientation must never break the metrics path."""
    try:
        from datetime import date

        from exocortex import orient as _orient
        v = _orient.orient(r["name"], r.get("root"), log, date.today())
        d = v["declared"]
        return {
            "canonical_status": d.get("canonical_status"), "tier": d.get("tier"),
            "maturity": d.get("maturity"), "last_reviewed": str(d.get("last_reviewed") or ""),
            "links": [{"edge": e, "target": t} for _, e, t in d.get("links", [])],
            "grade": v["grade"], "grade_reasons": v["reasons"],
            "capsule_present": bool(v["probe"].get("capsule_present")),
        }
    except Exception:
        return {}


def repos_api(repos: list[dict]) -> dict:
    """The control page's data: each repo's current tunable values + read-only frozen safety values +
    the ADR-019 orientation capsule view (declared claim, reader-computed grade). Estate-level
    ``link_flags`` surface one-sided cross-repo link declarations (the graph disagreeing with itself)."""
    try:
        from exocortex import orient as _orient
        log = _orient.load_log()
        link_flags = _orient.symmetry_flags(_orient.estate_links(repos, log))
    except Exception:
        log, link_flags = {}, []
    out = []
    for r in repos:
        genome = load_genome_for(r.get("config_path"))
        out.append({
            "name": r["name"],
            "root": str(r["root"]),
            "has_config": Path(r["config_path"]).is_file(),
            "tunable": {e["key"]: _get_nested(genome, e["key"]) for e in TUNABLE_SCHEMA},
            "frozen": {k: _get_nested(genome, k) for k in FROZEN_KEYS},
            "orientation": _orientation_view(r, log),
        })
    return {"schema": TUNABLE_SCHEMA, "frozen_keys": FROZEN_KEYS, "repos": out,
            "link_flags": link_flags}


def repo_vitals(state_dir: Path, genome: dict) -> dict:
    """The structured vitals digest the Tuner consumes (the same numbers the metrics expose, as JSON —
    so the client forwards a clean object instead of parsing Prometheus text)."""
    audit = read_jsonl(state_dir / "audit.jsonl")
    cons = [r for r in audit if r.get("event") in CONSEQUENCE_EVENTS]
    seglens = sorted(r["seg_len"] for r in cons if isinstance(r.get("seg_len"), int) and r["seg_len"] > 0)
    n = len(seglens)
    ge4 = sum(1 for s in seglens if s >= 4)
    colonies = read_colonies(state_dir)
    therm = genome.get("thermodynamics", {})
    cap = therm.get("max_edges_per_class", DEFAULTS["thermodynamics"]["max_edges_per_class"])
    at_cap = sum(1 for c in colonies.values() if len(c["tau"]) >= cap)
    inj = sum(int(r.get("wiki_injected", 0) or 0) for r in cons)
    used = sum(int(r.get("wiki_used", 0) or 0) for r in cons)
    ok = sum(1 for r in cons if r.get("outcome") == "ok")
    fail = sum(1 for r in cons if r.get("outcome") == "fail")
    # tier occupancy + somatic refusals (the policy/2 vitals — same audit walk, no new reads)
    tiers = {"SATED": 0, "STARVING": 0, "HYPOXIA": 0}
    latest_tier = ""
    for r in audit:
        t = r.get("tier")
        if t in tiers:
            tiers[t] += 1
            latest_tier = t
    tier_total = sum(tiers.values())
    lethal = sum(1 for r in audit
                 if r.get("event") == "PreToolUse" and r.get("somatic_permitted") is False)
    # declarative tail: per injected segment (consequence with wiki_injected>0), how many notes credited
    seg_used = sorted(int(r.get("wiki_used", 0) or 0) for r in cons
                      if int(r.get("wiki_injected", 0) or 0) > 0)
    n_inj_segs = len(seg_used)
    ge2 = sum(1 for u in seg_used if u >= 2)
    return {
        "deposits": n,
        "consequences": {"ok": ok, "fail": fail},
        "fail_rate": round(fail / (ok + fail), 3) if (ok + fail) else 0.0,
        "lethal_attempts": lethal,
        "tier": {"now": latest_tier,
                 "occupancy": {t: round(c / tier_total, 3) if tier_total else 0.0
                               for t, c in tiers.items()}},
        "seg_len_median": seglens[n // 2] if n else 0,
        "seg_len_ge4": ge4,
        "seg_len_ge4_pct": round(ge4 / n, 3) if n else 0.0,
        "colony": {"classes": len(colonies), "at_cap": at_cap, "max_edges_per_class": cap},
        "config": {
            "eligibility_trace_mode": 1 if genome.get("eligibility_trace", {}).get("mode") == "trace" else 0,
            "declarative_mode": 1 if genome.get("declarative", {}).get("mode") == "live" else 0,
            "endocrine_mode": 1 if genome.get("endocrine", {}).get("mode") == "tier" else 0,
            "explore_budget": genome.get("declarative", {}).get("explore_budget",
                              DEFAULTS["declarative"].get("explore_budget", 0)),
            "max_edges_per_class": cap,
            "prune_floor": therm.get("prune_floor", DEFAULTS["thermodynamics"]["prune_floor"]),
        },
        "wiki": {"injected": inj, "used": used, "credit_rate": round(used / inj, 3) if inj else 0.0,
                 "segments_injected": n_inj_segs,
                 "segments_ge2_pct": round(ge2 / n_inj_segs, 3) if n_inj_segs else 0.0,
                 "notes_credited_median": seg_used[n_inj_segs // 2] if n_inj_segs else 0},
    }


def vitals_api(repos: list[dict]) -> dict:
    """Per-repo structured vitals (the Tuner's input). Vitals only — never source.
    ``schema_version`` starts the additive-only contract: existing keys never change meaning or vanish;
    consumers must ignore keys they don't know."""
    out = []
    for r in repos:
        try:
            v = repo_vitals(Path(r["state_dir"]), load_genome_for(r.get("config_path")))
            v["repo"] = r["name"]
            out.append(v)
        except Exception as e:
            out.append({"repo": r["name"], "error": str(e)[:120]})
    return {"schema_version": 1, "repos": out}


# The BODY page — the story skin as a picture. One SVG organism per repo; each organ region is colored by
# a THRESHOLDED RAW VITAL and the rule is printed beside the color (list row + hover title) — color never
# carries meaning alone (docs/COLOR_DOCTRINE.md). Status palette (fixed, colorblind-mitigated by the always-
# visible state word): good #0ca30c · attention #fab219 · strained #ec835a · dormant #4a5064 · cold=outline.
BODY_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<title>SentAInce — the organism</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
 :root{--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--dormant:#4a5064;
       --bg:#0f1117;--card:#161a23;--line:#232733;--ink:#d7dae0;--ink2:#8b93a7;--ink3:#aab2c5}
 body{font:14px/1.5 system-ui,Segoe UI,sans-serif;margin:0;background:var(--bg);color:var(--ink)}
 header{padding:16px 24px;border-bottom:1px solid var(--line)}
 h1{font-size:18px;margin:0}a{color:#7aa2f7}.muted{color:var(--ink2)}
 .law{font-size:12.5px;color:var(--ink3);margin-top:4px}.law b{color:#cfe0ff}
 .estate{display:flex;gap:26px;padding:12px 24px;border-bottom:1px solid var(--line);flex-wrap:wrap}
 .stat .n{font-size:22px;font-weight:600}.stat .l{font-size:11.5px;color:var(--ink2)}
 .legend{display:flex;gap:16px;align-items:center;padding:10px 24px;font-size:12px;color:var(--ink3);flex-wrap:wrap}
 .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:-1px}
 .dot.cold{background:none;border:1.5px dashed var(--ink2)}
 .wrap{padding:16px 24px;display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;max-width:1400px}
 .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;display:flex;gap:14px}
 .card h2{font-size:15px;margin:0 0 6px}
 .organs{flex:1;min-width:0}
 .orow{font-size:12px;padding:3px 0}
 .orow .nm{color:var(--ink3);margin-right:6px}.orow .st{font-weight:600}
 .orow .tx{display:block;color:var(--ink2);margin-left:17px;font-size:11.5px;line-height:1.35}
 .foot{font-size:11.5px;color:var(--ink2);margin-top:6px;border-top:1px dashed #2c3242;padding-top:5px}
 svg .region{stroke:#2c3242;stroke-width:1.5}
 svg .base{fill:#1c222e;stroke:#2c3242;stroke-width:1.5}
 svg .cold{fill:none;stroke:var(--ink2);stroke-dasharray:3 3}
 footer{padding:14px 24px;border-top:1px solid var(--line);font-size:11.5px;color:var(--ink2);line-height:1.7}
</style></head><body>
<header><h1>🧬 SentAInce — the organism</h1>
 <div class=law>A <b>SyncQutrit Research Group</b> product · part of the <b>FreqOS</b> portfolio ·
  <a href="/control">tune the organs</a> · <a href="/metrics">/metrics</a> · <a href="/api/vitals">vitals JSON</a></div>
 <div class=law>The one law: a memory is earned by a closed <b>action → success (exit 0)</b> chain.
  Every color below is a <b>thresholded raw number</b> with its rule printed beside it — never a judgment.</div>
</header>
<div class=estate id=estate></div>
<div class=legend id=legend></div>
<div class=wrap id=repos><p class=muted>loading…</p></div>
<footer><b style="color:var(--ink3)">Honest by construction:</b> organs whose own gauge rated the prize modest or
 null ship <b>dormant (gray)</b> — the lab reports both directions. A cold organ (dashed outline) has simply
 not seen data yet; nothing here fakes green. Full rules: docs/COLOR_DOCTRINE.md in the repo.</footer>
<script>
const STATE={good:{c:'var(--good)',w:'healthy'},warn:{c:'var(--warn)',w:'attention'},
             serious:{c:'var(--serious)',w:'strained'},dormant:{c:'var(--dormant)',w:'dormant'},
             cold:{c:null,w:'no data yet'}};
// organ rules — each returns {state, text}; text IS the rule applied to the raw number (the honesty channel).
function organs(v){
 const cfg=v.config||{},tier=(v.tier||{}).now||'',col=v.colony||{},wiki=v.wiki||{};
 const lethal=v.lethal_attempts|0,dep=v.deposits|0,cls=col.classes|0,cap=col.at_cap|0;
 const inj=wiki.injected|0,used=wiki.used|0;
 const cons=v.consequences||{};const activity=(cons.ok|0)+(cons.fail|0)+lethal;
 return [
  {k:'immune',icon:'🛡️',nm:'Immune',
   ...(activity===0?{state:'cold',text:'no actions recorded yet — nothing to defend'}
     :lethal===0?{state:'good',text:'0 lethal attempts — the reflex stayed quiet'}
                :{state:'warn',text:lethal+' lethal attempt'+(lethal>1?'s':'')+' refused — read the audit'})},
  {k:'stamina',icon:'🫀',nm:'Stamina',
   ...(tier==='SATED'?{state:'good',text:'tier SATED'}
     :tier==='STARVING'?{state:'warn',text:'tier STARVING — doing less'}
     :tier==='HYPOXIA'?{state:'serious',text:'tier HYPOXIA — only what is safe'}
     :{state:'cold',text:'no session energy recorded yet'})},
  {k:'muscle',icon:'💪',nm:'Muscle memory',
   ...(dep>0?{state:'good',text:dep+' habit'+(dep>1?'s':'')+' earned (exit 0 only)'}
           :{state:'cold',text:'no habits yet — earning starts on your first exit 0'})},
  {k:'sleep',icon:'😴',nm:'Sleep',
   ...(cls===0?{state:'cold',text:'no habit-classes yet'}
     :cap>0?{state:'warn',text:cap+' class'+(cap>1?'es':'')+' at the edge cap — next sleep prunes'}
           :{state:'good',text:cls+' classes · none at the edge cap'})},
  {k:'notebook',icon:'📖',nm:'Notebook',
   ...(!cfg.declarative_mode?{state:'dormant',text:'off — notes neither injected nor credited'}
     :used>0?{state:'good',text:'credit rate '+((wiki.credit_rate||0)*100).toFixed(1)+'% ('+used+'/'+inj+' credited)'}
     :inj>0?{state:'cold',text:inj+' injected, none credited yet'}
           :{state:'cold',text:'live — nothing injected yet'})},
  {k:'credit',icon:'🎯',nm:'Credit timing',
   ...(cfg.eligibility_trace_mode?{state:'good',text:'trace mode — credit concentrates near success'}
                                :{state:'dormant',text:'off — its own gauge rated the prize modest'})},
  {k:'hormones',icon:'🧪',nm:'Stress hormones',
   ...(cfg.endocrine_mode?{state:'good',text:'tier mode — leaner sleep under stress'}
                        :{state:'dormant',text:'off — its own gauge rated the prize modest'})},
 ];}
function fill(el,o){const s=STATE[o.state];
 el.setAttribute('class','region'+(o.state==='cold'?' cold':''));
 if(s.c)el.setAttribute('style','fill:'+s.c);
 const t=document.createElementNS('http://www.w3.org/2000/svg','title');
 t.textContent=o.icon+' '+o.nm+' — '+s.w+' · '+o.text;el.appendChild(t);}
function bodySvg(os){
 const NS='http://www.w3.org/2000/svg';const svg=document.createElementNS(NS,'svg');
 svg.setAttribute('viewBox','0 0 120 200');svg.setAttribute('width','118');svg.setAttribute('height','196');
 const mk=(tag,attrs)=>{const e=document.createElementNS(NS,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,v);svg.appendChild(e);return e;};
 const by={};os.forEach(o=>by[o.k]=o);
 mk('rect',{x:38,y:50,width:44,height:64,rx:10,class:'base'});                       // torso (neutral)
 fill(mk('circle',{cx:60,cy:27,r:18}),by.sleep);                                    // head → sleep
 fill(mk('rect',{x:20,y:54,width:14,height:52,rx:7}),by.muscle);                    // arms → muscle memory
 fill(mk('rect',{x:86,y:54,width:14,height:52,rx:7}),Object.assign({},by.muscle,{icon:'',nm:'Muscle memory'}));
 fill(mk('path',{d:'M68 58 l9 4 v8 q0 8 -9 12 q-9 -4 -9 -12 v-8 z'}),by.immune);    // chest shield → immune
 fill(mk('circle',{cx:51,cy:67,r:7}),by.stamina);                                   // heart → stamina
 fill(mk('circle',{cx:60,cy:99,r:5}),by.hormones);                                  // gland → stress hormones
 fill(mk('rect',{x:42,y:116,width:15,height:58,rx:7}),by.credit);                   // legs → credit timing
 fill(mk('rect',{x:63,y:116,width:15,height:58,rx:7}),Object.assign({},by.credit,{icon:'',nm:'Credit timing'}));
 fill(mk('rect',{x:88,y:106,width:13,height:10,rx:2}),by.notebook);                 // book in hand → notebook
 return svg;}
async function load(){
 const d=await(await fetch('/api/vitals')).json();
 const host=document.getElementById('repos');host.innerHTML='';
 const L=document.getElementById('legend');
 L.innerHTML=Object.entries(STATE).map(([k,s])=>'<span><span class="dot'+(s.c?'':' cold')+'"'+
   (s.c?' style="background:'+s.c+'"':'')+'></span>'+s.w+'</span>').join('')+
   '<span class=muted>· hover any organ for its rule</span>';
 let dep=0,lethal=0,n=0;
 (d.repos||[]).forEach(v=>{
  if(v.error){const c=document.createElement('div');c.className='card';
   c.innerHTML='<div class=organs><h2>'+v.repo+'</h2><p class=muted>collect error: '+v.error+'</p></div>';
   host.appendChild(c);return;}
  n++;dep+=v.deposits|0;lethal+=v.lethal_attempts|0;
  const os=organs(v);const c=document.createElement('div');c.className='card';
  c.appendChild(bodySvg(os));
  const o=document.createElement('div');o.className='organs';
  o.innerHTML='<h2>'+v.repo+'</h2>';
  os.forEach(r=>{const s=STATE[r.state];const row=document.createElement('div');row.className='orow';
   row.innerHTML='<span class="dot'+(s.c?'':' cold')+'"'+(s.c?' style="background:'+s.c+'"':'')+'></span>'+
    '<span class=nm>'+r.icon+' '+r.nm+'</span><span class=st'+(s.c?' style="color:'+s.c+'"':'')+'>'+s.w+
    '</span><span class=tx>'+r.text+'</span>';
   o.appendChild(row);});
  const f=document.createElement('div');f.className='foot';
  f.textContent='raw: '+(v.deposits|0)+' deposits · fail rate '+(v.fail_rate??0)+' · seg_len median '+
   (v.seg_len_median|0)+' · '+((v.colony||{}).classes|0)+' classes';
  o.appendChild(f);c.appendChild(o);host.appendChild(c);});
 (d.dormant||[]).forEach(r=>{                       // undeployed sibling git repos — asleep, copy-paste onboarding
  const c=document.createElement('div');c.className='card';c.style.opacity='0.75';
  const os=Object.fromEntries(['immune','stamina','muscle','sleep','notebook','credit','hormones']
    .map(k=>[k,{k,icon:'',nm:k,state:'dormant',text:'no organism deployed'}]));
  c.appendChild(bodySvg(Object.values(os)));
  const o=document.createElement('div');o.className='organs';
  o.innerHTML='<h2>😴 '+r.name+' <span class=muted style="font-weight:normal;font-size:12px">not deployed</span></h2>'+
   '<p class=muted style="font-size:12px;margin:4px 0 8px">a git repo with no organism yet — deploying is a '+
   'deliberate CLI act (never done from this page):</p>';
  const cmd=document.createElement('code');cmd.textContent=r.deploy_cmd;
  cmd.style.cssText='display:block;font-size:11px;background:#0f1117;border:1px solid #232733;border-radius:6px;padding:6px 8px;word-break:break-all';
  o.appendChild(cmd);
  const b=document.createElement('button');b.textContent='copy deploy command';
  b.style.cssText='margin-top:7px;background:#2a3550;color:#cfe0ff;border:1px solid #3a4a6e;border-radius:6px;padding:4px 10px;cursor:pointer';
  b.onclick=async()=>{try{await navigator.clipboard.writeText(r.deploy_cmd);b.textContent='copied ✓';}
   catch(e){b.textContent='select + copy above';}setTimeout(()=>b.textContent='copy deploy command',2000);};
  o.appendChild(b);c.appendChild(o);host.appendChild(c);});
 if(!n&&!(d.repos||[]).length&&!(d.dormant||[]).length)
  host.innerHTML='<p class=muted>No repos discovered yet — deploy the organism into a '+
  'repo (<code>python -m exocortex.deploy install &lt;path&gt;</code>) and it appears here on the next refresh.</p>';
 document.getElementById('estate').innerHTML=
  '<span class=stat><div class=n>'+n+'</div><div class=l>organism'+(n===1?'':'s')+'</div></span>'+
  '<span class=stat><div class=n>'+dep+'</div><div class=l>habits earned (exit 0 only)</div></span>'+
  '<span class=stat><div class=n>'+lethal+'</div><div class=l>lethal attempts refused</div></span>';}
load();setInterval(load,15000);
</script></body></html>"""


CONTROL_HTML = """<!doctype html><html lang=en><head><meta charset=utf-8>
<title>SentAInce — the organism's control plane</title><meta name=viewport content="width=device-width,initial-scale=1">
<style>
 body{font:14px/1.5 system-ui,Segoe UI,sans-serif;margin:0;background:#0f1117;color:#d7dae0}
 header{padding:16px 24px;border-bottom:1px solid #232733}
 h1{font-size:18px;margin:0}a{color:#7aa2f7}.muted{color:#8b93a7}
 .law{font-size:12.5px;color:#aab2c5;margin-top:4px}.law b{color:#cfe0ff}
 .wrap{padding:16px 24px;max-width:1100px}
 .repo{background:#161a23;border:1px solid #232733;border-radius:10px;margin:14px 0;padding:14px 18px}
 .repo h2{font-size:15px;margin:0 0 2px}.repo .root{font-size:12px;color:#8b93a7;margin-bottom:10px;word-break:break-all}
 .organ{margin:12px 0 4px;font-size:13px;color:#cfe0ff;border-bottom:1px dotted #2c3242;padding-bottom:3px}
 .organ .sub{color:#8b93a7;font-weight:normal;font-size:12px}
 .knobs{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:10px}
 .knob{display:flex;flex-direction:column;gap:3px;background:#0f1117;border:1px solid #232733;border-radius:8px;padding:8px 10px}
 .knob label{font-size:12px;color:#aab2c5}.knob .hint{font-size:11px;color:#8b93a7;margin-bottom:2px}
 .row{display:flex;gap:6px}.row select,.row input{flex:1;background:#0f1117;color:#d7dae0;border:1px solid #2c3242;border-radius:6px;padding:5px 7px}
 button{background:#2a3550;color:#cfe0ff;border:1px solid #3a4a6e;border-radius:6px;padding:5px 12px;cursor:pointer}
 button:hover{background:#34436b}
 .frozen{margin-top:12px;padding-top:10px;border-top:1px dashed #2c3242;font-size:12px;color:#8b93a7}
 .frozen b{color:#e0af68}.lock{color:#e0af68}
 .ok{color:#9ece6a}.err{color:#f7768e}.note{font-size:12px;margin-left:8px}
 footer{padding:14px 24px;border-top:1px solid #232733;font-size:11.5px;color:#8b93a7;line-height:1.7}
 footer b{color:#aab2c5}
</style></head><body>
<header><h1>🧬 SentAInce — the organism's control plane</h1>
 <div class=law>A <b>SyncQutrit Research Group</b> product · part of the <b>FreqOS</b> portfolio ·
  <a href="/">← the organism</a> · tune each repo's organs · <a href="/metrics">/metrics</a> ·
  read the story in Grafana :3000</div>
 <div class=law>The one law: a memory is earned by a closed <b>action → success (exit 0)</b> chain — never by
  being read or repeated. You tune the <b>autopilot</b>; the <b>brakes</b> (🛡️ immune system) are never here.</div>
</header>
<div class=wrap>
 <p class=muted>The <span class=lock>🛡️ immune system</span> (<span class=lock>integrity</span>,
  <span class=lock>somatic_gate</span>, the audit chain) is shown 🔒 read-only and is <b>never web-writable</b> —
  safety is never for sale. Changes write <code>exocortex_config.json</code> and take effect on the repo's next
  action.</p>
 <div id=repos>loading…</div>
 <div id=estate class=repo style="display:none">
  <h2>🗺️ The estate file <span class=muted id=estatePath style="font-weight:normal;font-size:12px"></span></h2>
  <p class=muted style="font-size:12px">The file-based multi-repo registry (docs/ESTATE.md). The <b>file</b> is
   the source of truth — this form just edits it. Repos inside a scan-root need no entry; entries name repos
   outside it (or pin a display name).</p>
  <div id=estateRows></div>
  <div class=row style="max-width:640px;margin-top:8px">
   <input id=estName placeholder="name (optional — defaults to folder)">
   <input id=estRoot placeholder="repo root path" style="flex:2">
   <button id=estAdd>Add</button><span class=note id=estMsg></span>
  </div>
 </div>
</div>
<footer>
 <b>Honest by construction:</b> survival 1.000 / 0 lethal slips over N=100 live episodes (a labeled demonstration
 — the real proof is the 99-test lock) · consequence-sourcing discriminates clutter 0% vs 24% ·
 note-attribution precision 1.00 at overlap≥2 (controlled tasks). Organs whose own gauge rated the prize modest
 or null (eligibility, endocrine, uncertainty) ship OFF — the lab reports both directions.
</footer>
<script>
// each tunable knob mapped to its organ + a plain-language line (the anatomy skin).
const ORGANS={
 'declarative':{t:'📖 The notebook',s:'notes earn trust only when using them led to success'},
 'thermodynamics':{t:'💪 Muscle memory & 😴 sleep',s:'how habits form, fade, and get pruned'},
 'eligibility_trace':{t:'🎯 Credit timing',s:'which step of a winning streak gets the credit (dormant)'},
 'endocrine':{t:'🧪 Stress hormones',s:'under stress, sleep gets leaner (dormant)'},
};
const HINTS={
 'declarative.mode':'The notebook: off, or live (notes injected + credited on success).',
 'declarative.explore_budget':'How many un-earned notes to trial per session (breaks the cold-start deadlock). A trialled note delivers whole — never partially.',
 'declarative.explore_block_cap':'Byte bound on exploration: total blocks a splice may inject across trialled notes.',
 'thermodynamics.decay':'How fast unused habits fade — applied on every success AND every sleep (0.9 = −10%).',
 'thermodynamics.prune_floor':'The forgetting threshold: habits weaker than this are dropped.',
 'thermodynamics.max_edges_per_class':'Leanness cap: the strongest N routes a habit-class keeps after sleep.',
 'eligibility_trace.mode':'off = credit the whole streak evenly; trace = credit the step nearest success.',
 'eligibility_trace.gamma':'How sharply credit concentrates on the final steps (trace mode).',
 'endocrine.mode':'off = fixed sleep; tier = leaner sleep under metabolic stress.',
};
const KIND_INPUT=(e,v)=>{
 if(e.kind==='enum'){const s=document.createElement('select');
  e.choices.forEach(c=>{const o=document.createElement('option');o.value=o.textContent=c;if(String(c)===String(v))o.selected=true;s.appendChild(o);});return s;}
 const i=document.createElement('input');i.type='number';if('min'in e)i.min=e.min;if('max'in e)i.max=e.max;
 if(e.kind==='float')i.step='0.01';i.value=(v===null||v===undefined)?'':v;return i;};
function knobEl(e,r){
 const k=document.createElement('div');k.className='knob';
 const lab=document.createElement('label');lab.textContent=e.key;k.appendChild(lab);
 if(HINTS[e.key]){const h=document.createElement('div');h.className='hint';h.textContent=HINTS[e.key];k.appendChild(h);}
 const row=document.createElement('div');row.className='row';
 const inp=KIND_INPUT(e,r.tunable[e.key]);row.appendChild(inp);
 const b=document.createElement('button');b.textContent='Set';
 const msg=document.createElement('span');msg.className='note';
 b.onclick=async()=>{msg.textContent='…';msg.className='note';
  const res=await fetch('/api/config/'+encodeURIComponent(r.name),{method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({key:e.key,value:inp.value})});
  const j=await res.json();
  if(res.ok){msg.textContent='✓ '+j.value;msg.className='note ok';}
  else{msg.textContent='✗ '+(j.error||res.status);msg.className='note err';}};
 row.appendChild(b);k.appendChild(row);k.appendChild(msg);return k;}
async function load(){
 const d=await (await fetch('/api/repos')).json();
 const host=document.getElementById('repos');host.innerHTML='';
 if(!d.repos.length){host.innerHTML='<p class=err>No repos discovered.</p>';return;}
 d.repos.forEach(r=>{
  const box=document.createElement('div');box.className='repo';
  box.innerHTML=`<h2>${r.name} ${r.has_config?'':'<span class=muted>(no config yet)</span>'}</h2><div class=root>${r.root}</div>`;
  // group the schema by organ (dotted-key prefix), in a stable organ order
  const groups={};d.schema.forEach(e=>{const g=e.key.split('.')[0];(groups[g]=groups[g]||[]).push(e);});
  Object.keys(ORGANS).concat(Object.keys(groups).filter(g=>!(g in ORGANS))).forEach(g=>{
   if(!groups[g])return;
   const meta=ORGANS[g]||{t:g,s:''};
   const h=document.createElement('div');h.className='organ';
   h.innerHTML=`${meta.t} <span class=sub>· ${meta.s||g}</span>`;box.appendChild(h);
   const knobs=document.createElement('div');knobs.className='knobs';
   groups[g].forEach(e=>knobs.appendChild(knobEl(e,r)));box.appendChild(knobs);
  });
  const fr=document.createElement('div');fr.className='frozen';
  fr.innerHTML='🔒 🛡️ immune system (read-only, never web-writable): '+d.frozen_keys.map(k=>`<b>${k}</b>=${r.frozen[k]}`).join(' · ');
  box.appendChild(fr);host.appendChild(box);
 });}
async function estPost(body,msg){msg.textContent='…';msg.className='note';
 const res=await fetch('/api/estate',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
 const j=await res.json();
 if(res.ok){msg.textContent='✓ written';msg.className='note ok';loadEstate();}
 else{msg.textContent='✗ '+(j.error||res.status);msg.className='note err';}}
async function loadEstate(){
 const d=await (await fetch('/api/estate')).json();
 const box=document.getElementById('estate');if(!d.path){box.style.display='none';return;}
 box.style.display='';document.getElementById('estatePath').textContent='· '+d.path+(d.error?' — '+d.error:'');
 const rows=document.getElementById('estateRows');rows.innerHTML='';
 (d.repos||[]).forEach(e=>{const r=document.createElement('div');r.className='row';
  r.style.cssText='max-width:640px;margin:3px 0;align-items:center';
  r.innerHTML='<span style="flex:1;font-size:12.5px"><b>'+(e.display||e.name||'?')+'</b> <span class=muted>'+(e.root||'')+'</span></span>';
  const b=document.createElement('button');b.textContent='Remove';
  const msg=document.getElementById('estMsg');
  b.onclick=()=>estPost({action:'remove',entry:{name:e.name}},msg);
  r.appendChild(b);rows.appendChild(r);});
 if(!(d.repos||[]).length)rows.innerHTML='<p class=muted style="font-size:12px">no entries yet</p>';
 document.getElementById('estAdd').onclick=()=>{
  const name=document.getElementById('estName').value.trim(),root=document.getElementById('estRoot').value.trim();
  estPost({action:'add',entry:name?{name,root}:{root}},document.getElementById('estMsg'));};}
load();loadEstate();
</script></body></html>"""


# ----------------------------------------------------------------------------- server
_LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "[::1]", "::1")


def _origin_is_local(origin: str) -> bool:
    """True iff an Origin header value points at a loopback host (any port). An ABSENT Origin is handled
    by the caller (non-browser clients don't send one — allowed); a present non-loopback Origin is a
    cross-site browser request — the CSRF shape the control plane must refuse."""
    try:
        host = origin.split("//", 1)[1].split("/", 1)[0].rsplit(":", 1)[0].lower()
        return host in _LOOPBACK_HOSTS or origin.split("//", 1)[1].split("/", 1)[0].lower().startswith("[::1]")
    except Exception:
        return False


def _make_handler(resolve_repos, read_only: bool = False, token: str = "", resolve_dormant=None,
                  registry_path: Path | None = None):
    """``read_only`` → every POST is refused (the free-tier / pure-monitoring posture — the write surface
    is what the paid client drives). ``token`` → POST requires ``X-Exocortex-Token`` (or a Bearer). Both
    default OFF so the local dev posture is unchanged; compose/docs choose the hardened posture."""
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            path = self.path.split("?")[0].rstrip("/")
            if path in ("/healthz", "/health"):
                return self._send(200, "ok\n", "text/plain")
            if path in ("", "/index.html", "/body"):
                return self._send(200, BODY_HTML, "text/html; charset=utf-8")
            if path == "/control":
                return self._send(200, CONTROL_HTML, "text/html; charset=utf-8")
            if path == "/metrics":
                try:
                    return self._send(200, render(resolve_repos()), "text/plain; version=0.0.4")
                except Exception as e:
                    return self._send(500, f"# exporter error: {e}\n", "text/plain")
            if path == "/api/repos":
                try:
                    return self._json(200, repos_api(resolve_repos()))
                except Exception as e:
                    return self._json(500, {"error": str(e)})
            if path == "/api/estate":
                try:
                    return self._json(200, estate_view(registry_path))
                except Exception as e:
                    return self._json(500, {"error": str(e)})
            if path == "/api/vitals" or path.startswith("/api/vitals/"):
                try:
                    repos = resolve_repos()
                    if path.startswith("/api/vitals/"):
                        name = unquote(path[len("/api/vitals/"):])
                        repos = [r for r in repos if r["name"] == name]
                        if not repos:
                            return self._json(404, {"error": f"unknown repo '{name}'"})
                        return self._json(200, vitals_api(repos))
                    payload = vitals_api(repos)
                    if resolve_dormant is not None:      # additive key — consumers ignore unknowns
                        try:
                            payload["dormant"] = resolve_dormant({r["name"] for r in repos})
                        except Exception:
                            payload["dormant"] = []
                    return self._json(200, payload)
                except Exception as e:
                    return self._json(500, {"error": str(e)})
            self._send(404, "not found\n", "text/plain")

        def do_POST(self):  # noqa: N802
            # ---- write-surface guards (ENHANCEMENTS §C; ADR-012 seam hardening) ----
            if read_only:
                return self._json(403, {"error": "exporter is running --read-only (monitoring posture); "
                                                 "config writes are disabled"})
            # CSRF: a browser form/fetch can silently POST text/plain cross-site WITHOUT a CORS preflight;
            # requiring application/json forces the preflight (which fails — we send no CORS headers), and
            # a present non-loopback Origin is refused outright. Non-browser clients (no Origin) pass.
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if ctype != "application/json":
                return self._json(415, {"error": "Content-Type must be application/json"})
            origin = self.headers.get("Origin") or ""
            if origin and not _origin_is_local(origin):
                return self._json(403, {"error": "cross-origin config writes are refused"})
            if token:
                import hmac as _hmac
                supplied = (self.headers.get("X-Exocortex-Token")
                            or (self.headers.get("Authorization") or "").removeprefix("Bearer ").strip())
                if not (supplied and _hmac.compare_digest(supplied, token)):
                    return self._json(403, {"error": "missing/invalid control token"})
            path = self.path.split("?")[0].rstrip("/")
            if path == "/api/estate":
                try:
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    body = json.loads(self.rfile.read(n) or b"{}")
                except Exception:
                    return self._json(400, {"error": "bad JSON body"})
                code, payload = estate_apply(registry_path, body.get("action"),
                                             body.get("entry") or {})
                return self._json(code, payload)
            if path.startswith("/api/config/"):
                name = unquote(path[len("/api/config/"):])
                try:
                    n = int(self.headers.get("Content-Length", 0) or 0)
                    body = json.loads(self.rfile.read(n) or b"{}")
                except Exception:
                    return self._json(400, {"error": "bad JSON body"})
                repos = {r["name"]: r for r in resolve_repos()}
                if name not in repos:                 # name must resolve to a discovered repo (no traversal)
                    return self._json(404, {"error": f"unknown repo '{name}'"})
                code, payload = apply_config(repos[name]["root"], body.get("key"), body.get("value"))
                return self._json(code, payload)
            self._json(404, {"error": "not found"})

        def _json(self, code: int, obj: dict):
            self._send(code, json.dumps(obj), "application/json")

        def _send(self, code: int, body: str, ctype: str):
            data = body.encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):  # quiet
            pass

    return Handler


def main() -> int:
    ap = argparse.ArgumentParser(description="Exocortex Prometheus exporter + control plane (multi-repo)")
    ap.add_argument("--scan-root", action="append", default=[],
                    help="auto-scan <dir>/*/.claude/exocortex (repeatable; the easy multi-repo path)")
    ap.add_argument("--registry", default=None,
                    help="central registry JSON [{name,root}] (override/extend the scan)")
    ap.add_argument("--state-dir", default=None,
                    help="single-repo back-compat: dir holding audit.jsonl + colony_*.json")
    ap.add_argument("--port", type=int, default=9109)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--config", default=None, help="single-repo: path to that repo's exocortex_config.json")
    ap.add_argument("--once", action="store_true", help="print metrics once to stdout and exit")
    ap.add_argument("--read-only", action="store_true",
                    help="pure-monitoring posture: every POST (config write) is refused with 403 — the "
                         "free-tier default for any non-loopback exposure")
    ap.add_argument("--token", default=os.environ.get("EXOCORTEX_CONTROL_TOKEN", ""),
                    help="when set, POST requires X-Exocortex-Token (or Bearer) — the paid client sends it; "
                         "the browser control page then becomes view-only (env: EXOCORTEX_CONTROL_TOKEN)")
    args = ap.parse_args()

    scan_roots = [Path(s) for s in args.scan_root]
    # the estate file is first-class: used by default when present (docs/ESTATE.md); --registry overrides
    registry = Path(args.registry) if args.registry else (
        ESTATE_DEFAULT if (not args.state_dir and ESTATE_DEFAULT.is_file()) else None)

    # default (no scan-root/registry/state-dir given): single-repo over the default state dir, back-compat.
    default_state = None
    if not scan_roots and not registry and not args.state_dir:
        default_state = DEFAULT_STATE_DIR
        if args.config:
            os.environ["EXOCORTEX_CONFIG"] = args.config

    def resolve_repos() -> list[dict]:
        sd = Path(args.state_dir) if args.state_dir else default_state
        repos = discover_repos(scan_roots, registry, sd)
        if args.config and len(repos) == 1:           # honour an explicit single-repo config path
            repos[0]["config_path"] = Path(args.config)
        return repos

    if args.once:
        sys.stdout.write(render(resolve_repos()))
        return 0

    httpd = ThreadingHTTPServer(
        (args.host, args.port),
        _make_handler(resolve_repos, read_only=args.read_only, token=args.token,
                      resolve_dormant=lambda deployed: discover_dormant(scan_roots, deployed),
                      registry_path=registry))
    found = ", ".join(r["name"] for r in resolve_repos()) or "(none yet)"
    posture = "read-only" if args.read_only else ("token-gated" if args.token else "open(loopback-trust)")
    print(f"[exporter] http://{args.host}:{args.port}  body=/  control=/control  metrics=/metrics  "
          f"writes={posture}  repos: {found}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
