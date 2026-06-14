from __future__ import annotations

from dataclasses import dataclass

from vhe.backtest.costs import EquityIntradayCostModel
from vhe.backtest.models import Fill, MarketBar, Order, OrderSide, OrderType


@dataclass(frozen=True, slots=True)
class ConservativeFillModel:
    slippage_bps: float = 2.0
    volume_participation_cap: float = 0.05
    require_price_improvement: bool = True
    cost_model: EquityIntradayCostModel = EquityIntradayCostModel()

    def try_fill(self, order: Order, bar: MarketBar) -> Fill | None:
        if order.order_type == OrderType.MARKET:
            fill_price = self._apply_slippage(bar.open, order.side)
            return self._build_fill(order=order, bar=bar, fill_price=fill_price)

        if order.side == OrderSide.BUY:
            threshold = self._remove_slippage(order.price, order.side)
            touched = bar.low < threshold if self.require_price_improvement else bar.low <= order.price
        else:
            threshold = self._remove_slippage(order.price, order.side)
            touched = bar.high > threshold if self.require_price_improvement else bar.high >= order.price

        if not touched:
            return None

        fill_price = self._apply_slippage(order.price, order.side)
        return self._build_fill(order=order, bar=bar, fill_price=fill_price)

    def _build_fill(self, *, order: Order, bar: MarketBar, fill_price: float) -> Fill | None:
        max_quantity = max(int(bar.volume * self.volume_participation_cap), 1)
        quantity = min(order.quantity, max_quantity)
        if quantity <= 0:
            return None

        fees = self.cost_model.estimate(side=order.side, price=fill_price, quantity=quantity)
        return Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            price=fill_price,
            quantity=quantity,
            timestamp=bar.timestamp,
            fees=fees,
            reason=order.reason,
        )

    def _apply_slippage(self, price: float, side: OrderSide) -> float:
        adjustment = self.slippage_bps / 10_000
        return price * (1 + adjustment) if side == OrderSide.BUY else price * (1 - adjustment)

    def _remove_slippage(self, price: float, side: OrderSide) -> float:
        adjustment = self.slippage_bps / 10_000
        return price * (1 - adjustment) if side == OrderSide.BUY else price * (1 + adjustment)

