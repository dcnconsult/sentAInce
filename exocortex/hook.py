"""Exocortex hook dispatcher — the single entry point wired into Claude Code hooks.

Usage (from .claude/settings.json):  ``python <repo>/exocortex/hook.py <EventName>``
Reads the hook JSON on stdin, updates session state + the audit trail, and emits the per-event
decision (deny / ask / additionalContext) per the verified Claude Code 2.1.195 contract. It is
self-locating (adds the repo root to ``sys.path``) and **fails open** — a hook must never crash the
agent, so every error path falls through to allow / no-op.

Modes (``EXOCORTEX_MODE``): observe (Stage 0, log only + lethal failsafe) · somatic (+ hard veto) ·
epistemic (+ interoceptive injection) · full (both).
"""
from __future__ import annotations

import sys
import os
import json
import re
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from exocortex.config import (Mode, mode, lethal_failsafe,                  # noqa: E402
                              colony_enabled, colony_splice_enabled, embed_enabled,
                              declarative_enabled, declarative_vault, bridge_enabled, integrity_mode,
                              state_dir)
from exocortex import audit                                 # noqa: E402
from exocortex.state import SessionState, command_key       # noqa: E402


# ---- output helpers (verified 2.1.195 contract) ----
def _deny(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "deny", "permissionDecisionReason": reason}}


def _ask(reason: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "ask", "permissionDecisionReason": reason}}


def _allow(reason: str = "exocortex: permitted") -> dict:
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "permissionDecision": "allow", "permissionDecisionReason": reason}}


def _inject(event: str, text: str) -> dict:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def _bash_command(data: dict) -> str:
    ti = data.get("tool_input") or {}
    return str(ti.get("command", "")) if isinstance(ti, dict) else ""


def _classify_cue(prompt: str) -> str:
    """Discover/route the goal-class for a prompt. Prefers the semantic EMBEDDING classifier when opted in
    (`EXOCORTEX_EMBED=1`) and available; otherwise — or on any failure — the fast lexical classifier.
    Always returns a label (``_default`` only if everything fails); never crashes the hook."""
    if embed_enabled():
        try:
            from exocortex.embed_classifier import EmbeddingCueClassifier
            if EmbeddingCueClassifier.available():
                cc = EmbeddingCueClassifier.load()
                lab = cc.classify(prompt)["label"]
                cc.save()
                return lab
        except Exception:
            pass   # fall through to the lexical classifier
    try:
        from exocortex.cue_classifier import CueClassifier
        cc = CueClassifier.load()
        lab = cc.classify(prompt)["label"]
        cc.save()
        return lab
    except Exception:
        return "_default"


def _deposit_weight(st) -> float:
    """Session-quality weight for a colony deposit, in [WEIGHT_MIN, 1.0]. Two consequence-grounded factors:
      · activity — a focused task lays 1-2 deposits at ~full weight; a flailing session's later, wandering
        deposits decay as ``SESSION_DECAY ** session_deposits`` (catches the all-`exit 0` thrash that P-C
        found — a max-turns session dumping many succeeding-but-pointless commands);
      · success-rate — a success that came amid failures is weaker evidence than one in a clean run.
    A flailing session's clutter is thus born near the prune floor and self-cleans fast."""
    from exocortex.colony import SESSION_DECAY, WEIGHT_MIN
    activity = SESSION_DECAY ** max(0, int(getattr(st, "session_deposits", 0)))
    hist = getattr(st, "history", None) or []
    oks = sum(1 for _, o in hist if o == "ok")
    success_rate = (oks / len(hist)) if hist else 1.0
    return max(WEIGHT_MIN, activity * success_rate)


