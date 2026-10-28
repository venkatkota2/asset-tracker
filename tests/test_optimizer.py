import numpy as np
import pytest
from indexlens.optimizer import fit_weights, sparse_path, choose_budget


def test_recovers_known_fully_invested_portfolio():
    rng = np.random.default_rng(19)
    x = rng.normal(0, .01, (500, 4))
    expected = np.array([.35, .25, .2, .2])
    actual = fit_weights(x, x @ expected, max_weight=.4, ridge=0)
    np.testing.assert_allclose(actual, expected, atol=1e-5)


def test_constraints_and_infeasible_caps():
    rng = np.random.default_rng(7)
    x = rng.normal(0, .01, (200, 8))
    y = x[:, 0]
    weights = fit_weights(x, y, max_weight=.2)
    assert weights.min() >= 0
    assert weights.max() <= .2 + 1e-7
    assert weights.sum() == pytest.approx(1)
    with pytest.raises(ValueError, match="Infeasible"):
        fit_weights(x[:, :3], y, max_weight=.2)


def test_nested_supports_stay_within_budgets():
    rng = np.random.default_rng(3)
    x = rng.normal(0, .01, (240, 20))
    path = sparse_path(x, x[:, :6].mean(axis=1), [5, 10, 15])
    assert set(path[5]).issubset(path[10])
    assert set(path[10]).issubset(path[15])
    assert all(len(set(v)) == k for k, v in path.items())


def test_balanced_selection_and_flat_curve():
    scores = {5: .052, 10: .03413, 15: .03069, 20: .02808, 30: .02302, 40: .01894, 60: .01550}
    assert choose_budget(scores) == 20
    assert choose_budget({5: .01, 10: .01, 20: .01}) == 5
    with pytest.raises(ValueError):
        choose_budget({5: float('nan')})

