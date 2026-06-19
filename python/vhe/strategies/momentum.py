from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.live.models import LiveQuote
from vhe.strategies.regime import MarketRegime


@dataclass(frozen=True, slots=True)
class MomentumConfig:
    risk_per_trade: float = 62.5
    atr_stop_multiplier: float = 1.0
    breakout_buffer_pct: float = 0.002
    max_capital_per_trade: float = 6_250.0


@dataclass(frozen=True, slots=True)
class MomentumInputs:
    quote: LiveQuote
    regime: MarketRegime
    ema_20: float
    ema_50: float
    atr_14: float
    current_quantity: int = 0
    sentiment_score: float = 0.0
    sentiment_allows_entry: bool = True


@dataclass(slots=True)
class MomentumPlan:
    symbol: str
    enabled: bool
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    reason: str


@dataclass(slots=True)
class MomentumStrategy:
    config: MomentumConfig = field(default_factory=MomentumConfig)
    _order_sequence: int = 0

    def build_plan(self, inputs: MomentumInputs) -> MomentumPlan:
        quote = inputs.quote
        if inputs.regime != MarketRegime.TREND_UP:
            return MomentumPlan(quote.symbol, False, None, None, None, "regime_not_trend_up")
        if not inputs.sentiment_allows_entry:
            return MomentumPlan(quote.symbol, False, None, None, None, "sentiment_blocked")
        if inputs.current_quantity > 0:
            return MomentumPlan(quote.symbol, False, None, None, None, "position_already_open")
        if not (quote.ltp > inputs.ema_20 > inputs.ema_50):
            return MomentumPlan(quote.symbol, False, None, None, None, "ema_stack_not_bullish")

        entry = quote.high * (1 + self.config.breakout_buffer_pct)
        stop = entry - inputs.atr_14 * self.config.atr_stop_multiplier
        target = entry + inputs.atr_14 * 1.5
        return MomentumPlan(
            symbol=quote.symbol,
            enabled=True,
            entry_price=round(entry, 2),
            stop_price=round(stop, 2),
            target_price=round(target, 2),
            reason="trend_up_breakout",
        )

    def orders_from_plan(self, plan: MomentumPlan, quote: LiveQuote) -> list[Order]:
        if not plan.enabled or plan.entry_price is None:
            return []
        if quote.ltp < plan.entry_price:
            return []
        risk_per_share = max(plan.entry_price - (plan.stop_price or plan.entry_price), 0.01)
        risk_quantity = int(self.config.risk_per_trade // risk_per_share)
        capital_quantity = int(self.config.max_capital_per_trade // plan.entry_price)
        quantity = max(min(risk_quantity, capital_quantity), 1)
        return [self._order(quote.timestamp, quote.symbol, plan.entry_price, quantity, plan.reason)]

    def _order(self, timestamp: datetime, symbol: str, price: float, quantity: int, reason: str) -> Order:
        self._order_sequence += 1
        return Order(
            order_id=f"mo-{symbol}-{self._order_sequence}",
            symbol=symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=quantity,
            created_at=timestamp,
            reason=reason,
        )
