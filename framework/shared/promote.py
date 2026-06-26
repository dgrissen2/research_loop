#!/usr/bin/env python3
"""promote.py — deterministically apply a round's synthesis decisions.

Reads ``outputs/synthesis/round<N>.json`` and materializes its decisions into the
filesystem: `promote` decisions create a findings-note stub + a `Hypotheses` index row
at ``Round = N+1`` / ``hypothesis_status: active``; `experiment` decisions add a
`Follow-Up Experiments` row; `reprioritize` entries apply the contracts action->edit map.
Idempotent via ``promotion_ledger.json`` keyed ``round<N>/<decision_key>``. All writes are
staged and committed together (temp + atomic replace) with rollback of created notes on
failure. Markdown grammar + enums come from contracts.py (one shared code path).
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any

import contracts as C


def _read_prefix(project: Path) -> str:
    cfg = project / "hypothesis_tracking" / "research_loop.yml"
    if cfg.is_file():
        for ln in cfg.read_text(encoding="utf-8").splitlines():
            if ln.strip().startswith("prefix:"):
                return ln.split(":", 1)[1].strip().strip("\"'")
    return "HYP"


def _slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "untitled"


def _allocated_nums(project: Path, kind_letter: str, prefix: str) -> set[int]:
    """Numeric suffixes of every *allocated* ID of this kind/prefix.

    Reads only authoritative sources — note frontmatter ``id:``, the index ID columns, and
    the promotion ledger — NOT raw note prose. A provisional ID-like token written in a
    note's "Other Experiments" text is prose, never an allocation, so it can neither inflate
    the next number nor trigger a false collision.
    """
    ht = project / "hypothesis_tracking"
    prefix = prefix.upper()
    nums: set[int] = set()

    def _consider(raw: str) -> None:
        pid = C.parse_id((raw or "").strip())
        if pid and pid["kind"] == kind_letter and pid["prefix"] == prefix:
            nums.add(pid["num"])

    # 1) note frontmatter ids
    for p in ht.glob("h-*.md"):
        _consider(C.parse_frontmatter(p.read_text(encoding="utf-8")).get("id", ""))
    # 2) index ID columns
    idx = ht / "RESEARCH_HYPOTHESIS_INDEX.md"
    if idx.is_file():
        md = idx.read_text(encoding="utf-8")
        for table, col in (("hypotheses", "Hypothesis ID"), ("followup", "Experiment ID")):
            try:
                _, rows = C.read_index_table(md, table)
            except C.ContractError:
                rows = []
            for r in rows:
                _consider(r.get(col, ""))
    # 3) ledger (already-allocated this program)
    led = project / "outputs" / "promotion_ledger.json"
    if led.is_file():
        text = led.read_text(encoding="utf-8").strip()
        try:
            for v in (json.loads(text) if text else {}).values():
                _consider(v.get("id", ""))
        except json.JSONDecodeError:
            pass
    return nums


def _existing_max(project: Path, kind_letter: str, prefix: str) -> int:
    """Highest numeric suffix among *allocated* IDs of this kind/prefix (0 if none)."""
    return max({0} | _allocated_nums(project, kind_letter, prefix))


def _id_exists(project: Path, hid: str) -> bool:
    """True if `hid` is an *allocated* stable ID (authoritative sources only).

    Checks the allocated-number set for the ID's kind/prefix — never a raw-prose glob — so a
    note that merely *mentions* the next id in its text can no longer cause a false collision.
    """
    pid = C.parse_id(hid)
    if not pid:
        return False
    return pid["num"] in _allocated_nums(project, pid["kind"], pid["prefix"])


def _supersede_experiment(index_md: str, exp_id: str, by_hid: str) -> str:
    """Mark a Follow-Up Experiments row dropped/superseded and backlink the new hypothesis."""
    cols = list(C.INDEX_FOLLOWUP_COLUMNS)
    lines = index_md.splitlines()
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith(f"| {exp_id} "):
            row = dict(zip(cols, C._split_row(ln), strict=False))
            row["Status"] = f"dropped (promoted to {by_hid})"
            lines[i] = C.format_index_row("followup", row)
            break
    return "\n".join(lines) + ("\n" if index_md.endswith("\n") else "")


def _note_stub(hid: str, rnd: int, decision: dict[str, Any]) -> str:
    fm = C.format_frontmatter(
        {"id": hid, "round": rnd, "hypothesis_status": "active", "phase": "method"}
    )
    title = decision.get("title", "")
    parent = decision.get("parent")
    parent_line = f"\nPromoted from synthesis; parent: `{parent}`.\n" if parent else "\n"
    return (
        f"{fm}\n# {hid} — {title}\n{parent_line}\n"
        f"## 3. Claim Being Tested\n\n{decision.get('rationale', title)}\n\n"
        f"_Stub created by promote.py for round {rnd}; fill in when this hypothesis is worked._\n\n"
        f"[Index](RESEARCH_HYPOTHESIS_INDEX.md)\n"
    )


def apply_round(project: Path, rnd: int) -> dict[str, Any]:
    """Apply round `rnd`'s synthesis. Returns the structured result; raises on hard errors."""
    synthesis = C.load_synthesis(project / "outputs" / "synthesis" / f"round{rnd}.json")
    prefix = _read_prefix(project)
    index_path = project / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md"
    index_md = index_path.read_text(encoding="utf-8")
    ledger_path = project / "outputs" / "promotion_ledger.json"
    _ledger_text = ledger_path.read_text(encoding="utf-8").strip() if ledger_path.is_file() else ""
    ledger: dict[str, Any] = json.loads(_ledger_text) if _ledger_text else {}

    result: dict[str, Any] = {
        "created_notes": [], "index_rows_added": [], "experiments_added": [],
        "reprioritized": [], "skipped_existing": [],
        "deferred": synthesis["deferred"]["is_deferred"],
    }
    h_num = _existing_max(project, "H", prefix)
    e_num = _existing_max(project, "E", prefix)
    staged_notes: list[tuple[Path, str]] = []

    for d in synthesis["decisions"]:
        lkey = f"round{rnd}/{d['decision_key']}"
        if lkey in ledger:
            result["skipped_existing"].append(
                {"decision_key": d["decision_key"], "id": ledger[lkey]["id"]}
            )
            continue
        if d["classification"] == "promote":
            h_num += 1
            hid = C.stable_id("H", prefix, h_num)
            if _id_exists(project, hid):
                raise C.ContractError(f"ID collision: {hid} already exists")
            today = datetime.date.today().isoformat()
            fname = f"h-{prefix.lower()}-{h_num:03d}_{_slug(d['title'])}_{today}.md"
            note_path = project / "hypothesis_tracking" / fname
            staged_notes.append((note_path, _note_stub(hid, rnd + 1, d)))
            link = f"[{hid.lower()}]({fname})"
            index_md = C.append_index_row(index_md, "hypotheses", {
                "Hypothesis ID": hid, "Claim": d.get("title", ""), "Scope": "—",
                "Note": link, "Status": "active", "Best Evidence": "—",
                "Next Step": "work in next round", "Round": str(rnd + 1),
            })
            ledger[lkey] = {"id": hid, "path": str(note_path.relative_to(project)),
                            "kind": "hypothesis", "table": "hypotheses"}
            result["created_notes"].append(
                {"decision_key": d["decision_key"], "id": hid, "path": fname}
            )
            result["index_rows_added"].append({"id": hid, "table": "Hypotheses"})
            # PR-11: promoting an existing experiment supersedes it (mark dropped + backlink).
            from_exp = d.get("from_experiment_id")
            if from_exp:
                index_md = _supersede_experiment(index_md, from_exp, hid)
                result.setdefault("superseded", []).append({"experiment": from_exp, "by": hid})
        elif d["classification"] == "experiment":
            e_num += 1
            eid = C.stable_id("E", prefix, e_num)
            index_md = C.append_index_row(index_md, "followup", {
                "Experiment ID": eid, "Proposed Experiment": d.get("title", ""),
                "Why Run It": d.get("reason", ""), "Scope": "—",
                "Parent Hypothesis": d.get("parent") or "", "Source Note": "synthesis",
                "Priority": d.get("priority", "medium"), "Status": "planned",
            })
            ledger[lkey] = {"id": eid, "kind": "experiment", "table": "followup"}
            result["experiments_added"].append({"id": eid, "table": "Follow-Up Experiments"})

    index_md, reprioritized = _apply_reprioritize(index_md, synthesis)
    result["reprioritized"] = reprioritized

    _commit(index_path, index_md, staged_notes, ledger_path, ledger)
    return result


