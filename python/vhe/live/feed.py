from __future__ import annotations

import asyncio
import math
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timezone

from vhe.live.models import LiveQuote, MarketDepthLevel


class LiveFeed:
    async def stream(self) -> AsyncIterator[LiveQuote]:
        raise NotImplementedError


@dataclass(slots=True)
class SimulatedQuoteFeed(LiveFeed):
    symbols: list[str]
    interval_seconds: float = 0.5
    base_price: float = 1_000.0

    async def stream(self) -> AsyncIterator[LiveQuote]:
        tick = 0
        while True:
            for offset, symbol in enumerate(self.symbols):
                wave = math.sin((tick + offset * 7) / 8)
                drift = math.sin((tick + offset * 3) / 31) * 2
                ltp = self.base_price + offset * 37 + wave * 9 + drift
                spread = max(0.05, ltp * 0.0004)
                yield LiveQuote(
                    timestamp=datetime.now(tz=timezone.utc),
                    symbol=symbol,
                    ltp=round(ltp, 2),
                    open=round(ltp - 3.0, 2),
                    high=round(ltp + 8.0, 2),
                    low=round(ltp - 8.0, 2),
                    close=round(ltp - wave, 2),
                    volume=500_000 + tick * 100,
                    bid=MarketDepthLevel(price=round(ltp - spread / 2, 2), quantity=1_000),
                    ask=MarketDepthLevel(price=round(ltp + spread / 2, 2), quantity=1_000),
                )
            tick += 1
            await asyncio.sleep(self.interval_seconds)
