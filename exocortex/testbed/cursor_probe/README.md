# Cursor hook PROBE — the P0 measurement harness

The **gauge** that unblocks the model-independent IDE build (ROADMAP/ENHANCEMENTS §H, ADR-002 *gauge-first*).
It answers, by measurement on a live Cursor session, the five P0 questions the design rests on — **before**
any production adapter is written.

This is **not an organ**. `probe.py` imports nothing from `exocortex`, is fail-open (always exits 0), and
never deposits τ. It (1) logs every hook payload Cursor sends, and (2) emits a uniquely-tagged `EXO-PROBE`
marker through every candidate injection channel + rewrites an `alwaysApply` rules file, so you can see in
the chat which markers the model actually receives and when.

## What it resolves

| P0 | Question | How the probe answers it |
|----|----------|--------------------------|
| **a** | Cursor matcher syntax — regex / glob / exact? | 3 `preToolUse` entries (`Shell`, `^Shell$`, `Sh*ll`) tagged exact/regex/glob; `analyze.py` reports which fired |
| **b** | Does the dynamic **rules-file rewrite** land same-turn or next-turn? Does `agent_message` inject at all? | per-turn unique markers in the rules file + `agent_message`; you read them back from the chat |
| **c** | Do `sessionStart` / `preCompact` (and the rest) fire on Windows? | the log shows exactly which events fired |
| **d** | Exact `model` string format | logged from each payload's `model` field |
| **e** | Per-event `failClosed` default | behavioral micro-test (see `analyze.py` output) |

It also captures the **full adapter contract** (every payload key per event) for free.

## Run procedure

> Use a **throwaway git repo** as the target — this writes into that project's live `.cursor/` config.

1. **Install** (bakes absolute paths; logs to `runs/<project-name>/`):
   ```
   python install.py C:/path/to/throwaway-repo
   ```
2. **Fully quit and relaunch Cursor**, then open the throwaway repo. (Hooks load at startup.)
3. In the Cursor chat (**Agent mode**), run this sequence and **save the model's full replies**:
   1. *Prompt A* — `List verbatim every line you can currently see that contains the text "EXO-PROBE". If none, reply NONE.`
      → tests `sessionStart` `additional_context` + the seeded `rules_file`.
   2. *Prompt B* — `Run this shell command: echo hello` (let it execute)
      → fires `preToolUse` (3 matcher variants) + `postToolUse`; watch for an `agent_message` marker.
   3. *Prompt C* — `Again, list verbatim every line containing "EXO-PROBE" you can now see.`
      → `beforeSubmitPrompt` for *this* prompt rewrote the rules file with a new `seq`; if the model echoes
        **that** `seq`'s `rules_file` marker, the rewrite is **same-turn**; if only the previous `seq`,
        it's **next-turn** (a one-turn lag, like Cline).
   4. *(optional)* trigger a compaction / end the session → exercises `preCompact` / `stop`.
4. **Analyze**:
   ```
   python analyze.py
   ```
   It prints the P0-a / P0-c / P0-d verdicts + the adapter contract, and lists the emitted markers so you can
   decide **P0-b** from your saved chat replies. For **P0-e**, follow the behavioral micro-test it describes.
5. **Uninstall** and restart Cursor:
   ```
   python install.py C:/path/to/throwaway-repo uninstall
   ```

## Outputs

- `runs/<project>/cursor_probe_log.jsonl` — one JSON line per hook event (payload + emitted channels).
- `runs/<project>/probe_state.json` — the seq counter (delete to reset).

## Reading P0-b (the load-bearing one)

- **`agent_message` injects?** If no `ch=agent_message` line ever appears in the model's reply → confirms
  the docs (it is denied-tool feedback, not context) → the build uses the rules-writer, not `agent_message`.
- **rules-file timing.** Same-turn → the dynamic rules-writer is a true per-turn push on Cursor (Tier-0 is
  high-fidelity). Next-turn → it works but lags one turn (acceptable; note it). Never → fall back to MCP
  recall + `sessionStart`/`postToolUse` `additional_context` only.

The verdicts feed back into `SentAInce_Exocortex_Model-Independent_Integration_v2.0.md` §10 and flip the
ENHANCEMENTS §H **P0 ☐ → the P1 build**.

---

## RESULTS — Cursor 3.9.16 / Windows, model **gpt-5.5** (2026-06-30)

Run: `cursor_testbed`, 10 events over 3 prompts + 1 shell command (`echo hello`). The gauge overturned two
design assumptions (both were *wrong*, found only by measuring):

