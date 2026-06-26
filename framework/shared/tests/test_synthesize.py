"""Tests for synthesize.py (S5 / fact: synthesize)."""

from __future__ import annotations

import json

import contracts as C
import synthesize


def _proposals():
    return json.loads((__import__("pathlib").Path(__file__).resolve().parent
                       / "fixtures" / "good_proposals.json").read_text())


def test_synthesize_groups_and_covers():
    proposals = _proposals()
    result = synthesize.synthesize(proposals)
    keys = {d["decision_key"] for d in result["decisions"]}
    # one decision per unique candidate_key
    assert keys == {"qqq-beta-adjust", "oos-validation"}
    by_key = {d["decision_key"]: d for d in result["decisions"]}
    # convergence: qqq-beta-adjust proposed by quant/claude + quant/codex -> 2 sources
    assert len(by_key["qqq-beta-adjust"]["sources"]) == 2
    assert by_key["qqq-beta-adjust"]["classification"] == "experiment"
    assert by_key["oos-validation"]["classification"] == "promote"
    # coverage: every proposal candidate is in some decision's sources
    proposed = {c["candidate_key"] for b in proposals["blocks"] for c in b["candidates"]}
    covered = {s["candidate_key"] for d in result["decisions"] for s in d["sources"]}
    assert proposed <= covered


def test_synthesis_has_termination_recommendation():
    result = synthesize.synthesize(_proposals())
    assert result["termination_recommendation"] == {
        "recommend": "continue",
        "reason": None,
        "data_blocked": [],
    }


def test_synthesize_writes_valid_artifact(project_factory):
    proj = project_factory()
    out = synthesize.run(proj, 1)  # reads the fixture proposals already in the project
    assert out["round"] == 1
    # round-trips through the contract validator
    C.load_synthesis(proj / "outputs" / "synthesis" / "round1.json")
