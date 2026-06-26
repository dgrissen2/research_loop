---
id: H-COR-007
round: 2
hypothesis_status: active
phase: commentary
---

# H-COR-007 — Does the COR1M < 8 effect generalize beyond the 2024–2026 regime?

Promoted from round-1 synthesis (decision `era-stability`). Backlinks: [Index](RESEARCH_HYPOTHESIS_INDEX.md) · [goal facts](../goals/cor1m-concentration-hedge/facts.md) · [parent H-COR-002](h-cor-002_overbulled-hedge-trigger_2026-06-17.md)

## 3. Claim Being Tested

The forward-drawdown effect of COR1M < 8 is **not confined to the 2024–2026 regime** — it can be shown to hold (or at least to be testable) in earlier periods too.

## 4. Why This Matters

Every other verdict in this program (H-COR-001/002/003/006) rests on the same ~8 episodes. If those episodes are all one regime, none of the verdicts generalize and the whole signal is a 2024–2026 artifact. This is the load-bearing robustness question for the entire program.

## 5. Decision Summary

- Of 8 episodes with a full 21d window, **7 are 2024–2026 and only 1 is pre-2024** (2018-01-03).
- Within the 2024–2026 subsample the conditional effect is intact: trigger coef −1.84%, 95% CI [−2.86%, −0.34%] (off zero). But pre-2024 has **too few episodes to test** — cross-era stability **cannot be established**.
- Verdict: **inconclusive** for generalization. On this data the effect is, operationally, a 2024–2026 phenomenon; we cannot show it holds before, and cannot show it fails.

## 6. Target / Outcome Definition

Same 21d path-min drawdown effect (and the H-COR-006 conditional regression), partitioned by era: pre-2024 vs 2024–2026. Generalization ⇔ the effect is present and testable in **both** eras.

## 7. Data / Inputs Used

| Item | Source | Path | Date / Range | Notes |
|---|---|---|---|---|
| Trigger | Cboe COR1M | [data/cor1m.csv](../data/cor1m.csv) | 2018→2026-06-02 | abs8 |
| Outcome + controls | SPY/QQQ/VIX | [data/qqq_ohlc.csv](../data/qqq_ohlc.csv), [data/spy_ohlc.csv](../data/spy_ohlc.csv), [data/vix_ohlc.csv](../data/vix_ohlc.csv) | same | era-split regression |

## 8. Sample Integrity And Alignment

| Item | Value | Notes |
|---|---|---|
| Start | 2018-01-02 | |
| End | 2026-06-02 | |
| Episodes pre-2024 | **1** (2018-01-03) | far too few to estimate anything |
| Episodes 2024–2026 | **7** | all the statistical weight lives here |
| 2024–26 subsample | N=585 days | conditional trigger coef −1.84%, CI [−2.86%, −0.34%] |
| Missing-data policy | inner join | |
| Sign convention | effect "generalizes" only if present in both eras | |

## 10. Signal / Variable Definition

Era partition of the trigger and the H-COR-006 conditional regression; counts of trigger episodes per era; 2024–26-subsample bootstrap CI. Code: [scripts/cor1m_round4_experiments.py](../scripts/cor1m_round4_experiments.py) (E-COR-011).

## 11. Method

| Test ID | Method | Purpose | Window / Split | Pass Criterion |
|---|---|---|---|---|
| T1 | episode count by era | is there anything to test pre-2024? | pre-2024 vs 2024–26 | ≥ a few episodes each era |
| T2 | conditional regression on 2024–26 subsample | does the effect at least hold in-regime? | 2024–26 | CI off zero |

## 12. Results

| Test ID | Result | Effect Size | Statistical Support | Practical Read |
|---|---|---|---|---|
| T1 | **fails** | 1 pre-2024 vs 7 in 2024–26 | — | pre-2024 untestable |
| T2 | holds in-regime | trigger coef −1.84% | 95% CI [−2.86%, −0.34%] | effect lives in 2024–26 |

## 15. Threats To Validity And Confounds

