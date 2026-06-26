"""Tests for loop-reliability-v2 Tier 1 (the safety release).

Covers the accepted facts: a single shared atomic_write routed through every outputs/ writer
(byte-identical, torn-write-safe, breaker-safe), a per-project flock producer lock (refuse with
a distinct busy code, auto-release on death, release-on-breaker, fresh-project, no env bypass),
and the string-aware tolerant parse + strict required-leg signal.
"""

from __future__ import annotations

import fcntl
import json
import os
from pathlib import Path

import contracts as C
import emit
import install_support
import promote
import pytest
import synthesize


def _boom_replace(*_a, **_k):
    raise OSError("simulated crash before replace")


# --------------------------------------------------------------------------- atomic writes
def test_single_atomic_write_definition():
    # fact-1: the only definition lives in contracts; the others are aliases of it.
    assert promote._atomic_write is C.atomic_write
    assert install_support._atomic_write is C.atomic_write


def test_no_raw_json_write_text_in_producers():
    # fact-2: emit + synthesize route every JSON artifact write through atomic_write.
    for mod in (emit, synthesize):
        src = Path(mod.__file__).read_text(encoding="utf-8")
        assert ".write_text(json.dumps" not in src, f"{mod.__name__} has a raw JSON write_text"


def test_atomic_write_byte_parity_utf8(tmp_path):
    # fact-3: bytes are exactly the utf-8 encoding of the text; no .tmp left after success.
    p = tmp_path / "a.json"
    text = 'café — Größe\n{"k": "v"}\n'  # non-ASCII: proves encoding="utf-8" is honored
    C.atomic_write(p, text)
    assert p.read_bytes() == text.encode("utf-8")
    assert not (tmp_path / "a.json.tmp").exists()


def test_atomic_write_crash_leaves_prior_intact(tmp_path, monkeypatch):
    # fact-4: a crash before os.replace leaves the previous file intact; new content not promoted.
    p = tmp_path / "a.json"
    C.atomic_write(p, "OLD")
    monkeypatch.setattr(C.os, "replace", _boom_replace)
    with pytest.raises(OSError):
        C.atomic_write(p, "NEW")
    assert p.read_text() == "OLD"


def test_twin_health_torn_write_preserves_breaker(project_factory, monkeypatch):
    # fact-5: a torn twin_health.json write leaves the prior breaker counter intact.
    proj = project_factory(personas=("quant",))
    th = proj / "outputs" / "twin_health.json"
    th.write_text(json.dumps({"failed_instances": 2, "events": []}), encoding="utf-8")
    monkeypatch.setattr(C.os, "replace", _boom_replace)
    with pytest.raises(OSError):
        emit._bump_twin_health(proj, "codex", "quant", "commentary", "timeout")
    assert json.loads(th.read_text())["failed_instances"] == 2


# --------------------------------------------------------------------------- producer lock
def _hold_lock(proj: Path) -> int:
    lockpath = proj / "outputs" / ".emit.lock"
    lockpath.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lockpath, os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return fd


def test_concurrent_emit_refused_with_busy_code(project_factory):
    # fact-6: a second emit while the lock is held exits with the distinct busy code 3.
    proj = project_factory(personas=("quant",))
    fd = _hold_lock(proj)
    try:
        rc = emit.main(["seed", "--round", "1", "--project", str(proj)])
        assert rc == emit.EMIT_BUSY_EXIT == 3
    finally:
        os.close(fd)


def test_lock_auto_releases_on_holder_death(tmp_path):
    # fact-7: flock is the sole arbiter — closing the holder's fd frees it (no stale lock/steal).
    lockpath = tmp_path / "outputs" / ".emit.lock"
    lockpath.parent.mkdir(parents=True)
    fd1 = os.open(lockpath, os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd1, fcntl.LOCK_EX | fcntl.LOCK_NB)
    os.close(fd1)  # holder "dies"
    fd2 = os.open(lockpath, os.O_CREAT | os.O_RDWR)
    fcntl.flock(fd2, fcntl.LOCK_EX | fcntl.LOCK_NB)  # succeeds: nothing stale to reconcile
    os.close(fd2)


