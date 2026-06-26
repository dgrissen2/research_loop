"""Byte-identity goldens (Step 1) + assemble↔build parity (Step 3) for the subagent leg.

The goldens pin the EXACT bytes each subprocess builder emits for a fixed (claude, twin) input,
with `resolved_path` normalized to ``<PROJ>`` for portability. Step 1 asserts the refactored
builder reproduces the pre-refactor bytes; Step 3 asserts ``assemble_<phase>`` reproduces the
SAME bytes from a handed-off Claude record — the byte-identity guarantee (facts 5/6/8).

Regenerate ONLY after an intentional artifact-shape change::

    RL_REGEN_GOLDENS=1 ~/Dev/virtualenvs/research_loop/bin/python3 \
        -m pytest framework/shared/tests/test_subagent_parity.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import emit

GOLDENS = Path(__file__).resolve().parent / "fixtures" / "goldens"
PERSONAS = ("quant", "cio")
HID = "H-COR-001"

# Canonical Claude leg per phase: the build stub returns this, and (Step 3) the assemble handoff
# text decodes to exactly this — so both paths are byte-compared on identical Claude inputs.
SEED_CLAUDE = {"interpret": "seed read paragraph", "act": "expanded hypothesis list paragraph"}
COMMENTARY_CLAUDE = {"interpret": "interpret paragraph", "act": "act paragraph"}
PROPOSALS_CLAUDE = {
    "candidates": [{"candidate_key": "k", "kind": "hypothesis",
                    "title": "a title", "priority": "high", "parent": None}],
    "reprioritize": [],
}
# Canonical Codex twin (same per-phase shape).
TWIN_TWO_PARA = {"interpret": "twin interpret", "act": "twin act"}


def _norm(path: Path, proj: Path) -> str:
    """Read the artifact text with the volatile project path folded to <PROJ>."""
    return path.read_text(encoding="utf-8").replace(str(proj), "<PROJ>")


def _check_or_regen(name: str, actual: str) -> None:
    GOLDENS.mkdir(parents=True, exist_ok=True)
    golden = GOLDENS / name
    if os.environ.get("RL_REGEN_GOLDENS"):
        golden.write_text(actual, encoding="utf-8")
        return
    assert golden.is_file(), f"missing golden {golden}; regenerate with RL_REGEN_GOLDENS=1"
    assert actual == golden.read_text(encoding="utf-8"), f"{name} drifted from its golden"


# --------------------------------------------------------------------------- build runners (Step 1)
def build_seed(proj: Path, monkeypatch) -> Path:
    def stub(engine, pid, ppath, context, mode, timeout, prompt=None):
        leg = SEED_CLAUDE if engine == "claude" else TWIN_TWO_PARA
        return {"producer_status": "ok", **leg}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    return emit.build_seed_expansion(proj, 1, "seed ctx", emit._load_cfg(proj), 5)


def build_commentary(proj: Path, monkeypatch) -> Path:
    def stub(engine, pid, ppath, hyps, timeout, prompt=None):
        leg = COMMENTARY_CLAUDE if engine == "claude" else TWIN_TWO_PARA
        return {"producer_status": "ok", "by_hid": {h: dict(leg) for h, _ in hyps}}

    monkeypatch.setattr(emit, "invoke_persona_batch", stub)
    return emit.build_commentary_batch(proj, 1, [(HID, "ctx")], emit._load_cfg(proj), 5)[0]


def build_proposals(proj: Path, monkeypatch) -> Path:
    def stub(engine, pid, ppath, context, mode, timeout, prompt=None):
        cands = [{**c, "candidate_key": f"{pid}-{engine}-{c['candidate_key']}"}
                 for c in PROPOSALS_CLAUDE["candidates"]]
        return {"producer_status": "ok", "candidates": cands,
                "reprioritize": list(PROPOSALS_CLAUDE["reprioritize"])}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    return emit.build_proposals(proj, 1, "ctx", emit._load_cfg(proj), 5)


def test_seed_byte_golden(project_factory, monkeypatch):
    proj = project_factory(personas=PERSONAS, with_seed=False)
    _check_or_regen("seed.json", _norm(build_seed(proj, monkeypatch), proj))


def test_commentary_byte_golden(project_factory, monkeypatch):
    proj = project_factory(personas=PERSONAS)
    _check_or_regen("commentary.json", _norm(build_commentary(proj, monkeypatch), proj))


def test_proposals_byte_golden(project_factory, monkeypatch):
    proj = project_factory(personas=PERSONAS)
    _check_or_regen("proposals.json", _norm(build_proposals(proj, monkeypatch), proj))


# ----------------------------------------------------------- assemble↔golden parity (Step 3)
def _scaffold(proj: Path, phase: str, hyps=None) -> dict:
    """A scaffold matching the build helpers' inputs (hyps + resolved_path), for byte parity."""
    sc = {
        "run_id": "test-run", "round": 1, "phase": phase,
        "personas": [{"persona_id": pid, "resolved_source": "local",
                      "resolved_path": str(proj / ".claude" / "personas" / f"{pid}.md"),
                      "prompt": "frozen prompt"} for pid in PERSONAS],
    }
    if hyps is not None:
        sc["inputs"] = {"hyps": hyps}
    return sc


