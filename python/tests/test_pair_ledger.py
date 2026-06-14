from datetime import datetime, timezone

from vhe.backtest.models import Fill, OrderSide
from vhe.execution.pair_ledger import PairLedger


def _fill(order_id: str, symbol: str, side: OrderSide, price: float, quantity: int, reason: str) -> Fill:
    return Fill(
        order_id=order_id,
        symbol=symbol,
        side=side,
        price=price,
        quantity=quantity,
        timestamp=datetime.now(tz=timezone.utc),
        fees=1.0,
        reason=reason,
    )


def test_pair_ledger_opens_and_closes_trade_with_realized_pnl() -> None:
    ledger = PairLedger()
    entry = [
        _fill("1", "AAA", OrderSide.SELL, 110, 4, "pair_short_a"),
        _fill("2", "BBB", OrderSide.BUY, 100, 4, "pair_long_b"),
    ]
    exit_ = [
        _fill("3", "AAA", OrderSide.BUY, 100, 4, "pair_exit_a"),
        _fill("4", "BBB", OrderSide.SELL, 102, 4, "pair_exit_b"),
    ]

    opened = ledger.apply_pair_fills("AAA/BBB", entry)
    closed = ledger.apply_pair_fills("AAA/BBB", exit_)

    assert opened is not None
    assert opened.trade_id == "pair-trade-1"
    assert closed is opened
    assert closed.status == "CLOSED"
    assert closed.realized_pnl == 44.0
    assert closed.fees_paid == 4.0


def test_pair_ledger_ignores_exit_without_open_trade() -> None:
    ledger = PairLedger()
    exit_ = [_fill("3", "AAA", OrderSide.BUY, 100, 4, "pair_exit_a")]

    assert ledger.apply_pair_fills("AAA/BBB", exit_) is None
    assert ledger.snapshot() == []