def test_lock_released_after_breaker_halt(project_factory, monkeypatch):
    # fact-8: an emit raising TwinHaltError inside the lock still releases it.
    proj = project_factory(personas=("quant",))
    (proj / "outputs" / "twin_health.json").write_text(
        json.dumps({"failed_instances": 3, "events": []}), encoding="utf-8"
    )
    monkeypatch.setattr(emit, "invoke_persona",
                        lambda *a, **k: {"producer_status": "ok", "interpret": "i", "act": "a"})
    rc = emit.main(["seed", "--round", "1", "--project", str(proj)])
    assert rc == emit.TWIN_HALT_EXIT  # 7 — halted, but the lock must have been released:
    os.close(_hold_lock(proj))  # would raise BlockingIOError if the lock were still held


def test_fresh_project_lock_dir_created(tmp_path):
    # fact-9: the lock's parent dir is created before os.open (a project with no outputs/ yet).
    lockpath = tmp_path / "fresh" / "outputs" / ".emit.lock"
    assert not lockpath.parent.exists()
    with emit._producer_lock(lockpath):
        assert lockpath.exists()


def test_no_env_lock_bypass():
    # fact-10: no EMIT_NO_LOCK (or equivalent) lock bypass exists in the source.
    assert "EMIT_NO_LOCK" not in Path(emit.__file__).read_text(encoding="utf-8")


# --------------------------------------------------------------------------- tolerant parse
def test_parse_fenced_and_prose_preserves_candidates():
    # fact-11: code-fenced / prose-wrapped JSON parses with all candidates preserved.
    fenced = '```json\n{"candidates": [{"candidate_key": "k1"}], "reprioritize": []}\n```'
    assert emit._parse_proposal_json(fenced)["candidates"] == [{"candidate_key": "k1"}]
    prose = 'Sure — {"candidates": [{"candidate_key": "k2"}]} hope that helps.'
    assert emit._parse_proposal_json(prose)["candidates"] == [{"candidate_key": "k2"}]


def test_strip_trailing_commas_is_string_aware():
    # fact-12: structural trailing commas dropped; a string literal containing ",}" preserved.
    src = '{"a": "x,}", "items": [1, 2,], "b": 3,}'
    obj = json.loads(emit._strip_trailing_commas(src))
    assert obj == {"a": "x,}", "items": [1, 2], "b": 3}
    assert obj["a"] == "x,}"  # string content untouched


def test_strict_parse_raises_unparseable_but_lenient_returns_empty():
    # fact-13a: a required (strict) leg raises on unparseable; the lenient default returns {}.
    with pytest.raises(C.ContractError):
        emit._extract_json_object("not json at all", strict=True)
    assert emit._extract_json_object("not json at all") == {}


def test_require_claude_rejects_ok_but_empty(project_factory, monkeypatch):
    # fact-13b: an ok-but-empty commentary leg fails the build (never a valid-but-empty block).
    def stub(engine, *a, **k):
        if engine == "claude":
            return {"producer_status": "ok", "interpret": "", "act": ""}
        return {"producer_status": "ok", "interpret": "ti", "act": "ta"}

    monkeypatch.setattr(emit, "invoke_persona", stub)
    proj = project_factory(personas=("quant",))
    with pytest.raises(C.ContractError):
        emit.build_commentary(proj, 1, "H-FIX-001", "ctx", emit._load_cfg(proj), 5)


# --------------------------------------------------------------------------- scope
# NOTE: the Tier-1 `test_no_tier2_surface` guard (claude_leg / `/loop` absent from emit.py) was
# RETIRED in Tier 2, which DELIBERATELY introduces the `claude_leg` flag + the `prompts`/`assemble`
# surface. That surface is now covered by test_subagent_leg.py (fail-closed contract, assemble,
# freshness, R1) and test_subagent_parity.py (byte-identity). See
# goals/loop-reliability-tier2-subagents/plan.md §1 Step 3.
