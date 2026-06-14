from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time

import pandas as pd

from vhe.backtest.models import MarketBar, Order, OrderSide, OrderType
from vhe.indicators.trend import adx, atr, ema


@dataclass(frozen=True, slots=True)
class AdaptiveGridConfig:
    grid_spacing_atr_multiplier: float = 0.35
    max_levels: int = 5
    symbol_capital: float = 18_750.0
    force_exit_time: time = time(15, 10)
    no_buy_above_fair_value_pct: float = 0.03
    adx_range_threshold: float = 20.0
    min_quantity: int = 1


@dataclass(slots=True)
class AdaptiveGridStrategy:
    config: AdaptiveGridConfig
    symbol: str
    _filled_levels: set[int] = field(default_factory=set)
    _order_sequence: int = 0

    def prepare_history(self, bars: pd.DataFrame) -> pd.DataFrame:
        frame = bars.copy().sort_values("timestamp").reset_index(drop=True)
        frame["atr_14"] = atr(frame, period=14)
        frame["adx_14"] = adx(frame, period=14)
        frame["ema_50"] = ema(frame["close"], span=50)
        return frame

    def orders_for_bar(self, bar: MarketBar, row: pd.Series, current_quantity: int) -> list[Order]:
        if bar.timestamp.time() >= self.config.force_exit_time:
            if current_quantity <= 0:
                return []
            return [self._market_order(bar=bar, side=OrderSide.SELL, quantity=current_quantity, reason="force_exit")]

        if pd.isna(row["atr_14"]) or pd.isna(row["adx_14"]) or pd.isna(row["ema_50"]):
            return []

        if row["adx_14"] >= self.config.adx_range_threshold:
            return []

        fair_value = float(row["ema_50"])
        if bar.close > fair_value * (1 + self.config.no_buy_above_fair_value_pct):
            return []

        spacing = max(float(row["atr_14"]) * self.config.grid_spacing_atr_multiplier, 0.05)
        level_capital = self.config.symbol_capital / self.config.max_levels
        orders: list[Order] = []

        for level in range(1, self.config.max_levels + 1):
            if level in self._filled_levels:
                continue
            level_price = fair_value - spacing * level
            if level_price <= 0:
                continue
            if bar.close <= level_price:
                quantity = max(int(level_capital // level_price), self.config.min_quantity)
                orders.append(
                    self._limit_order(
                        bar=bar,
                        side=OrderSide.BUY,
                        price=level_price,
                        quantity=quantity,
                        reason=f"grid_level_{level}",
                    )
                )

        if current_quantity > 0 and bar.close >= fair_value:
            orders.append(
                self._limit_order(
                    bar=bar,
                    side=OrderSide.SELL,
                    price=fair_value,
                    quantity=current_quantity,
                    reason="mean_exit",
                )
            )

        return orders

    def on_fill_reason(self, reason: str) -> None:
        if reason.startswith("grid_level_"):
            self._filled_levels.add(int(reason.removeprefix("grid_level_")))
        elif reason in {"mean_exit", "force_exit"}:
            self._filled_levels.clear()

    def _limit_order(self, *, bar: MarketBar, side: OrderSide, price: float, quantity: int, reason: str) -> Order:
        self._order_sequence += 1
        return Order(
            order_id=f"{self.symbol}-{self._order_sequence}",
            symbol=self.symbol,
            side=side,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=quantity,
            created_at=bar.timestamp,
            reason=reason,
        )

    def _market_order(self, *, bar: MarketBar, side: OrderSide, quantity: int, reason: str) -> Order:
        self._order_sequence += 1
        return Order(
            order_id=f"{self.symbol}-{self._order_sequence}",
            symbol=self.symbol,
            side=side,
            order_type=OrderType.MARKET,
            price=bar.open,
            quantity=quantity,
            created_at=bar.timestamp,
            reason=reason,
        )

