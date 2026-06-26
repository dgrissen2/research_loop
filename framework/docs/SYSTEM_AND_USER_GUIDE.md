# research_loop — System & User Guide (the enforced back half)

**The one idea:** a round **cannot be marked done** until `verify_round.py` confirms — by reading the files
on disk — that the work actually happened. The model produces *judgment* (findings, persona reviews,
proposals, classifications); the *bookkeeping and the gate* are code. A Claude Code **Stop hook** runs the
gate and blocks ending the turn while a round is open and incomplete.

Companion docs: [RESEARCH_PROCESS.md](RESEARCH_PROCESS.md) (the loop, phase by phase),
[GETTING_STARTED.md](GETTING_STARTED.md) (5-minute intro),
[ADR 0001](../../docs/adr/0001-research-loop-enforcement.md) (why this design).

---

# Part 1 — Running a round

You work one **round** at a time: test the active hypotheses (Phases 1–5), then the back half runs
(Phases 6–8). The maintainer skill (`/goal`) drives it, but every step is a concrete artifact + a script:

```
Phase 1     emit.py seed        → outputs/seed_expansion.json   (round 1 only: panel+twin expand the seeds)
Phase 2–5   each hypothesis's findings note (claim → method → results → verdict)
Phase 6     emit.py commentary  → outputs/commentary/round<N>/<HID>.json   (per-persona review + twin)
Phase 8     emit.py proposals   → outputs/proposals/round<N>.json          (each persona proposes)
            synthesize.py       → outputs/synthesis/round<N>.json          (one decisions[] backlog)
            (review + classify each decision: promote | experiment | defer | drop + reason)
            promote.py          → new notes + index rows + promotion_ledger.json
Close       verify_round.py --round <N>     ← the gate. Close ONLY when it exits 0.
```

Under Claude Code the skill runs these for you, and the **Stop hook runs `verify_round.py`** and won't let
the turn end while the round is incomplete. To run by hand (scripts live at `.claude/skills/_research_loop/`):

```bash
RL=.claude/skills/_research_loop
python3 $RL/emit.py seed       --round 1 --context @<seed-ideas-file>   # Phase 1 (round 1 only)
python3 $RL/emit.py commentary --round 1                                # all active hypotheses + twins
python3 $RL/emit.py proposals  --round 1 --context @outputs/round1_findings.md
python3 $RL/synthesize.py      --round 1     # proposals → decisions[]; then edit classification + reason
python3 $RL/promote.py         --round 1     # materialize promote/experiment decisions
python3 $RL/verify_round.py    --round 1     # exit 0 = closeable
```

**Native-subagent leg (optional).** By default the producers' Claude calls are `claude -p` subprocesses. Set
`claude_leg: subagent` in `research_loop.yml` to run them as in-session subagents instead: `emit.py prompts
<phase>` freezes the prompt → the skill spawns one subagent per persona → `emit.py assemble <phase>` parses
the replies, fires the Codex twins, and writes the **byte-identical** artifact. Needs an interactive session;
keep `subprocess` for headless / CI.

## Reading the gate

| Exit | Meaning | What to do |
|---|---|---|
| **0** | Closeable | Done — move to the next round. |
| **2** | Incomplete | Read the punchlist (keyed by hypothesis / `phase8` / `memo`); fix each item; re-run. |
| **3** | Malformed | A required JSON file is invalid/empty; the message names the file + field. |

```
## verify_round — round 1: INCOMPLETE (2)
  [2] H-COR-001: missing required section: Threats To Validity
  [2] phase8: proposal candidates not covered by any decision: ['oos-validation']
```

## What "done" means (the rules the gate enforces)

- **Every active note is complete + backlinked** — target, sample integrity, method, results, threats,
  verdict (from the enum), decision impact, reproduction, Feynman, a persona-commentary excerpt; every link
  resolves.
- **Each confirmed persona reviewed it** — one block per persona in the round's `commentary.json`. When
  `codex: true`, each persona must carry a cross-model **twin attempt** — only a `timeout`/`unavailable`
  outcome is waved through (the loop never *blocks* on Codex, but a missing or wrong-engine twin fails exit 2).
  With codex off, the twin is skipped entirely.
- **Phase-8 work happened** — ≥ `K` proposal candidates on a non-deferred round; every candidate is *covered*
  by a synthesis decision; every decision traces back to a real proposing block; every `promote`/`experiment`
  decision was *materialized* (note/row + ledger entry).
- **No promotion quota** — a round may promote nothing if `synthesis.json` is `deferred` with a reason. The
  gate checks the *work and classification*, not that anything was promoted.
- **The memo gained this round's Timeline row** (and is finalized on the last round).

## The artifact you hand-edit: `synthesis/round<N>.json`

`synthesize.py` builds the `decisions[]`; you (or the skill) set each decision's classification + reason:

```jsonc
{ "round": 1, "deferred": { "is_deferred": false, "reason": null },
  "decisions": [ { "decision_key": "oos-validation",
                   "classification": "promote|experiment|defer|drop", "reason": "...",
                   "title": "...", "priority": "high", "parent": "H-COR-001|null",
                   "sources": [ { "persona_id": "quant", "engine": "claude", "candidate_key": "k" } ] } ] }
```

