from datetime import datetime, timezone

from vhe.live.kite_ws import FeedHealth
from vhe.live.models import LiveQuote


def test_feed_health_ignores_quote_age_when_market_closed() -> None:
    now = datetime.now(tz=timezone.utc)
    health = FeedHealth(
        source="yfinance",
        connected=True,
        subscribed_symbols=("RELIANCE",),
        last_tick_at=now,
    )
    old = now.replace(year=now.year - 1)
    quotes = {
        "RELIANCE": LiveQuote(
            timestamp=old,
            symbol="RELIANCE",
            ltp=100.0,
            open=99.0,
            high=101.0,
            low=98.0,
            close=99.5,
            volume=1000,
        )
    }
    snapshot = health.snapshot(quotes=quotes, max_stale_ms=3_000, market_closed=True)
    assert snapshot["is_stale"] is False
    assert snapshot["market_closed"] is True
