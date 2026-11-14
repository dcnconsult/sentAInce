# Read-time validity gauge v1: does served memory cite artifacts that no longer exist? (avenue 3 / R4b)

> **Public labels (2026-10-28).** Private estate repositories appear as `repo-A` … `repo-H`. This repo,
> `lab`, `research-vault` and `cursor_testbed` keep their usual public labels. Only the names changed: every
> number is as run, the mapping is the same across this run's result files, and the frozen pre-registration is
> untouched.

**Run:** 2026-10-26, under the frozen protocol [`PREREG.md`](PREREG.md), which was committed before the
gauge existed (`a1a46a9`).

**Gauge:** `exocortex/gauge/read_time_validity_gauge.py`. Its controls are in
`exocortex/tests/test_read_time_validity_gauge.py` (8 pass). They run against a real temporary git repo:
- a committed-then-deleted file must read *vanished*;
- a never-tracked path must read *unresolved* and must not be counted;
- the floor, pruning and serving rules are each pinned.

Eight deliberate breakages of the gauge were each caught by at least one test.

**Data:** a snapshot at epoch `1793036619` of the 8 estate stores, their working trees and their full git
history (`--all`). Aggregates are in [`results_2026-10-26.json`](results_2026-10-26.json).

## Results

### Declarative lanes (the two stores that serve notes)

| Store | D1 notes (orphans) | **V1** | D2 offered docs (gone) | **V2** | U2 | D0 blocks | D0 share | Citations: present / vanished / unresolved |
|---|---|---|---|---|---|---|---|---|
| this repo | **59** (5) | **0.0** | **94** (1) | **0.0** | 0.0 | 2,924 | 0.0 | 1,868 / **0** / 178 |
| repo-B | 16 (0) | 0.0 | **107** (0) | **0.0** | 0.0 | 14,229 | 0.0 | 943 / **0** / 144 |

Populations shown in **bold** are evaluable: ≥30 notes for D1, ≥30 offered docs for D2. repo-B's D1 is not.

**Orphans** are credited notes whose text is no longer in the digest. Content identity has already stopped
serving them: 5 of 64 credited ids in this repo.

### Procedural census and τ-floor census (all 8 stores)

| Store | Servable classes | With an artifact-bound node | Artifact | Classes a τ floor would silence |
|---|---|---|---|---|
| this repo | 36 | 0 | – | 25 (69%) |
| repo-B | 53 | 0 | – | 23 (43%) |
| lab | 91 | 1 | present | 63 (69%) |
| repo-A | 17 | 0 | – | 4 (24%) |
| repo-C | 25 | 0 | – | 16 (64%) |
| repo-E | 18 | 0 | – | 5 (28%) |
| repo-H | 17 | 0 | – | 3 (18%) |
| research-vault | 32 | 0 | – | 15 (47%) |

## Disposition (frozen rule, §5): **−1**

There are three evaluable populations, and V is **0.0** on every one, below the 0.01 null bar. No store
passes, so the precision audit is not triggered.

## Reading

**Nothing served cites a vanished file, because these repos almost never delete or rename files.** This
was checked against git directly, not only through the gauge:
- **this repo:** 514 commits, 1,109 paths ever tracked, **2 deleted** and **0 renames**;
- **repo-B:** 90 commits, 1,820 paths ever tracked, **0 deleted** and **0 renames**.

The conservative suffix rule is not what produced the zero. Counting by exact location finds the same 2
missing files.

Copilot-style validation of citations at read time guards against code churn. This estate's research
repositories are append-only in practice, so that guard would have nothing to catch here.

**The procedural half of R4b has no surface.** Of 289 servable classes, one carries a verb tied to a file,
and that file exists. At the verb level, a route never names the artifacts it used. That is the
abstraction `rt-stale-2` complains about, and here it is also why routes don't go stale this way. The test
stays a strict xfail: it pins a mechanism, not a prevalence.

**How fragile the −1 is (disclosed, not the frozen metric).** Citations that match no path, now or in
history, are *unresolved* and never counted.
- **Worst case:** if every unresolved citation were stale, explore stays under the build bar on both stores
  (V2 0.025 and 0.010). This repo's exploit lane, however, would reach V1 0.136 (8 of 59 notes).
- **Inspection of those 8 notes:** 7 cite something this rule cannot check from inside one repo:
  - a file outside the repo (2);
  - a build-output directory (1);
  - directories in another repo (2);
  - a contributor's proposed directory (1);
  - a git pathspec the extractor misread (1).
- **The 8th note** cites three helper scripts git never tracked. They may be stale. Counted, V1 would be
  1/59 = 0.017, which moves this population from the −1 band into 0. It stays far below the 0.05 build bar.

The substance does not change: a read-time citation check would almost never fire on what this estate serves.

**What the census adds:**
- **Cross-repo citations are the real blind spot.** repo-B's notes cite research-vault paths, and this
  repo's notes cite lab files. A per-repo check cannot validate either. If read-time validation is ever
  built, the case it has to handle is a citation into a sibling repo.
- **A τ floor at readout would be a large change, not a tweak.** Under the shipped recency decay, it would
  silence 18–69% of servable classes. That is a behaviour change whose value only an outcome measure can
  settle (avenue 4), not a prevalence gauge.

**Still true:**
- **This is a snapshot.** Exploit notes have no serving history, because the audit does not record which
  notes were injected.
- **The populations are small.** Only two stores serve notes today, and only three populations are
  evaluable.
- **Re-open the declarative half** on a repository that does churn: deletions and renames at a real rate,
  such as the external benchmark repos of avenue 4. There, the same gauge can be re-run unchanged.

**Verdict:** −1 · kind: experimental-design · on all three evaluable populations, served notes cite 0
vanished artifacts (V = 0.0), because the estate's repos almost never delete or rename files (2 deletions in
514 commits; 0 in 90), and the procedural lane has 1 artifact-bound node in 289 servable classes · park
R4b · re-open (−1 → 0) if a re-run on a repository with real file churn finds V ≥ 0.01, or if cross-repo
citations become checkable and show stale targets.
