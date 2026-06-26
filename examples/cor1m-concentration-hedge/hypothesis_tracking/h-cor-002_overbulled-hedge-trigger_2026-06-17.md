---
id: H-COR-002
round: 1
hypothesis_status: active
phase: commentary
---

# H-COR-002 — Is the COR1M < 8 "over-bulled" tail a usable forward hedge trigger?

Backlinks: [Index](RESEARCH_HYPOTHESIS_INDEX.md) · [goal facts](../goals/cor1m-concentration-hedge/facts.md) · [plan](../goals/cor1m-concentration-hedge/plan.md)

## 3. Claim Being Tested

A COR1M reading below 8 ("over-bulled" / SpotGamma certain-risk flag) precedes **worse forward outcomes** in SPY and QQQ — deeper path-min drawdown and a higher rate of −5% breaches than the unconditional base rate — strongly enough to act on as a hedge trigger.

## 4. Why This Matters

If true, COR1M < 8 is a simple, observable, non-circular entry rule for buying index protection. The decision it changes: *do you put on or step up an equity-index hedge when COR1M prints sub-8?*

## 5. Decision Summary

- COR1M < 8 precedes worse 21-day outcomes in **both** SPY and QQQ: deeper mean drawdown and a higher −5% breach rate. Breach **precision/lift**: SPY 1.74×, QQQ 2.01× the base rate; forward returns turn negative (QQQ −3.94%, SPY −1.95% at 21d).
- BUT after clustering correction the day-level edge is **not statistically significant** (moving-block bootstrap p = 0.13 QQQ, 0.23 SPY) and rests on only **8–9 episodes**, almost all in 2024–2026.
- Verdict: **weak_support**. Usable as a *soft risk flag / hedge tilt*, not a standalone statistically-proven trigger.

## 6. Target / Outcome Definition

Per ETF, from day-t close, at H ∈ {5,10,21,42} trading days: `path-min drawdown = min(close[t+1..t+H])/close[t]−1`; `breach = 1 if path-min ≤ −5%`; `fwd return = close[t+H]/close[t]−1`. Primary horizon = 21d. Scoring (fact-8): drawdown vs base rate **and** hit-rate/precision = P(breach | trigger) vs base rate = P(breach).

## 7. Data / Inputs Used

| Item | Source | Path | Date / Range | Notes |
|---|---|---|---|---|
| Trigger signal | Cboe COR1M | [data/cor1m.csv](../data/cor1m.csv) | 2018→2026-06-02 | abs8 = COR1M<8 |
| Outcome SPY/QQQ | Yahoo OHLC | [data/spy_ohlc.csv](../data/spy_ohlc.csv), [data/qqq_ohlc.csv](../data/qqq_ohlc.csv) | same | realized, non-circular |

## 8. Sample Integrity And Alignment

| Item | Value | Notes |
|---|---|---|
| Start | 2018-01-02 | |
| End | 2026-06-02 | |
| Aligned observations | 2115 days | 36 trigger-days with a full 21d window |
| Episodes | **9** (8 with full 21d window) | 2018-01-03, then 8 in 2024-06→2026-05 |
| Warm-up | none (fixed level) | |
| Missing-data policy | inner join | |
| Sign convention | drawdown negative; trigger "works" if triggered worse than baseline | |

## 10. Signal / Variable Definition

`trigger = COR1M[t] < 8.0`, fixed seed level (fact-5). Episodes = trigger-day clusters >5 calm days apart. Clustering-robust inference via moving-block bootstrap (block = horizon). Code: [scripts/cor1m_concentration_analysis.py](../scripts/cor1m_concentration_analysis.py).

## 11. Method

| Test ID | Method | Purpose | Window / Split | Pass Criterion |
|---|---|---|---|---|
| T1 | triggered vs baseline mean dd + breach, 21d, SPY & QQQ | does the flag precede worse outcomes | full sample | worse on both dd & breach in both ETFs |
| T2 | precision/lift = P(breach\|trig)/P(breach), 21d | economic signal strength | full sample | lift > 1 |
| T3 | moving-block bootstrap p (block=21), 5000 resamples | clustering-robust significance | full sample | p < 0.05 |
| T4 | episode-level entry-day means (N=8) | de-cluster the sample | episodes | triggered worse |

## 12. Results

| Test ID | Result | Effect Size | Statistical Support | Practical Read |
|---|---|---|---|---|
| T1 | PASS (both ETFs worse) | QQQ dd −6.41% vs −3.39%; SPY −3.98% vs −2.77% | descriptive | flag precedes deeper drawdowns |
| T2 | lift > 1 | SPY 1.74×, QQQ 2.01× (breach 33%/56% vs 19%/28%) | descriptive | flag ~doubles QQQ breach odds |
| T3 | **not significant** | gap QQQ +3.02% / SPY +1.20% | p = 0.13 / 0.23 | edge not separable from clustering noise |
| T4 | directionally worse | QQQ episode dd −3.73%, SPY −2.25% | N=8 | holds but tiny N |

42d horizon amplifies: QQQ triggered dd −8.60% (breach 78%) vs baseline −4.97% (38%); SPY −6.01% (breach 69%) vs −4.12% (28%).

