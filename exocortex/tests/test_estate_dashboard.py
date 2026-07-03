"""Estate dashboard ↔ exporter contract (P0.1 of the commercial arc). OUT of the 99-lock; run explicitly:

    python -m pytest exocortex/tests/test_estate_dashboard.py

The free multi-repo estate view must never reference a metric the exporter does not actually emit —
a dashboard querying a phantom series renders as an empty panel and silently lies. The test renders
the REAL exporter over a frozen two-repo fixture and asserts every `exocortex_*` name referenced by
any panel expression appears in the rendered exposition.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex.testbed.exporter import metrics as M                     # noqa: E402

DASHBOARD = _ROOT / "exocortex" / "testbed" / "compose" / "grafana" / "dashboards" / "estate.json"

_AUDIT_RECORDS = [
    # a PreToolUse the somatic failsafe blocked (the lethal_attempts source)
    {"session": "s1", "event": "PreToolUse", "tool": "Bash", "command": "rm -rf /",
     "somatic_permitted": False, "energy": 90.0, "tier": "SATED", "ts": "2026-07-01T00:00:00Z"},
    # consequences: one ok deposit (seg_len>0, wiki fields), one fail
    {"session": "s1", "event": "PostToolUse", "tool": "Bash", "command": "pytest -q",
     "outcome": "ok", "seg_len": 2, "wiki_injected": 3, "wiki_used": 1, "energy": 88.0,
     "tier": "SATED", "strategy_lock": 0, "ts": "2026-07-01T00:01:00Z"},
    {"session": "s1", "event": "PostToolUseFailure", "tool": "Bash", "command": "pytest -q bad",
     "outcome": "fail", "energy": 80.0, "tier": "STARVING", "strategy_lock": 1,
     "ts": "2026-07-01T00:02:00Z"},
]

_COLONY = {"label": "estate-fix", "tau": {"cue:x\tbash:pytest": 1.4, "bash:pytest\tEdit:test": 0.6},
           "deposits": 6, "consolidations": 2, "last_consolidated": 1780000000.0}


def _mkrepo(projects_root: Path, name: str) -> None:
    sd = projects_root / name / ".claude" / "exocortex"
    sd.mkdir(parents=True)
    (sd / "audit.jsonl").write_text(
        "\n".join(json.dumps(r) for r in _AUDIT_RECORDS) + "\n", encoding="utf-8")
    (sd / f"colony_{_COLONY['label']}.json").write_text(json.dumps(_COLONY), encoding="utf-8")


def _render_two_repo_fixture(tmp_path: Path) -> str:
    projects = tmp_path / "projects"
    _mkrepo(projects, "alpha")
    _mkrepo(projects, "beta")
    repos = M.discover_repos([projects], None, None)
    assert [r["name"] for r in repos] == ["alpha", "beta"]
    return M.render(repos)


def _dashboard_metric_names() -> set[str]:
    doc = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    names: set[str] = set()
    for panel in doc.get("panels", []):
        for target in panel.get("targets", []):
            names |= set(re.findall(r"\bexocortex_[a-z0-9_]+\b", target.get("expr", "")))
    assert names, "estate.json defines no Prometheus expressions — parse failure?"
    return names


def test_every_estate_expression_targets_an_emitted_metric(tmp_path):
    """The contract: each exocortex_* name in any estate panel expr exists in a real render."""
    text = _render_two_repo_fixture(tmp_path)
    emitted = set(re.findall(r"^(exocortex_[a-z0-9_]+?)(?:_bucket|_sum|_count)?\{",
                             text, flags=re.M))
    emitted |= set(re.findall(r"^# TYPE (exocortex_[a-z0-9_]+)", text, flags=re.M))
    missing = _dashboard_metric_names() - emitted
    assert not missing, f"estate.json queries metrics the exporter never emits: {sorted(missing)}"


def test_estate_fixture_exercises_the_table_columns(tmp_path):
    """The fixture is load-bearing: the series the estate table joins on are present per repo,
    with the values the frozen fixture dictates (1 lethal block, 1 deposit, 1 ok + 1 fail)."""
    text = _render_two_repo_fixture(tmp_path)
    for repo in ("alpha", "beta"):
        assert f'exocortex_deposits{{repo="{repo}"}} 1' in text
        assert f'exocortex_lethal_attempts{{repo="{repo}"}} 1' in text
        assert f'exocortex_consequences{{repo="{repo}",outcome="ok"}} 1' in text
        assert f'exocortex_consequences{{repo="{repo}",outcome="fail"}} 1' in text
        assert f'exocortex_colony_classes{{repo="{repo}"}} 1' in text
        assert f'exocortex_wiki_credit_rate{{repo="{repo}"}}' in text


def test_estate_dashboard_shape():
    """Structural invariants the provisioner relies on: unique uid, a version field (bump on edit —
    the file provisioner caches panels on an unchanged version), every data panel on the provisioned
    prometheus datasource, and the table's merge+organize transform pair."""
    doc = json.loads(DASHBOARD.read_text(encoding="utf-8"))
    assert doc["uid"] == "exocortex-estate"
    assert isinstance(doc.get("version"), int)
    assert doc["templating"]["list"] == [], "estate view is all-repos by design — no $repo filter"
    tables = [p for p in doc["panels"] if p.get("type") == "table"]
    assert len(tables) == 1
    transform_ids = [t["id"] for t in tables[0]["transformations"]]
    assert transform_ids == ["merge", "organize"]
    for panel in doc["panels"]:
        if panel.get("type") in ("stat", "table", "timeseries"):
            assert panel["datasource"] == {"type": "prometheus", "uid": "prometheus"}
