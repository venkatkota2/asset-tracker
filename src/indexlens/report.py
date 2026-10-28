"""Leakage-aware chronological model selection and compact public output."""

from datetime import datetime, timezone
import numpy as np

from .backtest import metrics, simulate
from .data import Dataset, prepare_returns
from .optimizer import choose_budget, fit_weights, sparse_path


def build_report(dataset: Dataset, budgets: list[int] | None = None,
                 max_weight: float = .25, cost_bps: float = 5,
                 complexity_weight: float = .5) -> dict:
    returns, quality = prepare_returns(dataset)
    budgets = budgets or [5, 10, 15, 20, 30, 40, 60]
    budgets = sorted(set(budgets))
    n = len(returns)
    train_end, validation_end = int(n * .6), int(n * .8)
    symbols = list(returns.columns[1:])
    x = returns[symbols].to_numpy()
    y = returns[dataset.benchmark].to_numpy()
    path = sparse_path(x[:train_end], y[:train_end], budgets, max_weight)
    scores, fitted_train = {}, {}
    for budget, support in path.items():
        w = fit_weights(x[:train_end, support], y[:train_end], max_weight)
        validation, _ = simulate(x[train_end:validation_end, support], w, cost_bps)
        scores[budget] = metrics(validation, y[train_end:validation_end])
        fitted_train[budget] = w
    recommended = choose_budget({k: m["tracking_rmse"] for k, m in scores.items()}, complexity_weight)
    portfolios = []
    for budget, support in path.items():
        # Freeze the selected support, then refit on train + validation before test.
        w = fit_weights(x[:validation_end, support], y[:validation_end], max_weight)
        test, turnover = simulate(x[validation_end:, support], w, cost_bps)
        test_metrics = metrics(test, y[validation_end:])
        test_metrics["traded_notional"] = float(turnover.sum())
        holdings = []
        for pos, weight in zip(support, w):
            if weight <= 1e-7:
                continue
            symbol = symbols[pos]
            holdings.append({"symbol": symbol, **dataset.assets[symbol], "weight": float(weight)})
        holdings.sort(key=lambda item: (-item["weight"], item["symbol"]))
        sectors = {}
        for h in holdings:
            sectors[h["sector"]] = sectors.get(h["sector"], 0) + h["weight"]
        portfolio_path = np.r_[100, 100 * np.cumprod(1 + test)]
        benchmark_path = np.r_[100, 100 * np.cumprod(1 + y[validation_end:])]
        series_dates = [str(d.date()) for d in returns.index[validation_end - 1:]]
        portfolios.append({
            "budget": budget, "holding_count": len(holdings), "holdings": holdings,
            "sectors": [{"sector": sector, "weight": value} for sector, value in
                        sorted(sectors.items(), key=lambda item: -item[1])],
            "validation": scores[budget], "test": test_metrics,
            "effective_holdings": float(1 / np.sum(w**2)),
            "max_weight": float(w.max()),
            "series": [{"date": d, "portfolio": round(float(p), 6), "benchmark": round(float(b), 6)}
                       for d, p, b in zip(series_dates, portfolio_path, benchmark_path)],
        })
    equal, _ = simulate(x[validation_end:], np.full(len(symbols), 1 / len(symbols)), cost_bps)
    def window(start, stop):
        return {"start": str(returns.index[start].date()), "end": str(returns.index[stop-1].date()),
                "observations": stop - start}
    warnings = list(dataset.warnings)
    if quality["excluded_assets"]:
        warnings.append(f"{len(quality['excluded_assets'])} assets excluded for incomplete histories; see data-quality details.")
    if quality["large_return_observations"]:
        warnings.append("Daily price moves above 50% were detected. Review source corporate-action adjustments.")
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark": {"id": "sp500", "name": "S&P 500", "proxy": dataset.benchmark,
                      "return_basis": "Simulated returns" if dataset.kind == "synthetic" else "Dividend- and split-adjusted SPY returns"},
        "dataset": {"kind": dataset.kind, "source": dataset.source,
                    "universe_as_of": dataset.universe_as_of, **quality},
        "windows": {"train": window(0, train_end), "validation": window(train_end, validation_end),
                    "test": window(validation_end, n)},
        "model": {"method": "Greedy support selection + constrained ridge least squares",
                  "long_only": True, "fully_invested": True, "max_position_weight": max_weight,
                  "cost_bps": cost_bps, "rebalance_every_sessions": 63,
                  "complexity_weight": complexity_weight, "weights_as_of": str(returns.index[validation_end-1].date()),
                  "selection_rule": "Normalize holding budget and validation RMSE to [0,1]; minimize the weighted squared distance from the ideal (smallest budget, lowest error). Equal default importance for simplicity and precision. Grid-dependent heuristic, not a global optimum.",
                  "evaluation": "Supports selected on training only; size selected on validation only; weights refit on train + validation; test never used for selection."},
        "recommended_budget": recommended, "portfolios": portfolios,
        "equal_weight_baseline": {"holding_count": len(symbols), **metrics(equal, y[validation_end:])},
        "warnings": warnings,
    }

