#!/usr/bin/env python3
"""Run an independent Codex plan review with optional persona overlays."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
from pathlib import Path


def _find_persona_registry() -> Path | None:
    """Locate persona_registry.py — vendored (project-local / global Claude) first,
    skillshare last. Honors RESEARCH_LOOP_PERSONA_REGISTRY override."""
    here = Path(__file__).resolve().parent
    candidates: list[Path] = []
    env = os.environ.get("RESEARCH_LOOP_PERSONA_REGISTRY")
    if env:
        candidates.append(Path(env).expanduser())
    candidates += [
        here,                                    # co-located with this script
        here.parent,                             # skill dir
        here.parent.parent,                      # skills root (install) / codex dir (repo)
        # installed shared resolver (SKILLS_DIR/_research_loop)
        here.parent.parent / "_research_loop",
        here.parent.parent.parent / "shared",    # repo dev layout: framework/shared
        Path.home() / ".claude" / "skills" / "_research_loop",
        # optional skillshare fallback
        Path.home() / ".config" / "skillshare" / "skills" / "persona-registry" / "scripts",
    ]
    for cand in candidates:
        if (cand / "persona_registry.py").is_file():
            return cand
    return None


_registry_dir = _find_persona_registry()
if _registry_dir is not None:
    sys.path.insert(0, str(_registry_dir))

from persona_registry import Persona, parse_tokens, resolve_personas  # noqa: E402,I001


DEFAULT_MODEL = "gpt-5.5"
DEFAULT_EFFORT = "xhigh"


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_file", nargs="?", help="Plan or design doc to review.")
    parser.add_argument("context_files", nargs="*", help="Optional spec/context files.")
    parser.add_argument("--personas", default="", help="Comma-separated personas or paths.")
    parser.add_argument("--persona-dir", action="append", default=[], help="Extra persona source.")
    parser.add_argument("--list-personas", action="store_true", help="List personas and exit.")
    parser.add_argument("--skip-generic", action="store_true", help="Only run persona overlays.")
    parser.add_argument("--no-synthesis", action="store_true", help="Skip synthesis.")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Codex model (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--effort",
        default=DEFAULT_EFFORT,
        help=f"Codex reasoning effort (default: {DEFAULT_EFFORT}).",
    )
    return parser.parse_args()


def repo_root(cwd: Path) -> Path:
    """Resolve git repo root, falling back to cwd."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    return cwd


def resolve_file(raw_path: str) -> Path:
    """Resolve and validate a file path."""
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    if not path.is_file():
        raise ValueError(f"File not found: {raw_path}")
    return path


def output_path(source_file: Path, suffix: str) -> Path:
    """Build a review output path next to the source file."""
    if source_file.suffix:
        return source_file.with_name(f"{source_file.stem}_{suffix}{source_file.suffix}")
    return source_file.with_name(f"{source_file.name}_{suffix}.md")


def context_lines(context_files: list[Path]) -> str:
    """Format context files for prompts."""
    return "\n".join(f"- {path}" for path in context_files) or "- None"


def generic_prompt(plan_file: Path, context_files: list[Path]) -> str:
    """Build the generic Codex plan review prompt."""
    return f"""You are reviewing a plan, roadmap, or design document.
This is NOT a code review. You have not seen prior reviewer comments.

Plan file:
- {plan_file}

Context files:
{context_lines(context_files)}

Read the files and evaluate:
1. Internal consistency: formulas, ranges, definitions, and milestones agree.
2. Spec fidelity: requirements missing from the plan or invented by the plan.
3. Logic errors: impossible thresholds, wrong comparisons, range overflow.
4. Data contracts: missing fields, undefined enums, units, and cross-milestone gaps.
5. Dependencies: ordering, parallelism claims, and unbuilt prerequisites.
6. Edge cases: division by zero, NaN, empty inputs, boundaries, rollback paths.
7. Test adequacy: coverage matches the plan's actual risk.

Output exactly:
## Codex Plan Review — Verdict: PASS / CONDITIONAL PASS / FAIL (N findings)

| # | Finding | Severity | Dimension | Details |
|---|---------|----------|-----------|---------|
"""