def model_from_transcript(path: str, tail_bytes: int = 65536) -> str:
    """Source the head model-id for the F3 provenance stamp from the session transcript TAIL — the hook stdin
    contract carries no model field, but the transcript records it at ``message.model`` of each
    ``type:"assistant"`` entry. Reads only the last ``tail_bytes`` (a bounded seek, NOT a full parse — the
    4-min-hang lesson: never heavy I/O on the hot path) and returns the model of the MOST RECENT assistant
    turn (so a mid-session ``/model`` switch is picked up). Fail-open → "" (then the version-distance term
    simply stays inert). The first line in the tail window is usually a truncated mid-line; it fails to parse
    and is skipped, and in reverse order a complete entry is found first anyway."""
    try:
        if not path or not os.path.isfile(path):
            return ""
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - tail_bytes))
            chunk = f.read()
        for ln in reversed(chunk.split(b"\n")):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue                       # truncated/partial line in the tail window → skip
            if d.get("type") == "assistant":
                msg = d.get("message")
                if isinstance(msg, dict) and msg.get("model"):
                    return str(msg["model"])
        return ""
    except Exception:
        return ""                              # a hook must never crash the agent


def prompt_from_cursor_transcript(path: str, tail_bytes: int = 262144) -> str:
    """The most recent USER prompt from a Cursor transcript — for the lazy-init classifier when a Cursor
    ``beforeSubmitPrompt`` didn't fire. Reads only the tail (bounded I/O — the 4-min-hang lesson); records are
    ``{"role":"user","message":{"content":[{"type":"text","text":...}]}}`` with a leading ``<timestamp>…``
    marker that is stripped. Fail-open → ''."""
    try:
        if not path or not os.path.isfile(path):
            return ""
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - tail_bytes))
            chunk = f.read()
        for ln in reversed(chunk.split(b"\n")):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if d.get("role") != "user":
                continue
            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            content = msg.get("content")
            if isinstance(content, list):
                text = " ".join(str(c.get("text", "")) for c in content if isinstance(c, dict))
            else:
                text = str(content or msg.get("text") or "")
            text = re.sub(r"<timestamp>.*?</timestamp>\s*", "", text, flags=re.S)   # strip the whole date block
            text = re.sub(r"</?timestamp>", " ", text).strip()                       # + any stray marker
            if text:
                return text[:2000]
        return ""
    except Exception:
        return ""


def _cursor_lazy_classify(session: str, data: dict) -> None:
    """Cursor beta: the first ``beforeSubmitPrompt`` of a turn/session often doesn't fire → the turn is never
    classified → the burst of agent tool-calls misbinds to ``_default`` (measured: coldstart_gauge — 84% of a
    real Cursor soak's deposits landed in _default). Recover: if THIS generation wasn't classified by a
    ``UserPromptSubmit``, read the last user prompt from the Cursor transcript, classify it, and seed
    ``goal_class`` + the trail ``cue:`` root — exactly what ``handle_userpromptsubmit`` would have. Cursor-only,
    fail-open; runs once per turn (keyed on ``generation_id``)."""
    from exocortex.config import provider
    if provider() != "cursor" or not colony_enabled():
        return
    try:
        gen = str(data.get("generation_id") or "")
        with SessionState.locked(session) as st:     # BUG_SESSIONSTATE_RACE: lock the load-modify-save
            if gen and gen == st.classified_generation:
                return                               # this turn was already classified (a UserPromptSubmit fired)
            if not gen and st.goal_class != "_default":
                return                               # no generation id, but already on a real class → leave it
            from exocortex import adapter
            prompt = prompt_from_cursor_transcript(adapter.cursor_transcript_path(data))
            if not prompt:
                return                               # can't recover the prompt → the existing _default path stands
            label = _classify_cue(prompt)
            st.goal_class = label
            st.trail = [f"cue:{label}"]              # seed the cue root so the first consequence forms an edge
            st.injected_exons = []
            st.action_buffer = []
            st.classified_generation = gen
            st.save()
    except Exception:
        pass   # a hook must never crash the agent


def _track_node(session: str, tool: str, payload: str) -> None:
    """Lay the verb-altitude node onto the colony's decision-trail (the path being walked toward the
    next consequence). Best-effort; the colony is the memory subsystem, orthogonal to somatic/epistemic.
    Always locks its own load→push→save (BUG_SESSIONSTATE_RACE: parallel PreToolUse hooks raced the
    unlocked save and dropped nodes → fused τ edges); never accepts a pre-loaded state — a stale
    unlocked read saved under the lock would clobber concurrent writers all the same."""
    if not colony_enabled():
        return
    try:
        from exocortex.colony import verb_node
        with SessionState.locked(session) as st:
            st.push_node(verb_node(tool, payload))
            st.save()
    except Exception:
        pass   # a hook must never crash the agent


