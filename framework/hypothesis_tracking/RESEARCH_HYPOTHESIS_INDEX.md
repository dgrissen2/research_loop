# Research Hypothesis Index — `<PREFIX>`

Master tracker for this project's research claims, experiments, and outcomes.

Project scope: `<PROJECT_ROOT>`
ID prefix: `<PREFIX>` (set by the installer; see `research_loop.yml`)

Use this index to prevent drift between the hypothesis being tested, the data and method used, the
result, and the next experiment queue.

## Core Supporting Documents

- [HYPOTHESIS_FINDINGS_TEMPLATE.md](HYPOTHESIS_FINDINGS_TEMPLATE.md)
- [DECISION_MAKER_MEMO_TEMPLATE.md](DECISION_MAKER_MEMO_TEMPLATE.md)
- [RESEARCH_PROCESS.md](../docs/RESEARCH_PROCESS.md)
- [USING_WITH_PLANNOTATOR.md](../docs/USING_WITH_PLANNOTATOR.md)
- [SYSTEM_AND_USER_GUIDE.md](../docs/SYSTEM_AND_USER_GUIDE.md) — how the scripts + gate enforce the back half

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
| | | | | | | | | | | | |

## Follow-Up Experiments

| Experiment ID | Proposed Experiment | Why Run It | Scope | Parent Hypothesis | Source Note | Priority | Status |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
