from __future__ import annotations

import argparse
from pathlib import Path

from vhe.config.models import AppConfig
from vhe.data.service import ingest_nse_bhavcopy


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

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = AppConfig.from_yaml(args.config)

    if args.command == "data-ingest-nse":
        result = ingest_nse_bhavcopy(config=config, trading_date=args.date, output_subdir=args.output_subdir)
        print(f"saved={result.output_path} rows={result.rows}")
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()

