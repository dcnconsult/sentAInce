# Bridge-validity gauge — Ticket 2's gate (§3B / §6C)

Run BEFORE writing any Hippocampus-bridge code, to answer: does HDC geometry synthesize VALID shortcut
edges `A→D` over the colony's transition memory? `exocortex/gauge/bridge_gauge.py`, live colony
(`.claude/exocortex`, 16 classes; numbers drift as the live soak deposits — `live_colony.json` is a snapshot).

## [1] Payoff ceiling — is there anything to shortcut?
Topological simple-path lengths (edges→count): `{1:~141, 2:~166, 3:~152, 4:~155, 5:~156, 6:~146}` —
≥2 edges **85%**, ≥3 edges **66%**, 13/16 classes have a ≥3-edge route, ~152 bridge candidates.

**CAVEAT (load-bearing):** these are *topological* simple paths, **inflated by graph cycles** (recurring
verb-nodes like `Edit:src`, `bash:cd` create long wandering paths). The real prize cap is the
**deposit-window segment length — median 2, cross-model** (eligibility_gauge `seg_len`). A bridge over a
cyclic graph path is not a meaningful route. So the topological richness OVERSTATES the prize; the genuine
shortcuttable-route population is small.

## [2] HDC geometric fidelity — does the chord land on a real route?
- **1-hop recall fidelity: 1.0** — the vendored `phase_router` (random Z3 codebook, M=2048) faithfully
  recalls stored transitions at this scale (T≪capacity).
- **2-hop chord precision: ~0.96** raw → **1.0 after the 0-well abstain** (conf ≥ 0.10). The
  `epistemic_gate`-style confidence floor culls the low-confidence chords (conf_median ~0.12, near the
  floor) and lifts precision to 1.0. **The abstain gate earns its keep.**

## Verdict (stats-only → the build gate)
The bridge *mechanism* is sound at this scale: the HDC router recalls routes faithfully and the 0-well
abstain cleanly removes false chords (0.96→1.0). **But two limits keep autonomous synthesis off the table:**
1. **Recall ≠ generalization.** With a random codebook the router RECOVERS stored transitions; it does not
   invent novel bridges. Real geometric generalization needs *semantic* node vectors (the declarative
   wiki's phasors) — untested here, and a different experiment.
2. **Executable validity is not offline-decidable.** That a real path `A→…→D` exists says nothing about
   whether the *direct* `A→D` works — the skipped steps may be necessary (Edit before test). Only walking
   it with the body settles that. Plus the prize is capped by the median-2 deposit-window reality.

**Decision:** if Ticket 2 is built, build ONLY the **consequence-preserving suggest-then-verify** form
(§3B option A): geometry proposes a *provisional* `A→D`, gated by the 0-well abstain (proven to raise
precision to 1.0); the **body walks it**; `exit 0` crystallizes (τ), `exit 1` scars (σ). **NEVER autonomous
crystallization.** And size it against the small genuine-route population, not the inflated topological count.
This is exactly what §3B/§6C predicted, now quantified.
