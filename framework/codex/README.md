# Codex review layer (optional)

These three skills give research_loop an independent **cross-model** review using
[OpenAI Codex](https://github.com/openai/codex). They are installed only if you tell the installer you
use Codex. They are optional — the loop falls back to Gemini or an in-Claude persona panel without them.

| Skill | Reviews | Personas |
|---|---|---|
| `codex-strategy-review` | research conclusions, findings notes, decision memos, arguments | yes (overlays) |
| `codex-plan-review` | plans, specs, design docs (e.g. a hypothesis method before running) | yes (overlays) |
| `codex-review` | **code** diffs (stays code-specific; not for research artifacts) | no |

## Prerequisites

- Codex CLI: `npm install -g @openai/codex`, then `codex login`.
- Python 3 — needed to run the Codex skills and the persona-listing helper; the core research loop does not require it.

## Model & reasoning effort

Defaults: **model `gpt-5.6-sol`**, **reasoning effort `xhigh`** — stated identically in each skill's SKILL.md.
To change (no reinstall):

- `codex-strategy-review` / `codex-plan-review`: pass `--model` / `--effort`, or edit `DEFAULT_MODEL` / `DEFAULT_EFFORT` at the top of the `.py` script.
- `codex-review` (a shell script): set the `CODEX_MODEL` / `CODEX_EFFORT` environment variables (defaults near the top of `codex_review.sh`).

The installer surfaces these defaults at install time and points here.

## Persona resolution

The persona resolver (`persona_registry.py`) is **framework-level** — installed at
`.claude/skills/_research_loop/` regardless of whether the Codex skills are, so Claude-only users still get
persona listing/resolution. `codex-strategy-review` and `codex-plan-review` locate it automatically.

Discovery is **project-local first**, then the global Claude folder (`~/.claude/personas`); a project
persona overrides a global one of the same id. A skillshare install is used only if present — never
required. Override sources with the `PERSONA_PATHS` env var (or `--persona-dir`), or the resolver location
with `RESEARCH_LOOP_PERSONA_REGISTRY`.

List available personas (works without Codex):

```bash
python3 .claude/skills/_research_loop/persona_registry.py --list
```

## Bounded execution & safe termination

Codex calls are **time-boxed and process-group-scoped**, so a hung review can never block the loop or
trample other work:

- Each `codex exec` is launched in its **own process group** (`start_new_session=True`). On timeout
  (`CODEX_TIMEOUT`, default **300s**) the runner kills **only that process group** (`os.killpg`) — leaving
  no orphaned `xhigh` children.
- **Never terminate codex by name** (`pkill codex` / `killall codex`). Other agents or sessions may be
  running codex at the same time; only the child group spawned by *this* call may be killed. macOS has no
  `timeout` binary, which is exactly why the bound is enforced in-process rather than by an external wrapper.
- For the loop's cross-model twin, prefer the bounded single-call runner
  `.claude/skills/_research_loop/run_codex_twin.py` over invoking `/codex-strategy-review` directly — the
  full wrapper runs a generic pass + one pass per persona + a synthesis pass (many `xhigh` calls), whereas
  the twin makes one combined-persona call with a hard timeout, one retry, and a fallback marker.
