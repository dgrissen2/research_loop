# Plan — COR1M concentration measure & over-bulled hedge trigger

Execution roadmap for goal `cor1m-concentration-hedge`. Drives the `research-hypothesis-maintainer`
loop (`/goal goals/cor1m-concentration-hedge/goal.md`) toward the accepted [facts.md](facts.md) under a
**round cap of 7**, with the **CIO / Quant / Portfolio Manager** panel.

## Solution approach

This is a research loop, not a feature build. The repo already ships the analysis engine
(`scripts/cor1m_concentration_analysis.py` + `cor1m_round2/3/4_experiments.py`) and the enforced back-half
gate (`.claude/skills/_research_loop/`). The work is to (1) **reconcile the shipped scripts to the agreed
facts**, (2) bind the three seed claims to stable IDs and run Phases 1–8 round by round, and (3) let the
gate (`verify_round.py`) enforce the per-round panel review + panel-proposed hypotheses every round until
the cap, ending in a finalized decision-maker memo.

Seed-claim → stable-ID binding (Phase 1 of the loop):

| Fact | Hypothesis | Stable ID |
|---|---|---|
| fact-2 | COR1M validly measures extreme concentration / crowding | `H-COR-001` |
| fact-3 | COR1M < 8 over-bulled tail is a usable forward hedge trigger (SPY, QQQ) | `H-COR-002` |
| fact-4 | COR1M tail adds edge beyond a VIX/vol baseline | `H-COR-003` |

## Ordered steps

### Step 1 — Confirm / refresh local data  *(fact-13)*
- Touches: `scripts/fetch_market_data.py` → `data/{cor1m,spy_ohlc,qqq_ohlc,vix_ohlc}.csv`, `outputs/data_coverage.txt`.
- Action: data already present (COR1M through 2026-06-02, latest 6.23 — currently sub-8). Re-run only if stale.
- **Verify:** `python3 scripts/fetch_market_data.py` exits 0; `data/cor1m.csv`, `data/spy_ohlc.csv`, `data/qqq_ohlc.csv`, `data/vix_ohlc.csv` exist and align on a common date range.

### Step 2 — Reconcile the analysis harness to the agreed facts  *(facts 5, 6, 7, 8)*
The shipped `cor1m_concentration_analysis.py` was authored with `HORIZONS=[10,21,63]`, instruments
`SPY/IWM/QQQ`, and `abs8`+`pctile` triggers. Align it to the facts:
- `HORIZONS = [5, 10, 21, 42]`  *(fact-7)*
- Primary instruments `["SPY", "QQQ"]`; IWM out of the primary tables  *(fact-6)*
- `ABS_THRESHOLD = 8`, treated as a **fixed seed** threshold — no optimization  *(fact-5)*
- Scoring per horizon emits **both**: forward **max drawdown vs unconditional base rate** AND **hit-rate / precision vs base rate** (add hit-rate/precision if not already computed)  *(fact-8)*
- Demote `pctile` from a seed trigger to a Round-2 robustness experiment (keeps fact-5 honest).
- **Verify:** run the script; output shows all four horizons {5,10,21,42}, both metrics (drawdown gap + hit-rate vs base rate) for SPY and QQQ, and no IWM row in the primary trigger tables.

### Step 3 — Phase 0→1: bind hypotheses, seed the index  *(fact-1, fact-14)*
- Confirm panel already done (`research_loop.yml` → `personas: [cio, quant, portfolio-manager]`, `round_cap: 7`).
- Write one findings-note stub per hypothesis (`hypothesis_tracking/h-cor-00{1,2,3}_<slug>_<date>.md`), each **backlinking to [facts.md](facts.md)**, and add **exactly one row per hypothesis** to `hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md` with backlinks and `Round = 1`.
- **Verify:** index has 3 `Hypotheses` rows (H-COR-001/002/003) with note + facts + script backlinks; each note frontmatter has `hypothesis_status: active`.

### Step 4 — Round 1 execution (Phases 2–5) for each active hypothesis
- `H-COR-001` (concentration validity): cross-sectional concentration-specificity via **QQQ-vs-SPY** contrast (IWM no longer available as the small-cap control — see Risks), plus available cross-checks (VIX, realized SPY/QQQ correlation/dispersion). Verdict capped per fact-9 (no external ground-truth).
- `H-COR-002` (trigger): COR1M<8 → forward max-drawdown and hit-rate/precision vs base rate at 5/10/21/42d on SPY & QQQ, with clustering-robust (moving-block bootstrap) and episode-level (one obs/episode) checks.
- `H-COR-003` (incremental vs VIX): low-VIX confound + OLS of forward drawdown on the trigger dummy controlling for VIX (`cor1m_round2_experiments.py` E-COR-002) — does the trigger coefficient survive?
- Each note records method, sample integrity (start/end/aligned N/warm-up/missing-data/sign), threats to validity, one verdict, and links its `scripts/` + `outputs/` artifacts.
- **Verify:** for each note — method table with pass criteria, results filled from `outputs/`, exactly one verdict in {supported, weak_support, mixed, not_supported, inconclusive}, Threats-to-Validity section present.

