# ADR 0001 — Enforce the research_loop back half with artifacts + a gate, not prose

- **Status:** Accepted
- **Date:** 2026-06-13
- **Context & design of record:** the internal goal package (`goals/loop-reliability-enforcement/`,
  `goals/research-hypothesis-framework/`, v5 + M5) — kept in the private development repo, not shipped in
  the public release.

## Context

The research_loop runs reliably through Phases 0–5 (scope → define → method → execute → interpret →
verdict), but the **back half** — Phase 6 (independent persona + cross-model verification), Phase 7 (record +
backlink), Phase 8 (propose → synthesize → promote) — was frequently skipped or only partially done. The root
cause is structural: the whole loop, including the failing parts, lived as **advisory prose** in
`RESEARCH_PROCESS.md` / the maintainer skill. By the time an agent reaches Phase 8 in a long, analysis-heavy
turn, those instructions have been crowded out of effective attention. Adding more prose (memory, re-pasting
the doc) competes for the same attention and does not change the mechanism. "Round complete" had no
machine-checkable definition — it meant *the agent asserted it*.

## Decision

Move control of the back half from prose into **persistent artifacts + a deterministic gate**:

1. **Artifacts are the source of truth.** Round/lifecycle state lives in the artifacts — note YAML
   frontmatter (`id` / `round` / `hypothesis_status` / `phase`) and an index `Round` column — not in a cache.
   `loop_state.json` (a resumable cache) is deferred to v2.
2. **One contract layer (`contracts.py`).** A single module owns JSON artifact structure
   (`commentary` / `proposals` / `synthesis`), the shared enums (incl. `persona_source` and the
   `resolved_source` / `resolved_path` provenance fields), the markdown artifact grammar (index columns, note
   frontmatter, link/ID/status-cell formats), and the action→edit map. It is imported by the producers,
   `promote.py`, and `verify_round.py` so there is exactly one validation/grammar code path. No JSON-Schema
   files and no vendored schema validator — structural checks are inline; relational/semantic rules
   (coverage, traceability, materialization) live in the verifier.
3. **A hard gate (`verify_round.py`).** A round cannot close unless the gate, reading only the on-disk
   artifacts, confirms note completeness + backlinks, per-persona independent commentary (twin optional via a
   `timeout`/`unavailable` fallback — never blocking), and that Phase-8 work happened (proposals → a
   `decisions[]` synthesis that classifies and covers every candidate → materialized promotions). Exit codes:
   `0` closeable, `2` incomplete (machine-keyed punchlist), `3` malformed artifact.
4. **No promotion quota.** The gate enforces that the *work and classification* happened, not that something
   was promoted; an honest deferred round passes with a reason.
5. **Human-authorized program termination.** `synthesize.py` may recommend `continue|converge|stop`, but the
   recommendation is advisory. The gate only recognizes a human-written `research_loop.yml termination:`
   record (`status`, `reason`, `round`, `authorized_by`) and then enforces that the decision-maker memo is
   finalized and records the same termination/convergence decision. Per-round `deferred` remains scoped to
   that round and does not close a program.
6. **A Stop hook** runs the gate so the agent cannot end a turn with an open, incomplete round. The hook is
   **shipped as an installer-wired artifact** (not activated in this framework repo); standalone use degrades
   to a documented manual verifier step.
7. **Brownfield-first install + selectable persona source.** Installing into an existing repo is additive and
   idempotent; `persona_source ∈ {local, global}` selects the authoritative persona library, with
   project-local overrides declared explicitly via `persona_overrides`.

## Consequences

- **Positive:** the back half becomes un-skippable and machine-checkable; mechanical Phase-8 file I/O moves
  out of model generation into `promote.py`; one contract layer prevents `promote`/`verify` drift.
- **Costs / trade-offs:** new scripts to build and test; the gate re-derives state from artifacts on every run
  (acceptable — a handful of files per round); the Stop hook is Claude Code-specific (mitigated by the
  documented manual path).
- **Deferred to v2:** the `loop_state.json` cache + `--rebuild-state`, experiment→hypothesis
  `from_experiment_id` sugar, `persona_version` in records, the `keep` reprioritize action, and Gemini
  emit-json parity.

## References

- Process: [`framework/docs/RESEARCH_PROCESS.md`](../../framework/docs/RESEARCH_PROCESS.md)
- Skill: [`framework/skills/research-hypothesis-maintainer/SKILL.md`](../../framework/skills/research-hypothesis-maintainer/SKILL.md)
