# Where this sits — the honest landscape

*Last reviewed 2026-07-22.*

If you are evaluating agent-safety tooling, you will find several categories of product that sound like
they solve the same problem. They mostly don't — they operate at different points in the call path, and
that difference decides what each one can actually stop.

This page describes those categories, and says plainly which one we are. We are **not trying to be the
everything-product.** Knowing which layer you need is more useful than a feature comparison, and if the
layer you need isn't us, we would rather you find that out here.

We describe categories rather than name products: naming is a claim about someone else's software, it
goes stale, and it invites a scoreboard instead of a decision.

## The altitude question

The useful axis is **where in the call path the check happens**, because that determines what the check
survives.

| Layer | Where it runs | What it can stop | What it can't |
|---|---|---|---|
| **Prompt / system-message rules** | inside the model's context | anything the model chooses to honor | anything that talks the model out of it |
| **Detection & inspection** | alongside the model — reading prompts, chain-of-thought, or generated code | injections and unsafe patterns it recognizes | what it doesn't recognize; it advises, something else still executes |
| **Proxy / gateway control planes** | out-of-process, mediating tool traffic — allowlists, approval gates, audit | anything crossing that boundary | anything that never crosses it — a local call the agent makes directly |
| **Dialog / conversation rails** | conversation flow control | off-policy conversation, moderation, dialog state | not aimed at tool-execution safety |
| **In-process execution refusal** ← *us* | at the host's tool-call hook, before the call runs | catalogued lethal actions, **regardless of what the model concluded** | anything outside its catalogue — it is a floor, not a ceiling |

These are **not competing answers to one question.** A gateway cannot see a call that never leaves the
process. A detector that flags a command still needs something downstream to refuse it. We are the
refusal, and a floor is only useful if you also have the rest of the building.

## What we claim

One thing, narrowly:

> The somatic gate refuses catalogued lethal actions **without asking the model**, so a prompt-injected or
> compromised model does not get a vote. Measured: N=100 live episodes against a gullible `llama3:8b` in a
> hardened container — survival **1.000**, 0 slips.

That lives in [`CLAIMS.md`](CLAIMS.md) with its evidence. CLAIMS is binding; nothing in this repo — this
page included — may exceed it.

Second: **memory that only records what verifiably worked.** A route earns retention through a closed
action → `exit 0` chain, never by being read or repeated. That is a real architectural difference from
conversation-history and vector-store memory, which retain whatever passed through them. Shipped and
tested. Its *benefit* is still being measured — see the last section.

## Earned memory vs retrieved memory

There is a healthy line of work — call it **graph engineering** — around treating the model as **one node
in a graph** rather than the center of the system, and giving it **relational** or graph-structured memory
instead of baking everything into weights. We think that framing is correct, and the terminology is a good
fit for what this project already is: the earned-route store *is* a directed graph, and the model is a
proposer inside it, not the whole of it.

Where we differ is the **one axis that defines this project**. In the common pattern, the graph or
relational memory is **retrieved from** — a store, usually pre-built, read to make the next generation more
likely or more coherent, and judged by a proxy for quality. Here, the graph is **earned into**: an edge
gains weight only when a real action closed successfully, retrieval alone changes nothing, and the signal
is an actual outcome rather than a proxy for one.

Same substrate — a graph, the model decentered. Opposite discharge: **retrieved-from vs earned-into.** We
believe the earned version pays off over a long horizon and across many repositories, precisely where a
larger context window stops helping. We have not proven that yet — the honest status is two sections down.
It is the harder bar on purpose: improving a likelihood score is one thing, moving real outcomes is
another, and we would rather be measured on the second even while the number is still only trending.

## Multi-repo visibility — the part that exists today

Most agent tooling is single-repo by construction: it sees the project it is installed in and nothing
else. Developers do not work that way. One person moves across a dozen repositories in a week, and the
useful questions are the ones that span them — *where is my agent actually refusing things? which
repositories have accumulated real earned memory and which are cold? what changed across the estate this
week?*

