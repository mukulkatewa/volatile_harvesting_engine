from datetime import datetime, timezone

from vhe.live.models import LiveQuote, MarketDepthLevel
from vhe.strategies.dynamic_grid import DynamicGridConfig, DynamicGridInputs, DynamicGridPlan, DynamicGridStrategy
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



def test_dynamic_grid_keeps_ladder_when_price_above_fair_value_band() -> None:
    strategy = DynamicGridStrategy(DynamicGridConfig(no_buy_above_fair_value_pct=0.012))
    plan = strategy.build_plan(
        DynamicGridInputs(quote=_quote(102), fair_value=100, atr_14=10, regime=MarketRegime.RANGE)
    )

    assert plan.buy_levels
    assert all(level < 100 for level in plan.buy_levels)
    assert strategy.orders_from_plan(plan, _quote(102), current_quantity=0, seed_deploy_allowed=True) == []
    resting = strategy.resting_buy_orders_from_plan(plan, _quote(102), current_quantity=0)
    assert len(resting) == 1
    assert resting[0].price < 102


def test_seed_deploy_enters_base_below_fair_value() -> None:
    strategy = DynamicGridStrategy(DynamicGridConfig(seed_deploy_pct=0.12))
    plan = strategy.build_plan(
        DynamicGridInputs(quote=_quote(98), fair_value=100, atr_14=10, regime=MarketRegime.RANGE)
    )
    orders = strategy.orders_from_plan(plan, _quote(98), current_quantity=0, seed_deploy_allowed=True)

    assert any(order.reason == "dynamic_grid_seed_deploy" and order.side.value == "BUY" for order in orders)


def test_seed_deploy_skipped_above_fair_value() -> None:
    strategy = DynamicGridStrategy(DynamicGridConfig(seed_deploy_pct=0.12))
    plan = strategy.build_plan(
        DynamicGridInputs(quote=_quote(101), fair_value=100, atr_14=10, regime=MarketRegime.RANGE)
    )
    orders = strategy.orders_from_plan(plan, _quote(101), current_quantity=0, seed_deploy_allowed=True)

    assert not any(order.reason == "dynamic_grid_seed_deploy" for order in orders)


def test_mean_exit_requires_harvest_band_above_cost() -> None:
    strategy = DynamicGridStrategy(DynamicGridConfig(min_harvest_pct=0.0035))
    plan = DynamicGridPlan(
        symbol="AAA",
        fair_value=100,
        spacing=3.5,
        regime=MarketRegime.RANGE,
        buy_levels=[96.5],
        sell_target=100.0,
    )

    # Gain of only 0.1% does not clear the 0.35% cost band -> hold.
    thin = strategy.orders_from_plan(plan, _quote(101), current_quantity=5, average_cost=99.9)
    assert not any(order.reason == "dynamic_grid_mean_exit" for order in thin)

    # Gain above the band -> harvest.
    wide = strategy.orders_from_plan(plan, _quote(101), current_quantity=5, average_cost=96.0)
    assert any(order.reason == "dynamic_grid_mean_exit" for order in wide)


def test_seed_entry_requires_dip_below_cost_band() -> None:
    strategy = DynamicGridStrategy(DynamicGridConfig(seed_deploy_pct=0.20, min_harvest_pct=0.0035))
    # Price only 0.1% below mean -> inside cost band -> no seed.
    plan = strategy.build_plan(
        DynamicGridInputs(quote=_quote(99.9), fair_value=100, atr_14=10, regime=MarketRegime.RANGE)
    )
    near = strategy.orders_from_plan(plan, _quote(99.9), current_quantity=0, seed_deploy_allowed=True)
    assert not any(order.reason == "dynamic_grid_seed_deploy" for order in near)


def test_min_order_notional_floors_quantity() -> None:
    strategy = DynamicGridStrategy(DynamicGridConfig(min_order_notional=4000.0))
    assert strategy._sized_quantity(500.0, 1000.0) == 4  # floored to 4000 notional
    assert strategy._sized_quantity(9000.0, 1000.0) == 9  # capital above floor wins


def test_mean_exit_blocked_when_unprofitable() -> None:
    strategy = DynamicGridStrategy()
    plan = DynamicGridPlan(
        symbol="AAA",
        fair_value=100,
        spacing=3.5,
        regime=MarketRegime.RANGE,
        buy_levels=[96.5, 93.0],
        sell_target=100.0,
    )

    profitable = strategy.orders_from_plan(plan, _quote(101), current_quantity=5, average_cost=95.0)
    assert any(order.reason == "dynamic_grid_mean_exit" for order in profitable)

    losing = strategy.orders_from_plan(plan, _quote(101), current_quantity=5, average_cost=105.0)
    assert not any(order.reason == "dynamic_grid_mean_exit" for order in losing)


def test_dynamic_grid_blocks_new_buys_outside_range() -> None:
    strategy = DynamicGridStrategy()
    plan = strategy.build_plan(
        DynamicGridInputs(quote=_quote(98), fair_value=100, atr_14=10, regime=MarketRegime.TREND_UP)
    )

    assert plan.buy_levels == []
    assert plan.reset_reason == "initial_grid"


def test_dynamic_grid_does_not_rebuy_filled_level() -> None:
    strategy = DynamicGridStrategy()
    plan = DynamicGridPlan(
        symbol="AAA",
        fair_value=100,
        spacing=3.5,
        regime=MarketRegime.RANGE,
        buy_levels=[96.5, 93.0, 89.5, 86.0, 82.5],
        sell_target=None,
    )
    quote = _quote(96)

    first = strategy.orders_from_plan(plan, quote, current_quantity=0)
    assert len(first) == 1
    assert first[0].reason == "dynamic_grid_level_1"
    strategy.on_fill_reason("AAA", "dynamic_grid_level_1")

    second = strategy.orders_from_plan(plan, quote, current_quantity=first[0].quantity)
    assert not any(order.reason == "dynamic_grid_level_1" for order in second)


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
