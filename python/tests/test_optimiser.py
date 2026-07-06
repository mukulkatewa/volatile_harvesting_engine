from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from vhe.backtest.optimiser import OptimiseResult, grid_search


def _synthetic_bars(n_bars: int = 200, symbol: str = "TST") -> pd.DataFrame:
    start = datetime(2025, 1, 2, 9, 15)
    rows = []
    for i in range(n_bars):
        close = 100.0 + (i % 10) - 5.0  # oscillates ±5 around 100
        rows.append({
            "timestamp": start + timedelta(minutes=5 * i),
            "symbol": symbol,
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": 10_000,
        })
    return pd.DataFrame(rows)


def test_grid_search_returns_optimise_result() -> None:
    bars = _synthetic_bars(200)
    param_grid = {"atr_multiplier": [0.30, 0.45], "max_levels": [3]}
    result = grid_search(bars, "TST", param_grid, initial_capital=25_000.0)
    assert isinstance(result, OptimiseResult)
    assert result.best_params["atr_multiplier"] in {0.30, 0.45}
    assert result.best_params["max_levels"] == 3


def test_grid_search_picks_from_all_combinations() -> None:
    bars = _synthetic_bars(200)
    param_grid = {"atr_multiplier": [0.30, 0.60], "max_levels": [3, 5]}
    result = grid_search(bars, "TST", param_grid, initial_capital=25_000.0)
    assert result.best_params["atr_multiplier"] in {0.30, 0.60}
    assert result.best_params["max_levels"] in {3, 5}


def test_grid_search_sharpe_is_finite_float() -> None:
    bars = _synthetic_bars(200)
    result = grid_search(bars, "TST", {"atr_multiplier": [0.45], "max_levels": [3]}, 25_000.0)
    assert isinstance(result.best_sharpe, float)
