"""persona_source resolution + provenance gate (S9 / facts: persona-global,
persona-override-switch, persona-provenance)."""

from __future__ import annotations

import json
from pathlib import Path

import contracts as C
import emit
import promote
import verify_round


def test_resolve_global_is_authoritative(tmp_path):
    proj = tmp_path / "proj"
    path, src = emit.resolve_persona(proj, "quant", "global", [])
    assert src == "global"
    assert path == Path.home() / ".claude" / "personas" / "quant.md"


def test_resolve_override_uses_local(tmp_path):
    proj = tmp_path / "proj"
    path, src = emit.resolve_persona(proj, "quant", "global", ["quant"])
    assert src == "local"
    assert path == proj / ".claude" / "personas" / "quant.md"


def test_resolve_local_default(tmp_path):
    proj = tmp_path / "proj"
    _path, src = emit.resolve_persona(proj, "quant", "local", [])
    assert src == "local"


def _run(proj):
    return verify_round.main(["--round", "1", "--project", str(proj)])


def test_provenance_undeclared_local_under_global_fails(project_factory, capsys):
    # fixtures resolve_source == 'local'; switch the project to global with NO overrides.
    proj = project_factory(persona_source="global")
    promote.apply_round(proj, 1)
    assert _run(proj) == C.EXIT_INCOMPLETE
    assert "persona_source=global" in capsys.readouterr().out


def test_provenance_ok_when_overridden(project_factory):
    # global, but both personas declared as local overrides -> local resolution allowed.
    proj = project_factory(persona_source="global", overrides=("quant", "cio"))
    promote.apply_round(proj, 1)
    assert _run(proj) == C.EXIT_OK


def test_provenance_ok_local_default(project_factory):
    proj = project_factory()  # local source, local records
    promote.apply_round(proj, 1)
    assert _run(proj) == C.EXIT_OK


def test_global_records_pass_under_global(project_factory):
    # rewrite the commentary/proposals records to resolved_source=global under global config
    proj = project_factory(persona_source="global", overrides=())
    for rel in ["outputs/commentary/round1/H-FIX-001.json", "outputs/proposals/round1.json"]:
        p = proj / rel
        data = json.loads(p.read_text())
        recs = data.get("personas") or data.get("blocks")
        for r in recs:
            r["resolved_source"] = "global"
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    promote.apply_round(proj, 1)
    assert _run(proj) == C.EXIT_OK
