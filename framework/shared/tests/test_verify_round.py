"""verify_round.py gate — the section-6 test matrix (S7).

Facts: gate-state, gate-notes, gate-commentary, gate-backlinks, gate-phase8,
gate-memo, gate-exit.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import contracts as C
import promote
import verify_round

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _ok_project(project_factory, **kw):
    """A project that PASSES round 1 (synthesis materialized via promote)."""
    proj = project_factory(**kw)
    promote.apply_round(proj, 1)
    return proj


def _run(proj, rnd=1):
    return verify_round.main(["--round", str(rnd), "--project", str(proj)])


def _read(p):
    return json.loads(p.read_text())


def _write(p, obj):
    p.write_text(json.dumps(obj, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- happy + state
def test_complete_round_is_closeable(project_factory):
    assert _run(_ok_project(project_factory)) == C.EXIT_OK


def test_freshly_promoted_note_not_gated_this_round(project_factory):
    proj = _ok_project(project_factory)
    notes = verify_round.iter_notes(proj)
    assert len(verify_round.active_for_round(notes, 1)) == 1  # only h-fix-001
    assert verify_round.active_for_round(notes, 2)  # promoted note lives in round 2


# --------------------------------------------------------------------------- notes
def test_missing_note_section_fails(project_factory, capsys):
    proj = _ok_project(project_factory)
    note = proj / "hypothesis_tracking" / "h-fix-001_demo_2026-06-13.md"
    text = note.read_text().replace("## 15. Threats To Validity And Confounds", "## 15. (removed)")
    note.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "Threats To Validity" in capsys.readouterr().out


def test_dangling_backlink_fails(project_factory, capsys):
    proj = _ok_project(project_factory)
    note = proj / "hypothesis_tracking" / "h-fix-001_demo_2026-06-13.md"
    note.write_text(note.read_text() + "\n[ghost](../scripts/nope.py)\n", encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "dangling backlink" in capsys.readouterr().out


# --------------------------------------------------------------------------- commentary
def test_commentary_missing_persona_fails(project_factory, capsys):
    proj = _ok_project(project_factory)
    cpath = proj / "outputs" / "commentary" / "round1" / "H-FIX-001.json"
    data = _read(cpath)
    data["personas"] = [p for p in data["personas"] if p["persona_id"] != "cio"]
    _write(cpath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "missing persona block: cio" in capsys.readouterr().out


def test_twin_not_ok_requires_twin_absent(project_factory, capsys):
    proj = _ok_project(project_factory)
    cpath = proj / "outputs" / "commentary" / "round1" / "H-FIX-001.json"
    data = _read(cpath)
    # quant twin timed out but agreement claims 'agree' -> relational violation (exit 2)
    for p in data["personas"]:
        if p["persona_id"] == "quant":
            p["twin"]["producer_status"] = "timeout"
            p["agreement"] = "agree"
    _write(cpath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "twin_absent" in capsys.readouterr().out


# --------------------------------------------------------------------------- phase 8
def test_coverage_failure(project_factory, capsys):
    proj = _ok_project(project_factory)
    spath = proj / "outputs" / "synthesis" / "round1.json"
    data = _read(spath)
    data["decisions"] = [d for d in data["decisions"] if d["decision_key"] != "oos-validation"]
    _write(spath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "not covered" in capsys.readouterr().out


def test_traceability_failure(project_factory, capsys):
    proj = _ok_project(project_factory)
    spath = proj / "outputs" / "synthesis" / "round1.json"
    data = _read(spath)
    for d in data["decisions"]:
        if d["decision_key"] == "oos-validation":
            d["sources"][0]["engine"] = "gemini"  # no matching proposal block
    _write(spath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "untraceable" in capsys.readouterr().out


def test_k_floor_non_deferred(project_factory, capsys):
    proj = _ok_project(project_factory)
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text().replace("K: 1", "K: 99"), encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "K=99" in capsys.readouterr().out


def test_deferred_round_passes(project_factory):
    proj = project_factory()  # no promote needed: deferred decisions don't materialize
    shutil.copy(FIXTURES / "deferred_synthesis.json",
                proj / "outputs" / "synthesis" / "round1.json")
    assert _run(proj) == C.EXIT_OK


def test_deferred_round_below_cap_no_finalization_required(project_factory):
    proj = project_factory(round_cap=3)
    shutil.copy(FIXTURES / "deferred_synthesis.json",
                proj / "outputs" / "synthesis" / "round1.json")
    # below the cap, no termination -> the living memo is not finalized, yet the round still closes
    memo_text = (proj / "hypothesis_tracking" / "memo-fix-decision.md").read_text()
    assert "**Status:** `living`" in memo_text
    assert _run(proj) == C.EXIT_OK


def test_malformed_artifact_exit3(project_factory, capsys):
    proj = _ok_project(project_factory)
    (proj / "outputs" / "synthesis" / "round1.json").write_text("{ not json", encoding="utf-8")
    assert _run(proj) == C.EXIT_MALFORMED


# --------------------------------------------------------------------------- memo
def test_memo_missing_round_fails(project_factory, capsys):
    proj = _ok_project(project_factory)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    memo.write_text("# Memo\n\n## Timeline\n- nothing here\n", encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "§4 Timeline has no row for round 1" in capsys.readouterr().out


def test_codex_true_requires_twin_attempt(project_factory, capsys):
    # codex:true but the twin was never attempted (no twin block) -> gate fails (finding A).
    proj = _ok_project(project_factory)
    cpath = proj / "outputs" / "commentary" / "round1" / "H-FIX-001.json"
    data = _read(cpath)
    for p in data["personas"]:
        p.pop("twin", None)
        p["agreement"] = "twin_absent"
    _write(cpath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "no cross-model twin attempt" in capsys.readouterr().out


def test_twin_foreign_engine_does_not_satisfy(project_factory, capsys):
    proj = _ok_project(project_factory)
    cpath = proj / "outputs" / "commentary" / "round1" / "H-FIX-001.json"
    data = _read(cpath)
    for p in data["personas"]:
        p["twin"] = {"engine": "gemini", "producer_status": "ok",
                     "interpret": "x", "act": "y", "artifact_path": None}
        p["agreement"] = "agree"
    _write(cpath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "no cross-model twin attempt" in capsys.readouterr().out


def test_codex_true_twin_timeout_still_passes(project_factory):
    # a real attempt that timed out is non-blocking (D8) -> still closeable.
    proj = _ok_project(project_factory)
    cpath = proj / "outputs" / "commentary" / "round1" / "H-FIX-001.json"
    data = _read(cpath)
    for p in data["personas"]:
        p["twin"] = {"engine": "codex", "producer_status": "timeout",
                     "interpret": None, "act": None, "artifact_path": None}
        p["agreement"] = "twin_absent"
    _write(cpath, data)
    assert _run(proj) == C.EXIT_OK


def test_codex_false_twin_not_required(project_factory):
    proj = _ok_project(project_factory)
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text().replace("codex: true", "codex: false"), encoding="utf-8")
    cpath = proj / "outputs" / "commentary" / "round1" / "H-FIX-001.json"
    data = _read(cpath)
    for p in data["personas"]:
        p.pop("twin", None)
        p["agreement"] = "twin_absent"
    _write(cpath, data)
    assert _run(proj) == C.EXIT_OK  # codex off -> twin optional


def test_seed_expansion_requires_twin(project_factory, capsys):
    proj = _ok_project(project_factory)
    spath = proj / "outputs" / "seed_expansion.json"
    data = _read(spath)
    for p in data["personas"]:
        p.pop("twin", None)
        p["agreement"] = "twin_absent"
    _write(spath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "seed expansion" in capsys.readouterr().out


def test_phase8_requires_codex_block(project_factory, capsys):
    proj = _ok_project(project_factory)
    ppath = proj / "outputs" / "proposals" / "round1.json"
    data = _read(ppath)
    data["blocks"] = [
        b for b in data["blocks"]
        if not (b["persona_id"] == "cio" and b["engine"] == "codex")
    ]
    _write(ppath, data)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "cross-model twin proposals block" in capsys.readouterr().out


def test_config_reads_termination_block(project_factory):
    proj = project_factory()
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text() + (
        "termination:\n"
        "  status: terminated\n"
        "  reason: converged\n"
        "  round: 1\n"
        "  authorized_by: user\n"
    ), encoding="utf-8")
    assert verify_round.load_config(proj)["termination"] == {
        "status": "terminated",
        "reason": "converged",
        "round": 1,
        "authorized_by": "user",
    }


def test_config_reads_quoted_codex_false_as_false(project_factory):
    proj = project_factory()
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text().replace("codex: true", 'codex: "false"'), encoding="utf-8")
    assert verify_round.load_config(proj)["codex"] is False


def test_memo_round_match_is_anchored(project_factory, capsys):
    # A §4 row for round 12 must NOT satisfy the round-1 requirement (exact Round-cell match).
    proj = _ok_project(project_factory)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    memo.write_text(
        "# Memo\n\n## 4. Timeline\n\n"
        "| Round | Date | Step | What happened | Artifact |\n"
        "|---|---|---|---|---|\n"
        "| 12 | 2026-06-13 | x | later work | y |\n",
        encoding="utf-8",
    )
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "§4 Timeline has no row for round 1" in capsys.readouterr().out


def test_k_floor_counts_distinct_keys(project_factory, capsys):
    # Two blocks echo the SAME candidate_key -> 1 distinct idea, must fail K=2.
    proj = project_factory(k=2)
    _write(proj / "outputs" / "proposals" / "round1.json", {
        "round": 1,
        "blocks": [
            {"persona_id": "quant", "engine": "claude", "producer_status": "ok",
             "resolved_source": "local", "resolved_path": ".claude/personas/quant.md",
             "candidates": [{"candidate_key": "solo", "kind": "hypothesis", "title": "t",
                             "priority": "high", "parent": None}], "reprioritize": []},
            {"persona_id": "quant", "engine": "codex", "producer_status": "ok",
             "resolved_source": "local", "resolved_path": ".claude/personas/quant.md",
             "candidates": [{"candidate_key": "solo", "kind": "hypothesis", "title": "t",
                             "priority": "high", "parent": None}], "reprioritize": []},
        ],
    })
    _write(proj / "outputs" / "synthesis" / "round1.json", {
        "round": 1, "deferred": {"is_deferred": False, "reason": None},
        "decisions": [{"decision_key": "solo", "classification": "experiment", "reason": "r",
                       "title": "t", "priority": "high", "parent": "H-FIX-001",
                       "sources": [
                           {"persona_id": "quant", "engine": "claude", "candidate_key": "solo"},
                           {"persona_id": "quant", "engine": "codex", "candidate_key": "solo"}]}],
    })
    promote.apply_round(proj, 1)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "distinct candidates 1 < K=2" in capsys.readouterr().out


def test_finalize_promise_does_not_satisfy(project_factory, capsys):
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    memo.write_text(memo.read_text() + "\nWe will finalize this next round.\n", encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE  # "finalize" is a promise, not finalization
    assert "not finalized" in capsys.readouterr().out


def test_last_round_requires_finalization(project_factory, capsys):
    proj = _ok_project(project_factory, round_cap=1)
    assert _run(proj) == C.EXIT_INCOMPLETE  # a living memo at the cap is not finalized
    assert "not finalized" in capsys.readouterr().out
    # finalize = flip the header Status to `final` (Verdict + §1 enum are already consistent)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    memo.write_text(
        memo.read_text().replace("**Status:** `living`", "**Status:** `final`"),
        encoding="utf-8",
    )
    assert _run(proj) == C.EXIT_OK


def test_early_close_requires_termination_block_and_finalized_memo(project_factory):
    proj = _ok_project(project_factory, round_cap=3)
    spath = proj / "outputs" / "synthesis" / "round1.json"
    data = _read(spath)
    data["termination_recommendation"] = {
        "recommend": "stop",
        "reason": "no decision-moving work remains",
        "data_blocked": [],
    }
    _write(spath, data)
    # Advisory only: without the human-authorized termination block, round 1 does not need
    # finalization and still closes normally.
    assert _run(proj) == C.EXIT_OK


def test_termination_block_requires_finalized_memo(project_factory, capsys):
    proj = _ok_project(project_factory, round_cap=3)
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text() + (
        "termination:\n"
        "  status: terminated\n"
        "  reason: converged\n"
        "  round: 1\n"
        "  authorized_by: user\n"
    ), encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    out = capsys.readouterr().out
    assert "termination/convergence decision marker" in out
    assert "memo not finalized" in out

    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    memo.write_text(
        memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
        + "\n## 8. Early Termination\nHuman authorized convergence.\n",
        encoding="utf-8",
    )
    assert _run(proj) == C.EXIT_OK


def test_termination_block_round_must_match(project_factory, capsys):
    proj = _ok_project(project_factory, round_cap=3)
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text() + (
        "termination:\n"
        "  status: terminated\n"
        "  reason: converged\n"
        "  round: 2\n"
        "  authorized_by: user\n"
    ), encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "termination round 2 does not match verified round 1" in capsys.readouterr().out


# --------------------------------------------------------------------------- memo finalization (v4)
def _finalize(memo: Path) -> None:
    """Flip the fixture memo's header Status living -> final (Verdict + §1 already consistent)."""
    memo.write_text(memo.read_text().replace("**Status:** `living`", "**Status:** `final`"),
                    encoding="utf-8")


