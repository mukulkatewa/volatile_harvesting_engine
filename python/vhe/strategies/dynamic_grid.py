from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.live.models import LiveQuote
from vhe.strategies.regime import MarketRegime


@dataclass(frozen=True, slots=True)
class DynamicGridConfig:
    atr_multiplier: float = 0.35
    max_levels: int = 5
    symbol_capital: float = 18_750.0
    no_buy_above_fair_value_pct: float = 0.03
    min_spacing: float = 0.05
    fill_tolerance_pct: float = 0.0
    seed_deploy_pct: float = 0.0
    level_capital_multiplier: float = 1.0


@dataclass(frozen=True, slots=True)
class DynamicGridInputs:
    quote: LiveQuote
    fair_value: float
    atr_14: float
    regime: MarketRegime
    current_quantity: int = 0


@dataclass(slots=True)
class DynamicGridPlan:
    symbol: str
    fair_value: float
    spacing: float
    regime: MarketRegime
    buy_levels: list[float]
    sell_target: float | None
    reset_reason: str | None = None


@dataclass(slots=True)
class DynamicGridStrategy:
    config: DynamicGridConfig = field(default_factory=DynamicGridConfig)
    _last_grid_center: dict[str, float] = field(default_factory=dict)
    _seeded_symbols: set[str] = field(default_factory=set)
    _order_sequence: int = 0

    def reset_session(self) -> None:
        self._last_grid_center.clear()
        self._seeded_symbols.clear()
        self._order_sequence = 0

    def build_plan(self, inputs: DynamicGridInputs) -> DynamicGridPlan:
        quote = inputs.quote
        spacing = max(inputs.atr_14 * self.config.atr_multiplier, self.config.min_spacing)
        reset_reason = self._reset_reason(symbol=quote.symbol, fair_value=inputs.fair_value, spacing=spacing)
        self._last_grid_center[quote.symbol] = inputs.fair_value

        if inputs.regime != MarketRegime.RANGE:
            return DynamicGridPlan(
                symbol=quote.symbol,
                fair_value=inputs.fair_value,
                spacing=round(spacing, 2),
                regime=inputs.regime,
                buy_levels=[],
                sell_target=round(inputs.fair_value, 2) if inputs.current_quantity > 0 else None,
                reset_reason=reset_reason or "regime_not_range",
            )

        if quote.ltp > inputs.fair_value * (1 + self.config.no_buy_above_fair_value_pct):
            return DynamicGridPlan(
                symbol=quote.symbol,
                fair_value=inputs.fair_value,
                spacing=round(spacing, 2),
                regime=inputs.regime,
                buy_levels=[],
                sell_target=round(inputs.fair_value, 2) if inputs.current_quantity > 0 else None,
                reset_reason=reset_reason or "price_above_fair_value_band",
            )

        buy_levels = [round(inputs.fair_value - spacing * level, 2) for level in range(1, self.config.max_levels + 1)]
        return DynamicGridPlan(
            symbol=quote.symbol,
            fair_value=round(inputs.fair_value, 2),
            spacing=round(spacing, 2),
            regime=inputs.regime,
            buy_levels=buy_levels,
            sell_target=round(inputs.fair_value, 2) if inputs.current_quantity > 0 else None,
            reset_reason=reset_reason,
        )

    def orders_from_plan(self, plan: DynamicGridPlan, quote: LiveQuote, *, current_quantity: int = 0) -> list[Order]:
        orders: list[Order] = []
        level_capital = (self.config.symbol_capital / self.config.max_levels) * self.config.level_capital_multiplier
        tolerance = 1.0 + self.config.fill_tolerance_pct

        if (
            self.config.seed_deploy_pct > 0
            and current_quantity == 0
            and plan.buy_levels
            and plan.regime == MarketRegime.RANGE
            and quote.symbol not in self._seeded_symbols
        ):
            deploy_capital = self.config.symbol_capital * self.config.seed_deploy_pct
            quantity = max(int(deploy_capital // quote.ltp), 1)
            orders.append(
                self._order(
                    quote.timestamp,
                    quote.symbol,
                    OrderSide.BUY,
                    quote.ltp,
                    quantity,
                    "dynamic_grid_seed_deploy",
                )
            )
            self._seeded_symbols.add(quote.symbol)

        for level_index, price in enumerate(plan.buy_levels, start=1):
            if quote.ltp <= price * tolerance:
                quantity = max(int(level_capital // price), 1)
                orders.append(
                    self._order(quote.timestamp, quote.symbol, OrderSide.BUY, price, quantity, f"dynamic_grid_level_{level_index}")
                )

        if plan.sell_target is not None and quote.ltp >= plan.sell_target and current_quantity > 0:
            orders.append(
                self._order(
                    quote.timestamp,
                    quote.symbol,
                    OrderSide.SELL,
                    plan.sell_target,
                    current_quantity,
                    "dynamic_grid_mean_exit",
                )
            )

        return orders

    def _reset_reason(self, *, symbol: str, fair_value: float, spacing: float) -> str | None:
        previous = self._last_grid_center.get(symbol)
        if previous is None:
            return "initial_grid"
        if abs(fair_value - previous) >= spacing:
            return "fair_value_shift"
        return None

    def _order(self, timestamp: datetime, symbol: str, side: OrderSide, price: float, quantity: int, reason: str) -> Order:
        self._order_sequence += 1
        return Order(
            order_id=f"dg-{symbol}-{self._order_sequence}",
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=quantity,
            created_at=timestamp,
            reason=reason,
        )
