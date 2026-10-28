from datetime import date
import httpx
import pytest
from indexlens.providers import FMPProvider, ProviderError


def test_adjusted_prices_and_cache_do_not_store_api_key(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        assert request.url.path == '/stable/historical-price-eod/dividend-adjusted'
        assert request.url.params['apikey'] == 'test-secret'
        return httpx.Response(200, json=[{'date':'2024-01-03','adjClose':102},
                                       {'date':'2024-01-02','adjClose':100}])
    client = httpx.Client(transport=httpx.MockTransport(handler))
    provider = FMPProvider('test-secret', tmp_path, client=client, sleep=lambda _: None)
    a = provider.prices('AAPL', date(2024, 1, 1), date(2024, 1, 4))
    b = provider.prices('AAPL', date(2024, 1, 1), date(2024, 1, 4))
    assert list(a) == [100, 102]
    assert a.equals(b) and len(calls) == 1
    assert all('test-secret' not in p.read_text() for p in tmp_path.iterdir())


def test_retry_after_then_success(tmp_path):
    calls, delays = [], []
    def handler(request):
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={'Retry-After':'2'})
        return httpx.Response(200, json=[])
    provider = FMPProvider('test-secret', tmp_path,
                           client=httpx.Client(transport=httpx.MockTransport(handler)), sleep=delays.append)
    assert provider._get('sp500-constituent') == []
    assert len(calls) == 2 and 2 in delays


@pytest.mark.parametrize('status,payload',[(403,{}),(200,{'Error Message':'secret-bearing text'}),(200,[{'date':'2024-01-02','close':100}])])
def test_provider_errors_are_explicit_and_sanitized(tmp_path,status,payload):
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(status,json=payload)))
    provider = FMPProvider('test-secret', tmp_path, client=client, sleep=lambda _: None)
    with pytest.raises(ProviderError) as error:
        provider.prices('AAPL', date(2024,1,1), date(2024,1,4))
    assert 'test-secret' not in str(error.value)
    assert 'secret-bearing' not in str(error.value)


def test_missing_key_does_not_fall_back_to_demo(monkeypatch,tmp_path):
    monkeypatch.delenv('FMP_API_KEY',raising=False)
    with pytest.raises(ProviderError,match='missing'):
        FMPProvider(cache_dir=tmp_path)

