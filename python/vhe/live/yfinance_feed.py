from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone

from vhe.live.feed import LiveFeed
from vhe.live.market_session import MarketSessionConfig, session_phase
from vhe.live.models import LiveQuote, MarketDepthLevel

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.ERROR)

MIN_POLL_SECONDS = 10.0
CLOSED_MARKET_POLL_SECONDS = 60.0
FETCH_TIMEOUT_SECONDS = 45.0
CACHE_MAX_AGE_SECONDS = 300.0


def to_yfinance_symbol(symbol: str) -> str:
    normalized = symbol.strip().upper()
    if normalized.endswith((".NS", ".BO")):
        return normalized
    return f"{normalized}.NS"


def from_yfinance_symbol(ticker: str) -> str:
    if ticker.endswith(".NS") or ticker.endswith(".BO"):
        return ticker.rsplit(".", 1)[0]
    return ticker


def fetch_yfinance_quotes(
    symbols: list[str],
    *,
    session: MarketSessionConfig | None = None,
    timeout_seconds: float = FETCH_TIMEOUT_SECONDS,
    cache: dict[str, LiveQuote] | None = None,
) -> list[LiveQuote]:
    now = datetime.now(tz=timezone.utc)
    phase = session_phase(session) if session is not None else None
    if not symbols:
        return []

    try:
        quotes = _fetch_batch_quotes(symbols, now, timeout_seconds=timeout_seconds)
    except Exception as exc:
        logger.warning("yfinance batch fetch failed: %s", exc)
        quotes = []

    if cache is not None:
        for quote in quotes:
            cache[quote.symbol] = quote

    if quotes:
        return quotes

    if cache:
        cached = _fresh_cached_quotes(cache, now)
        if cached:
            logger.info("yfinance empty batch — serving %d cached quote(s)", len(cached))
            return cached

    if phase is not None:
        logger.info("yfinance returned no quotes during %s", phase.value)
    return []


def fetch_yfinance_history_seed(symbols: list[str], *, lookback_days: int = 60) -> dict[str, list[dict[str, float]]]:
    """Load daily OHLC history so ADX/ATR warm up immediately on yfinance mode."""
    import yfinance as yf

    if not symbols:
        return {}

    tickers = [to_yfinance_symbol(symbol) for symbol in symbols]
    period = "3mo" if lookback_days > 60 else "2mo"
    seeds: dict[str, list[dict[str, float]]] = {}

    if len(tickers) == 1:
        frame = yf.download(
            tickers[0],
            period=period,
            interval="1d",
            progress=False,
            threads=False,
            auto_adjust=False,
        )
        bars = _bars_from_single_frame(frame)
        if bars:
            seeds[symbols[0]] = bars
        return seeds

    frame = yf.download(
        " ".join(tickers),
        period=period,
        interval="1d",
        progress=False,
        threads=False,
        group_by="ticker",
        auto_adjust=False,
    )
    for symbol, ticker in zip(symbols, tickers, strict=False):
        if frame is None or getattr(frame, "empty", True):
            continue
        columns = getattr(frame, "columns", None)
        block = frame[ticker] if columns is not None and ticker in getattr(columns, "levels", [[]])[0] else frame
        bars = _bars_from_single_frame(block)
        if bars:
            seeds[symbol] = bars
    return seeds


