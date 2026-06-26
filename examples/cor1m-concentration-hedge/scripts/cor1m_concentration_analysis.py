#!/usr/bin/env python3
"""COR1M over-bulled flag — hedge-trigger lead (H-COR-002) & concentration validity (H-COR-001).

Question: does the LOW tail of COR1M (over-bulled / extreme single-name concentration,
primary COR1M < 8) precede worse forward outcomes in SPY/QQQ (the hedge-trigger test,
H-COR-002), and is the penalty *concentration-specific* — heavier in the more
concentrated Nasdaq (QQQ) than in the broad S&P (SPY) — which is the read on whether
COR1M is measuring concentration at all (H-COR-001)?

Note (facts reconciliation, 2026-06-17): the hedge-trigger universe is SPY + QQQ only
(fact-6); IWM is out of scope, so the concentration-specificity test uses the WEAKER
QQQ-vs-SPY contrast (both are megacap-heavy) rather than the original QQQ/SPY-vs-IWM
control. This is a known limitation (plan.md Risk #2) — expect H-COR-001 to land weak/
inconclusive and to propose re-admitting IWM as a control-only series in Phase 8.

Signal  : COR1M[t] (Cboe 1-month implied correlation), options-derived.
Triggers: abs8   = COR1M < 8 (SpotGamma 'certain risk flag') — FIXED seed level (fact-5)
          pctile = COR1M <= 10th pct of trailing 252d (robustness only, not the seed)
Outcomes (realized, NON-circular — pure price path, no options inputs), per ETF, at
horizons H in {5, 10, 21, 42} trading days (fact-7), measured from day t's close:
          path-min drawdown = min(close[t+1..t+H]) / close[t] - 1
          breach            = 1 if path-min <= -5%
          fwd return        = close[t+H] / close[t] - 1
Scoring (fact-8): forward max drawdown AND hit-rate/precision vs the unconditional base
rate (precision = P(breach | trigger); base rate = P(breach) over all valid days; lift =
precision / base rate). Compare TRIGGERED days vs the NON-TRIGGERED baseline.

Clustering: COR1M<8 days cluster into a few episodes with OVERLAPPING forward windows,
so day-level significance is overstated (Quant guardrail). We therefore report:
  (a) day-level triggered-vs-baseline means,
  (b) EPISODE-level means (one obs per episode = its first trigger day), and
  (c) a moving-block bootstrap p-value (block length = H) for the 21d drawdown spread.

H-COR-002 PASS: at 21d (abs8), triggered is worse than baseline on BOTH deeper mean
  path-min drawdown AND higher -5% breach rate, in BOTH SPY and QQQ.
H-COR-001 PASS: at 21d (abs8), the triggered-vs-baseline drawdown GAP is larger in QQQ
  than in SPY (concentration-specific — heavier where concentration is higher). WEAK
  contrast without IWM; treat a pass as suggestive, not confirmatory.

Backlinks (research_loop):
- Goal facts : goals/cor1m-concentration-hedge/facts.md (H-COR-001, H-COR-002)
- Plan       : goals/cor1m-concentration-hedge/plan.md (Steps 2-4)
- Data       : data/cor1m.csv, data/{spy,qqq}_ohlc.csv (scripts/fetch_market_data.py)

Usage: python cor1m_concentration_analysis.py   ->  outputs/cor1m_concentration_results.txt
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

INSTRUMENTS = ["spy", "qqq"]
HORIZONS = [5, 10, 21, 42]
ABS_THRESHOLD = 8.0
PCTILE_WINDOW = 252
PCTILE_Q = 0.10
BREACH = -0.05
EPISODE_GAP = 5          # >5 calm days between trigger days starts a new episode
BOOT_N = 5000
SEED = 12345             # fixed -> byte-stable output


def load() -> pd.DataFrame:
    cor = pd.read_csv(DATA / "cor1m.csv", comment="#", parse_dates=["date"])
    df = cor[["date", "cor1m"]].copy()
    for name in INSTRUMENTS:
        etf = pd.read_csv(DATA / f"{name}_ohlc.csv", comment="#", parse_dates=["date"])
        df = df.merge(etf[["date", "close"]].rename(columns={"close": name}), on="date", how="inner")
    return df.sort_values("date").reset_index(drop=True)


def forward_metrics(close: np.ndarray, h: int) -> tuple[np.ndarray, np.ndarray]:
    """path-min drawdown and forward total return over the next h closes (NaN if truncated)."""
    n = len(close)
    pmin = np.full(n, np.nan)
    fret = np.full(n, np.nan)
    for i in range(n):
        if i + h >= n:
            continue
        window = close[i + 1: i + 1 + h]
        pmin[i] = window.min() / close[i] - 1.0
        fret[i] = close[i + h] / close[i] - 1.0
    return pmin, fret


def episode_ids(mask: np.ndarray) -> np.ndarray:
    """Label contiguous trigger episodes; -1 where not triggered. New episode if >EPISODE_GAP apart."""
    ids = np.full(len(mask), -1)
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return ids
    ep = 0
    prev = idx[0]
    ids[idx[0]] = 0
    for i in idx[1:]:
        if i - prev > EPISODE_GAP:
            ep += 1
        ids[i] = ep
        prev = i
    return ids


def block_bootstrap_p(pmin: np.ndarray, trig_mask: np.ndarray, h: int, rng) -> float:
    """One-sided p that triggered mean drawdown <= baseline by chance, via moving-block resample.

    Null: trigger timing carries no information. We draw, with replacement, contiguous blocks
    of length h (matching the forward-window overlap) to assemble a surrogate series the size of
    the triggered set, and compare its mean to the baseline mean. p = P(surrogate mean <= observed
    triggered mean). Block length = h keeps the autocorrelation the overlap induces.
    """
    valid = ~np.isnan(pmin)
    series = pmin[valid]
    trig = pmin[valid & trig_mask]
    if len(trig) == 0 or len(series) <= h:
        return float("nan")
    observed = np.nanmean(trig)
    n_blocks = int(np.ceil(len(trig) / h))
    max_start = len(series) - h
    surrogate_means = np.empty(BOOT_N)
    for b in range(BOOT_N):
        starts = rng.integers(0, max_start + 1, size=n_blocks)
        sample = np.concatenate([series[s:s + h] for s in starts])[:len(trig)]
        surrogate_means[b] = sample.mean()
    return float((surrogate_means <= observed).mean())


def fmt_pct(x: float) -> str:
    return "  nan  " if (x is None or (isinstance(x, float) and np.isnan(x))) else f"{x:+7.2%}"


def main() -> int:
    df = load()
    rng = np.random.default_rng(SEED)
    n = len(df)

    # Triggers (computed once; same trigger applies to every instrument).
    cor = df["cor1m"].to_numpy()
    abs8 = cor < ABS_THRESHOLD
    roll_q = df["cor1m"].rolling(PCTILE_WINDOW, min_periods=PCTILE_WINDOW).quantile(PCTILE_Q).to_numpy()
    pctile = cor <= roll_q          # NaN during warm-up -> comparison False
    triggers = {"abs8": abs8, "pctile": pctile}

    L = []
    P = L.append
    P("COR1M OVER-BULLED CONCENTRATION FLAG AS A HEDGE TRIGGER")
    P("H-COR-002 (trigger lead) & H-COR-001 (concentration specificity, QQQ-vs-SPY)")
    P("=" * 70)
    P(f"Data: real Cboe COR1M + Yahoo SPY/QQQ. Window {df['date'].min():%Y-%m-%d} -> "
      f"{df['date'].max():%Y-%m-%d}  (N={n} aligned days)")
    P(f"Triggers: abs8 = COR1M < {ABS_THRESHOLD:g}; pctile = COR1M <= {PCTILE_Q:.0%} of trailing "
      f"{PCTILE_WINDOW}d. Breach = path-min <= {BREACH:.0%}.")
    P("Outcomes are realized ETF price paths (no options inputs) -> NON-CIRCULAR.")
    P("")

    # Episode accounting for the primary trigger.
    eids = episode_ids(abs8)
    n_days = int(abs8.sum())
    n_eps = int(eids.max() + 1) if n_days else 0
    first_days = [int(np.where(eids == e)[0][0]) for e in range(n_eps)]
    P(f"Primary trigger episodes (abs8): {n_days} trigger-days in {n_eps} distinct episodes "
      f"(>{EPISODE_GAP} calm days apart). Episode-level N = {n_eps}.")
    P("Episode start dates: " + ", ".join(df['date'].iloc[first_days].dt.strftime('%Y-%m-%d')))
    P("")

    # Precompute forward metrics per instrument/horizon.
    fwd = {name: {h: forward_metrics(df[name].to_numpy(), h) for h in HORIZONS} for name in INSTRUMENTS}

    gaps_21_abs8: dict[str, float] = {}

    for tname, tmask in triggers.items():
        P("#" * 70)
        P(f"TRIGGER = {tname}   (triggered days with a full forward window vary by horizon)")
        P("#" * 70)
        for h in HORIZONS:
            P(f"\n--- horizon {h}d ---")
            P(f"{'inst':4s} | {'grp':8s} | {'N':>5s} | {'mean pmin dd':>12s} | "
              f"{'breach -5%':>10s} | {'mean fwd ret':>12s}")
            P("-" * 70)
            for name in INSTRUMENTS:
                pmin, fret = fwd[name][h]
                valid = ~np.isnan(pmin)
                tmsk = valid & tmask
                bmsk = valid & ~tmask
                for grp, m in (("trigger", tmsk), ("baseline", bmsk)):
                    nn = int(m.sum())
                    dd = float(np.nanmean(pmin[m])) if nn else float("nan")
                    br = float((pmin[m] <= BREACH).mean()) if nn else float("nan")
                    rr = float(np.nanmean(fret[m])) if nn else float("nan")
                    P(f"{name:4s} | {grp:8s} | {nn:5d} | {fmt_pct(dd):>12s} | "
                      f"{fmt_pct(br):>10s} | {fmt_pct(rr):>12s}")

                # episode-level (abs8 only): first day of each episode as one independent event
                if tname == "abs8":
                    ep_idx = [d for d in first_days if valid[d]]
                    ep_dd = float(np.nanmean(pmin[ep_idx])) if ep_idx else float("nan")
                    ep_br = float((pmin[ep_idx] <= BREACH).mean()) if ep_idx else float("nan")
                    P(f"{name:4s} | {'EPISODE':8s} | {len(ep_idx):5d} | {fmt_pct(ep_dd):>12s} | "
                      f"{fmt_pct(ep_br):>10s} | {'(entry-day events)':>12s}")
                P("-" * 70)

            # bootstrap p-values + gaps at the primary horizon/trigger
            if tname == "abs8" and h == 21:
                P("\nClustering-robust check (abs8, 21d): moving-block bootstrap p that triggered")
                P(f"mean drawdown <= baseline by chance (block len = {21}, {BOOT_N} resamples):")
                for name in INSTRUMENTS:
                    pmin, _ = fwd[name][21]
                    valid = ~np.isnan(pmin)
                    pval = block_bootstrap_p(pmin, tmask & valid, 21, rng)
                    dd_t = float(np.nanmean(pmin[valid & tmask]))
                    dd_b = float(np.nanmean(pmin[valid & ~tmask]))
                    gaps_21_abs8[name] = dd_b - dd_t   # >0 means triggered drawdowns are deeper
                    P(f"  {name:4s}: triggered {dd_t:+.2%} vs baseline {dd_b:+.2%}  "
                      f"gap={dd_b - dd_t:+.2%}  block-bootstrap p={pval:.3f}")

                # Hit-rate / precision vs the unconditional base rate (fact-8).
                P("\nHit-rate / precision vs base rate (abs8, 21d): does the flag concentrate")
                P("-5% breaches above the unconditional rate? precision=P(breach|trigger), "
                  "base=P(breach):")
                for name in INSTRUMENTS:
                    pmin, _ = fwd[name][21]
                    valid = ~np.isnan(pmin)
                    breach_all = pmin[valid] <= BREACH
                    breach_trig = pmin[valid & tmask] <= BREACH
                    base = float(breach_all.mean()) if valid.sum() else float("nan")
                    prec = float(breach_trig.mean()) if (valid & tmask).sum() else float("nan")
                    lift = prec / base if base else float("nan")
                    P(f"  {name:4s}: precision={prec:+.2%}  base_rate={base:+.2%}  "
                      f"lift={lift:.2f}x  (n_trig={int((valid & tmask).sum())})")

    # ---- Verdicts -------------------------------------------------------------
    P("\n" + "=" * 70)
    P("VERDICT CHECKS")
    P("=" * 70)

    # H-COR-002 (trigger lead): at 21d abs8, triggered worse than baseline on dd AND breach
    # in BOTH SPY and QQQ.
    worse = []
    for name in INSTRUMENTS:
        pmin, _ = fwd[name][21]
        valid = ~np.isnan(pmin)
        t = pmin[valid & abs8]; b = pmin[valid & ~abs8]
        dd_worse = np.nanmean(t) < np.nanmean(b)
        br_worse = (t <= BREACH).mean() > (b <= BREACH).mean()
        ok = bool(dd_worse and br_worse)
        worse.append(ok)
        P(f"  H-COR-002 {name}: deeper dd={dd_worse}, higher breach={br_worse} -> {'worse' if ok else 'not worse'}")
    h2_pass = sum(worse) == len(INSTRUMENTS)
    P(f"H-COR-002 PASS/FAIL: {'PASS' if h2_pass else 'FAIL'} "
      f"(triggered worse than baseline in {sum(worse)}/{len(INSTRUMENTS)} instruments at 21d; need all)")

    # H-COR-001 (concentration specificity): QQQ gap exceeds SPY gap (heavier where
    # concentration is higher). WEAK contrast without IWM (plan.md Risk #2).
    g_spy, g_qqq = gaps_21_abs8["spy"], gaps_21_abs8["qqq"]
    h1_pass = g_qqq > g_spy
    P("")
    P(f"  H-COR-001 gaps (baseline-minus-triggered dd; larger = trigger hurts more): "
      f"QQQ={g_qqq:+.2%}, SPY={g_spy:+.2%}")
    P(f"H-COR-001 PASS/FAIL: {'PASS' if h1_pass else 'FAIL'} "
      f"(concentration-specific iff QQQ gap exceeds SPY gap; WEAK contrast without IWM)")

    OUT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(L) + "\n"
    (OUT / "cor1m_concentration_results.txt").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
