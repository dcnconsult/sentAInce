# Pre-registration: read-time validity (avenue 3 / R4b) — does served memory cite artifacts that no longer exist?

**Frozen:** 2026-10-26, committed before the gauge is written or run. **Kind:** experimental-design.
**Gauge:** `exocortex/gauge/read_time_validity_gauge.py` (read-only snapshot over state dirs, the vault and
`git log`; stdlib).

## 1. Question

The landscape scan (2026-10-26) found one competitor re-validating a memory's code citations against the
current branch before using it. Our memory serves two lanes, and they can go stale in different ways:

- **Procedural splice.** Nodes are verb-altitude (`bash:make`, `Edit:src`) and carry no paths. A route can
  only reference an artifact through a verb that implies one:
  - a **manifest verb** (`make` needs a Makefile, `npm` needs `package.json`);
  - a **script verb** (`./run.sh` is keyed `bash:run.sh`).

  Red-team `rt-stale-2` pins this gap. R4b is parked "until a gauge shows spliced routes referencing
  vanished artifacts".
- **Declarative splice.** Notes are blocks of the repo's own Markdown, served either τ-verified (exploit) or
  flagged UNVERIFIED (explore). Content identity already invalidates an edited or deleted block, because
  its id leaves the digest. What it cannot catch is an **unchanged** block whose cited path has since
  vanished.

**Question:** read now, what share of what memory would serve cites at least one repo artifact that once
existed and no longer does? A read-time check, one that flags or withholds the note, is worth designing only
if that share is non-trivial **and** the check is precise.

## 2. What has already been seen (disclosed before freezing)

Population counts were taken for evaluability only. **No existence check has been run.**

- **Procedural.** Across the 8 stores, 1 servable class (lab) carries any artifact-bound verb node: one
  script verb, and no manifest verbs at all. Lane P is therefore a **census** and cannot move the
  disposition.
- **Declarative.** Notes are served only where τ-credited notes exist or `explore_budget > 0`. That holds
  for two stores:
  - **this repo:** 61 credited note ids, explore budget 5, an offer ledger of 95 docs / 1,782 offers;
  - **brAIn:** 16 credited note ids, explore budget 5, a ledger of 107 docs / 503 offers.

  lab, B0 and the research vault run the organ live but serve nothing today: they have 0 credited notes
  and explore is off by default. lab's 12-doc ledger is left over from an earlier explore setting. All
  three are **excluded** from the declarative lanes.
- **Orientation:** brAIn, lab and B0 grade HIGH. The research vault grades MEDIUM and enters only the Lane P
  census.

## 3. Definitions (frozen)

**Repo index (now):**
- *Current:* every file and directory under the repo root, walked while pruning `.git`, `.hg`, `.svn`,
  `node_modules`, `__pycache__`, virtualenvs and tool caches.
- *Ever-tracked:* every path in `git log --all --name-only` ∪ `git ls-files`, plus their parent
  directories.

**Citation extraction** from a note block's text:
- **Sources:** each whitespace token of a single-backtick span; Markdown link targets `](…)`; and
  `-m <dotted.module>`.
- **Normalize:**
  - strip quotes, brackets and trailing punctuation;
  - strip `#anchor`, `::nodeid`, `:LINE[-LINE]` and `#Lnn`;
  - strip a leading `./`.
- **Keep** a token if either:
  - it contains `/` and ends with a known extension or with `/`; or
  - it has no `/` and ends with a known extension.

  Known extensions: `py md json jsonl toml yaml yml txt sh ps1 bat cmd js mjs ts tsx html css csv ini
  cfg ipynb svg tex bib rs go c h cpp hpp sql xml`.
- **Drop:**
  - URLs (`://`);
  - absolute paths (`/…`, `~…`, a drive letter);
  - shell or environment tokens (`$`, `%`);
  - glob and meta characters (`* ? [ ] { } < > | =`);
  - `...` and `@`;
  - anything that resolves outside the repo.
- **Modules:** `-m a.b.c` gives two candidates, the file `a/b/c.py` and the package `a/b/c/`.

**Classification** of each citation:
- **present:** any of these exists now:
  - the path, resolved from the repo root or from the note's own doc directory;
  - a current file or directory equal to it or ending in `/` + it (suffix match);
  - for a bare filename, any current file with that basename.
- **vanished:** not present, but some ever-tracked path equals it or ends in `/` + it (for a bare filename,
  some ever-tracked basename).
