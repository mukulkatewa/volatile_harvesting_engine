from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.live.models import LiveQuote
from vhe.strategies.regime import MarketRegime


@dataclass(frozen=True, slots=True)
class PairConfig:
    symbol_a: str
    symbol_b: str
    hedge_ratio: float = 1.0
    mean: float = 0.0
    std: float = 0.01
    entry_z: float = 1.5
    exit_z: float = 0.25
    max_abs_z: float = 3.0
    leg_capital: float = 5_000.0


@dataclass(frozen=True, slots=True)
class PairInputs:
    quote_a: LiveQuote
    quote_b: LiveQuote
    regime: MarketRegime
    current_position: int = 0


@dataclass(frozen=True, slots=True)
class PairSpreadPlan:
    pair_id: str
    symbol_a: str
    symbol_b: str
    spread: float
    zscore: float
    action: str
    enabled: bool
    reason: str


@dataclass(slots=True)
class PairSpreadStrategy:
    config: PairConfig
    _order_sequence: int = 0

    def build_plan(self, inputs: PairInputs) -> PairSpreadPlan:
        pair_id = f"{self.config.symbol_a}/{self.config.symbol_b}"
        if inputs.regime == MarketRegime.CRASH:
            return self._plan(inputs, 0.0, "CASH", False, "crash_regime")

        spread = self._spread(inputs.quote_a.ltp, inputs.quote_b.ltp)
        zscore = self._zscore(spread)
        abs_z = abs(zscore)

        if abs_z >= self.config.max_abs_z:
            return PairSpreadPlan(pair_id, self.config.symbol_a, self.config.symbol_b, spread, zscore, "STOP", False, "zscore_hard_stop")
        if inputs.current_position != 0:
            if abs_z <= self.config.exit_z:
                return PairSpreadPlan(pair_id, self.config.symbol_a, self.config.symbol_b, spread, zscore, "EXIT", True, "mean_reversion_exit")
            return PairSpreadPlan(pair_id, self.config.symbol_a, self.config.symbol_b, spread, zscore, "WAIT", False, "position_open")
        if abs_z >= self.config.entry_z:
            action = "SHORT_A_LONG_B" if zscore > 0 else "LONG_A_SHORT_B"
            return PairSpreadPlan(pair_id, self.config.symbol_a, self.config.symbol_b, spread, zscore, action, True, "spread_deviation")
        return PairSpreadPlan(pair_id, self.config.symbol_a, self.config.symbol_b, spread, zscore, "WAIT", False, "inside_band")

    def orders_from_plan(self, plan: PairSpreadPlan, quote_a: LiveQuote, quote_b: LiveQuote) -> list[Order]:
        if not plan.enabled:
            return []
        qty_a = max(int(self.config.leg_capital // quote_a.ltp), 1)
        qty_b = max(int(self.config.leg_capital // quote_b.ltp), 1)

        if plan.action == "SHORT_A_LONG_B":
            return [
                self._order(quote_a.timestamp, quote_a.symbol, OrderSide.SELL, quote_a.ltp, qty_a, "pair_short_a"),
                self._order(quote_b.timestamp, quote_b.symbol, OrderSide.BUY, quote_b.ltp, qty_b, "pair_long_b"),
            ]
        if plan.action == "LONG_A_SHORT_B":
            return [
                self._order(quote_a.timestamp, quote_a.symbol, OrderSide.BUY, quote_a.ltp, qty_a, "pair_long_a"),
                self._order(quote_b.timestamp, quote_b.symbol, OrderSide.SELL, quote_b.ltp, qty_b, "pair_short_b"),
            ]
        return []

    def _spread(self, price_a: float, price_b: float) -> float:
        return math.log(price_a) - self.config.hedge_ratio * math.log(price_b)

    def _zscore(self, spread: float) -> float:
        return (spread - self.config.mean) / self.config.std

    def _plan(self, inputs: PairInputs, zscore: float, action: str, enabled: bool, reason: str) -> PairSpreadPlan:
        spread = self._spread(inputs.quote_a.ltp, inputs.quote_b.ltp)
        return PairSpreadPlan(
            pair_id=f"{self.config.symbol_a}/{self.config.symbol_b}",
            symbol_a=self.config.symbol_a,
            symbol_b=self.config.symbol_b,
            spread=spread,
            zscore=zscore,
            action=action,
            enabled=enabled,
            reason=reason,
        )

    def _order(self, timestamp: datetime, symbol: str, side: OrderSide, price: float, quantity: int, reason: str) -> Order:
        self._order_sequence += 1
        return Order(
            order_id=f"pair-{self.config.symbol_a}-{self.config.symbol_b}-{self._order_sequence}",
            symbol=symbol,
            side=side,
            order_type=OrderType.LIMIT,
            price=price,
            quantity=quantity,
            created_at=timestamp,
            reason=reason,
        )
