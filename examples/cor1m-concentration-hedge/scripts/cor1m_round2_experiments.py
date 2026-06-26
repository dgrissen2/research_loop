#!/usr/bin/env python3
"""Round 2 experiments for the COR1M concentration-hedge program.

E-COR-006  Episode-level robustness: leave-one-episode-out (LOO) on the 21d triggered-vs-baseline
           drawdown gap, and a threshold-sensitivity sweep over COR1M in {6,7,8,9,10}. Is `< 8`
           a structural level or a selected knife-edge / single-episode artifact?
E-COR-002  Low-VIX confound: does COR1M < 8 add forward-drawdown information beyond simply-low VIX?
           (a) conditional comparison within the low-VIX regime; (b) manual OLS of 21d path-min
           drawdown on the trigger dummy + VIX level — does the trigger coefficient survive?
E-COR-003  Hedge P&L (stylized, net of cost): at each EPISODE-ENTRY trigger, buy a 21d ATM protective
           put (premium from a Black-Scholes approximation using VIX as sigma). Compare hedged vs
           unhedged 21d outcome, net of premium. Does acting on the flag beat doing nothing?

Inference unit is the EPISODE (entry day) wherever overlap matters — round 1 showed 39 trigger days
collapse to ~9 episodes with overlapping 21d windows.

Backlinks: goals/cor1m-concentration-hedge/facts.md ; plan.md Step 7 ; parent note
hypothesis_tracking/h-cor-001_cor1m_overbulled_lead_2026-06-03.md
Usage: python cor1m_round2_experiments.py  ->  outputs/cor1m_round2_results.txt
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

INSTRUMENTS = ["spy", "iwm", "qqq"]
H = 21
ABS_THRESHOLD = 8.0
BREACH = -0.05
EPISODE_GAP = 5
SWEEP = [6.0, 7.0, 8.0, 9.0, 10.0]
SEED = 12345


def load() -> pd.DataFrame:
    cor = pd.read_csv(DATA / "cor1m.csv", comment="#", parse_dates=["date"])
    vix = pd.read_csv(DATA / "vix_ohlc.csv", comment="#", parse_dates=["date"])[["date", "close"]]
    df = cor[["date", "cor1m"]].merge(vix.rename(columns={"close": "vix"}), on="date", how="inner")
    for name in INSTRUMENTS:
        etf = pd.read_csv(DATA / f"{name}_ohlc.csv", comment="#", parse_dates=["date"])
        df = df.merge(etf[["date", "close"]].rename(columns={"close": name}), on="date", how="inner")
    return df.sort_values("date").reset_index(drop=True)


def path_min(close: np.ndarray, h: int) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    for i in range(n):
        if i + h < n:
            out[i] = close[i + 1: i + 1 + h].min() / close[i] - 1.0
    return out


def fwd_ret(close: np.ndarray, h: int) -> np.ndarray:
    n = len(close)
    out = np.full(n, np.nan)
    for i in range(n):
        if i + h < n:
            out[i] = close[i + h] / close[i] - 1.0
    return out


def episode_first_days(mask: np.ndarray) -> list[int]:
    idx = np.where(mask)[0]
    if len(idx) == 0:
        return []
    firsts = [int(idx[0])]
    prev = idx[0]
    for i in idx[1:]:
        if i - prev > EPISODE_GAP:
            firsts.append(int(i))
        prev = i
    return firsts


def ols(X: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Plain normal-equations OLS; X includes an intercept column."""
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    return beta


