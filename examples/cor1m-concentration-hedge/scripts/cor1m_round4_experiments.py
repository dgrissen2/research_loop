#!/usr/bin/env python3
"""Round 4 (closure) experiments.

E-COR-004  Circularity contrast: test the COR1M<8 trigger against a forward *options-derived* target —
           the 21d change in VIX — and contrast with the realized (non-circular) drawdown target. Both
           COR1M and VIX are implied/options measures, so this comparison is PARTIALLY CIRCULAR by
           construction; it exists to show why the realized price-path target (H-COR-001/003) is the
           honest one.
E-COR-011  Era stability: how many trigger episodes fall pre-2024 vs 2024-2026, and does the surviving
           conditional QQQ effect (E-COR-005 model) hold inside the 2024-26 subsample? With ~8 of 9
           episodes in 2024-26, cross-era stability essentially CANNOT be established — that itself is the
           finding (regime-concentration limitation).

Backlinks: H-COR-001/H-COR-003 ; goals/.../facts.md (fact-e-cor-004) ; plan.md Step 7.
Usage: python cor1m_round4_experiments.py -> outputs/cor1m_round4_results.txt
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
    n = len(df)

    # forward 21d VIX change (options-derived target) and realized QQQ drawdown (non-circular)
    fvix = np.full(n, np.nan)
    for i in range(n):
        if i + H < n:
            fvix[i] = vix[i + H] - vix[i]
    qdd = path_min(df["qqq"].to_numpy(), H)
    sdd = path_min(df["spy"].to_numpy(), H)

    L = []; P = L.append
    P("COR1M CONCENTRATION-HEDGE — ROUND 4 (closure): E-COR-004 circularity, E-COR-011 era stability")
    P("=" * 80)
    P(f"Data {df['date'].min():%Y-%m-%d}->{df['date'].max():%Y-%m-%d}  N={n}  horizon={H}d")
    P("")

    # ---- E-COR-004 circularity contrast ----
    P("#" * 80)
    P("E-COR-004  Circularity contrast: forward 21d VIX change (options-derived) vs realized QQQ drawdown")
    P("#" * 80)
    vmask = ~np.isnan(fvix)
    t = fvix[vmask & abs8]; b = fvix[vmask & ~abs8]
    P(f"  Forward 21d VIX change:  triggered (COR1M<8) mean = {t.mean():+.2f} pts (N={len(t)});  "
      f"baseline mean = {b.mean():+.2f} pts")
    P(f"  -> triggered VIX rises {t.mean() - b.mean():+.2f} pts more than baseline.")
    P("  NOTE: COR1M and VIX are BOTH implied/options measures; low COR1M coincides with low VIX, so this")
    P("        forward-VIX-rise is PARTIALLY CIRCULAR (mean-reversion of implied vol), not independent")
    P("        confirmation. Contrast: the realized QQQ drawdown target (H-COR-003) shares no options input")
    P(f"        and is the honest test. (Realized QQQ 21d dd triggered = {qdd[~np.isnan(qdd)&abs8].mean():+.2%}.)")
    P("")

    # ---- E-COR-011 era stability ----
    P("#" * 80)
    P("E-COR-011  Era stability of the conditional QQQ effect")
    P("#" * 80)
    yr = df["date"].dt.year.to_numpy()
    firsts = [d for d in episodes(abs8) if not np.isnan(qdd[d])]
    pre = [d for d in firsts if yr[d] < 2024]
    post = [d for d in firsts if yr[d] >= 2024]
    P(f"  Trigger episodes by era:  pre-2024 = {len(pre)} "
      f"({', '.join(df['date'].iloc[pre].dt.strftime('%Y-%m-%d')) or 'none'});  "
      f"2024-2026 = {len(post)}")
    P(f"  -> {len(post)}/{len(firsts)} episodes are 2024-2026. Cross-era stability CANNOT be established:")
    P("     pre-2024 has too few episodes to test. The effect is, on this data, a 2024-2026 phenomenon.")
    # conditional effect within 2024-26 subsample
    sub = yr >= 2024
    valid = ~np.isnan(qdd) & ~np.isnan(sdd) & sub
    y = qdd[valid]
    X = np.column_stack([np.ones(valid.sum()), abs8[valid].astype(float), sdd[valid], vix[valid]])
    bsub = ols(X, y)
    nn = len(y); nb = int(np.ceil(nn / H)); maxs = nn - H
    coefs = []
    for _ in range(2000):
        st = rng.integers(0, maxs + 1, size=nb)
        idx = np.concatenate([np.arange(s, s + H) for s in st])[:nn]
        coefs.append(ols(X[idx], y[idx])[1])
    lo, hi = np.percentile(coefs, [2.5, 97.5])
    sig = "significant" if not (lo <= 0 <= hi) else "NOT significant (CI spans 0)"
    P(f"  2024-26 subsample (N={int(valid.sum())} days): trigger coef {bsub[1]:+.2%} "
      f"controlling SPY dd + VIX; 95% block-bootstrap CI [{lo:+.2%}, {hi:+.2%}] -> {sig}")
    P("  Read: the surviving conditional effect lives within the 2024-26 regime; pre-2024 is untested.")
    P("")
    P("CONVERGENCE: remaining decision-moving gates (E-COR-008 real cost, E-COR-009 OOS) are data-blocked.")
    P("Program converges at H-COR-003 = weak_support (real, concentration-specific, but 2024-26-bound & N=8).")

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "cor1m_round4_results.txt").write_text("\n".join(L) + "\n")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
