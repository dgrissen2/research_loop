---
id: H-COR-001
round: 1
hypothesis_status: active
phase: commentary
---

# H-COR-001 — Does COR1M validly measure extreme market concentration / crowding?

Backlinks: [Index](RESEARCH_HYPOTHESIS_INDEX.md) · [goal facts](../goals/cor1m-concentration-hedge/facts.md) · [plan](../goals/cor1m-concentration-hedge/plan.md)

## 3. Claim Being Tested

If COR1M's low tail is genuinely measuring **single-stock concentration / crowding** (not just a generic vol cycle), then the forward-drawdown penalty after a COR1M < 8 reading should be **heavier in the more concentrated index (QQQ) than in the broad index (SPY)** and should scale smoothly with how deep into the tail the reading goes.

## 4. Why This Matters

Decides whether COR1M can be used as a *concentration* gauge at all. If the penalty is uniform across indices and unrelated to the depth of the tail, COR1M is just another vol proxy and the whole "concentration hedge" thesis collapses into "buy protection when vol is low," which VIX already tells you.

## 5. Decision Summary

- COR1M < 8 hurts QQQ (gap +3.02% at 21d) more than SPY (gap +1.20%), and the gap grows **monotonically** as the threshold tightens (x=10→6: +2.27% → +7.38%).
- Directionally consistent with a concentration reading, but the contrast is **weak** (both QQQ and SPY are megacap-heavy; no low-concentration control such as IWM in scope per fact-6) and there is **no external concentration ground-truth** (fact-9).
- Verdict: **weak_support**. Hold as research-only; propose re-admitting IWM as a control-only series and fetching an external concentration measure.

## 6. Target / Outcome Definition

`outcome = path-min drawdown over the next H closes = min(close[t+1..t+H]) / close[t] - 1`, per ETF, at H ∈ {5,10,21,42} trading days. The **concentration read** is the cross-index *gap*: `gap(inst) = mean dd(baseline) - mean dd(triggered)`; concentration-specificity ⇔ `gap(QQQ) > gap(SPY)`.

## 7. Data / Inputs Used

| Item | Source | Path | Date / Range | Notes |
|---|---|---|---|---|
| Primary signal | Cboe COR1M | [data/cor1m.csv](../data/cor1m.csv) | 2018-01-02→2026-06-02 | 1-month implied correlation |
| Outcome (QQQ, SPY) | Yahoo OHLC | [data/qqq_ohlc.csv](../data/qqq_ohlc.csv), [data/spy_ohlc.csv](../data/spy_ohlc.csv) | same | realized price paths (non-circular) |
| Alignment rule | inner join on date | — | N=2115 aligned days | |

## 8. Sample Integrity And Alignment

| Item | Value | Notes |
|---|---|---|
| Start | 2018-01-02 | |
| End | 2026-06-02 | |
| Aligned observations | 2115 days | 39 trigger-days in **9 episodes** (8 with a full 21d window) |
| Warm-up / lookback handling | none for abs8 (fixed level) | pctile robustness uses 252d warm-up |
| Missing-data policy | inner join drops unaligned dates | |
| Sign convention | drawdown is negative; larger gap = trigger hurts more | |

## 10. Signal / Variable Definition

`trigger = COR1M[t] < 8.0` (fixed seed level, no optimization — fact-5). Computed in [scripts/cor1m_concentration_analysis.py](../scripts/cor1m_concentration_analysis.py); threshold sweep in [scripts/cor1m_round2_experiments.py](../scripts/cor1m_round2_experiments.py) (E-COR-006).

## 11. Method

| Test ID | Method | Purpose | Window / Split | Pass Criterion |
|---|---|---|---|---|
| T1 | Cross-index gap QQQ vs SPY at 21d | concentration-specificity | full sample | gap(QQQ) > gap(SPY) |
| T2 | Threshold sweep COR1M<x, x∈{6..10} | structural vs knife-edge | full sample | monotone gap as x falls |
| T3 | Leave-one-episode-out on episode-entry dd | single-episode dominance | 8 episodes | LOO swing small |

## 12. Results

| Test ID | Result | Effect Size | Statistical Support | Practical Read |
|---|---|---|---|---|
| T1 | QQQ gap > SPY gap | +3.02% vs +1.20% | descriptive (no sig test) | concentration-consistent direction |
| T2 | monotone | x=6:+7.38%, 7:+5.58%, 8:+3.02%, 9:+2.24%, 10:+2.27% | smooth, not a spike at 8 | **structural**, not knife-edge |
| T3 | no single episode dominates | QQQ LOO swing 0.80%, SPY 0.62% | — | effect not one-episode artifact |

## 15. Threats To Validity And Confounds