def persona_prompt(plan_file: Path, context_files: list[Path], persona: Persona) -> str:
    """Build a persona-specific plan review prompt."""
    return f"""You are reviewing a plan through this persona lens:
- {persona.path}

Adopt the persona as an analytical lens. Do not imitate theatrical style.
You have not seen other reviewers' findings.

Plan file:
- {plan_file}

Context files:
{context_lines(context_files)}

Focus on what this persona would uniquely catch: missing contracts, hidden risks,
bad assumptions, infeasible milestones, weak validation, or domain-specific gaps.

Output exactly:
## Codex Plan Review — {persona.name}
**Verdict**: PASS / CONDITIONAL PASS / FAIL (N findings)

| # | Finding | Severity | Dimension | Details |
|---|---------|----------|-----------|---------|
"""


def synthesis_prompt(outputs: list[tuple[str, str]]) -> str:
    """Build synthesis prompt across plan reviews."""
    reviews = "\n\n".join(f"### {name}\n\n{output}" for name, output in outputs)
    return f"""Synthesize these independent plan reviews. Deduplicate findings, preserve
severity, and do not invent new issues not supported by a review.

{reviews}

Output exactly:
## Codex Plan Review — Panel Synthesis

| # | Finding | Severity | Dimension | Flagged By | Confidence |
|---|---------|----------|-----------|------------|------------|
"""


def run_codex(prompt: str, output_file: Path, model: str, effort: str) -> str:
    """Run Codex and return the output file contents."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    # Bounded + process-group-scoped: launch codex in its OWN session/process group and, on
    # timeout, kill ONLY that group (os.killpg) — never `codex` by name — so concurrent codex
    # runs from other agents/sessions are left untouched. Timeout: CODEX_TIMEOUT env (default 300s).
    timeout = int(os.environ.get("CODEX_TIMEOUT", "300"))
    proc = subprocess.Popen(
        [
            "codex",
            "exec",
            "-m",
            model,
            "-c",
            f"model_reasoning_effort={effort}",
            "--full-auto",
            "-o",
            str(output_file),
            "--",
            prompt,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)  # this invocation's group ONLY
        except ProcessLookupError:
            pass
        proc.communicate()
        raise RuntimeError(
            f"codex exec exceeded {timeout}s (killed its process group; other codex runs untouched)"
        ) from None
    if not output_file.is_file() or output_file.stat().st_size == 0:
        raise RuntimeError(stderr.strip() or stdout.strip() or "codex exec produced no output")
    return output_file.read_text(encoding="utf-8")


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    root = repo_root(Path.cwd())
    try:
        if args.list_personas:
            from persona_registry import discover_personas, print_table

            print_table(discover_personas(cwd=root, extra_sources=args.persona_dir))
            return 0

        if not args.plan_file:
            raise ValueError("plan_file is required unless --list-personas is used.")

        plan_file = resolve_file(args.plan_file)
        context_files = [resolve_file(path) for path in args.context_files]
        personas = resolve_personas(
            parse_tokens([args.personas]) if args.personas else [],
            cwd=root,
            extra_sources=args.persona_dir,
        )

        outputs: list[tuple[str, str]] = []
        if not args.skip_generic:
            review = run_codex(
                generic_prompt(plan_file, context_files),
                output_path(plan_file, "codex_review"),
                args.model,
                args.effort,
            )
            outputs.append(("Generic", review))

        for persona in personas:
            review = run_codex(
                persona_prompt(plan_file, context_files, persona),
                output_path(plan_file, f"{persona.id}_plan_review"),
                args.model,
                args.effort,
            )
            outputs.append((persona.name, review))

        if len(outputs) > 1 and not args.no_synthesis:
            review = run_codex(
                synthesis_prompt(outputs),
                output_path(plan_file, "plan_panel_synthesis"),
                args.model,
                args.effort,
            )
            outputs.append(("Panel Synthesis", review))

        print("\n\n---\n\n".join(output for _name, output in outputs))
        return 0
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
