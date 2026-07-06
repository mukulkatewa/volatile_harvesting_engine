from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from vhe.backtest.ledger import TradeRecord


@dataclass(slots=True)
class MonteCarloResult:
    var_95: float
    cvar_95: float
    p_ruin: float
    drawdown_p95: float
    kelly_fraction: float
    pnl_percentiles: dict[str, float]
    equity_curves: list[list[float]]
    sim_count: int
    trade_count: int


def run(
    trades: list[TradeRecord],
    initial_capital: float,
    n_sims: int = 10_000,
    rng_seed: int | None = None,
) -> MonteCarloResult:
    if len(trades) < 10:
        raise ValueError(f"need at least 10 trades, got {len(trades)}")
    if n_sims > 100_000:
        raise ValueError("n_sims must be <= 100,000")

    rng = random.Random(rng_seed)
    pnls = [t.pnl for t in trades]

    final_equities: list[float] = []
    max_drawdowns: list[float] = []
    ruin_count = 0
    sampled_curves: list[list[float]] = []

    for i in range(n_sims):
        sample = rng.choices(pnls, k=len(pnls))
        equity = initial_capital
        peak = equity
        max_dd = 0.0
        curve: list[float] = [equity]
        for pnl in sample:
            equity += pnl
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd
            curve.append(equity)
        final_equities.append(equity)
        max_drawdowns.append(max_dd)
        if equity < initial_capital * 0.5:
            ruin_count += 1
        if i < 100:
            sampled_curves.append(curve)

    arr = np.array(final_equities, dtype=np.float64)
    dd_arr = np.array(max_drawdowns, dtype=np.float64)

    var_95 = float(np.percentile(arr, 5))
    tail = arr[arr <= var_95]
    cvar_95 = float(tail.mean()) if tail.size > 0 else var_95

    winners = [t for t in trades if t.pnl > 0]
    losers = [t for t in trades if t.pnl < 0]
    win_rate = len(winners) / len(trades)
    loss_rate = 1.0 - win_rate
    avg_win = sum(t.pnl for t in winners) / len(winners) if winners else 1.0
    avg_loss = abs(sum(t.pnl for t in losers) / len(losers)) if losers else 1.0
    b = avg_win / avg_loss if avg_loss > 0 else 1.0
    kelly = win_rate - loss_rate / b
    kelly = max(0.0, min(0.25, kelly))

    pnl_arr = arr - initial_capital
    return MonteCarloResult(
        var_95=var_95,
        cvar_95=cvar_95,
        p_ruin=ruin_count / n_sims,
        drawdown_p95=float(np.percentile(dd_arr, 95)),
        kelly_fraction=round(kelly, 4),
        pnl_percentiles={
            "p5": float(np.percentile(pnl_arr, 5)),
            "p25": float(np.percentile(pnl_arr, 25)),
            "p50": float(np.percentile(pnl_arr, 50)),
            "p75": float(np.percentile(pnl_arr, 75)),
            "p95": float(np.percentile(pnl_arr, 95)),
        },
        equity_curves=sampled_curves,
        sim_count=n_sims,
        trade_count=len(trades),
    )
