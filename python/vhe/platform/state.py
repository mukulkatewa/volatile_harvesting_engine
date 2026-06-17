from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from enum import Enum

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
    kill_switch_reason: str | None = None
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
    market_session: dict = field(default_factory=dict)
    paper_stats: dict = field(default_factory=dict)
    strategy_status: dict = field(default_factory=dict)
    execution_orders: list[dict] = field(default_factory=list)
    reconciliation: dict = field(default_factory=dict)
    source: str = "simulated"
    connected: bool = False
    mode: str = "paper"
    phase: str = "2"

    def snapshot(self) -> dict:
        now = datetime.now(tz=timezone.utc)
        return {
            "source": self.source,
            "connected": self.connected,
            "mode": self.mode,
            "phase": self.phase,
            "server_time": now.isoformat(),
            "controls": asdict(self.controls),
            "regimes": self.regimes,
            "quotes": {symbol: _quote_to_dict(quote, now=now) for symbol, quote in self.quotes.items()},
            "plans": {symbol: _dataclass_to_dict(plan) for symbol, plan in self.plans.items()},
            "momentum_plans": {symbol: _dataclass_to_dict(plan) for symbol, plan in self.momentum_plans.items()},
            "pair_plans": {pair_id: _dataclass_to_dict(plan) for pair_id, plan in self.pair_plans.items()},
            "pair_trades": [_json_ready(trade) for trade in self.pair_trades[-20:]],
            "orders": [_dataclass_to_dict(order) for order in self.orders[-25:]],
            "fills": self._fills_snapshot(),
            "events": [entry.to_dict() for entry in self.events[-40:]],
            "portfolio": _json_ready(self.portfolio),
            "capital": _json_ready(self.capital),
            "indicators": _json_ready(self.indicators),
            "bars": _json_ready(self.bars),
            "feed_health": _json_ready(self.feed_health),
            "market_session": _json_ready(self.market_session),
            "paper_stats": _json_ready(self.paper_stats),
            "strategy_status": _json_ready(self.strategy_status),
            "execution_orders": _json_ready(self.execution_orders),
            "reconciliation": _json_ready(self.reconciliation),
        }

    def append_event(self, entry: PlatformEvent) -> None:
        self.events.append(entry)
        if len(self.events) > 200:
            del self.events[: len(self.events) - 200]

    def _fills_snapshot(self) -> list:
        if self.fills:
            return [_dataclass_to_dict(fill) for fill in self.fills[-25:]]
        return _json_ready(self.portfolio.get("fills", []))[-25:]


def _quote_to_dict(quote: LiveQuote, *, now: datetime) -> dict:
    payload = _dataclass_to_dict(quote)
    payload["spread_bps"] = quote.spread_bps
    payload["age_ms"] = max(int((now - quote.timestamp).total_seconds() * 1000), 0)
    return payload


def _dataclass_to_dict(obj: object) -> dict:
    return _json_ready(asdict(obj))


def _json_ready(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    if isinstance(value, tuple):
        return [_json_ready(item) for item in value]
    return value
