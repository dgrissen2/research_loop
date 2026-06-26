---
name: codex-plan-review
description: "Run an independent Codex plan review using GPT-5.5 with xhigh reasoning. Use for milestone roadmaps, implementation plans, architecture/design docs, and specs before implementation. Generic by default; flexible for optional persona lenses resolved from a local or global persona registry."
---

# Codex Plan Review

Independent plan review using Codex (`gpt-5.5`, `model_reasoning_effort=xhigh`).
This is for plans, roadmaps, specs, and design docs, not ordinary code diffs.

## Focus

The generic review checks:

- spec fidelity: missing requirements, invented scope, ambiguous acceptance criteria
- internal consistency: formulas, thresholds, score ranges, naming, and definitions
- dependency ordering: milestones that depend on unbuilt or underspecified pieces
- data contracts: fields, enums, units, return shapes, schemas, and file paths
- feasibility: work estimates, validation budgets, operational assumptions
- edge cases: empty inputs, boundaries, NaN/None, rollback and failure modes
- test adequacy: whether tests cover the actual risks in the plan

## Personas

This skill is flexible for different personas — they are optional lenses, not a fixed enum.
**Which personas to use should be specified up front when the goal is initiated** (the research_loop
maintainer skill confirms the set and creates any that don't exist). Example lenses: `architect`, `cto`,
`red-team`, `software-architect`, `quantitative-analyst`, or a specific-person persona you define — or
pass a direct path to a persona `.md` file.

Run without personas for a generic review; pass `--personas a,b,/path/to/persona.md` for a panel.

List what's available via the framework's shared resolver (works even without Codex):

```bash
python3 .claude/skills/_research_loop/persona_registry.py --list
```

## Model & reasoning effort

Defaults: **model `gpt-5.5`**, **reasoning effort `xhigh`**. To change (no reinstall): pass `--model` /
`--effort`, or edit `DEFAULT_MODEL` / `DEFAULT_EFFORT` at the top of the script.

## Workflow

Generic review:

```bash
python .claude/skills/codex-plan-review/scripts/codex_plan_review.py \
  <plan_file> \
  [context_file ...]
```

Generic review plus persona overlays:

```bash
python .claude/skills/codex-plan-review/scripts/codex_plan_review.py \
  <plan_file> \
  [context_file ...] \
  --personas architect,red-team,/path/to/custom_persona.md
```

The script writes review artifacts next to the plan file and prints the combined
output. Persona passes are independent; synthesis sees only completed outputs.

## Output Contract

Generic:

```text
## Codex Plan Review — Verdict: PASS / CONDITIONAL PASS / FAIL (N findings)
```

Persona:

```text
## Codex Plan Review — <Persona Name>
```

Synthesis:

```text
## Codex Plan Review — Panel Synthesis
```

## Persona resolution

Personas resolve via the framework's shared resolver
(`.claude/skills/_research_loop/persona_registry.py`), which is installed regardless of Codex. The Codex
script locates it automatically (a `RESEARCH_LOOP_PERSONA_REGISTRY` override, then the shared install
location). Discovery is **first-match-wins, project-local before global** (a project persona overrides a
global one of the same id), and never assumes skillshare:

1. `PERSONA_PATHS` (explicit override) or `--persona-dir`
2. project-local: `.claude/personas/`, `personas/`, `docs/personas/`
3. global Claude folder: `~/.claude/personas/`
4. (optional) a skillshare install — used only if present, never required
