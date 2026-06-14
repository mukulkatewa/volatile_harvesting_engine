from datetime import datetime, timezone

from vhe.live.models import LiveQuote
from vhe.strategies.pair_spread import PairConfig, PairInputs, PairSpreadStrategy
from vhe.strategies.regime import MarketRegime



def _quote(symbol: str, price: float) -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol=symbol,
        ltp=price,
        open=price,
        high=price,
        low=price,
        close=price,
        volume=100_000,
    )



def test_pair_spread_strategy_generates_short_a_long_b_when_spread_high() -> None:
    strategy = PairSpreadStrategy(PairConfig("AAA", "BBB", hedge_ratio=1.0, mean=0.0, std=0.01, entry_z=1.5))
    inputs = PairInputs(_quote("AAA", 102), _quote("BBB", 100), MarketRegime.RANGE)

    plan = strategy.build_plan(inputs)
    orders = strategy.orders_from_plan(plan, inputs.quote_a, inputs.quote_b)

    assert plan.enabled is True
    assert plan.action == "SHORT_A_LONG_B"
    assert [order.reason for order in orders] == ["pair_short_a", "pair_long_b"]



def test_pair_spread_strategy_waits_inside_band() -> None:
    strategy = PairSpreadStrategy(PairConfig("AAA", "BBB", hedge_ratio=1.0, mean=0.0, std=0.5, entry_z=1.5))
    plan = strategy.build_plan(PairInputs(_quote("AAA", 101), _quote("BBB", 100), MarketRegime.RANGE))

    assert plan.enabled is False
    assert plan.action == "WAIT"
