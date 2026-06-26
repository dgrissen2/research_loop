# Importing & using `research_loop` in another project

`research_loop` is a **Claude Code skill + a small pure-Python machinery layer** that runs a
disciplined, falsifiable research-hypothesis loop (seed → per-hypothesis phases → persona
commentary → proposals → synthesis → promotion), enforced by a Stop-hook **gate**. You **install
it into a target project**; it is not a pip package you import in code.

---

## 1. Prerequisites

- **Claude Code** — the `research-hypothesis-maintainer` skill runs inside it. (The machinery can
  also be driven standalone from the CLI; see §5.)
- **python3** — the producers + gate are **stdlib-only, zero pip dependencies**.
- *Optional* **OpenAI Codex CLI** (`npm i -g @openai/codex`) — adds the cross-model "twin" + the
  `codex-*-review` skills. The loop completes fine without it (in-Claude panel only).
- *Optional* **Plannotator** (`curl -fsSL https://plannotator.ai/install.sh | bash`) — the guided
  goal-setup UI the loop is designed around.

---

## 2. Install (air-drop into the target project)

The installer is **idempotent**, asks before each optional step, and overwrites the "universal"
files (skill, machinery, docs, personas) while keeping your "template" files (index, notes, config)
unless `--force`.

**A — from a local clone** (recommended when you already have the repo):

```bash
path/to/research_loop/install.sh /path/to/TARGET/project --local
#   --global   install into ~/.claude instead of the project's .claude/
#   --prefix XYZ        ID prefix (else derived from the dir name; the skill confirms it later)
#   --codex / --no-codex            install the Codex review skills (default: ask)
#   --plannotator / --no-plannotator
#   --yes      non-interactive (accept defaults)   --force  overwrite template files too
#   --ref <branch|tag|sha>          which version to use
```

**B — curl | bash** (run *inside* the target project):

```bash
curl -fsSL https://raw.githubusercontent.com/dgrissen2/research_loop/main/install.sh | bash
```

Either way you choose **project-local** (`.claude/` inside the project — versioned with the repo,
recommended) or **global** (`~/.claude/` — every project on the machine).

---

## 3. What lands in the target project (`--local` scope)

| Path | What it is |
|---|---|
| `.claude/skills/research-hypothesis-maintainer/SKILL.md` | **The skill** that drives the whole loop. |
| `.claude/skills/_research_loop/*.py` | **The machinery**: `emit.py` (producers), `verify_round.py` (gate), `contracts.py`, `synthesize.py`, `promote.py`, `persona_registry.py`, `run_codex_twin.py`. |
| `.claude/hooks/stop_verify_round.py` | **The gate as a Stop hook** — blocks ending a turn until the round validates. Auto-registered in `.claude/settings.json`. |
| `.claude/personas/*.md` | Sample reviewer personas (CIO / Portfolio Manager / Quant — *starting points*, not defaults; the skill confirms the panel per goal). |
| `hypothesis_tracking/research_loop.yml` | **Project config** (see §4). |
| `hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md` + note/memo templates | The tracked record. |
| `scripts/ data/ outputs/` | Work folders (analysis code, inputs, generated artifacts). |
| `docs/GETTING_STARTED.md`, `docs/RESEARCH_PROCESS.md`, … | The how-to + process spec. |

> `--global` puts the skill, machinery, and personas under `~/.claude/` instead; the
> `hypothesis_tracking/`, work folders, and `docs/` still land in the project.

The worked example is **deliberately not installed** (it would pollute a clean project — the loop
would treat it as prior work). It lives in the repo at `examples/cor1m-concentration-hedge`.

---

## 4. Configure — `hypothesis_tracking/research_loop.yml`

The installer writes this; key knobs the skill + gate read:

