from __future__ import annotations

import asyncio

import pytest

from vhe.platform.runtime import PlatformRuntime


class _BrokenSocket:
    async def send_json(self, _payload: dict) -> None:
        raise RuntimeError("connection closed")


class _HealthySocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


def test_broadcast_state_drops_disconnected_subscribers() -> None:
    runtime = PlatformRuntime.from_project_root()
    broken = _BrokenSocket()
    healthy = _HealthySocket()
    runtime.subscribers = {broken, healthy}

    asyncio.run(runtime._broadcast_state())

    assert broken not in runtime.subscribers
    assert healthy in runtime.subscribers
    assert len(healthy.sent) == 1


def test_reset_paper_clears_positions_and_risk_state() -> None:
    runtime = PlatformRuntime.from_project_root()
    runtime.paper_broker.cash = 10_000
    runtime.state.controls.last_risk_reject = "gross_exposure_limit"
    runtime.risk_guard.kill_switch = True

    runtime.reset_paper()

    assert runtime.paper_broker.cash == runtime.config.live.capital_cap_inr
    assert runtime.state.controls.last_risk_reject is None
    assert runtime.risk_guard.kill_switch is False
    assert runtime.state.portfolio["positions"] == []
    assert runtime.state.portfolio["gross_exposure_pct"] == 0.0
