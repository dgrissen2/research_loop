"""Tests for the Stop hook decision logic (S8 / fact: hook)."""

from __future__ import annotations

import promote
import stop_verify_round as hook


def test_open_incomplete_round_blocks(project_factory):
    proj = project_factory()  # round 1 active, synthesis not yet materialized
    block, message = hook.decide(proj)
    assert block is True
    assert "Round 1 is not closeable" in message


def test_complete_round_allows_stop(project_factory):
    proj = project_factory()
    promote.apply_round(proj, 1)  # materialize -> round 1 closeable
    block, message = hook.decide(proj)
    assert block is False


def test_earlier_incomplete_round_still_blocks(project_factory):
    # Round 1 left incomplete (not promoted); round 2 has started. The hook must still
    # gate round 1 — not just the latest started round.
    proj = project_factory()  # round 1 active, not materialized -> incomplete
    ht = proj / "hypothesis_tracking"
    fm2 = "---\nid: H-FIX-002\nround: 2\nhypothesis_status: active\nphase: recorded\n---\n"
    (ht / "h-fix-002_x_2026-06-17.md").write_text(fm2 + "# H-FIX-002\n", encoding="utf-8")
    (proj / "outputs" / "proposals" / "round2.json").write_text(
        '{"round":2,"blocks":[]}', encoding="utf-8"
    )
    block, message = hook.decide(proj)
    assert block is True
    assert "Round 1" in message  # earlier round not skipped


def test_no_active_round_allows_stop(project_factory):
    proj = project_factory()
    # flip the only active note to dropped -> no open round to gate
    note = proj / "hypothesis_tracking" / "h-fix-001_demo_2026-06-13.md"
    note.write_text(
        note.read_text().replace("hypothesis_status: active", "hypothesis_status: dropped"),
        encoding="utf-8",
    )
    block, _ = hook.decide(proj)
    assert block is False
