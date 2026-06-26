"""Functional tests for the native-subagent Claude leg.

Step 2 — the `prompts` scaffold (frozen prompts + provenance + run_id, oversize guard).
Step 3 — the `assemble` executor, the fail-closed claude_leg contract, run-id freshness,
identity validation, required-leg (R1) semantics, and twin-health-once-per-persona.
"""

from __future__ import annotations

import json
from pathlib import Path

import contracts as C
import emit
import pytest


def _scaffold(proj: Path, phase: str, rnd: int = 1) -> dict:
    path = proj / "outputs" / ".claude_legs" / f"{phase}_round{rnd}.json"
    return json.loads(path.read_text(encoding="utf-8"))


# ------------------------------------------------------------------- Step 2: prompts scaffold
def test_prompts_commentary_writes_scaffold(project_factory):
    proj = project_factory(personas=("quant", "cio"))
    rc = emit.main(["prompts", "commentary", "--round", "1", "--project", str(proj)])
    assert rc == 0
    sc = _scaffold(proj, "commentary")
    assert sc["round"] == 1 and sc["phase"] == "commentary"
    assert isinstance(sc["run_id"], str) and sc["run_id"]
    # one persona entry each, full provenance + a frozen prompt
    assert [p["persona_id"] for p in sc["personas"]] == ["quant", "cio"]
    for p in sc["personas"]:
        assert p["resolved_source"] == "local"
        assert p["resolved_path"].endswith(f"{p['persona_id']}.md")
        assert p["prompt"]
    # inputs.hyps covers every active hid
    assert [h[0] for h in sc["inputs"]["hyps"]] == ["H-FIX-001"]


def test_prompts_seed_and_proposals_omit_hyps(project_factory):
    proj = project_factory(personas=("quant",))
    for phase in ("seed", "proposals"):
        rc = emit.main(["prompts", phase, "--round", "1", "--project", str(proj),
                        "--context", "ctx"])
        assert rc == 0
        sc = _scaffold(proj, phase)
        assert sc["phase"] == phase
        assert "inputs" not in sc
        assert len(sc["personas"]) == 1 and sc["personas"][0]["prompt"]


