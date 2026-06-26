---
name: research-hypothesis-maintainer
description: "Run and maintain the research_loop hypothesis loop in this project: create/update findings notes and the hypothesis index from templates, run the seeded round-capped persona panel, provision custom personas, route cross-model review, and produce decision-maker memos. Use when the user wants to start a research loop, write a hypothesis/findings note, update the index, add a persona, or summarize a research verdict. Designed to run inside a Plannotator goal (/goal)."
---

# Research Hypothesis Maintainer

Orchestrates the research_loop process (see `docs/RESEARCH_PROCESS.md`) for **this project**. Generic and
project-agnostic: all project specifics come from config, not hardcoded values.

> **Back-half enforcement.** Phases 6–8 are machine-gated by the `_research_loop` scripts (`contracts.py`,
> `emit.py`, `synthesize.py`, `promote.py`, `verify_round.py`): a round closes **only when
> `verify_round.py` exits 0**. Rationale + contract: [ADR 0001](../../../docs/adr/0001-research-loop-enforcement.md).
> The per-phase wiring is in Mode A (below).

## Configuration — read this first

Read `hypothesis_tracking/research_loop.yml` (written by the installer). It provides:

```yaml
prefix: COR              # hypothesis/experiment ID prefix → H-COR-001 / E-COR-001
prefix_confirmed: false  # the installer does NOT ask for the prefix; you confirm it on first use
project_root: /abs/path  # project root
personas: []             # the CONFIRMED panel for the goal — empty until you confirm it; NOT a default.
                         # CIO / Portfolio Manager / Quant ship in personas_dir only as SAMPLES.
personas_dir: .claude/personas               # where persona avatars live (or ~/.claude/personas if global)
codex: true|false        # whether the vendored codex skills were installed
round_cap: 3             # ROUNDS per program (NOT a hypothesis count): ~1 round covers the seed group
                         # (Phase 6 batches all active hypotheses together) + headroom rounds for Phase-8
                         # discoveries; extending it is an allowed decision
commentary_batch: true   # Phase 6: one batched persona/twin call reviews all active hypotheses (cheaper);
                         # set false for isolated per-hypothesis calls
emit_max_workers: 3      # max concurrent model calls in emit.py (1 = serial fallback); clamped to [1,8]
claude_leg: subprocess   # Phase 1/6/8 Claude leg: 'subprocess' (default — `claude -p`, headless-capable)
                         # or 'subagent' (in-session persona subagents; commentary is always batched;
                         # NOT headless — see Phases 1/6/8). The Codex twin is unchanged either way.
termination:             # optional, written ONLY after human authorization of early program termination
  status: terminated     # gate-recognized values: active|terminated
  reason: "..."          # non-empty human-facing reason
  round: 2               # round being closed early
  authorized_by: "..."   # user/person who authorized it
```

**Prime the prefix on first use.** The installer deliberately does not ask the user for an ID prefix (a new
user has no reason to know what it means). So on the FIRST run, if `prefix_confirmed` is `false` or absent:
briefly explain that hypotheses get stable IDs like `H-<PREFIX>-001`, show the provisional `prefix`, and ask
the user to keep or change it. Then write the chosen value back to `research_loop.yml` and set
`prefix_confirmed: true`. Do this once, before creating the first note.

**Always confirm the personas — never default.** Do not assume CIO/PM/Quant (those are only samples shipped
in `personas_dir`). When defining a goal (or on first standalone run), **confirm with the user which
personas the panel will use**, and **create any that don't exist** via Mode B before seeding. Write the
confirmed list to `personas:` in `research_loop.yml`. List what's available with the shared resolver:
`python3 .claude/skills/_research_loop/persona_registry.py --list`.

If the config file is missing entirely, derive sensibly: prefix from the project dir name (uppercased, ≤4
chars, confirm with the user), confirm the persona set (do not auto-use the samples), detect `codex` from
whether the `codex-strategy-review` skill is present, and ask the user for a round cap.

