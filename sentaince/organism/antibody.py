"""The adaptive antibody — learned scars from witnessed harm (Experiment 4).

The innate immune system (``action_graph._LETHAL_PATTERNS`` + ``Interlock``) is a finite,
hard-coded scar list. It is structurally blind to any harmful action it was not pre-written to
recognize: ``classify("rm -rf /backups")`` is ``BENIGN`` because the innate ``rm`` pattern only
matches ``rm -rf /`` at the root. That is the honest finite-catalogue gap.

The **adaptive antibody** closes that gap the way an immune system does — not by widening the
innate germline list, but by *learning a new scar from one witnessed exposure*. When a permitted
action turns out to be harmful (ground-truth from the environment, never from the proposer or a
reflex's guess), the antibody records the action's **structural signature** and refuses any future
action sharing that signature.

Two design invariants, inherited from the organism law (control modulates dynamics; the
storage-separated floor caps safety):

1. **Additive, never subtractive.** The innate ``Interlock`` is composed read-only and checked
   first; the antibody can only *add* refusals, never weaken an innate one. ``_LETHAL_PATTERNS``,
   ``Interlock``, and ``effective_adjacency`` are imported, never modified.
2. **Bounded by a hand-specified signature space.** The antibody learns *which* signatures are
   toxic from experience; the signature *taxonomy* (effect × target-resource class) is engineered,
   not learned. This is the falsifiable scope — the eventual learned-signature version (slime-mold
   toxic-marking in RAG) is deliberately out of this experiment.

The signature granularity is the crux: too coarse (effect only) over-generalizes and false-scars
benign neighbours; the structural ``(effect, target)`` signature is the operating point this
experiment tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np

from .action_graph import Action
from .interlock import Interlock, Verdict, effective_adjacency


class Effect(Enum):
    """What an action *does* — its verb class."""

    DESTROY = "destroy"      # rm, dd, mkfs, shred, wipefs, truncate
    CONTROL = "control"      # kill, shutdown, reboot, iptables (host/service control)
    PERMISSION = "perm"      # chmod, chown, chgrp
    READ = "read"            # cat, ls, df, echo (non-destructive)
    OTHER = "other"          # unrecognized verb → not adaptively scar-able


class Target(Enum):
    """What an action acts *on* — its resource class."""

    PROTECTED = "protected"  # /etc /var /usr /boot ... and block devices /dev/sd*
    SCRATCH = "scratch"      # /tmp, /var/tmp, ./relative, /dev/null
    INIT = "init"            # PID 1
    FIREWALL = "firewall"    # iptables chains
    NONE = "none"            # no resource argument


@dataclass(frozen=True)
class Signature:
    """An action's structural shape: ``(effect, target)``. The scar is laid on the *shape*,
    not the literal command string, so one exposure generalizes across surface-distinct
    commands that share it (``rm -rf /backups`` → also refuses ``dd … of=/dev/sda``)."""

    effect: Effect
    target: Target

    @property
    def typed(self) -> bool:
        """Adaptively scar-able iff the verb is recognized (an OTHER effect is never learned)."""
        return self.effect is not Effect.OTHER


_DESTROY_VERBS = {"rm", "dd", "mkfs", "shred", "wipefs", "truncate", "fdisk", "parted"}
_CONTROL_VERBS = {"kill", "pkill", "killall", "shutdown", "reboot", "halt", "poweroff", "iptables"}
_PERMISSION_VERBS = {"chmod", "chown", "chgrp"}
_READ_VERBS = {"cat", "ls", "grep", "df", "du", "head", "tail", "find", "stat", "echo"}

# Resource roots. SCRATCH is checked before PROTECTED so that /var/tmp beats /var.
_SCRATCH_ROOTS = ("/tmp", "/var/tmp", "/var/cache", "/dev/null")
_PROTECTED_ROOTS = (
    "/etc", "/var", "/usr", "/boot", "/lib", "/lib64", "/opt", "/srv",
    "/home", "/root", "/data", "/backups", "/bin", "/sbin", "/sys", "/proc",
)
_BLOCK_DEVICE_PREFIXES = ("/dev/sd", "/dev/nvme", "/dev/hd", "/dev/vd", "/dev/xvd")


def _verb(command: str) -> str:
    """The leading binary, sudo-stripped and extension-stripped (``mkfs.ext4`` → ``mkfs``)."""
    tokens = command.strip().split()
    if not tokens:
        return ""
    head = tokens[0]
    if head == "sudo" and len(tokens) > 1:
        head = tokens[1]
    return head.split(".")[0]


def _effect(verb: str) -> Effect:
    if verb in _DESTROY_VERBS:
        return Effect.DESTROY
    if verb in _CONTROL_VERBS:
        return Effect.CONTROL
    if verb in _PERMISSION_VERBS:
        return Effect.PERMISSION
    if verb in _READ_VERBS:
        return Effect.READ
    return Effect.OTHER


def _paths(command: str) -> list[str]:
    """Path-like arguments, with ``if=``/``of=`` (dd) prefixes stripped."""
    out: list[str] = []
    for tok in command.strip().split()[1:]:
        arg = tok.split("=", 1)[1] if tok.startswith(("if=", "of=")) else tok
        if arg.startswith(("/", "./", "../", "~/")):
            out.append(arg)
    return out


def _target(command: str, verb: str, effect: Effect) -> Target:
    if effect is Effect.CONTROL:
        if verb == "iptables":
            return Target.FIREWALL
        tokens = command.strip().split()
        if verb in {"kill", "pkill", "killall"} and tokens and tokens[-1] == "1":
            return Target.INIT
        if verb in {"shutdown", "reboot", "halt", "poweroff"}:
            return Target.INIT
        return Target.NONE

    paths = _paths(command)
    for p in paths:
        if p.startswith(("./", "../", "~/")):
            return Target.SCRATCH
        if any(p == r or p.startswith(r + "/") for r in _SCRATCH_ROOTS):
            return Target.SCRATCH
    for p in paths:
        if p == "/" or any(p == r or p.startswith(r + "/") or p.startswith(r) for r in _PROTECTED_ROOTS):
            return Target.PROTECTED
        if any(p.startswith(prefix) for prefix in _BLOCK_DEVICE_PREFIXES):
            return Target.PROTECTED
    return Target.NONE


def signature_of(command: str) -> Signature:
    """Structurally type a command into ``(effect, target)``. Deterministic, pattern-free of the
    innate scar list and of the harm oracle — the antibody computes its *own* representation of a
    witnessed harm."""
    verb = _verb(command)
    effect = _effect(verb)
    target = _target(command, verb, effect)
    return Signature(effect=effect, target=target)


class AdaptiveAntibody:
    """A learned scar store keyed by structural signature.

    ``granularity``:
      - ``"structural"`` — key on ``(effect, target)`` (the treatment).
      - ``"effect_only"`` — key on ``effect`` alone (the over-generalization control: learning
        DESTROY-of-protected also scars DESTROY-of-scratch → false-scars benign neighbours).
    """

    def __init__(self, granularity: str = "structural") -> None:
        if granularity not in ("structural", "effect_only"):
            raise ValueError(f"unknown granularity {granularity!r}")
        self.granularity = granularity
        self._scars: set[tuple] = set()

    def _key(self, command: str) -> tuple | None:
        sig = signature_of(command)
        if not sig.typed:
            return None
        return (sig.effect,) if self.granularity == "effect_only" else (sig.effect, sig.target)

    def witness(self, command: str) -> bool:
        """One-shot aversive learning: record the signature of a witnessed-harmful action.

        Returns True if this laid a *new* scar (the signature was not already known)."""
        key = self._key(command)
        if key is None:
            return False
        is_new = key not in self._scars
        self._scars.add(key)
        return is_new

    def scarred(self, command: str) -> bool:
        """True iff the command's signature has been learned as toxic."""
        key = self._key(command)
        return key is not None and key in self._scars

    @property
    def n_scars(self) -> int:
        return len(self._scars)


class AdaptiveInterlock:
    """Innate ``Interlock`` + adaptive antibody, composed additively.

    The innate gate is checked first and never overridden weaker — the antibody can only add a
    refusal. A learned-toxic signature is given ``sigma = -1`` and run through the *same*
    ``effective_adjacency`` the innate scar uses, so the learned scar collapses the edge to zero by
    the identical NumPy operation, not a cooperative if-statement.
    """

    def __init__(self, antibody: AdaptiveAntibody, base_weight: float = 1.0) -> None:
        self._inner = Interlock(base_weight)
        self._antibody = antibody
        self._base = np.float64(base_weight)

    def gate(self, action: Action) -> Verdict:
        innate = self._inner.gate(action)
        if not innate.permitted:
            return innate  # the innate scar already refuses; the antibody never weakens it
        sigma = np.float64(-1.0 if self._antibody.scarred(action.command) else 1.0)
        capacity = float(effective_adjacency(self._base, sigma))
        if capacity > 0.0:
            return innate
        return Verdict(
            permitted=False,
            reason=(
                f"AdaptiveAntibody: refused learned-toxic signature "
                f"{signature_of(action.command)} `{action.command}` (capacity={capacity:.3f})"
            ),
            capacity=capacity,
        )
