from vhe.backtest.costs import EquityIntradayCostModel
from vhe.backtest.models import OrderSide


def test_equity_intraday_cost_model_charges_sell_stt_only() -> None:
    model = EquityIntradayCostModel()

    buy_cost = model.estimate(side=OrderSide.BUY, price=100.0, quantity=10)
    sell_cost = model.estimate(side=OrderSide.SELL, price=100.0, quantity=10)

    assert buy_cost > 0
    assert sell_cost > buy_cost

