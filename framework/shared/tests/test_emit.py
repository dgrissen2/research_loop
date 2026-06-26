"""Tests for emit.py orchestration (S5 / facts: emit-commentary, emit-proposals).

The model seam invoke_persona is monkeypatched so we exercise isolation, cardinality,
and contract validation without real model calls.
"""

from __future__ import annotations

import json

import contracts as C
import emit
import pytest


def test_commentary_one_block_per_persona_and_isolated(project_factory, monkeypatch):
    proj = project_factory(personas=("quant", "cio"))
    calls = []

    def stub(engine, persona_id, persona_path, context, mode, timeout):
        calls.append((engine, persona_id, str(persona_path)))
        if engine == "claude":
            return {"producer_status": "ok", "interpret": "i", "act": "a"}
        return {"producer_status": "ok", "interpret": "ti", "act": "ta"}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    out = emit.build_commentary(proj, 1, "H-FIX-001", "finding ctx",
                                emit._load_cfg(proj), timeout=5)
    data = C.load_commentary(out)
    assert {b["persona_id"] for b in data["personas"]} == {"quant", "cio"}
    # codex enabled -> each persona invoked once for claude AND once for codex (isolated)
    assert sorted(calls) == sorted([
        ("claude", "quant", str(proj / ".claude/personas/quant.md")),
        ("codex", "quant", str(proj / ".claude/personas/quant.md")),
        ("claude", "cio", str(proj / ".claude/personas/cio.md")),
        ("codex", "cio", str(proj / ".claude/personas/cio.md")),
    ])
    # each call saw exactly one persona path (no shared/anchoring context)
    assert all(p.endswith(f"{pid}.md") for _e, pid, p in calls)


def test_commentary_twin_timeout_marks_twin_absent(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))

    def stub(engine, *a, **k):
        if engine == "claude":
            return {"producer_status": "ok", "interpret": "i", "act": "a"}
        return {"producer_status": "timeout", "interpret": None, "act": None}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    out = emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)
    data = C.load_commentary(out)
    block = data["personas"][0]
    assert block["twin"]["producer_status"] == "timeout"
    assert block["agreement"] == "twin_absent"


def test_proposals_cardinality_and_uniqueness(project_factory, monkeypatch):
    proj = project_factory(personas=("quant", "cio"))

    def stub(engine, persona_id, persona_path, context, mode, timeout):
        # emit a duplicate candidate_key to prove per-block dedupe before validation
        return {
            "producer_status": "ok",
            "candidates": [
                {"candidate_key": f"{persona_id}-{engine}-k", "kind": "hypothesis",
                 "title": "t", "priority": "high", "parent": None},
                {"candidate_key": f"{persona_id}-{engine}-k", "kind": "hypothesis",
                 "title": "dup", "priority": "low", "parent": None},
            ],
            "reprioritize": [],
        }

    monkeypatch.setattr(emit, "invoke_persona", stub)
    out = emit.build_proposals(proj, 1, "round ctx", emit._load_cfg(proj), 5)
    data = C.load_proposals(out)
    # 2 personas x 2 engines (claude + codex) = 4 blocks
    assert len(data["blocks"]) == 4
    engines = {(b["persona_id"], b["engine"]) for b in data["blocks"]}
    assert engines == {("quant", "claude"), ("quant", "codex"),
                       ("cio", "claude"), ("cio", "codex")}
    # duplicate candidate_key deduped within each block
    assert all(len(b["candidates"]) == 1 for b in data["blocks"])


def test_proposals_claude_only_when_no_codex(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    # disable codex in config
    cfg = emit._load_cfg(proj)
    cfg["codex"] = False
    monkeypatch.setattr(
        emit, "invoke_persona",
        lambda *a, **k: {"producer_status": "ok", "candidates": [], "reprioritize": []},
    )
    out = emit.build_proposals(proj, 1, "ctx", cfg, 5)
    data = C.load_proposals(out)
    assert {b["engine"] for b in data["blocks"]} == {"claude"}


# ------------------------------------------------------------------- producer reliability (S3)
def _claude_ok():
    return {"producer_status": "ok", "interpret": "i", "act": "a"}


def test_twin_retries_once(project_factory, monkeypatch):
    # A non-ok twin is retried exactly once (2 attempts total); Claude is never retried (3a).
    proj = project_factory(personas=("quant",))
    calls: list[str] = []

    def stub(engine, *a, **k):
        calls.append(engine)
        if engine == "claude":
            return _claude_ok()
        return {"producer_status": "timeout", "interpret": None, "act": None}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)
    assert calls.count("claude") == 1
    assert calls.count("codex") == 2  # 1 retry