- **unresolved:** neither. This covers generated or ignored files, examples and typos. Unresolved
  citations are reported and **never** counted as vanished.

Suffix matching and doc-relative resolution both push toward *present*, so the rule is conservative by
construction.

## 4. Populations and metrics (per declarative-serving store)

**Digest.** The vault is re-digested now, read-only: `_md_files` with the repo's own `ingest`/`exclude`,
then `_digest_vault`. No cache is ever written.

**D1, exploit (τ-verified).**
- *Population:* note ids whose summed incident raw τ is ≥ 0.05 in **any** class colony. 0.05 is the splice
  floor that `node_tau` applies to raw τ. Only ids present in today's digest count.
- *Orphans:* credited ids missing from the digest are reported separately. Content identity has already
  invalidated them.
- *V1:* the share of D1 notes with ≥1 vanished citation. *Secondary:* the τ-weighted share.

**D2, explore (served UNVERIFIED).**
- *Population:* docs in the offer ledger that are present in today's digest, weighted by offer count.
  Offered docs that have left the digest are counted separately (already invalid).
- *V2* = Σ_d offers_d · (vanished-citing blocks_d / blocks_d) / Σ_d offers_d. This is the expected share
  of served explore blocks that cite a vanished path, assuming the proposer picks uniformly among a doc's
  blocks.
- *U2:* the offer-weighted share of docs with any vanished-citing block. It is an upper bound on V2.

**Descriptive.**
- Citation counts by class (present / vanished / unresolved).
- **D0:** the share of all digest blocks that cite a vanished path.

**Lane P census (every store).**
- *Servable class:* ≥2 deposits and a non-empty τ.
- *Splice node set:* the nodes of the top 8 edges by readout τ, plus the dominant path. Readout τ uses
  recency decay with a 30-day half-life, evaluated now.
- *Artifact-bound node:* a manifest verb, or a script verb (a verb ending in a script extension).
  - Manifest verbs: `make` `npm` `npx` `yarn` `pnpm` `cargo` `go` `mvn` `gradle` `gradlew` `tox` `poetry`
    `just` `docker-compose` `terraform` `nox`.
- *Artifact presence:* same classification as above. A manifest verb's artifact is its manifest filename
  anywhere in the repo; a script verb's is its basename.

**τ-floor census (R4 follow-up).** The share of servable classes whose maximum readout τ is below 0.05:
the classes a readout floor would silence. Descriptive only.

## 5. Decision rule (frozen)

**Evaluability:**
- D1 is evaluable with ≥30 notes; D2 is evaluable with ≥30 offered docs present in the digest.
- A store **passes** if any of its evaluable populations has V ≥ 0.05.

**Precision control** (after the run, before the verdict):
- Sample up to 20 (block, citation) pairs per passing store from its vanished citations, with seed
  `20261026`, and hand-audit each one.
- **Genuine:** the block presents the path as a current location a reader would act on.
- **Not genuine:** a historical or narrative mention (removed, renamed, was, formerly, superseded), an
  example or placeholder, or an extraction error.
- **Q** = genuine / audited.
- The auditor is the agent running the gauge (disclosed). The audit sheet quotes note text, so it stays
  private.

**Disposition:**
- **+1** (design a read-time citation check for the declarative splice, and gauge that design before
  building): ≥2 passing stores **and** Q ≥ 0.70.
- **−1** (park the declarative half of R4b): ≥1 evaluable population exists, and **every** evaluable
  population has V < 0.01.
- **0:** anything else. This includes V ≥ 0.05 with Q < 0.70 (a naive check would be too noisy), and fewer
  than 2 evaluable stores.

Lane P and the τ-floor census cannot move the disposition. `rt-stale-2` stays a strict xfail whatever the
result: it pins a mechanism, not a prevalence.

## 6. What this cannot show

- **Snapshot only.**
  - A citation that vanished and later returned, or vanished after its note was last served, is not
    distinguished.
  - Exploit notes have no serving history, because the audit does not record which notes were injected.
- **V2's uniform-choice assumption is wrong in direction.** The proposer ranks by relevance, not uniformly.
- **The ledger is not a clean sample.** It forgets docs that graduate to τ, and it counts from when F2
  shipped rather than over a fixed window.
- **A vanished citation does not prove the note misleads.** Hence the precision control.
- **No efficacy.** Whether a flag changes outcomes needs the avenue-4 benchmark.

## 7. Output

`results/read_time_validity_v1/RESULTS.md` plus an aggregate-only JSON: store labels and numbers, with no
note text, paths or class labels.
