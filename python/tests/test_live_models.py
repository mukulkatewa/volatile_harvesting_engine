from datetime import datetime, timezone

from vhe.live.models import LiveQuote, MarketDepthLevel



def test_live_quote_spread_bps_uses_top_of_book() -> None:
    quote = LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=100,
        open=99,
        high=101,
        low=98,
        close=99,
        volume=1000,
        bid=MarketDepthLevel(price=99.95, quantity=100),
        ask=MarketDepthLevel(price=100.05, quantity=100),
    )

    assert round(quote.spread_bps, 2) == 10.0
