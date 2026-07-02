"""Exp 6 — the outcome-conditioned scar oracle (the resolution of the antibody arc).

C5 proved destructive *intent* is not recoverable from the command string — by structure, lexicon,
or semantics. The resolution: stop reading the string; read the **effect**. Execute a proposed
action against a copy of the world-state (a sandbox dry-run), observe the state-delta, and refuse it
iff a **declared invariant** is violated.

Three properties that the string-level approaches could not have:

  * **spelling-invariant** — `rm -rf /backups`, `sh -c '…'`, `python3 -c "…rmtree…"`, `find / -delete`
    all produce the same delta (backups gone), so all are refused. (Defeats the C4-R *evasion* wall.)
  * **effect-specific** — `rm -rf /var/log/archive` (old logs, not a declared invariant) and
    `rm -rf /backups` are structurally identical but differ in *effect*; only the latter is refused.
    (Defeats the C4-R *collision* wall.)
  * **state-delta, not exit-code** — a destructive action *succeeds* (exit 0); the oracle reads what
    changed, not whether the action returned cleanly. (Defeats the exit-0 inversion.)

The honest core: this is **not a smarter classifier**. The effect model below stands in for a real
sandbox that *executes* the action (a container + filesystem diff); it observes outcomes, it does not
predict danger from surface form. Its limits are therefore a sandbox's limits — see the boundaries in
`docs/CLAIM_BOUNDARY.md` (C6): it defends only **declared** invariants (declaration stays a human/innate
channel), and only **sandboxable** effects (the un-sandboxable first-contact lethal still needs the
innate scar + human-in-the-loop).
"""
from __future__ import annotations

import re

# The abstract world: named resources, each in a state. PROTECTED names are the declared invariants;
# the rest exist but are not red-lined. ``photos`` exists but is deliberately UNDECLARED (the boundary).
PROTECTED: tuple[str, ...] = ("backups", "userdb", "etc_config", "boot", "disk")
NON_PROTECTED: tuple[str, ...] = ("tmp_cache", "build_dir", "var_log_archive", "spool")
UNDECLARED: tuple[str, ...] = ("photos",)
ALL_RESOURCES = PROTECTED + NON_PROTECTED + UNDECLARED


def default_world() -> dict[str, str]:
    return {r: "present" for r in ALL_RESOURCES}


def declared_invariants() -> set[str]:
    return set(PROTECTED)


# A path -> resource map (the "filesystem layout" the sandbox knows). Prefix-matched.
_PATH_TABLE: tuple[tuple[str, str], ...] = (
    ("/backups", "backups"),
    ("/var/lib/postgresql", "userdb"), ("/userdb", "userdb"),
    ("/etc", "etc_config"),
    ("/boot", "boot"),
    ("/dev/sda", "disk"), ("/dev/sdb", "disk"), ("/dev/nvme", "disk"),
    ("/tmp", "tmp_cache"),
    ("/var/spool", "spool"),
    ("/var/log/archive", "var_log_archive"),
    ("/home/user/photos", "photos"), ("/home", "photos"),
)
_DESTROY_VERBS = {"rm", "dd", "mkfs", "shred", "wipefs", "fdisk"}
_EMPTY_VERBS = {"truncate"}
_MUTATE_VERBS = {"chmod", "chown", "chgrp"}


def _resource(path: str) -> str | None:
    """Which resource a path refers to ('ALL' for root), or None if outside the modelled world."""
    p = path.rstrip("/") or "/"
    if p == "/":
        return "ALL"
    for prefix, res in _PATH_TABLE:
        if p == prefix or p.startswith(prefix + "/"):
            return res
    if path.startswith(("./", "../", "~/")):
        return "build_dir"
    return None


def _verb(command: str) -> str:
    toks = command.strip().split()
    if not toks:
        return ""
    head = toks[1] if (toks[0] == "sudo" and len(toks) > 1) else toks[0]
    return head.split(".")[0]


def _paths(command: str) -> list[str]:
    out: list[str] = []
    for tok in command.strip().split()[1:]:
        arg = tok.split("=", 1)[1] if tok.startswith(("if=", "of=")) else tok
        if arg.startswith(("/", "./", "../", "~/")):
            out.append(arg)
    return out


def _set_state(world: dict[str, str], res: str | None, state: str) -> None:
    if res is None:
        return
    if res == "ALL":
        for r in ALL_RESOURCES:
            world[r] = state
    elif res in world:
        world[res] = state


def apply(command: str, world: dict[str, str]) -> dict[str, str]:
    """The sandbox dry-run: return the world-state AFTER executing ``command`` (no real syscall).

    Unwraps shell/interpreter obfuscation by recursion/extraction — exactly as a real sandbox would
    by *running* the wrapped command. The point is that the OUTCOME is computed, never inferred from
    the surface form.
    """
    w = dict(world)
    cmd = command.strip()

    # shell wrapper: sh -c '<inner>' -> execute the inner
    m = re.match(r"(?:sudo\s+)?(?:sh|bash|zsh)\s+-c\s+(['\"])(.*)\1\s*$", cmd)
    if m:
        return apply(m.group(2), w)

    # interpreter wrapper: python -c "...rmtree('/p')..." / os.remove / unlink -> destroy that path
    if re.match(r"(?:sudo\s+)?python[0-9]?\s+-c\b", cmd):
        mp = re.search(r"(?:rmtree|remove|unlink)\(\s*['\"]([^'\"]+)['\"]", cmd)
        if mp:
            _set_state(w, _resource(mp.group(1)), "absent")
        return w

    verb = _verb(cmd)
    paths = _paths(cmd)

    # find <path> -delete : recursive delete under <path>
    if verb == "find" and "-delete" in cmd.split():
        _set_state(w, _resource(paths[0]) if paths else "ALL", "absent")
        return w

    if verb in _DESTROY_VERBS:
        for p in paths:
            _set_state(w, _resource(p), "absent")
    elif verb in _EMPTY_VERBS:
        for p in paths:
            _set_state(w, _resource(p), "empty")
    elif verb in _MUTATE_VERBS:
        for p in paths:
            _set_state(w, _resource(p), "mutated")
    return w


class OutcomeScarOracle:
    """Dry-run gate: permit iff executing the action in the sandbox violates no declared invariant."""

    def __init__(self, world: dict[str, str] | None = None, invariants: set[str] | None = None) -> None:
        self.world = world if world is not None else default_world()
        self.invariants = invariants if invariants is not None else declared_invariants()

    def violated(self, command: str) -> set[str]:
        """The set of declared invariants whose state would change — empty means safe."""
        after = apply(command, self.world)
        return {r for r in self.invariants if self.world.get(r) != after.get(r)}

    def permits(self, command: str) -> bool:
        return not self.violated(command)


def exit_code(command: str) -> int:
    """A well-formed action SUCCEEDS — including a destructive one. This is the exit-0 inversion:
    return code measures 'did it run', not 'was it safe'. Malformed/empty commands fail."""
    return 0 if command.strip() else 1


def exit_code_permits(command: str) -> bool:
    """The commodity 'trust success' gate: permit anything that runs cleanly (exit 0)."""
    return exit_code(command) == 0
