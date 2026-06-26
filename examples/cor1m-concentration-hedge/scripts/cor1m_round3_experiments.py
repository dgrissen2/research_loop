#!/usr/bin/env python3
"""Round 3 experiments — the H-COR-003 promotion gate (data-available parts).

E-COR-005  Beta vs concentration: is QQQ's extra triggered drawdown real concentration, or just QQQ's
           higher beta? Control QQQ's 21d path-min drawdown for SPY's 21d path-min drawdown (the market
           move) AND VIX, then test whether the COR1M<8 trigger STILL adds incremental QQQ drawdown.
           OLS: qqq_dd21 ~ trigger + spy_dd21 + VIX ; block-bootstrap CI for the trigger coef.
E-COR-010  Episode-only re-inference: redo the core QQQ test using ONE observation per episode (entry
           day, N=8) with a permutation p-value (random non-overlapping entry days) and an explicit
           multiple-testing note for the 6..10 threshold sweep (Bonferroni).

E-COR-008 (real option-chain cost) and E-COR-009 (walk-forward OOS) are DATA-BLOCKED (no option chain;
OOS needs more COR1M<8 episodes) — recorded, not run; the BS-from-VIX cost proxy from round 2 stands.

Backlinks: H-COR-003 note ; goals/.../facts.md ; plan.md Step 7.
Usage: python cor1m_round3_experiments.py -> outputs/cor1m_round3_results.txt
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

H = 21
ABS = 8.0
EPISODE_GAP = 5
SWEEP = [6.0, 7.0, 8.0, 9.0, 10.0]
SEED = 12345


def load():
    cor = pd.read_csv(DATA / "cor1m.csv", comment="#", parse_dates=["date"])
    vix = pd.read_csv(DATA / "vix_ohlc.csv", comment="#", parse_dates=["date"])[["date", "close"]]
    df = cor[["date", "cor1m"]].merge(vix.rename(columns={"close": "vix"}), on="date", how="inner")
    for n in ("spy", "qqq"):
        e = pd.read_csv(DATA / f"{n}_ohlc.csv", comment="#", parse_dates=["date"])
        df = df.merge(e[["date", "close"]].rename(columns={"close": n}), on="date", how="inner")
    return df.sort_values("date").reset_index(drop=True)


def path_min(c, h):
    n = len(c); o = np.full(n, np.nan)
    for i in range(n):
        if i + h < n:
            o[i] = c[i + 1:i + 1 + h].min() / c[i] - 1.0
    return o


def episodes(mask):
    idx = np.where(mask)[0]
    if not len(idx):
        return []
    f = [int(idx[0])]; p = idx[0]
    for i in idx[1:]:
        if i - p > EPISODE_GAP:
            f.append(int(i))
        p = i
    return f


def ols(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b


def main():
    df = load()
    rng = np.random.default_rng(SEED)
    cor = df["cor1m"].to_numpy(); vix = df["vix"].to_numpy()
    abs8 = cor < ABS
    qdd = path_min(df["qqq"].to_numpy(), H)
    sdd = path_min(df["spy"].to_numpy(), H)
    valid = ~np.isnan(qdd) & ~np.isnan(sdd)

    L = []; P = L.append
    P("COR1M CONCENTRATION-HEDGE — ROUND 3 (E-COR-005 beta-adjust, E-COR-010 episode-only)")
    P("=" * 78)
    P(f"Data {df['date'].min():%Y-%m-%d}->{df['date'].max():%Y-%m-%d}  N={len(df)}  horizon={H}d")
    P("DATA-BLOCKED (not run): E-COR-008 real option-chain cost; E-COR-009 walk-forward OOS (need more episodes).")
    P("")

    # ---- QQQ market beta (context) ----
    rq = df["qqq"].pct_change().to_numpy()
    rs = df["spy"].pct_change().to_numpy()
    m = ~np.isnan(rq) & ~np.isnan(rs)
    beta = np.cov(rq[m], rs[m])[0, 1] / np.var(rs[m])
    P(f"QQQ market beta to SPY (daily returns, full sample): {beta:.2f}")
    P("")

    # ---- E-COR-005: does trigger add QQQ drawdown beyond SPY's move + VIX? ----
    P("#" * 78)
    P("E-COR-005  Beta vs concentration  (qqq_dd21 ~ trigger + spy_dd21 + VIX)")
    P("#" * 78)
    y = qdd[valid]
    X = np.column_stack([np.ones(valid.sum()), abs8[valid].astype(float), sdd[valid], vix[valid]])
    b = ols(X, y)
    n = len(y); nb = int(np.ceil(n / H)); maxs = n - H
    coefs = []
    for _ in range(3000):
        st = rng.integers(0, maxs + 1, size=nb)
        idx = np.concatenate([np.arange(s, s + H) for s in st])[:n]
        coefs.append(ols(X[idx], y[idx])[1])
    lo, hi = np.percentile(coefs, [2.5, 97.5])
    sig = "significant (CI off 0)" if not (lo <= 0 <= hi) else "NOT significant (CI spans 0)"
    P(f"  trigger coef (incremental QQQ 21d drawdown, beyond SPY move + VIX) = {b[1]:+.2%}")
    P(f"  spy_dd21 coef (QQQ's loading on the market path) = {b[2]:+.2f}   VIX coef = {b[3]:+.4%}")
    P(f"  95% block-bootstrap CI for trigger coef [{lo:+.2%}, {hi:+.2%}] -> {sig}")
    # compare to the round-2 VIX-only trigger coef (-3.24%): how much shrinks after adding SPY drawdown?
    P(f"  Read: vs round-2 VIX-only coef -3.24%, controlling ALSO for SPY's own drawdown leaves {b[1]:+.2%}")
    P(f"        -> {'concentration-specific component survives' if b[1] < 0 and not (lo<=0<=hi) else 'largely explained by market move/beta' if b[1] > -0.005 else 'partial: shrinks but stays negative'}")
    P("")

    # ---- E-COR-010: episode-only inference + permutation + multiple testing ----
    P("#" * 78)
    P("E-COR-010  Episode-only inference (N=8 entries) + permutation p + multiple-testing")
    P("#" * 78)
    firsts = [d for d in episodes(abs8) if valid[d]]
    obs = np.mean([qdd[d] for d in firsts])
    P(f"  QQQ mean EPISODE-ENTRY 21d drawdown (N={len(firsts)}): {obs:+.2%}")
    # permutation: random sets of len(firsts) entry days >EPISODE_GAP apart, from valid days
    valid_idx = np.where(valid)[0]
    K = 10000; null = []
    need = len(firsts)
    for _ in range(K):
        chosen = []
        tries = 0
        while len(chosen) < need and tries < 100:
            c = int(rng.choice(valid_idx))
            if all(abs(c - x) > EPISODE_GAP for x in chosen):
                chosen.append(c)
            tries += 1
        if len(chosen) == need:
            null.append(np.mean([qdd[c] for c in chosen]))
    null = np.array(null)
    pval = float((null <= obs).mean())
    P(f"  Permutation p (random {need}-episode placements with mean dd <= observed): {pval:.3f}  "
      f"({'significant' if pval < 0.05 else 'NOT significant at 0.05 — expected at N=8'})")
    P(f"  Null mean dd = {null.mean():+.2%}; observed is {(null.mean()-obs):+.2%} deeper than random.")
    # multiple testing across thresholds
    P(f"  Multiple-testing note: the 6..10 sweep tested {len(SWEEP)} thresholds; "
      f"Bonferroni alpha = {0.05/len(SWEEP):.3f}. Episode-level p={pval:.3f} vs Bonferroni {0.05/len(SWEEP):.3f}.")
    P("")
    P("VERDICT INPUTS (round 3):")
    P(f"  E-COR-005: trigger {'KEEPS' if (b[1] < 0 and not (lo<=0<=hi)) else 'LOSES'} a concentration-specific component beyond beta/VIX.")
    P(f"  E-COR-010: episode-level permutation p={pval:.3f} -> {'holds' if pval<0.05 else 'underpowered (N=8), suggestive not significant'}.")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cor1m_round3_results.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