For a **deferred** round (nothing decision-moving), set `deferred.is_deferred: true` + a reason — the `K`
floor is waived and zero promotions pass, but you still must have *proposed* and *classified* every
candidate, so the gate knows the work happened. (Commentary/proposals shapes are defined + validated in
`contracts.py`'s loaders.)

## Personas: local vs global

In `research_loop.yml`:

```yaml
personas: [cio, quant, portfolio-manager]   # the confirmed panel for this goal
persona_source: local                        # 'local' (.claude/personas) or 'global' (~/.claude/personas)
persona_overrides: []                        # ids that stay local even under 'global'
K: 2                                          # min proposal candidates on a non-deferred round
```

Under **`global`**, confirmed personas resolve from `~/.claude/personas/` and **global wins** — a stray
same-id local file doesn't silently win; declare a deliberate `persona_overrides` entry. The gate's
provenance check fails (exit 2) if a record resolved `local` under `global` without being declared, so
`global` can't degrade to stale copies. Installing into an existing repo is **additive**: only adds loop
files, never touches existing `scripts/data/outputs`, and merges the Stop hook idempotently.

---

# Part 2 — How it's wired

## Layout

```
.claude/skills/_research_loop/   contracts.py (the contract layer) · emit.py (Phase 6/8 producers) ·
                                 synthesize.py · promote.py · verify_round.py (THE GATE) ·
                                 run_codex_twin.py · persona_registry.py
.claude/hooks/stop_verify_round.py   Stop hook → runs the gate on the open round
hypothesis_tracking/   the index, note + memo templates, research_loop.yml, the notes (h-*.md), memo-*.md
outputs/               commentary/round<N>/<HID>.json · proposals/round<N>.json ·
                       synthesis/round<N>.json · promotion_ledger.json
scripts/  data/        your analysis code + inputs
```

## Data flow (one round)

```
findings notes ──Phase 6──► emit.py commentary ──► commentary/round N/<HID>.json
               ──Phase 8──► emit.py proposals  ──► proposals/round N.json
                            synthesize.py       ──► synthesis/round N.json   (decisions[]; you classify)
                            promote.py          ──► new notes + index rows + promotion_ledger.json
                            verify_round.py ─reads─► notes + index + memo + the 3 JSON + ledger → exit 0/2/3
contracts.py validates every JSON and owns the markdown grammar (imported by all of the above).
The Stop hook runs the gate on **every started** round (an earlier incomplete round still blocks, even if a
later round has begun) and stops the turn on a non-zero exit.
```

## What each script does

| Script | Does | Key property |
|---|---|---|
| `emit.py` | each persona as an isolated, bounded call, once per engine; `commentary` (1 file/hypothesis), `proposals` (1 block/persona×engine) | per-project `flock` (one writer) + atomic writes; a timed-out engine → fallback record, never a crash or block |
| `run_codex_twin.py` | the Codex side — parallel per-persona calls, each its own process group | on timeout `killpg`s only that group (never `codex` by name) |
| `synthesize.py` | groups proposal candidates by `candidate_key` into one `decisions[]` | coverage + traceability hold by construction; you refine classifications |
| `promote.py` | materializes decisions → note stubs / index rows / ledger | idempotent (ledger-keyed) + atomic (temp + rename, rollback on failure) |
| `verify_round.py` | derives the round's active set from artifacts, runs every check | exit 0/2/3; no cache — the artifacts *are* the state |
| `stop_verify_round.py` | the Stop hook | runs the gate on every started round; blocks stop on a non-zero exit |

## The contract layer (`contracts.py`)

One source of truth so the producers, `promote.py`, and `verify_round.py` can't drift:

- **Loaders** (`load_commentary` / `load_proposals` / `load_synthesis`) parse + structurally validate (types,
  required fields, enums, ranges, `candidate_key` uniqueness, unique `decision_key`). Malformed → `MalformedArtifact`
  → gate **exit 3**. *Relational* rules (coverage, traceability, materialization, and `producer_status != ok ⇒
  agreement == twin_absent`) live in `verify_round.py`, not the schema.
- **Markdown grammar** — frontmatter keys, required note sections, and the two index tables via
  `read_index_table` / `append_index_row` (so writer and reader share one parser), plus the stable-ID and
  backlink helpers.

## Why it's reliable (and what it isn't)

- **Reliable:** "done" is a script exit code, not a model assertion; Phase-8 file I/O is code, not generation;
  the shared contract layer keeps writer and reader in sync; the Stop hook makes the gate unavoidable.
- **Crash-safe:** producers take a per-project `flock` and write atomically (temp + rename), so an interrupted
  or concurrent run can't corrupt an artifact.
- **Not magic:** the gate checks that the *work happened and is well-formed* — it does **not** judge the
  *quality* of a hypothesis or a verdict. That judgment is still the panel's (and yours).

## Extending it

- New persona engine → add an `--emit json` producer and list it in `contracts.SUPPORTED_TWIN_ENGINES`.
- New gate rule → add a `check_*` to `verify_round.py` (semantic) and/or a field to `contracts.py` (structural).
- The test suite (`framework/shared/tests/`, run with `pytest`) is the executable spec: contracts, producers,
  promote, the full gate matrix, the Stop hook, and a smoke run against the cor1m example.
