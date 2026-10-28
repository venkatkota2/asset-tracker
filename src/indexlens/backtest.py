"""Drifting portfolio weights, periodic rebalancing, and transparent error metrics."""

import numpy as np


def simulate(returns: np.ndarray, target: np.ndarray, cost_bps: float = 5,
             rebalance_every: int = 63) -> tuple[np.ndarray, np.ndarray]:
    returns, target = np.asarray(returns, float), np.asarray(target, float)
    if returns.ndim != 2 or returns.shape[1] != len(target) or len(returns) < 2:
        raise ValueError("Invalid backtest dimensions.")
    if (not np.isfinite(returns).all() or (returns <= -1).any()
            or not np.isfinite(target).all() or (target < 0).any()
            or not np.isclose(target.sum(), 1) or not 0 <= cost_bps <= 100
            or rebalance_every < 1):
        raise ValueError("Invalid returns, weights, cost, or rebalancing interval.")
    current = target.copy()
    result, turnover = [], []
    for t, row in enumerate(returns):
        traded = 0.0
        if t == 0:
            traded = 1.0  # Initial purchase from cash.
        elif t % rebalance_every == 0:
            traded = float(np.abs(target - current).sum())  # buys + sells
            current = target.copy()
        gross = float(current @ row)
        net = (1 - traded * cost_bps / 10_000) * (1 + gross) - 1
        result.append(net)
        turnover.append(traded)
        current = current * (1 + row) / (1 + gross)
    return np.asarray(result), np.asarray(turnover)


def metrics(portfolio: np.ndarray, benchmark: np.ndarray) -> dict:
    portfolio, benchmark = np.asarray(portfolio), np.asarray(benchmark)
    if len(portfolio) != len(benchmark) or len(portfolio) < 2:
        raise ValueError("Metrics require at least two aligned observations.")
    active = portfolio - benchmark
    wealth = np.r_[1.0, np.cumprod(1 + portfolio)]
    benchmark_wealth = np.prod(1 + benchmark)
    correlation = (float(np.corrcoef(portfolio, benchmark)[0, 1])
                   if np.std(portfolio) > 1e-14 and np.std(benchmark) > 1e-14 else None)
    return {
        "tracking_error": float(np.std(active, ddof=1) * np.sqrt(252)),
        "tracking_rmse": float(np.sqrt(np.mean(active**2)) * np.sqrt(252)),
        "annualized_active_mean": float(active.mean() * 252),
        "correlation": correlation,
        "total_return": float(wealth[-1] - 1),
        "benchmark_return": float(benchmark_wealth - 1),
        "cumulative_gap": float(wealth[-1] - benchmark_wealth),
        "max_drawdown": float(np.min(wealth / np.maximum.accumulate(wealth) - 1)),
    }

