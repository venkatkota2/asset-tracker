from pathlib import Path
from fastapi.testclient import TestClient
from indexlens import api


def test_report_and_allocations():
    with TestClient(api.app) as client:
        result = client.get('/api/report')
        assert result.status_code == 200
        report = result.json()
        result = client.post('/api/portfolio', json={'capital':20000,'max_holdings':10})
        assert result.status_code == 200
        body = result.json()
        assert body['dataset_kind'] == report['dataset']['kind']
        assert abs(sum(a['amount'] for a in body['allocations']) - 20000) < .1


def test_rejects_unsupported_benchmarks_and_budgets():
    with TestClient(api.app) as client:
        assert client.post('/api/portfolio',json={'benchmark':'nasdaq'}).status_code == 422
        assert client.post('/api/portfolio',json={'max_holdings':7}).status_code == 422
        assert client.post('/api/portfolio',json={'capital':-100}).status_code == 422
        assert client.get('/api/benchmarks').json()['benchmarks'][0]['id'] == 'sp500'


def test_missing_report_is_503(monkeypatch,tmp_path):
    monkeypatch.setattr(api,'REPORT_PATH',Path(tmp_path)/'absent.json')
    with TestClient(api.app) as client:
        assert client.get('/api/report').status_code == 503

