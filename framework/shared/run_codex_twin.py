#!/usr/bin/env python3
"""Bounded, PER-PERSONA-PARALLEL Codex cross-model twin for the persona panel (Mode C).

Each panelist runs as its OWN codex call, all in PARALLEL — not one grouped call:

- A single combined call reasons about every persona in one giant pass: slow and
  un-parallelizable. Per-persona concurrent calls make wall-clock ~ the slowest single
  persona, not the sum.
- Each call is independently bounded and process-group-scoped: codex is launched in its
  own process group (`start_new_session=True`); on timeout we kill ONLY that group
  (`os.killpg`) — never `codex` by name. One hung persona is reaped alone; concurrent
  codex runs from other agents are untouched.
- One retry per persona, then a per-persona fallback. The loop never blocks (the
  in-Claude panel always runs; the twin is an enhancement, never a hard dependency).

Two output modes:
- `--emit markdown` (default, unchanged): a combined cross-model commentary markdown file.
- `--emit json`: per-persona twin records `{persona_id, engine, producer_status,
  interpret, act, artifact_path}` (the contracts twin sub-shape) printed to stdout, for
  `emit.py` to merge into commentary.json. A timeout yields `producer_status:"timeout"`;
  a missing/failed codex yields `"unavailable"` — never a crash.

Usage:
    run_codex_twin.py <note.md> [evidence.txt] <combined_out.md>
        [--personas p1,p2,...] [--timeout 300] [--effort high] [--retries 1]
        [--emit markdown|json]
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PERSONA_HEADER = """Independent cross-model review of a research findings note, adopting the
ONE persona below. Give EXACTLY two paragraphs: (1) interpret THIS specific result through
that persona's lens (use the real numbers); (2) the concrete action that persona takes. Be
adversarial, specific, and brief. Output GitHub markdown only. Do not edit any files.
"""


def persona_prompt(note: Path, evidence: Path | None, persona_path: Path) -> str:
    blocks = [
        PERSONA_HEADER,
        f"=== PERSONA: {persona_path.stem} ===\n{persona_path.read_text()}",
        f"=== FINDINGS NOTE UNDER REVIEW ===\n{note.read_text()}",
    ]
    if evidence and evidence.exists():
        blocks.append(f"=== EVIDENCE ===\n{evidence.read_text()}")
    return "\n\n".join(blocks)


def run_once(prompt: str, out: Path, effort: str, timeout: int) -> tuple[bool, str]:
    """Run codex once, bounded. On timeout kill ONLY this call's process group.

    Returns (ok, reason). reason is 'ok' | 'timeout' | 'unavailable' | <stderr tail>.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    try:
        proc = subprocess.Popen(
            ["codex", "exec", "-m", "gpt-5.6-sol", "-c", f"model_reasoning_effort={effort}",
             "--full-auto", "--skip-git-repo-check", "-o", str(out), "--", prompt],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            start_new_session=True,  # own process group -> killpg reaps codex + child only
        )
    except FileNotFoundError:
        return False, "unavailable"
    try:
        _, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)  # THIS call's group only
        except ProcessLookupError:
            pass
        proc.communicate()
        return False, "timeout"
    ok = out.is_file() and out.stat().st_size > 0
    return ok, "ok" if ok else (stderr or "empty output")[-200:]


def run_persona(note, evidence, persona_path, out_dir, effort, timeout, retries):
    """Run one persona's codex call (with retries). Returns (pid, ok, out_path, reason)."""
    pid = persona_path.stem
    out = out_dir / f"{pid}.md"
    prompt = persona_prompt(note, evidence, persona_path)
    why = "not run"
    for _ in range(retries + 1):
        ok, why = run_once(prompt, out, effort, timeout)
        if ok:
            return pid, True, out, "ok"
    return pid, False, out, why


def _split_two(text: str) -> tuple[str, str]:
    """Split codex markdown into (interpret, act) paragraphs; best-effort."""
    parts = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], "\n\n".join(parts[1:])


def _resolved_source(persona_path: Path) -> str:
    home_personas = (Path.home() / ".claude" / "personas").resolve()
    try:
        persona_path.resolve().relative_to(home_personas)
        return "global"
    except ValueError:
        return "local"


def twin_record(result, persona_path: Path) -> dict:
    """Build a contracts twin sub-record from a run_persona result."""
    pid, ok, opath, why = result
    if ok:
        interpret, act = _split_two(opath.read_text())
        status = "ok"
    else:
        interpret, act = None, None
        status = "timeout" if why == "timeout" else "unavailable"
    return {
        "persona_id": pid,
        "engine": "codex",
        "producer_status": status,
        "interpret": interpret,
        "act": act,
        "artifact_path": str(opath) if ok else None,
        "resolved_source": _resolved_source(persona_path),
        "resolved_path": str(persona_path),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("note")
    ap.add_argument("evidence", nargs="?", default="")
    ap.add_argument("out")
    ap.add_argument("--personas", default="",
                    help="comma-separated persona file paths; default = .claude/personas/*.md")
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("CODEX_TIMEOUT", "300")))
    ap.add_argument("--effort", default="high")
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--emit", choices=("markdown", "json"), default="markdown")
    a = ap.parse_args(argv)

    if a.personas:
        ppaths = [Path(p) for p in a.personas.split(",") if p]
    else:
        ppaths = sorted(Path(".claude/personas").glob("*.md"))
    if not ppaths:
        print("no persona files found", file=sys.stderr)
        return 2

    note = Path(a.note)
    evidence = Path(a.evidence) if a.evidence else None
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    per_dir = out.parent / (out.stem + "_personas")

    # Every persona is its OWN codex call; all run in PARALLEL — each bounded +
    # process-group-scoped, so a hung persona is killed alone and others are untouched.
    with ThreadPoolExecutor(max_workers=len(ppaths)) as ex:
        futs = {
            ex.submit(run_persona, note, evidence, p, per_dir, a.effort, a.timeout, a.retries): p
            for p in ppaths
        }
        results = [(f.result(), futs[f]) for f in futs]

    if a.emit == "json":
        records = [twin_record(res, ppath) for res, ppath in results]
        records.sort(key=lambda r: r["persona_id"])
        print(json.dumps(records, indent=2))
        return 0

    # markdown (default, unchanged behavior)
    sections, ok_count = [], 0
    for (pid, ok, opath, why), _p in sorted(results, key=lambda rp: rp[0][0]):
        if ok:
            ok_count += 1
            sections.append(f"## Cross-model — {pid}\n\n{opath.read_text().strip()}\n")
        else:
            sections.append(f"## Cross-model — {pid}\n\n_cross-model timed out / unavailable "
                            f"({why}); use the in-Claude panel for this persona._\n")
    out.write_text("\n".join(sections) + "\n")

    if ok_count == 0:
        print("twin: all persona calls failed; in-Claude panel stands alone", file=sys.stderr)
        return 1
    print(f"twin ok: {ok_count}/{len(ppaths)} personas (parallel) -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