def test_twin_retry_recovers_on_second_attempt(project_factory, monkeypatch):
    proj = project_factory(personas=("quant",))
    seq = ["unavailable", "ok"]

    def stub(engine, *a, **k):
        if engine == "claude":
            return _claude_ok()
        status = seq.pop(0)
        ok = status == "ok"
        return {"producer_status": status, "interpret": "ti" if ok else None,
                "act": "ta" if ok else None}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    out = emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)
    assert C.load_commentary(out)["personas"][0]["twin"]["producer_status"] == "ok"
    # recovered on retry -> no failure recorded
    assert not (proj / "outputs" / "twin_health.json").exists()


def test_commentary_claude_crash_propagates(project_factory, monkeypatch):
    # The required Claude leg is NOT swallowed: a crash fails the build (CR-1 finding #1),
    # so it can never masquerade as valid-but-empty commentary.
    proj = project_factory(personas=("quant",))

    def stub(engine, *a, **k):
        if engine == "claude":
            raise RuntimeError("claude died")
        return {"producer_status": "ok", "interpret": "ti", "act": "ta"}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    with pytest.raises(RuntimeError):
        emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)


def test_emit_writes_fallback_on_producer_crash(project_factory, monkeypatch):
    # A raised producer becomes a recorded 'unavailable' block, never a missing one (3b).
    proj = project_factory(personas=("quant",))

    def stub(engine, *a, **k):
        if engine == "claude":
            return _claude_ok()
        raise RuntimeError("codex segfault")

    monkeypatch.setattr(emit, "invoke_persona", stub)
    out = emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)
    twin = C.load_commentary(out)["personas"][0]["twin"]
    assert twin["producer_status"] == "unavailable"
    assert "segfault" in twin["error"]


def test_twin_circuit_breaker_halts_at_three(project_factory, monkeypatch):
    # 3 cumulative post-retry twin failures trip the breaker; first two only increment (3c).
    proj = project_factory(personas=("quant",))

    def stub(engine, *a, **k):
        if engine == "claude":
            return _claude_ok()
        return {"producer_status": "unavailable", "interpret": None, "act": None}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    cfg = emit._load_cfg(proj)
    emit.build_commentary(proj, 1, "H-FIX-001", "ctx", cfg, 5)
    emit.build_commentary(proj, 2, "H-FIX-001", "ctx", cfg, 5)
    health = json.loads((proj / "outputs" / "twin_health.json").read_text())
    assert health["failed_instances"] == 2
    with pytest.raises(emit.TwinHaltError):
        emit.build_commentary(proj, 3, "H-FIX-001", "ctx", cfg, 5)


def test_seed_expansion_shape_with_twin(project_factory, monkeypatch):
    proj = project_factory(personas=("quant", "cio"))

    def stub(engine, persona_id, persona_path, context, mode, timeout):
        assert mode == "seed"
        return {"producer_status": "ok", "interpret": "read", "act": "expanded list"}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    out = emit.build_seed_expansion(proj, 1, "seed hypotheses", emit._load_cfg(proj), 5)
    data = json.loads(out.read_text())
    assert data["round"] == 1
    assert {b["persona_id"] for b in data["personas"]} == {"quant", "cio"}
    # codex enabled -> every persona carries a twin attempt with a producer_status
    assert all(b["twin"]["engine"] == "codex" and b["twin"]["producer_status"] == "ok"
               for b in data["personas"])


# ------------------------------------------------------------------- parallelism (step 1)
def test_commentary_claude_nonok_status_fails_build(project_factory, monkeypatch):
    # R1/R2: a clean non-ok Claude status (not an exception) FAILS the build — never written as
    # a valid-but-empty block the gate would silently accept.
    proj = project_factory(personas=("quant",))

    def stub(engine, *a, **k):
        if engine == "claude":
            return {"producer_status": "timeout", "interpret": None, "act": None}
        return {"producer_status": "ok", "interpret": "ti", "act": "ta"}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    with pytest.raises(C.ContractError):
        emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)


