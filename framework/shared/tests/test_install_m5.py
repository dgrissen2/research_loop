"""Brownfield install helpers (S9 / facts: install-fresh-additive, hook-merge)."""

from __future__ import annotations

import json

import install_support as ins
import pytest


def _settings(tmp_path):
    return tmp_path / ".claude" / "settings.json"


def test_merge_creates_when_absent(tmp_path):
    sp = _settings(tmp_path)
    assert ins.merge_hook(sp, "python3 .claude/hooks/stop_verify_round.py") == "created"
    data = json.loads(sp.read_text())
    cmds = [h["command"] for g in data["hooks"]["Stop"] for h in g["hooks"]]
    assert any(ins.HOOK_MARKER in c for c in cmds)


def test_merge_is_idempotent(tmp_path):
    sp = _settings(tmp_path)
    ins.merge_hook(sp, "python3 a/stop_verify_round.py")
    # a second install (even with a different path) must not add a duplicate
    assert ins.merge_hook(sp, "python3 b/stop_verify_round.py") == "present"
    data = json.loads(sp.read_text())
    groups = data["hooks"]["Stop"]
    assert len(groups) == 1


def test_merge_preserves_unrelated(tmp_path):
    sp = _settings(tmp_path)
    sp.parent.mkdir(parents=True)
    sp.write_text(json.dumps({
        "model": "opus",
        "hooks": {"PreToolUse": [{"hooks": [{"type": "command", "command": "echo hi"}]}]},
    }), encoding="utf-8")
    ins.merge_hook(sp, "python3 .claude/hooks/stop_verify_round.py")
    data = json.loads(sp.read_text())
    assert data["model"] == "opus"  # unrelated key preserved
    pre = data["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert pre == "echo hi"  # unrelated hook preserved
    assert data["hooks"]["Stop"]  # our hook added


def test_merge_aborts_on_malformed(tmp_path):
    sp = _settings(tmp_path)
    sp.parent.mkdir(parents=True)
    sp.write_text("{ not json", encoding="utf-8")
    with pytest.raises(ins.MalformedSettings):
        ins.merge_hook(sp, "python3 .claude/hooks/stop_verify_round.py")
    assert sp.read_text() == "{ not json"  # left untouched


def test_shadowing_warnings(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".claude" / "personas").mkdir(parents=True)
    (proj / ".claude" / "personas" / "quant.md").write_text("# quant\n", encoding="utf-8")
    # global + quant present locally + not overridden -> warned
    warns = ins.shadowing_warnings(proj, ["quant", "cio"], "global", [])
    assert len(warns) == 1 and "quant" in warns[0]
    # overridden -> no warning
    assert ins.shadowing_warnings(proj, ["quant"], "global", ["quant"]) == []
    # local mode -> never warns
    assert ins.shadowing_warnings(proj, ["quant"], "local", []) == []