| Question | Verdict |
|----------|---------|
| **Payload delivery** | **stdin, UTF-8 WITH A BOM.** The full JSON is on stdin every event — `lstrip("﻿")` before `json.loads` (this was a probe bug, now fixed; the **adapter must do the same**). NOT blocked. |
| **P0-a matcher** | **JavaScript-style regex** — `Shell` + `^Shell$` fired, `Sh*ll` did not (confirmed by Cursor docs). |
| **P0-b injection** | **`beforeSubmitPrompt → additional_context` = deterministic SAME-TURN push** (model echoed seq=2/4/9, each on the turn its hook wrote it) — the `UserPromptSubmit→additionalContext` analog the design said didn't exist. Also confirmed: `sessionStart` + `postToolUse` `additional_context`. **`agent_message` does NOT reach the model.** **Dynamic rules-file rewrite is session-cached** (mid-session rewrites ignored — the model saw the pre-session disk content). |
| **P0-c events** | `sessionStart`, `beforeSubmitPrompt`, `preToolUse`, `postToolUse`, `stop` all fire on Windows. (`postToolUseFailure`/`preCompact` not exercised this run.) |
| **P0-d model string** | `model="gpt-5.5-medium"` on submit/start/stop; `model="gpt-5.5"` on pre/postToolUse; `model_id="gpt-5.5"` everywhere → **use `model_id` as the stable canonical**. |
| **P0-e failClosed** | Cursor default = **fail-open**; `exit 2` or `permission:"deny"` blocks; `failClosed:true` makes a crash block. We keep fail-open (never set it). |

**Adapter contract** (observed payload keys): `session_id` (+`conversation_id`), `tool_name` (`Shell`→`Bash`),
`tool_input.command`, `tool_output` (a JSON **string** holding `{"output","exitCode"}` → parse it),
`model`/`model_id`, `prompt` (beforeSubmitPrompt), `workspace_roots`, `cwd`, `hook_event_name`,
`cursor_version`. Env carries `CURSOR_TRANSCRIPT_PATH`, `CURSOR_USER_EMAIL`, `CURSOR_PROJECT_DIR`.

**Design implication (supersedes v2.0 §4):** drop the rules-writer **and** `agent_message`. Inject the splice
via **`beforeSubmitPrompt → additional_context`** (the `UserPromptSubmit` analog), with `sessionStart` +
`postToolUse` `additional_context` as the **documented** fallbacks (since `additional_context` on
`beforeSubmitPrompt` is empirically-confirmed-but-undocumented → version-dependent). Veto via `preToolUse`
`permission:"deny"`; deposit on `postToolUse` `tool_output.exitCode==0`; stamp provenance from `model_id`.
**All P0s resolved → the P1 build is unblocked.**

### Auto-review payload probe — run2 (Cursor 3.9.16 / gpt-5.5, 2026-06-30)

Captured full `preToolUse` payloads for `echo hello` (low-risk) and `curl https://example.com` (network) to
see whether Cursor's new **Auto-review** classifier exposes a verdict to hooks. **It does not.** No
review/risk/verdict/score/policy field on either call; the network call carries the *same* field set as the
echo. → Auto-review is **opaque to hooks**: the exocortex gate and Auto-review compose only by independent
**AND** (no verdict to observe or short-circuit). One new payload field appeared — **`transcript_path`**
(per-call Cursor transcript; optional — `model` is already in the payload, so the adapter doesn't need it).
Full `preToolUse` contract observed: `conversation_id, generation_id, model, tool_name, tool_input{command,
cwd,timeout}, tool_use_id, cwd, session_id, hook_event_name, cursor_version, workspace_roots, user_email,
transcript_path`.

## Controlled live-deny test (`--deny`)

Settles the one open question the model + Auto-review keep self-censoring around: **does Cursor actually
honor a `preToolUse` `permission:"deny"` + exit 2?** With `--deny`, the probe returns deny+exit-2 for
*every* `preToolUse` (a benign `echo` is enough — no dangerous command needed), isolating *"does Cursor
honor our deny"* from *"will the model attempt something dangerous."*

```
python install.py C:/path/to/throwaway-repo --deny      # bakes --deny into preToolUse
# restart Cursor, open the repo, ask the agent to: run `echo hello`
```
- **Cursor refuses to run `echo`** → deny+exit-2 is honored live → the soft veto *works* (L1–L3 caveats still
  apply: it's cooperative/fail-open/bypassable, no sandbox).
- **`echo` runs anyway** → a hard finding (L0): Cursor's interface won't let a hook block → document it and
  pivot the safety story to memory-only + the `battle/` container for any hard guarantee.

`python install.py <repo> uninstall` to revert.