def test_proposals_claude_crash_propagates(project_factory, monkeypatch):
    # R2: the required Claude leg now propagates in proposals too (was swallowed to unavailable).
    proj = project_factory(personas=("quant",))

    def stub(engine, *a, **k):
        if engine == "claude":
            raise RuntimeError("claude died")
        return {"producer_status": "ok", "candidates": [], "reprioritize": []}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    with pytest.raises(RuntimeError):
        emit.build_proposals(proj, 1, "ctx", emit._load_cfg(proj), 5)


def test_proposals_claude_nonok_status_fails_build(project_factory, monkeypatch):
    # R2: a clean non-ok Claude status in proposals fails the build (required leg).
    proj = project_factory(personas=("quant",))

    def stub(engine, *a, **k):
        if engine == "claude":
            return {"producer_status": "unavailable", "candidates": [], "reprioritize": []}
        return {"producer_status": "ok", "candidates": [], "reprioritize": []}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    with pytest.raises(C.ContractError):
        emit.build_proposals(proj, 1, "ctx", emit._load_cfg(proj), 5)


def test_commentary_blocks_keep_input_order_under_parallelism(project_factory, monkeypatch):
    # _run_parallel returns results in INPUT order regardless of completion order (Plan R2).
    import time

    proj = project_factory(personas=("quant", "cio", "portfolio-manager"))
    delay = {"quant": 0.06, "cio": 0.03, "portfolio-manager": 0.0}  # input[0] finishes last

    def stub(engine, persona_id, persona_path, context, mode, timeout):
        if engine == "claude":
            time.sleep(delay.get(persona_id, 0.0))
            return {"producer_status": "ok", "interpret": "i", "act": "a"}
        return {"producer_status": "ok", "interpret": "ti", "act": "ta"}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    out = emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)
    data = C.load_commentary(out)
    assert [b["persona_id"] for b in data["personas"]] == ["quant", "cio", "portfolio-manager"]


def test_parallel_twin_failures_counted_once_each(project_factory, monkeypatch):
    # R3/R4: under the pool, each failed twin CALL is counted exactly once (no race/double-count);
    # 3 concurrent failures trip the breaker.
    proj = project_factory(personas=("quant", "cio", "portfolio-manager"))

    def stub(engine, *a, **k):
        if engine == "claude":
            return {"producer_status": "ok", "interpret": "i", "act": "a"}
        return {"producer_status": "unavailable", "interpret": None, "act": None}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    with pytest.raises(emit.TwinHaltError):
        emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)
    health = json.loads((proj / "outputs" / "twin_health.json").read_text())
    assert health["failed_instances"] == 3  # exactly one per failed twin call


def test_max_workers_precedence_and_clamp(monkeypatch):
    # R7: env > yaml > default; parse-safe; clamp to [1, 8].
    monkeypatch.delenv("EMIT_MAX_WORKERS", raising=False)
    assert emit._max_workers({}) == emit.MAX_WORKERS_DEFAULT
    assert emit._max_workers({"emit_max_workers": 6}) == 6
    assert emit._max_workers({"emit_max_workers": "5"}) == 5
    assert emit._max_workers({"emit_max_workers": 0}) == 1
    assert emit._max_workers({"emit_max_workers": 999}) == emit.MAX_WORKERS_CEILING
    assert emit._max_workers({"emit_max_workers": "oops"}) == emit.MAX_WORKERS_DEFAULT
    monkeypatch.setenv("EMIT_MAX_WORKERS", "7")
    assert emit._max_workers({"emit_max_workers": 2}) == 7


