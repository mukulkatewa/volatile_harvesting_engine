from datetime import datetime, timezone

from vhe.live.models import LiveQuote, MarketDepthLevel
from vhe.strategies.dynamic_grid import DynamicGridInputs, DynamicGridStrategy
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



def test_dynamic_grid_creates_atr_spaced_levels_only_in_range() -> None:
    strategy = DynamicGridStrategy()
    plan = strategy.build_plan(
        DynamicGridInputs(quote=_quote(98), fair_value=100, atr_14=10, regime=MarketRegime.RANGE)
    )

    assert plan.spacing == 3.5
    assert plan.buy_levels[:2] == [96.5, 93.0]



def test_dynamic_grid_blocks_new_buys_outside_range() -> None:
    strategy = DynamicGridStrategy()
    plan = strategy.build_plan(
        DynamicGridInputs(quote=_quote(98), fair_value=100, atr_14=10, regime=MarketRegime.TREND_UP)
    )

    assert plan.buy_levels == []
    assert plan.reset_reason == "initial_grid"


def test_dynamic_grid_exits_position_on_crash_regime() -> None:
    strategy = DynamicGridStrategy()
    plan = strategy.build_plan(
        DynamicGridInputs(
            quote=_quote(90),
            fair_value=100,
            atr_14=10,
            regime=MarketRegime.CRASH,
            current_quantity=12,
        )
    )
    orders = strategy.orders_from_plan(plan, _quote(90), current_quantity=12)

    assert len(orders) == 1
    assert orders[0].side.value == "SELL"
    assert orders[0].quantity == 12
    assert orders[0].reason == "dynamic_grid_regime_exit"
