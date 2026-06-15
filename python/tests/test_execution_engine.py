from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.execution.execution_engine import ExecutionEngine
from vhe.execution.order_fsm import OrderState
from vhe.execution.paper import PaperBroker
from vhe.live.models import LiveQuote
from datetime import datetime, timezone


def _quote() -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=100.0,
        open=99.0,
        high=101.0,
        low=98.0,
        close=99.5,
        volume=1000,
    )


def test_execution_engine_paper_fill() -> None:
    broker = PaperBroker(initial_cash=25_000.0)
    engine = ExecutionEngine(mode="paper", paper_broker=broker)
    order = Order(
        order_id="t1",
        symbol="AAA",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=100.0,
        quantity=1,
        created_at=_quote().timestamp,
        reason="test",
    )
    fill = engine.submit(order, _quote())
    assert fill is not None
    managed = engine.order_fsm.get("t1")
    assert managed is not None
    assert managed.state == OrderState.FILLED