# ------------------------------------------------------------------- batched commentary (step 2)
def test_batch_splits_into_per_hid_artifacts(project_factory, monkeypatch):
    # One batched call per persona/engine -> per-hid commentary.json (same contract).
    proj = project_factory(personas=("quant", "cio"))
    hyps = [("H-COR-001", "ctx1"), ("H-COR-002", "ctx2")]

    def stub(engine, pid, ppath, hh, timeout):
        return {"producer_status": "ok",
                "by_hid": {hid: {"interpret": f"{engine}-{pid}-{hid}", "act": "a"}
                           for hid, _ in hh}}

    monkeypatch.setattr(emit, "invoke_persona_batch", stub)
    outs = emit.build_commentary_batch(proj, 1, hyps, emit._load_cfg(proj), 5)
    assert len(outs) == 2
    for hid in ("H-COR-001", "H-COR-002"):
        data = C.load_commentary(proj / "outputs" / "commentary" / "round1" / f"{hid}.json")
        assert data["hypothesis_id"] == hid
        assert {b["persona_id"] for b in data["personas"]} == {"quant", "cio"}
        assert all(b["twin"]["producer_status"] == "ok" for b in data["personas"])


def test_batch_missing_hid_claude_raises(project_factory, monkeypatch):
    # R1: a hid missing from the required Claude batch FAILS the build (no silent empty pass).
    proj = project_factory(personas=("quant",))
    hyps = [("H-COR-001", "c1"), ("H-COR-002", "c2")]

    def stub(engine, pid, ppath, hh, timeout):
        by = {"H-COR-001": {"interpret": "i", "act": "a"}}  # H-COR-002 dropped
        if engine == "codex":
            by["H-COR-002"] = {"interpret": "ti", "act": "ta"}
        return {"producer_status": "ok", "by_hid": by}

    monkeypatch.setattr(emit, "invoke_persona_batch", stub)
    with pytest.raises(C.ContractError):
        emit.build_commentary_batch(proj, 1, hyps, emit._load_cfg(proj), 5)


def test_batch_twin_missing_hid_is_twin_absent(project_factory, monkeypatch):
    # Twin is non-blocking: a hid missing from the twin batch -> twin_absent for that hid only.
    proj = project_factory(personas=("quant",))
    hyps = [("H-COR-001", "c1"), ("H-COR-002", "c2")]

    def stub(engine, pid, ppath, hh, timeout):
        if engine == "claude":
            return {"producer_status": "ok",
                    "by_hid": {hid: {"interpret": "i", "act": "a"} for hid, _ in hh}}
        return {"producer_status": "ok",
                "by_hid": {"H-COR-001": {"interpret": "ti", "act": "ta"}}}  # H-COR-002 absent

    monkeypatch.setattr(emit, "invoke_persona_batch", stub)
    emit.build_commentary_batch(proj, 1, hyps, emit._load_cfg(proj), 5)
    d1 = C.load_commentary(proj / "outputs/commentary/round1/H-COR-001.json")
    d2 = C.load_commentary(proj / "outputs/commentary/round1/H-COR-002.json")
    assert d1["personas"][0]["agreement"] == "agree"
    assert d2["personas"][0]["agreement"] == "twin_absent"
    assert d2["personas"][0]["twin"]["producer_status"] == "unavailable"


def test_batch_oversize_raises(project_factory, monkeypatch):
    # R6: combined batch over the char cap fails loud BEFORE any model call.
    proj = project_factory(personas=("quant",))
    monkeypatch.setenv("EMIT_BATCH_MAX_CHARS", "10")
    monkeypatch.setattr(emit, "invoke_persona_batch",
                        lambda *a, **k: pytest.fail("must not invoke on oversize"))
    with pytest.raises(C.ContractError):
        emit.build_commentary_batch(proj, 1, [("H-COR-001", "x" * 50)], emit._load_cfg(proj), 5)


def test_cli_no_hypothesis_batches_active(project_factory, monkeypatch):
    # R5: `emit.py commentary --round N` with no --hypothesis batches all active hypotheses.
    proj = project_factory(personas=("quant",))

    def stub(engine, pid, ppath, hh, timeout):
        return {"producer_status": "ok",
                "by_hid": {hid: {"interpret": "i", "act": "a"} for hid, _ in hh}}

    monkeypatch.setattr(emit, "invoke_persona_batch", stub)
    rc = emit.main(["commentary", "--round", "1", "--project", str(proj)])
    assert rc == 0
    assert (proj / "outputs/commentary/round1/H-FIX-001.json").is_file()


