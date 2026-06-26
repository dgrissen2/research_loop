# Worked example — COR1M concentration & "over-bulled" hedge trigger

A complete, **dogfooded** run of research_loop on **real public data** — the kind of artifact the loop
produces end to end. It asks a genuine markets question and reaches a disciplined, **regime-bound negative**:
a promising signal that does **not** clear the bar for a sized trade.

> This example ships as a **reference**. It is **not** installed into your project by `install.sh` (the loop
> would otherwise treat it as prior work). Paths in the configs/notes are placeholders
> (`/path/to/...`, `.venv/bin/python`) — set them to your own when reproducing.

## The question

Does **COR1M** (CBOE 1-month implied correlation) measure extreme market concentration, and is its low
**"over-bulled" tail (COR1M < 8)** a *usable* forward hedge trigger for SPY / QQQ — judged by forward
drawdown and −5% breach rate vs the unconditional base rate, and against a VIX baseline?

## What the loop did

- **5 hypotheses** (`H-COR-001/002/003/006/007`) across a **2-round program** (round cap 7, **converged early
  at round 2** — the remaining decision-moving experiments were data-blocked).
- A confirmed **CIO / Quant / Portfolio-Manager** persona panel reviewed every finding, each paired with a
  **cross-model Codex twin** (Phase 6), then proposed + synthesized the next round's backlog (Phase 8).
- Every round passed the `verify_round.py` gate; the program closed in a **finalized decision-maker memo**.

## The outcome

**Program verdict: `weak_support` → decision: hold as research-only.** The COR1M < 8 flag roughly **doubles**
the near-term −5% breach rate (QQQ ~2.0×, SPY ~1.7×) and precedes deeper drawdowns — but it is **not
statistically significant** once episode clustering is accounted for (~8 episodes, almost all 2024–2026), and
it adds information **beyond VIX only for the concentrated index (QQQ)**. Usable as a small, QQQ-skewed hedge
**watch-flag**, not a sized standalone trigger.

| Hypothesis | Verdict |
|---|---|
| H-COR-001 — COR1M measures concentration (QQQ penalised > SPY) | `weak_support` |
| H-COR-002 — COR1M < 8 is a usable hedge trigger | `weak_support` |
| H-COR-003 — adds edge beyond VIX | `mixed` (QQQ yes, SPY no) |
| H-COR-006 — the QQQ penalty is concentration, not just beta | `weak_support` |
| H-COR-007 — the effect generalizes beyond 2024–26 | `inconclusive` (regime-bound) |

## How to read it

| Path | What's there |
|---|---|
| [`hypothesis_tracking/memo-cor-concentration-hedge_2026-06-17.md`](hypothesis_tracking/memo-cor-concentration-hedge_2026-06-17.md) | the finalized **decision-maker memo** — start here |
| [`hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md`](hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md) | the master index — every claim, verdict, and backlink |
| `hypothesis_tracking/h-cor-00*.md` | the five findings notes (claim → method → results → verdict → Feynman) |
| [`goals/cor1m-concentration-hedge/`](goals/cor1m-concentration-hedge/) | the Plannotator goal package (interview, facts, plan, goal) |
| [`outputs/`](outputs/README.md) | the loop artifacts — `commentary/`, `proposals/`, `synthesis/`, `promotion_ledger.json`, results |
| [`scripts/`](scripts/README.md) | the analysis scripts + `fetch_market_data.py` |
| [`data/`](data/README.md) | the five input CSVs, with sources + attribution |

## Data & reproduction

All inputs are **public**: CBOE **COR1M** plus **SPY / QQQ / IWM / VIX** OHLC (Yahoo / Stooq), attributed in
[`data/README.md`](data/README.md) and re-fetchable with
[`scripts/fetch_market_data.py`](scripts/fetch_market_data.py). Each findings note's *Reproduction* block
lists the exact commands (`.venv/bin/python scripts/<…>.py`).

New here? Start with the repo [README](../../README.md) and
[Getting Started](../../framework/docs/GETTING_STARTED.md).
