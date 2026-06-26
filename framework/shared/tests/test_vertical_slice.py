"""End-to-end vertical slice (S4): one hypothesis through promote -> verify.

Proves the deterministic spine: a round is INCOMPLETE before promotion materializes
its Phase-8 decisions, OK after, and INCOMPLETE again if a required artifact is removed.
"""

from __future__ import annotations

import contracts as C
import promote
import verify_round


def test_incomplete_before_promote_then_ok_after(project_factory):
    proj = project_factory()

    # Before promotion: synthesis decisions are not yet materialized -> exit 2.
    rc = verify_round.main(["--round", "1", "--project", str(proj)])
    assert rc == C.EXIT_INCOMPLETE

    # Promote the round-1 synthesis (creates H-FIX-002 note + E-FIX-001 row + ledger).
    result = promote.apply_round(proj, 1)
    assert result["created_notes"] and result["experiments_added"]
    ledger = (proj / "outputs" / "promotion_ledger.json").read_text(encoding="utf-8")
    assert "round1/oos-validation" in ledger and "round1/qqq-beta-adjust" in ledger

    # After promotion: the round is closeable -> exit 0.
    rc = verify_round.main(["--round", "1", "--project", str(proj)])
    assert rc == C.EXIT_OK


def test_promoted_note_lands_in_next_round(project_factory):
    proj = project_factory()
    promote.apply_round(proj, 1)
    # The promoted hypothesis is Round 2 / active -> not gated in round 1.
    notes = verify_round.iter_notes(proj)
    r2 = [fm for _p, _t, fm in notes if fm.get("round") == "2"]
    assert r2 and all(fm["hypothesis_status"] == "active" for fm in r2)
    assert verify_round.active_for_round(notes, 1)  # only h-fix-001 active in round 1
    assert len(verify_round.active_for_round(notes, 1)) == 1


def test_missing_commentary_fails_gate(project_factory):
    proj = project_factory(with_commentary=False)
    promote.apply_round(proj, 1)
    rc = verify_round.main(["--round", "1", "--project", str(proj)])
    assert rc == C.EXIT_INCOMPLETE


def test_promote_is_idempotent(project_factory):
    proj = project_factory()
    first = promote.apply_round(proj, 1)
    assert not first["skipped_existing"]
    second = promote.apply_round(proj, 1)
    skipped = {s["decision_key"] for s in second["skipped_existing"]}
    assert skipped == {"oos-validation", "qqq-beta-adjust"}
    assert not second["created_notes"]
