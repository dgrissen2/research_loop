# Research Process — research_loop

**Version:** 1.1
**Updated:** 2026-06-23
**Scope:** Any project that installed research_loop.

This document defines the research-hypothesis loop end-to-end. It is **designed to run through the
Plannotator goals workflow** (`/plannotator-setup-goal` → `/goal`); a standalone path is in the appendix.

> **Enforcement (Phases 6–8).** The back half is **machine-gated**, not just described here: a round cannot
> close until `verify_round.py` (the `_research_loop` scripts) confirms the work from the on-disk artifacts.
> See [ADR 0001](../../docs/adr/0001-research-loop-enforcement.md) for the rationale and contract.

---

## The Loop At A Glance

```
Phase 0  SCOPE        /plannotator-setup-goal: idea → seed ideas → persona seed expansion → cap proposal
                      human confirms the round cap; accepted hypotheses become the goal's facts
   │
   ▼
Phase 1  DEFINE       classify each idea: hypothesis vs experiment; write the claim + why-it-matters
Phase 2  METHOD       define target/outcome, sample integrity, tests + pass criteria
Phase 3  EXECUTE      run analysis (code in scripts/, inputs in data/, artifacts in outputs/)
Phase 4  INTERPRET    what worked / didn't; threats to validity & confounds
Phase 5  VERDICT      one verdict + decision impact
Phase 6  COMMENTARY   persona panel reviews the finding (codex → gemini → in-Claude fallback)
Phase 7  RECORD       findings note + index row + backlinks; promote experiments as needed
Phase 8  NEXT ROUND   panel PROPOSES + SYNTHESIZES new hypotheses; reprioritizes the backlog
   │
   └────────────► repeat Phases 1–8 until the ROUND CAP — the LAST round — is reached, unless a
                  human-authorized early-termination record is written. UPDATE the living decision
                  memo's Timeline at the end of every round; FINALIZE the full memo on the last round
                  or authorized early-termination round.
```

Everything backlinks to everything. Every artifact is reachable from the index, and the index is
reachable from every artifact.

---

## Phase 0 — Scope (recommended front door: `/plannotator-setup-goal`)

This is how a research program *starts*. See [USING_WITH_PLANNOTATOR.md](USING_WITH_PLANNOTATOR.md).

1. **Seed ideas.** State the research question and any starting intuitions ("seed ideas"). These seed the
   persona panel. <!-- TODO: link a real example seed (see examples/cor1m-concentration-hedge/) -->
2. **Confirm the personas.** Decide which reviewer personas this goal uses. **There is no default panel** —
   the skill always confirms the set with you and **creates any that don't exist** (via its persona
   provisioning flow). The shipped CIO / Portfolio Manager / Quant avatars are only **samples** to start
   from, not a forced default.
3. **Persona panel expands the seed.** The confirmed personas propose the first set of falsifiable hypotheses
   from the seed ideas. The maintainer runs `emit.py seed --round 1 --context @<seeds>`, writing
   `outputs/seed_expansion.json`; when `codex: true`, that artifact includes a Codex twin attempt for every
   persona and is gated in round 1.
4. **Confirm the round cap after expansion.** The skill computes `M = distinct expanded hypotheses`, proposes
   `round_cap = M + headroom`, explains the breakdown, and asks you to confirm or revise it. This bounds the
   program and is recorded in the goal and in `research_loop.yml`. **Size it to leave room for hypotheses
   that only surface mid-program** — the cap bounds the program; it is *not* a budget to be spent entirely on
   the initial seed set. A program that runs Phases 1–8 will keep generating new, panel-proposed hypotheses,
   and those need rounds to be tested. Treat extending the cap as an explicit, allowed decision (see
   Guardrail 4), not a drift.
5. The agreed hypotheses + round cap become the goal package's **facts** (`goals/<slug>/facts.md`). Execute
   with `/goal goals/<slug>/goal.md`; every findings note produced will **backlink to these goal facts**.

> No Plannotator? Do Phase 0 in chat: state seed ideas, confirm/create the personas, agree a round cap,
> ask the panel to propose initial hypotheses. Then proceed.

---

## Phase 1 — Define (expand the seed, then classify)

First, **the confirmed persona panel expands the seed ideas into an explicit initial hypothesis set** and
agrees on it through the gated `outputs/seed_expansion.json` artifact. If Codex is enabled, each persona's
Claude pass is paired with its Codex twin attempt; a timeout/unavailable twin is recorded but non-blocking,
while a missing twin block fails the round-1 gate. Record every agreed hypothesis and follow-up experiment in
[RESEARCH_HYPOTHESIS_INDEX.md](../hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md) with backlinks **before**
moving on.

