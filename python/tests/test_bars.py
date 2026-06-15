from datetime import datetime, timezone

from vhe.live.bars import BarAggregator
from vhe.live.models import LiveQuote


def _quote(symbol: str, ltp: float, minute: int, volume: int = 1000) -> LiveQuote:
    ts = datetime(2026, 6, 15, 10, minute, 0, tzinfo=timezone.utc)
    return LiveQuote(
        timestamp=ts,
        symbol=symbol,
        ltp=ltp,
        open=ltp - 1,
        high=ltp + 1,
        low=ltp - 2,
        close=ltp,
        volume=volume,
    )


def test_bar_aggregator_closes_bucket_on_interval_change() -> None:
    agg = BarAggregator(interval_minutes=5)
    first = agg.update(_quote("AAA", 100.0, 1))
    second = agg.update(_quote("AAA", 101.0, 4))
    assert first is None
    assert second is None
    current = agg.current_bar("AAA")
    assert current is not None
    assert current.high == 101.0

    closed = agg.update(_quote("AAA", 102.0, 6))
    assert closed is not None
    assert closed.close == 101.0
    assert len(agg.history("AAA")) >= 1