def _apply_reprioritize(
    index_md: str, synthesis: dict[str, Any]
) -> tuple[str, list[dict[str, str]]]:
    """Apply deprioritize/drop edits to existing rows in either index table (action map).

    `drop` sets Status=dropped (both tables); `deprioritize` lowers a Priority cell one step
    (Follow-Up Experiments only — Hypotheses rows have no Priority, so it is a no-op there).
    The target's ID prefix (H-/E-) selects the column layout.
    """
    _lower = {"high": "medium", "medium": "low", "low": "low"}
    done: list[dict[str, str]] = []
    for r in synthesis.get("reprioritize", []):
        action = r.get("action")
        rid = r["id"]
        if action not in C.ACTIONS:
            continue
        parsed = C.parse_id(rid)
        table = "hypotheses" if (parsed and parsed["kind"] == "H") else "followup"
        cols = list(C.INDEX_HYPOTHESES_COLUMNS if table == "hypotheses"
                    else C.INDEX_FOLLOWUP_COLUMNS)
        lines = index_md.splitlines()
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith(f"| {rid} "):
                row = dict(zip(cols, C._split_row(ln), strict=False))
                if action == "drop":
                    row["Status"] = "dropped"
                elif action == "deprioritize" and "Priority" in row:
                    row["Priority"] = _lower.get(row.get("Priority", "").strip(), "low")
                lines[i] = C.format_index_row(table, row)
                done.append({"id": rid, "action": action})
                break
        index_md = "\n".join(lines) + ("\n" if index_md.endswith("\n") else "")
    return index_md, done


def _commit(index_path: Path, index_md: str, staged_notes, ledger_path: Path, ledger) -> None:
    """Write notes + index + ledger atomically; roll back created notes on failure."""
    written: list[Path] = []
    try:
        for path, content in staged_notes:
            _atomic_write(path, content)
            written.append(path)
        _atomic_write(index_path, index_md)
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(ledger_path, json.dumps(ledger, indent=2) + "\n")
    except Exception:
        for path in written:
            path.unlink(missing_ok=True)
        raise


_atomic_write = C.atomic_write  # shared helper; single definition lives in contracts.py


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="apply a round's synthesis decisions")
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--project", default=".")
    args = parser.parse_args(argv)
    try:
        result = apply_round(Path(args.project).resolve(), args.round)
    except (C.ContractError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
