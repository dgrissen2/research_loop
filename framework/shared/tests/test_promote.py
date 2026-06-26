"""Tests for promote.py breadth (S6).

Facts: promote-ids, promote-ledger, promote-apply, promote-atomic.
"""

from __future__ import annotations

import json

import contracts as C
import promote
import pytest


# --------------------------------------------------------------------------- ID allocation
def test_existing_max_handles_gaps(project_factory):
    proj = project_factory()
    ht = proj / "hypothesis_tracking"
    fm = "---\nid: H-FIX-007\nround: 1\nhypothesis_status: active\nphase: recorded\n---\n"
    (ht / "h-fix-007_x_2026-06-13.md").write_text(fm + "# H-FIX-007\n", encoding="utf-8")
    assert promote._existing_max(proj, "H", "FIX") == 7  # not 1, despite gap


def test_existing_max_ignores_prose_ids(project_factory):
    # Provisional ID-like tokens in a note's BODY must NOT inflate/skip allocation (finding B).
    proj = project_factory()
    ht = proj / "hypothesis_tracking"
    fm = "---\nid: H-FIX-001\nround: 1\nhypothesis_status: active\nphase: recorded\n---\n"
    body = "# H-FIX-001\n\nOther experiments to run: E-FIX-555, H-FIX-099 (provisional).\n"
    (ht / "h-fix-001_demo_2026-06-13.md").write_text(fm + body, encoding="utf-8")
    # only the real frontmatter id H-FIX-001 counts; prose E-FIX-555 / H-FIX-099 ignored.
    assert promote._existing_max(proj, "H", "FIX") == 1
    assert promote._existing_max(proj, "E", "FIX") == 0


def test_id_exists_ignores_prose(project_factory):
    # A note's PROSE mentioning the NEXT id must not trigger a false collision (finding B).
    proj = project_factory()
    ht = proj / "hypothesis_tracking"
    note = ht / "h-fix-001_demo_2026-06-13.md"
    note.write_text(
        note.read_text(encoding="utf-8")
        + "\n\nNext up we should open H-FIX-002 to test the OOS regime.\n",
        encoding="utf-8",
    )
    # promote allocates H-FIX-002 (next after the real frontmatter id H-FIX-001); the
    # prose mention is ignored, so apply_round does NOT raise an ID collision.
    result = promote.apply_round(proj, 1)
    assert "H-FIX-002" in {n["id"] for n in result["created_notes"]}


def test_id_exists_checks_allocations_not_prose(project_factory):
    proj = project_factory()
    ht = proj / "hypothesis_tracking"
    note = ht / "h-fix-001_demo_2026-06-13.md"
    note.write_text(
        note.read_text(encoding="utf-8") + "\nmentions H-FIX-002 only in prose\n",
        encoding="utf-8",
    )
    assert promote._id_exists(proj, "H-FIX-001") is True   # real frontmatter allocation
    assert promote._id_exists(proj, "H-FIX-002") is False  # prose-only -> not allocated
    assert promote._allocated_nums(proj, "H", "FIX") == {1}


def test_collision_guard(project_factory, monkeypatch):
    proj = project_factory()
    ht = proj / "hypothesis_tracking"
    # A REAL allocation (frontmatter id), not prose — this is what a true collision looks like.
    fm = "---\nid: H-FIX-005\nround: 1\nhypothesis_status: active\nphase: recorded\n---\n"
    (ht / "h-fix-005_x_2026-06-13.md").write_text(fm + "# H-FIX-005\n", encoding="utf-8")
    # Force a stale max so the next id (H-FIX-005) collides with the real allocation above.
    monkeypatch.setattr(promote, "_existing_max", lambda *a, **k: 4)
    with pytest.raises(C.ContractError, match="collision"):
        promote.apply_round(proj, 1)


# --------------------------------------------------------------------------- ledger / convergence
def test_ledger_one_entry_per_decision(project_factory):
    proj = project_factory()
    promote.apply_round(proj, 1)
    ledger = json.loads((proj / "outputs" / "promotion_ledger.json").read_text())
    # qqq-beta-adjust has 2 sources but is ONE decision -> ONE ledger entry.
    assert set(ledger) == {"round1/qqq-beta-adjust", "round1/oos-validation"}


def test_experiment_row_no_note(project_factory):
    proj = project_factory()
    promote.apply_round(proj, 1)
    index = (proj / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md").read_text()
    _, followup = C.read_index_table(index, "followup")
    eids = {row["Experiment ID"] for row in followup}
    assert eids == {"E-FIX-001"}
    notes = list((proj / "hypothesis_tracking").glob("*e-fix-001*"))
    assert not notes  # experiments get a row, not a note


# --------------------------------------------------------------------------- reprioritize
def test_reprioritize_drop_and_deprioritize():
    cols_h = "| " + " | ".join(C.INDEX_HYPOTHESES_COLUMNS) + " |"
    sep_h = "|" + "|".join("---" for _ in C.INDEX_HYPOTHESES_COLUMNS) + "|"
    cols_e = "| " + " | ".join(C.INDEX_FOLLOWUP_COLUMNS) + " |"
    sep_e = "|" + "|".join("---" for _ in C.INDEX_FOLLOWUP_COLUMNS) + "|"
    hrow = "| H-FIX-009 |" + " |" * (len(C.INDEX_HYPOTHESES_COLUMNS) - 1)
    erow = ("| E-FIX-002 | exp | why | s | H-FIX-001 | note | high | planned |")
    md = "\n".join(["## Hypotheses", cols_h, sep_h, hrow, "",
                    "## Follow-Up Experiments", cols_e, sep_e, erow, ""]) + "\n"
    synthesis = {"reprioritize": [
        {"id": "H-FIX-009", "action": "drop", "why": "superseded"},
        {"id": "E-FIX-002", "action": "deprioritize", "why": "lower"},
    ]}
    out, done = promote._apply_reprioritize(md, synthesis)
    assert {d["id"] for d in done} == {"H-FIX-009", "E-FIX-002"}
    h_line = next(ln for ln in out.splitlines() if ln.startswith("| H-FIX-009"))
    assert "dropped" in h_line
    e_line = next(ln for ln in out.splitlines() if ln.startswith("| E-FIX-002"))
    assert "| medium |" in e_line  # high -> medium


def test_supersede_experiment():
    cols_e = "| " + " | ".join(C.INDEX_FOLLOWUP_COLUMNS) + " |"
    sep_e = "|" + "|".join("---" for _ in C.INDEX_FOLLOWUP_COLUMNS) + "|"
    erow = "| E-FIX-003 | exp | why | s | H-FIX-001 | note | medium | planned |"
    md = "\n".join(["## Follow-Up Experiments", cols_e, sep_e, erow, ""]) + "\n"
    out = promote._supersede_experiment(md, "E-FIX-003", "H-FIX-010")
    line = next(ln for ln in out.splitlines() if ln.startswith("| E-FIX-003"))
    assert "dropped (promoted to H-FIX-010)" in line


# --------------------------------------------------------------------------- atomicity
def test_atomic_rollback(project_factory, monkeypatch):
    proj = project_factory()
    ht = proj / "hypothesis_tracking"
    before = set(ht.glob("*.md"))

    def boom(path, content):
        raise RuntimeError("disk full")

    monkeypatch.setattr(promote, "_atomic_write", boom)
    with pytest.raises(RuntimeError):
        promote.apply_round(proj, 1)
    after = set(ht.glob("*.md"))
    assert after == before  # created note(s) rolled back
    assert not (proj / "outputs" / "promotion_ledger.json").exists()
