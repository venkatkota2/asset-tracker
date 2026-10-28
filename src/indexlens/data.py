"""Validated price panels and deterministic, explicitly synthetic demo data."""

from dataclasses import dataclass
import numpy as np
import pandas as pd


@dataclass
class Dataset:
    prices: pd.DataFrame
    assets: dict[str, dict[str, str]]
    benchmark: str
    source: str
    kind: str
    universe_as_of: str
    warnings: list[str]


def prepare_returns(dataset: Dataset) -> tuple[pd.DataFrame, dict]:
    """Use benchmark sessions; never interpolate, backfill, or forward-fill prices.

    Determine history eligibility from training dates only. Missing later prices
    fail the run instead of silently changing the candidate universe using future
    availability. The training-history filter still introduces selection bias.
    """
    prices = dataset.prices.copy()
    if dataset.benchmark not in prices or prices.columns.duplicated().any():
        raise ValueError("A unique benchmark and unique asset symbols are required.")
    if prices.index.has_duplicates or not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Price dates must be a unique DatetimeIndex.")
    prices = prices.sort_index().astype(float)
    if ((prices <= 0) & prices.notna()).any().any() or np.isinf(prices).any().any():
        raise ValueError("Prices must be finite and positive when present.")
    prices = prices.loc[prices[dataset.benchmark].notna()]
    candidates = [s for s in prices if s != dataset.benchmark]
    training_rows = int((len(prices) - 1) * .6) + 1
    excluded = [s for s in candidates if prices[s].iloc[:training_rows].isna().any()]
    eligible = [s for s in candidates if s not in excluded]
    if len(eligible) < 5:
        raise ValueError("At least five assets with complete price histories are required.")
    if len(prices) < 401:
        raise ValueError("At least 401 aligned daily price observations are required.")
    missing_later = [s for s in eligible if prices[s].iloc[training_rows:].isna().any()]
    if missing_later:
        raise ValueError(f"{len(missing_later)} training-eligible assets have missing validation/test prices. Refusing to change the universe using future availability.")
    returns = prices[[dataset.benchmark, *eligible]].pct_change(fill_method=None).iloc[1:]
    if not np.isfinite(returns.to_numpy()).all() or (returns <= -1).any().any():
        raise ValueError("Returns contain invalid observations.")
    quality = {
        "requested_assets": len(candidates), "eligible_assets": len(eligible),
        "excluded_assets": excluded, "observations": len(returns),
        "first_date": str(returns.index[0].date()),
        "last_date": str(returns.index[-1].date()),
        "large_return_observations": int((returns.abs() > .5).sum().sum()),
        "missing_data_policy": "Eligibility uses complete training histories only; later missing prices fail the run. No filling or interpolation.",
    }
    return returns, quality


SECTORS = ["Technology", "Financials", "Health care", "Consumer discretionary",
           "Communication", "Industrials", "Consumer staples", "Energy",
           "Utilities", "Real estate", "Materials"]


def demo_dataset(n_assets: int = 500, n_days: int = 1008, seed: int = 42) -> Dataset:
    """Factor simulation for UI and reproducible tests, NOT historical market data."""
    if n_assets < 5 or n_days < 400:
        raise ValueError("Demo requires >=5 assets and >=400 daily returns.")
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days + 1)
    # Weekdays are a simulation clock, not an exchange calendar.
    market = rng.normal(.00030, .009, (n_days, 1))
    sector_factors = rng.normal(0, .004, (n_days, len(SECTORS)))
    sector_ids = np.arange(n_assets) % len(SECTORS)
    betas = rng.uniform(.7, 1.3, n_assets)
    noise = rng.normal(0, 1, (n_days, n_assets)) * rng.uniform(.006, .018, n_assets)
    asset_returns = market * betas + sector_factors[:, sector_ids] + noise
    # A reproducible, uneven benchmark creates a meaningful concentration trade-off.
    index_weights = 1 / (np.arange(n_assets) + 8) ** .85
    index_weights /= index_weights.sum()
    benchmark = asset_returns @ index_weights
    symbols = [f"SIM{i+1:03d}" for i in range(n_assets)]
    matrix = np.column_stack([benchmark, asset_returns])
    prices = pd.DataFrame(100 * np.vstack([np.ones(n_assets + 1),
                                          np.cumprod(1 + matrix, axis=0)]),
                          index=dates, columns=["SIM-BENCHMARK", *symbols])
    assets = {s: {"name": f"{SECTORS[sector_ids[i]]} · simulated asset {i+1}",
                  "sector": SECTORS[sector_ids[i]]} for i, s in enumerate(symbols)}
    return Dataset(prices, assets, "SIM-BENCHMARK", "Seeded factor simulation (seed 42)",
                   "synthetic", "Not applicable — fictional universe", [
                       "All prices, symbols, weights and performance in this demo are simulated. They do not describe the S&P 500 or real investments.",
                       "The simulation uses weekdays, not the exchange holiday calendar.",
                   ])

