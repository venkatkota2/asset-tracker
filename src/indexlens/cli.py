"""Explicit data mode, fail-closed refresh, and atomic report publishing."""

import argparse
from datetime import date, timedelta
import json
import os
from pathlib import Path
import tempfile

from .data import demo_dataset
from .providers import FMPProvider, ProviderError
from .report import build_report


def write_report(report: dict, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, suffix=".tmp", delete=False) as file:
        json.dump(report, file, separators=(",", ":"), allow_nan=False)
        temporary = Path(file.name)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description="Build an IndexLens portfolio frontier.")
    parser.add_argument("command", choices=["build"])
    parser.add_argument("--provider", choices=["demo", "fmp"], required=True)
    parser.add_argument("--output", type=Path, default=Path("web/data/report.json"))
    parser.add_argument("--start", type=date.fromisoformat, default=date.today() - timedelta(days=365*4))
    # Exclude today's possibly unfinished daily observation.
    parser.add_argument("--end", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--cost-bps", type=float, default=5)
    parser.add_argument("--max-weight", type=float, default=.25)
    args = parser.parse_args()
    try:
        if args.provider == "demo":
            dataset = demo_dataset()
        else:
            with FMPProvider(requests_per_minute=int(os.getenv("FMP_REQUESTS_PER_MINUTE", "120"))) as provider:
                dataset = provider.dataset(args.start, args.end)
        report = build_report(dataset, max_weight=args.max_weight, cost_bps=args.cost_bps)
        write_report(report, args.output)
    except (ProviderError, ValueError, RuntimeError) as error:
        parser.exit(1, f"Build failed: {error}\nNo replacement report was published.\n")
    chosen = next(p for p in report["portfolios"] if p["budget"] == report["recommended_budget"])
    print(f"Saved {args.output}: {report['dataset']['kind']} data, {chosen['holding_count']} holdings, "
          f"test tracking error {chosen['test']['tracking_error']:.2%}.")


if __name__ == "__main__":
    main()

