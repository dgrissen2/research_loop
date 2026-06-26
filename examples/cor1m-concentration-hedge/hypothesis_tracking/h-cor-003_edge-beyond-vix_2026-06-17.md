---
id: H-COR-003
round: 1
hypothesis_status: active
phase: commentary
---

# H-COR-003 — Does the COR1M < 8 tail add edge beyond a VIX/vol baseline?

Backlinks: [Index](RESEARCH_HYPOTHESIS_INDEX.md) · [goal facts](../goals/cor1m-concentration-hedge/facts.md) · [plan](../goals/cor1m-concentration-hedge/plan.md)

## 3. Claim Being Tested

The forward-drawdown information in COR1M < 8 is **not just low-VIX in disguise**: after controlling for the VIX level, the COR1M < 8 trigger still carries incremental negative information about forward index drawdown.

## 4. Why This Matters

This is the make-or-break test. If COR1M < 8 adds nothing beyond "VIX is low," there is no reason to watch COR1M at all — you would act on VIX. The decision it changes: *is COR1M a distinct input to the hedge process, or redundant?*

## 5. Decision Summary

- Controlling for VIX via OLS of 21d path-min drawdown on `trigger + VIX`, the COR1M<8 coefficient is **−3.24% for QQQ with a 95% bootstrap CI of [−6.08%, −0.34%] (off zero → significant)** but **−1.57% for SPY with CI [−3.09%, +0.27%] (spans zero → not significant)**.
- Within the low-VIX regime, COR1M<8 still deepens 21d drawdown by −4.28% (QQQ) and −2.04% (SPY) vs low-VIX/COR1M≥8 days.
- Verdict: **mixed**. COR1M adds edge beyond VIX **for the concentrated index (QQQ)**, but not for SPY.

## 6. Target / Outcome Definition

`path_min_dd_21 = min(close[t+1..t+21])/close[t] − 1`, regressed on `trigger = 1[COR1M<8]` and `VIX_level[t]`. Incremental edge ⇔ trigger coefficient `b1` clearly negative with a bootstrap CI off zero.

## 7. Data / Inputs Used

| Item | Source | Path | Date / Range | Notes |
|---|---|---|---|---|
| Trigger | Cboe COR1M | [data/cor1m.csv](../data/cor1m.csv) | 2018→2026-06-02 | abs8 |
| Control | VIX level | [data/vix_ohlc.csv](../data/vix_ohlc.csv) | same | close |
| Outcome | QQQ/SPY OHLC | [data/qqq_ohlc.csv](../data/qqq_ohlc.csv), [data/spy_ohlc.csv](../data/spy_ohlc.csv) | same | realized path |

## 8. Sample Integrity And Alignment

| Item | Value | Notes |
|---|---|---|
| Start | 2018-01-02 | |
| End | 2026-06-02 | |
| Aligned observations | 2115 days | low-VIX regime = VIX ≤ 33rd pctile (16.0); 26 low-VIX & COR1M<8 days |
| Warm-up | none | |
| Missing-data policy | inner join | |
| Sign convention | more-negative b1 = trigger adds drawdown beyond VIX | |

## 10. Signal / Variable Definition

Manual OLS (no statsmodels dependency) of `path_min_dd_21 ~ b0 + b1·trigger + b2·VIX_level`; `b1` is the level shift in 21d path-min drawdown attributable to the trigger holding VIX fixed. 95% CI from a moving-block bootstrap. Code: [scripts/cor1m_round2_experiments.py](../scripts/cor1m_round2_experiments.py) (E-COR-002).

## 11. Method

| Test ID | Method | Purpose | Window / Split | Pass Criterion |
|---|---|---|---|---|
| T1 | OLS dd ~ trigger + VIX (QQQ, SPY) | partial out VIX | full sample | b1 < 0 with CI off zero |
| T2 | conditional comparison within low-VIX regime | non-parametric cross-check | VIX ≤ 16.0 | trigger deepens dd |

## 12. Results

| Test ID | Result | Effect Size | Statistical Support | Practical Read |
|---|---|---|---|---|
| T1 (QQQ) | **significant** | b1 = −3.24% | 95% CI [−6.08%, −0.34%] | adds edge beyond VIX |
| T1 (SPY) | **not significant** | b1 = −1.57% | 95% CI [−3.09%, +0.27%] | redundant with VIX |
| T2 | trigger deepens dd | QQQ −4.28%, SPY −2.04% | descriptive (N=26) | concentration-index-specific |

## 15. Threats To Validity And Confounds