Then classify every idea:

| Question | Answer | Action |
|---|---|---|
| Can it fail independently and change a real decision on its own? | Yes | **Hypothesis** — new findings note + a row in the `Hypotheses` table |
| Is it "what if we tried X slightly differently" / one leg of an existing hypothesis? | Yes | **Experiment** — a row in `Follow-Up Experiments` only |
| Not sure? | — | **Experiment first.** Promote once it has its own pass criterion and decision impact. |

- **Hypothesis** = standalone falsifiable claim with a pass criterion, a method, and a decision that
  changes if it passes or fails.
- **Experiment** = a variation, robustness check, sub-question, or sweep subordinate to a hypothesis.
- One findings note = one primary claim.

## Phase 2 — Method & sample integrity

Fill the findings note: exact target/outcome definition, data/inputs, sample integrity & alignment (start,
end, aligned N, warm-up, missing-data policy, sign convention), variable definition, and a method table
with explicit pass criteria.

## Phase 3 — Execute

Run the analysis. **Conventional work locations (created by the installer):**

| Folder | Holds |
|---|---|
| `scripts/` | analysis code that produces each conclusion |
| `data/` | input datasets and shipped sample data |
| `outputs/` | generated result tables, figures, artifacts |
| `hypothesis_tracking/` | the written record (notes, index, memos) |

Link the exact `scripts/` and `outputs/` paths from the findings note so the code behind each result is
discoverable.

## Phase 4 — Interpret

Record what replicated, what it seems to measure, and **threats to validity & confounds** (leakage,
look-ahead, signal/outcome overlap, regime-specificity, multiple testing). State whether the comparison is
independent, partially dependent, or dependent.

## Phase 5 — Verdict & decision impact

Choose exactly one verdict — `supported` · `weak_support` · `mixed` · `not_supported` · `inconclusive` —
and state the decision impact (promote / hold research-only / stop / one narrow follow-up).

## Phase 6 — Persona commentary (Claude panel + cross-model twin)

Run the **in-Claude persona panel** on the finding — every confirmed persona gives two paragraphs
(interpret, then act). This panel **always runs.**

If a cross-model engine is available, run the **same panel again through it** — so each persona is reviewed
twice (Claude + its twin), i.e. **N personas × 2 passes**:

```
in-Claude persona panel        → ALWAYS runs (N personas)
plus, if available, its twin:
    if codex CLI  → run_codex_twin.py  (one codex call PER persona, run in PARALLEL — not grouped)
    elif gemini   → /gemini-review
```

The cross-model twin runs **each panelist as its own, parallel, individually-bounded codex call** (see
`_research_loop/run_codex_twin.py`), not one grouped call — grouping serializes all personas into a single
slow pass. Each per-persona call is process-group-scoped per the timeout rule below.

Then **synthesize**: merge the Claude and cross-model commentary per persona, mark where they **agree**
(higher confidence) and explicitly **flag disagreements** for human judgment. Disagreements are surfaced in
the findings note's commentary, not silently dropped.

> **Bounded + process-group-scoped (non-negotiable).** Every Codex/Gemini review step — Phase 6, the Phase 1
> seed reconciliation, and the Phase 8 proposal twin — runs under a **5-minute hard timeout per call**
> (`CODEX_TIMEOUT`, default 300s), enforced **inside the runner**: the bundled `run_codex_twin.py` (and the
> codex scripts) launch codex in its **own process group** and, on timeout, kill **only that group**
> (`killpg`).
> - It does **not** rely on a `timeout` binary (macOS has none).
> - It must **NEVER** terminate codex by name — no `pkill codex`, no `killall codex`. **Other agents/sessions
>   may be running codex concurrently;** only the child process group *this* step spawned may be killed.
> - On timeout: abort the pass, note "cross-model timed out" in the commentary, and continue with the
>   in-Claude panel result. A stuck Codex call must never block the loop or leave orphaned children.

The loop completes even with no cross-model engine — the cross-model twin is an enhancement, never a hard
dependency.

## Phase 7 — Record & promote

- Add **exactly one** `Hypotheses` row per findings note.
- Copy every "Other Experiments To Run" item into `Follow-Up Experiments`.
- **Promote** an experiment into a hypothesis (new ID) once it stands alone.
- **Backlink everything**, both directions.

