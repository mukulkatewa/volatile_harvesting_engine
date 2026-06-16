from datetime import datetime, timezone

from vhe.live.models import LiveQuote
from vhe.strategies.dynamic_grid import DynamicGridConfig, DynamicGridInputs, DynamicGridPlan, DynamicGridStrategy
from vhe.strategies.regime import MarketRegime


def _quote(symbol: str, ltp: float) -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol=symbol,
        ltp=ltp,
        open=ltp,
        high=ltp + 1,
        low=ltp - 1,
        close=ltp,
        volume=1_000_000,
    )


def test_dynamic_grid_seed_deploy_puts_capital_to_work() -> None:
    strategy = DynamicGridStrategy(
        DynamicGridConfig(
            symbol_capital=10_000,
            max_levels=5,
            seed_deploy_pct=0.40,
            level_capital_multiplier=1.0,
        )
    )
    plan = DynamicGridPlan(
        symbol="BEL",
        fair_value=410,
        spacing=3,
        regime=MarketRegime.RANGE,
        buy_levels=[407, 404, 401, 398, 395],
        sell_target=None,
    )

    orders = strategy.orders_from_plan(plan, _quote("BEL", 408), current_quantity=0)

    assert len(orders) == 1
    assert orders[0].reason == "dynamic_grid_seed_deploy"
    assert orders[0].quantity == 9


def test_dynamic_grid_sells_full_position_at_mean() -> None:
    strategy = DynamicGridStrategy(DynamicGridConfig(symbol_capital=10_000, max_levels=5))
    plan = DynamicGridPlan(
        symbol="BEL",
        fair_value=410,
        spacing=3,
        regime=MarketRegime.RANGE,
        buy_levels=[],
        sell_target=410,
    )

    orders = strategy.orders_from_plan(plan, _quote("BEL", 411), current_quantity=37)

    assert len(orders) == 1
    assert orders[0].side.value == "SELL"
    assert orders[0].quantity == 37


def test_paper_broker_aggressive_fills_near_limit() -> None:
    from vhe.backtest.models import Order, OrderSide, OrderType
    from vhe.execution.paper import PaperBroker

    broker = PaperBroker(initial_cash=25_000, aggressive_fills=True, limit_tolerance_bps=50, fill_full_quantity=True)
    order = Order(
        order_id="1",
        symbol="AAA",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=100,
        quantity=10,
        created_at=_quote("AAA", 100).timestamp,
        reason="test",
    )

    fill = broker.submit(order, _quote("AAA", 100.4))

    assert fill is not None
    assert fill.quantity == 10
