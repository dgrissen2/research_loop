---
id: H-COR-006
round: 2
hypothesis_status: active
phase: commentary
---

# H-COR-006 — Is the QQQ over-bulled penalty concentration, not just beta?

Promoted from round-1 synthesis (decision `beta-vs-concentration`). Backlinks: [Index](RESEARCH_HYPOTHESIS_INDEX.md) · [goal facts](../goals/cor1m-concentration-hedge/facts.md) · [parent H-COR-003](h-cor-003_edge-beyond-vix_2026-06-17.md)

## 3. Claim Being Tested

The extra forward drawdown QQQ suffers after COR1M < 8 is **concentration-specific**, not merely QQQ's higher market beta: controlling for SPY's own drawdown (the market move) **and** VIX, the COR1M < 8 trigger still adds incremental QQQ drawdown.

## 4. Why This Matters

H-COR-003 found the COR1M edge survives a VIX control for QQQ but not SPY. The obvious alternative is that QQQ just moves ~1.16× the market, so any market-wide signal looks bigger there. If the QQQ edge is only beta, COR1M is not a *concentration* tool — you'd just scale a market signal. This decides whether the concentration story has residual substance.

## 5. Decision Summary

- Regressing `qqq_dd21 ~ trigger + spy_dd21 + VIX`: the trigger coefficient is **−1.67%** with a 95% block-bootstrap CI of **[−3.14%, −0.15%] (off zero → significant)**.
- A concentration-specific component **survives** after removing both the market move (QQQ beta = 1.16) and VIX. It is smaller than the VIX-only coefficient (−3.24%, H-COR-003), as expected.
- Episode-level permutation (N=8) p = 0.386 — underpowered. Verdict: **weak_support**.

## 6. Target / Outcome Definition

`qqq_dd21 = min(QQQ close[t+1..t+21])/close[t] − 1`, regressed on `trigger = 1[COR1M<8]`, `spy_dd21` (contemporaneous SPY 21d path-min drawdown = the market path), and `VIX_level[t]`. Concentration-specific ⇔ trigger coefficient negative with bootstrap CI off zero after these controls.

## 7. Data / Inputs Used

| Item | Source | Path | Date / Range | Notes |
|---|---|---|---|---|
| Trigger | Cboe COR1M | [data/cor1m.csv](../data/cor1m.csv) | 2018→2026-06-02 | abs8 |
| Market control | SPY OHLC | [data/spy_ohlc.csv](../data/spy_ohlc.csv) | same | spy_dd21 |
| VIX control | VIX | [data/vix_ohlc.csv](../data/vix_ohlc.csv) | same | level |
| Outcome | QQQ OHLC | [data/qqq_ohlc.csv](../data/qqq_ohlc.csv) | same | qqq_dd21 |

## 8. Sample Integrity And Alignment

| Item | Value | Notes |
|---|---|---|
| Start | 2018-01-02 | |
| End | 2026-06-02 | |
| Aligned observations | 2115 days | 36 trigger-days; ~8 independent episodes |
| QQQ beta to SPY | 1.16 | daily returns, full sample |
| Warm-up | none | |
| Missing-data policy | inner join | |
| Sign convention | more-negative trigger coef = concentration-specific drawdown beyond beta+VIX | |

## 10. Signal / Variable Definition

Manual three-regressor OLS `qqq_dd21 ~ b0 + b1·trigger + b2·spy_dd21 + b3·VIX`; 95% CI via moving-block bootstrap. Code: [scripts/cor1m_round3_experiments.py](../scripts/cor1m_round3_experiments.py) (E-COR-005).

## 11. Method

| Test ID | Method | Purpose | Window / Split | Pass Criterion |
|---|---|---|---|---|
| T1 | OLS qqq_dd ~ trigger + spy_dd + VIX | strip beta + vol | full sample | trigger b1 < 0, CI off zero |
| T2 | episode-only permutation (N=8) | clustering-honest significance | episodes | p < 0.05 (expected to fail at N=8) |

## 12. Results

| Test ID | Result | Effect Size | Statistical Support | Practical Read |
|---|---|---|---|---|
| T1 | **survives** | trigger b1 = −1.67% (spy_dd coef +1.00, VIX +0.026%) | 95% CI [−3.14%, −0.15%] | concentration residual is real |
| T2 | underpowered | episode mean dd −3.73% vs null −3.42% | permutation p = 0.386 | suggestive, not significant |

## 15. Threats To Validity And Confounds