### Step 5 — Per-round back half (Phases 6–8) — **runs EVERY round, gate-enforced**
Canonical block (from RESEARCH_PROCESS.md), applied identically to rounds 1…7. For round `N`, for each **active** hypothesis:

```text
Phase 6  emit.py commentary --round N --hypothesis <ID>   # each confirmed persona reviews, independently
                                                           # (isolated call) + its cross-model twin
Phase 7  the note's verdict/decision + backlinks are complete; "Other Experiments" copied to the index
Phase 8  emit.py proposals  --round N                      # each persona proposes new hypotheses/experiments
         synthesize.py      --round N                      # → one decisions[]; classify each + reason
         promote.py         --round N                      # materialize promote/experiment decisions
Close    verify_round.py    --round N                      # MUST exit 0; the Stop hook also runs it
```
`verify_round.py` blocks round N from closing unless every active hypothesis has a per-persona
`commentary.json` (Phase 6), a valid `proposals.json` + `synthesis.json` with full
coverage/traceability/materialization (Phase 8, ≥ `K`=2 candidates unless `deferred`), resolved backlinks,
and a memo Timeline entry. Scripts are at `.claude/skills/_research_loop/` and run from the project root.
- **Verify (every round):** `python3 .claude/skills/_research_loop/verify_round.py --round N` exits `0`.

### Step 6 — Rounds 2…7: grow, reprioritize, converge toward the cap
- Panel-proposed items materialize as new notes/experiments; the shipped `cor1m_round2/3/4_experiments.py`
  supply ready candidates (threshold sweep E-COR-006, VIX confound E-COR-002, beta-control E-COR-005,
  episode-only re-inference E-COR-010, era-stability E-COR-011). Data-blocked items (real option-chain cost
  E-COR-008, walk-forward OOS E-COR-009) stay `deferred` with a reason.
- Update the **living** decision memo's Timeline at the end of every round (append-only).
- **Verify:** each round closes with `verify_round.py` exit 0; index `Round` column advances; memo Timeline gains one entry per round.

### Step 7 — Closure at the cap  *(fact-11)*
- On round 7 (the cap), **finalize** the decision-maker memo (`hypothesis_tracking/memo-<id>-*.md` from `DECISION_MAKER_MEMO_TEMPLATE.md`): timeline + final verdicts for H-COR-001/002/003 + a plain-language (Feynman) explanation, restating the best current decision (promote / research-only / stop).
- **Verify:** memo exists, links its source notes, and carries a verdict for each top hypothesis; round-7 `verify_round.py` exits 0.

## Risks & open questions

1. **Tiny, regime-concentrated sample.** Only ~8–9 trigger episodes, nearly all in 2024–2026 (per `cor1m_round4_experiments.py` E-COR-011). Cross-era stability essentially **cannot** be established — the Quant persona will (correctly) cap H-COR-002/003 at `weak_support` / regime-specific. This is the single biggest threat to a "usable trigger" verdict.
2. **Dropping IWM weakens H1.** The shipped concentration-specificity test contrasts a concentrated index against a low-concentration one (QQQ vs IWM). Facts put IWM out of scope, so H1 now leans on **QQQ-vs-SPY** only — a weaker concentration contrast. *Open question for the panel/user:* re-admit IWM as a **control-only** series (not a hedge target) to preserve the H1 contrast, or accept the weaker QQQ-vs-SPY test? Current plan: accept QQQ-vs-SPY, flag the limitation in the H-COR-001 note.
3. **Fixed knife-edge threshold.** `< 8` is held fixed (fact-5, no optimization) — honest, but threshold-sensitivity (sweep 6…10, E-COR-006) is a required robustness check so the verdict isn't a single-level artifact.
4. **H1 is data-limited by design.** No external concentration ground-truth locally (fact-9); H1's verdict may land `inconclusive`/`weak_support` until external data is fetched as a follow-up. That is an accepted, honest outcome, not a failure.
5. **Implied-vs-implied circularity.** COR1M and VIX are both options-implied; H-COR-003's realized price-path target (not an options target) is what keeps the "edge beyond VIX" test honest (contrast: E-COR-004).
