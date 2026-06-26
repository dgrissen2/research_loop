---
name: codex-review
description: |
  Run an independent Codex code review using GPT-5.5 with xhigh reasoning.
  Use when user says "codex review", "cross-model review", "run codex on this",
  or during Step 3 of the agentic development process (milestone review panel).
  Collects git diff + changed files, sends to Codex CLI, returns structured findings.
---

# Codex Review

Independent cross-model code review using OpenAI Codex (GPT-5.5, xhigh reasoning). Designed to run in parallel with the three Claude review agents (Architect, CTO, Red Team) during the milestone review panel.

## Why This Exists

Codex reviews from a different model family than Claude, which means different blind spots. It does NOT see Claude's planning notes or prior review comments — only the code and diff. This anti-anchoring property is what makes the ensemble valuable.

## Instructions

### Step 1: Determine Review Scope

Check what the user wants reviewed:

- **If `$ARGUMENTS` contains a file path or directory**: Review that specific path
- **If `$ARGUMENTS` contains "pr" or "branch"**: Review all changes on the current branch vs main
- **If `$ARGUMENTS` is empty**: Review all uncommitted changes (staged + unstaged)
- **If running as part of `/milestone-review`**: Review all changes since the last commit on main

### Step 2: Collect the Diff and Changed Files

```bash
# For uncommitted changes:
DIFF=$(git diff HEAD)
CHANGED_FILES=$(git diff HEAD --name-only | grep '\.py$')

# For branch changes:
DIFF=$(git diff main...HEAD)
CHANGED_FILES=$(git diff main...HEAD --name-only | grep '\.py$')

# For specific path:
DIFF=$(git diff HEAD -- "$PATH")
CHANGED_FILES="$PATH"
```

If Serena is installed and there are **more than 15 changed files**, use it to build a focused review package instead of sending full files:
1. `get_symbols_overview` for each changed file
2. `find_symbol` with `include_body=True` for changed symbols only
3. `find_referencing_symbols` for each changed symbol (1 level deep)
4. Package the symbol bodies + caller context as the review content

### Step 3: Run the Codex Review

Execute the review script, passing the diff and file contents via stdin:

```bash
~/.claude/skills/codex-review/scripts/codex_review.sh
```

The script handles:
- Assembling diff + file content
- Piping to `codex exec -m gpt-5.5 -c model_reasoning_effort=xhigh`
- Passing the structured review prompt

**IMPORTANT**: Do NOT include any of Claude's reasoning, planning notes, or prior review comments in the Codex prompt. Codex must form its own independent judgment.

### Step 4: Parse and Present Findings

Read the Codex output. It will be structured as:

```
## Codex Review — Verdict: <PASS / CONDITIONAL PASS / FAIL>

| Finding | Severity | File:Line | Description |
|---------|----------|-----------|-------------|
```

Present this to the user as-is. If running as part of the full review panel, this output feeds into the Panel Synthesis step where Claude merges all four reviewer outputs.

### Step 5: Panel Synthesis (if running with full panel)

When Codex review runs alongside a Claude panel (personas such as Architect, CTO, and Red Team — or any personas specified for the goal):

1. **Agreement matrix**: Findings flagged by 2+ reviewers → bump severity (high confidence)
2. **Disagreements**: Findings where reviewers conflict → flag for human judgment
3. **Codex-only findings**: Issues only Codex caught → highlight as "cross-model catch"
4. **Deduplicated findings table**: Single table with source column showing which reviewer(s) flagged each issue

## Codex Review Dimensions

The review prompt instructs Codex to evaluate these dimensions:

| Dimension | What Codex Checks |
|---|---|
| API correctness | Do imported functions/methods exist and are they used correctly? |
| Logic errors | Off-by-one, wrong operators, swapped arguments, incorrect conditionals |
| Data contracts | Column names, field paths, enum values match their sources |
| Edge cases | Empty inputs, None propagation, division by zero, NaN/Inf handling |
| Silent failures | Swallowed exceptions, missing logging, default returns hiding errors |
| Security | Path traversal, injection, secrets in code, unsafe deserialization |

## Examples

```
# Review uncommitted changes
/codex-review

# Review a specific file
/codex-review src/scoring/engine.py

# Review current branch vs main
/codex-review branch

# Review as part of milestone panel (called automatically by /milestone-review)
/codex-review panel
```

## Troubleshooting

- **"codex: command not found"**: Install Codex CLI: `npm install -g @openai/codex`
- **Authentication error**: Run `codex login` to authenticate with OpenAI
- **Timeout on large diffs**: For milestones touching >15 files, the script automatically switches to Serena-extracted symbol bodies
- **Empty output**: Check that there are actual changes to review (`git diff HEAD` should show content)
