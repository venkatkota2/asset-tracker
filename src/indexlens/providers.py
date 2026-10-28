"""FMP stable REST adapter. Secrets and raw prices never enter public reports."""

from datetime import date
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile
import time
import httpx
import pandas as pd

from .data import Dataset


class ProviderError(RuntimeError):
    """Sanitized error: provider response URLs may contain credentials."""


class FMPProvider:
    BASE = "https://financialmodelingprep.com/stable"
    SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")

    def __init__(self, api_key: str | None = None, cache_dir: str | Path = ".cache/fmp",
                 ttl_hours: float = 24, requests_per_minute: int = 120,
                 client: httpx.Client | None = None, sleep=time.sleep):
        self.api_key = api_key or os.getenv("FMP_API_KEY", "")
        if not self.api_key:
            raise ProviderError("FMP_API_KEY is missing. Configure it server-side or run explicit demo mode.")
        if not 1 <= requests_per_minute <= 3000 or ttl_hours < 0:
            raise ValueError("Invalid provider cache or request-rate configuration.")
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_hours * 3600
        self.interval = 60 / requests_per_minute
        self.client = client or httpx.Client(timeout=30, follow_redirects=False)
        self.owns_client = client is None
        self.sleep = sleep
        self.last_request = 0.0

    def close(self):
        if self.owns_client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _get(self, endpoint: str, params: dict | None = None) -> list:
        params = params or {}
        cache_id = hashlib.sha256(json.dumps([endpoint, params], sort_keys=True).encode()).hexdigest()
        path = self.cache / f"{cache_id}.json"
        if path.exists() and time.time() - path.stat().st_mtime < self.ttl:
            try:
                cached = json.loads(path.read_text())
                if isinstance(cached, list):
                    return cached
            except (ValueError, OSError):
                pass
        for attempt in range(4):
            self.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.client.get(f"{self.BASE}/{endpoint}",
                                           params={**params, "apikey": self.api_key})
            except httpx.RequestError:
                if attempt == 3:
                    raise ProviderError("Market-data request failed after four attempts.") from None
                self.sleep(2**attempt)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    raise ProviderError("Market-data service is rate-limited or unavailable; existing report was preserved.")
                try:
                    delay = min(60, max(0, float(response.headers.get("Retry-After", 2**attempt))))
                except ValueError:
                    delay = 2**attempt
                self.sleep(delay)
                continue
            if response.status_code != 200:
                raise ProviderError(f"FMP HTTP {response.status_code}. Check API-key access and plan entitlements.")
            try:
                payload = response.json()
            except ValueError:
                raise ProviderError("Market-data provider returned invalid JSON.") from None
            if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
                raise ProviderError("Unexpected market-data response. Check plan access or quota.")
            with tempfile.NamedTemporaryFile(mode="w", dir=self.cache, delete=False) as tmp:
                json.dump(payload, tmp)
                temporary = Path(tmp.name)
            temporary.replace(path)
            return payload
        raise ProviderError("Market-data request failed.")

    def prices(self, symbol: str, start: date, end: date) -> pd.Series:
        if not self.SYMBOL.fullmatch(symbol):
            raise ProviderError("Provider returned an unsupported symbol format.")
        rows = self._get("historical-price-eod/dividend-adjusted",
                         {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()})
        if not rows:
            return pd.Series(dtype=float, name=symbol, index=pd.DatetimeIndex([]))
        frame = pd.DataFrame(rows)
        if not {"date", "adjClose"}.issubset(frame.columns):
            raise ProviderError("Adjusted-close field is missing; refusing to mix raw and adjusted prices.")
        try:
            dates = pd.to_datetime(frame["date"], errors="raise")
            values = pd.to_numeric(frame["adjClose"], errors="raise")
        except (ValueError, TypeError):
            raise ProviderError("Provider returned malformed price observations.") from None
        series = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name=symbol)
        if series.index.has_duplicates:
            raise ProviderError("Provider returned duplicate price dates.")
        return series.sort_index().loc[start.isoformat():end.isoformat()]

    def dataset(self, start: date, end: date, benchmark: str = "SPY") -> Dataset:
        if start >= end:
            raise ValueError("Start date must precede end date.")
        constituents = self._get("sp500-constituent")
        if not 450 <= len(constituents) <= 550:
            raise ProviderError("Unexpected S&P 500 universe size; refusing a silently incomplete universe.")
        assets = {}
        for row in constituents:
            symbol = row.get("symbol", "")
            if not self.SYMBOL.fullmatch(symbol) or symbol in assets or symbol == benchmark:
                raise ProviderError("Invalid or duplicate symbol in constituent universe.")
            assets[symbol] = {"name": str(row.get("name", symbol)),
                              "sector": str(row.get("sector", "Unclassified"))}
        series = [self.prices(benchmark, start, end)]
        if series[0].empty:
            raise ProviderError("Benchmark has no observations in the requested period.")
        for symbol in sorted(assets):
            series.append(self.prices(symbol, start, end))
        panel = pd.concat(series, axis=1)
        return Dataset(panel, assets, benchmark, "Financial Modeling Prep stable API", "market",
                       date.today().isoformat(), [
                           "SPY adjusted prices approximate S&P 500 total returns; fund fees and tracking differences remain.",
                           "Current constituents are used retrospectively. Survivorship and complete-history selection bias remain; this is not a point-in-time investment backtest.",
                           "Historical test-start weights are shown, not a current trade recommendation.",
                       ])

