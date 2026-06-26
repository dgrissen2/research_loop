# Facts — COR1M concentration measure & over-bulled hedge trigger

Accepted shared understanding for goal `cor1m-concentration-hedge`. Every findings note in the
`research-hypothesis-maintainer` loop backlinks here.

- The research loop is run by a confirmed three-persona panel — CIO, Quant Analyst, and Portfolio Manager — and every findings note is reviewed through all three.
- Hypothesis H1 tests whether COR1M is a valid measure of extreme market concentration / single-stock crowding.
- Hypothesis H2 tests whether the COR1M < 8 "over-bulled" tail is a usable forward hedge trigger for equity indices.
- Hypothesis H3 tests whether the COR1M < 8 tail adds edge beyond a VIX/vol-based trigger.
- The over-bulled trigger is defined as the absolute level COR1M < 8 (SpotGamma "certain risk flag"), used as a fixed seed threshold rather than a fitted or optimized parameter.
- The hedge trigger is evaluated on SPY (primary) and QQQ; IWM and non-equity assets are out of scope.
- Forward outcomes are measured at 5, 10, 21, and 42 trading-day horizons.
- The trigger's edge is scored against the unconditional base rate using forward maximum drawdown and hit-rate / precision, not average return alone.
- H1 is validated using COR1M as the concentration proxy plus locally available cross-checks (VIX, realized index correlation/dispersion from SPY/QQQ); fetching external concentration data (top-N weight, single-stock call volume) is a deferred follow-up experiment, not a round-1 dependency.
- The loop tests the signal on the underlying index (forward return/drawdown) only; option or convexity hedge structuring is deferred to a follow-up experiment and is not part of the seed hypotheses.
- The program runs under a round cap of 7 rounds and produces a decision-maker memo at the cap.
- Out of scope: live execution / broker integration, intraday or tick data, non-equity assets, a full backtest/portfolio engine, and parameter over-optimization (curve-fitting the threshold).
- Analysis uses local data only: `data/cor1m.csv`, `data/spy_ohlc.csv`, `data/qqq_ohlc.csv`, and `data/vix_ohlc.csv` (baseline).
- Each hypothesis produces a findings note that backlinks to this goal's facts and adds exactly one row to `RESEARCH_HYPOTHESIS_INDEX.md`.
