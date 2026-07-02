# `release/` — the community/commercial boundary (ADR-011)

This directory is the **single source of truth** for what ships to the public, Apache-2.0 **community
repo**. The boundary is *data* (`manifest.py`) enforced by *fail-closed gates* (`prepush_gates.py`), and the
public repo is **derived** deterministically from the private monorepo — not scrubbed by hand. See
[docs/ADR.md](../docs/ADR.md) ADR-011 and [docs/PRODUCT.md](../docs/PRODUCT.md).

## The boundary in one screen
- **Community (open, Apache-2.0):** the whole local **body** — immune kernel (`sentaince/`, `vendor/kernel/`),
  the C1–C7 evidence lock (`experiments/`, `tests/`), the exocortex host (colony, audit, MCP server, deploy,
  integrity, gauges), the **read-only** Cerebral Substrate slices (`cerebral/`), battle/demos/docker, and the
  gauge `results/`. *Never paywall safety* — the brake is free by **license**, not just by promise.
- **Commercial (held out):** `exocortex/tuner/` — the deterministic **policy table** (the honest moat), the
  emulator, the client↔Tuner protocol; plus the future actuator (S3), Consolidator daemon, cross-repo
  Alliance analytics, and the hosted service. *Sell the autopilot, never the brakes.*
- **Never public:** `patent/`, investor materials, the private denylist tokens (`denylist_private.py`),
  and any **private-crucible** content (the private patent vault, the quantum repo). Move the line only by
  editing `manifest.py`.

## Commands
```bash
python -m release.build_public                 # dry-run: what ships + the gate verdict (no writes)
python -m release.build_public --json          # machine-readable manifest + gates
python -m release.build_public --out ../SentAInce-public   # materialize the public tree (only if gates pass)
python -m release.prepush_gates                # (via build_public) the fail-closed checks
python cerebral/../release/tests/test_release.py            # or: python -m pytest release/tests
```

## The gates (all must PASS before any push — fail-closed)
1. **`patent_filed`** — the hard gate. Cleared only by a committed `release/PROVISIONALS_FILED` marker.
   **Code is disclosure**; nothing is published until the provisionals are filed.
2. **`no_commercial_or_private`** — the public set contains nothing under the commercial/never-public lists.
3. **`no_denylisted_tokens`** — no private-crucible names / patent ids / maintainer PII / absolute dev
   paths (identifying tokens live in the never-public `denylist_private.py`; generic ones in `manifest.py`).
4. **`no_secrets`** — no keys/PEM/PATs.
5. **`license_present`** — the Apache-2.0 `LICENSE` ships.

## Known work before the first push (the gates will keep failing until done)
- [ ] **File the provisionals**, then add `release/PROVISIONALS_FILED`. *(The #1 gate — everything waits on it.)*
- [x] **Scrub the private-crucible tokens from the public tree.** Done 2026-07-01: prose anonymized to
      `research-vault`, raw gauge labels excluded (never-public), machine paths genericized, and the
      public set now derives from git-TRACKED files only.
- [x] **Copyright holder confirmed** in `LICENSE` (`SentAInce / FreqOS authors`, pseudonymous by choice) + `NOTICE` added.
- [x] `CONTRIBUTING.md` added; top-level `README` reviewed for the public tree.
- [ ] (Optional) SPDX headers pass across source — a mechanical follow-up; the root `LICENSE` already covers it.

## First-push procedure (squashed history — no leak)
1. `python -m release.build_public --out ../SentAInce-public` (only succeeds once all gates pass).
2. In the derived tree: `git init && git add -A && git commit -m "Initial public release vX.Y.Z"`.
3. Create the empty public GitHub repo, `git remote add origin …`, `git push -u origin main`.
   The private monorepo's history (with `patent/` etc.) is **never** pushed.