def test_finalize_requires_resolved_verdict(project_factory, capsys):
    # Status:final but a placeholder Verdict (a fresh-template header) -> not finalized.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace(
        "**Verdict:** `weak_support`",
        "**Verdict:** `<supported / weak_support / mixed / not_supported / inconclusive>`",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "not finalized" in capsys.readouterr().out


def test_finalize_section1_missing_verdict(project_factory, capsys):
    # final + resolved Verdict, but §1 states no enum at all -> not finalized.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace(
        "We tested H-FIX-001 and found weak_support; hold as research-only pending more data.",
        "We tested it and recommend holding for now.",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "exactly once" in capsys.readouterr().out


def test_finalize_section1_two_distinct_enums(project_factory, capsys):
    # §1 names two different verdicts -> ambiguous -> not finalized.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace(
        "We tested H-FIX-001 and found weak_support; hold as research-only pending more data.",
        "We found weak_support overall, though one sub-claim was mixed.",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "no other verdict" in capsys.readouterr().out


def test_finalize_section1_duplicate_enum(project_factory, capsys):
    # the header enum appears twice in §1 -> not "exactly once" -> not finalized.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace(
        "We tested H-FIX-001 and found weak_support; hold as research-only pending more data.",
        "We found weak_support; the weak_support holds across regimes.",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "exactly once" in capsys.readouterr().out