# ------------------------------------------------------------------- code-review fixes
def test_batch_empty_twin_entry_is_twin_absent(project_factory, monkeypatch):
    # A twin entry present but with no content (interpret/act both falsy) is twin_absent,
    # NOT "agree" — "agree" must mean a real corroborating twin review.
    proj = project_factory(personas=("quant",))
    hyps = [("H-COR-001", "c1")]

    def stub(engine, pid, ppath, hh, timeout):
        if engine == "claude":
            return {"producer_status": "ok",
                    "by_hid": {"H-COR-001": {"interpret": "i", "act": "a"}}}
        return {"producer_status": "ok",
                "by_hid": {"H-COR-001": {"interpret": None, "act": None}}}  # empty content

    monkeypatch.setattr(emit, "invoke_persona_batch", stub)
    emit.build_commentary_batch(proj, 1, hyps, emit._load_cfg(proj), 5)
    blk = C.load_commentary(proj / "outputs/commentary/round1/H-COR-001.json")["personas"][0]
    assert blk["agreement"] == "twin_absent"
    assert blk["twin"]["producer_status"] == "unavailable"


def test_active_hyps_duplicate_id_raises(project_factory):
    # Two active round-1 notes sharing an id would silently collide -> fail loud.
    proj = project_factory(personas=("quant",))
    (proj / "hypothesis_tracking" / "h-fix-001-dup_2026-06-19.md").write_text(
        "---\nid: H-FIX-001\nround: 1\nhypothesis_status: active\nphase: recorded\n---\n\n# dup\n",
        encoding="utf-8",
    )
    with pytest.raises(C.ContractError):
        emit._active_hyps(proj, 1)


def test_cli_no_hypothesis_isolated_mode(project_factory, monkeypatch):
    # R5: commentary_batch:false routes the no-hypothesis CLI to isolated per-hyp build_commentary.
    proj = project_factory(personas=("quant",))
    cfg = emit._load_cfg(proj)
    cfg["commentary_batch"] = False
    monkeypatch.setattr(emit, "_load_cfg", lambda p: cfg)
    calls = []

    def stub(engine, pid, ppath, context, mode, timeout):
        calls.append((engine, mode))
        return {"producer_status": "ok", "interpret": "i", "act": "a"}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    monkeypatch.setattr(emit, "invoke_persona_batch",
                        lambda *a, **k: pytest.fail("batch seam used in isolated mode"))
    rc = emit.main(["commentary", "--round", "1", "--project", str(proj)])
    assert rc == 0
    assert (proj / "outputs/commentary/round1/H-FIX-001.json").is_file()
    assert ("claude", "commentary") in calls


def test_run_parallel_respects_max_workers():
    # In-flight jobs never exceed the cap.
    import threading
    import time

    live = 0
    peak = 0
    lock = threading.Lock()

    def job():
        nonlocal live, peak
        with lock:
            live += 1
            peak = max(peak, live)
        time.sleep(0.02)
        with lock:
            live -= 1
        return 1

    results = emit._run_parallel([job for _ in range(8)], 3)
    assert results == [1] * 8
    assert peak <= 3


def test_batch_twin_partial_recovers_on_retry(project_factory, monkeypatch):
    # A partial twin batch (drops a hid) is retried; a complete second attempt recovers it.
    proj = project_factory(personas=("quant",))
    hyps = [("H-COR-001", "c1"), ("H-COR-002", "c2")]
    seq = iter([
        {"H-COR-001": {"interpret": "ti", "act": "ta"}},  # attempt 1: partial (002 dropped)
        {"H-COR-001": {"interpret": "ti", "act": "ta"},
         "H-COR-002": {"interpret": "ti2", "act": "ta2"}},  # attempt 2: complete
    ])

    def stub(engine, pid, ppath, hh, timeout):
        if engine == "claude":
            return {"producer_status": "ok",
                    "by_hid": {hid: {"interpret": "i", "act": "a"} for hid, _ in hh}}
        return {"producer_status": "ok", "by_hid": next(seq)}

    monkeypatch.setattr(emit, "invoke_persona_batch", stub)
    emit.build_commentary_batch(proj, 1, hyps, emit._load_cfg(proj), 5)
    d2 = C.load_commentary(proj / "outputs/commentary/round1/H-COR-002.json")["personas"][0]
    assert d2["agreement"] == "agree"  # recovered on retry, not left twin_absent
