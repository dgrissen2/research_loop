#!/usr/bin/env bash
# research_loop installer — air-drop the research-hypothesis framework into a project.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/dgrissen2/research_loop/main/install.sh | bash
#   ./install.sh [TARGET_DIR] [--global] [--local] [--prefix XYZ] [--codex] [--no-codex]
#                [--plannotator] [--no-plannotator] [--yes] [--force] [--ref REF]
#
# File classification:
#   universal  — always overwritten (skill, personas, process docs)
#   template   — copied only if missing (findings/memo templates, index, examples)
#
# No Node and no Python dependency. (Python is used only by the optional Codex skills.)

set -euo pipefail

REPO="dgrissen2/research_loop"
RAW_BASE="https://raw.githubusercontent.com/${REPO}"
REF="${RESEARCH_LOOP_REF:-main}"

# ---- options ----
TARGET=""
SCOPE=""            # local | global  (empty → ask)
PREFIX=""
WANT_CODEX=""       # yes | no | "" (ask)
WANT_PLAN=""        # yes | no | "" (ask)
ASSUME_YES=false
FORCE=false

# ---- colors ----
if [ -t 1 ]; then
  R=$'\033[0;31m'; G=$'\033[0;32m'; Y=$'\033[0;33m'; B=$'\033[0;34m'; D=$'\033[2m'; N=$'\033[0m'
else
  R=""; G=""; Y=""; B=""; D=""; N=""
fi
say()  { printf "%s\n" "$*"; }
info() { printf "%s%s%s\n" "$B" "$*" "$N"; }
ok()   { printf "%s%s%s\n" "$G" "$*" "$N"; }
warn() { printf "%s%s%s\n" "$Y" "$*" "$N"; }

# ---- prompts (read from /dev/tty so curl|bash still works) ----
# NB: these helpers are called inside $(...) where fd 1 is a pipe, so we must detect
# the terminal via /dev/tty directly — never via `[ -t 1 ]`.
have_tty() { { true < /dev/tty; } 2>/dev/null; }

ask_yn() {  # ask_yn "Question?" default(y|n) -> echoes yes|no
  local q="$1" def="$2" ans
  if $ASSUME_YES || ! have_tty; then
    [ "$def" = "y" ] && { echo yes; return; } || { echo no; return; }
  fi
  local hint="[y/N]"; [ "$def" = "y" ] && hint="[Y/n]"
  printf "%s %s " "$q" "$hint" > /dev/tty
  read -r ans < /dev/tty || ans=""
  ans="$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')"
  [ -z "$ans" ] && ans="$def"
  case "$ans" in y|yes) echo yes ;; *) echo no ;; esac
}

ask_val() {  # ask_val "Prompt" default -> echoes value
  local q="$1" def="$2" ans
  if $ASSUME_YES || ! have_tty; then echo "$def"; return; fi
  printf "%s [%s] " "$q" "$def" > /dev/tty
  read -r ans < /dev/tty || ans=""
  [ -z "$ans" ] && ans="$def"
  echo "$ans"
}

usage() { sed -n '2,18p' "$0" 2>/dev/null || true; exit 0; }

# ---- arg parsing ----
while [ $# -gt 0 ]; do
  case "$1" in
    --global) SCOPE="global" ;;
    --local) SCOPE="local" ;;
    --prefix) PREFIX="${2:-}"; shift ;;
    --prefix=*) PREFIX="${1#*=}" ;;
    --codex) WANT_CODEX="yes" ;;
    --no-codex) WANT_CODEX="no" ;;
    --plannotator) WANT_PLAN="yes" ;;
    --no-plannotator) WANT_PLAN="no" ;;
    --yes|-y) ASSUME_YES=true ;;
    --force) FORCE=true ;;
    --ref) REF="${2:-main}"; shift ;;
    --ref=*) REF="${1#*=}" ;;
    -h|--help) usage ;;
    *) [ -z "$TARGET" ] && TARGET="$1" || { warn "Unexpected arg: $1"; exit 1; } ;;
  esac
  shift
