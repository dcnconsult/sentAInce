# Outcome signatures v1: widening `classify_outcome` (R1c)

**Date:** 2026-09-16. **Change:** `exocortex/hook.py` `_EXITCODE_RE`, `_FAIL_MARKERS` and the new `_FAIL_RX`.
**Why:** memory red-team gap `rt-tool-1`. When an agent masks a command's exit code (`|| true`,
`; echo "exit: $?"`), the Bash tool exits 0 and the hook must judge the outcome from stdout/stderr alone.
The old signature list read 8 common failure shapes as success, and a success read earns τ.

## Newly caught (each is a red-team item that now passes)
- lowercase `exit code 1`
- `exit status 2` / `returned non-zero exit status 2`
- pytest summary `1 failed, 3 passed in`
- `npm ERR!`
- `make: *** [all] Error 2`
- `error:` at line start (git, cargo, gcc)
- `Permission denied`, except on `warning:` lines
- a bare exception line such as `ModuleNotFoundError: …`

**Still not caught, by construction:** a fully silenced command (`2>/dev/null || true`) has no output to
read. That is R1a (inspecting the command text), and it stays pinned as a strict xfail.

## Replay before shipping (read-only)
The replay re-classifies the stored 240-character output snippet of every recorded `ok` consequence
([`replay.py`](replay.py)).

| Store | Recorded `ok` | Now `fail` | Share |
|---|---|---|---|
| this repo | 3,249 | 17 | 0.52% |
| research-vault | 3,422 | 11 | 0.32% |

**How the two rules were tuned before landing** (on a first replay):
- **`Permission denied`:** the unrestricted version flipped 15 successful commands whose only match was
  git's benign `warning: could not open directory … Permission denied`. Those lines are now excluded.
- **Test-summary rule:** the loose version matched prose (`mo=1 errors (expect none)`). It now requires
  pytest's `N failed,` / `N failed in` shape.

**Reading of the final flips:** every flip whose matched text appears in the printed preview is genuine
failure output: a failing test, `error: pathspec`, a rejected push, a `SyntaxError`, a refused file write,
a failed Ollama call. Three previews end before the match, so those three were not checked by eye.

**Known conservative false positive:** prose containing `exit code 1` now reads as `fail`. A false
positive only **withholds** τ; it can never grant any.

**Scope.** Snippets are truncated at 240 characters, so these shares are lower bounds on how often the
widened rules fire. The replay measures classification only; it does not measure how often masked
failures occur in live sessions (that is R1a's gauge).

**Verdict:** +1 · kind: experimental-design · 8 red-team signatures close, at a replayed flip rate of about
0.5% with no benign flip observed after tuning · −1 if a later replay shows benign flips above 0.5% of
recorded `ok`.