## 15. Threats To Validity And Confounds

- **Clustering / tiny N.** 36 trigger-days collapse to ~8 independent episodes with overlapping forward windows; day-level counts overstate significance (hence the bootstrap, which is not significant).
- **Regime concentration.** 8 of 9 episodes are 2024–2026 — the result is essentially an artifact of one bull-to-wobble regime; cross-era stability cannot be established (see H-COR-005 / E-COR-011).
- **Multiple testing.** Two ETFs × four horizons × two triggers were examined; no family-wise correction applied to the headline.
- Signal and outcome are **independent** (no options inputs in the realized path) — no leakage.
- **Confound with VIX.** Whether the edge survives controlling for low VIX is the separate H-COR-003 question (answer: only in QQQ).

## 18. Final Verdict

**weak_support.** Every descriptive cut points the same way — sub-8 COR1M precedes deeper drawdowns and roughly double the −5% breach rate, growing with horizon — which is economically meaningful and directionally robust (episode-level, LOO). But the clustering-robust bootstrap is not significant and the sample is 8 episodes from one regime, so this cannot be sold as a proven standalone trigger.

## 19. Decision Impact

Promote to **operational watch-flag**, not a mechanical trigger: when COR1M < 8, *tilt toward* index protection (QQQ before SPY) and tighten risk, sized small because the statistical confidence is low. Do not commit a fixed hedge budget to it yet. Re-evaluate as new episodes accrue out-of-sample.

## 20. Other Experiments To Run

| Experiment ID | Proposed Experiment | Why Run It | Scope | Priority | Status |
|---|---|---|---|---|---|
| E-COR-103 | Walk-forward / out-of-sample test as new episodes print | only honest cure for tiny in-sample N | local | high | planned |
| E-COR-104 | Family-wise multiple-testing correction across ETF×horizon×trigger | headline is uncorrected | local | medium | planned |

## 21. Independent Persona Commentary

> Human-readable excerpt of [commentary.json](../outputs/commentary/round1/H-COR-002.json) (written for round 1).

### Persona — `cio`

Interpret: The economic shape is exactly what I would want from a tail flag — it gets *more* right as the horizon lengthens and it doubles the breach rate in the crowded index. That is a usable allocation tell even if the p-value is soft, because as a CIO I am buying asymmetric protection, not betting the farm on the mean.

Act: I am comfortable treating COR1M<8 as a standing "raise hedge readiness" flag at small size. I will not size it like a high-conviction signal until it survives out-of-sample.

### Persona — `quant`

Interpret: This is the textbook clustering trap. 36 "observations" are 8 episodes; the moving-block bootstrap p of 0.13/0.23 is the honest number and it does not clear 0.05. The lift figures are real but rest on ~8 independent draws, almost all from 2024–26 — that is a single regime, not a tested distribution.

Act: Verdict must stay weak_support; do not promote to a mechanical trigger. The only thing that moves this is genuine out-of-sample episodes (E-COR-103) and a multiple-testing correction (E-COR-104). I would explicitly forbid threshold tuning.

### Persona — `portfolio-manager`

Interpret: From a risk-budget seat, a flag that roughly doubles the odds of a −5% breach and reliably precedes negative drift is actionable *as insurance*, because the cost of a small hedge is bounded and the payoff is convex. The danger is over-trusting it and over-hedging into the 11 of 12 times it's noise.

Act: Implement as a small, rules-light tilt: on COR1M<8, add a modest QQQ-skewed hedge, cap the premium spend, and let it expire if no breach. Pair with H-COR-003 to confirm it's adding something VIX wasn't already telling me.

## 22. Reproduction

```bash
PY=.venv/bin/python
$PY scripts/cor1m_concentration_analysis.py   # triggered-vs-baseline dd, breach, precision/lift, bootstrap p
```

Artifacts: [outputs/cor1m_concentration_results.txt](../outputs/cor1m_concentration_results.txt).

## 23. Next Step

Stand up the out-of-sample tracker (E-COR-103): log each new COR1M<8 episode and its realized 21d/42d outcome as it happens.

## 24. Feynman Explanation

**Paragraph 1 — What is this signal?** Think of COR1M as a "everyone's leaning the same way" gauge. Below 8, it's flashing that traders have stopped buying market-wide insurance and are all crowding into a few hot stocks — the boat is tipping to one side.

**Paragraph 2 — What did the test show?** After the gauge flashed, the market more often took a bigger dip over the next month — about twice as likely to drop 5% as usual, and the longer you waited the worse it looked. So the flash does seem to come before trouble.

**Paragraph 3 — Why does this matter?** It's like a smoke alarm: when it goes off, you don't evacuate the city, but you do check the stove and keep a fire extinguisher handy — here, you buy a little cheap insurance on the index, leaning toward the techy one.

**Paragraph 4 — What would a curious person ask next?** "How many times has the alarm actually gone off?" Only about eight or nine, almost all in the last two years — too few to be sure it isn't luck. In your own words: it's an early-warning flag worth a small, cheap hedge, but not yet something to bet big on, because we've barely seen it work.
