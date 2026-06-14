from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

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
    mode: str = "paper"

    def snapshot(self) -> dict:
        now = datetime.now(tz=timezone.utc)
        return {
            "source": self.source,
            "connected": self.connected,
            "mode": self.mode,
            "server_time": now.isoformat(),
            "quotes": {symbol: _quote_to_dict(quote, now=now) for symbol, quote in self.quotes.items()},
            "plans": {symbol: asdict(plan) for symbol, plan in self.plans.items()},
            "orders": [asdict(order) for order in self.orders[-25:]],
        }


def _quote_to_dict(quote: LiveQuote, *, now: datetime) -> dict:
    payload = asdict(quote)
    payload["spread_bps"] = quote.spread_bps
    payload["age_ms"] = max(int((now - quote.timestamp).total_seconds() * 1000), 0)
    return payload