def _buffer_action(session: str, tool: str, data: dict) -> None:
    """Record the consequence-bearing content of a tool call (the Bash command / edit content) onto the
    current segment's action buffer — the surface the wiki attribution scans for used-note echo. Gated
    on the declarative organ (dormant by default → zero overhead); best-effort, never crashes."""
    if not declarative_enabled():
        return
    try:
        from exocortex.wiki.store import action_text_of
        txt = action_text_of(tool, data)
        if not txt:
            return
        with SessionState.locked(session) as st:     # BUG_SESSIONSTATE_RACE: lock the load-modify-save
            st.action_buffer = (list(getattr(st, "action_buffer", [])) + [txt[:2000]])[-50:]
            st.save()
    except Exception:
        pass   # a hook must never crash the agent


def targets_exist(command: str) -> bool:
    """Does the command name an absolute path that EXISTS on the real fs? Used by the UNGATED null's
    safety floor — the null lets a gate-refused command 'execute', but only against an ABSENT target
    (harmless by construction); a command touching a real existing path is denied even in the null."""
    return any(os.path.exists(p) for p in re.findall(r"/[A-Za-z0-9_./\-]+", command))


_FAIL_MARKERS = ("Traceback (most recent call last)", "command not found",
                 "No such file or directory", "fatal:", "FAILED", "AssertionError")
_EXITCODE_RE = re.compile(r"(?:exit|Exit code)[:\s]+([1-9]\d*)")


def classify_outcome(data: dict) -> str:
    """A PostToolUse 'success' can hide a failed inner command (agents append `; echo \"exit: $?\"`
    or `|| true`, so the Bash tool exits 0). Read the OBSERVED effect — stdout/stderr — and call it
    'fail' on a non-zero echoed exit code or a known error signature. Heuristic and conservative."""
    tr = data.get("tool_response") or {}
    if isinstance(tr, dict):
        blob = f"{tr.get('stdout', '')}\n{tr.get('stderr', '')}"
    else:
        blob = str(tr)
    if _EXITCODE_RE.search(blob):
        return "fail"
    return "fail" if any(mk in blob for mk in _FAIL_MARKERS) else "ok"


