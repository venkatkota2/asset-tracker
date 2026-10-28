# Adding benchmarks and asset classes

The `Dataset` boundary separates data ingestion from optimization. A new provider
must supply a positive, adjusted price DataFrame with a unique DatetimeIndex,
a benchmark column, candidate symbols, names/sectors, data-kind metadata, source,
universe date and relevant limitations. The candidate set must exclude the
benchmark instrument itself; otherwise a one-asset solution simply buying that
ETF defeats the sparse constituent-replication objective.

## Next benchmark

1. Add the benchmark and candidate universe to a registry, with a verified
   total-return data source and point-in-time membership if available.
2. Add a provider method returning `Dataset`; preserve corporate-action and
   calendar semantics instead of converting missing observations into zero returns.
3. Build one report per benchmark, each with its own observation windows and
   selection provenance.
4. Extend `/api/benchmarks`, the request enum and report lookup. Return 404/422
   for unsupported ids. Do not build arbitrary provider URLs from visitor input.
5. Populate the frontend selector from that registry; fetch the selected report.
6. Add a no-leakage test and a known-return numerical test for the new data path.

## Bonds, foreign equities and mixed assets

Use currency-consistent total returns, not raw clean bond prices or a mix of local
and base currencies. Treat accrued interest, coupons, distributions, FX, calendar
alignment and stale prices explicitly. A 252-session annualization and fixed
equity-style cost assumption may no longer be appropriate. Restrict turnover and
liquidity, add realistic minimum trade sizes, and measure transaction costs.

## Higher research fidelity

- Historical constituents and delisting returns to remove current-universe bias.
- Nested walk-forward model selection with genuinely forward-only refits.
- Mixed-integer quadratic optimization or local swaps to benchmark the greedy search.
- Sector/factor exposure constraints and covariance shrinkage for stability.
- Turnover penalties relative to the previously implemented portfolio.
- Model stability across regimes, parameter ranges and transaction-cost scenarios.
- Bootstrap uncertainty that respects serial dependence.
- Authenticated asynchronous optimization jobs for custom inputs, with quotas and
  results caching; keep provider ingestion separate from anonymous traffic.

Never describe the current demo as a historical S&P 500 result. Never optimize
on the full sample and then describe those same dates as out-of-sample.

