from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from vhe.backtest.models import Fill, Order
from vhe.live.models import LiveQuote
from vhe.platform.events import PlatformEvent
from vhe.strategies.dynamic_grid import DynamicGridPlan
from vhe.strategies.momentum import MomentumPlan
from vhe.strategies.pair_spread import PairSpreadPlan


@dataclass(slots=True)
class PlatformControls:
    automation_paused: bool = False
    kill_switch: bool = False
    last_risk_reject: str | None = None


@dataclass(slots=True)
class PlatformState:
    quotes: dict[str, LiveQuote] = field(default_factory=dict)
    plans: dict[str, DynamicGridPlan] = field(default_factory=dict)
    momentum_plans: dict[str, MomentumPlan] = field(default_factory=dict)
    pair_plans: dict[str, PairSpreadPlan] = field(default_factory=dict)
    pair_trades: list[dict] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)
    events: list[PlatformEvent] = field(default_factory=list)
    portfolio: dict = field(default_factory=dict)
    controls: PlatformControls = field(default_factory=PlatformControls)
    capital: dict = field(default_factory=dict)
    regimes: dict[str, str] = field(default_factory=dict)
    indicators: dict[str, dict] = field(default_factory=dict)
    bars: dict[str, dict] = field(default_factory=dict)
    feed_health: dict = field(default_factory=dict)
    source: str = "simulated"
    connected: bool = False
    mode: str = "paper"
    phase: str = "1"

    def snapshot(self) -> dict:
        now = datetime.now(tz=timezone.utc)
        return {
            "source": self.source,
            "connected": self.connected,
            "mode": self.mode,
            "phase": self.phase,
            "server_time": now.isoformat(),
            "controls": asdict(self.controls),
            "capital": self.capital,
            "regimes": self.regimes,
            "indicators": self.indicators,
            "bars": self.bars,
            "feed_health": self.feed_health,
            "quotes": {symbol: _quote_to_dict(quote, now=now) for symbol, quote in self.quotes.items()},
            "plans": {symbol: asdict(plan) for symbol, plan in self.plans.items()},
            "momentum_plans": {symbol: asdict(plan) for symbol, plan in self.momentum_plans.items()},
            "pair_plans": {pair_id: asdict(plan) for pair_id, plan in self.pair_plans.items()},
            "pair_trades": self.pair_trades[-20:],
            "orders": [asdict(order) for order in self.orders[-25:]],
            "fills": [asdict(fill) for fill in self.fills[-25:]],
            "events": [entry.to_dict() for entry in self.events[-40:]],
            "portfolio": self.portfolio,
        }

    def append_event(self, entry: PlatformEvent) -> None:
        self.events.append(entry)
        if len(self.events) > 200:
            del self.events[: len(self.events) - 200]


def _quote_to_dict(quote: LiveQuote, *, now: datetime) -> dict:
    payload = asdict(quote)
    payload["spread_bps"] = quote.spread_bps
    payload["age_ms"] = max(int((now - quote.timestamp).total_seconds() * 1000), 0)
    return payload