SentAInce is built around an **estate**: one file names every repository the stack watches
([`docs/ESTATE.md`](ESTATE.md)), and the dashboard reports across all of them rather than one at a time.
This is shipped, local, and needs no account.

We think this is the honest near-term differentiator — not because the mechanism is exotic, but because
it is the question nobody else is answering, and it is a precondition for everything below.

## Where this is going — labeled as a bet, not a claim

Cross-repository **intelligence and governance** is the direction: memory and policy that reason over the
whole estate rather than each repo in isolation. Not "which command do I refuse here," but *what has this
developer's whole body of work established, and what should hold across all of it.*

We are not aware of anyone addressing that layer. That is the bet.

**Status: measured, directional, not yet proven.** Our controlled A/B on earned-memory guidance:

- Paired same-task ON/OFF, R=5, full N: **50/80 (0.625) vs 38/80 (0.475)** — a **+15pp gap that stayed
  stable** (12.5–15.6pp) across a 5× increase in runs.
- **p = 0.0781.** The pre-registered gate was p ≤ 0.05. **The gate is not met**, and we stopped rather
  than extend a third time — extending until a number crosses a line is how you fool yourself.
- Honest reason it is underpowered: a short timeline, one maintainer, and a task battery where only 6 of
  16 tasks could move at all (5 were saturated, 4 impossible in both arms, 1 tied mid-range). The ceiling
  was the instrument, not the effect.
- **The secondary measures do not survive the primary's own paired test**, so we claim none of them —
  not efficiency, not a do-no-harm advantage. Success rate is the only signal here. We found that by
  re-analyzing our own result and losing; see the changelog.

So: **trending, on a real control, with the gate openly unmet.** We publish it in that shape deliberately.
A directional result reported as a win would be the exact failure this project was built to avoid, and a
directional result buried would be dishonest in the other direction. What would settle it is a
better-powered battery — or your null, run on your own corpus.

## Running us alongside, not instead

- **With a gateway control plane:** it governs what crosses the tool boundary; we cover local calls that
  never cross it. Different blast radii, nothing to reconcile.
- **With a detector:** it classifies, we refuse. A detector's finding is worth most when something
  downstream is guaranteed to act on it.
- **With dialog rails:** orthogonal — conversation policy above, execution floor below.
- **With any MCP client:** the memory server speaks the open standard and is read-only, including from
  non-Anthropic hosts.

## Host support — stated plainly

The *somatic hook gate* is host-specific, because it installs into a host's tool-call hook:

| Host | Status |
|---|---|
| **Claude Code** | supported — the full hook gate |
| **Cursor** | soft shim: fail-open and user-bypassable. Real, and weaker; we say so rather than list it as parity |
| **Codex** | near-term target — the host surface is maturing quickly and is the next one we intend to support |
| **Kimi Code** | near-term target — early, but it exposes the hook elements this design needs |
| **Any MCP client** | memory organ only — read-only recall, **not** the hook gate |

Until a host appears in the supported row, assume you get the memory organ and not the gate. We would
rather you know that before installing than after.

## Governance frameworks

We would rather plug into emerging agent-governance standards than invent a competing one:

- **AGNTCY / OASF** — the memory server ships a machine-readable agent-directory record
  ([`oasf-record.json`](../oasf-record.json)), versioned with the package.
- **MCP** — the open standard; any compliant client can read earned memory.
- **Audit** — the hash-chained, tamper-evident trail is built to satisfy an external reviewer, not just
  us. Tamper with a record and provenance renders `CHAIN BROKEN` rather than failing quietly.

## How to falsify this page

Every row above is a claim, and claims here are meant to be breakable. If a category description
misrepresents a class of product you know well, or a status is wrong, open an issue — corrections land on
the record with the same discipline as everything else, and this page carries the date it was last checked.

The fastest way to change our mind about the cross-repository thesis is a gauge run on your own corpus.
Nulls are the contribution we value most.
