# Getting Started with research_loop

The 5-minute how-to: turn a research question into a tested, falsifiable, fully-backlinked record of what
you tried, what held up, and what to do about it. Best driven through
**[Plannotator](https://plannotator.ai)'s goals workflow** ([repo](https://github.com/backnotprop/plannotator)),
but it also runs standalone.

> 📓 **Want to see the finished product first?** Browse the worked example —
> **[`examples/cor1m-concentration-hedge/`](../../examples/cor1m-concentration-hedge/)** — a complete,
> dogfooded study (goal package, findings notes, index, decision memo) on real public data.

---

## 1. What got installed

| Path | What it is |
|---|---|
| `.claude/skills/research-hypothesis-maintainer/` | the **skill** that runs the loop |
| `.claude/personas/` | **sample** reviewer personas (CIO, PM, Quant) — starting points, not defaults |
| `hypothesis_tracking/` | your findings notes, the master index, the memo template, and `research_loop.yml` (config) |
| `scripts/` · `data/` · `outputs/` | your analysis code, inputs, and results |

Opt into **Codex** at install and three optional review skills also land: `codex-strategy-review`
(stress-test a finding with a second model), `codex-plan-review` (review a method *before* you run it),
`codex-review` (code diffs).

## 2. Run your first loop

```text
1.  /plannotator-setup-goal      → describe your question + a few "seed ideas" + a round cap (e.g. 2–3);
                                   the panel proposes the starting hypotheses (the goal's facts)
2.  /goal goals/<slug>/goal.md   → the loop runs round by round: each hypothesis gets a findings note
                                   (claim → method → results → verdict → decision) + persona commentary,
                                   all recorded in the index — then it proposes next-round hypotheses
3.  Read the results             → hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md (the map)
                                   + the decision-maker memo (plain-language roll-up + Feynman explanation)
```

**First run** confirms two things with you: a short **ID prefix** (e.g. `COR` → stable IDs `H-COR-001`) and
the **persona set** (there's no default panel — it confirms and creates whichever you choose; CIO/PM/Quant
are just samples).

> ▶ See what step 1 produces:
> **[`…/goals/cor1m-concentration-hedge/`](../../examples/cor1m-concentration-hedge/goals/cor1m-concentration-hedge/)**
> — `interview.json` + `facts.md` are the seeded hypotheses + round cap.

**No Plannotator?** Tell Claude: *"Use the research-hypothesis-maintainer skill to start a research loop on
`<your question>`."* Same loop, same artifacts — you just lose the guided setup and point-and-click review.

## 3. The discipline that makes it useful

- **Hypothesis vs experiment** — a *hypothesis* is a standalone falsifiable claim that changes a decision; an
  *experiment* is a sub-question under one (promoted to a hypothesis when it can stand alone).
- **One note per claim**, one verdict (`supported` … `inconclusive`), one decision impact.
- **Backlink everything** — note ↔ index ↔ goal ↔ `scripts/`/`data/`/`outputs/`; the code behind any result
  is one click away.
- **Stable IDs, immutable outcomes** — never overwrite a past result; append new evidence.
- **Enforced by code** — a Claude Code **Stop hook** runs `verify_round.py` and won't let a round close until
  the on-disk artifacts prove the work happened. (Mechanics: [SYSTEM_AND_USER_GUIDE.md](SYSTEM_AND_USER_GUIDE.md).)

## Where to go next

- **[The worked example](../../examples/cor1m-concentration-hedge/)** — read a real, finished loop end to end
  (runs on real public data, re-fetchable via its `scripts/`).
- [USING_WITH_PLANNOTATOR.md](USING_WITH_PLANNOTATOR.md) — the goals-driven workflow in detail.
- [RESEARCH_PROCESS.md](RESEARCH_PROCESS.md) — the full versioned process and guardrails.
- [SYSTEM_AND_USER_GUIDE.md](SYSTEM_AND_USER_GUIDE.md) — how the scripts + Stop-hook gate enforce the back half.
