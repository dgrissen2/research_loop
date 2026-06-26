---
name: codex-strategy-review
description: "Run an independent Codex adversarial strategy and logic review using GPT-5.5 with xhigh reasoning. Generic by default; flexible for optional persona lenses resolved from a local or global persona registry. Use for strategy docs, research conclusions, optimizer proposals, risk frameworks, decision memos, or arguments that need stress-testing."
---

# Codex Strategy Review

Independent adversarial logic review using Codex (`gpt-5.5`,
`model_reasoning_effort=xhigh`). This skill is generic by default and flexible for different personas.

## Focus

Use this to stress-test a strategy, argument, proposal, research conclusion, risk
framework, optimizer design, decision memo, or any other plan where the question is
"does this logic hold up?"

The generic review checks:

- conclusions that do not follow from premises
- hidden, circular, fragile, or unstated assumptions
- made-up thresholds, constants, weights, or scoring rules
- missing evidence, counterexamples, and falsification tests
- incorrect math, units, base rates, or time horizons
- feasibility, incentives, adoption, and operational constraints
- downside, tail risks, failure modes, monitoring, and reversibility
- contradictions between goals, constraints, and proposed mechanisms

## Personas

This skill is flexible for different personas — they are optional lenses, not a fixed enum.
**Which personas to use should be specified up front when the goal is initiated** (the research_loop
maintainer skill confirms the set and creates any that don't exist). Example lenses: `architect`, `cto`,
`red-team`, `quant`, `quantitative-analyst`, or a specific-person persona you define — or pass a direct
path to a persona `.md` file.

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
python .claude/skills/codex-strategy-review/scripts/codex_strategy_review.py \
  <strategy_file> \
  [context_file ...]
```

Generic review plus persona overlays:

```bash
python .claude/skills/codex-strategy-review/scripts/codex_strategy_review.py \
  <strategy_file> \
  [context_file ...] \
  --personas quant,pm,/path/to/custom_persona.md
```

Legacy form still works:

```bash
python .claude/skills/codex-strategy-review/scripts/codex_strategy_review.py \
  <strategy_file> \
  quant,pm \
  [context_file ...]
```

Each persona pass is independent. The final synthesis may see all completed
outputs and deduplicates agreement, disagreement, and unique catches.

## Output Contract

Generic:

```text
## Codex Strategy Review — Generic Logic
```

Persona:

```text
## Codex Strategy Review — <Persona Name>
```

Synthesis:

```text
## Codex Strategy Review — Panel Synthesis
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
