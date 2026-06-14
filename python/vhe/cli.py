from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from vhe.config.models import AppConfig
from vhe.data.panel import load_history_from_parquet_dir
from vhe.data.service import ingest_nse_bhavcopy
from vhe.live.kite import nse_equity_token_map
from vhe.live.kite_instruments import cache_instruments_csv, load_cached_instruments
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

    kite_cache_parser = subparsers.add_parser("kite-cache-instruments", help="Cache a Kite instruments CSV file locally.")
    kite_cache_parser.add_argument("--csv", type=Path, required=True, help="Path to the Kite instruments CSV file.")
    kite_cache_parser.add_argument("--date", required=True, help="Trading date in YYYY-MM-DD format.")
    kite_cache_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/raw/kite"),
        help="Directory where instrument cache files are stored.",
    )

    kite_tokens_parser = subparsers.add_parser("kite-token-map", help="Print NSE equity instrument tokens for configured symbols.")
    kite_tokens_parser.add_argument("--date", required=True, help="Trading date in YYYY-MM-DD format.")
    kite_tokens_parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("data/raw/kite"),
        help="Directory where instrument cache files are stored.",
    )

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

    if args.command == "kite-cache-instruments":
        payload = args.csv.read_text()
        result = cache_instruments_csv(payload, cache_dir=args.cache_dir, trading_date=date.fromisoformat(args.date))
        print(f"saved={result.path} instruments={len(result.instruments)}")
        return

    if args.command == "kite-token-map":
        result = load_cached_instruments(cache_dir=args.cache_dir, trading_date=date.fromisoformat(args.date))
        token_map = nse_equity_token_map(result.instruments, config.universe.symbols)
        for symbol in sorted(token_map):
            print(f"{symbol}={token_map[symbol]}")
        missing = sorted(set(config.universe.symbols) - set(token_map))
        if missing:
            print(f"missing={','.join(missing)}")
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
