#!/usr/bin/env python3
"""emit.py — the Phase-1/6/8 producers: `emit.py seed | commentary | proposals`.

Runs **each persona as its own isolated, bounded call** (anti-anchoring: no shared
transcript), once per engine — Claude always, plus each *supported* twin engine
(Codex in v1). Writes contracts-validated artifacts:

- `seed`       -> `outputs/seed_expansion.json` (Phase-1: personas + twins expand the seed
  hypothesis set; one block per persona, same twin sub-shape as commentary).
- `commentary` -> `outputs/commentary/round<N>/<hyp-id>.json` (one per active hypothesis).
- `proposals`  -> `outputs/proposals/round<N>.json` (one Claude block per confirmed
  persona + one per supported twin engine; per-block candidate_key uniqueness).

The model invocation is the single seam `invoke_persona(...)`; tests monkeypatch it so the
orchestration (isolation, cardinality, validation) is exercised without real model calls.

Producer reliability (a layer SEPARATE from the gate; D8 keeps a single twin failure
non-blocking): each twin call retries once (2 attempts total); every persona/twin block is
ALWAYS written even if a call raises (`producer_status='unavailable'` + captured `error`), so
a missing block always means "not attempted"; and a cumulative circuit-breaker
(`outputs/twin_health.json`) halts the run with a dedicated exit code after 3 twin failures.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import contracts as C

# Canonical definition lives in contracts (shared by the gate); aliased here so existing
# references (emit.SUPPORTED_TWIN_ENGINES) and the producer code keep working.
SUPPORTED_TWIN_ENGINES = C.SUPPORTED_TWIN_ENGINES


# --------------------------------------------------------------------------- persona resolution
def resolve_persona(
    project: Path, pid: str, persona_source: str, overrides: list[str]
) -> tuple[Path, str]:
    """Return (path, resolved_source). Under 'global', global wins unless pid is overridden."""
    local = project / ".claude" / "personas" / f"{pid}.md"
    glob = Path.home() / ".claude" / "personas" / f"{pid}.md"
    if persona_source == "global" and pid not in overrides:
        return glob, "global"
    return local, "local"


# --------------------------------------------------------------------------- model seam
def _run_cli(cmd: list[str], prompt: str, via_stdin: bool, timeout: int) -> tuple[str, str]:
    """Run a bounded, process-group-scoped CLI call. Returns (producer_status, text)."""
    try:
        proc = subprocess.Popen(
            cmd if via_stdin else [*cmd, prompt],
            text=True, stdin=subprocess.PIPE if via_stdin else None,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
        )
    except FileNotFoundError:
        return "unavailable", ""
    try:
        out, _ = proc.communicate(input=prompt if via_stdin else None, timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.communicate()
        return "timeout", ""
    if proc.returncode != 0 or not (out or "").strip():
        return "unavailable", (out or "")
    return "ok", out


def _invoke_cli(engine: str, prompt: str, timeout: int) -> tuple[str, str]:
    """Dispatch a single bounded model call by engine. Returns (producer_status, text)."""
    if engine == "claude":
        cmd = ["claude", "-p", "--model", "claude-opus-5-5", "--effort", "high",
               "--no-session-persistence", "--permission-mode", "auto", "--tools", "default"]
        return _run_cli(cmd, prompt, via_stdin=True, timeout=timeout)
    cmd = ["codex", "exec", "-m", "gpt-5.6-sol", "-c", "model_reasoning_effort=high",
           "--full-auto", "--skip-git-repo-check", "--"]
    return _run_cli(cmd, prompt, via_stdin=False, timeout=timeout)


# --------------------------------------------------------------------------- prompt builders (pure)
def _persona_text(persona_path: Path, persona_id: str) -> str:
    """The persona body fed into a prompt: the file's text, or the id as a fallback label.

    The single definition both the subprocess seams and the frozen-prompt scaffold use, so a
    frozen prompt is byte-identical to what `invoke_persona*` would have built (no divergence).
    """
    return persona_path.read_text(encoding="utf-8") if persona_path.is_file() else persona_id


def _commentary_prompt(persona_text: str, context: str) -> str:
    """The isolated per-hypothesis commentary prompt (two paragraphs: interpret; then act)."""
    return (f"Adopt ONLY this persona and review the finding in EXACTLY two paragraphs "
            f"(interpret; then act).\n=== PERSONA ===\n{persona_text}\n"
            f"=== FINDING ===\n{context}")


def _seed_prompt(persona_text: str, context: str) -> str:
    """The Phase-1 seed-expansion prompt (two paragraphs: read of seeds; expanded list)."""
    return (f"Adopt ONLY this persona. Given the SEED hypotheses below, brainstorm and "
            f"expand them into a fuller, de-duplicated set, converging on the strongest "
            f"distinct hypotheses. EXACTLY two paragraphs: (1) your read of the seeds; "
            f"(2) the expanded hypothesis list.\n=== PERSONA ===\n{persona_text}\n"
            f"=== SEED HYPOTHESES ===\n{context}")


def _proposals_prompt(persona_text: str, context: str) -> str:
    """The Phase-8 proposals prompt (candidates/reprioritize JSON per the contract).

    When `context` carries an 'ALREADY TRACKED' list (folded in by the producers via
    `_existing_items_block`), the panel is told not to duplicate it — so it proposes genuinely
    new items or explicit variants.
    """
    return (f"Adopt ONLY this persona. Propose NEW hypotheses/experiments as JSON "
            f'{{"candidates":[...],"reprioritize":[...]}} per the contract. If an ALREADY '
            f"TRACKED list appears below, do NOT duplicate those items — a variant is OK only "
            f"if you state how it differs.\n"
            f"=== PERSONA ===\n{persona_text}\n=== ROUND FINDINGS ===\n{context}")


def _commentary_batch_prompt(persona_text: str, hyps: list[tuple[str, str]]) -> str:
    """The batched-commentary prompt: review every hyp, return one JSON entry per hid."""
    ids = ", ".join(hid for hid, _ in hyps)
    findings = "\n\n".join(f"=== {hid} ===\n{ctx}" for hid, ctx in hyps)
    return (
        f"Adopt ONLY this persona and review EACH finding below. Return ONLY a JSON object "
        f'mapping every hypothesis id to {{"interpret": "...", "act": "..."}} — exactly one '
        f"entry for each of these ids: {ids}.\n"
        f"=== PERSONA ===\n{persona_text}\n=== FINDINGS ===\n{findings}"
    )


def invoke_persona(engine: str, persona_id: str, persona_path: Path, context: str,
                   mode: str, timeout: int, prompt: str | None = None) -> dict[str, Any]:
    """THE model seam (monkeypatched in tests). Returns a partial record for `mode`.

    With `prompt=None` the per-mode prompt is built from the persona file + context (today's
    behavior). A supplied `prompt` is used as-is for the CLI call — the seam `assemble` uses to
    fire the Codex twin from a FROZEN prompt (no persona-file re-read, no input divergence).
    """
    if prompt is None:
        persona_text = _persona_text(persona_path, persona_id)
        if mode == "commentary":
            prompt = _commentary_prompt(persona_text, context)
        elif mode == "seed":
            prompt = _seed_prompt(persona_text, context)
        else:
            prompt = _proposals_prompt(persona_text, context)
    status, text = _invoke_cli(engine, prompt, timeout)
    if mode in ("commentary", "seed"):
        return {"producer_status": status, **_parse_seed_record(text)}
    # proposals: an ok call returning unparseable JSON is a real failure, not empty output —
    # parse strictly so the required leg raises instead of masking as empty candidates.
    return {"producer_status": status, **_parse_proposals_record(text, strict=(status == "ok"))}


def _split_two(text: str) -> tuple[str | None, str | None]:
    parts = [p.strip() for p in text.strip().split("\n\n") if p.strip()]
    if not parts:
        return None, None
    return parts[0], ("\n\n".join(parts[1:]) or None)


def _strip_trailing_commas(text: str) -> str:
    """Drop a comma that precedes a closing ``}``/``]``, but ONLY outside string literals.

    A raw ``re.sub`` would corrupt a comma inside a JSON string value (e.g. a candidate title
    containing ``",}"``); this tracks quote/escape state so only *structural* trailing commas
    are removed — never string content (the "syntax only, never invents content" invariant).
    """
    out: list[str] = []
    in_str = esc = False
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
            out.append(ch)
        elif ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if not (j < n and text[j] in "}]"):
                out.append(ch)  # keep it; it's a real separator, not a trailing comma
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _extract_json_object(text: str, *, strict: bool = False) -> dict[str, Any]:
    """Extract the outermost JSON object from model text ({...} -> dict).

    Tolerant of code fences / surrounding prose (the outermost ``{``..``}`` is taken) and of
    structural trailing commas (string-aware cleanup). ``strict=True`` is for a REQUIRED leg:
    an unparseable result raises ContractError instead of silently returning ``{}`` — closing
    the swallow-to-empty hole where a failed parse otherwise looked like valid-but-empty output.
    """
    try:
        start, end = text.index("{"), text.rindex("}")
        obj = json.loads(_strip_trailing_commas(text[start:end + 1]))
    except (ValueError, json.JSONDecodeError) as exc:
        if strict:
            raise C.ContractError(f"required model JSON is unparseable: {exc}") from exc
        return {}
    if isinstance(obj, dict):
        return obj
    if strict:
        raise C.ContractError("required model JSON is not an object")
    return {}


def _parse_proposal_json(text: str, *, strict: bool = False) -> dict[str, Any]:
    obj = _extract_json_object(text, strict=strict)
    return {"candidates": obj.get("candidates", []),
            "reprioritize": obj.get("reprioritize", [])}


# --------------------------------------------------------------------------- parse seam (pure)
def _parse_seed_record(text: str) -> dict[str, Any]:
    """Two-paragraph parse for seed / isolated-commentary text -> {interpret, act}."""
    interpret, act = _split_two(text)
    return {"interpret": interpret, "act": act}


def _parse_proposals_record(text: str, *, strict: bool = False) -> dict[str, Any]:
    """Proposals parse -> {candidates, reprioritize} (thin name over _parse_proposal_json)."""
    return _parse_proposal_json(text, strict=strict)


def _parse_commentary_record(text: str, hyps: list[tuple[str, str]]) -> dict[str, Any]:
    """Batched-commentary parse -> the by_hid {hid: {interpret, act}} mapping.

    Tolerant extraction of the outermost JSON object; only well-formed dict entries for the
    requested hids are kept (a dropped/garbled hid is simply absent, the same as the subprocess
    batch seam — completeness is then enforced by the required-Claude check, not here).
    """
    raw = _extract_json_object(text)
    by_hid: dict[str, Any] = {}
    for hid, _ in hyps:
        entry = raw.get(hid)
        if isinstance(entry, dict):
            by_hid[hid] = {"interpret": entry.get("interpret"), "act": entry.get("act")}
    return by_hid


# --------------------------------------------------------------------------- producer reliability
TWIN_FAILURE_THRESHOLD = 3   # cumulative twin failures (post-retry) that trip the breaker
TWIN_HALT_EXIT = 7           # dedicated exit code: circuit-breaker halted the run (3c)


class TwinHaltError(RuntimeError):
    """Cumulative twin failures reached the circuit-breaker threshold; the run must halt (3c)."""

    def __init__(self, failed_instances: int) -> None:
        self.failed_instances = failed_instances
        super().__init__(
            f"twin circuit-breaker tripped: {failed_instances} cumulative twin failures "
            f"(>= {TWIN_FAILURE_THRESHOLD}). Halting so the run can be reported to the user."
        )


def _invoke_safe(engine: str, pid: str, ppath: Path, context: str, mode: str,
                 timeout: int, retries: int, prompt: str | None = None) -> dict[str, Any]:
    """Invoke `invoke_persona` with `retries` extra attempts. ALWAYS returns a record.

    Retries while the producer_status is not 'ok' (3a — twins pass retries=1 → 2 attempts;
    the Claude leg passes retries=0). A raised producer exception is captured into an
    'unavailable' fallback record with the error text (3b) so a missing block downstream
    always means 'not attempted', never 'attempted but died'. A frozen `prompt` (assemble's
    twin leg) is forwarded only when present, so existing seam monkeypatches keep their arity.
    """
    extra = {} if prompt is None else {"prompt": prompt}
    rec: dict[str, Any] = {"producer_status": "unavailable"}
    for _ in range(retries + 1):
        try:
            rec = invoke_persona(engine, pid, ppath, context, mode, timeout, **extra)
        except Exception as exc:  # noqa: BLE001 — a producer crash must not kill the loop
            rec = {"producer_status": "unavailable", "error": str(exc)}
        if rec.get("producer_status") == "ok":
            break
    return rec


def _bump_twin_health(project: Path, engine: str, pid: str, mode: str, status: str) -> int:
    """Increment the cumulative twin-failure counter in outputs/twin_health.json; return total."""
    path = project / "outputs" / "twin_health.json"
    health: dict[str, Any] = {"failed_instances": 0, "events": []}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8") or "{}")
            if isinstance(loaded, dict):
                health = loaded
        except json.JSONDecodeError:
            print(f"[emit] WARNING: {path} is corrupt; resetting the twin-failure counter",
                  file=sys.stderr)
    health["failed_instances"] = int(health.get("failed_instances", 0)) + 1
    health.setdefault("events", []).append(
        {"engine": engine, "persona_id": pid, "mode": mode, "producer_status": status}
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(path, json.dumps(health, indent=2) + "\n")
    return int(health["failed_instances"])


def _check_breaker(project: Path) -> None:
    """Raise TwinHaltError if cumulative twin failures have reached the threshold (3c)."""
    path = project / "outputs" / "twin_health.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8") or "{}")
    except json.JSONDecodeError:
        print(f"[emit] WARNING: {path} is corrupt; cannot evaluate the twin circuit-breaker",
              file=sys.stderr)
        return
    total = int(data.get("failed_instances", 0)) if isinstance(data, dict) else 0
    if total >= TWIN_FAILURE_THRESHOLD:
        raise TwinHaltError(total)


# --------------------------------------------------------------------------- builders
def _engines(cfg: dict[str, Any]) -> list[str]:
    engines = ["claude"]
    if cfg.get("codex"):
        engines += [e for e in SUPPORTED_TWIN_ENGINES]
    return engines


# --------------------------------------------------------------------------- bounded parallelism
MAX_WORKERS_DEFAULT = 3   # concurrent Codex-xhigh calls are heavy; stay conservative (R7/A3)
MAX_WORKERS_CEILING = 8


def _max_workers(cfg: dict[str, Any]) -> int:
    """Concurrency cap: EMIT_MAX_WORKERS env > cfg emit_max_workers > default 3.

    Parse-safe (bad/missing -> default), clamped to [1, 8]. `1` is the serial fallback —
    the no-code rollback for parallelism (Plan R7).
    """
    raw = os.environ.get("EMIT_MAX_WORKERS")
    if raw is None:
        raw = cfg.get("emit_max_workers")
    try:
        n = int(raw)
    except (TypeError, ValueError):
        n = MAX_WORKERS_DEFAULT
    return max(1, min(MAX_WORKERS_CEILING, n))


def _run_parallel(jobs: list, max_workers: int) -> list:
    """Run zero-arg `jobs` concurrently; return results in input order.

    Jobs that raise are captured; after all settle, the FIRST exception by input index is
    re-raised, so a required-leg (Claude) crash fails the build deterministically (Plan R2).
    Optional (twin) jobs go through `_invoke_safe` and never raise. With `max_workers <= 1`
    or a single job, runs serially — disabling concurrency (the Plan R7 fallback). The serial
    path short-circuits on the first raising job; the parallel path lets all submitted jobs
    finish before re-raising. Both fail the build, but failure-path side effects differ.
    """
    n = len(jobs)
    if n == 0:
        return []
    if max_workers <= 1 or n == 1:
        return [job() for job in jobs]
    results: list[Any] = [None] * n
    errors: list[BaseException | None] = [None] * n
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        fut_to_i = {ex.submit(jobs[i]): i for i in range(n)}
        for fut in concurrent.futures.as_completed(fut_to_i):
            i = fut_to_i[fut]
            try:
                results[i] = fut.result()
            except BaseException as exc:  # noqa: BLE001 — re-raised in index order below
                errors[i] = exc
    for err in errors:
        if err is not None:
            raise err
    return results


def _require_claude(rec: dict[str, Any], who: str) -> dict[str, Any]:
    """The Claude leg is REQUIRED: a non-ok status fails the build (Plan R1/R2).

    `invoke_persona` already raises on a crash; this also rejects a clean non-ok status
    (timeout/unavailable) so a failed Claude call can never be written as a valid-but-empty
    block the gate would silently accept. For a commentary/seed leg it additionally rejects an
    ok result whose interpret AND act are both empty (a masked failure — e.g. unparseable
    prose), closing the swallow-to-empty hole.
    """
    if rec.get("producer_status") != "ok":
        raise C.ContractError(
            f"required Claude leg for {who} did not succeed "
            f"(producer_status={rec.get('producer_status')!r})"
        )
    if ("interpret" in rec or "act" in rec) and not (rec.get("interpret") or rec.get("act")):
        raise C.ContractError(f"required Claude leg for {who} returned empty interpret and act")
    return rec


def _twin_block(rec: dict[str, Any]) -> dict[str, Any]:
    """Shape a commentary/seed twin sub-block from an `_invoke_safe` record (no I/O)."""
    block: dict[str, Any] = {
        "engine": "codex",
        "producer_status": rec.get("producer_status", "unavailable"),
        "interpret": rec.get("interpret"),
        "act": rec.get("act"),
        "artifact_path": None,
    }
    if rec.get("error"):
        block["error"] = rec["error"]
    return block


def _record_twin_failures(project: Path, blocks: list[dict[str, Any]], mode: str) -> None:
    """Serial twin-health bookkeeping after the pool drains (Plan R3): one bump per failed
    twin CALL — avoids the read-modify-write race of bumping inside worker threads."""
    for b in blocks:
        tw = b.get("twin")
        if tw and tw.get("producer_status") != "ok":
            _bump_twin_health(project, tw.get("engine", "codex"),
                              b.get("persona_id", "?"), mode, tw["producer_status"])


# --------------------------------------------------------------------------- block shapers (pure)
def _seed_block(pid: str, rsource: str, ppath: Path, claude_rec: dict[str, Any],
                twin_rec: dict[str, Any] | None, use_twin: bool) -> dict[str, Any]:
    """Pure paired block (Claude + optional Codex twin) for seed / isolated commentary.

    Status-driven agreement: a twin counts as "agree" iff its producer_status is ok. Shared by
    the subprocess builder and the assembler so both emit byte-identical blocks.
    """
    block: dict[str, Any] = {
        "persona_id": pid,
        "claude": {"interpret": claude_rec.get("interpret") or "",
                   "act": claude_rec.get("act") or ""},
        "resolved_source": rsource,
        "resolved_path": str(ppath),
        "disagreement_note": None,
    }
    if use_twin:
        twin_rec = twin_rec or {}
        block["twin"] = _twin_block(twin_rec)
        block["agreement"] = "agree" if twin_rec.get("producer_status") == "ok" else "twin_absent"
    else:
        block["agreement"] = "twin_absent"
    return block


def _commentary_block(pid: str, rsource: str, ppath: Path, claude_entry: dict[str, Any],
                      twin_rec: dict[str, Any] | None, hid: str,
                      use_twin: bool) -> dict[str, Any]:
    """Pure per-(hid, persona) batched-commentary block. Shared by the batch builder + assembler.

    Content-gated agreement: a twin entry counts as "agree" only when the twin call succeeded
    AND this hid carries content — a present-but-empty entry is twin_absent, not "agree".
    """
    block: dict[str, Any] = {
        "persona_id": pid,
        "claude": {"interpret": claude_entry.get("interpret") or "",
                   "act": claude_entry.get("act") or ""},
        "resolved_source": rsource,
        "resolved_path": str(ppath),
        "disagreement_note": None,
    }
    if use_twin:
        trec = twin_rec or {}
        te = (trec.get("by_hid") or {}).get(hid)
        # A twin entry only counts when the call succeeded AND this hid has content;
        # a present-but-empty entry is twin_absent, not "agree" (parity with non-batch).
        te_ok = bool(te and (te.get("interpret") or te.get("act")))
        tstatus = trec.get("producer_status", "unavailable") if te_ok else "unavailable"
        block["twin"] = {
            "engine": "codex",
            "producer_status": tstatus,
            "interpret": (te or {}).get("interpret"),
            "act": (te or {}).get("act"),
            "artifact_path": None,
        }
        if trec.get("error"):
            block["twin"]["error"] = trec["error"]
        block["agreement"] = "agree" if tstatus == "ok" else "twin_absent"
    else:
        block["agreement"] = "twin_absent"
    return block


def _proposals_block(pid: str, engine: str, rsource: str, ppath: Path,
                     rec: dict[str, Any]) -> dict[str, Any]:
    """Pure per-(persona, engine) proposals block (dedupes candidate_keys). Shared."""
    block: dict[str, Any] = {
        "persona_id": pid, "engine": engine,
        "producer_status": rec.get("producer_status", "unavailable"),
        "resolved_source": rsource, "resolved_path": str(ppath),
        "candidates": _dedupe_candidates(rec.get("candidates", [])),
        "reprioritize": rec.get("reprioritize", []),
    }
    if rec.get("error"):
        block["error"] = rec["error"]
    return block


def build_commentary(project: Path, rnd: int, hid: str, context: str,
                     cfg: dict[str, Any], timeout: int) -> Path:
    """Build + validate one commentary.json (a block per confirmed persona; isolated calls).

    Personas run concurrently under a bounded pool (Plan R2/R7). The required Claude leg fails
    the build on any non-ok status; the optional twin is always written; twin-failure
    bookkeeping is serial after the pool drains (Plan R3).
    """
    source = cfg.get("persona_source", "local")
    overrides = list(cfg.get("persona_overrides", []))
    use_twin = "codex" in _engines(cfg)
    resolved = [(pid, *resolve_persona(project, pid, source, overrides))
                for pid in cfg.get("personas", [])]

    def _block(pid: str, ppath: Path, rsource: str) -> dict[str, Any]:
        claude = _require_claude(
            invoke_persona("claude", pid, ppath, context, "commentary", timeout),
            f"commentary {hid} / {pid}",
        )
        block: dict[str, Any] = {
            "persona_id": pid,
            "claude": {"interpret": claude.get("interpret") or "",
                       "act": claude.get("act") or ""},
            "resolved_source": rsource,
            "resolved_path": str(ppath),
            "disagreement_note": None,
        }
        if use_twin:
            rec = _invoke_safe("codex", pid, ppath, context, "commentary", timeout, retries=1)
            block["twin"] = _twin_block(rec)
            block["agreement"] = "agree" if rec.get("producer_status") == "ok" else "twin_absent"
        else:
            block["agreement"] = "twin_absent"
        return block

    jobs = [(lambda pid=pid, pp=pp, rs=rs: _block(pid, pp, rs)) for pid, pp, rs in resolved]
    blocks = _run_parallel(jobs, _max_workers(cfg))
    _record_twin_failures(project, blocks, "commentary")
    data = {"round": rnd, "hypothesis_id": hid, "personas": blocks}
    out = project / "outputs" / "commentary" / f"round{rnd}" / f"{hid}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out, json.dumps(data, indent=2) + "\n")
    C.load_commentary(out)  # self-check
    _check_breaker(project)  # halt if cumulative twin failures hit the threshold (3c)
    return out


# --------------------------------------------------------------------------- batched commentary
BATCH_MAX_CHARS_DEFAULT = 120_000   # R6: fail loud above this combined batch size


def _batch_max_chars(cfg: dict[str, Any]) -> int:
    """Oversize threshold: EMIT_BATCH_MAX_CHARS env > cfg emit_batch_max_chars > default."""
    raw = os.environ.get("EMIT_BATCH_MAX_CHARS")
    if raw is None:
        raw = cfg.get("emit_batch_max_chars")
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return BATCH_MAX_CHARS_DEFAULT


def invoke_persona_batch(engine: str, persona_id: str, persona_path: Path,
                         hyps: list[tuple[str, str]], timeout: int,
                         prompt: str | None = None) -> dict[str, Any]:
    """Batched commentary seam (monkeypatched in tests): ONE call reviews all `hyps`
    [(hid, context), ...] and returns {producer_status, by_hid: {hid: {interpret, act}}}.

    With `prompt=None` the batch prompt is built from the persona file (today's behavior); a
    supplied `prompt` is used as-is — the FROZEN prompt `assemble` fires the Codex twin from.
    """
    if prompt is None:
        prompt = _commentary_batch_prompt(_persona_text(persona_path, persona_id), hyps)
    status, text = _invoke_cli(engine, prompt, timeout)
    by_hid = _parse_commentary_record(text, hyps) if status == "ok" else {}
    return {"producer_status": status, "by_hid": by_hid}


def _invoke_safe_batch(engine: str, pid: str, ppath: Path, hyps: list[tuple[str, str]],
                       timeout: int, retries: int, prompt: str | None = None) -> dict[str, Any]:
    """Retry+fallback wrapper for the batched seam (twin leg). ALWAYS returns a record.

    Retries while the call is not ok OR the response dropped some requested hids — a partial
    batch is the common twin failure mode, so the retry budget should cover it, not just a
    hard error (Plan R3 reliability intent). A frozen `prompt` (assemble's twin leg) is
    forwarded only when present, so existing seam monkeypatches keep their arity.
    """
    extra = {} if prompt is None else {"prompt": prompt}
    rec: dict[str, Any] = {"producer_status": "unavailable", "by_hid": {}}
    want = {hid for hid, _ in hyps}
    for _ in range(retries + 1):
        try:
            rec = invoke_persona_batch(engine, pid, ppath, hyps, timeout, **extra)
        except Exception as exc:  # noqa: BLE001 — a producer crash must not kill the loop
            rec = {"producer_status": "unavailable", "by_hid": {}, "error": str(exc)}
        if rec.get("producer_status") == "ok" and want.issubset(rec.get("by_hid", {})):
            break
    return rec


def build_commentary_batch(project: Path, rnd: int, hyps: list[tuple[str, str]],
                           cfg: dict[str, Any], timeout: int) -> list[Path]:
    """Batched Phase-6 (Plan G1/R1/R3/R6): one (persona, engine) call covers ALL `hyps`
    [(hid, context)], split into per-hid commentary.json files (identical shape/contract to
    the per-hypothesis path). The required Claude leg fails the build if any hid is missing or
    empty (R1); the optional twin is non-blocking. One twin CALL per persona counts once for
    health (R3). Fails loud above the batch size cap (R6).
    """
    if not hyps:
        return []
    total = sum(len(ctx) for _, ctx in hyps)
    cap = _batch_max_chars(cfg)
    if total > cap:
        raise C.ContractError(
            f"round {rnd} commentary batch too large ({total} > {cap} chars); "
            f"set commentary_batch: false or split the round"
        )
    source = cfg.get("persona_source", "local")
    overrides = list(cfg.get("persona_overrides", []))
    use_twin = "codex" in _engines(cfg)
    resolved = [(pid, *resolve_persona(project, pid, source, overrides))
                for pid in cfg.get("personas", [])]

    def _claude_job(pid: str, ppath: Path, rsource: str) -> dict[str, Any]:
        rec = invoke_persona_batch("claude", pid, ppath, hyps, timeout)
        _require_claude(rec, f"commentary batch / {pid}")  # non-ok status -> fail build (R2)
        for hid, _ in hyps:
            e = rec["by_hid"].get(hid)
            if not (e and (e.get("interpret") or e.get("act"))):
                raise C.ContractError(
                    f"required Claude commentary for {hid} / {pid} missing or empty in batch"
                )
        return {"persona_id": pid, "rsource": rsource, "ppath": str(ppath), "rec": rec}

    def _twin_job(pid: str, ppath: Path, rsource: str) -> dict[str, Any]:
        rec = _invoke_safe_batch("codex", pid, ppath, hyps, timeout, retries=1)
        return {"persona_id": pid, "rsource": rsource, "ppath": str(ppath), "rec": rec}

    jobs = [(lambda p=pid, pp=pp, rs=rs: _claude_job(p, pp, rs)) for pid, pp, rs in resolved]
    if use_twin:
        jobs += [(lambda p=pid, pp=pp, rs=rs: _twin_job(p, pp, rs)) for pid, pp, rs in resolved]
    settled = _run_parallel(jobs, _max_workers(cfg))

    n = len(resolved)
    claude_by_pid = {r["persona_id"]: r for r in settled[:n]}
    twin_by_pid = {r["persona_id"]: r for r in settled[n:]} if use_twin else {}

    # Twin-health: one bump per failed twin CALL (Plan R3), serial after the pool.
    for pid, _pp, _rs in resolved:
        tr = twin_by_pid.get(pid)
        if tr and tr["rec"].get("producer_status") != "ok":
            _bump_twin_health(project, "codex", pid, "commentary",
                              tr["rec"].get("producer_status", "unavailable"))

    out_paths: list[Path] = []
    for hid, _ctx in hyps:
        blocks = []
        for pid, pp, rs in resolved:
            cr = claude_by_pid[pid]["rec"]["by_hid"][hid]
            trec = twin_by_pid[pid]["rec"] if use_twin else None
            blocks.append(_commentary_block(pid, rs, pp, cr, trec, hid, use_twin))
        data = {"round": rnd, "hypothesis_id": hid, "personas": blocks}
        out = project / "outputs" / "commentary" / f"round{rnd}" / f"{hid}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        C.atomic_write(out, json.dumps(data, indent=2) + "\n")
        C.load_commentary(out)  # self-check (same per-hid contract as the isolated path)
        out_paths.append(out)
    _check_breaker(project)  # halt if cumulative twin failures hit the threshold (3c)
    return out_paths


def _existing_items_block(project: Path) -> str:
    """Render already-tracked hypotheses + experiments (ID, title, status) for the Phase-8
    proposals prompt, so the panel proposes genuinely new items instead of duplicates.

    Best-effort and fail-open: a missing / empty / malformed index yields '' (it must never
    block a producer). IDs + one-line titles + status only — never note bodies (keep it lean).
    """
    index = project / "hypothesis_tracking" / "RESEARCH_HYPOTHESIS_INDEX.md"
    try:
        md = index.read_text(encoding="utf-8")
    except (OSError, UnicodeError):  # missing, unreadable, or non-UTF-8 index — fail open
        return ""
    lines: list[str] = []
    for table, id_col, title_col in (("hypotheses", "Hypothesis ID", "Claim"),
                                     ("followup", "Experiment ID", "Proposed Experiment")):
        try:
            _, rows = C.read_index_table(md, table)
        except C.ContractError:
            continue
        for r in rows:
            hid = (r.get(id_col) or "").strip()
            if not hid:
                continue
            title = " ".join((r.get(title_col) or "").split())[:100]
            status = (r.get("Status") or "").strip()
            lines.append(f"- {hid} ({status}) {title}".rstrip())
    if not lines:
        return ""
    return ("=== ALREADY TRACKED (do NOT re-propose; a variant is OK only if it states how it "
            "differs) ===\n" + "\n".join(lines))


def build_proposals(project: Path, rnd: int, context: str,
                    cfg: dict[str, Any], timeout: int) -> Path:
    """Build + validate proposals.json (one Claude block/persona + one/supported twin engine).

    Persona x engine jobs run concurrently under a bounded pool (Plan R2/R7): the Claude leg is
    REQUIRED (non-ok fails the build); twin legs are optional (always-write). Twin-failure
    bookkeeping is serial after the pool drains (Plan R3).
    """
    source = cfg.get("persona_source", "local")
    overrides = list(cfg.get("persona_overrides", []))
    resolved = [(pid, *resolve_persona(project, pid, source, overrides))
                for pid in cfg.get("personas", [])]

    # Show the panel what's already tracked so it proposes new items, not dupes (folded into
    # context — same for every persona; the seam stays untouched so monkeypatch arity holds).
    existing = _existing_items_block(project)
    context = f"{context}\n\n{existing}" if existing else context

    def _block(pid: str, ppath: Path, rsource: str, engine: str) -> dict[str, Any]:
        is_twin = engine in SUPPORTED_TWIN_ENGINES
        if is_twin:
            rec = _invoke_safe(engine, pid, ppath, context, "proposals", timeout, retries=1)
        else:
            rec = _require_claude(
                invoke_persona(engine, pid, ppath, context, "proposals", timeout),
                f"proposals / {pid}",
            )
        return _proposals_block(pid, engine, rsource, ppath, rec)

    jobs = [
        (lambda pid=pid, pp=pp, rs=rs, e=engine: _block(pid, pp, rs, e))
        for pid, pp, rs in resolved
        for engine in _engines(cfg)
    ]
    blocks = _run_parallel(jobs, _max_workers(cfg))
    for b in blocks:
        if b["engine"] in SUPPORTED_TWIN_ENGINES and b["producer_status"] != "ok":
            _bump_twin_health(project, b["engine"], b["persona_id"], "proposals",
                              b["producer_status"])
    data = {"round": rnd, "blocks": blocks}
    out = project / "outputs" / "proposals" / f"round{rnd}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out, json.dumps(data, indent=2) + "\n")
    C.load_proposals(out)  # self-check (enforces per-block candidate_key uniqueness)
    _check_breaker(project)  # halt if cumulative twin failures hit the threshold (3c)
    return out


def _selfcheck_seed_expansion(data: dict[str, Any], require_twin: bool) -> None:
    """Structural self-check for seed_expansion.json (mirrors load_commentary's self-check role).

    The gate's Phase-1 check (Step 4c) is the real authority; this only guarantees emit never
    writes a structurally broken artifact. Raises MalformedArtifact on violation.
    """
    field = "seed_expansion"
    if not isinstance(data.get("round"), int):
        raise C.MalformedArtifact(f"{field}.round: expected integer")
    personas = data.get("personas")
    if not isinstance(personas, list) or not personas:
        raise C.MalformedArtifact(f"{field}.personas: at least one persona block required")
    for i, b in enumerate(personas):
        pf = f"{field}.personas[{i}]"
        if not isinstance(b.get("persona_id"), str):
            raise C.MalformedArtifact(f"{pf}.persona_id: required string")
        claude = b.get("claude")
        if not (isinstance(claude, dict) and isinstance(claude.get("interpret"), str)
                and isinstance(claude.get("act"), str)):
            raise C.MalformedArtifact(f"{pf}.claude: interpret/act strings required")
        if require_twin:
            tw = b.get("twin")
            if not (isinstance(tw, dict) and tw.get("engine") in SUPPORTED_TWIN_ENGINES
                    and tw.get("producer_status") in C.PRODUCER_STATUS):
                raise C.MalformedArtifact(f"{pf}.twin: supported engine + producer_status required")


def build_seed_expansion(project: Path, rnd: int, context: str,
                         cfg: dict[str, Any], timeout: int) -> Path:
    """Build the gated Phase-1 seed-expansion artifact (personas + twins expand the seeds).

    Writes `outputs/seed_expansion.json` = {round, personas:[...]} where each persona block
    carries Claude's expansion and (when codex) a twin sub-block in the same shape as
    commentary, so the gate can reuse the commentary twin-validation helper (Step 4c).
    """
    source = cfg.get("persona_source", "local")
    overrides = list(cfg.get("persona_overrides", []))
    use_twin = "codex" in _engines(cfg)
    resolved = [(pid, *resolve_persona(project, pid, source, overrides))
                for pid in cfg.get("personas", [])]

    def _block(pid: str, ppath: Path, rsource: str) -> dict[str, Any]:
        claude = _require_claude(
            invoke_persona("claude", pid, ppath, context, "seed", timeout),
            f"seed / {pid}",
        )
        twin = (_invoke_safe("codex", pid, ppath, context, "seed", timeout, retries=1)
                if use_twin else None)
        return _seed_block(pid, rsource, ppath, claude, twin, use_twin)

    jobs = [(lambda pid=pid, pp=pp, rs=rs: _block(pid, pp, rs)) for pid, pp, rs in resolved]
    blocks = _run_parallel(jobs, _max_workers(cfg))
    _record_twin_failures(project, blocks, "seed")
    data = {"round": rnd, "personas": blocks}
    _selfcheck_seed_expansion(data, use_twin)  # self-check (parity with commentary/proposals)
    out = project / "outputs" / "seed_expansion.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out, json.dumps(data, indent=2) + "\n")
    _check_breaker(project)  # halt if cumulative twin failures hit the threshold (3c)
    return out


def _dedupe_candidates(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop duplicate candidate_keys within a block (keep first) before writing."""
    seen: set[str] = set()
    out = []
    for c in cands:
        key = c.get("candidate_key")
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# --------------------------------------------------------------------------- producer lock
EMIT_BUSY_EXIT = 3   # the producer lock is held by another emit — refused to run (run-once);
# distinct from ContractError/OSError (1) and TwinHaltError (7).


class EmitBusyError(RuntimeError):
    """Another emit process already holds this project's producer lock (run-once enforcement)."""


@contextmanager
def _producer_lock(path: Path):
    """Serialize emit per project via a single advisory ``flock`` — the SOLE ownership arbiter.

    A second live emit fails ``LOCK_NB`` with ``EmitBusyError`` (the SKILL must wait, not
    relaunch — this is what removes the back-half thrash). A holder dying for ANY reason (normal
    exit, ContractError, TwinHaltError, SIGTERM, even SIGKILL) makes the OS close its fd and drop
    the flock, so the next ``LOCK_NB`` simply succeeds — there is NO stale lock to reconcile and
    NO PID-steal (which would introduce a TOCTOU). The PID record is written AFTER acquiring and
    is used only for the diagnostic message.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        try:
            held = path.read_text(errors="replace")[:200]
        except OSError:
            held = ""
        os.close(fd)
        raise EmitBusyError(
            f"another emit is already running for this project ({held or 'pid unknown'}); "
            f"not relaunching — wait for it to finish"
        ) from exc
    try:
        os.ftruncate(fd, 0)
        os.write(fd, json.dumps({"pid": os.getpid(), "start": int(time.time())}).encode())
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


# --------------------------------------------------------------------------- CLI
def _load_cfg(project: Path) -> dict[str, Any]:
    import verify_round  # reuse the single config reader
    cfg = verify_round.load_config(project)
    leg = cfg.get("claude_leg", "subprocess")
    if leg not in ("subprocess", "subagent"):
        raise C.ContractError(
            f"claude_leg must be 'subprocess' or 'subagent', got {leg!r}"
        )
    cfg["claude_leg"] = leg
    return cfg


def _active_hyps(project: Path, rnd: int) -> list[tuple[str, str]]:
    """Discover (hid, note_text) for hypotheses active in round `rnd` (reuses the gate's reader).

    Hypothesis ids must be unique within a round; a duplicate would silently collide on the
    per-hid commentary artifact (and merge in the batch), so fail loud instead.
    """
    import verify_round
    hyps: list[tuple[str, str]] = []
    seen: set[str] = set()
    for note_path, text, fm in verify_round.active_for_round(
        verify_round.iter_notes(project), rnd
    ):
        hid = fm.get("id", note_path.stem)
        if hid in seen:
            raise C.ContractError(
                f"duplicate active hypothesis id {hid!r} in round {rnd}; ids must be unique "
                f"(one commentary artifact per id)"
            )
        seen.add(hid)
        hyps.append((hid, text))
    return hyps


# --------------------------------------------------------------------------- subagent handoff
CLAUDE_LEGS_DIR = ".claude_legs"   # under outputs/ (gitignored): scaffolds + run-id records


def _scaffold_path(project: Path, phase: str, rnd: int) -> Path:
    """The atomic per-(phase, round) scaffold the `prompts` verb writes and `assemble` reads."""
    return project / "outputs" / CLAUDE_LEGS_DIR / f"{phase}_round{rnd}.json"


def _records_dir(project: Path, phase: str, rnd: int, run_id: str) -> Path:
    """The run-id-scoped records dir; run-id-unique, so a prior run's records cannot leak in."""
    return project / "outputs" / CLAUDE_LEGS_DIR / f"{phase}_round{rnd}.{run_id}"


def _build_scaffold(phase: str, project: Path, rnd: int, context: str,
                    cfg: dict[str, Any]) -> dict[str, Any]:
    """Freeze each persona's prompt + provenance for `phase`/`rnd` into a scaffold dict.

    The frozen prompt is the unit of truth: the SKILL feeds it to a persona subagent and
    `assemble` fires the Codex twin from it (no persona-file re-read). Commentary additionally
    freezes the active hyps (the twin's by_hid is shaped from these) and enforces the batch
    oversize guard, failing closed to the subprocess path.
    """
    source = cfg.get("persona_source", "local")
    overrides = list(cfg.get("persona_overrides", []))
    resolved = [(pid, *resolve_persona(project, pid, source, overrides))
                for pid in cfg.get("personas", [])]
    scaffold: dict[str, Any] = {
        "run_id": f"{os.getpid()}-{int(time.time())}",
        "round": rnd,
        "phase": phase,
    }
    if phase == "commentary":
        hyps = _active_hyps(project, rnd)
        total = sum(len(ctx) for _, ctx in hyps)
        cap = _batch_max_chars(cfg)
        if total > cap:
            raise C.ContractError(
                f"round {rnd} commentary batch too large ({total} > {cap} chars); "
                f"set claude_leg: subprocess or split the round"
            )
        scaffold["inputs"] = {"hyps": [[hid, ctx] for hid, ctx in hyps]}
        scaffold["personas"] = [
            {"persona_id": pid, "resolved_source": rs, "resolved_path": str(pp),
             "prompt": _commentary_batch_prompt(_persona_text(pp, pid), hyps)}
            for pid, pp, rs in resolved
        ]
    else:
        builder = _seed_prompt if phase == "seed" else _proposals_prompt
        ctx = context
        if phase == "proposals":  # fold in the already-tracked backlog so the panel avoids dupes
            existing = _existing_items_block(project)
            if existing:
                ctx = f"{context}\n\n{existing}"
        scaffold["personas"] = [
            {"persona_id": pid, "resolved_source": rs, "resolved_path": str(pp),
             "prompt": builder(_persona_text(pp, pid), ctx)}
            for pid, pp, rs in resolved
        ]
    return scaffold


def _emit_prompts(a: argparse.Namespace, project: Path) -> int:
    """`emit.py prompts <phase>`: freeze prompts + provenance into an atomic run-id scaffold.

    Read-only (no model call, no producer lock): writes the scaffold, then prints each persona's
    frozen prompt + the run_id + records dir so the SKILL can spawn subagents and place records.
    """
    phase = a.phase
    if phase not in ("seed", "commentary", "proposals"):
        print("prompts mode requires a phase: seed|commentary|proposals", file=sys.stderr)
        return 1
    cfg = _load_cfg(project)
    context = a.context
    if context.startswith("@"):
        context = Path(context[1:]).read_text(encoding="utf-8")
    try:
        scaffold = _build_scaffold(phase, project, a.round, context, cfg)
        path = _scaffold_path(project, phase, a.round)
        path.parent.mkdir(parents=True, exist_ok=True)
        C.atomic_write(path, json.dumps(scaffold, indent=2) + "\n")
    except (C.ContractError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    records = _records_dir(project, phase, a.round, scaffold["run_id"])
    print(f"scaffold {path}")
    print(f"run_id {scaffold['run_id']}")
    print(f"records_dir {records}")
    for p in scaffold["personas"]:
        print(f"--- persona {p['persona_id']} ---")
        print(p["prompt"])
    return 0


# --------------------------------------------------------------------------- assemble
def _normalize_seed_leg(text: str | None) -> dict[str, Any]:
    """A handed-off seed/commentary-style Claude record -> explicit producer_status (fact-11).

    Missing/empty -> 'unavailable'; otherwise the SAME two-paragraph parse the subprocess path
    uses, marked 'ok'. The required-Claude check then rejects an empty interpret/act.
    """
    if not (text and text.strip()):
        return {"producer_status": "unavailable"}
    return {"producer_status": "ok", **_parse_seed_record(text)}


def _normalize_commentary_leg(text: str | None, hyps: list[tuple[str, str]]) -> dict[str, Any]:
    """A handed-off batched-commentary record -> {producer_status, by_hid} (fact-11)."""
    if not (text and text.strip()):
        return {"producer_status": "unavailable", "by_hid": {}}
    return {"producer_status": "ok", "by_hid": _parse_commentary_record(text, hyps)}


def _normalize_proposals_leg(text: str | None) -> dict[str, Any]:
    """A handed-off proposals record -> {producer_status, candidates, reprioritize} (fact-11).

    Unparseable JSON in a present record is a real failure (strict parse) -> 'unavailable',
    NOT empty candidates — mirroring the subprocess strict=(status=='ok') parse.
    """
    if not (text and text.strip()):
        return {"producer_status": "unavailable", "candidates": [], "reprioritize": []}
    try:
        payload = _parse_proposals_record(text, strict=True)
    except C.ContractError:
        return {"producer_status": "unavailable", "candidates": [], "reprioritize": []}
    return {"producer_status": "ok", **payload}


def _validate_scaffold(scaffold: Any, phase: str, rnd: int, cfg: dict[str, Any]) -> None:
    """Identity-validate the scaffold BEFORE any twin or write (fact-2, fact-11).

    Round + phase must match the invocation; the ordered persona-id list must equal the config
    (set AND order); every persona must carry frozen provenance + prompt. Any mismatch, a torn
    scaffold, or a malformed entry shape raises ContractError (never an uncaught AttributeError/
    IndexError) so no artifact is produced from a foreign/stale/garbled handoff.
    """
    if not isinstance(scaffold, dict):
        raise C.ContractError("assemble scaffold is not a JSON object")
    if scaffold.get("round") != rnd:
        raise C.ContractError(f"scaffold round {scaffold.get('round')!r} != --round {rnd}")
    if scaffold.get("phase") != phase:
        raise C.ContractError(f"scaffold phase {scaffold.get('phase')!r} != {phase!r}")
    if not (isinstance(scaffold.get("run_id"), str) and scaffold["run_id"]):
        raise C.ContractError("scaffold missing a non-empty run_id")
    personas = scaffold.get("personas")
    if not (isinstance(personas, list) and all(isinstance(p, dict) for p in personas)):
        raise C.ContractError("scaffold personas missing or malformed")
    ordered = [p.get("persona_id") for p in personas]
    expected = list(cfg.get("personas", []))
    if ordered != expected:
        raise C.ContractError(f"scaffold personas {ordered} != config personas {expected}")
    for p in personas:
        if not (p.get("resolved_source") and p.get("resolved_path") and p.get("prompt")):
            raise C.ContractError(
                f"scaffold persona {p.get('persona_id')!r} missing provenance or prompt"
            )
    if phase == "commentary":
        hyps = (scaffold.get("inputs") or {}).get("hyps")
        if not (isinstance(hyps, list)
                and all(isinstance(h, (list, tuple)) and len(h) == 2 for h in hyps)):
            raise C.ContractError(
                "commentary scaffold inputs.hyps malformed (need [hid, ctx] pairs)"
            )


def assemble_seed(project: Path, scaffold: dict[str, Any], claude_texts: dict[str, str | None],
                  cfg: dict[str, Any], timeout: int) -> Path:
    """Assemble seed_expansion.json from handed-off Claude legs + freshly fired Codex twins."""
    rnd = scaffold["round"]
    use_twin = "codex" in _engines(cfg)
    # 1+2: normalize + REQUIRE each Claude leg (R1) before any twin call or write.
    claude_by_pid = {p["persona_id"]: _require_claude(
        _normalize_seed_leg(claude_texts.get(p["persona_id"])), f"seed / {p['persona_id']}")
        for p in scaffold["personas"]}
    # 3: fire ONLY Codex twins, from the frozen prompt (no persona-file re-read, no claude leg).
    twin_by_pid: dict[str, Any] = {}
    if use_twin:
        jobs = [(lambda p=p: _invoke_safe("codex", p["persona_id"], Path(p["resolved_path"]),
                                          "", "seed", timeout, retries=1, prompt=p["prompt"]))
                for p in scaffold["personas"]]
        twin_by_pid = dict(zip([p["persona_id"] for p in scaffold["personas"]],
                               _run_parallel(jobs, _max_workers(cfg)), strict=True))
    # 4: pair via the shared shaper, in persona order.
    blocks = [
        _seed_block(p["persona_id"], p["resolved_source"], Path(p["resolved_path"]),
                    claude_by_pid[p["persona_id"]],
                    twin_by_pid.get(p["persona_id"]) if use_twin else None, use_twin)
        for p in scaffold["personas"]
    ]
    _record_twin_failures(project, blocks, "seed")
    data = {"round": rnd, "personas": blocks}
    _selfcheck_seed_expansion(data, use_twin)
    out = project / "outputs" / "seed_expansion.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out, json.dumps(data, indent=2) + "\n")
    _check_breaker(project)
    return out


def assemble_commentary(project: Path, scaffold: dict[str, Any],
                        claude_texts: dict[str, str | None], cfg: dict[str, Any],
                        timeout: int) -> list[Path]:
    """Assemble per-hid commentary.json from handed-off Claude legs + fired Codex twins."""
    rnd = scaffold["round"]
    use_twin = "codex" in _engines(cfg)
    hyps = [(h[0], h[1]) for h in scaffold["inputs"]["hyps"]]
    # 1+2: normalize + REQUIRE each Claude leg (R1): non-ok status OR any missing/empty hid fails.
    claude_by_pid: dict[str, Any] = {}
    for p in scaffold["personas"]:
        pid = p["persona_id"]
        rec = _require_claude(_normalize_commentary_leg(claude_texts.get(pid), hyps),
                              f"commentary batch / {pid}")
        for hid, _ in hyps:
            e = rec["by_hid"].get(hid)
            if not (e and (e.get("interpret") or e.get("act"))):
                raise C.ContractError(
                    f"required Claude commentary for {hid} / {pid} missing or empty"
                )
        claude_by_pid[pid] = rec
    # 3: fire ONLY Codex twins from the frozen prompt; twin-health bumps ONCE per persona.
    twin_by_pid: dict[str, Any] = {}
    if use_twin:
        jobs = [(lambda p=p: _invoke_safe_batch(
                    "codex", p["persona_id"], Path(p["resolved_path"]), hyps, timeout,
                    retries=1, prompt=p["prompt"]))
                for p in scaffold["personas"]]
        twin_by_pid = dict(zip([p["persona_id"] for p in scaffold["personas"]],
                               _run_parallel(jobs, _max_workers(cfg)), strict=True))
        for p in scaffold["personas"]:
            tr = twin_by_pid.get(p["persona_id"])
            if tr and tr.get("producer_status") != "ok":
                _bump_twin_health(project, "codex", p["persona_id"], "commentary",
                                  tr.get("producer_status", "unavailable"))
    # 4: pair via the shared shaper (byte-identical to build_commentary_batch).
    out_paths: list[Path] = []
    for hid, _ctx in hyps:
        blocks = []
        for p in scaffold["personas"]:
            pid = p["persona_id"]
            cr = claude_by_pid[pid]["by_hid"][hid]
            trec = twin_by_pid.get(pid) if use_twin else None
            blocks.append(_commentary_block(pid, p["resolved_source"],
                                            Path(p["resolved_path"]), cr, trec, hid, use_twin))
        data = {"round": rnd, "hypothesis_id": hid, "personas": blocks}
        out = project / "outputs" / "commentary" / f"round{rnd}" / f"{hid}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        C.atomic_write(out, json.dumps(data, indent=2) + "\n")
        C.load_commentary(out)
        out_paths.append(out)
    _check_breaker(project)
    return out_paths


def assemble_proposals(project: Path, scaffold: dict[str, Any],
                       claude_texts: dict[str, str | None], cfg: dict[str, Any],
                       timeout: int) -> Path:
    """Assemble proposals.json: handed-off Claude block/persona + fired Codex twin/persona."""
    rnd = scaffold["round"]
    engines = _engines(cfg)
    # 1+2: normalize + REQUIRE each Claude leg (status-only for proposals) before any twin/write.
    claude_by_pid = {p["persona_id"]: _require_claude(
        _normalize_proposals_leg(claude_texts.get(p["persona_id"])),
        f"proposals / {p['persona_id']}") for p in scaffold["personas"]}
    # 3: fire ONLY Codex twins from the frozen prompt.
    twin_by_pid: dict[str, Any] = {}
    if "codex" in engines:
        jobs = [(lambda p=p: _invoke_safe("codex", p["persona_id"], Path(p["resolved_path"]),
                                          "", "proposals", timeout, retries=1, prompt=p["prompt"]))
                for p in scaffold["personas"]]
        twin_by_pid = dict(zip([p["persona_id"] for p in scaffold["personas"]],
                               _run_parallel(jobs, _max_workers(cfg)), strict=True))
    # 4: shape blocks per persona, engine-inner (parity with build_proposals ordering).
    blocks = []
    for p in scaffold["personas"]:
        pid = p["persona_id"]
        for engine in engines:
            rec = (claude_by_pid[pid] if engine == "claude"
                   else twin_by_pid.get(pid, {"producer_status": "unavailable"}))
            blocks.append(_proposals_block(pid, engine, p["resolved_source"],
                                           Path(p["resolved_path"]), rec))
    for b in blocks:
        if b["engine"] in SUPPORTED_TWIN_ENGINES and b["producer_status"] != "ok":
            _bump_twin_health(project, b["engine"], b["persona_id"], "proposals",
                              b["producer_status"])
    data = {"round": rnd, "blocks": blocks}
    out = project / "outputs" / "proposals" / f"round{rnd}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    C.atomic_write(out, json.dumps(data, indent=2) + "\n")
    C.load_proposals(out)
    _check_breaker(project)
    return out


def _assemble_phase(a: argparse.Namespace, project: Path, cfg: dict[str, Any]) -> list[Path]:
    """I/O boundary for `assemble`: read the scaffold + run-id records, then call the assembler.

    Reads the frozen scaffold (``--claude-legs`` path, default the deterministic location), then
    each persona's verbatim record from the run-id-scoped dir — so a prior run's records cannot
    leak in (freshness). The assembler functions stay file-free + injectable for unit tests.
    """
    phase = a.phase
    if phase not in ("seed", "commentary", "proposals"):
        raise C.ContractError("assemble mode requires a phase: seed|commentary|proposals")
    arg = a.claude_legs
    scaffold_path = (Path(arg[1:] if arg.startswith("@") else arg) if arg
                     else _scaffold_path(project, phase, a.round))
    try:
        scaffold = json.loads(scaffold_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise C.ContractError(f"unreadable/torn assemble scaffold {scaffold_path}: {exc}") from exc
    _validate_scaffold(scaffold, phase, a.round, cfg)
    records = _records_dir(project, phase, a.round, scaffold["run_id"])
    claude_texts: dict[str, str | None] = {}
    for p in scaffold["personas"]:
        rec_path = records / f"{p['persona_id']}.txt"
        claude_texts[p["persona_id"]] = (
            rec_path.read_text(encoding="utf-8") if rec_path.is_file() else None
        )
    if phase == "commentary":
        return assemble_commentary(project, scaffold, claude_texts, cfg, a.timeout)
    if phase == "seed":
        return [assemble_seed(project, scaffold, claude_texts, cfg, a.timeout)]
    return [assemble_proposals(project, scaffold, claude_texts, cfg, a.timeout)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="emit seed/commentary/proposals artifacts")
    ap.add_argument("mode", choices=("seed", "commentary", "proposals", "prompts", "assemble"))
    ap.add_argument("phase", nargs="?", choices=("seed", "commentary", "proposals"),
                    default=None, help="phase for the prompts/assemble verbs")
    ap.add_argument("--round", type=int, required=True)
    ap.add_argument("--project", default=".")
    ap.add_argument("--hypothesis", help="hypothesis id (commentary mode)")
    ap.add_argument("--context", default="", help="finding/round/seed context text or @file")
    ap.add_argument("--claude-legs", default=None,
                    help="assemble: scaffold path (@file or bare); default the deterministic one")
    ap.add_argument("--timeout", type=int, default=int(os.environ.get("CODEX_TIMEOUT", "300")))
    a = ap.parse_args(argv)
    project = Path(a.project).resolve()
    if a.mode == "prompts":
        return _emit_prompts(a, project)  # read-only: freeze the scaffold OUTSIDE the lock
    # One emit per project at a time: the lock removes the back-half relaunch thrash (run-once).
    try:
        with _producer_lock(project / "outputs" / ".emit.lock"):
            return _dispatch(a, project)
    except EmitBusyError as exc:
        print(str(exc), file=sys.stderr)
        return EMIT_BUSY_EXIT


def _dispatch(a: argparse.Namespace, project: Path) -> int:
    """Run the requested producer/assembler (under the held lock); map failures to exit codes."""
    cfg = _load_cfg(project)
    leg = cfg.get("claude_leg", "subprocess")
    context = a.context
    if context.startswith("@"):
        context = Path(context[1:]).read_text(encoding="utf-8")
    try:
        if a.mode == "assemble":
            # Fail-closed: assemble pairs handed-off Claude legs; it must not run as a producer.
            if leg != "subagent":
                raise C.ContractError(
                    "emit.py assemble requires claude_leg: subagent in research_loop.yml"
                )
            outs = _assemble_phase(a, project, cfg)
        elif leg == "subagent":
            # Fail-closed: a subprocess producer must never silently run `claude -p` under subagent.
            raise C.ContractError(
                f"emit.py {a.mode} cannot run a subprocess Claude leg under claude_leg: "
                f"subagent; use `prompts {a.mode}` + persona subagents + `assemble {a.mode}`"
            )
        elif a.mode == "commentary" and not a.hypothesis:
            # No --hypothesis: cover ALL active hypotheses for the round in one process.
            # commentary_batch (default true) -> one batched call per persona/engine (R5);
            # false -> isolated per-hypothesis calls: personas run in parallel within each call,
            #          but the hypotheses run serially (the isolation/cost tradeoff; true = fast).
            hyps = _active_hyps(project, a.round)
            if cfg.get("commentary_batch", True):
                outs = build_commentary_batch(project, a.round, hyps, cfg, a.timeout)
            else:
                outs = [build_commentary(project, a.round, hid, ctx, cfg, a.timeout)
                        for hid, ctx in hyps]
        elif a.mode == "commentary":
            outs = [build_commentary(project, a.round, a.hypothesis, context, cfg, a.timeout)]
        elif a.mode == "seed":
            outs = [build_seed_expansion(project, a.round, context, cfg, a.timeout)]
        else:
            outs = [build_proposals(project, a.round, context, cfg, a.timeout)]
    except TwinHaltError as exc:
        print(str(exc), file=sys.stderr)
        return TWIN_HALT_EXIT
    except (C.ContractError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    for out in outs:
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
