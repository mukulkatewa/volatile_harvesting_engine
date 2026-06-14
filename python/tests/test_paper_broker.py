from datetime import datetime, timezone

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.execution.paper import PaperBroker
from vhe.live.models import LiveQuote



def _quote(price: float) -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=price,
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=10_000,
    )



def test_paper_broker_applies_buy_and_sell_fills() -> None:
    broker = PaperBroker(initial_cash=25_000)
    buy = Order("1", "AAA", OrderSide.BUY, OrderType.LIMIT, 100, 10, _quote(100).timestamp, "test_buy")
    sell = Order("2", "AAA", OrderSide.SELL, OrderType.LIMIT, 105, 10, _quote(105).timestamp, "test_sell")

    assert broker.submit(buy, _quote(100)) is not None
    assert broker.positions["AAA"].quantity == 10
    assert broker.submit(sell, _quote(105)) is not None

    snapshot = broker.snapshot({"AAA": _quote(105)})
    assert snapshot["positions"][0]["quantity"] == 0
    assert snapshot["realized_pnl"] > 0
    assert snapshot["fees_paid"] > 0



def test_paper_broker_deduplicates_order_ids() -> None:
    broker = PaperBroker(initial_cash=25_000)
    order = Order("1", "AAA", OrderSide.BUY, OrderType.LIMIT, 100, 10, _quote(100).timestamp, "test_buy")

    assert broker.submit(order, _quote(100)) is not None
    assert broker.submit(order, _quote(100)) is None


def test_paper_broker_supports_simulated_short_then_cover() -> None:
    broker = PaperBroker(initial_cash=25_000)
    sell = Order("short-1", "AAA", OrderSide.SELL, OrderType.LIMIT, 105, 5, _quote(105).timestamp, "short")
    buy = Order("cover-1", "AAA", OrderSide.BUY, OrderType.LIMIT, 100, 5, _quote(100).timestamp, "cover")

    assert broker.submit(sell, _quote(105)) is not None
    assert broker.positions["AAA"].quantity == -5
    assert broker.submit(buy, _quote(100)) is not None

    snapshot = broker.snapshot({"AAA": _quote(100)})
    assert snapshot["positions"][0]["quantity"] == 0
    assert snapshot["realized_pnl"] > 0


def test_paper_broker_atomic_batch_rejects_all_when_one_leg_cannot_fill() -> None:
    broker = PaperBroker(initial_cash=25_000)
    sell = Order("pair-1", "AAA", OrderSide.SELL, OrderType.LIMIT, 100, 5, _quote(100).timestamp, "pair_short")
    buy = Order("pair-2", "AAA", OrderSide.BUY, OrderType.LIMIT, 99, 5, _quote(100).timestamp, "pair_long")

    fills = broker.submit_atomic([sell, buy], {"AAA": _quote(100)})

    assert fills == []
    assert broker.positions == {}
    assert broker.cash == 25_000
    assert broker.seen_order_ids == set()


def test_paper_broker_atomic_batch_applies_all_legs() -> None:
    broker = PaperBroker(initial_cash=25_000)
    sell = Order("pair-1", "AAA", OrderSide.SELL, OrderType.LIMIT, 100, 5, _quote(100).timestamp, "pair_short")
    buy = Order("pair-2", "AAA", OrderSide.BUY, OrderType.LIMIT, 100, 2, _quote(100).timestamp, "pair_long")

    fills = broker.submit_atomic([sell, buy], {"AAA": _quote(100)})

    assert [fill.order_id for fill in fills] == ["pair-1", "pair-2"]
    assert broker.positions["AAA"].quantity == -3
    assert broker.seen_order_ids == {"pair-1", "pair-2"}
