from __future__ import annotations

from dataclasses import asdict, dataclass, field

from vhe.backtest.models import Order
from vhe.live.models import LiveQuote
from vhe.strategies.dynamic_grid import DynamicGridPlan


@dataclass(slots=True)
class PlatformState:
    quotes: dict[str, LiveQuote] = field(default_factory=dict)
    plans: dict[str, DynamicGridPlan] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)
    source: str = "simulated"
    connected: bool = False

    def snapshot(self) -> dict:
        return {
            "source": self.source,
            "connected": self.connected,
            "quotes": {symbol: _quote_to_dict(quote) for symbol, quote in self.quotes.items()},
            "plans": {symbol: asdict(plan) for symbol, plan in self.plans.items()},
            "orders": [asdict(order) for order in self.orders[-25:]],
        }


def _quote_to_dict(quote: LiveQuote) -> dict:
    payload = asdict(quote)
    payload["spread_bps"] = quote.spread_bps
    return payload
