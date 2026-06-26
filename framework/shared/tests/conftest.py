"""Pytest configuration + a project-tree builder for the enforcement suite.

Adds `framework/shared/` to sys.path so the stdlib-only modules import by name,
and provides a `project_factory` fixture that materializes a complete, gate-shaped
research_loop project in a tmp dir (index, an active note, memo, config, and the
round-1 commentary/proposals/synthesis JSON) for end-to-end gate/promote tests.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

SHARED_DIR = Path(__file__).resolve().parent.parent
HOOKS_DIR = SHARED_DIR.parent / "hooks"
for _d in (SHARED_DIR, HOOKS_DIR):
    if str(_d) not in sys.path:
        sys.path.insert(0, str(_d))

TESTS = Path(__file__).resolve().parent
FRAMEWORK = TESTS.parents[1]
FIXTURES = TESTS / "fixtures"
INDEX_TEMPLATE = FRAMEWORK / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md"

_NOTE = """\
---
id: H-FIX-001
round: 1
hypothesis_status: active
phase: recorded
---

# H-FIX-001 — Demo hypothesis

## 6. Target / Outcome Definition
outcome = demo.

## 8. Sample Integrity And Alignment
N = 100.

## 11. Method
T1 demo test.

## 12. Results
T1 small positive.

## 15. Threats To Validity And Confounds
regime-specific.

## 18. Final Verdict
`weak_support` — demo, underpowered.

## 19. Decision Impact
hold research-only.

## 22. Reproduction
```bash
python3 scripts/demo.py
```

## 24. Feynman Explanation
Like checking the weather before a picnic.

## 21. Independent Persona Commentary
> generated excerpt; canonical: [commentary.json](../outputs/commentary/round1/H-FIX-001.json)

Backlinks: [Index](RESEARCH_HYPOTHESIS_INDEX.md) · [demo](../scripts/demo.py)
"""

_MEMO = """\
# Decision-Maker Memo — H-FIX-001: demo

**Status:** `living`
**Date:** `2026-06-13`
**Verdict:** `weak_support`
**Decision:** `hold as research-only`

## 1. Executive Summary

We tested H-FIX-001 and found weak_support; hold as research-only pending more data.

## 4. Timeline — What Actually Happened

| Round | Date | Step | What happened | Artifact |
|---|---|---|---|---|
| 1 | 2026-06-13 | test | tested H-FIX-001; weak_support | h-fix-001 |

## 7. Feynman Explanation

Like checking the weather before a picnic.
"""


def _yaml(personas, round_cap, k, persona_source, overrides, prefix):
    plist = ", ".join(personas)
    olist = ", ".join(overrides)
    return (
        f"prefix: {prefix}\n"
        f"personas: [{plist}]\n"
        f"codex: true\n"
        f"round_cap: {round_cap}\n"
        f"K: {k}\n"
        f"persona_source: {persona_source}\n"
        f"persona_overrides: [{olist}]\n"
    )


@pytest.fixture
def project_factory(tmp_path):
    """Return build(**overrides) -> project Path with a complete round-1 setup."""

    def build(
        *,
        personas=("quant", "cio"),
        round_cap=2,
        k=1,
        persona_source="local",
        overrides=(),
        prefix="FIX",
        with_commentary=True,
        with_seed=True,
    ) -> Path:
        proj = tmp_path / "proj"
        ht = proj / "hypothesis_tracking"
        ht.mkdir(parents=True)
        (proj / "scripts").mkdir()
        (proj / "data").mkdir()
        (proj / "outputs").mkdir()
        (proj / "scripts" / "demo.py").write_text("print('demo')\n", encoding="utf-8")
        shutil.copy(INDEX_TEMPLATE, ht / "RESEARCH_HYPOTHESIS_INDEX.md")
        (ht / "h-fix-001_demo_2026-06-13.md").write_text(_NOTE, encoding="utf-8")
        (ht / "memo-fix-decision.md").write_text(_MEMO, encoding="utf-8")
        (ht / "research_loop.yml").write_text(
            _yaml(personas, round_cap, k, persona_source, overrides, prefix), encoding="utf-8"
        )
        # round-1 artifacts
        cround = proj / "outputs" / "commentary" / "round1"
        cround.mkdir(parents=True)
        if with_commentary:
            shutil.copy(FIXTURES / "good_commentary.json", cround / "H-FIX-001.json")
        (proj / "outputs" / "proposals").mkdir()
        (proj / "outputs" / "synthesis").mkdir()
        shutil.copy(FIXTURES / "good_proposals.json",
                    proj / "outputs" / "proposals" / "round1.json")
        shutil.copy(FIXTURES / "good_synthesis.json",
                    proj / "outputs" / "synthesis" / "round1.json")
        if with_seed:
            seed = {
                "round": 1,
                "personas": [
                    {
                        "persona_id": pid,
                        "claude": {"interpret": "seed read", "act": "expanded list"},
                        "resolved_source": (
                            "local" if (persona_source == "global" and pid in overrides)
                            else persona_source
                        ),
                        "resolved_path": f".claude/personas/{pid}.md",
                        "agreement": "agree",
                        "twin": {"engine": "codex", "producer_status": "ok",
                                 "interpret": "ti", "act": "ta", "artifact_path": None},
                    }
                    for pid in personas
                ],
            }
            write_json(proj / "outputs" / "seed_expansion.json", seed)
        return proj

    return build


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")