## Core artifacts (in `hypothesis_tracking/`)

- [RESEARCH_HYPOTHESIS_INDEX.md](../../hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md) — master tracker
- [HYPOTHESIS_FINDINGS_TEMPLATE.md](../../hypothesis_tracking/HYPOTHESIS_FINDINGS_TEMPLATE.md) — one note per claim
- [DECISION_MAKER_MEMO_TEMPLATE.md](../../hypothesis_tracking/DECISION_MAKER_MEMO_TEMPLATE.md) — the roll-up

Work locations: code in `scripts/`, inputs in `data/`, generated artifacts in `outputs/`.

---

## Mode A — Run the loop (seeded, round-capped)

Use when starting or continuing a research program.

### A0. Establish context

- **Inside a Plannotator goal?** If a `goals/<slug>/` package is present (or the user ran `/goal`), read its
  `goal.md` and `facts.md`. Treat the agreed hypotheses + round cap as the goal's facts. Every findings note
  and index row you create **backlinks to those goal facts**.
- **Verify the plan carries the per-round back half (inject if missing).** Read `goals/<slug>/plan.md`. It
  **must** contain the canonical **"Per-round back half (Phases 6–8) — runs EVERY round"** block (see
  `docs/RESEARCH_PROCESS.md`). If it's absent — or the plan only spells the back half out for round 1 — **add
  the canonical block to `plan.md`** before running any round, so the roadmap matches what the gate enforces
  on rounds 2…N. (The gate enforces it regardless; this keeps the plan honest.)
- **Provision the analysis environment — adapt to THIS machine.** Before running any analysis (A2 step 2),
  ensure a Python environment exists with the packages the `scripts/` import (e.g. `numpy`/`pandas`, plus
  whatever else they need). **Discover the machine's convention rather than assuming one:** check the
  project's `AGENTS.md` / `CLAUDE.md` (and `.vscode/launch.json`) for a venv location — e.g.
  `~/Dev/virtualenvs/<project>/` — and use it; otherwise create a project-local `.venv`. Create the env if
  absent and `pip install` the needed packages. **Never assume bare `python3` has scientific libraries** —
  run every analysis script with that environment's interpreter, and record the interpreter path in each
  note's **Reproduction** section so the run is reproducible on this machine.
- **Standalone?** Recommend `/plannotator-setup-goal` once. If the user declines, proceed: ask for **seed
  ideas** in chat; propose the round cap after seed expansion (A1.5).
- **Confirm the personas (always).** Before seeding, confirm the panel for this goal and create any missing
  personas (Mode B). Persist the confirmed set to `personas:` in `research_loop.yml`. Never silently use the
  samples.

### A1. Seed (Phase 0/1)

From the seed ideas, run the gated seed producer so the confirmed persona panel expands them into an
explicit initial hypothesis set:

```text
python3 .claude/skills/_research_loop/emit.py seed --round 1 --context @<seed-ideas-file>
```

This writes `outputs/seed_expansion.json`. If `codex: true`, each persona block must carry its Codex twin
attempt (`producer_status: ok|timeout|unavailable`); `verify_round.py` gates this artifact in round 1.
If `emit.py` exits with the twin circuit-breaker code (`7`), stop the loop and report the cumulative twin
failure to the user instead of continuing with silently degraded cross-model coverage.
(Under `claude_leg: subagent`, run the seed phase via the spawn-collect-assemble flow in **A5** instead of
this single command — same artifact, in-session persona subagents for the Claude leg.)

Review the expanded set with the user, classify each item (hypothesis vs experiment — see rule below), and
write the initial `Hypotheses` / `Follow-Up Experiments` rows with backlinks **before** running tests.

### A1.5. Propose and confirm the round cap

After seed expansion, compute `M = count(distinct expanded hypotheses)` from `seed_expansion.json` and the
accepted user edits. **The round cap counts ROUNDS, not hypotheses** — a single round tests the whole active
group together (Phase 6 reviews them in one batched pass), so the seed set is *covered* in **`R_cover`
rounds — normally 1** (all M tested in round 1; split into more only if you deliberately want to stage a
large set). On top of that add **`H` headroom rounds** for the follow-ups Phase 8 will surface:

