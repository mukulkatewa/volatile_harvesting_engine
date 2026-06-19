from datetime import datetime, timezone

from vhe.live.models import LiveQuote
from vhe.strategies.momentum import MomentumInputs, MomentumStrategy
from vhe.strategies.regime import MarketRegime


def _quote(ltp: float = 105) -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=ltp,
        open=100,
        high=106,
        low=99,
        close=ltp,
        volume=100_000,
    )


def test_momentum_blocked_by_negative_sentiment() -> None:
    strategy = MomentumStrategy()
    plan = strategy.build_plan(
        MomentumInputs(
            quote=_quote(),
            regime=MarketRegime.TREND_UP,
            ema_20=100,
            ema_50=98,
            atr_14=2,
            sentiment_allows_entry=False,
        )
    )
    assert plan.enabled is False
    assert plan.reason == "sentiment_blocked"