- **Absence of evidence ≠ evidence of absence.** One pre-2024 episode means we cannot say the effect is absent earlier — only that it is untestable. Hence *inconclusive*, not *not_supported*.
- **Survivorship of the regime.** COR1M only printed sub-8 meaningfully in 2024–26 (the over-bulled, concentrated era); the signal and the regime are nearly the same event, so "does it generalize" may be unanswerable until COR1M re-enters the sub-8 zone in a different regime.
- This limitation propagates to **every** other verdict in the program — they are all 2024–26-weighted.

## 18. Final Verdict

**inconclusive.** The effect is intact and significant *within* 2024–2026 (trigger coef −1.84%, CI off zero), but with only one pre-2024 episode its behavior in other regimes simply cannot be estimated. We can neither confirm nor refute generalization; operationally the program's findings should be treated as **regime-bound to 2024–2026** until COR1M prints sub-8 in a structurally different market.

## 19. Decision Impact

Apply a **regime caveat to the whole program**: COR1M < 8 is a usable QQQ hedge flag *in the current concentrated regime*, with no evidence it travels. Do not extrapolate the verdicts to a different market structure. The decision-moving cure (out-of-sample episodes across regimes, E-COR-009) is data-blocked.

## 20. Other Experiments To Run

| Experiment ID | Proposed Experiment | Why Run It | Scope | Priority | Status |
|---|---|---|---|---|---|
| E-COR-009 | Out-of-sample / new-regime episodes as they print | only way to test generalization | needs more episodes | high | data-blocked |

## 21. Independent Persona Commentary

> Human-readable excerpt of [commentary.json](../outputs/commentary/round2/H-COR-007.json) (written for round 2).

### Persona — `cio`

Interpret: This is the caveat that frames everything else. A signal that only exists in one regime is a regime tool, not a law of markets. I'm comfortable using it *now*, in this concentrated tape, precisely because the regime it was found in is the regime we're in — but I won't pretend it's a permanent edge.

Act: Adopt COR1M as a current-regime hedge flag with an explicit "re-test when the regime changes" rider. No claim of durability in committee materials.

### Persona — `quant`

Interpret: One pre-2024 episode is zero degrees of freedom — the correct verdict is inconclusive, not not_supported, and certainly not supported. The 2024–26 in-regime CI off zero is real but it is in-sample to the regime; there is no out-of-regime split. Per my own rule, the absence of a valid out-of-sample split caps confidence.

Act: Mark the whole program 2024–26-bound. Forbid any backtest that quietly assumes cross-regime stability. The only thing that resolves this is genuine new episodes (E-COR-009), which we cannot manufacture.

### Persona — `portfolio-manager`

Interpret: For risk governance, "works in this regime, unknown elsewhere" is actually a workable posture — I hedge the regime I'm in. The trap is letting a 2024–26 edge harden into a permanent assumption in the risk model.

Act: Size COR1M-driven hedges to the current regime only, with a documented expiry/re-validation trigger if market breadth normalizes. Keep it out of any long-horizon strategic assumption.

## 22. Reproduction

```bash
PY=.venv/bin/python
$PY scripts/cor1m_round4_experiments.py   # E-COR-011 era split + 2024-26 subsample CI
```

Artifacts: [outputs/cor1m_round4_results.txt](../outputs/cor1m_round4_results.txt).

## 23. Next Step

Stand up the cross-regime out-of-sample log (E-COR-009) and re-test if/when COR1M prints sub-8 in a different market structure — data-blocked until then.

## 24. Feynman Explanation

**Paragraph 1 — What is this about?** We found a warning signal, but we noticed almost every time it ever fired was in the last two years. So we asked: is this a real, all-weather warning, or just something about *this* particular stretch of market?

**Paragraph 2 — What did we learn?** Out of eight warning events, seven were 2024–2026 and only one was earlier. With just one old example, we literally can't check whether it worked in the past — there isn't enough history to test.

**Paragraph 3 — Why does it matter?** It means we should trust the signal *for now*, in today's crowded market, but not assume it'll work in a totally different kind of market. It's like a tool tested only on sunny days — useful today, unproven in the rain.

**Paragraph 4 — What would you ask next?** "So when will we know if it's all-weather?" Only when the signal fires again in a different market and we see what happens. In your own words: it's a today-tool, not a forever-tool, and we won't know more until the market changes and it flashes again.