## Phase 8 — Next round (propose → synthesize → reprioritize)

The persona panel does not just "review" — it actively grows and re-orders the research backlog. Run this as
a two-stage panel, mirroring Phase 6's Mode C (the in-Claude panel **always** runs; its cross-model twin
runs when available):

1. **Propose (each persona, independently).** Every confirmed persona reviews the round's findings and
   proposes **candidate new hypotheses and follow-up experiments**, and flags which *existing* open items
   should be de-prioritized, dropped, or promoted in light of what was just learned. If `codex: true` (or
   gemini is available), run the **same panel through the cross-model twin** so each persona proposes twice
   (Claude + twin) — `N personas × 2 passes`.
2. **Synthesize (across the panel).** Merge the proposals into a single agreed list: **de-duplicate**
   overlapping ideas, **mark agreements** (panel + twin converge → higher priority/confidence), and
   **explicitly flag disagreements** (Claude vs twin, or persona vs persona) for human judgment rather than
   dropping them. Classify each surviving item as hypothesis vs experiment (Phase 1 rule) and assign a
   **priority**. This synthesized, reprioritized backlog — not the raw proposals — is what gets recorded.

**Enforced by the gate.** Phases 6–8 run through the `_research_loop` scripts and are checked by
`verify_round.py` (see [ADR 0001](../../docs/adr/0001-research-loop-enforcement.md)): `emit.py` writes the
per-persona commentary (Phase 6) and proposals (Phase 8) as isolated, bounded calls — serialized by a
per-project `flock` (one producer at a time) and written atomically (temp + rename). The Claude persona leg
runs as a `claude -p` subprocess by default, or as in-session subagents under `claude_leg: subagent` (via
the `emit.py prompts` → `assemble` modes) — **byte-identical** artifacts either way, Codex twin unchanged. `synthesize.py`
assembles proposals into one `decisions[]` synthesis (convergence = one decision, many `sources`);
`promote.py` deterministically materializes `promote`/`experiment` decisions into notes/index rows + a ledger;
`verify_round.py` then confirms — from the artifacts — note completeness, backlinks, per-persona commentary,
Phase-8 coverage/traceability/materialization, the round-1 seed expansion, and the memo entry. **A round
closes only when the gate exits 0.** There is **no promotion quota**: the gate enforces that the
propose→synthesize→classify→materialize
*work* happened, not that anything was promoted — an honest round may set `synthesis.json`'s `deferred` flag
(with a reason) and promote nothing.

### Program-level convergence / early termination

`synthesize.py` may emit an advisory `termination_recommendation`:

```json
{"recommend": "continue|converge|stop", "reason": null, "data_blocked": []}
```

This recommendation never closes a program by itself. When the recommendation is `converge` or `stop`, the
maintainer skill must show the recommendation, reason, and data-blocked work to the user and ask whether to
apply the early stop. Only after explicit human authorization does the skill write the binding
`research_loop.yml` record:

```yaml
termination:
  status: terminated
  reason: "..."
  round: N
  authorized_by: "..."
```

The same decision must be recorded in the decision-maker memo, and the memo must be finalized for that
round. `verify_round.py` reads this record and enforces finalization; it does not decide to terminate on its
own.

This is distinct from per-round `deferred`. `deferred: true` means a round may close without promotions
because the proposed work is not decision-moving or is data-blocked. It does **not** end the program, does
not finalize the memo below the cap, and does not substitute for the human-authorized `termination:` record.

Record every agreed item in the index **with backlinks before the next round begins**. Then repeat
Phases 1–8 — **until the round cap is reached.** Because the panel keeps surfacing genuinely new hypotheses,
**the program must always leave room for rounds beyond the initial seeded set** so those new hypotheses are
actually tested and not just logged (see Phase 0 step 3 and Guardrail 4).

**The decision-maker memo is a living document** — not a one-time write-up at the end. Create the
[decision-maker memo](../hypothesis_tracking/DECISION_MAKER_MEMO_TEMPLATE.md) after the first round, then
update it every round under **two rules**: (1) **append-only — the §4 Timeline**: add this round's row(s)
with the `Round` cell set to N, never editing a prior row; (2) **rewrite to the current verdict —
§1/§3/§5/§7**: restate the executive summary, findings, decision, and Feynman so the body never contradicts
the header (never overwrite a prior *outcome* — when a verdict changes, say so and why). The memo carries a
machine-checkable header — `Status`, `Verdict`, `Decision`, each on its own line — that the gate parses.
**On the last round (the round cap), finalize:** do that §1/§3/§5/§7 rewrite to the final verdict **and flip
`Status` to `final`** — finalization is that rewrite plus the Status flip, *not* merely appending a Feynman
section. If a human-authorized early termination is recorded, finalize in that termination round instead.
("Last round" = whatever cap you chose; there is nothing special about any particular number.) On a
finalizing close, `verify_round.py` prints the absolute `MEMO:` and `INDEX:` paths and the maintainer skill
offers to open both in Plannotator.

