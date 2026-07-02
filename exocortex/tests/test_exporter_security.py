"""Exporter control-plane write-surface guards (ADR-012 seam hardening; ENHANCEMENTS §C).

OUT of the 99-lock. Real HTTP round-trips against a ThreadingHTTPServer on an ephemeral port:
CSRF (content-type + Origin), --read-only, and the shared control token.

    python -m pytest exocortex/tests/test_exporter_security.py
"""
from __future__ import annotations

import json
import threading
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer

import pytest

from exocortex.testbed.exporter.metrics import _make_handler, _origin_is_local


@pytest.fixture()
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / ".claude" / "exocortex").mkdir(parents=True)
    (root / "exocortex_config.json").write_text(json.dumps({"eligibility_trace": {"mode": "off"}}),
                                                encoding="utf-8")
    return root


def _serve(repo_root, **handler_kw):
    handler = _make_handler(lambda: [{"name": "r1", "root": repo_root,
                                      "state_dir": repo_root / ".claude" / "exocortex",
                                      "config_path": repo_root / "exocortex_config.json"}], **handler_kw)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def _post(url, body: dict, ctype="application/json", headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": ctype, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def _get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read().decode()


WRITE = {"key": "eligibility_trace.gamma", "value": 0.8}     # an allowlisted TUNABLE knob


def test_default_posture_allows_json_write_and_get(repo):
    httpd, base = _serve(repo)
    try:
        assert _get(base + "/healthz")[0] == 200
        code, payload = _post(base + "/api/config/r1", WRITE)
        assert code == 200, payload
    finally:
        httpd.shutdown()


def test_read_only_refuses_all_posts_but_serves_reads(repo):
    httpd, base = _serve(repo, read_only=True)
    try:
        code, payload = _post(base + "/api/config/r1", WRITE)
        assert code == 403 and "read-only" in payload["error"]
        assert _get(base + "/api/repos")[0] == 200            # monitoring surface stays up
    finally:
        httpd.shutdown()


def test_csrf_content_type_and_origin(repo):
    httpd, base = _serve(repo)
    try:
        # the browser cross-site no-preflight shape: text/plain → refused
        code, payload = _post(base + "/api/config/r1", WRITE, ctype="text/plain")
        assert code == 415, payload
        # a present non-loopback Origin → refused even with correct content-type
        code, payload = _post(base + "/api/config/r1", WRITE, headers={"Origin": "http://evil.example"})
        assert code == 403 and "cross-origin" in payload["error"]
        # the control page's own shape (loopback Origin) still works
        code, _ = _post(base + "/api/config/r1", WRITE, headers={"Origin": f"http://127.0.0.1:9109"})
        assert code == 200
    finally:
        httpd.shutdown()


def test_token_required_when_configured(repo):
    httpd, base = _serve(repo, token="s3cret")
    try:
        code, payload = _post(base + "/api/config/r1", WRITE)
        assert code == 403 and "token" in payload["error"]
        code, _ = _post(base + "/api/config/r1", WRITE, headers={"X-Exocortex-Token": "s3cret"})
        assert code == 200
        code, _ = _post(base + "/api/config/r1", WRITE, headers={"Authorization": "Bearer s3cret"})
        assert code == 200
        code, _ = _post(base + "/api/config/r1", WRITE, headers={"X-Exocortex-Token": "wrong"})
        assert code == 403
    finally:
        httpd.shutdown()


def test_origin_parser():
    assert _origin_is_local("http://localhost:9109")
    assert _origin_is_local("http://127.0.0.1")
    assert not _origin_is_local("http://evil.example")
    assert not _origin_is_local("garbage")


def test_frozen_keys_still_unreachable_with_token(repo):
    """The safety boundary is orthogonal to auth: a VALID token still cannot touch the safety genome."""
    httpd, base = _serve(repo, token="s3cret")
    try:
        code, payload = _post(base + "/api/config/r1", {"key": "integrity.mode", "value": "off"},
                              headers={"X-Exocortex-Token": "s3cret"})
        assert code == 403, payload                            # TUNABLE_SCHEMA allowlist: not writable
    finally:
        httpd.shutdown()
