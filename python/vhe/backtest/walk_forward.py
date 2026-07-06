from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from statistics import mode as stat_mode

import numpy as np
import pandas as pd

from vhe.backtest.engine import EventDrivenBacktester
from vhe.backtest.optimiser import grid_search
from vhe.strategies.adaptive_grid import AdaptiveGridConfig, AdaptiveGridStrategy

_PARAM_GRID: dict = {
    "atr_multiplier": [0.30, 0.45, 0.60],
    "max_levels": [3, 5],
}


@dataclass(frozen=True, slots=True)
class WFWindow:
    period: str
    is_sharpe: float
    oos_sharpe: float
    oos_pnl: float
    best_params: dict


@dataclass(frozen=True, slots=True)
class WFResult:
    windows: list[WFWindow]
    wf_efficiency: float
    verdict: str
    param_stability: dict


def _oos_metrics(
    bars: pd.DataFrame,
    symbol: str,
    params: dict,
    initial_capital: float,
) -> tuple[float, float]:
    strategy = AdaptiveGridStrategy(
        config=AdaptiveGridConfig(
            grid_spacing_atr_multiplier=params["atr_multiplier"],
            max_levels=params["max_levels"],
            symbol_capital=initial_capital * 0.70,
            force_exit_time=time(15, 10),
        ),
        symbol=symbol,
    )
    bt = EventDrivenBacktester(strategy=strategy, initial_cash=initial_capital)
    summary = bt.run(bars)
    trades = bt.ledger.trades
    if not trades:
        return 0.0, round(summary.realized_pnl, 2)
    pnls = np.array([t.pnl for t in trades], dtype=np.float64)
    std = float(pnls.std()) if len(pnls) > 1 else 1.0
    sharpe = float(pnls.mean()) / std if std > 0 else 0.0
    return round(sharpe, 3), round(summary.realized_pnl, 2)


def run(
    bars_df: pd.DataFrame,
    symbol: str,
    train_days: int = 60,
    test_days: int = 15,
    step_days: int = 15,
    initial_capital: float = 75_000.0,
) -> WFResult:
    df = bars_df.copy().sort_values("timestamp").reset_index(drop=True)
    df["_date"] = pd.to_datetime(df["timestamp"]).dt.date
    dates = sorted(df["_date"].unique())

    if len(dates) < train_days + test_days:
        raise ValueError(
            f"need at least {train_days + test_days} trading days, got {len(dates)}"
        )

    windows: list[WFWindow] = []
    i = 0
    while i + train_days + test_days <= len(dates):
        train_dates = set(dates[i : i + train_days])
        test_dates = set(dates[i + train_days : i + train_days + test_days])

        train_bars = df[df["_date"].isin(train_dates)].drop(columns=["_date"]).copy()
        test_bars = df[df["_date"].isin(test_dates)].drop(columns=["_date"]).copy()

        opt = grid_search(train_bars, symbol, _PARAM_GRID, initial_capital)
        oos_sharpe, oos_pnl = _oos_metrics(test_bars, symbol, opt.best_params, initial_capital)

        period_start = min(train_dates)
        period_end = max(train_dates)
        test_start = min(test_dates)
        test_end = max(test_dates)
        period = f"{period_start} to {period_end} | test: {test_start} to {test_end}"

        windows.append(
            WFWindow(
                period=period,
                is_sharpe=round(opt.best_sharpe, 3),
                oos_sharpe=oos_sharpe,
                oos_pnl=oos_pnl,
                best_params=opt.best_params,
            )
        )
        i += step_days

    if not windows:
        raise ValueError("no walk-forward windows were generated")

    is_sharpes = [w.is_sharpe for w in windows]
    oos_sharpes = [w.oos_sharpe for w in windows]
    mean_is = float(np.mean(is_sharpes)) if is_sharpes else 0.0
    mean_oos = float(np.mean(oos_sharpes)) if oos_sharpes else 0.0
    wfe = round(mean_oos / mean_is, 4) if mean_is != 0 else 0.0

    if wfe > 0.5:
        verdict = "Not overfit"
    elif wfe > 0.3:
        verdict = "Marginal"
    else:
        verdict = "Curve-fitted"

    atr_mults = [w.best_params["atr_multiplier"] for w in windows]
    try:
        dominant = stat_mode(atr_mults)
    except Exception:
        dominant = atr_mults[0]
    stability = round(sum(1 for v in atr_mults if v == dominant) / len(atr_mults), 2)

    return WFResult(
        windows=windows,
        wf_efficiency=wfe,
        verdict=verdict,
        param_stability={"atr_multiplier": dominant, "stability_score": stability},
    )
