#!/usr/bin/env python3
"""Fetch real market data for the COR1M concentration-hedge study.

Pulls daily OHLC for SPY / IWM / QQQ and the VIX level from Yahoo Finance
(`yfinance`, with a Stooq CSV fallback that needs no key), and the Cboe 1-Month
Implied Correlation index (COR1M) from Cboe's public index-history CDN. Writes tidy
CSVs to ``data/`` and a coverage summary to ``outputs/data_coverage.txt``.

Backlinks (research_loop):
- Goal facts : goals/cor1m-concentration-hedge/facts.md (fact-data)
- Plan       : goals/cor1m-concentration-hedge/plan.md (Step 1)

Usage:
    python fetch_market_data.py [--start 2018-01-01] [--end YYYY-MM-DD]

Notes:
- COR1M has no free Yahoo/Stooq mirror; it comes only from Cboe. If Cboe's series
  does not extend back to --start, the TRUE first date is reported in the coverage
  summary and NOT silently shortened (see plan.md Risk 1).
"""
from __future__ import annotations

import argparse
import csv
import io
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"

# Yahoo ticker -> output basename
ETF_TICKERS = {"SPY": "spy", "IWM": "iwm", "QQQ": "qqq"}
VIX_TICKER = {"^VIX": "vix"}

# Cboe public index-history CDN (same host that serves VIX_History.csv)
CBOE_COR1M_URLS = [
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/COR1M_History.csv",
    "https://cdn.cboe.com/api/global/us_indices/daily_prices/COR1M_history.csv",
]

OHLC_COLS = ["date", "open", "high", "low", "close", "volume"]


def _isnan(x) -> bool:
    try:
        return x != x
    except Exception:
        return False


def _write_csv(path: Path, rows: list[dict], cols: list[str], header_note: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as fh:
        if header_note:
            fh.write(f"# {header_note}\n")
        writer = csv.DictWriter(fh, fieldnames=cols)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in cols})
    return path


def _via_yfinance(ticker: str, start: str, end: str) -> list[dict] | None:
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return None
    try:
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    except Exception:
        return None
    if df is None or df.empty:
        return None
    df = df.reset_index()
    # yfinance may return a MultiIndex on columns for a single ticker; flatten it.
    df.columns = [c[0] if isinstance(c, tuple) else c for c in df.columns]
    rows = []
    for _, r in df.iterrows():
        try:
            rows.append({
                "date": str(r["Date"])[:10],
                "open": round(float(r["Open"]), 4),
                "high": round(float(r["High"]), 4),
                "low": round(float(r["Low"]), 4),
                "close": round(float(r["Close"]), 4),
                "volume": int(r["Volume"]) if not _isnan(r["Volume"]) else "",
            })
        except (KeyError, ValueError, TypeError):
            continue
    return rows or None


def _via_stooq(ticker: str, start: str, end: str) -> list[dict] | None:
    sym = {"SPY": "spy.us", "IWM": "iwm.us", "QQQ": "qqq.us", "^VIX": "^vix"}.get(ticker)
    if sym is None:
        return None
    url = (f"https://stooq.com/q/d/l/?s={sym}"
           f"&d1={start.replace('-', '')}&d2={end.replace('-', '')}&i=d")
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            text = resp.read().decode("utf-8")
    except Exception:
        return None
    rows = []
    for r in csv.DictReader(io.StringIO(text)):
        if not r.get("Date"):
            continue
        rows.append({
            "date": r["Date"],
            "open": r.get("Open", ""), "high": r.get("High", ""),
            "low": r.get("Low", ""), "close": r.get("Close", ""),
            "volume": r.get("Volume", ""),
        })
    return rows or None


def fetch_ohlc(ticker: str, name: str, start: str, end: str) -> tuple[list[dict], str]:
    rows = _via_yfinance(ticker, start, end)
    source = "yfinance"
    if not rows:
        rows = _via_stooq(ticker, start, end)
        source = "stooq"
    return (rows or []), source


def fetch_cor1m(start: str, end: str) -> tuple[list[dict], str]:
    """Cboe COR1M history -> rows of {date, cor1m}. Cboe CSV cols: DATE, ... value col."""
    text = None
    used = ""
    for url in CBOE_COR1M_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
                used = url
                break
        except Exception:
            continue
    if not text:
        return [], ""
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        return [], used
    # Cboe files vary: find the date col and a numeric value col.
    cols = [h.strip().lower() for h in header]
    date_i = next((i for i, c in enumerate(cols) if c in ("date", "trade_date")), 0)
    val_i = next((i for i in range(len(cols)) if i != date_i), 1)
    rows = []
    for r in reader:
        if len(r) <= max(date_i, val_i) or not r[date_i].strip():
            continue
        raw_date = r[date_i].strip()
        # Normalize common Cboe date formats to YYYY-MM-DD.
        d = None
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m/%d/%y"):
            try:
                d = datetime.strptime(raw_date, fmt).strftime("%Y-%m-%d")
                break
            except ValueError:
                continue
        if d is None or not (start <= d <= end):
            continue
        try:
            val = float(r[val_i])
        except ValueError:
            continue
        rows.append({"date": d, "cor1m": round(val, 4)})
    rows.sort(key=lambda x: x["date"])
    return rows, used


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = p.parse_args()

    summary: list[str] = []
    summary.append("COR1M concentration-hedge — data coverage")
    summary.append("=" * 48)
    summary.append(f"Requested window: {args.start} -> {args.end}")
    summary.append("")

    ok = True
    for ticker, name in {**ETF_TICKERS, **VIX_TICKER}.items():
        rows, source = fetch_ohlc(ticker, name, args.start, args.end)
        if not rows:
            summary.append(f"  FAIL  {ticker:5s} ({name}): no data from yfinance or stooq")
            ok = False
            continue
        path = _write_csv(DATA / f"{name}_ohlc.csv", rows, OHLC_COLS,
                          header_note=f"{ticker} daily OHLC via {source}; fetched for COR1M study")
        first, last = rows[0]["date"], rows[-1]["date"]
        summary.append(f"  OK    {ticker:5s} ({name}): {len(rows):5d} rows  {first} -> {last}  via {source}")

    cor_rows, cor_src = fetch_cor1m(args.start, args.end)
    if not cor_rows:
        summary.append("  FAIL  COR1M: no data from Cboe CDN (see plan.md Risk 1 & 5)")
        ok = False
    else:
        _write_csv(DATA / "cor1m.csv", cor_rows, ["date", "cor1m"],
                   header_note=f"Cboe COR1M 1-month implied correlation via {cor_src}")
        first, last = cor_rows[0]["date"], cor_rows[-1]["date"]
        summary.append(f"  OK    COR1M       : {len(cor_rows):5d} rows  {first} -> {last}  via Cboe")
        summary.append("")
        if first > "2018-01-31":
            summary.append(f"  NOTE  COR1M true start is {first} (later than 2018-01-01). "
                           f"Record this real start in sample integrity; do not backfill (plan.md Risk 1).")
        below8 = sum(1 for r in cor_rows if r["cor1m"] < 8)
        summary.append(f"  COR1M < 8 trigger days in window: {below8}")

    summary.append("")
    summary.append("Result: " + ("ALL SOURCES OK" if ok else "SOME SOURCES FAILED — see above"))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data_coverage.txt").write_text("\n".join(summary) + "\n")
    print("\n".join(summary))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
