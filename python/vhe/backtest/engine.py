from __future__ import annotations

from datetime import date

import pandas as pd

from vhe.backtest.fill import ConservativeFillModel
from vhe.backtest.ledger import PortfolioLedger
from vhe.backtest.models import BacktestSummary, MarketBar, PositionSnapshot
from vhe.strategies.adaptive_grid import AdaptiveGridStrategy


class EventDrivenBacktester:
    def __init__(
        self,
        *,
        strategy: AdaptiveGridStrategy,
        initial_cash: float,
        fill_model: ConservativeFillModel | None = None,
    ) -> None:
        self.strategy = strategy
        self.ledger = PortfolioLedger(initial_cash=initial_cash)
        self.fill_model = fill_model or ConservativeFillModel()
        self.snapshots: list[PositionSnapshot] = []

    def run(self, bars: pd.DataFrame) -> BacktestSummary:
        prepared = self.strategy.prepare_history(bars)
        if prepared.empty:
            raise ValueError("cannot backtest an empty bar set")

        peak_equity = self.ledger.initial_cash
        max_drawdown = 0.0

        for _, row in prepared.iterrows():
            bar = MarketBar(
                timestamp=pd.Timestamp(row["timestamp"]).to_pydatetime(),
                symbol=str(row["symbol"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=int(row["volume"]),
            )
            orders = self.strategy.orders_for_bar(bar, row, self.ledger.quantity)
            for order in orders:
                fill = self.fill_model.try_fill(order, bar)
                if fill is None:
                    continue
                self.ledger.apply_fill(fill)
                self.strategy.on_fill_reason(fill.reason)

            equity = self.ledger.mark_to_market(bar.close)
            peak_equity = max(peak_equity, equity)
            drawdown = (peak_equity - equity) / peak_equity if peak_equity else 0.0
            max_drawdown = max(max_drawdown, drawdown)
            self.snapshots.append(
                PositionSnapshot(
                    timestamp=bar.timestamp,
                    symbol=bar.symbol,
                    quantity=self.ledger.quantity,
                    avg_price=self.ledger.avg_price,
                    realized_pnl=self.ledger.realized_pnl,
                    fees_paid=self.ledger.fees_paid,
                    equity=equity,
                )
            )

        first_timestamp = pd.Timestamp(prepared.iloc[0]["timestamp"]).date()
        last_timestamp = pd.Timestamp(prepared.iloc[-1]["timestamp"]).date()
        return BacktestSummary(
            start_date=date.fromisoformat(str(first_timestamp)),
            end_date=date.fromisoformat(str(last_timestamp)),
            initial_cash=self.ledger.initial_cash,
            final_equity=self.ledger.mark_to_market(float(prepared.iloc[-1]["close"])),
            realized_pnl=self.ledger.realized_pnl,
            fees_paid=self.ledger.fees_paid,
            total_trades=len(self.ledger.trades),
            win_rate=self.ledger.win_rate(),
            max_drawdown=max_drawdown,
        )