```text
round_cap = R_cover (rounds to cover the M seed hypotheses; normally 1) + H (headroom rounds)
```

State the breakdown to the user verbatim, e.g. *"Seed expansion produced M=6 hypotheses, all tested together
in round 1 (R_cover=1); add H=3 headroom rounds for follow-ups → proposed round_cap = 4. Confirm or revise."*
Do not run round work until the cap is confirmed. Then **write** the confirmed integer to
`hypothesis_tracking/research_loop.yml` as `round_cap: <N>`, **re-read the file to confirm it persisted**
(the gate reads `round_cap` from there — not from the memo, so a memo-only cap is a bug), and reflect it in
the goal facts/plan when running inside Plannotator.

### A2. Per hypothesis, run Phases 1–7

For each active hypothesis this round:
1. Fill a findings note from the template (claim, target, sample integrity, variable def, method + pass
   criteria).
2. Execute the analysis; put code in `scripts/`, artifacts in `outputs/`; link exact paths.
3. Interpret: what worked / didn't; **threats to validity & confounds**.
4. Verdict (one of `supported|weak_support|mixed|not_supported|inconclusive`) + decision impact.
5. **Persona commentary is round-level, not per-hypothesis:** Phase 6 (A5) runs one batched pass over *all*
   active hypotheses and writes each `commentary/round<N>/<ID>.json`. Draft this note's own interpret/verdict
   here; do not invoke the panel per-hypothesis.
6. Record: add one `Hypotheses` row; copy every "Other Experiments To Run" item into `Follow-Up
   Experiments`; backlink both directions.

### A3. Next round (Phase 8 — propose → synthesize → reprioritize)

The panel doesn't just review — it grows and re-orders the backlog (two stages, mirroring Mode C):
1. **Propose** — each confirmed persona reviews the round's findings and proposes candidate new hypotheses +
   follow-up experiments, and flags existing open items to de-prioritize/drop/promote. If a cross-model twin
   is available, run the same panel through it (N × 2).
2. **Synthesize** — merge across the panel: de-duplicate, mark agreements (→ higher priority), explicitly
   flag disagreements for human judgment, classify each survivor (hypothesis vs experiment), assign priority.
   Record this **synthesized, reprioritized** backlog in the index with backlinks **before** the next round.

After recording the backlog, **update the living decision-maker memo for this round** (see A4).
If `outputs/synthesis/round<N>.json` contains
`termination_recommendation.recommend: converge` or `stop`, treat it as advisory only: tell the user the
recommendation, reason, and any `data_blocked` items, then ask whether to apply an early program stop.
Only if the user explicitly confirms, write the `termination:` block to `research_loop.yml` with exactly
`status`, `reason`, `round`, and `authorized_by`, and finalize the decision-maker memo in the same round.
If the user declines, leave `termination:` absent and continue until the cap or a later authorization.

**Repeat A2–A3 until the round cap — the last round — is reached.** Because the panel keeps surfacing
genuinely new hypotheses, the program must leave room for rounds beyond the seeded set so they are tested,
not just logged — if new hypotheses are still being confirmed as the cap nears, **extending the cap is the
correct deliberate decision** (record it in `research_loop.yml` + the goal), not a drift.

### A4. The decision-maker memo (living — updated every round, finalized on the last round)

The [decision-maker memo](../../hypothesis_tracking/DECISION_MAKER_MEMO_TEMPLATE.md) is a **living roll-up**,
not a one-time close-out (see RESEARCH_PROCESS.md Phase 8). It carries a machine-checkable header the gate
parses — `**Status:**` (`living` → `final`), `**Verdict:**` (exactly one of `supported` / `weak_support` /
`mixed` / `not_supported` / `inconclusive`), `**Decision:**`, each on its own line — so keep it resolved (no
`<…>` placeholders) from round 1 on.