def main() -> int:
    df = load()
    rng = np.random.default_rng(SEED)
    cor = df["cor1m"].to_numpy()
    vix = df["vix"].to_numpy()
    abs8 = cor < ABS_THRESHOLD

    pmin = {n: path_min(df[n].to_numpy(), H) for n in INSTRUMENTS}
    fret = {n: fwd_ret(df[n].to_numpy(), H) for n in INSTRUMENTS}

    L: list[str] = []
    P = L.append
    P("COR1M CONCENTRATION-HEDGE — ROUND 2 EXPERIMENTS (E-COR-006, E-COR-002, E-COR-003)")
    P("=" * 78)
    P(f"Data {df['date'].min():%Y-%m-%d}->{df['date'].max():%Y-%m-%d}  N={len(df)}  horizon={H}d")
    P("")

    # ===================== E-COR-006: episode LOO + threshold sweep =====================
    P("#" * 78)
    P("E-COR-006  Episode-level robustness (leave-one-episode-out + threshold sweep)")
    P("#" * 78)
    firsts = episode_first_days(abs8)
    firsts = [d for d in firsts if not np.isnan(pmin["qqq"][d])]
    P(f"Episodes with a full {H}d forward window: {len(firsts)}  "
      f"(dates: {', '.join(df['date'].iloc[firsts].dt.strftime('%Y-%m-%d'))})")
    P("")
    P("Leave-one-episode-out: QQQ & SPY mean EPISODE-ENTRY path-min drawdown, dropping each episode.")
    for name in ("qqq", "spy"):
        vals = np.array([pmin[name][d] for d in firsts])
        full = vals.mean()
        P(f"  {name.upper()} full episode mean dd = {full:+.2%}")
        loo = []
        for j, d in enumerate(firsts):
            keep = np.delete(vals, j)
            loo.append((df['date'].iloc[d].strftime('%Y-%m-%d'), keep.mean()))
        worst = max(loo, key=lambda x: x[1])   # dropping which episode most weakens (raises) the dd
        best = min(loo, key=lambda x: x[1])
        P(f"    drop {worst[0]} -> {worst[1]:+.2%} (effect weakest without it); "
          f"drop {best[0]} -> {best[1]:+.2%} (strongest)")
        swing = worst[1] - best[1]
        P(f"    LOO swing = {swing:.2%}  -> {'FRAGILE: one episode dominates' if swing > abs(full) else 'no single episode dominates'}")
    P("")
    P("Threshold sweep (COR1M < x): QQQ 21d triggered mean dd, baseline, gap, episode count")
    P(f"  {'x':>3s} | {'trig N':>6s} | {'eps':>3s} | {'trig dd':>8s} | {'base dd':>8s} | {'gap':>7s}")
    for x in SWEEP:
        m = cor < x
        valid = ~np.isnan(pmin["qqq"])
        t = pmin["qqq"][valid & m]
        b = pmin["qqq"][valid & ~m]
        eps = len(episode_first_days(m))
        P(f"  {x:3.0f} | {len(t):6d} | {eps:3d} | {t.mean():+8.2%} | {b.mean():+8.2%} | {b.mean() - t.mean():+7.2%}")
    P("  Read: a smooth monotone gap as x falls = structural; a spike only at x=8 = knife-edge.")
    P("")

    # ===================== E-COR-002: low-VIX confound =====================
    P("#" * 78)
    P("E-COR-002  Does COR1M < 8 add forward-drawdown info beyond low VIX?")
    P("#" * 78)
    valid = ~np.isnan(pmin["qqq"])
    vix_low_thresh = np.nanquantile(vix[valid], 0.33)
    low_vix = vix <= vix_low_thresh
    P(f"Low-VIX regime = VIX <= 33rd pctile ({vix_low_thresh:.1f}).  "
      f"Conditional comparison within low-VIX days (QQQ, {H}d path-min dd):")
    for name in ("qqq", "spy"):
        v = ~np.isnan(pmin[name])
        a = pmin[name][v & low_vix & abs8]      # low-VIX AND triggered
        c = pmin[name][v & low_vix & ~abs8]     # low-VIX but NOT triggered
        P(f"  {name.upper()}: low-VIX & COR1M<8 (N={len(a)}) dd={a.mean() if len(a) else float('nan'):+.2%}   "
          f"vs low-VIX & COR1M>=8 (N={len(c)}) dd={c.mean():+.2%}   "
          f"delta={(a.mean()-c.mean()) if len(a) else float('nan'):+.2%}")
    P("")
    P("Manual OLS:  path_min_dd_21 ~ b0 + b1*trigger(COR1M<8) + b2*VIX_level   (QQQ & SPY)")
    for name in ("qqq", "spy"):
        v = ~np.isnan(pmin[name])
        y = pmin[name][v]
        X = np.column_stack([np.ones(v.sum()), abs8[v].astype(float), vix[v]])
        beta = ols(X, y)
        # block-bootstrap CI for the trigger coef (block=H to respect overlap)
        n = len(y); nb = int(np.ceil(n / H)); maxs = n - H
        coefs = []
        for _ in range(2000):
            starts = rng.integers(0, maxs + 1, size=nb)
            idx = np.concatenate([np.arange(s, s + H) for s in starts])[:n]
            coefs.append(ols(X[idx], y[idx])[1])
        lo, hi = np.percentile(coefs, [2.5, 97.5])
        sig = "significant" if (lo > 0) == (hi > 0) and not (lo <= 0 <= hi) else "NOT significant (CI spans 0)"
        P(f"  {name.upper()}: trigger coef b1={beta[1]:+.3%} (shift in the 21d path-min drawdown, not per-day), "
          f"VIX coef b2={beta[2]:+.4%} per VIX point; "
          f"95% block-bootstrap CI for b1 [{lo:+.3%}, {hi:+.3%}] -> {sig}")
    P("  Read: if b1 stays clearly negative with a CI off zero, COR1M<8 adds info beyond VIX.")
    P("")

    # ===================== E-COR-003: hedge P&L net of cost =====================
    P("#" * 78)
    P("E-COR-003  Stylized 21d ATM protective-put hedge P&L (net of cost), episode-entry triggers")
    P("#" * 78)
    P("Cost model: ATM put premium ~ BS with sigma=VIX/100, T=21/252, r=0, S=K (stylized, not live quotes).")
    P(f"  {'inst':4s} | {'eps':>3s} | {'unhedged ret':>12s} | {'hedged ret':>11s} | {'premium':>8s} | {'hedge adds':>10s}")
    for name in ("qqq", "spy"):
        rows_un, rows_hd, prem_l = [], [], []
        for d in firsts:
            S = df[name].iloc[d]
            ST = df[name].iloc[d + H]
            sigma = vix[d] / 100.0
            T = H / 252.0
            # BS ATM put, r=0, S=K: P = S*(N(d2_neg)-N(d1_neg)) ; d1=0.5*sigma*sqrt(T), d2=-d1
            d1 = 0.5 * sigma * math.sqrt(T)
            Nd = lambda z: 0.5 * (1 + math.erf(z / math.sqrt(2)))
            put = S * (Nd(d1) - Nd(-d1))   # = S*(2*Nd(d1)-1)
            premium = put / S              # as fraction of notional
            payoff = max(0.0, S - ST) / S  # long put payoff fraction (K=S)
            un = ST / S - 1.0
            hd = un + payoff - premium     # hold underlying + long ATM put, net of premium
            rows_un.append(un); rows_hd.append(hd); prem_l.append(premium)
        un_m = np.mean(rows_un); hd_m = np.mean(rows_hd); pr_m = np.mean(prem_l)
        adds = hd_m - un_m
        P(f"  {name:4s} | {len(firsts):3d} | {un_m:+12.2%} | {hd_m:+11.2%} | {pr_m:8.2%} | "
          f"{adds:+10.2%} {'(helps)' if adds > 0 else '(hurts)'}")
    P("  Read: hedge 'adds' > 0 means the protective put beat doing nothing across these episodes, net of cost.")

    OUT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(L) + "\n"
    (OUT / "cor1m_round2_results.txt").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
