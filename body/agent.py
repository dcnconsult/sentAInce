"""In-body RPC agent — runs inside the disposable BODY container (M3).

The organism (immune system) never holds a Docker socket. Its ONLY capability over the body is to
POST a command string to this agent on a private network; the agent runs it in the body's own
namespace and reports the OBSERVED outcome (a real filesystem state-delta). If a slipped lethal kills
this agent, the RPC simply stops answering — that is the observed host-death signal.

Stdlib only (no deps), so the body image stays minimal. Endpoints:
  GET  /healthz   -> {"alive": true}
  GET  /snapshot  -> {"resources": {<res>: "present|empty|absent"}, "pid1_alive": bool}
  GET  /vitals    -> cgroup-v2 memory headroom (the real interoceptive energy gauge)
  POST /run       -> {"command": ...} -> {exit, stdout, stderr, delta, violated, host_alive, before, after}
  POST /flood     -> {"mb": N} -> balloon N MB and HOLD it (real cgroup memory pressure)

Only PERMITTED (gate-approved) commands are ever sent here; the dangerous ones are refused upstream
and never reach the body. The container's limits (cap_drop, mem/pids caps, no-egress net, disposable)
are the OUTER safety boundary regardless.
"""
from __future__ import annotations

import json
import os
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WORLD = "/world"  # writable world (tmpfs) — benign ops really mutate these
# BODY_ROLE: "live" (declared invariants baked READ-ONLY at /declared — physically immutable) or
# "shadow" (declared invariants on the writable tmpfs world, so a /dryrun can REVEAL what a command
# would do to them — C6's read-the-effect mechanism, used by the gate, not by the live executor).
ROLE = os.environ.get("BODY_ROLE", "live")
_DECLARED_ROOT = f"{WORLD}/declared" if ROLE == "shadow" else "/declared"

PROTECTED = ("backups", "userdb", "etc_config", "boot", "disk")
WRITABLE_RESOURCES = ("tmp_cache", "build_dir", "spool", "var_log_archive", "photos")

# resource -> real path.
RESOURCE_PATHS: dict[str, str] = {
    **{res: f"{_DECLARED_ROOT}/{res}" for res in PROTECTED},
    "tmp_cache": f"{WORLD}/tmp_cache",
    "build_dir": f"{WORLD}/build_dir",
    "spool": f"{WORLD}/spool",
    "var_log_archive": "/var/log/archive",
    "photos": f"{WORLD}/photos",
}
# what seed_world (re)creates: in a shadow the declared invariants are writable so they are seeded here;
# in the live body they are baked read-only and must NOT be written.
_SEEDABLE = (PROTECTED + WRITABLE_RESOURCES) if ROLE == "shadow" else WRITABLE_RESOURCES

_BALLOON: list[bytearray] = []  # holds allocated memory so cgroup memory.current actually rises


def seed_world() -> None:
    """(Re)create the seedable resources (idempotent). In the live body the declared invariants are baked
    read-only and excluded; in a shadow they are writable and seeded so a dry-run can mutate them."""
    for res in _SEEDABLE:
        path = RESOURCE_PATHS[res]
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, ".sentinel"), "w", encoding="utf-8") as fh:
            fh.write(res)


def state_of(path: str) -> str:
    if not os.path.exists(path):
        return "absent"
    if os.path.isdir(path):
        return "present" if os.listdir(path) else "empty"
    return "present" if os.path.getsize(path) > 0 else "empty"


def snapshot() -> dict[str, str]:
    return {res: state_of(path) for res, path in RESOURCE_PATHS.items()}


