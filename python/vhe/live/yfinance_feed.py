from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from vhe.live.feed import LiveFeed
from vhe.live.market_session import MarketSessionConfig, session_phase
from vhe.live.models import LiveQuote, MarketDepthLevel

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.ERROR)

MIN_POLL_SECONDS = 10.0
CLOSED_MARKET_POLL_SECONDS = 60.0
FETCH_TIMEOUT_SECONDS = 20.0
CHUNK_TIMEOUT_SECONDS = 15.0
CACHE_MAX_AGE_SECONDS = 600.0
CHUNK_SIZE = 5
# Intraday resolution so the live LTP actually moves between polls (volatility to harvest).
# Daily bars are static intraday and leave grid levels permanently untouched.
INTRADAY_INTERVAL = "5m"
INTRADAY_PERIOD = "1d"
DAILY_INTERVAL = "1d"
DAILY_PERIOD = "5d"


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

    quotes: list[LiveQuote] = []
    for chunk in _chunked(symbols, CHUNK_SIZE):
        try:
            quotes.extend(_fetch_batch_quotes(chunk, now, timeout_seconds=min(timeout_seconds, CHUNK_TIMEOUT_SECONDS)))
        except Exception as exc:
            logger.warning("yfinance chunk fetch failed (%s): %s", ", ".join(chunk), exc)
            for symbol in chunk:
                try:
                    quotes.extend(_fetch_batch_quotes([symbol], now, timeout_seconds=CHUNK_TIMEOUT_SECONDS))
                except Exception as single_exc:
                    logger.debug("yfinance single fetch failed for %s: %s", symbol, single_exc)

    if cache is not None:
        for quote in quotes:
            cache[quote.symbol] = quote

    fetched = {quote.symbol for quote in quotes}
    missing = [symbol for symbol in symbols if symbol not in fetched]
    if missing and cache:
        for symbol in missing:
            cached = cache.get(symbol)
            if cached is None:
                continue
            age = (now - cached.timestamp).total_seconds()
            if age <= CACHE_MAX_AGE_SECONDS:
                quotes.append(replace(cached, timestamp=now))

    if quotes:
        return quotes

    if cache:
        cached = _fresh_cached_quotes(cache, now)
        if cached:
            logger.info("yfinance empty batch — serving %d cached quote(s)", len(cached))
            return [replace(quote, timestamp=now) for quote in cached]

    if phase is not None:
        logger.info("yfinance returned no quotes during %s", phase.value)
    return []


