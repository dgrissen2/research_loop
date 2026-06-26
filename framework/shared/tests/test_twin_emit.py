"""Tests for run_codex_twin.py --emit json (S5 / fact: twin-emit)."""

from __future__ import annotations

import json

import run_codex_twin as twin


def _personas(tmp_path):
    a = tmp_path / "quant.md"
    b = tmp_path / "cio.md"
    a.write_text("# quant\n", encoding="utf-8")
    b.write_text("# cio\n", encoding="utf-8")
    return a, b


def test_emit_json_ok(tmp_path, monkeypatch, capsys):
    def fake_run_once(prompt, out, effort, timeout):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("Interpretation paragraph.\n\nAction paragraph.", encoding="utf-8")
        return True, "ok"

    monkeypatch.setattr(twin, "run_once", fake_run_once)
    a, b = _personas(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("# finding\n", encoding="utf-8")
    rc = twin.main([str(note), "", str(tmp_path / "out.md"),
                    "--personas", f"{a},{b}", "--emit", "json"])
    assert rc == 0
    records = json.loads(capsys.readouterr().out)
    assert {r["persona_id"] for r in records} == {"quant", "cio"}
    for r in records:
        assert r["engine"] == "codex"
        assert r["producer_status"] == "ok"
        assert r["interpret"] == "Interpretation paragraph."
        assert r["act"] == "Action paragraph."


def test_emit_json_timeout_is_not_fatal(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(twin, "run_once", lambda *a, **k: (False, "timeout"))
    a, b = _personas(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("# finding\n", encoding="utf-8")
    rc = twin.main([str(note), "", str(tmp_path / "out.md"),
                    "--personas", f"{a},{b}", "--emit", "json", "--retries", "0"])
    assert rc == 0
    records = json.loads(capsys.readouterr().out)
    assert all(r["producer_status"] == "timeout" for r in records)
    assert all(r["interpret"] is None and r["artifact_path"] is None for r in records)


def test_emit_json_unavailable(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(twin, "run_once", lambda *a, **k: (False, "unavailable"))
    a, _ = _personas(tmp_path)
    note = tmp_path / "note.md"
    note.write_text("# finding\n", encoding="utf-8")
    twin.main([str(note), "", str(tmp_path / "out.md"),
               "--personas", str(a), "--emit", "json", "--retries", "0"])
    records = json.loads(capsys.readouterr().out)
    assert records[0]["producer_status"] == "unavailable"


def test_split_two():
    assert twin._split_two("a\n\nb\n\nc") == ("a", "b\n\nc")
    assert twin._split_two("only") == ("only", "")
