# Adversarial Rubric — research_loop

Last Updated: 2026-06-19

Purpose: domain attack vectors for milestone reviews of the research_loop enforcement layer.

## Data Boundaries

| Boundary | Format | Validation | Failure Mode |
|---|---|---|---|
| `hypothesis_tracking/research_loop.yml` | Minimal YAML subset | `verify_round.load_config`; termination block via `contracts.load_termination` | Misparsed config can disable gates, mis-size cap, or falsely authorize termination |
| `outputs/commentary/roundN/<HID>.json` | JSON | `contracts.load_commentary`; semantic twin checks in `verify_round` | Missing persona/twin attempt can pass as completed review |
| `outputs/seed_expansion.json` | JSON | `emit._selfcheck_seed_expansion`; `verify_round.check_seed_expansion` | Initial hypotheses may be accepted without persona/twin expansion |
| `outputs/proposals/roundN.json` | JSON | `contracts.load_proposals`; Phase-8 coverage/traceability/twin checks | New backlog can skip a persona, twin, or source and still appear synthesized |
| `outputs/synthesis/roundN.json` | JSON | `contracts.load_synthesis`; materialization checks in `verify_round` | Decisions can cite nonexistent proposal sources or skip materialization |
| `outputs/promotion_ledger.json` | JSON | `verify_round.check_materialization` JSON parse + key lookup | Gate can falsely believe a decision was materialized or reject valid work |
| Findings notes and memo markdown | Markdown + frontmatter | `contracts.parse_frontmatter`; note/memo checks in `verify_round` | Lifecycle state, finalization, or backlinks can drift from JSON artifacts |
| `RESEARCH_HYPOTHESIS_INDEX.md` | Markdown tables | `contracts.read_index_table` and `promote` writers | Stable IDs and status/round authority can drift from notes |
| Persona files | Markdown | `emit.resolve_persona`; provenance checked in `verify_round` | Wrong persona source can silently change reviewer behavior |
| External CLI outputs | Free text / embedded JSON | `emit.invoke_persona`; parser fallbacks; contracts self-checks | Model output shape can collapse into empty proposals or unavailable twins |

## Type Coercion Vectors

| Coercion | Location | Risk | Test Exists? |
|---|---|---|---|
| YAML scalar string to bool/int/string | `verify_round._scalar` | `true`, numeric strings, or quoted values may alter gate flags | Partial: config round/codex tests; add edge tests when parser grows |
| Nested YAML mapping to dict | `verify_round.load_config` | `termination:` may be parsed as list or empty block | Yes: `test_config_reads_termination_block` |
| Termination round string to int | `contracts.load_termination` | Non-numeric or bool values can authorize wrong round | Yes: contract termination tests |
| Note frontmatter round remains string | `contracts.parse_frontmatter`, `active_for_round` | Active set can miss notes if writers change type/format | Existing frontmatter/index tests |
| Stable ID text to numeric allocation | `contracts.parse_id`, `promote._allocated_nums` | Prose mentions can be mistaken for allocated IDs | Yes: prose-ID regression tests |
| Markdown table cells with pipes | `contracts._split_row` | Cell shift corrupts status/round authority | Yes: pipe round-trip test |
| Producer status enums | `contracts.load_*`, `verify_round._twin_attempted` | Foreign engine/status can satisfy twin gates | Yes: foreign-engine/twin tests |

## Trust Assumptions

| Assumption | What Breaks | Severity | Test Exists? |
|---|---|---|---|
| `contracts.py` is the source of truth for enums and artifact grammar | Producers and gate drift apart | HIGH | Grammar/enums tests |
| A supported twin attempt is `engine in SUPPORTED_TWIN_ENGINES` plus `producer_status` | A fake or foreign twin satisfies Codex requirement | HIGH | Yes |
| A timeout/unavailable twin is non-blocking per round but counted by producer health | Dead twin silently degrades an entire program | HIGH | Yes |
| `termination_recommendation` is advisory only | Model output can close a program without a human | HIGH | Yes |
| A binding early stop requires `research_loop.yml termination:` plus finalized memo marker | Informal early stop bypasses finalization | HIGH | Yes |
| `deferred` is per-round only | A deferred decision ends the whole program | MEDIUM | Yes |
| Persona `resolved_source` matches configured source/overrides | Review can use unintended global/local personas | MEDIUM | Existing provenance tests |
| Promotion ledger keys are authoritative materialization evidence | A stale/missing ledger changes closeability | MEDIUM | Existing vertical-slice tests |

## Cascade Risks

| Cascade Point | Blast Radius | Isolation | Test Exists? |
|---|---|---|---|
| `load_config` misparses config | All verifier checks use wrong personas/codex/cap/termination | Small parser subset; direct tests for nested block | Partial |
| `emit` writes missing instead of fallback twin block | Gate cannot distinguish failure from skipped attempt | Always-write fallback + breaker | Yes |
| `synthesize` omits candidate coverage | Promotions/index/memo built from incomplete decisions | Coverage/traceability gate | Yes |
| `promote` ID allocation scans prose | False collisions block later rounds | Frontmatter/index/ledger allocation only | Yes |
| Termination block accepted without memo finalization | Program closes without decision record | Memo marker + finalization checks | Yes |
| Stale fixtures encode old contract | Test suite green against obsolete artifact shape | Fixture validation asserts persona/engine pairs | Yes |

## Registry Drift Risks

| Registry | Code Location | Drift Detection | Last Verified |
|---|---|---|---|
| Artifact schemas/enums | `framework/shared/contracts.py` | `test_contracts.py`, fixture validation | 2026-06-19 |
| Gate semantics | `framework/shared/verify_round.py` | `test_verify_round.py`, hook/persona/vertical tests | 2026-06-19 |
| Producer semantics | `framework/shared/emit.py` | `test_emit.py`, `test_twin_emit.py` | 2026-06-19 |
| Process docs | `framework/docs/RESEARCH_PROCESS.md`, ADR 0001 | Manual doc review plus `rg` for key terms | Pending M4 |
| Maintainer skill runtime instructions | `framework/skills/research-hypothesis-maintainer/SKILL.md` | Manual skill cross-check | Pending M4 |
| Goal acceptance matrix | `goals/loop-convergence-fixes/plan.md` | Manual plan/status update | Pending |

## Learned Vectors

| Vector | Source Milestone | Category | Recurrence |
|---|---|---|---|
| Prose ID false collision | Loop convergence fixes | Type coercion / trust | Guard `_allocated_nums` against raw prose scans |
| Foreign or missing twin block satisfies gate | Loop convergence fixes | Trust / data boundary | Require supported engine plus `producer_status` |
| Twin only checked in one phase | Loop convergence fixes | Coverage cascade | Gate seed, commentary, and proposals |
| Informal early stop treated as sanctioned convergence | Clean-room dogfood | Trust / process | Require human termination block and finalized memo |
| Hand-rolled YAML parser cannot read nested config | CR-1 finding | Type coercion | Keep parser subset explicit and directly tested |
| Fixture drift hides changed contract | M2 implementation | Registry drift | Assert required persona/engine shape, not stale counts |
