#!/usr/bin/env python3
"""synthesize.py — assemble a round's proposals into one decisions[] synthesis.

Deterministically groups the round's proposal candidates by `candidate_key`
(convergence = one decision with multiple `sources`) and writes
``outputs/synthesis/round<N>.json``. Coverage and traceability hold by construction:
every proposal candidate becomes (or joins) exactly one decision whose `sources` cite the
blocks that emitted it. Default classification follows the proposer's `kind`
(`hypothesis`->`promote`, `experiment`->`experiment`); the maintainer skill may refine
classifications/reasons or set the round-level `deferred` flag afterward.

This is the *assembler*; the panel's judgment lives in the proposals (model-authored) and
in any post-hoc edits to the synthesis. The gate (`verify_round.py`) enforces coverage,
traceability, and materialization on whatever synthesis is present.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import contracts as C


def synthesize(proposals: dict[str, Any]) -> dict[str, Any]:
    """Build the synthesis dict from a validated proposals dict (coverage by construction)."""
    rnd = proposals["round"]
    order: list[str] = []
    reps: dict[str, dict[str, Any]] = {}
    sources: dict[str, list[dict[str, str]]] = {}
    for block in proposals["blocks"]:
        for cand in block.get("candidates", []):
            key = cand["candidate_key"]
            if key not in reps:
                reps[key] = cand
                sources[key] = []
                order.append(key)
            sources[key].append({
                "persona_id": block["persona_id"],
                "engine": block["engine"],
                "candidate_key": key,
            })

    decisions: list[dict[str, Any]] = []
    for key in order:
        cand = reps[key]
        srcs = sources[key]
        classification = "experiment" if cand.get("kind") == "experiment" else "promote"
        who = ", ".join(sorted({f"{s['persona_id']}/{s['engine']}" for s in srcs}))
        decision: dict[str, Any] = {
            "decision_key": key,
            "classification": classification,
            "reason": f"Converged across {len(srcs)} proposer(s): {who}.",
            "title": cand.get("title", ""),
            "priority": cand.get("priority", "medium"),
            "parent": cand.get("parent"),
            # Carry the proposer's substance so promote.py's note stub keeps it.
            "rationale": cand.get("rationale", ""),
            "falsification": cand.get("falsification", ""),
            "decision_impact": cand.get("decision_impact", ""),
            "sources": srcs,
        }
        decisions.append(decision)

    # Consolidate existing-item reprioritizations from the proposal blocks (last wins per id).
    reprio: dict[str, dict[str, str]] = {}
    for block in proposals["blocks"]:
        for r in block.get("reprioritize", []):
            reprio[r["id"]] = {"id": r["id"], "action": r["action"], "why": r.get("why", "")}

    return {
        "round": rnd,
        "deferred": {"is_deferred": False, "reason": None},
        "termination_recommendation": {
            "recommend": "continue",
            "reason": None,
            "data_blocked": [],
        },
        "decisions": decisions,
        "reprioritize": list(reprio.values()),
    }


def run(project: Path, rnd: int) -> dict[str, Any]:
    """Read proposals/round<N>.json, write synthesis/round<N>.json, return the synthesis."""
    proposals = C.load_proposals(project / "outputs" / "proposals" / f"round{rnd}.json")
    result = synthesize(proposals)
    out = project / "outputs" / "synthesis" / f"round{rnd}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out, json.dumps(result, indent=2) + "\n")
    C.load_synthesis(out)  # self-check: the assembled artifact must validate
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="assemble proposals -> synthesis")
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--project", default=".")
    args = parser.parse_args(argv)
    try:
        result = run(Path(args.project).resolve(), args.round)
    except (C.ContractError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
