# Goal — COR1M concentration measure & over-bulled hedge trigger

Run the `research-hypothesis-maintainer` loop, reviewed by a confirmed **CIO / Quant Analyst /
Portfolio Manager** panel, to determine (1) whether **COR1M** is a valid measure of extreme market
concentration / single-stock crowding, and (2) whether its low **"over-bulled" tail (COR1M < 8)** is a
*usable* forward hedge trigger for SPY and QQQ — judged by forward max-drawdown and hit-rate vs the
unconditional base rate, and against a VIX/vol baseline. The program runs under a **7-round cap** and ends
in a finalized decision-maker memo.

## Shared understanding
The agreed, reviewed definition of what we're testing — the three seed hypotheses, the trigger definition,
indices, success metrics, scope, and guardrails — is the fact sheet:

- [facts.md](facts.md)

## Execution plan
The ordered steps, the files/scripts each touches, per-step verification, the gate-enforced per-round back
half (Phases 6–8), and the known risks:

- [plan.md](plan.md)

Supporting framework docs: [RESEARCH_PROCESS.md](../../../../framework/docs/RESEARCH_PROCESS.md) ·
[USING_WITH_PLANNOTATOR.md](../../../../framework/docs/USING_WITH_PLANNOTATOR.md) ·
[RESEARCH_HYPOTHESIS_INDEX.md](../../hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md)

## Done condition
All 7 rounds complete with `verify_round.py` exiting 0 each round; `H-COR-001/002/003` carry recorded
verdicts in `RESEARCH_HYPOTHESIS_INDEX.md` with full backlinks to their findings notes and evidence; and a
**finalized decision-maker memo** states the verdict and decision (promote / research-only / stop) for each
of the three hypotheses, every claim traceable back to [facts.md](facts.md).
