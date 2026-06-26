"""Tests for the contracts layer (S1 / facts: contracts-core, contracts-grammar)."""

from __future__ import annotations

import json
from pathlib import Path

import contracts as C
import pytest


# --------------------------------------------------------------------------- helpers
def _write(tmp_path: Path, name: str, obj) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(obj) if not isinstance(obj, str) else obj, encoding="utf-8")
    return p


def _good_commentary() -> dict:
    return {
        "round": 1,
        "hypothesis_id": "H-COR-001",
        "personas": [
            {
                "persona_id": "quant",
                "claude": {"interpret": "x", "act": "y"},
                "agreement": "agree",
                "resolved_source": "local",
                "resolved_path": ".claude/personas/quant.md",
                "twin": {"engine": "codex", "producer_status": "ok"},
            }
        ],
    }


def _good_proposals() -> dict:
    return {
        "round": 1,
        "blocks": [
            {
                "persona_id": "quant",
                "engine": "claude",
                "producer_status": "ok",
                "resolved_source": "local",
                "resolved_path": ".claude/personas/quant.md",
                "candidates": [
                    {"candidate_key": "k1", "kind": "hypothesis", "title": "t",
                     "priority": "high", "parent": None},
                ],
                "reprioritize": [{"id": "H-COR-002", "action": "deprioritize", "why": "w"}],
            }
        ],
    }


def _good_synthesis() -> dict:
    return {
        "round": 1,
        "deferred": {"is_deferred": False, "reason": None},
        "decisions": [
            {
                "decision_key": "k1",
                "classification": "promote",
                "reason": "r",
                "title": "t",
                "priority": "high",
                "sources": [{"persona_id": "quant", "engine": "claude", "candidate_key": "k1"}],
            }
        ],
    }


# --------------------------------------------------------------------------- happy path
def test_loads_good_artifacts(tmp_path):
    assert C.load_commentary(_write(tmp_path, "c.json", _good_commentary()))["round"] == 1
    assert C.load_proposals(_write(tmp_path, "p.json", _good_proposals()))["round"] == 1
    assert C.load_synthesis(_write(tmp_path, "s.json", _good_synthesis()))["round"] == 1


# --------------------------------------------------------------------------- malformed (exit 3)
def test_empty_file_is_malformed(tmp_path):
    with pytest.raises(C.MalformedArtifact):
        C.load_proposals(_write(tmp_path, "p.json", "   "))


def test_invalid_json_is_malformed(tmp_path):
    with pytest.raises(C.MalformedArtifact):
        C.load_synthesis(_write(tmp_path, "s.json", "{not json"))


def test_missing_required_field_is_field_keyed(tmp_path):
    bad = _good_commentary()
    del bad["personas"][0]["agreement"]
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_commentary(_write(tmp_path, "c.json", bad))
    assert "agreement" in str(e.value)


def test_bad_enum_is_malformed(tmp_path):
    bad = _good_proposals()
    bad["blocks"][0]["engine"] = "mistral"
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_proposals(_write(tmp_path, "p.json", bad))
    assert "engine" in str(e.value)


def test_bad_priority_is_malformed(tmp_path):
    bad = _good_proposals()
    bad["blocks"][0]["candidates"][0]["priority"] = "urgent"
    with pytest.raises(C.MalformedArtifact):
        C.load_proposals(_write(tmp_path, "p.json", bad))


def test_experiment_candidate_requires_parent(tmp_path):
    bad = _good_proposals()
    bad["blocks"][0]["candidates"][0] = {
        "candidate_key": "k2", "kind": "experiment", "title": "t",
        "priority": "low", "parent": None,
    }
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_proposals(_write(tmp_path, "p.json", bad))
    assert "parent" in str(e.value)


# --------------------------------------------------------------------------- uniqueness
def test_duplicate_candidate_key_within_block(tmp_path):
    bad = _good_proposals()
    bad["blocks"][0]["candidates"].append(
        {"candidate_key": "k1", "kind": "hypothesis", "title": "t2",
         "priority": "low", "parent": None}
    )
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_proposals(_write(tmp_path, "p.json", bad))
    assert "duplicate" in str(e.value)


def test_duplicate_decision_key_within_round(tmp_path):
    bad = _good_synthesis()
    dup = dict(bad["decisions"][0])
    bad["decisions"].append(dup)
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_synthesis(_write(tmp_path, "s.json", bad))
    assert "duplicate" in str(e.value)


# --------------------------------------------------------------------------- deferred rule
def test_deferred_without_reason_is_malformed(tmp_path):
    bad = _good_synthesis()
    bad["deferred"] = {"is_deferred": True, "reason": None}
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_synthesis(_write(tmp_path, "s.json", bad))
    assert "reason" in str(e.value)


def test_empty_promote_independent_of_deferred(tmp_path):
    """A non-deferred round with no promote decisions is structurally valid (D3/PR-2)."""
    ok = _good_synthesis()
    ok["decisions"][0]["classification"] = "drop"
    ok["decisions"][0].pop("title", None)
    ok["decisions"][0].pop("priority", None)
    assert C.load_synthesis(_write(tmp_path, "s.json", ok))["round"] == 1


