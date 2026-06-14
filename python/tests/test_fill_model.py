from datetime import datetime

from vhe.backtest.fill import ConservativeFillModel
from vhe.backtest.models import MarketBar, Order, OrderSide, OrderType


def test_conservative_limit_buy_requires_trade_through_price() -> None:
    model = ConservativeFillModel(slippage_bps=0, require_price_improvement=True)
    order = Order(
        order_id="1",
        symbol="AAA",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=100.0,
        quantity=5,
        created_at=datetime(2026, 6, 14, 9, 20),
        reason="grid_level_1",
    )

    no_fill_bar = MarketBar(datetime(2026, 6, 14, 9, 21), "AAA", 101.0, 102.0, 100.0, 101.0, 1000)
    fill_bar = MarketBar(datetime(2026, 6, 14, 9, 22), "AAA", 101.0, 102.0, 99.95, 100.5, 1000)

    assert model.try_fill(order, no_fill_bar) is None
    assert model.try_fill(order, fill_bar) is not None