done

TARGET="${TARGET:-$PWD}"
mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

# ---- locate or fetch the framework payload ----
SCRIPT_SRC=""
case "${BASH_SOURCE[0]:-}" in
  ""|/dev/stdin|bash|sh) SCRIPT_SRC="" ;;
  *) SCRIPT_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)" ;;
esac

PAYLOAD_ROOT=""
CLEANUP_TMP=""
if [ -n "$SCRIPT_SRC" ] && [ -d "$SCRIPT_SRC/framework" ]; then
  PAYLOAD_ROOT="$SCRIPT_SRC"
  info "Using local framework payload at $PAYLOAD_ROOT"
else
  info "Fetching research_loop payload ($REPO@$REF)…"
  TMP="$(mktemp -d)"; CLEANUP_TMP="$TMP"
  if ! curl -fsSL "https://github.com/${REPO}/archive/refs/heads/${REF}.tar.gz" -o "$TMP/rl.tgz" 2>/dev/null; then
    curl -fsSL "https://github.com/${REPO}/archive/${REF}.tar.gz" -o "$TMP/rl.tgz"
  fi
  tar -xzf "$TMP/rl.tgz" -C "$TMP"
  PAYLOAD_ROOT="$(find "$TMP" -maxdepth 1 -type d -name 'research_loop-*' | head -n1)"
  [ -d "$PAYLOAD_ROOT/framework" ] || { warn "Payload missing framework/"; exit 1; }
fi
trap '[ -n "$CLEANUP_TMP" ] && rm -rf "$CLEANUP_TMP"' EXIT

FW="$PAYLOAD_ROOT/framework"
VERSION="$(cat "$PAYLOAD_ROOT/VERSION" 2>/dev/null || echo "?")"

# ---- banner ----
say ""
info "research_loop installer (v${VERSION})"
say "${D}A research-hypothesis framework, designed to run through the Plannotator goals workflow.${N}"
say "Target project: $TARGET"
say ""

# ---- prefix (derived silently; the SKILL confirms/primes it on first use — we don't
#      ask here because a new user has no reason to know what an ID prefix is) ----
if [ -n "$PREFIX" ]; then
  PREFIX_CONFIRMED=true
else
  base="$(basename "$TARGET")"
  PREFIX="$(printf '%s' "$base" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9' | cut -c1-4)"
  [ -z "$PREFIX" ] && PREFIX="RL"
  PREFIX_CONFIRMED=false
fi
PREFIX="$(printf '%s' "$PREFIX" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9' | cut -c1-6)"

# ---- scope: ask local vs global ----
if [ -z "$SCOPE" ]; then
  info "Where should the skill + personas live?"
  say "research_loop installs a Claude ${B}skill${N} (\"research-hypothesis-maintainer\" — it runs the"
  say "whole research loop for you) plus a few ${B}sample reviewer personas${N} (CIO / Portfolio Manager /"
  say "Quant — starting points, not defaults; the skill confirms/creates the panel per goal). Two places:"
  say ""
  say "  ${B}1) project-local${N}  ${D}→ .claude/skills + .claude/personas inside THIS project.${N}"
  say "     ${D}Committed with the repo, travels with it, only active here. Best if you want the${N}"
  say "     ${D}framework versioned alongside the research.  [default, recommended]${N}"
  say "  ${B}2) global${N}         ${D}→ ~/.claude/skills + ~/.claude/personas (your user-wide Claude folder).${N}"
  say "     ${D}Available in every project on this machine, not committed anywhere.${N}"
  say ""
  choice="$(ask_val "Choose 1 or 2" "1")"
  [ "$choice" = "2" ] && SCOPE="global" || SCOPE="local"
fi

if [ "$SCOPE" = "global" ]; then
  SKILLS_DIR="$HOME/.claude/skills"
  PERSONAS_DIR="$HOME/.claude/personas"
  PERSONAS_CFG="$HOME/.claude/personas"