def asm_seed(proj: Path, monkeypatch) -> Path:
    # the handed-off Claude text decodes (via _split_two) to exactly SEED_CLAUDE
    monkeypatch.setattr(emit, "invoke_persona",
                        lambda *a, **k: {"producer_status": "ok", **TWIN_TWO_PARA})
    texts = {pid: f"{SEED_CLAUDE['interpret']}\n\n{SEED_CLAUDE['act']}" for pid in PERSONAS}
    return emit.assemble_seed(proj, _scaffold(proj, "seed"), texts, emit._load_cfg(proj), 5)


def asm_commentary(proj: Path, monkeypatch) -> Path:
    monkeypatch.setattr(
        emit, "invoke_persona_batch",
        lambda engine, pid, ppath, hyps, timeout, prompt=None: {
            "producer_status": "ok", "by_hid": {h: dict(TWIN_TWO_PARA) for h, _ in hyps}})
    texts = {pid: json.dumps({HID: COMMENTARY_CLAUDE}) for pid in PERSONAS}
    sc = _scaffold(proj, "commentary", hyps=[[HID, "ctx"]])
    return emit.assemble_commentary(proj, sc, texts, emit._load_cfg(proj), 5)[0]


def asm_proposals(proj: Path, monkeypatch) -> Path:
    monkeypatch.setattr(
        emit, "invoke_persona",
        lambda *a, **k: {"producer_status": "ok", "reprioritize": [],
                         "candidates": [{**c, "candidate_key": f"{a[1]}-codex-{c['candidate_key']}"}
                                        for c in PROPOSALS_CLAUDE["candidates"]]})
    texts = {pid: json.dumps(
        {"candidates": [{**c, "candidate_key": f"{pid}-claude-{c['candidate_key']}"}
                        for c in PROPOSALS_CLAUDE["candidates"]], "reprioritize": []})
        for pid in PERSONAS}
    return emit.assemble_proposals(proj, _scaffold(proj, "proposals"), texts,
                                   emit._load_cfg(proj), 5)


def test_assemble_seed_byte_parity(project_factory, monkeypatch):
    # fact-6/8: assemble reproduces build's exact bytes (proven == the committed golden).
    proj = project_factory(personas=PERSONAS, with_seed=False)
    assert _norm(asm_seed(proj, monkeypatch), proj) == (GOLDENS / "seed.json").read_text("utf-8")


def test_assemble_commentary_byte_parity(project_factory, monkeypatch):
    proj = project_factory(personas=PERSONAS)
    assert _norm(asm_commentary(proj, monkeypatch), proj) == \
        (GOLDENS / "commentary.json").read_text("utf-8")


def test_assemble_proposals_byte_parity(project_factory, monkeypatch):
    proj = project_factory(personas=PERSONAS)
    assert _norm(asm_proposals(proj, monkeypatch), proj) == \
        (GOLDENS / "proposals.json").read_text("utf-8")