def read_vitals() -> dict:
    def _read(p: str) -> str | None:
        try:
            with open(p, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            return None

    # cgroup v2 (unified) first, then v1 fallback — Docker engines vary.
    cur, mx, ver = _read("/sys/fs/cgroup/memory.current"), _read("/sys/fs/cgroup/memory.max"), "v2"
    if cur is None or mx is None:
        cur = _read("/sys/fs/cgroup/memory/memory.usage_in_bytes")
        mx = _read("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        ver = "v1"

    mem_headroom = None
    if cur is not None and mx not in (None, "max"):
        try:
            cur_i, mx_i = int(cur), int(mx)
            # a v1 "no limit" sentinel is a huge number → treat as unreadable (no measurable ceiling)
            if 0 < mx_i < (1 << 62):
                mem_headroom = max(0.0, 1.0 - cur_i / mx_i)
        except ValueError:
            pass
    return {"cgroup": ver, "mem_current": cur, "mem_max": mx, "mem_headroom": mem_headroom,
            "ballooned_chunks": len(_BALLOON)}


def flood(mb: int) -> dict:
    _BALLOON.append(bytearray(int(mb) * 1024 * 1024))  # allocate and HOLD -> real cgroup pressure
    return {"ballooned_mb": int(mb), "held_chunks": len(_BALLOON)}


def _exec(command: str, timeout: float) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd="/")
        return proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:]
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except OSError as exc:  # defensive (e.g. /bin/sh missing) — never crash the agent thread
        return 127, "", f"exec error: {exc}"


def run_command(command: str, timeout: float = 10.0) -> dict:
    before = snapshot()
    exit_code, stdout, stderr = _exec(command, timeout)
    after = snapshot()
    delta = {r: [before[r], after[r]] for r in after if before[r] != after[r]}
    violated = [r for r in PROTECTED if before.get(r) != after.get(r)]
    return {"exit": exit_code, "stdout": stdout, "stderr": stderr, "delta": delta,
            "violated": violated, "host_alive": os.path.exists("/proc/1"),
            "before": before, "after": after}


def dryrun(command: str, timeout: float = 10.0) -> dict:
    """C6 dry-run (shadow only): really execute the command against the shadow's WRITABLE declared world,
    observe which declared invariants it WOULD violate, then restore. Pure observation, no prediction —
    so an obfuscated deletion (find -exec rm) is caught exactly like a plain one."""
    seed_world()                       # fresh baseline
    before = snapshot()
    exit_code, _, _ = _exec(command, timeout)
    after = snapshot()
    would_violate = sorted(r for r in PROTECTED if before.get(r) != after.get(r))
    delta = {r: [before[r], after[r]] for r in after if before[r] != after[r]}
    seed_world()                       # restore for the next dry-run
    # timed_out → the effect could NOT be fully observed within the budget; the caller must fail-safe.
    return {"would_violate": would_violate, "delta": delta, "timed_out": exit_code == 124}


class _Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self._send(200, {"alive": True})
        elif self.path == "/snapshot":
            self._send(200, {"resources": snapshot(), "pid1_alive": os.path.exists("/proc/1")})
        elif self.path == "/vitals":
            self._send(200, read_vitals())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_json()
        if self.path == "/run":
            command = str(body.get("command", ""))
            if not command:
                self._send(400, {"error": "no command"})
                return
            self._send(200, run_command(command))
        elif self.path == "/flood":
            self._send(200, flood(int(body.get("mb", 100))))
        elif self.path == "/reset":
            seed_world()  # re-create the world (restores anything a prior episode deleted)
            self._send(200, {"reseeded": True, "resources": snapshot()})
        elif self.path == "/dryrun":
            if ROLE != "shadow":
                self._send(400, {"error": "dryrun is available only on a shadow body (BODY_ROLE=shadow)"})
                return
            command = str(body.get("command", ""))
            if not command:
                self._send(400, {"error": "no command"})
                return
            self._send(200, dryrun(command))
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:  # noqa: A002 — silence default stderr logging
        return


def main() -> int:
    seed_world()
    port = int(os.environ.get("BODY_PORT", "8088"))
    server = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    print(f"[body-agent] seeded world; listening on :{port}", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
