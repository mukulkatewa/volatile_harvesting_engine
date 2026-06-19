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


def test_stale_kill_switch_auto_clears_when_feed_recovers() -> None:
    runtime = PlatformRuntime.from_project_root()
    runtime.risk_guard.kill_switch = True
    runtime.risk_guard.kill_switch_reason = "stale_quote_feed"
    runtime.state.controls.kill_switch = True
    runtime.state.controls.kill_switch_reason = "stale_quote_feed"
    runtime.state.feed_health = {"is_stale": False, "market_closed": False}

    runtime._maybe_clear_stale_kill_switch(runtime.state.feed_health)

    assert runtime.risk_guard.kill_switch is False
    assert runtime.state.controls.kill_switch_reason is None


def test_sync_all_active_resting_orders_arms_multiple_symbols() -> None:
    from datetime import datetime, timezone

    from vhe.live.models import LiveQuote
    from vhe.platform.runtime import PlatformRuntime
    from vhe.strategies.dynamic_grid import DynamicGridPlan
    from vhe.strategies.regime import MarketRegime

    runtime = PlatformRuntime.from_project_root()
    runtime.reset_paper()
    now = datetime.now(tz=timezone.utc)
    for symbol, ltp in (("TCS", 2075.0), ("INFY", 1040.0)):
        quote = LiveQuote(
            timestamp=now,
            symbol=symbol,
            ltp=ltp,
            open=ltp,
            high=ltp + 1,
            low=ltp - 1,
            close=ltp,
            volume=100_000,
        )
        runtime.state.quotes[symbol] = quote
        runtime.state.plans[symbol] = DynamicGridPlan(
            symbol=symbol,
            fair_value=ltp - 5,
            spacing=3.0,
            regime=MarketRegime.RANGE,
            buy_levels=[ltp - 8, ltp - 11, ltp - 14],
            sell_target=None,
        )
        runtime.state.regimes[symbol] = MarketRegime.RANGE.value
    runtime.state.active_trading_symbols = ["TCS", "INFY"]
    runtime.orchestrator.sync_all_active_resting_orders()
    resting = list(runtime.orchestrator.paper_broker.resting_orders.values())
    assert len(resting) == 2
    assert {order.symbol for order in resting} == {"TCS", "INFY"}


def test_grid_fill_counter_resets_when_position_flattens() -> None:
    from vhe.backtest.models import Fill, OrderSide
    from datetime import datetime, timezone

    runtime = PlatformRuntime.from_project_root()
    runtime.reset_paper()
    orch = runtime.orchestrator
    orch._symbol_grid_fills["INFY"] = orch._max_grid_fills_per_symbol()

    # A sell that flattens the (zero) position must clear the lifetime counter
    sell = Fill(
        order_id="dg-INFY-x",
        symbol="INFY",
        side=OrderSide.SELL,
        price=1000.0,
        quantity=5,
        timestamp=datetime.now(tz=timezone.utc),
        fees=1.0,
        reason="dynamic_grid_mean_exit",
    )
    orch._after_fill(sell)
    assert "INFY" not in orch._symbol_grid_fills


def test_manual_kill_switch_not_auto_cleared() -> None:
    runtime = PlatformRuntime.from_project_root()
    runtime.risk_guard.kill_switch = True
    runtime.risk_guard.kill_switch_reason = "manual_kill"
    runtime.state.feed_health = {"is_stale": False, "market_closed": False}

    runtime._maybe_clear_stale_kill_switch(runtime.state.feed_health)

    assert runtime.risk_guard.kill_switch is True


def test_process_quote_does_not_crash_on_seed_allowed() -> None:
    from datetime import datetime, timezone

    from vhe.live.models import LiveQuote
    from vhe.platform.services.indicator_service import IndicatorSnapshot
    from vhe.strategies.regime import MarketRegime

    runtime = PlatformRuntime.from_project_root()
    quote = LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="RELIANCE",
        ltp=1400.0,
        open=1398.0,
        high=1402.0,
        low=1395.0,
        close=1400.0,
        volume=100_000,
    )
    snapshot = IndicatorSnapshot(
        symbol="RELIANCE",
        ltp=1400.0,
        ema_20=1395.0,
        ema_50=1388.0,
        atr_14=12.0,
        adx_14=18.0,
        fair_value=1398.0,
    )
    runtime.orchestrator.process_quote(quote, snapshot, MarketRegime.RANGE)
    assert runtime.state.quotes["RELIANCE"].ltp == 1400.0


def test_yfinance_paper_skips_stale_kill_switch() -> None:
    runtime = PlatformRuntime.from_project_root()
    runtime.config.strategies.feed.source = "yfinance"
    runtime.config.live.mode = "paper"
    runtime.config.live.risk.kill_switch_on_stale_quotes = True
    runtime._feed_started_at = None
    runtime.state.feed_health = {"is_stale": True, "market_closed": False, "stale_symbols": ["AAA"]}

    runtime._enforce_stale_feed_guard()

    assert runtime.risk_guard.kill_switch is False
