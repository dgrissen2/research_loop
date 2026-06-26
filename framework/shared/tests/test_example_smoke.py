"""S10 smoke: the gate operates on the real cor1m worked example without crashing.

The shipped example is a complete, dogfooded run (it carries commentary/proposals/synthesis
+ a promotion ledger), so the gate may exit OK or report incompleteness depending on the
round — either way it must run end-to-end against real artifacts, not raise.
"""

from __future__ import annotations

from pathlib import Path

import contracts as C
import verify_round

REPO = Path(__file__).resolve().parents[3]
EXAMPLE = REPO / "examples" / "cor1m-concentration-hedge"


def test_example_config_and_notes_parse():
    cfg = verify_round.load_config(EXAMPLE)
    assert cfg["prefix"] == "COR"
    assert set(cfg["personas"]) == {"cio", "quant", "portfolio-manager"}
    notes = verify_round.iter_notes(EXAMPLE)
    ids = {fm.get("id") for _p, _t, fm in notes}
    assert {"H-COR-001", "H-COR-002", "H-COR-003"} <= ids


def test_example_round1_active_set():
    notes = verify_round.iter_notes(EXAMPLE)
    active1 = {fm["id"] for _p, _t, fm in verify_round.active_for_round(notes, 1)}
    assert active1 == {"H-COR-001", "H-COR-002", "H-COR-003"}  # round-1 hypotheses
    active2 = {fm["id"] for _p, _t, fm in verify_round.active_for_round(notes, 2)}
    assert active2 == {"H-COR-006", "H-COR-007"}  # promoted into round 2


def test_gate_runs_without_crashing():
    # The example carries full round artifacts; the gate may pass or report incompleteness
    # depending on the round — the invariant under test is that it runs, not that it raises.
    problems = verify_round.verify(EXAMPLE, 1)
    assert isinstance(problems, list)
    # exit code path is reachable and deterministic
    rc = verify_round.main(["--round", "1", "--project", str(EXAMPLE)])
    assert rc in (C.EXIT_INCOMPLETE, C.EXIT_MALFORMED, C.EXIT_OK)
