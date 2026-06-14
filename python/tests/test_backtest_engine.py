from datetime import datetime, time, timedelta

import pandas as pd

from vhe.backtest.engine import EventDrivenBacktester
from vhe.strategies.adaptive_grid import AdaptiveGridConfig, AdaptiveGridStrategy


def test_event_driven_backtester_runs_adaptive_grid_round_trip() -> None:
    start = datetime(2026, 6, 14, 9, 15)
    rows = []
    for index in range(120):
        close = 100.4 if index % 2 == 0 else 99.6
        if 90 <= index <= 93:
            close = 96.0
        if 100 <= index <= 104:
            close = 101.0
        rows.append(
            {
                "timestamp": start + timedelta(minutes=5 * index),
                "symbol": "AAA",
                "open": close,
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 10_000,
            }
        )

    bars = pd.DataFrame(rows)
    strategy = AdaptiveGridStrategy(
        config=AdaptiveGridConfig(symbol_capital=10_000, adx_range_threshold=101.0, force_exit_time=time(23, 59)),
        symbol="AAA",
    )
    summary = EventDrivenBacktester(strategy=strategy, initial_cash=25_000).run(bars)

    assert summary.total_trades >= 1
    assert summary.final_equity > 0
    assert summary.fees_paid > 0

