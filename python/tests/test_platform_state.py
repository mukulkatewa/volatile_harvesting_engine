from datetime import datetime, timezone

from vhe.backtest.models import Fill, OrderSide
from vhe.execution.paper import PaperBroker
from vhe.live.models import LiveQuote
from vhe.platform.state import PlatformState
import json


def test_platform_state_snapshot_serializes_quotes() -> None:
    state = PlatformState(connected=True, portfolio={"equity": 25000}, fills=[])
    state.quotes["AAA"] = LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=100,
        open=99,
        high=101,
        low=98,
        close=99,
        volume=1000,
    )

    snapshot = state.snapshot()

    assert snapshot["connected"] is True
    assert snapshot["mode"] == "paper"
    assert snapshot["phase"] == "2"
    assert "server_time" in snapshot
    assert "capital" in snapshot
    assert "regimes" in snapshot
    assert snapshot["quotes"]["AAA"]["ltp"] == 100
    assert snapshot["quotes"]["AAA"]["age_ms"] >= 0
    assert isinstance(snapshot["quotes"]["AAA"]["timestamp"], str)
    assert snapshot["portfolio"]["equity"] == 25000
    assert snapshot["fills"] == []
    assert snapshot["controls"]["kill_switch"] is False


def test_platform_state_snapshot_serializes_portfolio_fills() -> None:
    broker = PaperBroker()
    ts = datetime.now(tz=timezone.utc)
    broker.fills.append(
        Fill(
            order_id="demo-1",
            symbol="RELIANCE",
            side=OrderSide.BUY,
            price=100.0,
            quantity=1,
            timestamp=ts,
            fees=1.0,
            reason="test",
        )
    )
    quote = LiveQuote(timestamp=ts, symbol="RELIANCE", ltp=100, open=99, high=101, low=98, close=99, volume=1000)
    state = PlatformState(portfolio=broker.snapshot({"RELIANCE": quote}))

    snapshot = state.snapshot()
    json.dumps(snapshot)

    assert isinstance(snapshot["portfolio"]["fills"][0]["timestamp"], str)
    assert snapshot["portfolio"]["fills"][0]["side"] == "BUY"


def test_platform_server_reserves_pair_symbols_from_single_name_quantity() -> None:
    from vhe.execution.paper import PaperPosition
    from vhe.platform.runtime import PlatformRuntime

    runtime = PlatformRuntime.from_project_root()
    runtime.paper_broker.positions["RELIANCE"] = PaperPosition(symbol="RELIANCE", quantity=-4, avg_price=1000)
    runtime.paper_broker.positions["BEL"] = PaperPosition(symbol="BEL", quantity=3, avg_price=100)

    assert runtime.orchestrator.is_pair_symbol("RELIANCE") is True
    assert runtime.orchestrator.single_name_quantity("RELIANCE") == 0
    assert runtime.orchestrator.single_name_quantity("BEL") == 3

    runtime.paper_broker.positions.clear()
