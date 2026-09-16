# Pre-registration: working-verb keying (R0 / DQ-1) — does it keep the consequence law's discrimination?

**Frozen:** 2026-09-16, committed before the gauge is written or run. **Kind:** experimental-design.
**Gauge:** `exocortex/gauge/verb_keying_gauge.py` (read-only over an audit JSONL, stdlib).

## 1. Question

The live colony keys a Bash action by its **first token** (`colony._bash_verb`). For compound commands
that token is often navigation or an environment assignment, so `cd repo && pytest -q` becomes
`bash:cd` and `PYTHONIOENCODING=utf-8 python x.py` becomes `bash:PYTHONIOENCODING=utf-8`.

The alternative is a **working-verb** keying (defined in §3). Does it preserve or improve the
discrimination the consequence law relies on, while removing the navigation/env keys?

## 2. What has already been seen (disclosed before freezing)

A scratch replay on 2026-09-16 counted, over depositing `PostToolUse ok` consequences:

| Measure | SentAInce (n=3,207) | research-vault (n=3,407) |
|---|---|---|
| Command starts with `cd … &&` / `;` / `\|\|` | 31.1% | 47.1% |
| Command starts with `VAR=val` | 9.4% | 9.3% |

**Not yet computed for either keying:** clutter, pass/fail edge overlap, and the node/edge counts below.

## 3. The two keyings (frozen)

Both apply to Bash (and PowerShell) command text. File tools stay `Tool:src|test|other` in both.

- **first:** exactly `exocortex.colony._bash_verb`, the shipped behavior.
- **working:**
  1. Split the command on the top-level separators `&&`, `||` and `;`, and take the segments in order.
  2. Within a segment, keep only the part before the first `|`.
  3. Strip leading `VAR=val` tokens.
  4. Strip leading wrappers: `sudo`, `time`, `nohup`, `env`, `command`, `exec`, and `timeout <n>`.
  5. Take the basename of the next token, with shell punctuation stripped as in `_bash_verb`.
  6. Skip any segment whose verb is navigation or session setup: `cd`, `pushd`, `popd`, `export`, `set`,
     `source`, `.`, `unset`, `shopt`, `setopt`.
  7. The key is the first non-skipped segment's verb. If every segment is skipped, the key is the first
     segment's verb, so `cd x` alone stays `bash:cd`.

## 4. Replay model (frozen)

- **Segmentation:** per session, in file order.
  - `UserPromptSubmit` resets the trail to `[cue:<class>]`, where the class comes from the record's
    `reason` field (`class=<label>`).
  - `PreToolUse` appends the node.
  - `PostToolUse` or `PostToolUseFailure` closes the segment, labelled with its `outcome`
    (`ok` / `fail`), and its edges are recorded.
  - After `ok` the trail re-roots to `[cue, node(cmd)]`; after `fail` it re-roots to `[cue]`, mirroring
    `hook.handle_consequence`.
  - Self-edges are dropped (W5).
- **Colony:** the mirror colony `exocortex.gauge.analyze._Colony` (DECAY 0.9, PRUNE 1e-3), one per class,
  under two policies:
  - **consequence:** deposit only `ok` segments;
  - **frequency:** deposit every segment (the clutter null).
- **Metrics, per keying, per repo:**
  - **M1 `nav_env_share`:** share of `ok`-segment edges with an endpoint that is a navigation or env key
    (`bash:cd`, `bash:pushd`, `bash:popd`, `bash:export`, `bash:set`, `bash:source`, or any key containing
    `=`).
  - **M2 `frequency_clutter`:** fraction of the frequency-policy memory that is fail-only, i.e. edges seen
    in `fail` segments and never in `ok` segments. Higher means the law has more to discriminate. The
    consequence-policy clutter is 0 by construction and is reported only as a check.
  - **M3 `pass_fail_jaccard`:** Jaccard overlap between the ok-edge set and the fail-edge set. Lower means
    success and failure routes are more separable.
  - **M4, descriptive only:** distinct nodes, distinct edges, and per-class entropy of the consequence
    colony.

## 5. Decision rule (frozen)

Tolerance ε = 0.02, absolute.

- **+1 (build R0 behind a knob):** on **both** repos, all three hold:
  - (a) M1 under working ≤ 0.5 × M1 under first;
  - (b) M2 working ≥ M2 first − ε;
  - (c) M3 working ≤ M3 first + ε.
- **−1 (first-token keying is accidentally load-bearing; document it, don't "fix" it):** (b) or (c) fails
  on **both** repos.
- **0:** anything else, such as a mixed result across repos, or (a) failing. Report it and do not build.
- The consequence-policy clutter must be 0 under both keyings. If it is not, the replay is wrong and
  the run is void.

## 6. What this cannot show

- It shows whether the keying **keeps the discrimination signal on recorded traffic**.
- It does not show that working-verb routes help an agent reach `exit 0` (efficacy stays unmeasured, as
  in CLAIMS).
- It does not re-run the scripted-stream result behind the PROVEN 0%/24% row. That result is structural
  under the consequence policy, and its frequency arm used a single-command stream.

## 7. Output

`results/verb_keying_v1/RESULTS.md` plus an aggregate-only JSON. It contains no command text, and the
second repo is labelled `research-vault`.