- **After round 1**, create it for the top hypotheses from the template.
- **Every round, two update rules:**
  - **Append-only — §4 Timeline:** add this round's row(s) with the `Round` cell = N; never edit a prior row.
  - **Rewrite to the current verdict — §1 / §3 / §5 / §7:** restate summary, findings, decision, and Feynman
    to the verdict as it now stands, so the body never contradicts the header — especially when the decision
    flips (don't overwrite a prior *outcome*; say what changed and why). §1 states the verdict as **exactly
    one enum token**, the same as the header `Verdict`.
- **Finalize on the last round (the round cap) — or the round a human authorizes early termination:** do that
  §1/§3/§5/§7 rewrite to the final verdict **and flip `**Status:**` to `final`**. Finalize = that rewrite +
  the Status flip, *not* merely appending a Feynman section.

"Last round" is whatever cap was chosen — nothing special about any number. The gate enforces *structural*
finalization (resolved `Status: final` + a resolved `Verdict` echoed exactly once in §1, per memo); the
narrative quality is your responsibility.

### A5. Close the round (machine-enforced — non-negotiable)

The back half is gated by the `_research_loop` scripts; a round is **not** done until the gate passes.
**This runs identically EVERY round (rounds 2…N are the same as round 1)** — the gate applies it uniformly,
so never skip the per-round panel review or the per-round panel-proposed hypotheses. For each round, drive
the artifacts through:

```text
Phase 1  python3 .claude/skills/_research_loop/emit.py seed        --round 1 --context @<seed-ideas-file>
Phase 6  python3 .claude/skills/_research_loop/emit.py commentary --round N
         # one batched call per persona/twin covers ALL active hypotheses (default) and splits
         # into per-hid commentary/round<N>/<ID>.json. For strict per-hypothesis isolation set
         # commentary_batch: false; pass --hypothesis <ID> to (re)build a single note.
Phase 8  python3 .claude/skills/_research_loop/emit.py proposals  --round N --context @<round-findings>
         python3 .claude/skills/_research_loop/synthesize.py      --round N      # proposals -> decisions[]
         # (review/edit synthesis/round<N>.json: classify promote|experiment|defer|drop + reasons;
         #  if termination_recommendation is converge|stop, ask the user before writing termination:)
         python3 .claude/skills/_research_loop/promote.py          --round N      # materialize decisions
Close    python3 .claude/skills/_research_loop/verify_round.py     --round N
```

The table above is the **`claude_leg: subprocess`** (default) path — each `emit.py <phase>` runs the Claude
persona leg as a `claude -p` subprocess.

**`claude_leg: subagent` — Phases 1/6/8 only.** When the config sets `claude_leg: subagent`, the Claude
persona leg runs as **in-session subagents** instead of `claude -p`. Replace each `emit.py <phase>` line
above (`seed` / `commentary` / `proposals`) with the spawn-collect-assemble flow below;
`synthesize.py` / `promote.py` / `verify_round.py` are unchanged. (Commentary is always **batched** under
`subagent`; `commentary_batch: false` does not apply.)

1. **Freeze the prompts (read-only).** `emit.py prompts <phase> --round N [--context @<file>]` writes the
   scaffold `outputs/.claude_legs/<phase>_round<N>.json` and prints, per persona, its **frozen prompt**,
   plus the `run_id` and the records dir. No lock, no model call. (Commentary fails closed here above the
   batch size cap — fall back to `claude_leg: subprocess`.)
2. **Spawn the panel — ONE message, N persona subagents.** Spawn exactly one subagent per persona printed
   in step 1 (one persona avatar each, no shared transcript, Opus). Hand each **only its frozen prompt** and
   instruct it to **return ONLY the raw answer** in the phase's native format — seed: two paragraphs
   (interpret; then act); commentary: the by-hid JSON object; proposals: the `{candidates, reprioritize}`
   JSON. The harness **blocks** until all return (no relaunch window).
3. **Persist verbatim.** Write each subagent's output **exactly as returned** (Write tool — no edits, no
   interpolation) to `<records-dir>/<persona_id>.txt`. If a persona errored or returned an empty/garbled
   answer, **re-spawn that one persona exactly once**, then persist.