### Per-round back half (Phases 6–8) — runs EVERY round (canonical block)

This is not a round-1-only ritual; it runs **identically every round** and the gate enforces it every round.
A plan need not re-describe rounds 2…N — **paste this block once and treat it as applying to every round.**
For round `N`, for each **active** hypothesis:

```text
Phase 6  emit.py commentary --round N --hypothesis <ID>   # each confirmed persona reviews, independently
                                                           # (isolated call) + its cross-model twin
Phase 7  the note's verdict/decision + backlinks are complete; "Other Experiments" copied to the index
Phase 8  emit.py proposals  --round N                      # each persona proposes new hypotheses/experiments
         synthesize.py      --round N                      # → one decisions[]; classify each + reason;
                                                           # may include advisory termination_recommendation
         promote.py         --round N                      # materialize promote/experiment decisions
Close    verify_round.py    --round N                      # MUST exit 0; the Stop hook also runs it
```

`verify_round.py` will **block round N from closing** unless, for round N: every active hypothesis has a
per-persona `commentary.json` (Phase 6), a valid `proposals.json` + `synthesis.json` with full
coverage/traceability/materialization (Phase 8, ≥ `K` candidates unless `deferred`), resolved backlinks, and
a memo Timeline entry. **So even a terse plan cannot skip the per-round panel review or the per-round
panel-proposed hypotheses** — the machinery applies this block uniformly to rounds 2…N.

---

## Guardrails (non-negotiable)

1. **Follow the loop in order.** Do not jump to a verdict before method + execution + interpretation exist.
2. **Index before advancing.** Every new hypothesis/experiment is written to the index *with backlinks*
   before the next round begins.
3. **Stable IDs, immutable outcomes.** `H-<PREFIX>-001` / `E-<PREFIX>-001`; never overwrite a result —
   append new evidence and note the change.
4. **Respect the round cap — but always leave room for new hypotheses.** Stop at the agreed number of
   rounds unless the user explicitly authorizes program-level early termination through the maintainer skill.
   The cap is set (Phase 0) above the initial seed set precisely so that hypotheses surfaced mid-program in
   Phase 8 get their own rounds to be tested, not merely logged. If the panel is still proposing and
   confirming genuinely new hypotheses as the cap approaches, **extending the cap is the correct deliberate
   decision** — recorded in `research_loop.yml` and the goal — not a drift to be avoided. A per-round
   `deferred` decision is not early termination.
5. **One note per claim.** Keep notes focused.
6. **Honest negatives.** A clean negative result is a finding, not a documentation failure.
7. **Backlink everything.** Notes ↔ index ↔ goal facts ↔ scripts/data/outputs.
8. **Cross-model calls are time-boxed AND process-group-scoped.** Every Codex/Gemini step runs under a
   5-minute hard timeout enforced inside the runner, which kills **only the process group it spawned**
   (`killpg`) — **never `codex` by name** (`pkill`/`killall` are forbidden; other agents may be running it).
   On timeout: abort, note it, continue with the in-Claude result; leave no orphaned children. The twin
   never blocks the loop.

---

## Roles

- **`research-hypothesis-maintainer` skill** — orchestrates the loop, writes notes/index/memo, enforces the
  guardrails, runs the persona panel, and manages persona provisioning.
- **Personas** — seed hypotheses (Phase 0/8) and review findings (Phase 6). Confirmed per goal (no forced
  default); CIO / Portfolio Manager / Quant ship only as samples, and the skill creates whatever personas
  the goal calls for via its provisioning flow.
- **Cross-model reviewers** — Codex / Gemini, optional.

## Appendix — Running standalone (no Plannotator)

The loop works without the goals framework: ask the `research-hypothesis-maintainer` skill to start a
research loop, give it your seed ideas and a round cap in chat, and it will run Phases 1–8 against
`hypothesis_tracking/` directly. You lose the goal package's facts/plan scaffolding and the
browser-based review, but the artifacts and discipline are identical.
