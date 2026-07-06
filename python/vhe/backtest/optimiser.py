from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import time
from itertools import product

import numpy as np
import pandas as pd

from vhe.backtest.engine import EventDrivenBacktester
from vhe.strategies.adaptive_grid import AdaptiveGridConfig, AdaptiveGridStrategy


@dataclass(frozen=True, slots=True)
class OptimiseResult:
    best_params: dict
    best_sharpe: float


def _sharpe_for_params(
    bars: pd.DataFrame,
    symbol: str,
    params: dict,
    initial_capital: float,
) -> tuple[dict, float]:
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
    bt.run(bars)
    trades = bt.ledger.trades
    if not trades:
        return params, -999.0
    pnls = np.array([t.pnl for t in trades], dtype=np.float64)
    std = float(pnls.std()) if len(pnls) > 1 else 1.0
    sharpe = float(pnls.mean()) / std if std > 0 else 0.0
    return params, sharpe


def grid_search(
    bars: pd.DataFrame,
    symbol: str,
    param_grid: dict,
    initial_capital: float = 75_000.0,
) -> OptimiseResult:
    keys = list(param_grid.keys())
    combos = [dict(zip(keys, vals)) for vals in product(*param_grid.values())]

    best_params = combos[0]
    best_sharpe = -999.0

    with ThreadPoolExecutor(max_workers=min(len(combos), 4)) as pool:
        futures = {
            pool.submit(_sharpe_for_params, bars, symbol, p, initial_capital): p
            for p in combos
        }
        for future in as_completed(futures):
            params, sharpe = future.result()
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_params = params

    return OptimiseResult(best_params=best_params, best_sharpe=round(best_sharpe, 4))
