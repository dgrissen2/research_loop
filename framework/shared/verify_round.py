#!/usr/bin/env python3
"""verify_round.py — the deterministic back-half gate for research_loop.

Reads ONLY the on-disk artifacts (notes + index + memo + JSON artifacts) for a given
round and decides whether the round is closeable. Exit codes:

    0  round is closeable
    2  round incomplete (a machine-keyed punchlist is printed to stdout)
    3  a required artifact is malformed/structurally invalid

State authority is the artifacts (D1/D2): there is no cache and no --rebuild-state in v1.
All JSON structure + the markdown grammar come from contracts.py (one shared code path).
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import contracts as C


@dataclass(frozen=True)
class Problem:
    """A single gate failure. severity: 'incomplete' (exit 2) or 'malformed' (exit 3)."""

    severity: str
    key: str
    message: str


# --------------------------------------------------------------------------- config + notes
def _scalar(value: str) -> Any:
    """Parse the tiny scalar subset used in research_loop.yml."""
    value = value.strip()
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lstrip("-").isdigit():
        return int(value)
    return value.strip("\"'")


def _coerce_config_value(key: str, value: Any) -> Any:
    """Apply key-aware coercions after quote stripping."""
    if key == "codex" and isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    return value


def load_config(project: Path) -> dict[str, Any]:
    """Minimal research_loop.yml reader (scalars, inline lists, block lists/maps)."""
    path = project / "hypothesis_tracking" / "research_loop.yml"
    cfg: dict[str, Any] = {
        "personas": [], "codex": False, "round_cap": 1, "K": 2,
        "persona_source": "local", "persona_overrides": [],
    }
    if not path.is_file():
        return cfg
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip() or ":" not in line or line[0] in " -":
            # block list items are consumed by their key below
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if val.startswith("[") and val.endswith("]"):
            cfg[key] = [v.strip().strip("\"'") for v in val[1:-1].split(",") if v.strip()]
        elif val == "":
            indented: list[str] = []
            while i < len(lines) and (
                lines[i].startswith((" ", "\t")) or not lines[i].strip()
            ):
                child = lines[i].split("#", 1)[0].rstrip()
                i += 1
                if child.strip():
                    indented.append(child.lstrip())
            if indented and indented[0].startswith("- "):
                cfg[key] = [item[2:].strip().strip("\"'") for item in indented
                            if item.startswith("- ")]
            elif indented:
                block: dict[str, Any] = {}
                for child in indented:
                    if ":" not in child or child.startswith("- "):
                        continue
                    ckey, _, cval = child.partition(":")
                    block[ckey.strip()] = _scalar(cval)
                cfg[key] = block
            else:
                cfg[key] = []
        else:
            cfg[key] = _coerce_config_value(key, _scalar(val))
    return cfg


def iter_notes(project: Path) -> list[tuple[Path, str, dict[str, str]]]:
    """Return (path, text, frontmatter) for each findings note (h-*.md, excludes memos)."""
    ht = project / "hypothesis_tracking"
    out = []
    for p in sorted(ht.glob("h-*.md")):
        if p.name.startswith("memo-"):
            continue
        text = p.read_text(encoding="utf-8")
        out.append((p, text, C.parse_frontmatter(text)))
    return out


def active_for_round(notes, rnd: int) -> list[tuple[Path, str, dict[str, str]]]:
    """Active set = frontmatter round == rnd and hypothesis_status == 'active' (D2)."""
    sel = []
    for p, text, fm in notes:
        if fm.get("round") == str(rnd) and fm.get("hypothesis_status") == "active":
            sel.append((p, text, fm))
    return sel


# --------------------------------------------------------------------------- per-note checks
def note_headings(text: str) -> list[str]:
    return [ln.lstrip("#").strip() for ln in text.splitlines() if ln.lstrip().startswith("#")]


def check_note_completeness(text: str, key: str) -> list[Problem]:
    problems: list[Problem] = []
    headings_blob = " || ".join(note_headings(text)).lower()
    for section in C.NOTE_REQUIRED_SECTIONS:
        if section.lower() not in headings_blob:
            problems.append(Problem("incomplete", key, f"missing required section: {section}"))
    if not any(v in text for v in C.VERDICTS):
        problems.append(Problem("incomplete", key, "no verdict from the allowed set"))
    return problems


def check_backlinks(project: Path, note_path: Path, text: str, key: str) -> list[Problem]:
    problems: list[Problem] = []
    for target in C.link_targets(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        clean = target.split("#", 1)[0]
        if not clean:
            continue
        resolved = (note_path.parent / clean).resolve()
        if not resolved.exists():
            problems.append(Problem("incomplete", key, f"dangling backlink: {target}"))
    return problems


def _twin_attempted(twin: Any) -> bool:
    """True iff `twin` is a real cross-model attempt: a SUPPORTED engine + a producer_status.

    A block whose engine is not a supported twin engine (e.g. a stray 'gemini'/'claude') does
    NOT satisfy the codex-attempt requirement (fact-twin-engine), even if it carries a status.
    """
    return (
        isinstance(twin, dict)
        and twin.get("engine") in C.SUPPORTED_TWIN_ENGINES
        and bool(twin.get("producer_status"))
    )


def _check_persona_twins(
    personas: list[dict[str, Any]], key: str, require_twin: bool, where: str
) -> list[Problem]:
    """Shared twin rule for Phase-1 seed + Phase-6 commentary (fact-twin-three-phases).

    When require_twin, every persona must carry an ATTEMPTED twin (supported engine +
    producer_status). A genuine timeout/unavailable still passes (non-blocking, D8); a
    missing OR foreign-engine twin = the twin was silently skipped, and fails (exit 2).
    Also enforces the relational rule: producer_status != ok => agreement == twin_absent.
    """
    problems: list[Problem] = []
    engines = "/".join(C.SUPPORTED_TWIN_ENGINES)
    for p in personas:
        twin = p.get("twin")
        attempted = _twin_attempted(twin)
        if require_twin and not attempted:
            problems.append(
                Problem("incomplete", key,
                        f"{p.get('persona_id')}: codex enabled but no cross-model twin attempt "
                        f"in {where} (need a {engines} twin with producer_status)")
            )
            continue
        if (
            attempted
            and twin.get("producer_status") != "ok"
            and p.get("agreement") != "twin_absent"
        ):
            problems.append(
                Problem("incomplete", key,
                        f"{p.get('persona_id')}: twin {twin.get('producer_status')} but agreement "
                        f"!= twin_absent")
            )
    return problems


def check_commentary(
    project: Path, rnd: int, hid: str, personas: list[str], key: str, require_twin: bool
) -> list[Problem]:
    problems: list[Problem] = []
    path = project / "outputs" / "commentary" / f"round{rnd}" / f"{hid}.json"
    if not path.is_file():
        return [Problem("incomplete", key, f"missing commentary.json for {hid}")]
    try:
        data = C.load_commentary(path)
    except C.MalformedArtifact as exc:
        return [Problem("malformed", key, str(exc))]
    by_persona = {p["persona_id"]: p for p in data["personas"]}
    for persona in personas:
        if persona not in by_persona:
            problems.append(
                Problem("incomplete", key, f"commentary missing persona block: {persona}")
            )
    problems += _check_persona_twins(data["personas"], key, require_twin, "commentary")
    return problems


# --------------------------------------------------------------------------- phase-1 seed check
def check_seed_expansion(project: Path, rnd: int, cfg: dict[str, Any]) -> list[Problem]:
    """Phase-1 gate (round 1 only): personas + twins must have expanded the seed set.

    Required only when codex is enabled AND personas are configured — a standalone chat-start
    program with no panel has no seed expansion to gate (documented limitation). When required,
    a missing `outputs/seed_expansion.json` fails; a present file must carry a twin attempt per
    persona, the same rule as commentary (fact-twin-three-phases, fact-phase1-expansion).
    """
    if rnd != 1:
        return []
    personas = list(cfg.get("personas", []))
    require_twin = bool(cfg.get("codex"))
    path = project / "outputs" / "seed_expansion.json"
    if not path.is_file():
        if require_twin and personas:
            return [Problem("incomplete", "seed",
                            "round 1: missing seed_expansion.json (codex enabled — Phase-1 "
                            "persona+twin seed expansion is required)")]
        return []
    raw = path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw) if raw.strip() else None
    except json.JSONDecodeError as exc:
        return [Problem("malformed", "seed", f"seed_expansion.json invalid: {exc}")]
    if not isinstance(data, dict) or not isinstance(data.get("personas"), list):
        return [Problem("malformed", "seed", "seed_expansion.json: missing personas[] array")]
    blocks = [b for b in data["personas"] if isinstance(b, dict)]
    problems: list[Problem] = []
    present = {b.get("persona_id") for b in blocks}
    for pid in personas:
        if pid not in present:
            problems.append(
                Problem("incomplete", "seed", f"seed_expansion missing persona block: {pid}")
            )
    problems += _check_persona_twins(blocks, "seed", require_twin, "seed expansion")
    return problems


# --------------------------------------------------------------------------- phase-8 checks
def check_phase8(project: Path, rnd: int, cfg: dict[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    pp = project / "outputs" / "proposals" / f"round{rnd}.json"
    sp = project / "outputs" / "synthesis" / f"round{rnd}.json"
    if not pp.is_file() or not sp.is_file():
        return [Problem("incomplete", "phase8", "missing proposals.json or synthesis.json")]
    try:
        proposals = C.load_proposals(pp)
        synthesis = C.load_synthesis(sp)
    except C.MalformedArtifact as exc:
        return [Problem("malformed", "phase8", str(exc))]

    blocks = proposals["blocks"]
    # (persona_id, engine) -> set(candidate_key); and the full candidate-key universe.
    block_keys: dict[tuple[str, str], set[str]] = {}
    all_candidate_keys: set[str] = set()
    for b in blocks:
        ck = {c["candidate_key"] for c in b.get("candidates", [])}
        block_keys[(b["persona_id"], b["engine"])] = ck
        all_candidate_keys |= ck

    # codex enabled => Phase-8 proposals must ALSO carry a cross-model twin attempt per persona
    # (a block with a supported twin engine + producer_status). emit.build_proposals always
    # writes it; here the gate REQUIRES it so a silently-skipped twin can't pass
    # (fact-twin-three-phases).
    if bool(cfg.get("codex")):
        twin_personas = {
            b["persona_id"] for b in blocks
            if b.get("engine") in C.SUPPORTED_TWIN_ENGINES and b.get("producer_status")
        }
        for pid in cfg.get("personas", []):
            if pid not in twin_personas:
                engines = "/".join(C.SUPPORTED_TWIN_ENGINES)
                problems.append(
                    Problem("incomplete", "phase8",
                            f"{pid}: codex enabled but no cross-model twin proposals block "
                            f"(need a {engines} block with producer_status)")
                )

    deferred = synthesis["deferred"]["is_deferred"]
    K = int(cfg.get("K", 2))
    # Count DISTINCT candidate keys, not raw records: a single idea echoed by the Claude
    # and Codex blocks (same candidate_key) is one proposal, not two (it collapses to one
    # decision), so it must not trivially satisfy the K floor.
    distinct = len(all_candidate_keys)
    if not deferred and distinct < K:
        problems.append(Problem("incomplete", "phase8", f"distinct candidates {distinct} < K={K}"))

    covered: set[str] = set()
    for d in synthesis["decisions"]:
        for s in d["sources"]:
            covered.add(s["candidate_key"])
            blk = block_keys.get((s["persona_id"], s["engine"]))
            if blk is None or s["candidate_key"] not in blk:
                problems.append(
                    Problem("incomplete", "phase8",
                            f"decision {d['decision_key']}: untraceable source "
                            f"{s['persona_id']}/{s['engine']}/{s['candidate_key']}")
                )
    uncovered = all_candidate_keys - covered
    if uncovered:
        problems.append(
            Problem("incomplete", "phase8",
                    f"proposal candidates not covered by any decision: {sorted(uncovered)}")
        )

    problems += check_materialization(project, rnd, synthesis)
    return problems


def check_materialization(project: Path, rnd: int, synthesis: dict[str, Any]) -> list[Problem]:
    problems: list[Problem] = []
    ledger_path = project / "outputs" / "promotion_ledger.json"
    ledger: dict[str, Any] = {}
    if ledger_path.is_file():
        try:
            ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return [Problem("malformed", "phase8", f"promotion_ledger.json invalid: {exc}")]
    for d in synthesis["decisions"]:
        if d["classification"] not in {"promote", "experiment"}:
            continue
        lkey = f"round{rnd}/{d['decision_key']}"
        if lkey not in ledger:
            problems.append(
                Problem("incomplete", "phase8",
                        f"decision {d['decision_key']} not materialized (no ledger entry {lkey})")
            )
    return problems


def check_provenance(project: Path, rnd: int, cfg: dict[str, Any],
                     active) -> list[Problem]:
    """Each persona record's resolved_source must match the configured persona_source
    (an undeclared 'local' resolution under 'global' fails; overrides may resolve local)."""
    source = cfg.get("persona_source", "local")
    overrides = set(cfg.get("persona_overrides", []))
    problems: list[Problem] = []

    def _check(records, where: str) -> None:
        for r in records:
            pid = r.get("persona_id")
            rsrc = r.get("resolved_source")
            if rsrc is None:
                continue
            allowed = "local" if (source == "global" and pid in overrides) else source
            if rsrc != allowed:
                problems.append(
                    Problem("incomplete", where,
                            f"{pid}: resolved_source={rsrc} but persona_source={source} "
                            f"(not in persona_overrides)")
                )

    pp = project / "outputs" / "proposals" / f"round{rnd}.json"
    if pp.is_file():
        try:
            _check(C.load_proposals(pp)["blocks"], "provenance")
        except C.MalformedArtifact:
            pass  # malformed already reported by check_phase8
    for _p, _t, fm in active:
        hid = fm.get("id", "")
        cpath = project / "outputs" / "commentary" / f"round{rnd}" / f"{hid}.json"
        if cpath.is_file():
            try:
                _check(C.load_commentary(cpath)["personas"], "provenance")
            except C.MalformedArtifact:
                pass
    return problems


# --------------------------------------------------------------------------- decision-maker memo
# Match the FIELD by its label, not a strict value shape, so a second/stale/placeholder
# `**Status:**`/`**Verdict:**` line is still COUNTED (and rejected) instead of silently ignored.
_STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\*(.*)$", re.MULTILINE)
_VERDICT_LINE_RE = re.compile(r"^\*\*Verdict:\*\*(.*)$", re.MULTILINE)
_FINAL_STATUS = {"final", "finalized"}
# Verdict enum surface forms, MOST-SPECIFIC FIRST so the 'supported' inside 'not supported' is
# masked by 'not_supported' and 'weak support' is never miscounted (§1 states exactly one enum).
_ENUM_PATTERNS = (
    ("not_supported", re.compile(r"\bnot[\s_-]+supported\b", re.IGNORECASE)),
    ("weak_support", re.compile(r"\bweak[\s_-]+support\b", re.IGNORECASE)),
    ("inconclusive", re.compile(r"\binconclusive\b", re.IGNORECASE)),
    ("supported", re.compile(r"\bsupported\b", re.IGNORECASE)),
    ("mixed", re.compile(r"\bmixed\b", re.IGNORECASE)),
)


def _canon_enum(value: str) -> str:
    """Canonical verdict id: lowercase, collapse runs of space/underscore/hyphen to '_'."""
    return re.sub(r"[\s_-]+", "_", value.strip().lower())


def _memo_section(text: str, num: int) -> str | None:
    """Body lines between the '## <num>' h2 and the next h2 (None if the heading is absent).

    `\\b` after the number tolerates '## 1.', '## 1)', '## 1 Foo' but NOT '## 10.'/'## 12.'.
    """
    head = re.compile(rf"^##\s+{num}\b")
    out: list[str] = []
    capturing = False
    for line in text.splitlines():
        if not capturing:
            if head.match(line):
                capturing = True
            continue
        if re.match(r"^##\s+\S", line):  # next h2 ends the region ('###' is not an h2)
            break
        out.append(line)
    return "\n".join(out) if capturing else None


def _enum_hits(text: str) -> dict[str, int]:
    """Count whole-token verdict enums in `text`, masking each match longest-first."""
    counts: dict[str, int] = {}
    masked = text
    for canon_id, pat in _ENUM_PATTERNS:
        masked, n = pat.subn(lambda m: " " * (m.end() - m.start()), masked)
        if n:
            counts[canon_id] = n
    return counts


def _is_separator_row(cells: list[str]) -> bool:
    """A markdown table delimiter row, e.g. |---|:--:|---| (cells of only '-', ':', space)."""
    return bool(cells) and all(c and set(c) <= set("-: ") for c in cells)


def _timeline_row_for_round(section4: str, rnd: int) -> bool:
    """True iff §4 has a markdown TABLE with a `Round` column and a data row for round `rnd`.

    Tables are CONTIGUOUS runs of `|` lines, each evaluated on its own — a second, non-timeline
    table later in §4 cannot lend its rows to the timeline. A run counts only as a real table with
    a header + a `|---|` separator + at least one data row. Cells use the shared escaped-pipe-aware
    splitter so a literal `\\|` inside a cell does not shift the `Round` column.
    """

    def _block_matches(block: list[str]) -> bool:
        if len(block) < 3:  # header + separator + >= 1 data row
            return False
        header = [c.lower() for c in C._split_row(block[0])]
        if "round" not in header or not _is_separator_row(C._split_row(block[1])):
            return False
        ridx = header.index("round")
        for row in block[2:]:
            cells = C._split_row(row)
            if _is_separator_row(cells):
                continue
            if ridx < len(cells) and cells[ridx].strip("` ") == str(rnd):
                return True
        return False

    block: list[str] = []
    for line in section4.splitlines():
        if line.strip().startswith("|"):
            block.append(line)
        elif _block_matches(block):
            return True
        else:
            block = []
    return _block_matches(block)


def _termination_state(cfg: dict[str, Any], rnd: int) -> tuple[dict[str, Any] | None, bool, bool]:
    """(termination | None, terminated_here, at_cap). Raises MalformedArtifact if invalid."""
    termination = C.load_termination(cfg.get("termination"))
    terminated_here = bool(
        termination and termination["status"] == "terminated" and termination["round"] == rnd
    )
    at_cap = rnd == int(cfg.get("round_cap", rnd))
    return termination, terminated_here, at_cap


def _is_final_round(cfg: dict[str, Any], rnd: int) -> bool:
    """Whether round `rnd` is a finalizing close (the cap or a same-round termination)."""
    try:
        _t, terminated_here, at_cap = _termination_state(cfg, rnd)
    except C.MalformedArtifact:
        return False
    return at_cap or terminated_here


def _check_memo_finalized(memo: Path, text: str) -> list[Problem]:
    """One memo is finalized iff Status resolves to 'final', Verdict resolves to one enum, and §1
    states exactly that one enum (no other). Per-memo, so a stale sibling memo can't mask it."""
    name = memo.name
    statuses = _STATUS_LINE_RE.findall(text)
    if len(statuses) != 1:
        return [Problem("incomplete", "memo",
                        f"{name}: memo not finalized (need exactly one '**Status:**' line, "
                        f"found {len(statuses)})")]
    if statuses[0].strip("` ").lower() not in _FINAL_STATUS:
        return [Problem("incomplete", "memo",
                        f"{name}: memo not finalized (Status '{statuses[0].strip()}' is not "
                        f"'final')")]
    verdicts = _VERDICT_LINE_RE.findall(text)
    if len(verdicts) != 1:
        return [Problem("incomplete", "memo",
                        f"{name}: memo not finalized (need exactly one '**Verdict:**' line, "
                        f"found {len(verdicts)})")]
    header_enum = _canon_enum(verdicts[0].strip("` "))
    if header_enum not in C.VERDICTS:
        return [Problem("incomplete", "memo",
                        f"{name}: memo not finalized (Verdict '{verdicts[0].strip()}' is not one "
                        f"of {sorted(C.VERDICTS)})")]
    section1 = _memo_section(text, 1)
    if section1 is None:
        return [Problem("incomplete", "memo",
                        f"{name}: memo not finalized (no '## 1.' Executive Summary section)")]
    hits = _enum_hits(section1)
    if set(hits) != {header_enum} or hits.get(header_enum) != 1:
        return [Problem("incomplete", "memo",
                        f"{name}: memo not finalized (§1 must state the verdict '{header_enum}' "
                        f"exactly once and no other verdict; found {dict(hits) or 'none'})")]
    return []


