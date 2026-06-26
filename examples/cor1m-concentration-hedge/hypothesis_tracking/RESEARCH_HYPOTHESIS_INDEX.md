# Research Hypothesis Index — `COR`

Master tracker for this project's research claims, experiments, and outcomes.

Project scope: `/path/to/cor1m-concentration-hedge` (goal: [cor1m-concentration-hedge](../goals/cor1m-concentration-hedge/goal.md))
ID prefix: `COR` (set by the installer; see `research_loop.yml`)

Use this index to prevent drift between the hypothesis being tested, the data and method used, the
result, and the next experiment queue.

## Core Supporting Documents

- [HYPOTHESIS_FINDINGS_TEMPLATE.md](HYPOTHESIS_FINDINGS_TEMPLATE.md)
- [DECISION_MAKER_MEMO_TEMPLATE.md](DECISION_MAKER_MEMO_TEMPLATE.md)
- [RESEARCH_PROCESS.md](../../../framework/docs/RESEARCH_PROCESS.md)
- [USING_WITH_PLANNOTATOR.md](../../../framework/docs/USING_WITH_PLANNOTATOR.md)
- [SYSTEM_AND_USER_GUIDE.md](../../../framework/docs/SYSTEM_AND_USER_GUIDE.md) — how the scripts + gate enforce the back half

## Maintenance Rules

1. Every new findings note adds **exactly one** row to the `Hypotheses` table.
2. Every item in a note's `Other Experiments To Run` is also added to `Follow-Up Experiments` below.
3. If a follow-up experiment becomes a standalone claim, **promote** it into `Hypotheses` with a new `Hypothesis ID`.
4. **Stable IDs:** hypotheses `H-<PREFIX>-001`, `H-<PREFIX>-002`, …; experiments `E-<PREFIX>-001`, …
5. **Never overwrite a prior outcome.** If a rerun changes the result, update the row and add the new artifact path or commit in `Best Evidence`.
6. **Backlinks are mandatory.** Every row links its note, its supporting docs, and its key files (scripts/data/outputs) — and the note links back here.
7. Every row states its `Scope` explicitly.
8. **Round (enforcement).** Every `Hypotheses` row carries the `Round` it is active/tested in (Phase-8-created
   rows carry `current_round + 1`). The note's frontmatter `hypothesis_status` (`active`/`deferred`/`dropped`)
   is the gate's lifecycle authority; the `Status` column here is the human-facing outcome/verdict.

## Hypotheses

| Hypothesis ID | Claim | Primary Signal/Variable | Primary Target/Outcome | Scope | Note | Supporting Docs | Supporting Files | Status | Best Evidence | Next Step | Round |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H-COR-001 | COR1M low tail measures concentration (QQQ penalised more than SPY) | COR1M < 8 | 21d path-min drawdown gap, QQQ vs SPY | SPY, QQQ; local | [h-cor-001](h-cor-001_concentration-validity_2026-06-17.md) | [facts](../goals/cor1m-concentration-hedge/facts.md) | [analysis](../scripts/cor1m_concentration_analysis.py) | weak_support | monotone threshold sweep; QQQ gap +3.02% > SPY +1.20% | re-admit IWM control (E-COR-101) | 1 |
| H-COR-002 | COR1M < 8 is a usable forward hedge trigger | COR1M < 8 | 21d/42d drawdown & −5% breach vs base rate (SPY, QQQ) | SPY, QQQ; local | [h-cor-002](h-cor-002_overbulled-hedge-trigger_2026-06-17.md) | [facts](../goals/cor1m-concentration-hedge/facts.md) | [analysis](../scripts/cor1m_concentration_analysis.py) | weak_support | breach lift SPY 1.74×/QQQ 2.01×; bootstrap p 0.23/0.13 (NS) | out-of-sample tracker (E-COR-103) | 1 |
| H-COR-003 | COR1M < 8 adds edge beyond VIX | COR1M < 8 controlling VIX level | 21d path-min drawdown OLS coefficient | SPY, QQQ; local | [h-cor-003](h-cor-003_edge-beyond-vix_2026-06-17.md) | [facts](../goals/cor1m-concentration-hedge/facts.md) | [round2](../scripts/cor1m_round2_experiments.py) | mixed | QQQ b1 −3.24% CI[−6.08,−0.34]; SPY CI spans 0 | beta control (E-COR-105) | 1 |
| H-COR-006 | The QQQ over-bulled penalty is concentration, not just beta | COR1M < 8 controlling SPY dd + VIX | QQQ 21d path-min drawdown OLS coef | QQQ; local | [h-cor-006](h-cor-006_the-qqq-over-bulled-penalty-is-concentration-not_2026-06-17.md) | [facts](../goals/cor1m-concentration-hedge/facts.md) | [round3](../scripts/cor1m_round3_experiments.py) | weak_support | trigger coef −1.67% CI[−3.14,−0.15] survives beta+VIX; episode permutation p=0.39 | data-blocked (E-COR-009 OOS) | 2 |
| H-COR-007 | The COR1M<8 effect generalizes beyond the 2024-2026 regime | COR1M < 8, era-split | 21d drawdown effect by era | SPY, QQQ; local | [h-cor-007](h-cor-007_the-cor1m-8-effect-generalizes-beyond-the-2024-2_2026-06-17.md) | [facts](../goals/cor1m-concentration-hedge/facts.md) | [round4](../scripts/cor1m_round4_experiments.py) | inconclusive | 7/8 episodes 2024-26; in-regime coef −1.84% CI off 0; pre-2024 untestable | data-blocked (E-COR-009 OOS) | 2 |

## Follow-Up Experiments

| Experiment ID | Proposed Experiment | Why Run It | Scope | Parent Hypothesis | Source Note | Priority | Status |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
| E-COR-107 | Re-admit IWM as a control-only low-concentration reference | Converged across 2 proposer(s): cio/claude, portfolio-manager/claude. | — | H-COR-001 | synthesis | high | planned |
| E-COR-108 | Out-of-sample tracker for new COR1M<8 episodes | Converged across 2 proposer(s): portfolio-manager/claude, quant/claude. | — | H-COR-002 | synthesis | high | planned |
| E-COR-109 | Family-wise multiple-testing correction across ETF x horizon x trigger | Converged across 1 proposer(s): quant/claude. | — | H-COR-002 | synthesis | medium | planned |
| E-COR-110 | Stylized protective-put hedge P&L at episode entry, net of cost | Converged across 1 proposer(s): portfolio-manager/claude. | — | H-COR-002 | synthesis | medium | planned |
