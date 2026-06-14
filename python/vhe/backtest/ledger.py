from __future__ import annotations

from dataclasses import dataclass, field

from vhe.backtest.models import Fill, OrderSide


@dataclass(slots=True)
class TradeRecord:
    entry_price: float
    exit_price: float
    quantity: int
    pnl: float
    fees: float


@dataclass(slots=True)
class PortfolioLedger:
    initial_cash: float
    cash: float = field(init=False)
    quantity: int = 0
    avg_price: float = 0.0
    realized_pnl: float = 0.0
    fees_paid: float = 0.0
    trades: list[TradeRecord] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.cash = self.initial_cash

    def apply_fill(self, fill: Fill) -> None:
        self.fees_paid += fill.fees
        if fill.side == OrderSide.BUY:
            total_cost = fill.price * fill.quantity
            new_quantity = self.quantity + fill.quantity
            self.avg_price = ((self.avg_price * self.quantity) + total_cost) / new_quantity
            self.quantity = new_quantity
            self.cash -= total_cost + fill.fees
            return

        sell_quantity = min(fill.quantity, self.quantity)
        if sell_quantity <= 0:
            return

        gross_pnl = (fill.price - self.avg_price) * sell_quantity
        net_pnl = gross_pnl - fill.fees
        self.realized_pnl += net_pnl
        self.cash += fill.price * sell_quantity - fill.fees
        self.quantity -= sell_quantity
        self.trades.append(
            TradeRecord(
                entry_price=self.avg_price,
                exit_price=fill.price,
                quantity=sell_quantity,
                pnl=net_pnl,
                fees=fill.fees,
            )
        )
        if self.quantity == 0:
            self.avg_price = 0.0

    def mark_to_market(self, last_price: float) -> float:
        return self.cash + self.quantity * last_price

    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        winners = sum(1 for trade in self.trades if trade.pnl > 0)
        return winners / len(self.trades)