4. **Assemble once.** `emit.py assemble <phase> --round N --claude-legs @<scaffold>` fires **only** the
   Codex twins (from the frozen prompts), pairs them with the handed-off Claude legs, and writes the SAME
   artifacts the subprocess path would. A missing / empty / unparseable required leg → ContractError and
   the round fails (no silent persona drop).
5. **Close** via `verify_round.py --round N` (below).

> **Not headless.** `claude_leg: subagent` needs a live Claude Code session for step 2 — it cannot run in
> CI / `claude -p`. The Codex twin still runs standalone, and `claude_leg: subprocess` (the default)
> preserves full headless operation.

**Run each `emit.py` call exactly once and block on it.** It is slow (per-persona model calls + Codex twins)
and holds a per-project lock; a missing artifact *while it is still running* means it is working — do NOT
relaunch it. Only re-run a back-half producer when the gate punchlist names a specific missing/failed
artifact after a *completed* emit. **Under `claude_leg: subagent` the same run-once rule covers the whole
spawn-collect-assemble:** the harness already blocked on the persona subagents, so do not re-spawn the panel
or re-run `assemble` unless the punchlist names a specific missing artifact.

**Close the round only when `verify_round.py` exits 0.** Exit 2 prints a machine-keyed punchlist of exactly
what is missing — fix those items and re-run the *named* producer once (a genuine miss after a completed
emit, NOT an in-flight or busy run). `verify_round.py` exit 3 means a required JSON artifact is malformed.
`emit.py` exit 3 is different — another emit already holds the project lock (busy); wait, do not relaunch.
Exit 7 from `emit.py` means the cumulative twin circuit-breaker tripped; stop and report it to the user
before continuing. Under Claude Code the Stop hook runs this gate automatically and blocks ending the turn
on a non-zero exit; standalone, run it yourself as the final check.
**There is no
promotion quota** — a round may legitimately promote nothing if `synthesis.json` marks it `deferred` with a
reason (the gate enforces that the propose→synthesize→classify→materialize *work* happened, not that anything
was promoted).

### A6. Close out the program (final round only)

When the gate closes the **final** round — the round cap, or the round a human authorized early termination —
`verify_round.py` prints, after the `OK` banner, stable parseable lines for the artifacts the decision-maker
opens next:

```text
MEMO: <absolute path>     # one line per memo-*.md
INDEX: <absolute path>    # the research hypothesis index
```