def check_memo(project: Path, rnd: int, cfg: dict[str, Any]) -> list[Problem]:
    ht = project / "hypothesis_tracking"
    memos = sorted(ht.glob("memo-*.md"))
    if not memos:
        return [Problem("incomplete", "memo", "no decision-maker memo found")]

    # Program-level early-termination decision (human-authorized; fact-early-stop-human-only).
    # The gate only READS the recorded decision — it never terminates a program on its own.
    try:
        termination, terminated_here, at_cap = _termination_state(cfg, rnd)
    except C.MalformedArtifact as exc:
        return [Problem("malformed", "memo", f"termination block invalid: {exc}")]

    texts = {m: m.read_text(encoding="utf-8") for m in memos}
    problems: list[Problem] = []

    if termination and termination["status"] == "terminated" and termination["round"] != rnd:
        problems.append(
            Problem("incomplete", "memo",
                    f"termination round {termination['round']} does not match verified round {rnd}")
        )

    # Every memo grows its §4 Timeline by one row each round — require a data row whose `Round`
    # cell == N, per memo (a prose mention or a row without a matching Round cell no longer counts).
    for memo, text in texts.items():
        section4 = _memo_section(text, 4)
        if section4 is None or not _timeline_row_for_round(section4, rnd):
            problems.append(
                Problem("incomplete", "memo",
                        f"{memo.name}: §4 Timeline has no row for round {rnd}")
            )

    # The early stop must be recorded in the memo too, not only in research_loop.yml (program-level
    # marker — any memo carrying it satisfies the rule).
    if terminated_here:
        blob = "\n".join(texts.values()).lower()
        if not re.search(r"terminat|converg|early[ -]?stop", blob):
            problems.append(
                Problem("incomplete", "memo",
                        "early termination recorded in research_loop.yml but the memo has no "
                        "termination/convergence decision marker (must be recorded in BOTH)")
            )

    # `deferred` is untouched: a round N < cap with no termination block closes WITHOUT
    # finalization (fact-deferred-scoped). Finalization is required only at the cap OR when a
    # termination is recorded for THIS round (fact-early-term-finalized) — validated per memo.
    if at_cap or terminated_here:
        for memo, text in texts.items():
            problems += _check_memo_finalized(memo, text)
    return problems


