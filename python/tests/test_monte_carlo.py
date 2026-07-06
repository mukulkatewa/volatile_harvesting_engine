from __future__ import annotations

import pytest

from vhe.backtest.ledger import TradeRecord
from vhe.backtest.monte_carlo import MonteCarloResult, run


def _trades(n_win: int, win_pnl: float, n_lose: int, lose_pnl: float) -> list[TradeRecord]:
    wins = [TradeRecord(entry_price=100.0, exit_price=100.0, quantity=1, pnl=win_pnl, fees=0.0) for _ in range(n_win)]
    losses = [TradeRecord(entry_price=100.0, exit_price=100.0, quantity=1, pnl=lose_pnl, fees=0.0) for _ in range(n_lose)]
    return wins + losses


def test_run_returns_result_dataclass() -> None:
    result = run(_trades(8, 100.0, 2, -50.0), initial_capital=10_000, n_sims=500, rng_seed=42)
    assert isinstance(result, MonteCarloResult)
    assert result.sim_count == 500
    assert result.trade_count == 10


def test_positive_edge_low_ruin_probability() -> None:
    result = run(_trades(8, 100.0, 2, -50.0), initial_capital=10_000, n_sims=1000, rng_seed=42)
    assert result.p_ruin < 0.05
    assert result.pnl_percentiles["p50"] > 0


def test_negative_edge_high_ruin_probability() -> None:
    # worst case: 8 × (-1000) = -8000 loss → equity = 2000, well below 5000 ruin floor
    result = run(_trades(2, 500.0, 8, -1000.0), initial_capital=10_000, n_sims=1000, rng_seed=42)
    assert result.p_ruin > 0.30


def test_kelly_clamps_to_zero_when_losing() -> None:
    result = run(_trades(1, 10.0, 9, -100.0), initial_capital=10_000, n_sims=500, rng_seed=0)
    assert result.kelly_fraction == 0.0


def test_kelly_clamps_to_max_025() -> None:
    result = run(_trades(10, 1000.0, 1, -1.0), initial_capital=10_000, n_sims=500, rng_seed=0)
    assert result.kelly_fraction <= 0.25


def test_raises_on_fewer_than_10_trades() -> None:
    with pytest.raises(ValueError, match="need at least 10 trades"):
        run(_trades(4, 100.0, 5, -50.0), initial_capital=10_000)


def test_equity_curves_at_most_100() -> None:
    result = run(_trades(6, 80.0, 4, -60.0), initial_capital=10_000, n_sims=500, rng_seed=1)
    assert len(result.equity_curves) <= 100
    assert len(result.equity_curves) > 0


def test_var_below_median_for_positive_edge() -> None:
    result = run(_trades(7, 80.0, 3, -60.0), initial_capital=10_000, n_sims=2000, rng_seed=7)
    # var_95 is the 5th-percentile equity; median equity should be higher
    assert result.var_95 <= result.pnl_percentiles["p50"] + 10_000


def test_pnl_percentiles_keys_present() -> None:
    result = run(_trades(5, 100.0, 5, -80.0), initial_capital=10_000, n_sims=500, rng_seed=3)
    assert set(result.pnl_percentiles.keys()) == {"p5", "p25", "p50", "p75", "p95"}


def test_cvar_le_var() -> None:
    result = run(_trades(5, 100.0, 5, -80.0), initial_capital=10_000, n_sims=1000, rng_seed=5)
    assert result.cvar_95 <= result.var_95 + 1.0  # CVaR (expected shortfall) ≤ VaR