# ---- per-event handlers ----
def handle_pretooluse(data: dict, m: Mode):
    # The Exocortex is the permission authority for the session. Non-command tools (Read/Edit/Write/…)
    # are sandbox-local and auto-granted so the agent can work headlessly; only Bash is gated. We still
    # AUDIT non-command tools (lightly) so judges can see grounding (did it read the file before answering?).
    tool = data.get("tool_name", "")
    session = str(data.get("session_id", "session"))
    _cursor_lazy_classify(session, data)   # Cursor: recover goal_class if beforeSubmitPrompt missed this turn
    if tool != "Bash":
        ti = data.get("tool_input") or {}
        if tool == "PowerShell" and isinstance(ti, dict):
            # D3: PowerShell is a COMMAND tool — carry its command text so the audit stays judgeable and
            # the trail node lands at the verb altitude (`ps:<verb>`), not a flat PowerShell:other. Still
            # auto-allowed here: the somatic gate's vocabulary is Bash-shaped; extending the VETO to
            # PowerShell is a separate design question, not part of the consequence-coverage fix.
            target = str(ti.get("command") or "")
        else:
            target = str(ti.get("file_path") or ti.get("path") or ti.get("pattern") or "") if isinstance(ti, dict) else ""
        audit.append(audit.record(session=session, event="PreToolUse", mode=m.value, tool=tool,
                                   command=target, action="allow"))
        _track_node(session, tool, target)   # colony trail (the path toward the next consequence)
        _buffer_action(session, tool, data)  # wiki attribution: what the model actually did (gated)
        return _allow("exocortex: non-command tool permitted")
    cmd = _bash_command(data)
    if not cmd.strip():
        return _allow()

    from exocortex.somatic import vet, sig_label   # lazy (pulls the locked gate + numpy)
    from exocortex import epistemic as epi

    decision = vet(cmd)
    everdict = epi.assess(cmd)
    key = command_key(cmd)
    st = SessionState.load(session)

    action, out = "allow", _allow("exocortex: permitted")
    if m is Mode.UNGATED:
        # anti-vacuity null: the gate is REMOVED, so a gate-refused command executes — EXCEPT the
        # experiment's hard safety floor: NEVER execute a C1 lethal (rm -rf /, kill -9 1) and never a
        # command whose target exists on the real fs (absent target → harmless by construction).
        if (not decision.permitted) and (decision.organ == "C1_interlock" or targets_exist(cmd)):
            action, out = "deny", _deny("ungated null: hard safety floor (C1 lethal / existing-path target)")
    elif m in (Mode.SOMATIC, Mode.FULL):
        if not decision.permitted:
            action, out = "deny", _deny(f"exocortex somatic veto [{decision.organ}]: {decision.reason}")
        elif everdict.decision.value == "abstain":
            action, out = "deny", _deny(f"exocortex epistemic ABSTAIN: {everdict.reason}")
        elif everdict.decision.value == "verify":
            action, out = "ask", _ask(f"exocortex epistemic VERIFY: {everdict.reason}")
    elif (not decision.permitted) and lethal_failsafe():
        # OBSERVE / EPISTEMIC: no epistemic veto, but NEVER execute a gate-recognized-destructive
        # command on a real host — record the ATTEMPT (the baseline metric), block execution.
        action, out = "deny", _deny(f"exocortex safety failsafe [{decision.organ}]: {decision.reason}")

    rec = audit.record(
        session=session, event="PreToolUse", mode=m.value, tool="Bash", command=cmd,
        command_key=key, signature=sig_label(cmd),
        somatic_permitted=decision.permitted, somatic_organ=decision.organ,
        epistemic_decision=everdict.decision.value, action=action,
        energy=st.energy, tier=st.tier(), strategy_lock=st.consecutive_failures(key),
        reason=(out["hookSpecificOutput"]["permissionDecisionReason"] if out else ""),
    )
    audit.append(rec)
    _track_node(session, "Bash", cmd)   # extend the trail with the command node — loads FRESH under the
    #                                     state lock (the old reuse of the st read above was the race:
    #                                     save-after-stale-load dropped concurrent hooks' nodes)
    _buffer_action(session, "Bash", data)   # wiki attribution: the command the model ran (gated)
    return out


