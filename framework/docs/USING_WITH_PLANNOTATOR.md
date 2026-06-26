# Using research_loop with Plannotator

research_loop is **designed to be driven through [Plannotator](https://plannotator.ai)** and its goals
workflow. This is the recommended way to run the framework: you scope a research question into a *goal
package*, execute the loop through `/goal`, and use Plannotator's browser UI to read and annotate the
hypothesis docs as they grow.

> Don't have Plannotator? The installer offers to add it (`curl -fsSL https://plannotator.ai/install.sh | bash`).
> You can also run the loop standalone — see the appendix of [RESEARCH_PROCESS.md](RESEARCH_PROCESS.md).

---

## The workflow

### 1. Scope the question into a goal — `/plannotator-setup-goal`

```
/plannotator-setup-goal
```

Plannotator interviews you, builds a reviewed **fact sheet**, and produces a goal package under
`goals/<slug>/` (`interview.json`, `facts.md`, `plan.md`, `goal.md`).

In research_loop, this is **Phase 0**: state your **seed ideas**, agree a **round cap**, and let the
persona panel propose the **initial hypotheses**. Those agreed hypotheses + round cap become the goal's
**facts** — the shared, reviewed definition of what you're testing.

> 📷 *Screenshot pending (`assets/plannotator-facts-review.png`) — reviewing the seed hypotheses as goal
> facts before execution. See [assets/README](assets/README.md) to capture it.*
> <!-- TODO: link the example goal facts — examples/cor1m-concentration-hedge/goals/cor1m-concentration-hedge/facts.md -->

### 2. Execute the loop — `/goal`

```
/goal goals/<slug>/goal.md
```

> `/goal` is **Claude Code's native goal framework** — research_loop plugs into it; there's nothing extra
> to install for this step.

The `research-hypothesis-maintainer` skill runs the loop (Phases 1–8 of
[RESEARCH_PROCESS.md](RESEARCH_PROCESS.md)) round by round, writing findings notes, index rows, and — at
the round cap — a decision-maker memo. **Every findings note backlinks to the goal's facts**, so you can
always trace a verdict back to the question that motivated it.

> **Plan requirement (when `/plannotator-setup-goal` writes `plan.md`):** the generated plan **must include a
> "Per-round back half (Phases 6–8)" block that applies to *every* round, not just round 1** — copy the
> canonical block from [RESEARCH_PROCESS.md](RESEARCH_PROCESS.md#per-round-back-half-phases-68--runs-every-round-canonical-block).
> The gate enforces the per-round panel review + panel-proposed hypotheses regardless of the plan's wording,
> but the plan should state it once so the roadmap matches what the machinery does.

### 3. Read & loop on the hypothesis docs in Plannotator — `/plannotator-annotate`

Open any findings note, the index, or the memo in Plannotator's annotation UI to review and leave inline
feedback the skill can act on:

```
/plannotator-annotate hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md
/plannotator-annotate hypothesis_tracking/h-<prefix>-001_<slug>_<date>.md
```

> 📷 *Screenshot pending (`assets/plannotator-annotate-finding.png`) — leaving inline feedback on a
> hypothesis; the maintainer skill incorporates it on the next pass. See [assets/README](assets/README.md).*
> <!-- TODO: capture against the example — examples/cor1m-concentration-hedge/hypothesis_tracking/h-cor-001_*.md -->

### 4. Cross-model review (optional)

If Codex is installed, the loop routes findings through `/codex-strategy-review` for an independent
second opinion; you can also run it by hand on any note:

```
/codex-strategy-review hypothesis_tracking/h-<prefix>-001_<slug>_<date>.md --personas cio,quant
```

---

## How the pieces backlink

```
goals/<slug>/facts.md        (the question, as agreed facts)
      ▲  backlink
      │
hypothesis_tracking/
  ├── RESEARCH_HYPOTHESIS_INDEX.md   ←→  each findings note (one row per hypothesis)
  ├── h-<prefix>-001_*.md            →   scripts/  data/  outputs/  (the evidence)
  └── memo-<id>-*.md                 →   the findings note it summarizes
```

The goal's facts are the root; the index is the map; notes link to their evidence and back to the index;
the memo links to its note. Plannotator lets you walk these links visually and annotate any node.

---

## Tips

- Keep one hypothesis per findings note; the index is the place that ties the program together.
- Re-run `/plannotator-annotate` on the index between rounds to steer which follow-up experiments get
  promoted next.
- The round cap is your friend — it's a deliberate stopping point, not a limit you must hit.
- **Execution model (optional knob).** The producers' Claude leg runs as `claude -p` subprocesses by
  default; set **`claude_leg: subagent`** in `research_loop.yml` to run it as native in-session subagents
  instead (via `emit.py`'s `prompts` → `assemble` modes — **byte-identical** artifacts; needs an interactive
  session, so keep `subprocess` for headless / CI). Either way each producer run is `flock`-locked and writes
  atomically. See the [System & User Guide](SYSTEM_AND_USER_GUIDE.md) for the mechanics.
