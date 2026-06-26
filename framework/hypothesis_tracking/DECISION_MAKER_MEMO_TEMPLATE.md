# Decision-Maker Memo — `<HYPOTHESIS_ID>`: `<short title>`

*A plain-language roll-up for a decision-maker who will not read the full findings note. No unexplained
jargon. Link the underlying [findings note](.) and [index row](RESEARCH_HYPOTHESIS_INDEX.md).*

> **Living document — two update rules.** Create it after round 1, then every round:
> **(a) Append-only — the Timeline (§4):** add this round's row(s) with `Round` = N; never edit a prior row.
> **(b) Rewritten every round — §1 / §3 / §5 / §7:** restate them to the *current* verdict so the body never
> contradicts the header. **Finalize** on the last round (the round cap) **or** the round a human authorizes
> early termination: rewrite §1/§3/§5/§7 to the final verdict and flip the header **Status** to `final`.

**Status:** `living`
**Date:** `YYYY-MM-DD`
**Verdict:** `<supported / weak_support / mixed / not_supported / inconclusive>`
**Decision:** `<promote / hold as research-only / stop / fund one narrow follow-up>`

## 1. Executive Summary

Three to five sentences: what we asked, what we found, and what we should do. **Lead with the decision, and
state the verdict as exactly one enum token** — the same token as the header `Verdict` (`supported` /
`weak_support` / `mixed` / `not_supported` / `inconclusive`), written once.

## 2. What We Tested And Why It Mattered

The claim in one paragraph, and the decision it would change.

## 3. What We Found

The result in plain terms — effect size and confidence stated as "big/small" and "strong/weak/mixed",
not raw statistics. Note the strongest caveat.

## 4. Timeline — What Actually Happened

A clear, chronological account of how we got here. One row per meaningful step (idea, data pull, test,
rerun, objection answered, verdict). This is the audit trail in plain language — **append this round's rows
at the end of each round** (append-only), setting each new row's `Round` to the round number; it is the part
of the memo that grows every round.

| Round | Date | Step | What happened | Artifact |
|---|---|---|---|---|
| | | | | |

## 5. The Decision And Its Consequences

What we will do, what we will not do, and what would change our mind.

## 6. Open Questions / Next Step

The single most important follow-up.

## 7. Feynman Explanation — For A Smart 12-Year-Old

*Four short paragraphs, one everyday analogy each, no jargon.*

**What is this about?**
[The thing we measured, as if explaining to a curious kid.]

**What did we learn?**
[Did it work or not, in plain words. Big effect or small?]

**Why does it matter?**
[The real decision this informs, with one concrete scenario.]

**What would you ask next?**
[The natural "but wait…" question — then invite them to explain it back in their own words.]