def _bars_from_single_frame(frame: object) -> list[dict[str, float]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    bars: list[dict[str, float]] = []
    for _, row in frame.iterrows():
        close = float(row["Close"])
        if close <= 0:
            continue
        open_ = float(row.get("Open", close))
        high = float(row.get("High", close))
        low = float(row.get("Low", close))
        bars.append({"open": open_, "high": high, "low": low, "close": close, "ltp": close})
    return bars[-60:]


def _fresh_cached_quotes(cache: dict[str, LiveQuote], now: datetime) -> list[LiveQuote]:
    fresh: list[LiveQuote] = []
    for quote in cache.values():
        age = (now - quote.timestamp).total_seconds()
        if age <= CACHE_MAX_AGE_SECONDS:
            fresh.append(quote)
    return fresh


def _fetch_batch_quotes(symbols: list[str], timestamp: datetime, *, timeout_seconds: float) -> list[LiveQuote]:
    import yfinance as yf

    tickers = [to_yfinance_symbol(symbol) for symbol in symbols]
    if len(tickers) == 1:
        frame = yf.download(
            tickers[0],
            period="5d",
            interval="1d",
            progress=False,
            threads=False,
            auto_adjust=False,
            timeout=timeout_seconds,
        )
        quote = _quote_from_single_frame(symbols[0], frame, timestamp)
        return [quote] if quote is not None else []

    frame = yf.download(
        " ".join(tickers),
        period="5d",
        interval="1d",
        progress=False,
        threads=False,
        group_by="ticker",
        auto_adjust=False,
        timeout=timeout_seconds,
    )
    quotes: list[LiveQuote] = []
    for symbol, ticker in zip(symbols, tickers, strict=False):
        quote = _quote_from_grouped_frame(symbol, ticker, frame, timestamp)
        if quote is not None:
            quotes.append(quote)
    return quotes


def _quote_from_single_frame(symbol: str, frame: object, timestamp: datetime) -> LiveQuote | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    row = frame.iloc[-1]
    ltp = float(row["Close"])
    if ltp <= 0:
        return None
    return _build_quote(
        symbol,
        timestamp,
        ltp,
        float(row.get("Open", ltp)),
        float(row.get("High", ltp)),
        float(row.get("Low", ltp)),
        float(row["Close"]),
        int(row.get("Volume", 0) or 0),
    )


def _quote_from_grouped_frame(symbol: str, ticker: str, frame: object, timestamp: datetime) -> LiveQuote | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    columns = getattr(frame, "columns", None)
    if columns is not None and ticker in getattr(columns, "levels", [[]])[0]:
        block = frame[ticker]
        return _quote_from_single_frame(symbol, block, timestamp)
    return _quote_from_single_frame(symbol, frame, timestamp)


def _build_quote(
    symbol: str,
    timestamp: datetime,
    ltp: float,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int,
) -> LiveQuote:
    spread = max(0.05, ltp * 0.0005)
    return LiveQuote(
        timestamp=timestamp,
        symbol=symbol,
        ltp=round(ltp, 2),
        open=round(open_, 2),
        high=round(high, 2),
        low=round(low, 2),
        close=round(close, 2),
        volume=volume,
        bid=MarketDepthLevel(price=round(ltp - spread / 2, 2), quantity=1),
        ask=MarketDepthLevel(price=round(ltp + spread / 2, 2), quantity=1),
    )


@dataclass(slots=True)
class YFinanceQuoteFeed(LiveFeed):
    symbols: list[str]
    interval_seconds: float = 15.0
    session: MarketSessionConfig | None = None
    _cache: dict[str, LiveQuote] = field(default_factory=dict)
    _empty_streak: int = 0

    async def stream(self) -> AsyncIterator[LiveQuote]:
        while True:
            phase = session_phase(self.session) if self.session is not None else None
            poll_seconds = max(self.interval_seconds, MIN_POLL_SECONDS)
            if phase is not None and phase.value != "open":
                poll_seconds = max(poll_seconds, CLOSED_MARKET_POLL_SECONDS)

            quotes = await asyncio.to_thread(
                fetch_yfinance_quotes,
                self.symbols,
                session=self.session,
                cache=self._cache,
            )

            if quotes:
                self._empty_streak = 0
                for quote in quotes:
                    yield quote
            else:
                self._empty_streak += 1
                if self._empty_streak == 1:
                    logger.warning("yfinance returned zero quotes for watchlist (%d symbols)", len(self.symbols))

            await asyncio.sleep(poll_seconds)