def handle_consequence(data: dict, m: Mode, outcome: str):
    tool = data.get("tool_name", "")
    if tool not in ("Bash", "PowerShell"):     # D3: consequence observation covers BOTH command tools —
        return None                            # the audit showed PowerShell 10/0 pre/post (fully dark)
    cmd = _bash_command(data)
    tr = data.get("tool_response") or {}
    if isinstance(tr, dict):
        snippet = f"{tr.get('stdout', '')} {tr.get('stderr', '')}".strip()[:240]
    else:
        snippet = (str(tr) or str(data.get("error", "")))[:240]
    if not snippet and data.get("error"):
        snippet = str(data.get("error"))[:240]
    session = str(data.get("session_id", "session"))
    key = command_key(cmd)
    # BUG_SESSIONSTATE_RACE: the whole consequence bookkeeping is one load-modify-save on the session
    # state (debit/record + trail re-root + wiki attribution surfaces) — hold the state lock across it
    # so a concurrent hook (parallel Bash+PowerShell consequences) can't drop a history entry/deposit.
    with SessionState.locked(session) as st:
        st.debit(outcome)
        st.record(key, outcome)
        # F3 provenance: resolve the head model-id for the deposit stamp from the transcript TAIL (the hook stdin
        # has no model field). An explicit EXOCORTEX_MODEL wins; otherwise fill it from the transcript so BOTH the
        # procedural and declarative deposits below stamp it (the hook process is ephemeral → env mutation is
        # contained to this one event). Only on a verified exit 0, where a deposit will actually happen.
        if outcome == "ok" and not os.environ.get("EXOCORTEX_MODEL"):
            _m = model_from_transcript(data.get("transcript_path", ""))
            if _m:
                os.environ["EXOCORTEX_MODEL"] = _m
        # Colony: a Bash consequence closes the current trail-segment. Deposit pheromone on the path into the
        # CURRENT goal-class's colony ONLY on a verified exit 0 (the reflex-memory law — symmetric to the
        # strategy-lock scar); drop it on failure. Re-root the trail at the cue (pivot P-A): on success also
        # keep the command node so multi-command workflows chain; on failure keep only the cue (drop the
        # failed tail). The cue root means even a single successful command forms an edge.
        seg_len = 0                                          # #edges this consequence deposited (3D telemetry)
        lock_failopen = int(getattr(st, "_lock_failopen", False))   # W4: session-lock acquisition result
        if colony_enabled():
            try:
                from exocortex.colony import Colony, edges, verb_node
                from exocortex.endocrine import levers
                cue = f"cue:{getattr(st, 'goal_class', '_default')}"
                if outcome == "ok":
                    es = edges(st.trail)
                    seg_len = len(es)                       # the flail-then-succeed segment length (live)
                    if es:
                        prune, _cap = levers(st.tier())     # allostatic prune floor (endocrine; off→static)
                        # ADR-020 W3: the colony RMW gets its OWN cross-process lock — the session lock
                        # (held here) is per-session; two sessions share a class's colony file. Lock
                        # order law: session before colony, never the reverse.
                        with Colony.locked(st.goal_class) as col:
                            col.deposit(es, _deposit_weight(st), prune=prune,   # session-quality discount + 3D trace
                                        ts=time.time(), model=os.environ.get("EXOCORTEX_MODEL", ""))  # F3 provenance stamp
                            col.save()
                        lock_failopen += int(col._lock_failopen)   # W4: colony-lock acquisition result
                        st.session_deposits = getattr(st, "session_deposits", 0) + 1
                    st.trail = [cue, verb_node(tool, cmd)]  # D3: `bash:`/`ps:` per the actual command tool
                else:
                    st.trail = [cue]
            except Exception:
                pass   # a hook must never crash the agent
        # Declarative wiki (Ticket 1; gated, dormant by default): the SAME exit-0 consequence credits the wiki
        # notes the model actually USED this segment (content echo in the action buffer) — never merely injected.
        wiki_injected = wiki_used = 0
        if declarative_enabled() and outcome == "ok":
            try:
                from exocortex.wiki.attribute import deposit_attributed
                from exocortex.wiki.store import load_graph
                injected = list(getattr(st, "injected_exons", []))
                wiki_injected = len(injected)
                graph = load_graph(declarative_vault(), label=st.goal_class)
                if graph is not None and graph.nodes:
                    action = " \n".join(getattr(st, "action_buffer", []))
                    used = deposit_attributed(graph, injected, action, 0,
                                              cue=f"cue:{st.goal_class}", label=st.goal_class)
                    wiki_used = len(used)
                    if used:
                        st.wiki_active = used   # the proposer's spreading-activation seed for the next turn
            except Exception:
                pass
        # Hippocampus verify (Ticket 2; gated, BOTH outcomes): a provisional bridge is WALKED when both endpoints
        # were attributed this segment → exit-0 crystallizes the a→d edge, repeated no-pay walks scar it.
        if bridge_enabled() and declarative_enabled():
            try:
                from exocortex.wiki.attribute import attribute_used
                from exocortex.wiki.bridge import load_bridges, save_bridges, verify
                from exocortex.wiki.store import load_graph
                gb = load_graph(declarative_vault(), label=st.goal_class)
                if gb is not None and gb.nodes:
                    walked = attribute_used(gb, list(getattr(st, "injected_exons", [])),
                                            " \n".join(getattr(st, "action_buffer", [])))
                    bridges = load_bridges()
                    verify(gb, bridges, walked, 0 if outcome == "ok" else 1, label=st.goal_class)
                    save_bridges(bridges)
            except Exception:
                pass
        st.action_buffer = []   # the consequence closes the segment (mirrors the colony trail re-root)
        st.save()
    audit.append(audit.record(
        session=session, event=("PostToolUse" if outcome == "ok" else "PostToolUseFailure"),
        mode=m.value, tool=tool, command=cmd, command_key=key,
        energy=st.energy, tier=st.tier(), strategy_lock=st.consecutive_failures(key),
        outcome=outcome, output=snippet, seg_len=seg_len,
        wiki_injected=wiki_injected, wiki_used=wiki_used,
        lock_failopen=lock_failopen,   # W4: fail-open lock acquisitions during this consequence
    ))
    return None


