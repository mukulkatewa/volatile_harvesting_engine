from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from zoneinfo import ZoneInfo


class SessionPhase(str, Enum):
    PRE_MARKET = "pre_market"
    OPEN = "open"
    FORCE_EXIT = "force_exit"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class MarketSessionConfig:
    timezone: str = "Asia/Kolkata"
    session_start: time = time(9, 15)
    session_end: time = time(15, 30)
    force_exit_time: time = time(15, 10)

    @classmethod
    def from_strings(
        cls,
        *,
        timezone: str = "Asia/Kolkata",
        session_start: str = "09:15",
        session_end: str = "15:30",
        force_exit_time: str = "15:10",
    ) -> MarketSessionConfig:
        return cls(
            timezone=timezone,
            session_start=time.fromisoformat(session_start),
            session_end=time.fromisoformat(session_end),
            force_exit_time=time.fromisoformat(force_exit_time),
        )


def now_in_session_tz(config: MarketSessionConfig, *, now: datetime | None = None) -> datetime:
    moment = now or datetime.now(tz=ZoneInfo("UTC"))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    return moment.astimezone(ZoneInfo(config.timezone))


def session_phase(config: MarketSessionConfig, *, now: datetime | None = None) -> SessionPhase:
    local = now_in_session_tz(config, now=now)
    if local.weekday() >= 5:
        return SessionPhase.CLOSED
    current = local.time()
    if current < config.session_start:
        return SessionPhase.PRE_MARKET
    if current >= config.session_end:
        return SessionPhase.CLOSED
    if current >= config.force_exit_time:
        return SessionPhase.FORCE_EXIT
    return SessionPhase.OPEN


def is_trading_window(config: MarketSessionConfig, *, now: datetime | None = None) -> bool:
    return session_phase(config, now=now) == SessionPhase.OPEN


def allows_new_risk(config: MarketSessionConfig, *, now: datetime | None = None) -> bool:
    return session_phase(config, now=now) == SessionPhase.OPEN
