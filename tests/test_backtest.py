import numpy as np
import pytest
from indexlens.backtest import simulate, metrics


def test_buy_and_hold_drift_is_not_constant_weight_rebalancing():
    x = np.array([[.10, 0], [0, .10]])
    net, turnover = simulate(x, np.array([.5, .5]), cost_bps=0, rebalance_every=63)
    assert net[0] == pytest.approx(.05)
    assert net[1] == pytest.approx(.1 * .5 / 1.05)
    assert np.prod(1 + net) == pytest.approx(1.10)
    assert turnover.sum() == 1


def test_initial_and_rebalance_costs_are_on_traded_notional():
    x = np.array([[.10, 0], [0, 0]])
    net, turnover = simulate(x, np.array([.5, .5]), cost_bps=10, rebalance_every=1)
    assert net[0] == pytest.approx(1.05 * .999 - 1)
    assert turnover[1] == pytest.approx(2 * (.55 / 1.05 - .5))
    assert net[1] == pytest.approx(-turnover[1] * .001)


def test_rmse_detects_bias_that_tracking_error_does_not():
    benchmark = np.array([.01, -.01, .005, -.003])
    result = metrics(benchmark + .001, benchmark)
    assert result['tracking_error'] < 1e-12
    assert result['tracking_rmse'] == pytest.approx(.001 * np.sqrt(252))
    assert result['annualized_active_mean'] == pytest.approx(.252)


def test_drawdown_includes_initial_capital():
    result = metrics(np.array([-.1, 0]), np.array([0, 0]))
    assert result['max_drawdown'] == pytest.approx(-.1)
    assert result['correlation'] is None