def handle_userpromptsubmit(data: dict, m: Mode):
    session = str(data.get("session_id", "session"))
    prompt = str(data.get("prompt", ""))
    # BUG_SESSIONSTATE_RACE: hold the state lock across the turn re-seed (goal_class/trail/attribution
    # surfaces) so a straggler PostToolUse from the previous turn can't clobber the fresh segment.
    with SessionState.locked(session) as st:

        # Cue-classifier (pivot P-B): assign this prompt to a DISCOVERED goal-class. The label keys the
        # per-class colony AND seeds the trail's `cue:` root (pivot P-A) — so even a one-command turn forms
        # an edge and every deposit binds to its class.
        label = "_default"
        if colony_enabled():
            label = _classify_cue(prompt)
        st.goal_class = label
        st.trail = [f"cue:{label}"]
        st.injected_exons = []      # the new turn's wiki attribution surface (set below if we splice)
        st.action_buffer = []       # fresh segment

        blocks = []
        if m in (Mode.EPISTEMIC, Mode.FULL):
            from exocortex.interocept import interoceptive_block
            b = interoceptive_block(st)
            if b:
                blocks.append(b)
        # Splice the MATCHING class's converged memory via the verified channel. Trigger on the re-splice
        # flag (first prompt / post-compaction wake) OR a task-class SWITCH (surface the right skill when the
        # work changes). Abstains automatically on a novel/unconverged class (its colony splice is empty).
        if colony_enabled() and colony_splice_enabled() and (st.resplice or label != st.last_spliced_class):
            try:
                from exocortex.colony import Colony
                splice = Colony.load(label).splice()
                if splice:
                    blocks.append(splice)
                    st.last_spliced_class = label
            except Exception:
                pass
        # Declarative wiki (Ticket 1; gated, dormant by default): propose candidates (structural + lexical +
        # muscle-memory; numpy-free), let the Transcriptome filter by earned τ, inject — and record the
        # injected exon ids as this turn's attribution surface. Abstains silently on a cold/empty wiki.
        if declarative_enabled():
            try:
                from exocortex.wiki.propose import propose
                from exocortex.wiki.splice import splice_with_ids
                from exocortex.wiki.store import load_graph
                graph = load_graph(declarative_vault(), label=label)
                if graph is not None and graph.nodes:
                    cands = propose(graph, prompt=prompt, active_context=list(getattr(st, "wiki_active", [])))
                    wiki, injected = splice_with_ids(graph, cands)
                    st.injected_exons = injected
                    if wiki:
                        blocks.append(wiki)
                    # Hippocampus offer (Ticket 2; gated): surface provisional bridges whose source the proposer
                    # raised, and add BOTH endpoints to the attribution surface so a walk (A & D both used in one
                    # exit-0) is detectable. Provisional — crystallizes only on that exit-0.
                    if bridge_enabled():
                        from exocortex.wiki.bridge import load_bridges, offer, save_bridges
                        bridges = load_bridges()
                        bpay, endpoints = offer(graph, bridges, cands)
                        if bpay:
                            blocks.append(bpay)
                            st.injected_exons = list(dict.fromkeys(injected + endpoints))
                            save_bridges(bridges)
            except Exception:
                pass
        st.resplice = False
        st.classified_generation = str(data.get("generation_id") or "")   # Cursor: mark this turn classified (lazy-init skip)
        st.save()

    out = _inject("UserPromptSubmit", "\n\n".join(blocks)) if blocks else None
    audit.append(audit.record(
        session=session, event="UserPromptSubmit", mode=m.value,
        energy=st.energy, tier=st.tier(), injected=bool(blocks), reason=f"class={label}",
    ))
    return out


