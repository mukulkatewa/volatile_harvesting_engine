from datetime import datetime, timezone

from vhe.live.models import LiveQuote
from vhe.platform.state import PlatformState



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
    assert "server_time" in snapshot
    assert snapshot["quotes"]["AAA"]["ltp"] == 100
    assert snapshot["quotes"]["AAA"]["age_ms"] >= 0
    assert snapshot["portfolio"]["equity"] == 25000
    assert snapshot["fills"] == []
    assert snapshot["controls"]["kill_switch"] is False
