from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from vhe.config.env import load_env_file
from vhe.config.models import AppConfig
from vhe.data.panel import load_history_from_parquet_dir
from vhe.data.service import ingest_nse_bhavcopy
from vhe.live.kite import nse_equity_token_map
from vhe.live.kite_auth import kite_login_url, load_kite_api_key, load_kite_credentials, load_kite_exchange_credentials
from vhe.live.kite_instruments import KiteAuth, KiteInstrumentClient, cache_instruments_csv, load_cached_instruments
from vhe.live.kite_session import KiteSessionClient
from vhe.config.loader import BrokerConfig
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

    kite_login_parser = subparsers.add_parser("kite-login-url", help="Print the Zerodha login URL for today's access token.")
    kite_login_parser.add_argument("--redirect-url", default="http://127.0.0.1", help="Redirect URL configured in the Kite app.")

    kite_exchange_parser = subparsers.add_parser("kite-exchange-token", help="Exchange a request_token for an access_token.")
    kite_exchange_parser.add_argument("--request-token", required=True, help="request_token from the login redirect URL.")

    kite_download_parser = subparsers.add_parser("kite-download-instruments", help="Download and cache today's Kite instrument master.")
    kite_download_parser.add_argument("--date", default=None, help="Trading date YYYY-MM-DD (default: today).")
    kite_download_parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/kite"))

    return parser



def main() -> None:
    load_env_file()
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

    if args.command == "kite-login-url":
        broker = BrokerConfig()
        api_key = load_kite_api_key(broker)
        print(kite_login_url(api_key, redirect_url=args.redirect_url))
        print("After login, copy request_token from the redirect URL and run:")
        print("  vhe kite-exchange-token --request-token <token>")
        return

    if args.command == "kite-exchange-token":
        broker = BrokerConfig()
        credentials = load_kite_exchange_credentials(broker)
        session = KiteSessionClient(credentials).exchange_request_token(args.request_token)
        print(f"access_token={session.access_token}")
        print(f"user_id={session.user_id}")
        print(f"login_time={session.login_time}")
        print(f"export {broker.access_token_env}={session.access_token}")
        return

    if args.command == "kite-download-instruments":
        broker = BrokerConfig()
        credentials = load_kite_credentials(broker)
        as_of = date.fromisoformat(args.date) if args.date else date.today()
        client = KiteInstrumentClient(KiteAuth(credentials.api_key, credentials.access_token))
        result = cache_instruments_csv(client.download_csv(), cache_dir=args.cache_dir, trading_date=as_of)
        print(f"saved={result.path} instruments={len(result.instruments)}")
        return

    parser.error(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
