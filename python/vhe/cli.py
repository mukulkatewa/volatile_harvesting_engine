from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from vhe.config.models import AppConfig
from vhe.data.panel import load_history_from_parquet_dir
from vhe.data.service import ingest_nse_bhavcopy
from vhe.scanner.daily import build_candidate_report



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vhe", description="Volatility Harvesting Engine CLI")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/app.yaml"),
        help="Path to the application config file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    ingest_parser = subparsers.add_parser("data-ingest-nse", help="Download and store NSE bhavcopy data.")
    ingest_parser.add_argument("--date", required=True, help="Trading date in YYYY-MM-DD format.")
    ingest_parser.add_argument(
        "--output-subdir",
        default="nse_bhavcopy",
        help="Subdirectory under raw_data_dir where the file will be stored.",
    )

    scan_parser = subparsers.add_parser("scan-daily", help="Rank symbols from stored daily bhavcopy history.")
    scan_parser.add_argument("--as-of", required=True, help="Scanner date in YYYY-MM-DD format.")
    scan_parser.add_argument(
        "--bhavcopy-dir",
        type=Path,
        default=None,
        help="Directory containing bhavcopy parquet files. Defaults to data/raw/nse_bhavcopy.",
    )
    scan_parser.add_argument("--top-n", type=int, default=10, help="Number of candidates to print.")

    return parser



def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = AppConfig.from_yaml(args.config)

    if args.command == "data-ingest-nse":
        result = ingest_nse_bhavcopy(config=config, trading_date=args.date, output_subdir=args.output_subdir)
        print(f"saved={result.output_path} rows={result.rows}")
        return

    if args.command == "scan-daily":
        bhavcopy_dir = args.bhavcopy_dir or (config.paths.raw_data_dir / "nse_bhavcopy")
        history = load_history_from_parquet_dir(bhavcopy_dir, symbols=config.universe.symbols or None)
        report = build_candidate_report(
            history,
            as_of=date.fromisoformat(args.as_of),
            min_close_price_inr=config.data.min_close_price_inr,
            min_turnover_inr=config.data.turnover_threshold_inr,
            max_gap_pct=5.0,
            top_n=args.top_n,
        )
        if report.empty:
            print("no candidates matched the current filters")
            return

        display_columns = [
            "symbol",
            "close",
            "atr_pct",
            "adx_14",
            "avg_turnover_20d",
            "gap_pct",
            "candidate_score",
        ]
        print(report[display_columns].to_string(index=False))
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
