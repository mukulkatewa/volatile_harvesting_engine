from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True, slots=True)
class MarketDepthLevel:
    price: float
    quantity: int
    orders: int = 0


@dataclass(frozen=True, slots=True)
class LiveQuote:
    timestamp: datetime
    symbol: str
    ltp: float
    open: float
    high: float
    low: float
    close: float
    volume: int
    bid: MarketDepthLevel | None = None
    ask: MarketDepthLevel | None = None

    @property
    def spread_bps(self) -> float | None:
        if self.bid is None or self.ask is None or self.ltp <= 0:
            return None
        return ((self.ask.price - self.bid.price) / self.ltp) * 10_000


@dataclass(frozen=True, slots=True)
class LiveFeedState:
    connected: bool
    source: str
    quotes: dict[str, LiveQuote] = field(default_factory=dict)
    last_error: str | None = None
