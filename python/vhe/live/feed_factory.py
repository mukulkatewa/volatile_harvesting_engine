from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from vhe.config.loader import PlatformConfig
from vhe.live.feed import LiveFeed, SimulatedQuoteFeed
from vhe.live.kite import nse_equity_token_map
from vhe.live.kite_auth import KiteCredentialError, load_kite_credentials
from vhe.live.kite_instruments import load_cached_instruments
from vhe.live.kite_ws import KiteWebSocketFeed

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FeedBuildResult:
    feed: LiveFeed
    source: str
    subscribed_symbols: tuple[str, ...]
    warning: str | None = None


def build_quote_feed(config: PlatformConfig, *, project_root: Path, trading_date: date | None = None) -> FeedBuildResult:
    feed_cfg = config.strategies.feed
    symbols = tuple(feed_cfg.symbols)

    if feed_cfg.source != "kite":
        return FeedBuildResult(
            feed=SimulatedQuoteFeed(symbols=list(symbols), interval_seconds=feed_cfg.interval_seconds),
            source="simulated",
            subscribed_symbols=symbols,
        )

    broker = config.live.broker
    if not broker.websocket_enabled:
        warning = "feed.source=kite but broker.websocket_enabled=false; using simulated feed"
        return FeedBuildResult(
            feed=SimulatedQuoteFeed(symbols=list(symbols), interval_seconds=feed_cfg.interval_seconds),
            source="simulated",
            subscribed_symbols=symbols,
            warning=warning,
        )

    try:
        credentials = load_kite_credentials(broker)
    except KiteCredentialError as exc:
        warning = str(exc)
        if not feed_cfg.fallback_to_simulated:
            raise
        logger.warning("%s; falling back to simulated feed", warning)
        return FeedBuildResult(
            feed=SimulatedQuoteFeed(symbols=list(symbols), interval_seconds=feed_cfg.interval_seconds),
            source="simulated",
            subscribed_symbols=symbols,
            warning=warning,
        )

    cache_dir = broker.instrument_cache_dir
    if not cache_dir.is_absolute():
        cache_dir = project_root / cache_dir
    as_of = trading_date or date.today()
    try:
        instruments = load_cached_instruments(cache_dir=cache_dir, trading_date=as_of).instruments
    except FileNotFoundError as exc:
        warning = f"{exc}; run vhe kite-cache-instruments first"
        if not feed_cfg.fallback_to_simulated:
            raise
        logger.warning("%s; falling back to simulated feed", warning)
        return FeedBuildResult(
            feed=SimulatedQuoteFeed(symbols=list(symbols), interval_seconds=feed_cfg.interval_seconds),
            source="simulated",
            subscribed_symbols=symbols,
            warning=warning,
        )

    token_map = nse_equity_token_map(instruments, list(symbols))
    missing = sorted(set(symbols) - set(token_map))
    if missing:
        warning = f"missing instrument tokens for: {', '.join(missing)}"
        if not feed_cfg.fallback_to_simulated:
            raise ValueError(warning)
        logger.warning("%s; falling back to simulated feed", warning)
        return FeedBuildResult(
            feed=SimulatedQuoteFeed(symbols=list(symbols), interval_seconds=feed_cfg.interval_seconds),
            source="simulated",
            subscribed_symbols=symbols,
            warning=warning,
        )

    token_symbol_map = {token: symbol for symbol, token in token_map.items()}
    return FeedBuildResult(
        feed=KiteWebSocketFeed(
            api_key=credentials.api_key,
            access_token=credentials.access_token,
            token_symbol_map=token_symbol_map,
            mode=broker.subscription_mode,
            reconnect_seconds=broker.reconnect_seconds,
        ),
        source="kite",
        subscribed_symbols=symbols,
    )