# --------------------------------------------------------------------------- grammar + enums
def test_grammar_constants_present():
    assert "Status" in C.INDEX_HYPOTHESES_COLUMNS and "Round" in C.INDEX_HYPOTHESES_COLUMNS
    assert C.FRONTMATTER_KEYS == ("id", "round", "hypothesis_status", "phase")
    assert "Persona Commentary" in C.NOTE_REQUIRED_SECTIONS
    assert set(C.ACTION_EDIT) == C.ACTIONS == {"deprioritize", "drop"}
    assert "global" in C.PERSONA_SOURCE and "local" in C.PERSONA_SOURCE


def test_frontmatter_roundtrip():
    block = C.format_frontmatter(
        {"id": "H-COR-004", "round": 2, "hypothesis_status": "active", "phase": "method"}
    )
    parsed = C.parse_frontmatter(block + "\n# body\n")
    assert parsed["id"] == "H-COR-004"
    assert parsed["hypothesis_status"] == "active"
    assert parsed["round"] == "2"


def test_stable_id_and_parse():
    assert C.stable_id("H", "cor", 4) == "H-COR-004"
    assert C.parse_id("H-COR-004") == {"kind": "H", "prefix": "COR", "num": 4}
    assert C.parse_id("not-an-id") is None


def test_index_row_pipe_in_cell_roundtrips():
    # A cell containing a literal '|' must not shift later columns (Status/Round).
    header = "| " + " | ".join(C.INDEX_HYPOTHESES_COLUMNS) + " |"
    sep = "|" + "|".join("---" for _ in C.INDEX_HYPOTHESES_COLUMNS) + "|"
    md = "## Hypotheses\n\n" + header + "\n" + sep + "\n| | | | | | | | | | | | |\n"
    md2 = C.append_index_row(md, "hypotheses", {
        "Hypothesis ID": "H-COR-001", "Claim": "SPY | QQQ divergence",
        "Status": "active", "Round": "3", "Next Step": "go",
    })
    _, rows = C.read_index_table(md2, "hypotheses")
    row = next(r for r in rows if r["Hypothesis ID"] == "H-COR-001")
    assert row["Claim"] == "SPY | QQQ divergence"  # pipe preserved, not split
    assert row["Status"] == "active" and row["Round"] == "3"  # columns not shifted


def test_link_targets():
    md = "see [the note](hypothesis_tracking/h-cor-001.md) and [code](scripts/a.py)"
    assert C.link_targets(md) == ["hypothesis_tracking/h-cor-001.md", "scripts/a.py"]


# ----------------------------------------------------------------------- termination schema (S1)
def _term(**over):
    base = {"status": "terminated", "reason": "x", "round": 1, "authorized_by": "u"}
    base.update(over)
    return base


def test_termination_enums_present():
    assert C.TERMINATION_RECOMMEND == {"continue", "converge", "stop"}
    assert C.TERMINATION_STATUS == {"active", "terminated"}


def test_synthesis_termination_recommendation_optional(tmp_path):
    """Pre-existing synthesis with no recommendation still loads (optional field)."""
    s = _good_synthesis()
    assert "termination_recommendation" not in s
    assert C.load_synthesis(_write(tmp_path, "s.json", s))["round"] == 1


def test_synthesis_termination_recommendation_valid(tmp_path):
    s = _good_synthesis()
    s["termination_recommendation"] = {
        "recommend": "converge",
        "reason": "no new hypotheses for two rounds",
        "data_blocked": ["E-COR-008", "E-COR-009"],
    }
    out = C.load_synthesis(_write(tmp_path, "s.json", s))
    assert out["termination_recommendation"]["recommend"] == "converge"


def test_synthesis_termination_recommendation_bad_enum(tmp_path):
    s = _good_synthesis()
    s["termination_recommendation"] = {"recommend": "halt", "reason": None, "data_blocked": []}
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_synthesis(_write(tmp_path, "s.json", s))
    assert "recommend" in str(e.value)


def test_synthesis_termination_recommendation_bad_data_blocked(tmp_path):
    s = _good_synthesis()
    s["termination_recommendation"] = {"recommend": "stop", "reason": "x", "data_blocked": [123]}
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_synthesis(_write(tmp_path, "s.json", s))
    assert "data_blocked" in str(e.value)


def test_load_termination_none_returns_none():
    assert C.load_termination(None) is None


def test_load_termination_valid_coerces_round():
    # Values arrive from the YAML reader as strings; round normalizes to int.
    out = C.load_termination(_term(reason="converged", round="2", authorized_by="user"))
    assert out == {"status": "terminated", "reason": "converged", "round": 2,
                   "authorized_by": "user"}


def test_load_termination_bad_status():
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_termination(_term(status="closed"))
    assert "status" in str(e.value)


def test_load_termination_missing_round():
    block = _term()
    del block["round"]
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_termination(block)
    assert "round" in str(e.value)


def test_load_termination_requires_nonempty_reason():
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_termination(_term(reason="  "))
    assert "reason" in str(e.value)


def test_load_termination_non_numeric_round():
    with pytest.raises(C.MalformedArtifact) as e:
        C.load_termination(_term(round="two"))
    assert "round" in str(e.value)