# --------------------------------------------------------------------------- driver
def verify(project: Path, rnd: int) -> list[Problem]:
    cfg = load_config(project)
    personas = list(cfg.get("personas", []))
    require_twin = bool(cfg.get("codex"))
    problems: list[Problem] = []
    active = active_for_round(iter_notes(project), rnd)
    for note_path, text, fm in active:
        hid = fm.get("id", note_path.stem)
        key = hid
        problems += check_note_completeness(text, key)
        problems += check_backlinks(project, note_path, text, key)
        problems += check_commentary(project, rnd, hid, personas, key, require_twin)
    problems += check_seed_expansion(project, rnd, cfg)
    problems += check_phase8(project, rnd, cfg)
    problems += check_provenance(project, rnd, cfg, active)
    problems += check_memo(project, rnd, cfg)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="research_loop round gate")
    parser.add_argument("--round", type=int, required=True, help="round number to verify")
    parser.add_argument("--project", default=".", help="project root (default: cwd)")
    args = parser.parse_args(argv)
    project = Path(args.project).resolve()

    problems = verify(project, args.round)
    malformed = [p for p in problems if p.severity == "malformed"]
    incomplete = [p for p in problems if p.severity == "incomplete"]

    if malformed:
        print(f"## verify_round — round {args.round}: MALFORMED ({len(malformed)})")
        for p in malformed:
            print(f"  [3] {p.key}: {p.message}")
        return C.EXIT_MALFORMED
    if incomplete:
        print(f"## verify_round — round {args.round}: INCOMPLETE ({len(incomplete)})")
        for p in incomplete:
            print(f"  [2] {p.key}: {p.message}")
        return C.EXIT_INCOMPLETE
    print(f"## verify_round — round {args.round}: OK — round is closeable")
    # On a finalizing close (the round cap or a same-round termination), surface the artifacts the
    # human will open next as stable, parseable lines distinct from the OK banner.
    if _is_final_round(load_config(project), args.round):
        ht = project / "hypothesis_tracking"
        for memo in sorted(ht.glob("memo-*.md")):
            print(f"MEMO: {memo.resolve()}")
        print(f"INDEX: {(ht / 'RESEARCH_HYPOTHESIS_INDEX.md').resolve()}")
    return C.EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
