#!/usr/bin/env python3
"""Claude Code Stop hook — blocks ending a turn while a research round is open + incomplete.

Determines the currently-open round from the artifacts (the highest round with an active
hypothesis), runs `verify_round.verify()`, and — if the round is incomplete or has a
malformed artifact — returns a block decision with the punchlist so the agent must finish
the back half before stopping. If there is nothing to gate, it allows the stop.

Ship-only: the installer copies this to `.claude/hooks/` and registers it in target
projects. It is NOT activated in the framework repo itself (which runs no rounds).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _ensure_scripts_on_path(project: Path) -> None:
    """Make `verify_round` importable from the installed _research_loop dir (or dev tree)."""
    candidates = [
        project / ".claude" / "skills" / "_research_loop",
        Path.home() / ".claude" / "skills" / "_research_loop",
        Path(__file__).resolve().parent.parent / "shared",  # dev layout: framework/shared
    ]
    for cand in candidates:
        if (cand / "verify_round.py").is_file():
            sys.path.insert(0, str(cand))
            return


def decide(project: Path) -> tuple[bool, str]:
    """Return (block, message). block=True means the round is open and not closeable."""
    _ensure_scripts_on_path(project)
    try:
        import verify_round
    except ImportError:
        return False, "verify_round not found; cannot gate (allowing stop)"

    notes = verify_round.iter_notes(project)
    # A round is a closeable-candidate only if it has been *started* — freshly promoted
    # backlog (phase: method, no artifacts yet) is the NEXT round's work, not this one's.
    started: set[int] = set()
    for _p, _t, fm in notes:
        if fm.get("hypothesis_status") != "active" or not fm.get("round", "").isdigit():
            continue
        rnd = int(fm["round"])
        proposals = project / "outputs" / "proposals" / f"round{rnd}.json"
        cdir = project / "outputs" / "commentary" / f"round{rnd}"
        worked = fm.get("phase", "") not in ("", "method")
        if proposals.is_file() or (cdir.is_dir() and any(cdir.glob("*.json"))) or worked:
            started.add(rnd)
    if not started:
        return False, "no open round"
    # Gate EVERY started round, not just the latest — an earlier round left incomplete
    # (e.g. its notes never finished) must still block, even if a later round has begun.
    failing: list[str] = []
    for rnd in sorted(started):
        problems = verify_round.verify(project, rnd)
        if problems:
            failing.append(f"Round {rnd} is not closeable ({len(problems)} item(s)):")
            failing += [f"  - {p.key}: {p.message}" for p in problems]
    if not failing:
        return False, f"rounds {sorted(started)} closeable"
    return True, "\n".join(failing)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        payload = {}
    project = Path(payload.get("cwd") or ".").resolve()
    block, message = decide(project)
    if block:
        # Block the Stop and surface the punchlist as the reason.
        print(json.dumps({"decision": "block", "reason": message}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