def fetch_yfinance_history_seed(symbols: list[str], *, lookback_days: int = 60) -> dict[str, list[dict[str, float]]]:
    """Warm up ADX/ATR/EMA on the same intraday (5m) scale the live feed trades on.

    Falls back to daily history when intraday is unavailable (e.g. extended holiday).
    """
    import yfinance as yf

    if not symbols:
        return {}

    tickers = [to_yfinance_symbol(symbol) for symbol in symbols]
    seeds: dict[str, list[dict[str, float]]] = {}

    def _seed_from_frame(frame: object, symbol: str, ticker: str) -> None:
        if frame is None or getattr(frame, "empty", True):
            return
        columns = getattr(frame, "columns", None)
        if columns is not None and getattr(columns, "nlevels", 1) > 1 and ticker in getattr(columns, "levels", [[]])[0]:
            block = frame[ticker]
        else:
            block = frame
        bars = _bars_from_single_frame(block)
        if bars:
            seeds[symbol] = bars

    def _download(period: str, interval: str) -> object:
        joined = tickers[0] if len(tickers) == 1 else " ".join(tickers)
        return yf.download(
            joined,
            period=period,
            interval=interval,
            progress=False,
            threads=False,
            group_by="ticker",
            auto_adjust=False,
        )

    intraday = _download("5d", INTRADAY_INTERVAL)
    for symbol, ticker in zip(symbols, tickers, strict=False):
        _seed_from_frame(intraday, symbol, ticker)

    missing = [s for s in symbols if s not in seeds]
    if missing:
        daily_period = "3mo" if lookback_days > 60 else "2mo"
        daily = _download(daily_period, "1d")
        for symbol, ticker in zip(symbols, tickers, strict=False):
            if symbol in missing:
                _seed_from_frame(daily, symbol, ticker)
    return seeds


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _scalar(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    if hasattr(value, "iloc"):
        try:
            if len(value) == 0:
                return default
            value = value.iloc[0]
        except Exception:
            return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _bars_from_single_frame(frame: object) -> list[dict[str, float]]:
    if frame is None or getattr(frame, "empty", True):
        return []
    bars: list[dict[str, float]] = []
    for _, row in frame.iterrows():
        close = _scalar(row["Close"])
        if close <= 0:
            continue
        bars.append(
            {
                "open": _scalar(row.get("Open", close), close),
                "high": _scalar(row.get("High", close), close),
                "low": _scalar(row.get("Low", close), close),
                "close": close,
                "ltp": close,
            }
        )
    return bars[-60:]


def _fresh_cached_quotes(cache: dict[str, LiveQuote], now: datetime) -> list[LiveQuote]:
    fresh: list[LiveQuote] = []
    for quote in cache.values():
        age = (now - quote.timestamp).total_seconds()
        if age <= CACHE_MAX_AGE_SECONDS:
            fresh.append(quote)
    return fresh


def _fetch_batch_quotes(symbols: list[str], timestamp: datetime, *, timeout_seconds: float) -> list[LiveQuote]:
    # Prefer intraday bars (moving LTP); fall back to daily when intraday is empty
    # (weekends/holidays/pre-open) so we still show the last available close.
    quotes = _download_quotes(symbols, timestamp, timeout_seconds, INTRADAY_PERIOD, INTRADAY_INTERVAL)
    fetched = {quote.symbol for quote in quotes}
    missing = [symbol for symbol in symbols if symbol not in fetched]
    if missing:
        quotes.extend(_download_quotes(missing, timestamp, timeout_seconds, DAILY_PERIOD, DAILY_INTERVAL))
    return quotes


def _download_quotes(
    symbols: list[str],
    timestamp: datetime,
    timeout_seconds: float,
    period: str,
    interval: str,
) -> list[LiveQuote]:
    import yfinance as yf

    if not symbols:
        return []
    tickers = [to_yfinance_symbol(symbol) for symbol in symbols]
    if len(tickers) == 1:
        frame = yf.download(
            tickers[0],
            period=period,
            interval=interval,
            progress=False,
            threads=False,
            auto_adjust=False,
            timeout=timeout_seconds,
        )
        quote = _quote_from_single_frame(symbols[0], frame, timestamp)
        return [quote] if quote is not None else []

    frame = yf.download(
        " ".join(tickers),
        period=period,
        interval=interval,
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
    # The last intraday bar is often still forming (NaN close); walk back to the last valid bar.
    row = None
    for index in range(len(frame) - 1, -1, -1):
        candidate = frame.iloc[index]
        if _scalar(candidate["Close"]) > 0:
            row = candidate
            break
    if row is None:
        return None
    ltp = _scalar(row["Close"])
    if ltp <= 0:
        return None
    return _build_quote(
        symbol,
        timestamp,
        ltp,
        _scalar(row.get("Open", ltp), ltp),
        _scalar(row.get("High", ltp), ltp),
        _scalar(row.get("Low", ltp), ltp),
        ltp,
        int(_scalar(row.get("Volume", 0))),
    )


def _quote_from_grouped_frame(symbol: str, ticker: str, frame: object, timestamp: datetime) -> LiveQuote | None:
    if frame is None or getattr(frame, "empty", True):
        return None
    columns = getattr(frame, "columns", None)
    if columns is not None and getattr(columns, "nlevels", 1) > 1:
        level_values = columns.get_level_values(0)
        if ticker not in level_values:
            return None
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
        volume=max(volume, 0),
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
