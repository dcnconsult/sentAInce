# Color doctrine — the organism's visual language

> The binding rule set for every SentAInce surface that colors a metric (the body page at
> `:9109/`, Grafana boards, future reports). One doctrine, one meaning per color, everywhere.

## The two laws

1. **A color is a thresholded raw number, never a judgment.** Every colored element states,
   adjacent to the color, the rule that produced it and the raw value it was applied to
   ("3 classes at the edge cap — next sleep prunes"). If a metric has no honest
   healthy/unhealthy direction (e.g. colony entropy — descriptive, not good/bad), it gets
   **no health color**: show it as neutral text.
2. **Color never carries meaning alone.** Every state ships with its word (and, where drawn,
   its organ icon): the body page prints a state word + rule text beside every colored organ
   and every region carries a hover title. This is the colorblind mitigation — the
   good↔attention↔strained hues are NOT reliably separable under deuteranopia (measured
   ΔE 4.1 good↔red-family) — and it is not optional.

## The states (fixed palette — never themed)

| State | Word | Hex | Meaning |
|---|---|---|---|
| good | healthy | `#0ca30c` | the thresholded vital is inside its stated healthy rule |
| warn | attention | `#fab219` | the vital crossed its stated attention rule — look, don't panic |
| serious | strained | `#ec835a` | the organism is protecting itself (e.g. tier HYPOXIA) |
| dormant | dormant | `#4a5064` | the organ ships OFF because its own gauge rated the prize modest/null — honesty, not failure |
| cold | no data yet | *(no fill — dashed outline)* | the organ is on but has seen no data; **nothing ever fakes green** |

`critical #d03b3b` is reserved and currently unused — no free-tier vital has an honest
"critical" rule yet. Do not repurpose it.

**dormant vs cold is a real distinction:** dormant = a deliberate, gauge-backed OFF (solid
gray fill); cold = alive but unfed (outline only). A fresh deploy renders a mostly-cold body —
that is the correct, honest picture (the negative control).

## The organ rules (body page, `/api/vitals` fields)

| Organ (region) | Vital | Rule |
|---|---|---|
| 🛡️ Immune (chest shield) | `lethal_attempts` | 0 → good "the reflex stayed quiet" · >0 → warn "N refused — read the audit". Never `serious`: a refusal means the gate **worked**. |
| 🫀 Stamina (heart) | `tier.now` | SATED → good · STARVING → warn · HYPOXIA → serious · none → cold |
| 💪 Muscle memory (arms) | `deposits` | >0 → good "N habits earned (exit 0 only)" · 0 → cold |
| 😴 Sleep (head) | `colony.classes`, `colony.at_cap` | no classes → cold · at_cap>0 → warn "next sleep prunes" · else good |
| 📖 Notebook (book) | `config.declarative_mode`, `wiki.*` | mode off → dormant · credited>0 → good (credit rate shown) · else cold (injected-but-uncredited is *not* unhealthy) |
| 🎯 Credit timing (legs) | `config.eligibility_trace_mode` | off → dormant · trace → good |
| 🧪 Stress hormones (gland) | `config.endocrine_mode` | off → dormant · tier → good |

Metrics shown as neutral text only (direction exists but no ratified threshold, or no
direction at all): `fail_rate`, `seg_len_median`, colony entropy, class counts.

## Adoption

Any other surface (Grafana skins, reports, downstream consumers of `/api/vitals`) adopts this
table as-is and may **extend** it (new organs/states) but never redefine an existing state's
hex, word, or rule direction. Free-tier surfaces show every raw number; anything ranked,
trended, or advisory is out of scope for this doctrine (and for the free tier).
