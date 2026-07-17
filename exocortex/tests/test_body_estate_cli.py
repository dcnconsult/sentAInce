"""Body-page arc contracts (2026-07-17 slice): the vitals schema_version, the estate-file
round-trip rules (docs/ESTATE.md), dormant-repo discovery, and the CLI's lazy-plugin proof.

OUT of the 99-lock; run explicitly:

    python -m pytest exocortex/tests/test_body_estate_cli.py
"""
from __future__ import annotations

import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from exocortex import cli                                                # noqa: E402
from exocortex.testbed.exporter import metrics as M                      # noqa: E402


# ----------------------------------------------------------------------------- helpers
def _deployed(tmp_path: Path, name: str) -> Path:
    root = tmp_path / name
    (root / ".claude" / "exocortex").mkdir(parents=True)
    return root


def _serve(repos, **handler_kw):
    handler = M._make_handler(lambda: repos, **handler_kw)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _rec(root: Path) -> dict:
    return {"name": root.name, "root": root,
            "state_dir": root / ".claude" / "exocortex",
            "config_path": root / "exocortex_config.json"}


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# ----------------------------------------------------------------------------- vitals contract
def test_vitals_api_carries_schema_version(tmp_path):
    """The additive-only contract starts at schema_version 1 — consumers key forward-compat off it."""
    out = M.vitals_api([_rec(_deployed(tmp_path, "r1"))])
    assert out["schema_version"] == 1
    assert out["repos"][0]["repo"] == "r1"


def test_cold_repo_vitals_are_all_zero_never_fabricated(tmp_path):
    """The cold-body negative control at API level: an empty state dir yields zeros, so the body
    page renders outlines — nothing fakes green."""
    v = M.repo_vitals(_deployed(tmp_path, "cold") / ".claude" / "exocortex", {})
    assert v["deposits"] == 0 and v["lethal_attempts"] == 0
    assert v["consequences"] == {"ok": 0, "fail": 0} and v["tier"]["now"] == ""


def test_body_page_is_home_and_control_moved(tmp_path):
    httpd, base = _serve([_rec(_deployed(tmp_path, "r1"))])
    try:
        with urllib.request.urlopen(base + "/", timeout=5) as r:
            assert "SentAInce — the organism<" in r.read().decode("utf-8")
        with urllib.request.urlopen(base + "/control", timeout=5) as r:
            assert "control plane" in r.read().decode("utf-8")
    finally:
        httpd.shutdown()


# ----------------------------------------------------------------------------- estate contract
def test_estate_roundtrip_preserves_unknown_keys(tmp_path):
    """docs/ESTATE.md rule 2: keys the editor doesn't know — top-level AND per-entry — survive
    a write verbatim (the estate file is a shared contract downstream tools may extend)."""
    est = tmp_path / "estate.json"
    est.write_text(json.dumps({"version": 1, "future_key": {"x": 1},
                               "repos": [{"name": "keep", "root": "C:/k", "custom_ext": 42}]}),
                   encoding="utf-8")
    code, _ = M.estate_apply(est, "add", {"name": "new", "root": "C:/n", "tags": ["t"]})
    assert code == 200
    data = json.loads(est.read_text(encoding="utf-8"))
    assert data["future_key"] == {"x": 1}
    assert {"name": "keep", "root": "C:/k", "custom_ext": 42} in data["repos"]
    assert {"name": "new", "root": "C:/n", "tags": ["t"]} in data["repos"]


def test_estate_view_ignores_unknown_keys_and_legacy_list(tmp_path):
    """docs/ESTATE.md rule 1: unknown keys are never an error; a bare list is the legacy form."""
    est = tmp_path / "e.json"
    est.write_text(json.dumps({"version": 1, "mystery": True, "repos": []}), encoding="utf-8")
    v = M.estate_view(est)
    assert v["version"] == 1 and v["mystery"] is True
    est.write_text(json.dumps([{"name": "a", "root": "C:/a"}]), encoding="utf-8")
    v = M.estate_view(est)
    assert v["repos"] == [{"name": "a", "root": "C:/a"}]


def test_estate_remove_missing_is_404_and_no_registry_is_400(tmp_path):
    est = tmp_path / "e.json"
    est.write_text(json.dumps({"version": 1, "repos": []}), encoding="utf-8")
    assert M.estate_apply(est, "remove", {"name": "ghost"})[0] == 404
    assert M.estate_apply(None, "add", {"root": "C:/x"})[0] == 400


def test_estate_post_respects_read_only_posture(tmp_path):
    """The estate write sits behind the SAME guards as every exporter write."""
    est = tmp_path / "e.json"
    est.write_text(json.dumps({"version": 1, "repos": []}), encoding="utf-8")
    httpd, base = _serve([], read_only=True, registry_path=est)
    try:
        code, _ = _post(base + "/api/estate", {"action": "add", "entry": {"root": "C:/x"}})
        assert code == 403
    finally:
        httpd.shutdown()


# ----------------------------------------------------------------------------- dormant discovery
def test_discover_dormant_finds_undeployed_git_repos_only(tmp_path):
    (tmp_path / "plain_dir").mkdir()                                  # no .git → not listed
    (tmp_path / ".hidden" / ".git").mkdir(parents=True)               # dot-dir → not listed
    dormant = tmp_path / "sleeper"
    (dormant / ".git").mkdir(parents=True)                            # git, undeployed → listed
    deployed = _deployed(tmp_path, "awake")
    (deployed / ".git").mkdir()                                       # git + deployed → not listed
    out = M.discover_dormant([tmp_path], {"awake"})
    assert [d["name"] for d in out] == ["sleeper"]
    assert "exocortex.deploy install" in out[0]["deploy_cmd"]


# ----------------------------------------------------------------------------- CLI
def test_cli_status_never_touches_plugin_machinery(tmp_path, monkeypatch, capsys):
    """The lazy-loading proof: with the entry-points machinery BROKEN, `sentaince status` still
    works — a bad plugin can never break the vitals voice."""
    import importlib.metadata as ilm

    def _boom(*a, **kw):
        raise RuntimeError("plugin machinery must not be touched by status")
    monkeypatch.setattr(ilm, "entry_points", _boom)
    root = _deployed(tmp_path, "r1")
    assert cli.cmd_status([str(root)]) == 0
    assert "no routes yet" in capsys.readouterr().out


def test_cli_status_not_deployed_exits_1(tmp_path, capsys):
    assert cli.cmd_status([str(tmp_path)]) == 1
    assert "not deployed" in capsys.readouterr().out


def test_cli_unknown_command_dispatches_lazily(monkeypatch, capsys):
    """Unknown subcommands hit the plugin group; with none installed the exit is 2 + a help line."""
    monkeypatch.setattr(sys, "argv", ["sentaince", "definitely-not-a-command"])
    assert cli.main() == 2
    assert "unknown command" in capsys.readouterr().out


def test_cli_status_counts_routes_from_raw_colony_json(tmp_path, capsys):
    root = _deployed(tmp_path, "r1")
    sd = root / ".claude" / "exocortex"
    (sd / "colony_x.json").write_text(json.dumps({"label": "x", "tau": {"a\tb": 1.0, "b\tc": 0.5}}),
                                      encoding="utf-8")
    assert cli.cmd_status([str(root)]) == 0
    assert "2 routes earned" in capsys.readouterr().out
