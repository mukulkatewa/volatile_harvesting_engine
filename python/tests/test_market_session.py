from datetime import datetime
from zoneinfo import ZoneInfo

from vhe.live.market_session import MarketSessionConfig, SessionPhase, is_trading_window, session_phase


def _ist(*, hour: int, minute: int, weekday: int = 0) -> datetime:
    # 2026-06-15 is a Monday (weekday=0)
    base = datetime(2026, 6, 15, hour, minute, tzinfo=ZoneInfo("Asia/Kolkata"))
    if weekday:
        from datetime import timedelta

        base = base + timedelta(days=weekday)
    return base


def test_session_phase_open() -> None:
    config = MarketSessionConfig.from_strings()
    assert session_phase(config, now=_ist(hour=10, minute=0)) == SessionPhase.OPEN
    assert is_trading_window(config, now=_ist(hour=10, minute=0))


def test_session_phase_force_exit() -> None:
    config = MarketSessionConfig.from_strings()
    assert session_phase(config, now=_ist(hour=15, minute=15)) == SessionPhase.FORCE_EXIT


def test_session_phase_closed_after_hours() -> None:
    config = MarketSessionConfig.from_strings()
    assert session_phase(config, now=_ist(hour=15, minute=35)) == SessionPhase.CLOSED


def test_session_phase_weekend_closed() -> None:
    config = MarketSessionConfig.from_strings()
    assert session_phase(config, now=_ist(hour=10, minute=0, weekday=5)) == SessionPhase.CLOSED
