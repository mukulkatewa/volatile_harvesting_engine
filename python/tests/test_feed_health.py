from datetime import datetime, timezone

from vhe.live.kite_ws import FeedHealth
from vhe.live.models import LiveQuote


def test_feed_health_allows_mutation() -> None:
    health = FeedHealth(source="yfinance", connected=True, subscribed_symbols=("RELIANCE",), last_tick_at=None)
    now = datetime.now(tz=timezone.utc)
    health.last_tick_at = now
    health.connected = True
    assert health.last_tick_at == now


def test_feed_health_snapshot_warmup_skips_missing_symbols() -> None:
    now = datetime.now(tz=timezone.utc)
    health = FeedHealth(
        source="yfinance",
        connected=True,
        subscribed_symbols=("RELIANCE", "HDFCBANK"),
        last_tick_at=now,
    )
    quotes = {
        "RELIANCE": LiveQuote(
            timestamp=now,
            symbol="RELIANCE",
            ltp=100.0,
            open=99.0,
            high=101.0,
            low=98.0,
            close=99.5,
            volume=1000,
        )
    }
    snapshot = health.snapshot(quotes=quotes, max_stale_ms=120_000)
    assert snapshot["is_stale"] is False
    assert snapshot["stale_symbols"] == []