def handle_precompact(data: dict, m: Mode):
    """The circadian 'sleep'. EMPIRICALLY VERIFIED (headless capture, 2.1.195): PreCompact fires
    (trigger auto|manual) but its ``additionalContext`` is NOT injected into the model — so this hook
    does the CONSOLIDATION only (decay once, prune the dust, cap to the strongest reflexes) and sets a
    per-session re-splice flag. The colony lives in ``colony.json`` (it already survives compaction,
    independent of the transcript); the dense memory is spliced back on the next ``UserPromptSubmit``
    (the verified injection channel) — see [[claude-code-hook-contract-2-1-195]]."""
    session = str(data.get("session_id", "session"))
    consolidated = 0
    if colony_enabled():
        try:
            from exocortex.colony import Colony
            from exocortex.endocrine import levers
            prune, cap = levers(SessionState.load(session).tier())   # read-only peek (no save → no race)
            # ADR-020 W3: consolidate is a cross-process RMW — discover the classes, then re-load and
            # sweep EACH under its own colony lock so a concurrent deposit isn't silently overwritten
            # (one class at a time; every colony lock released before the session flag-write below,
            # per the session-before-colony order law).
            for label in [c.label for c in Colony.all()]:
                with Colony.locked(label) as col:
                    col.consolidate(prune=prune, cap=cap)
                    col.save()
                consolidated += 1
            # BUG_SESSIONSTATE_RACE: lock only the flag write — not the whole consolidation sweep above
            with SessionState.locked(session) as st:
                st.resplice = True      # wake → re-inject the matching class's map on the next prompt
                st.save()
        except Exception:
            consolidated = 0            # fail open — never block compaction
    # Hippocampus bridge (Ticket 2; gated, dormant): sleep is when geometry PROPOSES provisional A→D edges
    # over the wiki's semantic phasors (numpy/MiniLM here is fine — off the per-tool hot path). It only
    # proposes; the live session walks them and a later exit-0 crystallizes / exit-1 scars.
    if bridge_enabled() and declarative_enabled():
        try:
            from exocortex.wiki.bridge import synthesize
            from exocortex.wiki.digest import encode_phasor
            from exocortex.wiki.store import load_graph
            graph = load_graph(declarative_vault())
            if graph is not None and graph.nodes:
                graph.build_phasor_bank(encode_phasor)   # materialize semantic phasors (sleep only)
                synthesize(graph, stamp=session)
        except Exception:
            pass                        # fail open — bridge synthesis must never block compaction
    audit.append(audit.record(session=session, event="PreCompact", mode=m.value,
                              injected=bool(consolidated)))
    return None                         # PreCompact additionalContext is ignored by the harness


def handle_sessionstart(data: dict, m: Mode):
    session = str(data.get("session_id", "session"))
    # Cryptographic immune system (ADR-009; gated, dormant): before accepting a token, verify the frozen DNA
    # (somatic organs + Φ⁶/HDC kernel) against the committed baseline. enforce → apoptosis (fail-closed
    # exit 1) on a mismatch — death over mutated DNA; warn → record it and continue.
    if integrity_mode() != "off":
        try:
            from exocortex.integrity import verify_kernel
            r = verify_kernel()
            if not r["ok"]:
                enforce = integrity_mode() == "enforce"
                audit.append(audit.record(
                    session=session, event="IntegrityViolation", mode=m.value,
                    action=("apoptosis" if enforce else "warn"),
                    reason=("kernel-lock mismatch: "
                            f"mismatched={r.get('mismatched', [])[:5]} missing={r.get('missing', [])[:3]} "
                            f"{r.get('reason', '')}")))
                if enforce:
                    sys.exit(1)             # apoptosis — refuse to operate on mutated DNA
        except SystemExit:
            raise
        except Exception:
            pass                            # a verify *error* must not brick startup (only a verified mismatch does)
    st = SessionState(session_id=session)   # fresh session → full energy
    st.resplice = True                       # splice the colony's procedural memory on the first prompt
    st.save()
    audit.append(audit.record(session=session, event="SessionStart", mode=m.value,
                              energy=st.energy, tier=st.tier()))
    return _vitals(m)


