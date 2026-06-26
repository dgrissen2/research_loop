---
id: H-<PREFIX>-___
round: <N>
hypothesis_status: active
phase: method
---

# Hypothesis Findings Template

Use **one document per primary claim**. Keep each findings note focused on a single hypothesis.

> **Frontmatter (required, enforced).** Every real note starts with the `---` block above:
> `id` (stable ID), `round` (the round this hypothesis is active/tested in — Phase-8-created notes
> carry `current_round + 1`), `hypothesis_status` (`active` / `deferred` / `dropped` — the gate's
> lifecycle authority), and `phase` (`method` → `execute` → `interpret` → `verdict` → `commentary` →
> `recorded`). `verify_round.py` reads these; do not omit them.

> Conventions (see `docs/RESEARCH_PROCESS.md`):
> - File name: `h-<prefix>-001_<short_slug>_YYYY-MM-DD.md` in `hypothesis_tracking/`.
> - Use **stable IDs** `H-<PREFIX>-001`; never overwrite a prior outcome — append new evidence.
> - **Backlink everything**: every supporting doc, dataset, and analysis script is linked, not described in prose.
> - Analysis code lives in `scripts/`, inputs in `data/`, generated artifacts in `outputs/` — link the exact paths.

## 1. Hypothesis ID

`H-<PREFIX>-___`

## 2. Short Title

One line.

## 3. Claim Being Tested

One sentence only. State a falsifiable claim.

> Example: `<signal X>` leads `<outcome Y>` by `1` to `7` periods.

## 4. Why This Matters

State the **decision** this would change if true. If nothing changes either way, this is not a hypothesis.

## 5. Decision Summary

In `2`–`4` lines:

- what the result says
- whether the hypothesis is usable, research-only, or rejected
- the immediate decision

## 6. Target / Outcome Definition

State the **exact** target or outcome series at the top of the document — units, horizon, and thresholds.

> Example: `outcome = 1` if `<metric>` crosses `<threshold>` within the next `N` periods.

## 7. Data / Inputs Used

| Item | Source | Path | Date / Range | Notes |
|---|---|---|---|---|
| Primary signal / variable | | | | |
| Comparison target / outcome | | | | |
| Alignment rule | | | | |

## 8. Sample Integrity And Alignment

State the exact testable sample and sign conventions.

| Item | Value | Notes |
|---|---|---|
| Start | | |
| End | | |
| Aligned observations | | |
| Warm-up / lookback handling | | |
| Missing-data policy | | |
| Sign / direction convention | | |

## 9. Supporting Documents And Files

Every findings note links all supporting `.md` documents and key files. These links must also be reflected in
[RESEARCH_HYPOTHESIS_INDEX.md](RESEARCH_HYPOTHESIS_INDEX.md).

### Supporting `.md` Documents

| Item | Path | Why It Supports This Note |
|---|---|---|
| Originating goal (if any) | | |
| Prior findings note | | |
| Plan / design doc | | |
| Review / audit doc | | |

### Supporting Files

| Item | Path | Type | Why It Supports This Note |
|---|---|---|---|
| Analysis script | `scripts/...` | code | |
| Input dataset | `data/...` | data | |
| Output artifact / result table | `outputs/...` | output | |

## 10. Signal / Variable Definition

Define the exact variable under test:

- formula
- source function or script (link the path under `scripts/`)
- any transformations

## 11. Method

| Test ID | Method | Purpose | Window / Split | Pass Criterion |
|---|---|---|---|---|
| T1 | | | | |
| T2 | | | | |
| T3 | | | | |

## 12. Results

| Test ID | Result | Effect Size | Statistical Support | Practical Read |
|---|---|---|---|---|
| T1 | | | | |
| T2 | | | | |
| T3 | | | | |

## 13. What Actually Worked

Short paragraph on what replicated across datasets, windows, eras, or methods.

## 14. What It Seems To Be Measuring

Short paragraph in plain English.

## 15. Threats To Validity And Confounds

State explicitly (domain-neutral):

- what could make this result an artifact rather than a real effect (leakage, look-ahead, overlap between the signal and the outcome, confounding, regime-specificity, multiple-testing)
- whether the signal and the outcome are **independent**, **partially dependent**, or **dependent** — and why
- what the strongest remaining objection is

## 16. What Did Not Hold Up

Be explicit: which tests failed, which effects were too small, which results were unstable or regime-specific.

## 17. Key Objections And How Well They Were Answered

| Objection | Answered? | Evidence |
|---|---|---|
| | | |

## 18. Final Verdict

Choose exactly one: `supported` · `weak_support` · `mixed` · `not_supported` · `inconclusive`.

Then `2`–`4` sentences explaining why.

## 19. Decision Impact

State what to do because of this result (promote / hold as research-only / stop / run one narrower follow-up).

## 20. Other Experiments To Run

Every row here must also be added to
[RESEARCH_HYPOTHESIS_INDEX.md](RESEARCH_HYPOTHESIS_INDEX.md) under **Follow-Up Experiments**.

| Experiment ID | Proposed Experiment | Why Run It | Scope | Priority | Status |
|---|---|---|---|---|---|
| E-<PREFIX>-___ | | | | `high`/`medium`/`low` | `planned` |

### Index Update Instruction

For every experiment row above: copy it into `Follow-Up Experiments` in the index, set `Parent Hypothesis`
to this note's ID, set `Source Note` to this file's path, and backlink both ways. If an experiment later becomes
a standalone claim, **promote** it into the `Hypotheses` table with a new `Hypothesis ID`.

## 21. Independent Persona Commentary

> **Generated, not hand-authored (D6).** The canonical record is
> `outputs/commentary/round<N>/<id>.json` (written by `emit.py commentary`). This section is a
> human-readable **excerpt** of that file with a backlink — regenerated by the loop; do not hand-edit.
> Backlink: [commentary.json](../outputs/commentary/round<N>/<id>.json)

One subsection per **confirmed persona for this goal** (the set agreed at goal setup and recorded in
`hypothesis_tracking/research_loop.yml` — there is no default panel). Each persona gives **exactly 2
paragraphs**: (1) interpret the result through that persona's lens; (2) state the concrete action that
follows. If a cross-model twin ran (Codex/Gemini), note per persona where the two **agree** and **flag any
disagreement**.

### Persona — `<persona-1>`

Paragraph 1: ...
Paragraph 2: ...

### Persona — `<persona-2>`

Paragraph 1: ...
Paragraph 2: ...

### Persona — `<persona-3>`

Paragraph 1: ...
Paragraph 2: ...

## 22. Reproduction

```bash
# exact commands — reference scripts/ and data/
```

Artifacts: linked file paths under `outputs/`, commit hash, output documents.

## 23. Next Step

One concrete next action only.

## 24. Feynman Explanation

*Plain-language explanation for a smart 12-year-old. No unexplained jargon. One everyday analogy per
paragraph. Four paragraphs.*

**Paragraph 1 — What is this signal/variable, in plain English?**
[What is being measured? One analogy from everyday life.]

**Paragraph 2 — What did the test show?**
[Did it work or fail, without statistics. One sentence on whether the effect was big or small.]

**Paragraph 3 — Why does this matter for the decision?**
[The decision context. What would someone do differently if this is real? One concrete scenario.]

**Paragraph 4 — What is the next question a curious person would ask?**
[The natural "but wait…" follow-up. Then: "Now explain it back in your own words — what is this actually measuring, and when would you trust it?"]
