from datetime import datetime, timezone

from vhe.backtest.models import Order, OrderSide, OrderType
from vhe.execution.risk import RiskConfig, RiskGuard



def _order(quantity: int = 1) -> Order:
    return Order(
        order_id="risk-1",
        symbol="AAA",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        price=100,
        quantity=quantity,
        created_at=datetime.now(tz=timezone.utc),
        reason="risk_test",
    )



def test_risk_guard_blocks_kill_switch_and_pause() -> None:
    guard = RiskGuard(RiskConfig())

    guard.kill_switch = True
    assert guard.evaluate(_order(), {"initial_cash": 25_000, "equity": 25_000, "positions": []}).reason == "kill_switch_active"

    guard.kill_switch = False
    guard.automation_paused = True
    assert guard.evaluate(_order(), {"initial_cash": 25_000, "equity": 25_000, "positions": []}).reason == "automation_paused"



def test_risk_guard_blocks_daily_loss_and_quantity_limit() -> None:
    guard = RiskGuard(RiskConfig(max_daily_loss_pct=0.01, max_single_symbol_qty=10))

    assert guard.evaluate(_order(), {"initial_cash": 25_000, "equity": 24_000, "positions": []}).reason == "daily_loss_limit"
    assert guard.evaluate(_order(quantity=11), {"initial_cash": 25_000, "equity": 25_000, "positions": []}).reason == "symbol_quantity_limit"