- **Partial circularity (controlled here, not eliminated).** COR1M and VIX are both options-implied; regressing one on the other is a within-family comparison. The realized price-path target keeps the *outcome* non-circular, which is why this is the honest version (vs E-COR-004's options-target contrast).
- **Tiny conditioned N.** Only 26 low-VIX & COR1M<8 days (far fewer independent episodes); the QQQ CI is off zero but barely.
- **Regime concentration** as in H-COR-002.
- The QQQ-yes / SPY-no split could itself be the **beta** confound (QQQ moves more), tested in H-COR-005 / E-COR-005.

## 18. Final Verdict

**mixed.** COR1M < 8 carries drawdown information beyond the VIX level for QQQ (coefficient off zero on the bootstrap), but for SPY the incremental effect is indistinguishable from zero once VIX is controlled. So COR1M is a distinct input *where concentration lives* (the Nasdaq), and largely redundant with VIX for the broad market.

## 19. Decision Impact

Keep COR1M in the hedge process **for the concentrated index only**. For SPY hedging, VIX is sufficient — do not add COR1M complexity. Next, separate concentration from beta (E-COR-005) before trusting the QQQ-specific edge.

## 20. Other Experiments To Run

| Experiment ID | Proposed Experiment | Why Run It | Scope | Priority | Status |
|---|---|---|---|---|---|
| E-COR-105 | Beta control: regress QQQ dd on trigger + SPY dd + VIX | is the QQQ edge concentration or just beta? | local | high | planned |
| E-COR-106 | Options-target contrast (Δ21d VIX) to expose circularity | show realized target is the honest one | local | low | planned |

## 21. Independent Persona Commentary

> Human-readable excerpt of [commentary.json](../outputs/commentary/round1/H-COR-003.json) (written for round 1).

### Persona — `cio`

Interpret: This is the result that earns COR1M a seat at the table — but only at one chair. If COR1M is just VIX for SPY, I won't add it to the broad-market playbook; if it's distinct for QQQ, that's where concentration risk actually concentrates, so that's where I want a second instrument. The asymmetry is the finding, not a disappointment.

Act: Authorize COR1M as a Nasdaq-specific hedge input; keep the SPY hedge VIX-driven. Hold pending the beta test before I treat the QQQ edge as concentration rather than leverage.

### Persona — `quant`

Interpret: The honest read is one CI off zero (QQQ) and one CI spanning zero (SPY), both on a handful of conditioned days — this is suggestive, not robust. The OLS is a manual two-regressor fit; I'd want heteroskedasticity-aware errors and, crucially, a third regressor for the market move (SPY dd) before I credit "beyond VIX" rather than "beyond VIX but actually beta."

Act: Cap at mixed. Require E-COR-105 (beta control) next; if the trigger coefficient survives SPY-dd + VIX, the claim strengthens to weak_support, otherwise it collapses to "QQQ beta."

### Persona — `portfolio-manager`

Interpret: Operationally, "COR1M adds nothing to SPY hedging but something to QQQ hedging" is a clean, usable rule — it tells me where not to waste complexity. The risk is leaning on a 26-day conditional effect that could be beta in disguise.

Act: Route COR1M into the QQQ hedge sleeve only, VIX into the SPY sleeve, and gate any sizing on the beta test clearing. No redundant COR1M overlay on broad-market protection.

## 22. Reproduction

```bash
PY=.venv/bin/python
$PY scripts/cor1m_round2_experiments.py   # E-COR-002: OLS dd ~ trigger + VIX, bootstrap CI
```

Artifacts: [outputs/cor1m_round2_results.txt](../outputs/cor1m_round2_results.txt).

## 23. Next Step

Run the beta control (E-COR-105): does the QQQ trigger coefficient survive adding SPY's drawdown as a regressor?

## 24. Feynman Explanation

**Paragraph 1 — What is this signal?** VIX is the market's overall "how scared are we" meter. COR1M is a different meter — "are people crowding into a few names." The question is whether the crowding meter tells you anything the fear meter doesn't already.

**Paragraph 2 — What did the test show?** For the tech-heavy index, the crowding meter still predicted extra trouble even after we accounted for the fear meter. For the broad index, it didn't — once you knew the fear level, the crowding meter added nothing.

**Paragraph 3 — Why does this matter?** It means you only need the crowding meter where the crowding actually is — the Nasdaq. For the whole market, the plain fear meter is enough, so you keep things simple there.

**Paragraph 4 — What would a curious person ask next?** "Wait — the tech index also just *moves more*. Is the crowding meter really catching crowding, or just bigger swings?" Right — that's the next test. In your own words: COR1M earns its keep only for the crowded index, and even there we still have to rule out that it's just measuring bigger-swinging stocks.
