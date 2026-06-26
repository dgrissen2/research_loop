"""Tests for the template/index migration + fixtures (S2).

Facts: template-migration, example-migration.
"""

from __future__ import annotations

from pathlib import Path

import contracts as C
import pytest

TESTS = Path(__file__).resolve().parent
FRAMEWORK = TESTS.parents[1]
REPO = TESTS.parents[2]
FIXTURES = TESTS / "fixtures"

TEMPLATE = FRAMEWORK / "hypothesis_tracking" / "HYPOTHESIS_FINDINGS_TEMPLATE.md"
INDEX_TEMPLATE = FRAMEWORK / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md"
EXAMPLE_HT = REPO / "examples" / "cor1m-concentration-hedge" / "hypothesis_tracking"


# --------------------------------------------------------------------------- template
def test_findings_template_has_frontmatter():
    fm = C.parse_frontmatter(TEMPLATE.read_text(encoding="utf-8"))
    assert set(C.FRONTMATTER_KEYS).issubset(fm), f"missing frontmatter keys: {fm}"


def test_findings_template_marks_commentary_generated():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "commentary.json" in text  # D6: note carries a generated excerpt/backlink


def test_index_template_has_round_column():
    text = INDEX_TEMPLATE.read_text(encoding="utf-8")
    header = next(ln for ln in text.splitlines() if ln.startswith("| Hypothesis ID"))
    cols = [c.strip() for c in header.strip("|").split("|")]
    assert cols == list(C.INDEX_HYPOTHESES_COLUMNS), cols


# --------------------------------------------------------------------------- migrated example
@pytest.mark.parametrize(
    "name,hid,rnd",
    [
        ("h-cor-001_concentration-validity_2026-06-17.md", "H-COR-001", "1"),
        ("h-cor-002_overbulled-hedge-trigger_2026-06-17.md", "H-COR-002", "1"),
        ("h-cor-003_edge-beyond-vix_2026-06-17.md", "H-COR-003", "1"),
        (
            "h-cor-006_the-qqq-over-bulled-penalty-is-concentration-not_2026-06-17.md",
            "H-COR-006",
            "2",
        ),
        (
            "h-cor-007_the-cor1m-8-effect-generalizes-beyond-the-2024-2_2026-06-17.md",
            "H-COR-007",
            "2",
        ),
    ],
)
def test_example_notes_have_valid_frontmatter(name, hid, rnd):
    fm = C.parse_frontmatter((EXAMPLE_HT / name).read_text(encoding="utf-8"))
    assert fm["id"] == hid
    assert fm["round"] == rnd
    assert fm["hypothesis_status"] in C.HYPOTHESIS_STATUS
    assert fm["phase"] in C.PHASES


def test_example_index_has_round_column():
    text = (EXAMPLE_HT / "RESEARCH_HYPOTHESIS_INDEX.md").read_text(encoding="utf-8")
    header = next(ln for ln in text.splitlines() if ln.startswith("| Hypothesis ID"))
    cols = [c.strip() for c in header.strip("|").split("|")]
    assert cols == list(C.INDEX_HYPOTHESES_COLUMNS), cols


# --------------------------------------------------------------------------- fixtures load
def test_fixtures_validate():
    assert C.load_commentary(FIXTURES / "good_commentary.json")["hypothesis_id"] == "H-FIX-001"
    proposals = C.load_proposals(FIXTURES / "good_proposals.json")
    assert {(b["persona_id"], b["engine"]) for b in proposals["blocks"]} == {
        ("quant", "claude"), ("quant", "codex"), ("cio", "claude"), ("cio", "codex"),
    }
    assert len(C.load_synthesis(FIXTURES / "good_synthesis.json")["decisions"]) == 2
