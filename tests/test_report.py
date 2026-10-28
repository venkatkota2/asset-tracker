import copy
import json
import numpy as np
import pytest
from indexlens.data import demo_dataset, prepare_returns
from indexlens.report import build_report


@pytest.fixture(scope="module")
def dataset():
    return demo_dataset(n_assets=30, n_days=500)


def test_holdout_changes_cannot_change_selection_or_weights(dataset):
    first = build_report(dataset, budgets=[5, 10, 20])
    altered = copy.deepcopy(dataset)
    # First held-out return is price row 401; train + validation ends at row 400.
    altered.prices.iloc[401:, 1:] *= np.linspace(1, 1.5, len(altered.prices) - 401)[:, None]
    second = build_report(altered, budgets=[5, 10, 20])
    assert first['recommended_budget'] == second['recommended_budget']
    for a, b in zip(first['portfolios'], second['portfolios']):
        assert a['holdings'] == b['holdings']
        assert a['validation'] == b['validation']
        assert a['test']['total_return'] != b['test']['total_return']


def test_missing_prices_are_excluded_not_filled(dataset):
    missing = copy.deepcopy(dataset)
    missing.prices.iloc[50, 1] = np.nan
    returns, quality = prepare_returns(missing)
    assert 'SIM001' not in returns
    assert quality['excluded_assets'] == ['SIM001']
    assert len(returns) == 500


def test_windows_and_export_are_consistent(dataset):
    report = build_report(dataset, budgets=[5, 10, 20])
    assert report['windows']['train']['end'] < report['windows']['validation']['start']
    assert report['windows']['validation']['end'] < report['windows']['test']['start']
    for p in report['portfolios']:
        assert len(p['series']) == report['windows']['test']['observations'] + 1
        assert p['series'][0]['portfolio'] == 100
        assert sum(h['weight'] for h in p['holdings']) == pytest.approx(1, abs=1e-6)
        assert max(h['weight'] for h in p['holdings']) <= .25 + 1e-7
        assert p['holding_count'] <= p['budget']
    assert json.loads(json.dumps(report, allow_nan=False))['dataset']['kind'] == 'synthetic'


def test_missing_holdout_data_fails_instead_of_changing_universe(dataset):
    missing = copy.deepcopy(dataset)
    missing.prices.iloc[-20, 1] = np.nan
    with pytest.raises(ValueError, match="future availability"):
        build_report(missing, budgets=[5, 10, 20])


def test_invalid_prices_fail(dataset):
    broken = copy.deepcopy(dataset)
    broken.prices.iloc[10, 1] = -1
    with pytest.raises(ValueError, match="positive"):
        prepare_returns(broken)

