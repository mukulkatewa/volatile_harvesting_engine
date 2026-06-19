from datetime import datetime, timezone

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.execution.execution_engine import ExecutionEngine
from vhe.execution.paper import PaperBroker
from vhe.live.models import LiveQuote
from vhe.strategies.dynamic_grid import DynamicGridPlan, DynamicGridStrategy
from vhe.strategies.regime import MarketRegime


def _quote(symbol: str, ltp: float, *, low: float | None = None) -> LiveQuote:
    low_price = low if low is not None else ltp - 1
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol=symbol,
        ltp=ltp,
        open=ltp,
        high=ltp + 1,
        low=low_price,
        close=ltp,
        volume=100_000,
    )


def test_paper_broker_places_and_fills_resting_limit_on_bar_low() -> None:
    broker = PaperBroker(initial_cash=25_000, use_bar_low_for_fills=True)
    order = Order(
        "dg-RELIANCE-L1",
        "RELIANCE",
        OrderSide.BUY,
        OrderType.LIMIT,
        1320.0,
        5,
        _quote("RELIANCE", 1326.0).timestamp,
        "dynamic_grid_level_1",
    )

    assert broker.place_resting(order) is True
    assert len(broker.resting_orders) == 1

    fills = broker.fill_resting({"RELIANCE": _quote("RELIANCE", 1326.0, low=1318.0)})

    assert len(fills) == 1
    assert fills[0].price == 1320.0
    assert broker.positions["RELIANCE"].quantity == 5
    assert broker.resting_orders == {}


def test_execution_engine_syncs_resting_grid_orders() -> None:
    broker = PaperBroker(initial_cash=25_000, use_bar_low_for_fills=True)
    engine = ExecutionEngine(mode="paper", paper_broker=broker)
    strategy = DynamicGridStrategy()
    plan = DynamicGridPlan(
        symbol="RELIANCE",
        fair_value=1325.0,
        spacing=5.0,
        regime=MarketRegime.RANGE,
        buy_levels=[1320.0, 1315.0],
        sell_target=None,
    )
    quote = _quote("RELIANCE", 1326.0)

    resting = strategy.resting_buy_orders_from_plan(plan, quote, current_quantity=0)
    assert len(resting) == 2
    assert resting[0].order_id == "dg-RELIANCE-L1"

    assert engine.place_resting(resting[0]) is True
    assert engine.place_resting(resting[0]) is True
    assert len(broker.resting_orders) == 1

    fills = engine.process_resting({"RELIANCE": _quote("RELIANCE", 1326.0, low=1319.0)})
    assert len(fills) == 1
    assert broker.positions["RELIANCE"].quantity == resting[0].quantity
