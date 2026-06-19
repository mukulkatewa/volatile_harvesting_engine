from datetime import datetime, timezone

from vhe.live.models import LiveQuote, MarketDepthLevel
from vhe.strategies.dynamic_grid import DynamicGridPlan, DynamicGridStrategy
from vhe.strategies.regime import MarketRegime


def _quote(ltp: float) -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=ltp,
        open=100,
        high=104,
        low=96,
        close=100,
        volume=100_000,
        bid=MarketDepthLevel(price=ltp - 0.05, quantity=1000),
        ask=MarketDepthLevel(price=ltp + 0.05, quantity=1000),
    )


def test_resting_buy_orders_use_stable_ids_without_ltp_cross() -> None:
    strategy = DynamicGridStrategy()
    plan = DynamicGridPlan(
        symbol="AAA",
        fair_value=100,
        spacing=3.5,
        regime=MarketRegime.RANGE,
        buy_levels=[96.5, 93.0, 89.5],
        sell_target=None,
    )

    resting = strategy.resting_buy_orders_from_plan(plan, _quote(102), current_quantity=0)
    immediate = strategy.orders_from_plan(plan, _quote(102), current_quantity=0)

    assert len(resting) == 1
    assert resting[0].order_id == "dg-AAA-L1"
    assert immediate == []