def _vitals(m: Mode) -> dict | None:
    """The one line that answers "is this thing on?" — the organism's ONLY channel to the human.

    Every other output we emit is model-facing: `additionalContext` goes to the model (verified), and
    `permissionDecisionReason` is rendered only on deny/ask — on allow it is discarded. So the sole
    user-visible event was a refusal, at a MEASURED veto_rate of 0.0009 (1 per 1115 tool calls). A
    working install and a broken install therefore produced identical observations — and the docs sold
    that silence as correctness. This is the fix: speak once per session, on an earned fact.

    Deliberately NOT chatty (PI 2026-07-16: "rare + earned, default ON"). No agent-behavior change, no
    tau, no ADR-001 exposure — this only changes what the HUMAN sees. Never raises: vitals are a
    courtesy, and the hook's fail-open outranks them.

    `systemMessage` is a TOP-LEVEL key (sibling of hookSpecificOutput). Empirically on 2.1.211: accepted
    (outcome=success, no stderr) and NOT delivered to the model (planted-token capture — the control
    token in additionalContext was echoed back by the model; this one never was). User-side RENDERING is
    doc-claimed and unverifiable headlessly (`-p` has no UI); if it turns out inert, this degrades to a
    no-op and the voice belongs in the `sentaince status` CLI instead.
    """
    try:
        bits = [f"mode={m.value}"]
        try:
            from exocortex.colony import Colony
            n = sum(len(Colony.load(p.stem.replace("colony_", "", 1)).tau)
                    for p in state_dir().glob("colony_*.json"))
            bits.append(f"{n} routes earned" if n else "no routes yet — earning starts on your first exit 0")
        except Exception:
            pass
        if integrity_mode() != "off":
            bits.append(f"integrity={integrity_mode()}")
        return {"systemMessage": "🧬 sentaince: " + " · ".join(bits)}
    except Exception:
        return None                          # a courtesy must never wedge a session


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else ""
    # CLI overrides (Claude Code does NOT forward arbitrary parent env to hooks, so the runner bakes
    # these into the per-run settings.json command rather than relying on EXOCORTEX_* env vars).
    argv = sys.argv[2:]
    for flag, var in (("--mode", "EXOCORTEX_MODE"), ("--audit", "EXOCORTEX_AUDIT"),
                      ("--state", "EXOCORTEX_STATE_DIR"), ("--colony", "EXOCORTEX_COLONY"),
                      ("--provider", "EXOCORTEX_PROVIDER")):
        if flag in argv:
            try:
                os.environ[var] = argv[argv.index(flag) + 1]
            except IndexError:
                pass
    from exocortex import adapter   # provider I/O shim — the Claude path passes through unchanged
    raw = sys.stdin.read()
    data = adapter.read_payload(raw)            # BOM-safe parse (Cursor sends UTF-8 with a BOM)
    prov = adapter.detect(os.environ.get("EXOCORTEX_PROVIDER", ""), data)
    if prov == "cursor":
        event, data = adapter.normalize_in(data, event)   # camelCase event + key/tool/tool_output mapping
        _m = adapter.model_id(data)                        # F3 provenance straight from the payload
        if _m:
            os.environ["EXOCORTEX_MODEL"] = _m
    m = mode()
    out = None
    try:
        if event == "PreToolUse":
            out = handle_pretooluse(data, m)
        elif event == "PostToolUse":
            _oc = adapter.outcome(data) if prov == "cursor" else classify_outcome(data)
            out = handle_consequence(data, m, _oc)  # may be a masked failure (Claude heuristic path)
        elif event == "PostToolUseFailure":
            out = handle_consequence(data, m, "fail")
        elif event == "UserPromptSubmit":
            out = handle_userpromptsubmit(data, m)
        elif event == "PreCompact":
            out = handle_precompact(data, m)
        elif event == "SessionStart":
            out = handle_sessionstart(data, m)
    except Exception:
        out = None  # fail open — never crash the agent
    exit_code = 0
    if prov == "cursor":
        out, exit_code = adapter.serialize_out(out)   # flat keys; a hard veto = deny + exit 2
    if out is not None:
        sys.stdout.write(json.dumps(out))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
