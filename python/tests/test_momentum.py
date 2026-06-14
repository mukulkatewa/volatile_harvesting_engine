from datetime import datetime, timezone

from vhe.live.models import LiveQuote
from vhe.strategies.momentum import MomentumInputs, MomentumStrategy
from vhe.strategies.regime import MarketRegime



def _quote(price: float) -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=price,
        open=price - 1,
        high=price,
        low=price - 2,
        close=price - 1,
        volume=10_000,
    )



def test_momentum_strategy_arms_only_in_trend_up() -> None:
    strategy = MomentumStrategy()
    plan = strategy.build_plan(MomentumInputs(_quote(110), MarketRegime.TREND_UP, ema_20=105, ema_50=100, atr_14=4))

    assert plan.enabled is True
    assert plan.entry_price is not None



def test_momentum_strategy_blocks_range_regime() -> None:
    strategy = MomentumStrategy()
    plan = strategy.build_plan(MomentumInputs(_quote(110), MarketRegime.RANGE, ema_20=105, ema_50=100, atr_14=4))

    assert plan.enabled is False
    assert plan.reason == "regime_not_trend_up"
