# data/

Real market data used by this worked example. Regenerate any time with
[`../scripts/fetch_market_data.py`](../scripts/fetch_market_data.py).

| File | What | Source |
|---|---|---|
| `cor1m.csv` | Cboe 1-Month Implied Correlation Index (daily) | Cboe — `https://cdn.cboe.com/api/global/us_indices/daily_prices/COR1M_History.csv` |
| `spy_ohlc.csv` | SPY daily OHLC | Yahoo Finance (`yfinance`), Stooq fallback |
| `qqq_ohlc.csv` | QQQ daily OHLC | Yahoo Finance / Stooq |
| `iwm_ohlc.csv` | IWM daily OHLC | Yahoo Finance / Stooq |
| `vix_ohlc.csv` | VIX daily OHLC | Yahoo Finance / Stooq |

## Attribution & terms

**COR1M** values are © Cboe Exchange, Inc. ("Cboe Data"), redistributed here in small volume solely to make
this open-source example reproducible. Cboe Data is provided under Cboe's own terms of use; it is not
licensed by this project, and the project makes no warranty as to its accuracy. If you redistribute or use
COR1M beyond running this example, review Cboe's terms (<https://www.cboe.com/us/indices/>) and consider
fetching it yourself via `fetch_market_data.py` rather than relying on this snapshot.

OHLC series are standard public market data retrieved from Yahoo Finance / Stooq.

## Reproduce

```bash
cd ../scripts && python3 fetch_market_data.py   # rewrites these CSVs from source
```