On that close, tell the user the program is complete, surface both paths, and **offer** (don't assume) to
open them in Plannotator — mirror the gate's `MEMO:`/`INDEX:` lines verbatim so the paths shown are exactly
what it emitted:

> **Research program complete.** Final decision memo + hypothesis index:
> - memo: `<MEMO path>`
> - index: `<INDEX path>`
>
> Open them in `/plannotator-annotate`? (memo / index / both / skip)

If the user accepts, run `/plannotator-annotate <path>` for each chosen file. Non-final rounds close normally
and print no such block — there is nothing to finalize or open yet.

### Guardrails (enforce — see RESEARCH_PROCESS.md)

Follow the loop in order; index every new item with backlinks before the next round; stable IDs; never
overwrite outcomes; one note per claim; honest negatives; respect the round cap — but leave room for new
hypotheses (extending the cap is an allowed, recorded decision, not a drift).

---

## Mode B — Confirm & provision personas

### Confirm the set (always, when defining a goal)
There is **no default panel.** When a goal is being defined (or on first standalone run), confirm which
personas the panel will use — propose the shipped **samples** (CIO / Portfolio Manager / Quant) as options,
but let the user name any others. For every chosen persona that does **not** already have an avatar in
`personas_dir`, **create it** with the pipeline below before seeding. Persist the confirmed list to
`personas:` in `research_loop.yml`. This is re-invokable any time the user asks to add a persona.

### Per persona to create
1. **Interview** briefly: who they are, the lens they bring, what they push hardest on, domain/vocabulary.
2. **Ask** (once a persona is suggested): "Run web research to deepen this persona's build-out? [y/N]". If
   yes, use web search to gather the archetype's real frameworks, characteristic objections, vocabulary,
   and biases.
3. **If `codex: true`**, run `/codex-strategy-review` on the drafted persona for an independent cross-model
   critique; fold in the findings.
4. **Synthesize** a persona avatar markdown file in the registry format (frontmatter `id/name/aliases/
   domain/status/version` + body with worldview, what-you-stress-test, hard rules, in-the-loop, tone) and
   **save** it to `personas_dir`.
5. Add the new persona id to `personas:` in `research_loop.yml`.

---

## Mode C — Persona commentary (Claude panel + cross-model twin)

For persona commentary / stress-testing a finding (or reconciling the seed in A1):

1. **Always** run the **in-Claude persona panel**: read each confirmed persona avatar and produce two
   paragraphs (interpret, then act) per persona.
2. **If a cross-model engine is available, run the same panel through it** — one bounded, combined call:
   - **Codex** → `python3 .claude/skills/_research_loop/run_codex_twin.py <note> <out.md> --personas <confirmed>`.
     It runs **one codex call PER persona, all in parallel** (not one grouped call — grouping is slow). Each
     call is **bounded and process-group-scoped**: its own process group; on timeout (`CODEX_TIMEOUT`,
     default 300s) it kills **only that group** (`killpg`), records a per-persona fallback, and never blocks
     the loop. Prefer it over calling `/codex-strategy-review` directly in the loop — that wrapper runs
     generic + per-persona + synthesis sequentially (many `xhigh` passes).
   - else if gemini available → `/gemini-review <note>` (same 5-min bound).
   - **NEVER** terminate codex by name (`pkill codex` / `killall codex`) — other agents/sessions may be
     running codex concurrently; only ever kill the process group THIS call spawned.
   - **On timeout / unavailable:** continue with the in-Claude panel result and note "cross-model timed out".
3. **Synthesize**: merge per persona, mark agreements (higher confidence), and **explicitly flag
   disagreements** between the Claude and cross-model passes for human judgment. Record agreements and
   flagged disagreements in the note's commentary — never drop them silently.

The artifact shape is identical regardless of engine: one section per persona, two paragraphs each. The
in-Claude panel always runs; the cross-model twin is an enhancement, never a hard dependency.

---

## Hypothesis vs Experiment (classification rule)

| Question | Answer | Action |
|---|---|---|
| Can it fail independently and change a real decision on its own? | Yes | **Hypothesis** — note + `Hypotheses` row |
| "What if we tried X differently" / one leg of an existing hypothesis? | Yes | **Experiment** — `Follow-Up Experiments` row only |
| Unsure? | — | Experiment first; **promote** to hypothesis (new ID) once it has its own pass criterion + decision impact |

## Non-negotiable rules

- Exact target/outcome definition near the top of every note.
- Backlinks (not prose) for every supporting doc, dataset, and script — both directions, including the goal facts.
- One findings note = one primary claim.
- Separate signal definition · method · result · interpretation · decision impact.
- Stale results are rerun or explicitly labeled stale; never present stale metrics as current.
- Every "Other Experiments To Run" item also lands in the index.

## Final check before saving a note

ID · decision summary · exact target · sample integrity · supporting-doc + file backlinks (incl. goal
facts) · method table · results table · threats to validity · verdict · decision impact · other experiments
· persona commentary (one block per confirmed persona; agreements + flagged disagreements if a twin ran) ·
reproduction commands · Feynman explanation.
Index: one hypothesis row + all follow-up experiments copied over, all backlinked.
