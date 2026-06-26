# Decision-Maker Memo — `COR` program: COR1M concentration measure & over-bulled hedge trigger

*A plain-language roll-up for a decision-maker who will not read the full findings notes. Links the underlying
notes and the [index](RESEARCH_HYPOTHESIS_INDEX.md).*

> **Living document → FINALIZED.** Created after round 1; round 2 reached **convergence** — both remaining
> decision-moving experiments are data-blocked — so the program concluded at **round 2 of the 7-round cap**
> (the cap was headroom; guardrail 4 permits stopping early when converged). The Timeline (§4) is append-only;
> §1/§3/§5/§7 were rewritten to the final verdict on close.

**Status:** `final`
**Date:** `2026-06-17`
**Verdict:** `weak_support`
**Decision:** `hold as research-only`

Use COR1M < 8 as a small, QQQ-skewed hedge *watch-flag* in the current concentrated regime, **not** a sized
standalone trigger. The program verdict is regime-bound and mixed across sub-claims (see §3).

## 1. Executive Summary

We asked whether COR1M (1-month implied correlation) measures extreme market concentration and whether its
sub-8 "over-bulled" tail is a usable hedge trigger for equity indices. After round 1: the sub-8 flag **does**
precede deeper drawdowns and roughly **double the −5% breach rate** (QQQ 2.0×, SPY 1.7×) over the next 1–2
months — but the edge is **not statistically significant** once clustering is accounted for (only ~8–9
episodes, almost all 2024–2026), and it adds information **beyond VIX only for the concentrated index (QQQ)**.
Overall program verdict: `weak_support`. Decision: treat COR1M < 8 as a low-confidence, QQQ-skewed
*hedge-readiness flag* at small size; do not commit a hedge budget until it survives out-of-sample.

## 2. What We Tested And Why It Mattered

Three linked claims: H-COR-001 (does COR1M measure concentration?), H-COR-002 (is sub-8 a usable hedge
trigger?), H-COR-003 (does it add anything beyond VIX?). Together they decide whether COR1M deserves a place in
the index-hedging process or is just a repackaged low-vol signal.

## 3. What We Found

- **H-COR-002 (trigger):** weak_support. Direction and economics are consistent and sizeable (deeper drawdown,
  ~2× breach odds, negative forward drift, worse with horizon), but the clustering-robust bootstrap p is
  0.13 (QQQ) / 0.23 (SPY) — not significant. Strongest caveat: 8 episodes from one regime.
- **H-COR-001 (concentration):** weak_support. QQQ penalised more than SPY and the effect scales smoothly with
  how deep COR1M falls (structural, not a knife-edge at 8) — but no low-concentration control (IWM out of
  scope) and no external concentration benchmark, so it is suggestive only.
- **H-COR-003 (beyond VIX):** mixed. Survives a VIX control for QQQ (coefficient −3.24%, 95% CI off zero) but
  not for SPY (CI spans zero). COR1M is a distinct input where concentration lives, redundant with VIX for the
  broad market.

## 4. Timeline — What Actually Happened

