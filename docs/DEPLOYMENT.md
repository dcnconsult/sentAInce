# FreqOS / SentAInce — Packaging & Deployment

The tiered deployment roadmap. The governing principle ([ADR-009](ADR.md)): **language is not a tamper
boundary** — tamper-resistance is a layered set of mathematical/physical invariants (verify · sign ·
isolate · tamper-evident), not a compiled binary. We do not pay the ATP cost of a heavier tier until the
physical environment demands it.

## The tiers
| Tier | Artifact | When | Tamper posture |
|---|---|---|---|
| **T1 — pip wheel** | `sentaince` package (hatchling; `pip`/`pipx`) + the Claude Code **or Cursor** hook wiring (`--provider`) | dev · personal · the live soak | source-visible; integrity via the **layer below** (kernel-lock verify + hash-chained audit) |
| **T2 — Nuitka binary** | one compiled executable (Python→C→native), keeps the numpy kernel | a single artifact / IP packaging is demanded | obfuscation + single-file; **a convenience, not a security control** |
| **T3 — container image** | the control plane + the hardened RPC body (no Docker socket, read-only system FS) | isolated / multi-tenant / strongest posture | **physical immutability** of declared invariants — the only *complete* guarantee |
| **T4 — standalone MCP daemon** | a long-running signed, sandboxed service usable by any agent host (the "graduation") | enterprise / external service | Rust shell over the FFI-bound math kernel; remote attestation + `seccomp` |

The current shipping reality is **T1** (the hook control plane — Claude Code or Cursor via `--provider`), with
**T3** already proven for the body (the battle-test container). T2 and T4 are on-demand.

> **Tiers vs entry points.** T1–T4 are *packaging* tiers. The organism's two entry points — the hooks
> (earn + enforce) and the read-only [memory MCP server](MCP_SERVER.md) (retrieve/consume) — are
> orthogonal to them: every tier can carry both.

## T1 — pip wheel (current)
```bash
pip install -e .            # or: pipx install sentaince  (once published)
# wire the hooks (Claude Code → .claude/settings.json, Cursor → .cursor/hooks.json):
python -m exocortex.deploy install <project> [--provider claude|cursor|both]   # or hand-write (USER_GUIDE.md §2)
```
Genome config via `exocortex_config.json` (search order + every knob in [OPERATIONS.md](OPERATIONS.md)).
This is the right tier for the live soak and single-developer use. Integrity is provided by the
language-agnostic layer ([ADR-009](ADR.md)): startup kernel-lock verification + the hash-chained audit.

## T2 — Nuitka single binary (on demand)
Reach for this **only** if a single executable is required for distribution or casual IP protection — never
as a security boundary.
```bash
python -m nuitka --standalone --onefile exocortex/hook.py      # compiles C-bindings of the numpy physics
```
Nuitka compiles to C/native **without re-implementing the verified kernel** (so the lock holds). Sign the
artifact; ship the kernel-lock baseline + the audit-chain alongside. ~5% of a Rust rewrite's cost.

## T3 — container image (isolation)
The strongest tamper posture, already proven for the body (`battle/`, see
[battle_test/WHITEPAPER.md](battle_test/WHITEPAPER.md)): the organism holds **no Docker socket**, the system
FS is **read-only**, and declared invariants are **physically immutable** — the conclusion of the battle-test
is that this physical immutability is the *only complete* guarantee; the symbolic oracle and dry-run are
partial. Package the control plane the same way; mount the Genome + baseline read-only.

## T4 — standalone MCP daemon (the graduation; Rust horizon)
The clean long-term shape: move from in-process hooks to a long-running
service any compliant agent host can call. This — and **only** this — is where a Rust rewrite is justified:
a memory-safe, signable, `seccomp`-sandboxable daemon for the numpy-free control plane (somatic gate +
colony + audit). The **frozen mathematical kernel stays Python/numpy** (or a separately re-verified port)
behind an FFI boundary — reimplementing it would shatter the lock and demand re-verification. This is a
deliberate v2 architecture decision triggered by a deployment requirement, decided gauge-first — not a
tamper band-aid.

## The integrity layer (ships across all tiers — `exocortex/integrity.py`)
Language-agnostic, dormant by default (`integrity.mode = off`; `warn` / `enforce` opt-in):
- **Startup kernel-lock verification (apoptosis)** — hash the frozen DNA (somatic organs + Φ⁶/HDC kernel)
  against the committed baseline; `enforce` → fail-closed `exit 1` on mismatch. *Death over mutated DNA.*
- **Hash-chained audit (epigenetic ledger)** — `hash_N = SHA256(payload_N ‖ hash_{N-1})`; any silent edit to
  a past decision snaps the chain. Fail-open on write, tamper-evident on read.

See [OPERATIONS.md](OPERATIONS.md) for enabling these, and [SECURITY.md](SECURITY.md) for the threat model.
