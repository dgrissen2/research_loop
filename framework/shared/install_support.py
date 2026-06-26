#!/usr/bin/env python3
"""Brownfield install helpers (M5): safe .claude/settings.json hook merge + shadow checks.

Factored out of install.sh so the risky, edge-case-laden bits are unit-tested:

- `merge_hook`  — register the Stop hook in .claude/settings.json without clobbering: create
  if absent; ABORT on malformed JSON (leave the file untouched); add exactly once (dedupe by
  a stable marker); preserve all unrelated hooks/keys; write atomically (temp + replace).
- `shadowing_warnings` — under `persona_source: global`, flag stray local same-id persona
  files that would shadow the global library (unless explicitly declared in persona_overrides).

CLI: `install_support.py merge-hook <settings.json> <command>` (used by install.sh).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import contracts as C

HOOK_MARKER = "stop_verify_round"  # dedupe key: any command containing this is "our" hook


class MalformedSettings(RuntimeError):
    """settings.json exists but is not valid JSON — refuse to modify it."""


_atomic_write = C.atomic_write  # shared helper; single definition lives in contracts.py


def merge_hook(settings_path: str | Path, command: str, event: str = "Stop") -> str:
    """Idempotently register a command hook for `event`. Returns 'created'|'added'|'present'."""
    path = Path(settings_path)
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        data: dict = {}
        status = "created"
    else:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise MalformedSettings(f"{path} is not valid JSON ({exc}); not modifying it") from exc
        if not isinstance(data, dict):
            raise MalformedSettings(f"{path} top-level is not an object; not modifying it")
        status = "added"

    hooks = data.setdefault("hooks", {})
    groups = hooks.setdefault(event, [])
    # already present? (dedupe by marker across any group's command entries)
    for group in groups:
        for h in group.get("hooks", []):
            if HOOK_MARKER in str(h.get("command", "")):
                return "present"  # nothing written
    groups.append({"hooks": [{"type": "command", "command": command}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(path, json.dumps(data, indent=2) + "\n")
    return status


def shadowing_warnings(
    project: str | Path, personas: list[str], persona_source: str, overrides: list[str]
) -> list[str]:
    """Under 'global', warn about local same-id persona files that would shadow global."""
    if persona_source != "global":
        return []
    project = Path(project)
    out: list[str] = []
    for pid in personas:
        if pid in overrides:
            continue
        local = project / ".claude" / "personas" / f"{pid}.md"
        if local.is_file():
            out.append(
                f"persona '{pid}': local {local} shadows the global library under "
                f"persona_source: global — remove it or add '{pid}' to persona_overrides."
            )
    return out


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) >= 3 and argv[0] == "merge-hook":
        try:
            status = merge_hook(argv[1], argv[2])
        except MalformedSettings as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(status)
        return 0
    print("usage: install_support.py merge-hook <settings.json> <command>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