def test_finalize_not_supported_is_not_a_supported_hit(project_factory):
    # The atomic longest-first matcher reads 'not supported' as ONE not_supported, not also a
    # bare 'supported' -> a not_supported verdict echoed once in §1 finalizes cleanly.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace("**Verdict:** `weak_support`", "**Verdict:** `not_supported`")
    text = text.replace(
        "We tested H-FIX-001 and found weak_support; hold as research-only pending more data.",
        "We tested H-FIX-001 and the claim was not supported; drop it.",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_OK


def test_finalize_duplicate_status_line(project_factory, capsys):
    # two **Status:** lines -> ambiguous header -> not finalized.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    _finalize(memo)
    memo.write_text(memo.read_text() + "\n**Status:** `final`\n", encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "exactly one '**Status:**' line" in capsys.readouterr().out


def test_memo_timeline_row_needs_round_cell(project_factory, capsys):
    # A dated §4 table WITHOUT a Round column/cell does not satisfy the round-N row requirement.
    proj = _ok_project(project_factory)  # cap 2, round 1 (no finalization needed)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace(
        "| Round | Date | Step | What happened | Artifact |\n"
        "|---|---|---|---|---|\n"
        "| 1 | 2026-06-13 | test | tested H-FIX-001; weak_support | h-fix-001 |",
        "| Date | Step | What happened | Artifact |\n"
        "|---|---|---|---|\n"
        "| 2026-06-13 | test | did things | h-fix-001 |",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "§4 Timeline has no row for round 1" in capsys.readouterr().out


def test_multi_memo_one_stale_fails(project_factory, capsys):
    # A finalized primary memo plus a stale sibling (living + no round-1 row) -> the round fails,
    # and the punchlist names the stale memo (per-memo checks, no cross-memo masking).
    proj = _ok_project(project_factory, round_cap=1)
    _finalize(proj / "hypothesis_tracking" / "memo-fix-decision.md")
    (proj / "hypothesis_tracking" / "memo-fix-secondary.md").write_text(
        "# Decision-Maker Memo — H-FIX-002: stale\n\n"
        "**Status:** `living`\n**Verdict:** `mixed`\n\n"
        "## 1. Executive Summary\n\nmixed.\n\n"
        "## 4. Timeline\n\n"
        "| Round | Date | Step | What happened | Artifact |\n|---|---|---|---|---|\n",
        encoding="utf-8",
    )
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "memo-fix-secondary.md" in capsys.readouterr().out


def test_final_close_prints_memo_and_index_paths(project_factory, capsys):
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    _finalize(memo)
    assert _run(proj) == C.EXIT_OK
    out = capsys.readouterr().out
    assert f"MEMO: {memo.resolve()}" in out
    index = proj / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md"
    assert f"INDEX: {index.resolve()}" in out


def test_termination_close_prints_paths(project_factory, capsys):
    proj = _ok_project(project_factory, round_cap=3)
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text() + (
        "termination:\n  status: terminated\n  reason: converged\n  round: 1\n"
        "  authorized_by: user\n"
    ), encoding="utf-8")
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    memo.write_text(
        memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
        + "\n## 8. Early Termination\nHuman authorized convergence.\n",
        encoding="utf-8",
    )
    assert _run(proj) == C.EXIT_OK
    out = capsys.readouterr().out
    assert f"MEMO: {memo.resolve()}" in out
    assert "INDEX:" in out


def test_below_cap_close_prints_no_paths(project_factory, capsys):
    proj = _ok_project(project_factory, round_cap=2)  # round 1 < cap, no termination
    assert _run(proj) == C.EXIT_OK
    out = capsys.readouterr().out
    assert "MEMO:" not in out
    assert "INDEX:" not in out


# ----------------------------------------------------------- review hardening (codex + red-team)
def test_finalize_rejects_extra_stale_status_line(project_factory, capsys):
    # A clean `Status: final` PLUS a second, prose Status line is still two fields -> not finalized
    # (the field is matched by LABEL, so a stale/contradictory line cannot hide from the count).
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    memo.write_text(
        memo.read_text().replace(
            "**Status:** `living`",
            "**Status:** `final`\n**Status:** living — provisional through round 1",
        ),
        encoding="utf-8",
    )
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "exactly one '**Status:**' line" in capsys.readouterr().out


def test_finalize_rejects_duplicate_verdict_placeholder(project_factory, capsys):
    # A resolved Verdict PLUS a leftover placeholder Verdict line is two fields -> not finalized.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace(
        "**Verdict:** `weak_support`",
        "**Verdict:** `weak_support`\n**Verdict:** `<supported / weak_support / mixed>`",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "exactly one '**Verdict:**' line" in capsys.readouterr().out


def test_finalize_accepts_spaced_verdict_form(project_factory):
    # A space surface form of a multi-word verdict canonicalizes and finalizes (no false-red).
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace("**Verdict:** `weak_support`", "**Verdict:** `weak support`")
    text = text.replace(
        "We tested H-FIX-001 and found weak_support; hold as research-only pending more data.",
        "We tested H-FIX-001 and found weak support; hold as research-only pending more data.",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_OK


def test_finalize_accepts_hyphen_verdict_header(project_factory):
    # A hyphen form ('not-supported') in the header canonicalizes; §1 'not supported' matches.
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace("**Verdict:** `weak_support`", "**Verdict:** `not-supported`")
    text = text.replace(
        "We tested H-FIX-001 and found weak_support; hold as research-only pending more data.",
        "We tested H-FIX-001 and the claim was not supported; drop it.",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_OK


def test_timeline_second_table_does_not_lend_its_rows(project_factory, capsys):
    # A non-timeline table later in §4 must NOT satisfy the round-N row check for the timeline.
    proj = _ok_project(project_factory)  # cap 2, round 1 (no finalization needed)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace(
        "| Round | Date | Step | What happened | Artifact |\n"
        "|---|---|---|---|---|\n"
        "| 1 | 2026-06-13 | test | tested H-FIX-001; weak_support | h-fix-001 |",
        "| Round | Date | Step | What happened | Artifact |\n"
        "|---|---|---|---|---|\n"
        "| 2 | 2026-06-13 | test | round 2 work | h-fix-001 |\n\n"
        "| ID | Note |\n|---|---|\n| 1 | leftover — not a timeline row |",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "§4 Timeline has no row for round 1" in capsys.readouterr().out


def test_timeline_requires_separator_row(project_factory, capsys):
    # A header + data row with no `|---|` separator is not a markdown table -> does not count.
    proj = _ok_project(project_factory)  # cap 2, round 1
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace(
        "| Round | Date | Step | What happened | Artifact |\n"
        "|---|---|---|---|---|\n"
        "| 1 | 2026-06-13 | test | tested H-FIX-001; weak_support | h-fix-001 |",
        "| Round | Date | Step | What happened | Artifact |\n"
        "| 1 | 2026-06-13 | test | no separator above this row | h-fix-001 |",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "§4 Timeline has no row for round 1" in capsys.readouterr().out


def test_timeline_escaped_pipe_does_not_shift_round_column(project_factory):
    # A literal escaped pipe in a cell before the Round column must not shift the column index.
    proj = _ok_project(project_factory)  # cap 2, round 1
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace(
        "| Round | Date | Step | What happened | Artifact |\n"
        "|---|---|---|---|---|\n"
        "| 1 | 2026-06-13 | test | tested H-FIX-001; weak_support | h-fix-001 |",
        "| Pair | Round | Date | Note |\n"
        "|---|---|---|---|\n"
        "| SPY \\| QQQ | 1 | 2026-06-13 | round 1 |",
    )
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_OK


def test_section1_heading_without_dot_is_accepted(project_factory):
    # '## 1 Executive Summary' (no dot) is still §1 for finalization (but '## 10.' is not).
    proj = _ok_project(project_factory, round_cap=1)
    memo = proj / "hypothesis_tracking" / "memo-fix-decision.md"
    text = memo.read_text().replace("**Status:** `living`", "**Status:** `final`")
    text = text.replace("## 1. Executive Summary", "## 1 Executive Summary")
    memo.write_text(text, encoding="utf-8")
    assert _run(proj) == C.EXIT_OK