def test_prompts_commentary_oversize_fails_closed(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    monkeypatch.setenv("EMIT_BATCH_MAX_CHARS", "1")
    rc = emit.main(["prompts", "commentary", "--round", "1", "--project", str(proj)])
    assert rc == 1  # ContractError mapped to exit 1
    assert not (proj / "outputs" / ".claude_legs" / "commentary_round1.json").exists()


def test_prompts_requires_phase(project_factory):
    proj = project_factory(personas=("quant",))
    rc = emit.main(["prompts", "--round", "1", "--project", str(proj)])
    assert rc == 1


# ------------------------------------------------------------------- Step 3: assemble + flag
def _set_leg(proj: Path, leg: str) -> None:
    yml = proj / "hypothesis_tracking" / "research_loop.yml"
    yml.write_text(yml.read_text(encoding="utf-8") + f"claude_leg: {leg}\n", encoding="utf-8")


def _make_scaffold(proj: Path, phase: str, personas, hyps=None) -> dict:
    sc = {
        "run_id": "rid", "round": 1, "phase": phase,
        "personas": [{"persona_id": pid, "resolved_source": "local",
                      "resolved_path": str(proj / ".claude" / "personas" / f"{pid}.md"),
                      "prompt": "frozen"} for pid in personas],
    }
    if hyps is not None:
        sc["inputs"] = {"hyps": hyps}
    return sc


def _ok_batch(engine, pid, ppath, hyps, timeout, prompt=None):
    return {"producer_status": "ok",
            "by_hid": {h: {"interpret": "ti", "act": "ta"} for h, _ in hyps}}


def _ok_proposals(*a, **k):
    return {"producer_status": "ok", "candidates": [], "reprioritize": []}


def _ctext(*hids: str) -> str:
    """A handed-off Claude commentary record (by-hid JSON) covering `hids`."""
    return json.dumps({h: {"interpret": "i", "act": "a"} for h in hids})


# --- fact-3: assemble fires ONLY codex, never claude ---
def test_assemble_fires_only_codex(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    seen = []
    monkeypatch.setattr(emit, "invoke_persona_batch",
                        lambda engine, *a, **k: seen.append(engine) or _ok_batch(engine, *a, **k))
    monkeypatch.setattr(emit, "invoke_persona",
                        lambda engine, *a, **k: seen.append(engine) or {"producer_status": "ok"})
    sc = _make_scaffold(proj, "commentary", ("quant",), hyps=[["H1", "c"]])
    emit.assemble_commentary(proj, sc, {"quant": _ctext("H1")}, emit._load_cfg(proj), 5)
    assert seen and all(e == "codex" for e in seen)


# --- fact-10: required Claude leg fails the round ---
@pytest.mark.parametrize("text", [None, "", "   "])
def test_assemble_seed_missing_record_fails(project_factory, monkeypatch, text):
    proj = project_factory(personas=("quant",))
    monkeypatch.setattr(emit, "invoke_persona",
                        lambda *a, **k: {"producer_status": "ok", "interpret": "ti", "act": "ta"})
    with pytest.raises(C.ContractError):
        emit.assemble_seed(proj, _make_scaffold(proj, "seed", ("quant",)),
                           {"quant": text}, emit._load_cfg(proj), 5)


def test_assemble_commentary_missing_hid_fails(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    monkeypatch.setattr(emit, "invoke_persona_batch", _ok_batch)
    sc = _make_scaffold(proj, "commentary", ("quant",), hyps=[["H1", "c"], ["H2", "c"]])
    # the handed-off record covers only H1 -> H2 missing -> required leg fails
    with pytest.raises(C.ContractError):
        emit.assemble_commentary(proj, sc, {"quant": _ctext("H1")}, emit._load_cfg(proj), 5)


def test_assemble_proposals_empty_candidates_ok(project_factory, monkeypatch):
    # proposals is STATUS-ONLY: an ok record with empty candidates SUCCEEDS (preserved behavior).
    proj = project_factory(personas=("quant",))
    monkeypatch.setattr(emit, "invoke_persona", _ok_proposals)
    out = emit.assemble_proposals(proj, _make_scaffold(proj, "proposals", ("quant",)),
                                  {"quant": json.dumps({"candidates": [], "reprioritize": []})},
                                  emit._load_cfg(proj), 5)
    assert any(b["engine"] == "claude" and b["candidates"] == []
               for b in C.load_proposals(out)["blocks"])


def test_assemble_proposals_unparseable_record_fails(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    monkeypatch.setattr(emit, "invoke_persona", _ok_proposals)
    with pytest.raises(C.ContractError):
        emit.assemble_proposals(proj, _make_scaffold(proj, "proposals", ("quant",)),
                                {"quant": "not json at all"}, emit._load_cfg(proj), 5)


# --- fact-11: identity validation ---
def test_validate_scaffold_rejects_mismatches(project_factory):
    proj = project_factory(personas=("quant", "cio"))
    cfg = emit._load_cfg(proj)
    good = _make_scaffold(proj, "seed", ("quant", "cio"))
    emit._validate_scaffold(good, "seed", 1, cfg)  # baseline: passes
    for bad, phase, rnd in [
        ("not-a-dict", "seed", 1),                            # torn / non-object
        ({**good, "round": 2}, "seed", 1),                    # wrong round
        (good, "commentary", 1),                              # wrong phase
        (_make_scaffold(proj, "seed", ("cio", "quant")), "seed", 1),   # order mismatch
        (_make_scaffold(proj, "seed", ("quant",)), "seed", 1),         # set mismatch
        ({**good, "personas": ["not-a-dict"]}, "seed", 1),             # malformed persona entry
        (_make_scaffold(proj, "commentary", ("quant", "cio"), hyps=[["H1"]]),
         "commentary", 1),                                            # malformed hyp (not a pair)
    ]:
        with pytest.raises(C.ContractError):
            emit._validate_scaffold(bad, phase, rnd, cfg)


# --- fact-1: fail-closed claude_leg contract ---
def test_fail_closed_producer_under_subagent(project_factory):
    proj = project_factory(personas=("quant",))
    _set_leg(proj, "subagent")
    assert emit.main(["commentary", "--round", "1", "--project", str(proj)]) == 1


def test_fail_closed_assemble_under_subprocess(project_factory):
    proj = project_factory(personas=("quant",))  # default leg = subprocess
    assert emit.main(["assemble", "seed", "--round", "1", "--project", str(proj)]) == 1


# --- fact-14: twin-health bumps ONCE per persona, not per hid ---
def test_assemble_commentary_twin_health_once_per_persona(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    monkeypatch.setattr(emit, "invoke_persona_batch",
                        lambda *a, **k: {"producer_status": "unavailable", "by_hid": {}})
    sc = _make_scaffold(proj, "commentary", ("quant",),
                        hyps=[["H1", "c"], ["H2", "c"], ["H3", "c"]])
    texts = {"quant": json.dumps({h: {"interpret": "i", "act": "a"} for h in ("H1", "H2", "H3")})}
    emit.assemble_commentary(proj, sc, texts, emit._load_cfg(proj), 5)
    health = json.loads((proj / "outputs" / "twin_health.json").read_text(encoding="utf-8"))
    assert health["failed_instances"] == 1  # one persona -> one bump, not 3 (per hid)


# --- fact-11: run-id freshness + full CLI flow ---
def test_assemble_full_cli_flow(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    _set_leg(proj, "subagent")
    monkeypatch.setattr(emit, "invoke_persona_batch", _ok_batch)
    assert emit.main(["prompts", "commentary", "--round", "1", "--project", str(proj)]) == 0
    sc = _scaffold(proj, "commentary")
    rdir = proj / "outputs" / ".claude_legs" / f"commentary_round1.{sc['run_id']}"
    rdir.mkdir(parents=True)
    (rdir / "quant.txt").write_text(
        json.dumps({"H-FIX-001": {"interpret": "ci", "act": "ca"}}), encoding="utf-8")
    assert emit.main(["assemble", "commentary", "--round", "1", "--project", str(proj)]) == 0
    data = C.load_commentary(proj / "outputs" / "commentary" / "round1" / "H-FIX-001.json")
    assert data["personas"][0]["claude"]["interpret"] == "ci"


def test_assemble_stale_run_id_record_ignored(project_factory, monkeypatch):
    # A record under a PRIOR run_id dir does NOT satisfy the current run's required leg.
    proj = project_factory(personas=("quant",))
    _set_leg(proj, "subagent")
    monkeypatch.setattr(emit, "invoke_persona_batch", _ok_batch)
    assert emit.main(["prompts", "commentary", "--round", "1", "--project", str(proj)]) == 0
    legs = proj / "outputs" / ".claude_legs"
    stale = legs / "commentary_round1.STALE-run"
    stale.mkdir(parents=True)
    (stale / "quant.txt").write_text(
        json.dumps({"H-FIX-001": {"interpret": "i", "act": "a"}}), encoding="utf-8")
    # assemble reads ONLY the scaffold's run_id dir -> the current record is missing -> fails
    assert emit.main(["assemble", "commentary", "--round", "1", "--project", str(proj)]) == 1


def test_assemble_torn_scaffold_fails(project_factory):
    proj = project_factory(personas=("quant",))
    _set_leg(proj, "subagent")
    legs = proj / "outputs" / ".claude_legs"
    legs.mkdir(parents=True)
    (legs / "seed_round1.json").write_text("{ this is torn", encoding="utf-8")
    assert emit.main(["assemble", "seed", "--round", "1", "--project", str(proj)]) == 1


# --- proposals dedup: the panel is shown the already-tracked backlog (no dupes) ---
def test_existing_items_block_fails_open(project_factory):
    proj = project_factory(personas=("quant",))
    idx = proj / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md"
    idx.write_bytes(b"\xff\xfe not valid utf-8 \x80\x81")  # corrupt / non-UTF-8 must not crash
    assert emit._existing_items_block(proj) == ""
    idx.unlink()  # missing index must not crash either
    assert emit._existing_items_block(proj) == ""


def test_proposals_prompt_lists_already_tracked(project_factory):
    proj = project_factory(personas=("quant",))
    (proj / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md").write_text(
        "# Index\n\n## Hypotheses\n"
        "| Hypothesis ID | Claim | Status |\n|---|---|---|\n"
        "| H-FIX-009 | demo concentration claim | weak_support |\n\n"
        "## Follow-Up Experiments\n"
        "| Experiment ID | Proposed Experiment | Why Run It | Scope | Parent Hypothesis "
        "| Source Note | Priority | Status |\n|---|---|---|---|---|---|---|---|\n"
        "| E-FIX-009 | demo oos tracker | x | - | H-FIX-009 | synthesis | high | planned |\n",
        encoding="utf-8",
    )
    block = emit._existing_items_block(proj)
    assert "ALREADY TRACKED" in block
    assert "H-FIX-009" in block and "E-FIX-009" in block
    # the frozen proposals prompt (subagent leg) carries it; round context stays intact
    sc = emit._build_scaffold("proposals", proj, 2, "the round findings", emit._load_cfg(proj))
    prompt = sc["personas"][0]["prompt"]
    assert "ALREADY TRACKED" in prompt
    assert "H-FIX-009" in prompt and "the round findings" in prompt