else
  SKILLS_DIR="$TARGET/.claude/skills"
  PERSONAS_DIR="$TARGET/.claude/personas"
  PERSONAS_CFG=".claude/personas"
fi
ok "Scope: $SCOPE  (skills → $SKILLS_DIR)"
say ""

# ---- sync helpers ----
copy_universal() { # src dst
  mkdir -p "$(dirname "$2")"; cp "$1" "$2"
  printf "  ${G}%-7s${N} %s\n" "set" "${2/#$HOME/~}"
}
copy_template() { # src dst
  if [ -f "$2" ] && ! $FORCE; then
    printf "  ${Y}%-7s${N} %s ${D}(exists)${N}\n" "keep" "${2/#$HOME/~}"; return
  fi
  mkdir -p "$(dirname "$2")"; cp "$1" "$2"
  printf "  ${G}%-7s${N} %s\n" "create" "${2/#$HOME/~}"
}

# ---- universal: skill, personas, docs ----
info "Skill + personas + docs (refreshed):"
copy_universal "$FW/skills/research-hypothesis-maintainer/SKILL.md" \
               "$SKILLS_DIR/research-hypothesis-maintainer/SKILL.md"
for p in "$FW"/personas/*.md; do
  copy_universal "$p" "$PERSONAS_DIR/$(basename "$p")"
done
for d in "$FW"/docs/*.md; do
  copy_universal "$d" "$TARGET/docs/$(basename "$d")"
done
# Shared framework-level helpers — installed ALWAYS (even without Codex):
#   persona_registry.py : persona listing/resolution (Claude-only users need it too)
#   run_codex_twin.py   : bounded, process-group-scoped cross-model twin runner (Mode C)
#   contracts/emit/synthesize/promote/verify_round : the back-half enforcement gate
for s in persona_registry run_codex_twin contracts emit synthesize promote verify_round; do
  copy_universal "$FW/shared/$s.py" "$SKILLS_DIR/_research_loop/$s.py"
done
# Stop hook — gates round closure. Shipped here, then REGISTERED in settings.json via a
# safe additive merge (create-if-absent / abort-on-malformed / dedupe / preserve / atomic).
copy_universal "$FW/hooks/stop_verify_round.py" "$TARGET/.claude/hooks/stop_verify_round.py"
HOOK_CMD="python3 $TARGET/.claude/hooks/stop_verify_round.py"
if python3 "$FW/shared/install_support.py" merge-hook \
     "$TARGET/.claude/settings.json" "$HOOK_CMD" >/dev/null 2>&1; then
  ok "Registered Stop hook (round gate) in .claude/settings.json"
else
  say "  ${D}Could not merge .claude/settings.json (malformed?); register the Stop hook manually:${N}"
  say "  ${D}  $HOOK_CMD${N}"
fi
say ""

# ---- templates + scaffolds (copy if missing) ----
info "Templates + index + work folders (kept if present):"
for t in "$FW"/hypothesis_tracking/*.md; do
  copy_template "$t" "$TARGET/hypothesis_tracking/$(basename "$t")"
done
# work folders
for wf in scripts data outputs; do
  if [ ! -d "$TARGET/$wf" ]; then
    mkdir -p "$TARGET/$wf"
    case "$wf" in
      scripts) note="Analysis code that produces each conclusion (link these from findings notes).";;
      data)    note="Input datasets and sample data.";;
      outputs) note="Generated result tables, figures, and artifacts.";;
    esac
    printf "# %s\n\n%s\n" "$wf/" "$note" > "$TARGET/$wf/README.md"
    : > "$TARGET/$wf/.gitkeep"
    printf "  ${G}%-7s${N} %s\n" "create" "$wf/"
  else
    printf "  ${Y}%-7s${N} %s ${D}(exists)${N}\n" "keep" "$wf/"
  fi
done
# NOTE: the worked example is intentionally NOT copied into the project. Shipping it would
# pollute a fresh project (the maintainer skill / plannotator-setup-goal would treat the
# converged cor1m example as prior work and "reproduce" it instead of starting clean). The
# example lives in the research_loop repo for reference: github.com/dgrissen2/research_loop
# → examples/cor1m-concentration-hedge. Opt in with RESEARCH_LOOP_WITH_EXAMPLES=1 if you want
# a local copy (e.g. for offline study), knowing it will be visible to the loop.
if [ "${RESEARCH_LOOP_WITH_EXAMPLES:-0}" = "1" ] \
   && [ -d "$PAYLOAD_ROOT/examples" ] && [ ! -d "$TARGET/examples" ]; then
  cp -R "$PAYLOAD_ROOT/examples" "$TARGET/examples"
  printf "  ${G}%-7s${N} %s ${D}(opt-in; visible to the loop)${N}\n" "create" "examples/"
fi
say ""

# ---- Codex layer (optional) ----
info "Optional: a second opinion from a different AI (OpenAI Codex)"
say "Research is more trustworthy when an ${B}independent model${N} — not the same one that wrote the"
say "finding — tries to poke holes in it. That catches blind spots a single model shares with itself."
say "If you have OpenAI's ${B}Codex CLI${N}, research_loop can hand each conclusion to it for that"
say "cross-check. We'd install three small skills:"
say "  ${D}• codex-strategy-review — stress-tests your research conclusions / findings${N}"
say "  ${D}• codex-plan-review     — reviews a hypothesis's method before you run it${N}"
say "  ${D}• codex-review          — reviews code (kept code-specific)${N}"
say "${D}Entirely optional: with no Codex, the loop still completes — it falls back to a Gemini review${N}"
say "${D}or an in-Claude persona panel. Only say yes if you actually have the Codex CLI installed.${N}"
say ""
[ -z "$WANT_CODEX" ] && WANT_CODEX="$(ask_yn "Install the Codex review skills? (only if you use OpenAI Codex)" n)"
if [ "$WANT_CODEX" = "yes" ]; then
  # (persona_registry.py is already installed above, regardless of Codex)
  for cs in codex-strategy-review codex-plan-review codex-review; do
    mkdir -p "$SKILLS_DIR/$cs/scripts"
    cp "$FW/codex/$cs/SKILL.md" "$SKILLS_DIR/$cs/SKILL.md"
    cp "$FW"/codex/$cs/scripts/* "$SKILLS_DIR/$cs/scripts/" 2>/dev/null || true
    printf "  ${G}%-7s${N} %s\n" "set" "${SKILLS_DIR/#$HOME/~}/$cs"
  done
  say ""
  warn "Which Codex model these skills use, and how hard it thinks:"
  say "  ${D}• model  = ${B}gpt-5.5${N}${D}  — the engine doing the review.${N}"
  say "  ${D}• effort = ${B}xhigh${N}${D}    — Codex's reasoning depth. Higher = more thorough but slower${N}"
  say "  ${D}            and more expensive. 'xhigh' is the most careful setting; lower it (high/medium)${N}"
  say "  ${D}            if reviews feel too slow or costly.${N}"
  say "  ${D}Change anytime — no reinstall needed:${N}"
  say "  ${D}  · edit DEFAULT_MODEL / DEFAULT_EFFORT atop the *.py scripts, or pass --model/--effort;${N}"
  say "  ${D}  · set CODEX_MODEL / CODEX_EFFORT env vars (codex-review). Full notes: ${SKILLS_DIR/#$HOME/~}/_research_loop and the codex README.${N}"
  say "  ${D}  · or just ask the skill to change them for you later.${N}"
  CODEX_FLAG=true
else
  say "${D}Skipped Codex. Add it anytime: install the Codex CLI (npm i -g @openai/codex) and re-run this installer.${N}"
  CODEX_FLAG=false
fi
say ""

# ---- Plannotator (strongly recommended) ----
info "Strongly recommended: Plannotator (this is how research_loop is meant to be driven)"
say "${B}Plannotator${N} is a browser tool that lets you scope a research question into a structured"
say "\"goal\", then review and annotate documents (plans, findings, diffs) in a real UI instead of"
say "scrolling raw markdown in the terminal.  ${D}→ https://plannotator.ai${N}"
say ""
say "research_loop is ${B}built around it${N}: the intended flow is"
say "  ${D}/plannotator-setup-goal${N}  (turn an idea → seed hypotheses + a round cap → a goal package)"
say "  ${D}/goal goals/<slug>/goal.md${N}  (run the whole research loop through that goal)"
say "Without Plannotator the framework still works standalone, but you lose the guided goal setup and"
say "the point-and-click review of your hypotheses — which is most of what makes the loop pleasant to use."
say "${D}That's why we really recommend installing it now. It's a quick curl install from plannotator.ai.${N}"
say ""
[ -z "$WANT_PLAN" ] && WANT_PLAN="$(ask_yn "Install Plannotator now? (strongly recommended)" y)"
if [ "$WANT_PLAN" = "yes" ]; then
  if command -v plannotator >/dev/null 2>&1; then
    ok "Plannotator already installed ($(plannotator --version 2>/dev/null || echo present))."
  else
    info "Installing Plannotator (latest, from plannotator.ai)…"
    curl -fsSL https://plannotator.ai/install.sh | bash || warn "Plannotator install did not complete; see https://plannotator.ai"
  fi
else
  say "${D}Skipped. Install later: curl -fsSL https://plannotator.ai/install.sh | bash  (https://plannotator.ai)${N}"
fi
say ""

# ---- write config ----
CFG="$TARGET/hypothesis_tracking/research_loop.yml"
{
  echo "# research_loop project config (read by the research-hypothesis-maintainer skill)"
  echo "# prefix is provisional until the skill confirms it with you on first use"
  echo "prefix: $PREFIX"
  echo "prefix_confirmed: $PREFIX_CONFIRMED"
  echo "project_root: $TARGET"
  echo "scope: $SCOPE"
  echo "# personas: the CONFIRMED panel — empty until the skill confirms it per goal (NOT a default)."
  echo "# CIO / Portfolio Manager / Quant ship in personas_dir only as samples to start from."
  echo "personas: []"
  echo "personas_dir: $PERSONAS_CFG"
  echo "codex: $CODEX_FLAG"
  echo "round_cap: 3"
  echo "# K: minimum candidate proposals on a non-deferred round (Phase-8 coverage floor)."
  echo "K: 2"
  echo "# persona_source: 'local' (.claude/personas) or 'global' (~/.claude/personas, shared"
  echo "# across repos). Under 'global', global wins for confirmed ids; declare per-repo"
  echo "# overrides in persona_overrides. See RESEARCH_PROCESS.md / ADR 0001."
  echo "persona_source: local"
  echo "persona_overrides: []"
  echo "framework_version: $VERSION"
} > "$CFG"
ok "Wrote $CFG"
say ""

# ---- next steps ----
ok "research_loop installed."
say ""
say "${B}Start here →${N} read the how-to guide: ${B}docs/GETTING_STARTED.md${N}"
say "${D}It walks you through your first research loop in a few minutes.${N}"
say ""
say "The short version:"
say "  1. ${B}/plannotator-setup-goal${N}    scope a research question → goal package (seed ideas + round cap)"
say "  2. ${B}/goal goals/<slug>/goal.md${N}  run the hypothesis loop (the skill confirms your ID prefix on first use)"
say "  3. Read ${B}hypothesis_tracking/RESEARCH_HYPOTHESIS_INDEX.md${N} + the decision-maker memo"
say ""
say "${D}More docs: docs/GETTING_STARTED.md · docs/RESEARCH_PROCESS.md · docs/USING_WITH_PLANNOTATOR.md${N}"