| Round | Date | Step | What happened | Artifact |
|---|---|---|---|---|
| 1 | 2026-06-17 | Scope (Phase 0) | Goal set via Plannotator: 3 seed hypotheses, panel CIO/Quant/PM, round cap 7 | [facts](../goals/cor1m-concentration-hedge/facts.md) |
| 1 | 2026-06-17 | Data | Confirmed local COR1M + SPY/QQQ/VIX through 2026-06-02 (latest COR1M 6.23, sub-8) | [data](../data/) |
| 1 | 2026-06-17 | Harness reconcile | Aligned analysis to facts: horizons 5/10/21/42, SPY+QQQ, fixed abs8, precision/lift | [analysis](../scripts/cor1m_concentration_analysis.py) |
| 1 | 2026-06-17 | Round 1 execute | Ran trigger-lead, concentration-gap, VIX-confound (E-COR-002) | [results](../outputs/cor1m_concentration_results.txt), [round2](../outputs/cor1m_round2_results.txt) |
| 1 | 2026-06-17 | Round 1 verdicts | H-COR-001 weak_support; H-COR-002 weak_support; H-COR-003 mixed | [h-001](h-cor-001_concentration-validity_2026-06-17.md), [h-002](h-cor-002_overbulled-hedge-trigger_2026-06-17.md), [h-003](h-cor-003_edge-beyond-vix_2026-06-17.md) |
| 1 | 2026-06-17 | Round 1 panel (Phase 6-8) | CIO/Quant/PM commentary; panel promoted 2 new hypotheses + 4 experiments | [commentary](../outputs/commentary/round1/), [synthesis](../outputs/synthesis/round1.json) |
| 1 | 2026-06-17 | Promoted to round 2 | H-COR-006 (concentration vs beta), H-COR-007 (era stability) | index rows |
| 2 | 2026-06-17 | Round 2 execute | E-COR-005 beta control; E-COR-011 era split; E-COR-004 circularity contrast | [round3](../outputs/cor1m_round3_results.txt), [round4](../outputs/cor1m_round4_results.txt) |
| 2 | 2026-06-17 | Round 2 verdicts | H-COR-006 weak_support (concentration residual −1.67% survives beta+VIX); H-COR-007 inconclusive (7/8 episodes 2024-26, pre-2024 untestable) | [h-006](h-cor-006_the-qqq-over-bulled-penalty-is-concentration-not_2026-06-17.md), [h-007](h-cor-007_the-cor1m-8-effect-generalizes-beyond-the-2024-2_2026-06-17.md) |
| 2 | 2026-06-17 | Round 2 converge | Phase 8 deferred: remaining experiments (real option cost E-COR-008/110, walk-forward OOS E-COR-009/108) are data-blocked → program concluded at round 2 of 7 | [synthesis](../outputs/synthesis/round2.json) |

### Final verdicts (program close)

| ID | Claim | Verdict | One-line basis |
|---|---|---|---|
| H-COR-001 | COR1M measures concentration | weak_support | QQQ penalised > SPY, monotone threshold, but weak contrast / no external ground-truth |
| H-COR-002 | COR1M < 8 is a usable hedge trigger | weak_support | ~2× breach lift & negative drift, but bootstrap p 0.13–0.23, N≈8 |
| H-COR-003 | Adds edge beyond VIX | mixed | survives VIX control for QQQ only, not SPY |
| H-COR-006 | QQQ penalty is concentration not beta | weak_support | −1.67% residual survives beta(1.16)+VIX, CI off 0; episode p 0.39 |
| H-COR-007 | Effect generalizes beyond 2024–26 | inconclusive | 1 pre-2024 episode → untestable; effect is regime-bound |

## 5. The Decision And Its Consequences

**Do:** keep COR1M < 8 as a standing, small, QQQ-skewed hedge-readiness flag; route COR1M into the QQQ hedge
sleeve only, leave SPY hedging VIX-driven. **Don't:** size a fixed hedge budget to the flag, tune the
threshold, or treat the concentration claim as proven. **Would change our mind:** the QQQ edge surviving a
beta control (H-COR-006), the effect holding out-of-sample / across eras (H-COR-007), or an external
concentration benchmark confirming H-COR-001.

## 6. Open Questions / Next Step

The single most important follow-up: **is the QQQ-specific edge concentration or just beta?** (H-COR-006 /
E-COR-005, round 2). Note: forward-reference IDs in some round-1 note prose were provisional; the canonical
follow-ups are H-COR-006, H-COR-007 and E-COR-107…110 in the index.

## 7. Feynman Explanation — For A Smart 12-Year-Old

**What is this about?** COR1M is a meter for whether everyone in the market is crowding into the same few star
stocks. We're checking if, when the meter gets very low, a fall is coming — and whether that's worth buying a
little insurance for.

**What did we learn?** When the meter dropped below 8, the market did fall harder afterward about twice as
often as usual — a real-looking warning. But it's only happened a handful of times, almost all recently, so we
can't be sure it isn't luck.

**Why does it matter?** It's a smoke alarm worth a cheap, small response (a little insurance on the techy
index), not a reason to sell everything. And for the broad market, the ordinary fear meter (VIX) already tells
you the same thing.

**What would you ask next?** "Is the techy index really reacting to crowding, or does it just swing more
anyway?" That's exactly what we test next. In your own words: a promising early-warning flag, useful in small
size on the crowded index, still waiting for more proof.
