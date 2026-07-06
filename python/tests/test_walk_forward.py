from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from vhe.backtest.walk_forward import WFResult, WFWindow, run


def _bars(n_days: int, symbol: str = "TST") -> pd.DataFrame:
    rows = []
    base = datetime(2025, 1, 2, 9, 15)
    for day in range(n_days):
        day_start = base + timedelta(days=day)
        for minute in range(75):  # 75 five-min bars per day
            close = 100.0 + (minute % 8) - 4.0
            rows.append({
                "timestamp": day_start + timedelta(minutes=5 * minute),
                "symbol": symbol,
                "open": close,
                "high": close + 0.5,
                "low": close - 0.5,
                "close": close,
                "volume": 5_000,
            })
    return pd.DataFrame(rows)


def test_run_returns_wf_result() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert isinstance(result, WFResult)
    assert len(result.windows) >= 1
    assert all(isinstance(w, WFWindow) for w in result.windows)


def test_window_count_is_correct() -> None:
    bars = _bars(n_days=40)
    result = run(bars, "TST", train_days=20, test_days=5, step_days=5, initial_capital=25_000.0)
    assert len(result.windows) >= 2


def test_wf_efficiency_is_float_between_neg_and_pos() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert isinstance(result.wf_efficiency, float)


def test_verdict_is_valid_string() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert result.verdict in {"Not overfit", "Marginal", "Curve-fitted"}


def test_param_stability_contains_atr_key() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    assert "atr_multiplier" in result.param_stability
    assert "stability_score" in result.param_stability
    assert 0.0 <= result.param_stability["stability_score"] <= 1.0


def test_raises_when_not_enough_bars() -> None:
    bars = _bars(n_days=5)
    with pytest.raises(ValueError, match="need at least"):
        run(bars, "TST", train_days=20, test_days=10, step_days=5, initial_capital=25_000.0)


def test_window_fields_present() -> None:
    bars = _bars(n_days=30)
    result = run(bars, "TST", train_days=15, test_days=5, step_days=5, initial_capital=25_000.0)
    w = result.windows[0]
    assert isinstance(w.period, str)
    assert isinstance(w.is_sharpe, float)
    assert isinstance(w.oos_sharpe, float)
    assert isinstance(w.oos_pnl, float)
    assert "atr_multiplier" in w.best_params
    assert "max_levels" in w.best_params
