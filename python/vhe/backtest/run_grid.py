from __future__ import annotations

import argparse
from datetime import time
from pathlib import Path

import pandas as pd

from vhe.backtest.engine import EventDrivenBacktester
from vhe.strategies.adaptive_grid import AdaptiveGridConfig, AdaptiveGridStrategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an adaptive grid backtest from OHLCV bars.")
    parser.add_argument("--bars", type=Path, required=True, help="Path to a CSV or parquet file of OHLCV bars.")
    parser.add_argument("--symbol", required=True, help="Symbol to backtest.")
    parser.add_argument("--initial-cash", type=float, default=25_000.0, help="Initial cash in INR.")
    parser.add_argument("--symbol-capital", type=float, default=18_750.0, help="Capital cap for this symbol.")
    parser.add_argument("--force-exit-time", default="15:10", help="Forced exit time as HH:MM.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    bars = _load_bars(args.bars)
    symbol = args.symbol.upper()
    bars = bars[bars["symbol"].astype(str).str.upper() == symbol].copy()
    if bars.empty:
        raise SystemExit(f"no bars found for symbol={symbol}")

    strategy = AdaptiveGridStrategy(
        config=AdaptiveGridConfig(
            symbol_capital=args.symbol_capital,
            force_exit_time=time.fromisoformat(args.force_exit_time),
        ),
        symbol=symbol,
    )
    summary = EventDrivenBacktester(strategy=strategy, initial_cash=args.initial_cash).run(bars)
    print(
        "\n".join(
            [
                f"start_date={summary.start_date}",
                f"end_date={summary.end_date}",
                f"initial_cash={summary.initial_cash:.2f}",
                f"final_equity={summary.final_equity:.2f}",
                f"realized_pnl={summary.realized_pnl:.2f}",
                f"fees_paid={summary.fees_paid:.2f}",
                f"total_trades={summary.total_trades}",
                f"win_rate={summary.win_rate:.2%}",
                f"max_drawdown={summary.max_drawdown:.2%}",
            ]
        )
    )


def _load_bars(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path)
    elif path.suffix.lower() == ".parquet":
        frame = pd.read_parquet(path)
    else:
        raise ValueError(f"unsupported bar file extension: {path.suffix}")

    required_columns = {"timestamp", "symbol", "open", "high", "low", "close", "volume"}
    missing = required_columns - set(frame.columns)
    if missing:
        raise ValueError(f"bars file missing required columns: {sorted(missing)}")
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    return frame


if __name__ == "__main__":
    main()