```yaml
prefix: ABC               # hypothesis/experiment ID prefix → H-ABC-001 / E-ABC-001
personas: []              # the CONFIRMED panel — empty until you confirm it per goal
personas_dir: .claude/personas
codex: true|false         # whether the Codex twin/review skills are installed
round_cap: 3              # max ROUNDS per program (the gate enforces this hard cap)
K: 2                      # min candidate proposals on a non-deferred round (Phase-8 floor)
persona_source: local     # 'local' (.claude/personas) or 'global' (~/.claude/personas)
persona_overrides: []
# claude_leg: subprocess  # OPTIONAL (default subprocess). See below.
```

**`claude_leg` (optional, default `subprocess`)** — how the Claude persona leg of the producers runs:
- `subprocess` *(default)* — `claude -p` calls; **headless / CI-capable**.
- `subagent` — in-session **persona subagents** (warm, no cold start; commentary is always batched).
  **Not headless** — needs a live Claude Code session. Same **byte-identical** artifacts either way;
  the Codex twin is unchanged. The skill's Phase 1/6/8 prose (SKILL.md §A5) describes the
  spawn-collect-assemble flow.

Every producer run is **`flock`-locked** (one producer per project at a time) and writes its artifacts
**atomically** (temp + rename), so a crash or concurrent run never leaves a torn file.

---

## 5. Use it

**Guided (recommended)** — in Claude Code, inside the target project:

```text
/plannotator-setup-goal        # scope an idea → seed hypotheses + a round cap → a goal package
/goal goals/<slug>/goal.md     # run the whole loop (the skill confirms your ID prefix on first use)
```

Then read `hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md` + the decision-maker memo.

**Standalone CLI** — the machinery runs without the skill (e.g. from your own automation). A round:

```bash
RL=.claude/skills/_research_loop          # (or ~/.claude/skills/_research_loop under --global)
python3 $RL/emit.py seed       --round 1 --context @seed_ideas.md        # Phase 1
python3 $RL/emit.py commentary --round N                                 # Phase 6 (all active hyps)
python3 $RL/emit.py proposals  --round N --context @round_findings.md    # Phase 8
python3 $RL/synthesize.py      --round N                                 # proposals → decisions[]
python3 $RL/promote.py         --round N                                 # materialize decisions
python3 $RL/verify_round.py    --round N                                 # GATE: exit 0 = round closes
```

Exit codes worth knowing: `emit.py` → `3` = another emit holds the lock (wait, don't relaunch),
`7` = twin circuit-breaker tripped (stop, report); `verify_round.py` → `2` = punchlist of what's
missing, `3` = a required artifact is malformed.

Under `claude_leg: subagent`, the producer call for a phase becomes three steps the **skill**
performs in-session: `emit.py prompts <phase>` → spawn one persona subagent per persona, write each
raw answer to the printed records dir → `emit.py assemble <phase> --claude-legs @<scaffold>`.

---

## 6. Verify the install

```bash
ls .claude/skills/research-hypothesis-maintainer/SKILL.md          # the skill
ls .claude/skills/_research_loop/                                  # the 7 machinery scripts
python3 -c "import json;print('Stop hook' if 'stop_verify_round' in open('.claude/settings.json').read() else 'NOT registered')"
python3 .claude/skills/_research_loop/verify_round.py --round 1    # runs the gate (exit 0/2/3)
```

In Claude Code, the skill should be discoverable as `research-hypothesis-maintainer`.

---

## 7. Update / re-import

Re-run the installer (idempotent): the skill, machinery, hook, personas, and docs are refreshed;
your `research_loop.yml`, index, notes, and templates are kept (use `--force` to overwrite those
too). Pin a version with `--ref <tag|sha>`.

---

## 8. Cost note

The loop is **heavy on model calls** (Phase 6 & 8 panels are *N personas × 2 passes* when the
Codex twin is on, across multiple rounds). To dial down: `--no-codex` at install, lower Codex
`--effort` (`xhigh`→`medium`), fewer personas, smaller `round_cap`. Treat `xhigh` + Codex + many
rounds + several personas as the max-plan configuration.