- **No low-concentration control.** Both QQQ and SPY are megacap-concentrated; without IWM (out of scope, fact-6) the QQQ-vs-SPY contrast is weak and could reflect QQQ's higher beta rather than concentration (tested separately in H-COR-003 / E-COR-005).
- **No external ground-truth.** "Concentration" is inferred from COR1M's own construction plus the cross-index gap; we never compare to top-N market-cap weight or single-stock call volume (fact-9 defers this).
- **Regime-specificity.** 8 of 9 episodes are 2024–2026; the "concentration era" and the COR1M-low era coincide, so co-movement ≠ causation.
- Signal (implied correlation) and outcome (realized price path) are **independent by construction** (no options inputs in the outcome) — that part is clean.

## 18. Final Verdict

**weak_support.** The direction (QQQ penalised more than SPY) and the smooth monotone threshold response both point to COR1M's low tail carrying real concentration information rather than a knife-edge artifact. But the contrast is weak without a low-concentration control, there is no external concentration benchmark, and the sample is regime-concentrated — so this is suggestive, not established.

## 19. Decision Impact

Hold as **research-only**. Do not yet treat COR1M as a validated concentration gauge. Fund two narrow follow-ups: (a) re-admit IWM as a *control-only* series to restore the concentration contrast; (b) fetch an external concentration measure (top-N S&P weight or single-stock call volume) to anchor the claim.

## 20. Other Experiments To Run

| Experiment ID | Proposed Experiment | Why Run It | Scope | Priority | Status |
|---|---|---|---|---|---|
| E-COR-101 | Re-admit IWM as control-only low-concentration reference | restores the concentration contrast the facts removed | local | high | planned |
| E-COR-102 | Fetch external concentration series (top-N weight / single-stock call vol) | external ground-truth for the validity claim | local+fetch | medium | planned |

## 21. Independent Persona Commentary

> Human-readable excerpt of [commentary.json](../outputs/commentary/round1/H-COR-001.json) (written for round 1).

### Persona — `cio`

Interpret: A monotone threshold response is the part I weight most — it says the signal is graded, not a single cherry-picked level, which is what separates a real allocation tell from a backtest accident. But "QQQ hurts more than SPY" is a thin reed for a concentration claim when both indices are dominated by the same seven names; I read this as *consistent with* concentration, not *evidence of* it.

Act: I will not change the strategic book on this alone. I authorize the two follow-ups (IWM control, external concentration data) and treat COR1M<8 as a watch-flag, not an allocation input, until the contrast is real.

### Persona — `quant`

Interpret: T1 has no significance test attached and the QQQ-vs-SPY gap (3.02% vs 1.20%) is a difference of two noisy means on 8 episodes — I would not report it as an effect. T2 (monotone sweep) and T3 (small LOO swing) are the credible parts: they argue against a knife-edge and against single-episode dominance, which is genuinely reassuring about stability.

Act: Cap the verdict at weak_support. Before any promotion, I require a low-concentration control (IWM) so "concentration-specific" is a real two-sided contrast, and an external concentration variable so the claim isn't circular with COR1M's own construction.

### Persona — `portfolio-manager`

Interpret: For risk governance the validity question matters only insofar as it changes what I hedge. Right now the evidence says "the flag bites harder in the more concentrated tape," which is usable as a *tilt* (hedge QQQ before SPY) even if the academic concentration claim is unproven.

Act: I will let H-COR-002 (the tradeability test) carry the operational decision and keep H-COR-001 as supporting color. No book change from this note in isolation.

## 22. Reproduction

```bash
PY=.venv/bin/python
$PY scripts/cor1m_concentration_analysis.py   # gap(QQQ) vs gap(SPY), 21d
$PY scripts/cor1m_round2_experiments.py        # E-COR-006 threshold sweep + LOO
```

Artifacts: [outputs/cor1m_concentration_results.txt](../outputs/cor1m_concentration_results.txt), [outputs/cor1m_round2_results.txt](../outputs/cor1m_round2_results.txt).

## 23. Next Step

Re-admit IWM as a control-only series (E-COR-101) and re-run the cross-index gap as a genuine high-vs-low concentration contrast.

## 24. Feynman Explanation

**Paragraph 1 — What is this signal?** COR1M is like a crowd-mood meter for the stock market. When it is very low, traders have stopped buying insurance on the whole market and are instead piling into bets on a handful of star stocks — everyone crowding into the same corner of the room.

**Paragraph 2 — What did the test show?** When the meter dropped below 8, the tech-heavy index (QQQ) later fell harder than the broad index (SPY), and the deeper the meter dropped, the bigger the later fall — smoothly, not by luck at one magic number. That smoothness is the encouraging part.

**Paragraph 3 — Why does this matter?** If the meter really measures crowding, you would hedge the crowded index first. But here both indices we compared are crowded with the same giant companies, so we can't yet be sure the meter is measuring *crowding* rather than just *jumpiness*.

**Paragraph 4 — What would a curious person ask next?** "What about an index that *isn't* crowded — like small companies (IWM)? If the meter barely hurts those, that proves it's about crowding." Exactly — that's the next test. Now, in your own words: this is measuring how much the whole market is leaning on a few names, and you'd trust it more once you check it against an index that doesn't lean that way.
