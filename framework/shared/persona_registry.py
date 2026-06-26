#!/usr/bin/env python3
"""Resolve persona avatar (.md) files for research_loop.

Discovery is project-local first, then the global Claude folder (~/.claude/personas).
A skillshare install (~/.config/skillshare) is supported only as an OPTIONAL last-resort
fallback if it happens to exist — research_loop never assumes or requires it.

This resolver is framework-level (not Codex-specific): it is installed regardless of whether
the Codex skills are, so Claude-only users still get persona listing/resolution.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Optional skillshare fallback locations (used only if present; not required).
SKILLSHARE_PERSONAS = Path.home() / ".config" / "skillshare" / "personas"
SKILLSHARE_SKILLS = Path.home() / ".config" / "skillshare" / "skills"


@dataclass(frozen=True)
class Persona:
    """Resolved persona metadata."""

    id: str
    name: str
    aliases: tuple[str, ...]
    domain: str
    path: str
    status: str = "unknown"
    version: str = ""


def normalize_alias(value: str) -> str:
    """Normalize an alias or ID for lookup."""
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def split_list(value: str) -> list[str]:
    """Parse a simple YAML-ish scalar list."""
    stripped = value.strip()
    if not stripped:
        return []
    if stripped.startswith("[") and stripped.endswith("]"):
        inner = stripped[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("\"'") for part in inner.split(",") if part.strip()]
    return [stripped.strip("\"'")]


def parse_frontmatter(text: str) -> dict[str, Any]:
    """Parse the small frontmatter subset used by persona files."""
    if not text.startswith("---\n"):
        return {}
    _, _, remainder = text.partition("---\n")
    frontmatter, separator, _body = remainder.partition("\n---\n")
    if not separator:
        return {}

    data: dict[str, Any] = {}
    current_list_key = ""
    for raw_line in frontmatter.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_list_key:
            data.setdefault(current_list_key, []).append(line[4:].strip().strip("\"'"))
            continue
        current_list_key = ""
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            data[key] = []
            current_list_key = key
        elif value.startswith("["):
            data[key] = split_list(value)
        else:
            data[key] = value.strip("\"'")
    return data


def heading_name(text: str, path: Path) -> str:
    """Extract a display name from markdown content."""
    for line in text.splitlines()[:80]:
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip()
        title = re.sub(r"^Persona(?: Avatar)?:\s*", "", title, flags=re.I)
        return title or path.stem.replace("_", " ").replace("-", " ").title()
    return path.stem.replace("_", " ").replace("-", " ").title()


def persona_from_path(path: Path) -> Persona | None:
    """Load persona metadata from one markdown file."""
    if not path.is_file() or path.suffix.lower() != ".md":
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="replace")

    frontmatter = parse_frontmatter(text)
    persona_id = str(frontmatter.get("id") or normalize_alias(path.stem))
    name = str(frontmatter.get("name") or heading_name(text, path))
    domain = str(frontmatter.get("domain") or path.parent.name)
    status = str(frontmatter.get("status") or "legacy")
    version = str(frontmatter.get("version") or "")

    aliases = set(frontmatter.get("aliases") or [])
    aliases.update({persona_id, path.stem, path.stem.replace("_", "-")})
    aliases.add(name)
    normalized_aliases = tuple(sorted({normalize_alias(alias) for alias in aliases if alias}))
    return Persona(
        id=normalize_alias(persona_id),
        name=name,
        aliases=normalized_aliases,
        domain=domain,
        path=str(path),
        status=status,
        version=version,
    )


def expand_source(source: str) -> list[Path]:
    """Expand a file, directory, or glob source to markdown paths."""
    expanded = os.path.expanduser(source)
    if any(char in expanded for char in "*?[]"):
        return sorted(Path(path).resolve() for path in glob.glob(expanded, recursive=True))

    path = Path(expanded).resolve()
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.glob("**/*.md"))
    return []


def env_sources() -> list[str]:
    """Return explicit persona sources from the environment.

    PERSONA_PATHS is the standard override (colon-separated files, dirs, or globs).
    SKILLSHARE_PERSONA_PATHS is still honored for backward compatibility, but is not required.
    """
    raw = os.environ.get("PERSONA_PATHS") or os.environ.get("SKILLSHARE_PERSONA_PATHS", "")
    return [source for source in raw.split(os.pathsep) if source]


GLOBAL_CLAUDE_PERSONAS = Path.home() / ".claude" / "personas"


def default_sources(cwd: Path) -> list[str]:
    """Return default persona discovery sources.

    research_loop policy: resolve personas PROJECT-LOCAL first, then fall back to
    the global Claude personas folder, then the skillshare canonical/legacy stores.
    First-match-wins, so a project-local persona overrides a global one of the same id.
    """
    return [
        # 1. project-local (where research_loop installs personas)
        str(cwd / ".claude" / "personas" / "**/*.md"),
        str(cwd / "personas" / "**/*.md"),
        str(cwd / "docs" / "personas" / "**/*.md"),
        str(cwd / ".skillshare" / "personas" / "**/*.md"),
        # 2. global Claude folder (where `--global` / global installs land)
        str(GLOBAL_CLAUDE_PERSONAS / "**/*.md"),
        # 3. OPTIONAL skillshare fallback (only if present; never required)
        str(SKILLSHARE_PERSONAS / "**/*.md"),
        str(SKILLSHARE_SKILLS / "*" / "personas" / "*.md"),
    ]


def discover_personas(
    cwd: Path | None = None,
    extra_sources: list[str] | None = None,
) -> list[Persona]:
    """Discover personas using first-match-wins alias semantics."""
    cwd = (cwd or Path.cwd()).resolve()
    sources = [*env_sources(), *(extra_sources or []), *default_sources(cwd)]
    seen_paths: set[Path] = set()
    personas_by_id: dict[str, Persona] = {}
    known_aliases: set[str] = set()

    for source in sources:
        for path in expand_source(source):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            persona = persona_from_path(path)
            if persona is None:
                continue
            if persona.id in personas_by_id:
                continue
            if persona.status != "canonical" and persona.id in known_aliases:
                continue
            personas_by_id[persona.id] = persona
            known_aliases.update(persona.aliases)
    return list(personas_by_id.values())


def registry_by_alias(personas: list[Persona]) -> dict[str, Persona]:
    """Build alias lookup for resolved personas."""
    registry: dict[str, Persona] = {}
    for persona in personas:
        registry.setdefault(persona.id, persona)
        for alias in persona.aliases:
            registry.setdefault(alias, persona)
    return registry


def parse_tokens(raw_tokens: list[str]) -> list[str]:
    """Parse comma-separated persona tokens."""
    parsed: list[str] = []
    for raw in raw_tokens:
        parsed.extend(token.strip() for token in raw.split(",") if token.strip())
    return parsed


def resolve_personas(
    tokens: list[str],
    cwd: Path | None = None,
    extra_sources: list[str] | None = None,
) -> list[Persona]:
    """Resolve persona aliases or direct paths."""
    personas = discover_personas(cwd=cwd, extra_sources=extra_sources)
    registry = registry_by_alias(personas)
    resolved: list[Persona] = []
    errors: list[str] = []

    for token in tokens:
        path = Path(token).expanduser()
        if path.is_file():
            persona = persona_from_path(path.resolve())
        else:
            persona = registry.get(normalize_alias(token))
        if persona is None:
            errors.append(token)
            continue
        if persona not in resolved:
            resolved.append(persona)

    if errors:
        sample = ", ".join(sorted(registry)[:30])
        raise ValueError(f"Unknown persona(s): {', '.join(errors)}. Known aliases: {sample}")
    return resolved


def print_table(personas: list[Persona]) -> None:
    """Print personas as a markdown table."""
    print("| ID | Name | Domain | Aliases | Path |")
    print("|---|---|---|---|---|")
    for persona in sorted(personas, key=lambda item: (item.domain, item.id)):
        short_aliases = [alias for alias in persona.aliases if alias != persona.id][:5]
        aliases = ", ".join(f"`{alias}`" for alias in short_aliases)
        print(
            f"| `{persona.id}` | {persona.name} | {persona.domain} | "
            f"{aliases} | `{persona.path}` |"
        )


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true", help="List discovered personas.")
    parser.add_argument("--resolve", nargs="*", help="Resolve comma-separated aliases or paths.")
    parser.add_argument("--persona-dir", action="append", default=[], help="Extra persona source.")
    parser.add_argument("--cwd", default=str(Path.cwd()), help="Project cwd for local discovery.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")
    return parser.parse_args()


def main() -> int:
    """CLI entrypoint."""
    args = parse_args()
    cwd = Path(args.cwd).expanduser().resolve()
    try:
        if args.resolve is not None:
            personas = resolve_personas(
                parse_tokens(args.resolve),
                cwd=cwd,
                extra_sources=args.persona_dir,
            )
        else:
            personas = discover_personas(cwd=cwd, extra_sources=args.persona_dir)
        if args.json:
            print(json.dumps([asdict(persona) for persona in personas], indent=2))
        else:
            print_table(personas)
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
