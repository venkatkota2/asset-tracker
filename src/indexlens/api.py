"""FastAPI serves published results and, when available, the same web interface.

Network ingestion runs in a controlled CLI/job, not in visitor requests. This
keeps provider credentials private and avoids a public endpoint exhausting quota.
"""

from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(title="IndexLens API", version="0.1.0",
              description="Sparse S&P 500 replication; precomputed, versioned research results.")
origins = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:8000").split(",") if v.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"], allow_credentials=False)
REPORT_PATH = Path(os.getenv("INDEXLENS_REPORT", "web/data/report.json"))


@lru_cache(maxsize=4)
def _load(path: str, modified: int) -> dict:
    return json.loads(Path(path).read_text())


def report() -> dict:
    try:
        return _load(str(REPORT_PATH), REPORT_PATH.stat().st_mtime_ns)
    except (OSError, ValueError):
        raise HTTPException(503, "Report unavailable. Run the Python build command first.") from None


@app.get("/api/health")
def health():
    return {"status": "ok", "report_available": REPORT_PATH.exists()}


@app.get("/api/benchmarks")
def benchmarks():
    return {"benchmarks": [{"id": "sp500", "name": "S&P 500", "market_proxy": "SPY"}]}


@app.get("/api/report")
def get_report():
    return report()


class PortfolioRequest(BaseModel):
    benchmark: Literal["sp500"] = "sp500"
    max_holdings: int | None = Field(default=None, ge=5, le=60)
    capital: float = Field(default=10000, gt=0, le=1e12, allow_inf_nan=False)


@app.post("/api/portfolio")
def get_portfolio(request: PortfolioRequest):
    data = report()
    budget = request.max_holdings or data["recommended_budget"]
    candidates = [p for p in data["portfolios"] if p["budget"] == budget]
    if not candidates:
        raise HTTPException(422, "Choose one of the published holding budgets: " +
                            ", ".join(str(p["budget"]) for p in data["portfolios"]))
    portfolio = candidates[0]
    return {"dataset_kind": data["dataset"]["kind"], "weights_as_of": data["model"]["weights_as_of"],
            "portfolio": portfolio,
            "allocations": [{"symbol": h["symbol"], "amount": round(request.capital * h["weight"], 2)}
                            for h in portfolio["holdings"]]}


WEB_ROOT = Path(os.getenv("INDEXLENS_WEB_ROOT", "web"))
if WEB_ROOT.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_ROOT), html=True), name="frontend")

