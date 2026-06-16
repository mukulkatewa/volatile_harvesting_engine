from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from datetime import datetime, timezone

from vhe.live.feed import LiveFeed
from vhe.live.market_session import MarketSessionConfig, session_phase
from vhe.live.models import LiveQuote, MarketDepthLevel

logger = logging.getLogger(__name__)

MIN_POLL_SECONDS = 10.0
CLOSED_MARKET_POLL_SECONDS = 60.0
FETCH_TIMEOUT_SECONDS = 12.0
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="yfinance")


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
) -> list[LiveQuote]:
    now = datetime.now(tz=timezone.utc)
    phase = session_phase(session) if session is not None else None
    quotes: list[LiveQuote] = []

    for symbol in symbols:
        try:
            future = _executor.submit(_fetch_single_quote, symbol, now)
            quote = future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            logger.warning("yfinance quote timed out for %s", symbol)
            continue
        except Exception as exc:
            logger.warning("yfinance quote failed for %s: %s", symbol, exc)
            continue
        if quote is not None:
            quotes.append(quote)

    if not quotes and phase is not None:
        logger.info("yfinance returned no quotes during %s", phase.value)
    return quotes


def _fetch_single_quote(symbol: str, timestamp: datetime) -> LiveQuote | None:
    import yfinance as yf

    yf_symbol = to_yfinance_symbol(symbol)
    ticker = yf.Ticker(yf_symbol)
    return _quote_from_ticker(symbol, ticker, timestamp)


def _quote_from_ticker(symbol: str, ticker: object, timestamp: datetime) -> LiveQuote | None:
    fast_info = getattr(ticker, "fast_info", None)
    if fast_info is not None:
        ltp = _pick_price(fast_info, ("last_price", "lastPrice", "regular_market_price", "regularMarketPrice"))
        if ltp is not None and ltp > 0:
            open_ = _pick_price(fast_info, ("open", "regular_market_open", "regularMarketOpen")) or ltp
            high = _pick_price(fast_info, ("day_high", "dayHigh", "regular_market_day_high", "regularMarketDayHigh")) or ltp
            low = _pick_price(fast_info, ("day_low", "dayLow", "regular_market_day_low", "regularMarketDayLow")) or ltp
            close = _pick_price(fast_info, ("previous_close", "previousClose", "regular_market_previous_close")) or ltp
            volume = int(_pick_price(fast_info, ("last_volume", "lastVolume", "ten_day_average_volume")) or 0)
            return _build_quote(symbol, timestamp, ltp, open_, high, low, close, volume)

    history = ticker.history(period="1d", interval="1m")
    if history is None or history.empty:
        return None
    row = history.iloc[-1]
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


def _pick_price(fast_info: object, keys: tuple[str, ...]) -> float | None:
    for key in keys:
        try:
            value = fast_info[key]
        except (KeyError, TypeError, AttributeError):
            value = getattr(fast_info, key, None)
        if value is not None:
            try:
                parsed = float(value)
            except (TypeError, ValueError):
                continue
            if parsed > 0:
                return parsed
    return None


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

    async def stream(self) -> AsyncIterator[LiveQuote]:
        while True:
            phase = session_phase(self.session) if self.session is not None else None
            poll_seconds = max(self.interval_seconds, MIN_POLL_SECONDS)
            if phase is not None and phase.value != "open":
                poll_seconds = max(poll_seconds, CLOSED_MARKET_POLL_SECONDS)

            try:
                quotes = await asyncio.to_thread(
                    fetch_yfinance_quotes,
                    self.symbols,
                    session=self.session,
                )
            except Exception as exc:
                logger.exception("yfinance batch fetch failed: %s", exc)
                quotes = []

            for quote in quotes:
                yield quote
            await asyncio.sleep(poll_seconds)
