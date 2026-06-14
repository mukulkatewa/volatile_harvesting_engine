from datetime import datetime, timedelta

import pandas as pd

from vhe.backtest.run_grid import _load_bars


def test_load_bars_accepts_csv_with_required_columns(tmp_path) -> None:
    path = tmp_path / "bars.csv"
    start = datetime(2026, 6, 14, 9, 15)
    frame = pd.DataFrame(
        [
            {
                "timestamp": start + timedelta(minutes=5),
                "symbol": "AAA",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1000,
            }
        ]
    )
    frame.to_csv(path, index=False)

    loaded = _load_bars(path)

    assert loaded.iloc[0]["symbol"] == "AAA"
    assert pd.api.types.is_datetime64_any_dtype(loaded["timestamp"])

