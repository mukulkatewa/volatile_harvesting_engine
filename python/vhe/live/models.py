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
    bids: tuple[MarketDepthLevel, ...] = ()
    asks: tuple[MarketDepthLevel, ...] = ()

    @property
    def spread_bps(self) -> float | None:
        best_bid = self.bid or (self.bids[0] if self.bids else None)
        best_ask = self.ask or (self.asks[0] if self.asks else None)
        if best_bid is None or best_ask is None or self.ltp <= 0:
            return None
        return ((best_ask.price - best_bid.price) / self.ltp) * 10_000


@dataclass(frozen=True, slots=True)
class LiveFeedState:
    connected: bool
    source: str
    quotes: dict[str, LiveQuote] = field(default_factory=dict)
    last_error: str | None = None
