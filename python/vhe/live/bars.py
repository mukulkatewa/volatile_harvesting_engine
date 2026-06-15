from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from vhe.live.models import LiveQuote

IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True, slots=True)
class OhlcvBar:
    symbol: str
    interval_minutes: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    started_at: datetime
    closed_at: datetime


@dataclass(slots=True)
class _BarBuilder:
    symbol: str
    interval_minutes: int
    open: float
    high: float
    low: float
    close: float
    volume: int
    started_at: datetime
    closed_at: datetime

    def to_bar(self) -> OhlcvBar:
        return OhlcvBar(
            symbol=self.symbol,
            interval_minutes=self.interval_minutes,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
            started_at=self.started_at,
            closed_at=self.closed_at,
        )


@dataclass(slots=True)
class BarAggregator:
    interval_minutes: int = 5
    timezone: ZoneInfo = IST
    _current: dict[str, _BarBuilder] = field(default_factory=dict)
    _history: dict[str, deque[OhlcvBar]] = field(default_factory=dict)
    history_size: int = 120

    def update(self, quote: LiveQuote) -> OhlcvBar | None:
        bucket_start = _bucket_start(quote.timestamp, self.interval_minutes, self.timezone)
        bucket_end = bucket_start + timedelta(minutes=self.interval_minutes)
        current = self._current.get(quote.symbol)

        if current is None or bucket_start != current.started_at:
            closed = current.to_bar() if current is not None else None
            self._current[quote.symbol] = _BarBuilder(
                symbol=quote.symbol,
                interval_minutes=self.interval_minutes,
                open=quote.ltp,
                high=quote.ltp,
                low=quote.ltp,
                close=quote.ltp,
                volume=quote.volume,
                started_at=bucket_start,
                closed_at=bucket_end,
            )
            if closed is not None:
                history = self._history.setdefault(quote.symbol, deque(maxlen=self.history_size))
                history.append(closed)
                return closed
            return None

        current.high = max(current.high, quote.ltp)
        current.low = min(current.low, quote.ltp)
        current.close = quote.ltp
        current.volume = max(current.volume, quote.volume)
        return None

    def current_bar(self, symbol: str) -> OhlcvBar | None:
        builder = self._current.get(symbol)
        return builder.to_bar() if builder is not None else None

    def history(self, symbol: str) -> list[OhlcvBar]:
        bars = list(self._history.get(symbol, deque()))
        current = self._current.get(symbol)
        if current is not None:
            bars = bars + [current]
        return bars

    def bars_snapshot(self) -> dict[str, dict]:
        payload: dict[str, dict] = {}
        for symbol, builder in self._current.items():
            bar = builder.to_bar()
            payload[symbol] = {
                "interval_minutes": bar.interval_minutes,
                "open": round(bar.open, 2),
                "high": round(bar.high, 2),
                "low": round(bar.low, 2),
                "close": round(bar.close, 2),
                "volume": bar.volume,
                "started_at": bar.started_at.isoformat(),
            }
        return payload


def _bucket_start(timestamp: datetime, interval_minutes: int, tz: ZoneInfo) -> datetime:
    local = timestamp.astimezone(tz)
    minute_bucket = (local.minute // interval_minutes) * interval_minutes
    return local.replace(minute=minute_bucket, second=0, microsecond=0)
