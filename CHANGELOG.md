# Changelog

All notable changes to **research_loop** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **1.1.0 is research_loop's first public release.** The `1.0.1` and `1.0.0` entries
> below were internal development milestones, kept here so the lineage of the loop's
> execution and safety model is on the record.

## [1.1.0] — 2026-06-23

First public release. Adds an optional native-subagent execution path for the
producers while keeping the default behaviour and the on-disk artifacts unchanged.

### Added

- **Native-subagent Claude leg (`claude_leg`).** A new project-config key,
  `claude_leg: subprocess | subagent` (default `subprocess`), selects how the Claude
  persona leg of each producer runs: as a `claude -p` subprocess (the original path)
  or as native, in-session Claude Code subagents.
- **`prompts` / `assemble` producer modes in `emit.py`.** `prompts` freezes the exact
  prompt, provenance, and `run_id` into an atomic on-disk scaffold; `assemble` reads
  the subagents' replies back through the *same* parse seam, normalises producer
  status, fires only the Codex twins, pairs them, and self-validates the scaffold
  identity (round / phase / ordered personas / provenance).
- **`research-hypothesis-maintainer` skill:** the A5 spawn → collect → assemble flow
  and a headless note for the new leg.

### Changed

- Producers now build their artifacts through shared, pure "block shaper" helpers used
  by *both* the subprocess builders and the subagent assemblers, so the two paths emit
  **byte-identical** artifacts by construction (locked down by byte-golden tests). The
  Stop-hook gate sees zero diff regardless of `claude_leg`.

### Notes

- Native subagents require an interactive Claude Code session. For headless automation
  (`claude -p`, CI), keep `claude_leg: subprocess`.
- `assemble` runs fail-closed: it requires the subagent leg, preserves the
  required-Claude (R1) contract, and scopes its records directory to the `run_id` so a
  stale run can't be mistaken for a fresh one.

## [1.0.1] — 2026-06-22

Safety-hardening of the producer/gate write path (the "Tier-1" work).

### Fixed

- **Producer lock.** Each producer run now takes a per-project `flock`, making it the
  sole writer for that project and preventing concurrent runs from racing or
  interleaving artifact writes.
- **Atomic writes.** Artifacts are written to a temp file and atomically renamed into
  place, so an interrupted run can never leave a torn / partially written JSON file.
- **Tolerant parse.** The reader tolerates benign trailing / whitespace noise in
  producer output without masking real required-Claude (R1) failures — lenient where it
  is safe, fail-closed where it matters.

## [1.0.0] — 2026-06-03

Initial framework: the enforced, falsifiable back-half research loop.

### Added

- **Enforced loop.** `verify_round.py` runs as a Claude Code **Stop hook** that blocks
  the loop from terminating until the round's convergence and coverage criteria are met.
- **Core machinery.** `contracts.py` (artifact schemas + validation), `emit.py`
  (seed / commentary / proposals producers), `synthesize.py` (per-round synthesis),
  `promote.py` (promotion ledger), `persona_registry.py` (first-match-wins persona
  resolution), and the optional `run_codex_twin.py` cross-model twin.
- **Multi-persona panels** with optional cross-model (Codex) twins, plus convergence and
  twin-reliability gating, driven by the `research-hypothesis-maintainer` skill.
- **Plannotator goals workflow** integration, the `install.sh` one-line installer, MIT
  licensing, and the published documentation set.