- **Underpowered episode inference.** N=8 episode entries → permutation p 0.386; the day-level CI off zero leans on overlapping windows. The residual is real in the regression but cannot be confirmed episode-by-episode.
- **Regime concentration.** Same 2024–2026 dominance as the rest of the program (H-COR-007).
- **Beta estimate is full-sample.** A time-varying beta could absorb or release some of the residual.
- The market control (`spy_dd21`) is contemporaneous to the outcome window — the correct way to net out the market path — and shares no options input, so the residual is genuinely "beyond beta + vol."

## 18. Final Verdict

**weak_support.** After removing the market move (QQQ beta 1.16) and VIX, COR1M < 8 still adds about −1.67% of incremental QQQ drawdown with a bootstrap CI off zero — a genuine concentration-specific residual, not pure beta. But episode-level power is absent (N=8, permutation p 0.386), so the residual is suggestive rather than established.

## 19. Decision Impact

Keep COR1M as a **QQQ-specific** hedge input: the residual beyond beta+VIX justifies watching it for the concentrated index. Do not over-size — the residual is small (~1.7%) and underpowered. This answers the H-COR-003 open question affirmatively but weakly.

## 20. Other Experiments To Run

| Experiment ID | Proposed Experiment | Why Run It | Scope | Priority | Status |
|---|---|---|---|---|---|
| E-COR-008 | Real option-chain hedge cost (vs stylized BS) | turns the residual into a net-of-cost edge | needs option chain | high | data-blocked |
| E-COR-009 | Walk-forward out-of-sample as episodes accrue | the only cure for N=8 | needs more episodes | high | data-blocked |

## 21. Independent Persona Commentary

> Human-readable excerpt of [commentary.json](../outputs/commentary/round2/H-COR-006.json) (written for round 2).

### Persona — `cio`

Interpret: This is the result I needed to keep COR1M on the board — the QQQ effect is not merely "tech moves more." A −1.67% residual after stripping beta and vol is small but it's the signature of something concentration-specific, which is exactly the risk I worry about in a top-heavy market.

Act: COR1M stays a sanctioned QQQ-sleeve hedge input. I accept it is small and underpowered; I size accordingly and revisit as episodes accrue.

### Persona — `quant`

Interpret: The regression residual is honest — the market path is netted out contemporaneously, VIX is controlled, and the CI is off zero. But the episode-level permutation at p 0.386 is the number that governs: with 8 independent events I cannot certify this. The day-level CI borrows strength from overlapping windows.

Act: weak_support, not stronger. I will not endorse any sizing that assumes significance. The decision-moving tests (real cost, walk-forward) are data-blocked, so the honest move is to stop refining in-sample and wait for out-of-sample episodes.

### Persona — `portfolio-manager`

Interpret: A ~1.7% concentration-specific drawdown edge on QQQ, surviving beta and vol, is enough to justify a small protective tilt but not a standalone program. The data-blocked cost test matters to me most — a stylized put helped QQQ by +0.50% gross, but real spreads could erase that.

Act: Run a minimal QQQ hedge tilt on COR1M<8, premium-capped, and flag E-COR-008 (real cost) as the gate before any scale-up.

## 22. Reproduction

```bash
PY=.venv/bin/python
$PY scripts/cor1m_round3_experiments.py   # E-COR-005 beta-adjusted OLS + bootstrap CI
```

Artifacts: [outputs/cor1m_round3_results.txt](../outputs/cor1m_round3_results.txt).

## 23. Next Step

Hold for out-of-sample episodes (E-COR-009) and real option-chain cost (E-COR-008); both are data-blocked today.

## 24. Feynman Explanation

**Paragraph 1 — What is this signal?** The tech index naturally swings more than the broad market — about 1.16 times as much. So when any market-wide warning fires, tech looks like it reacts more just because it's bouncier. We wanted to know if there's something *extra* in tech beyond that bounciness.

**Paragraph 2 — What did the test show?** Even after we subtracted out the normal market move and the fear level, the crowding flag still left a small extra dent in tech — about 1.7%. Small, but it didn't disappear.

**Paragraph 3 — Why does this matter?** It means COR1M is catching something specific to the crowded tech names, not just repackaging "the market is jumpy." That's why we keep it for tech hedging and not for the broad market.

**Paragraph 4 — What would a curious person ask next?** "Is 1.7% on only eight events real, or just a wiggle?" Honest answer: we can't be sure with so few events — we need to watch new ones as they happen. In your own words: there's a small genuine tech-only signal here, worth a light hedge, but the jury's still out until we see more.
