from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from vhe.config.loader import PlatformConfig, load_platform_config
from vhe.execution.capital import CapitalAllocator
from vhe.execution.execution_engine import ExecutionEngine
from vhe.execution.pair_ledger import PairLedger
from vhe.execution.paper import PaperBroker
from vhe.execution.reconciler import Reconciler
from vhe.live.bars import BarAggregator, OhlcvBar
from vhe.live.feed_factory import FeedBuildResult, build_quote_feed
from vhe.live.market_session import MarketSessionConfig, SessionPhase, session_phase
from vhe.live.kite_ws import FeedHealth
from vhe.live.models import LiveQuote
from vhe.platform.events import event
from vhe.platform.services.indicator_service import IndicatorService
from vhe.platform.services.regime_service import RegimeService
from vhe.platform.services.strategy_orchestrator import StrategyOrchestrator, build_risk_guard
from vhe.platform.state import PlatformState
from vhe.storage.db import PlatformDatabase


@dataclass(slots=True)
class PlatformRuntime:
    config: PlatformConfig
    state: PlatformState = field(default_factory=PlatformState)
    paper_broker: PaperBroker = field(init=False)
    pair_ledger: PairLedger = field(init=False)
    risk_guard: object = field(init=False)
    capital_allocator: CapitalAllocator = field(init=False)
    indicator_service: IndicatorService = field(default_factory=IndicatorService)
    bar_aggregator: BarAggregator = field(init=False)
    regime_service: RegimeService = field(init=False)
    orchestrator: StrategyOrchestrator = field(init=False)
    execution: ExecutionEngine = field(init=False)
    reconciler: Reconciler = field(init=False)
    database: PlatformDatabase | None = field(init=False)
    feed_health: FeedHealth = field(init=False)
    feed_task: asyncio.Task | None = None
    heartbeat_task: asyncio.Task | None = None
    subscribers: set = field(default_factory=set)
    _project_root: Path = field(default_factory=lambda: _project_root())
    _market_session: MarketSessionConfig = field(init=False)
    _last_session_phase: SessionPhase | None = None

    @classmethod
    def from_project_root(cls, project_root: Path | None = None, live_config_name: str | None = None) -> PlatformRuntime:
        import os

        root = project_root or _project_root()
        config_name = live_config_name or os.environ.get("VHE_LIVE_CONFIG", "live_paper.yaml")
        config = load_platform_config(root, live_config_name=config_name)
        runtime = cls(config=config, _project_root=root)
        runtime.bootstrap()
        return runtime

    def bootstrap(self) -> None:
        live = self.config.live
        self.state.mode = live.mode
        self.bar_aggregator = BarAggregator(interval_minutes=self.config.strategies.feed.bar_interval_minutes)
        self.paper_broker = self._build_paper_broker(live.capital_cap_inr)
        self.pair_ledger = PairLedger()
        self.risk_guard = build_risk_guard(self.config)
        self.capital_allocator = CapitalAllocator(
            total_capital=live.capital_cap_inr,
            buckets=self.config.strategies.capital,
            max_symbols=live.max_symbols,
            max_grid_levels=live.max_grid_levels,
            max_symbol_deploy_pct=live.risk.max_symbol_deploy_pct,
        )
        self.regime_service = RegimeService(config=self.config.strategies.regime)
        db_path = live.storage.sqlite_path
        if not db_path.is_absolute():
            db_path = self._project_root / db_path
        self.database = PlatformDatabase(db_path)
        self.execution = ExecutionEngine.from_config(
            mode=live.mode,
            paper_broker=self.paper_broker,
            broker_config=live.broker,
        )
        self.reconciler = Reconciler(kite_broker=self.execution.kite_broker)
        self.orchestrator = StrategyOrchestrator(
            config=self.config,
            state=self.state,
            execution=self.execution,
            pair_ledger=self.pair_ledger,
            risk_guard=self.risk_guard,
            capital_allocator=self.capital_allocator,
            regime_service=self.regime_service,
            database=self.database,
        )
        self.state.capital = self.capital_allocator.buckets_snapshot()
        self.state.portfolio = self.execution.snapshot_portfolio({})
        self.state.feed_health = {"source": self.config.strategies.feed.source, "connected": False}
        self.state.phase = "2"
        self._market_session = _market_session_from_config(self.config)
        self._restore_persisted_events()

    def _build_paper_broker(self, initial_cash: float) -> PaperBroker:
        paper = self.config.live.paper
        return PaperBroker(
            initial_cash=initial_cash,
            aggressive_fills=paper.aggressive_fills,
            limit_tolerance_bps=paper.limit_tolerance_bps,
            fill_full_quantity=paper.fill_full_quantity,
        )

    def _restore_persisted_events(self) -> None:
        if self.database is None:
            return
        persisted = self.database.recent_events(limit=40)
        if persisted and not self.state.events:
            from datetime import datetime

            from vhe.platform.events import PlatformEvent

            for row in persisted:
                ts = row["timestamp"]
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                self.state.events.append(
                    PlatformEvent(
                        category=row["category"],
                        message=row["message"],
                        severity=row["severity"],
                        timestamp=ts,
                    )
                )

    def reset_paper(self) -> None:
        live = self.config.live
        self.paper_broker = self._build_paper_broker(live.capital_cap_inr)
        self.execution = ExecutionEngine.from_config(
            mode=live.mode,
            paper_broker=self.paper_broker,
            broker_config=live.broker,
        )
        self.orchestrator.execution = self.execution
        self.pair_ledger = PairLedger()
        self.orchestrator.pair_ledger = self.pair_ledger
        self.orchestrator.grid_strategy.reset_session()
        self.indicator_service.reset_session()
        self.risk_guard.kill_switch = False
        self.risk_guard.automation_paused = False
        self.state.controls.kill_switch = False
        self.state.controls.automation_paused = False
        self.state.controls.last_risk_reject = None
        self.state.orders.clear()
        self.state.fills.clear()
        self.state.pair_trades.clear()
        self.state.plans.clear()
        self.state.momentum_plans.clear()
        self.state.pair_plans.clear()
        self.state.regimes.clear()
        self.state.indicators.clear()
        self.state.execution_orders.clear()
        self.state.strategy_status.clear()
        self.state.portfolio = self.orchestrator._enrich_portfolio(self.paper_broker.snapshot(self.state.quotes))
        self.state.capital = self.capital_allocator.buckets_snapshot()
        self.state.append_event(event("control", "Paper account reset"))

    async def start_feed(self) -> None:
        if self.feed_task is not None and not self.feed_task.done():
            return
        self.feed_task = asyncio.create_task(self._run_feed(), name="vhe-feed")
        self.feed_task.add_done_callback(self._feed_task_done)
        if self.heartbeat_task is None or self.heartbeat_task.done():
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="vhe-heartbeat")

    def _feed_task_done(self, task: asyncio.Task) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            self.state.connected = False
            self.state.append_event(event("feed", f"Feed stopped: {exc}", "danger"))

    async def _run_feed(self) -> None:
        reconnect_seconds = self.config.live.broker.reconnect_seconds
        while True:
            try:
                build = build_quote_feed(self.config, project_root=self._project_root)
                self._init_feed_health(build)
                self.state.source = build.source
                self.state.connected = True
                message = f"Feed started ({build.source})"
                if build.warning:
                    message = f"{message} — {build.warning}"
                    self.state.append_event(event("feed", message, "warning"))
                    if self.database:
                        self.database.append_event(category="feed", message=message, severity="warning")
                else:
                    self.state.append_event(event("feed", message, "info"))

                async for quote in build.feed.stream():
                    await self._handle_quote(quote)
            except Exception as exc:
                self.state.connected = False
                if hasattr(self, "feed_health"):
                    self.feed_health.connected = False
                self.state.append_event(event("feed", f"Feed crashed: {exc}", "danger"))
                await asyncio.sleep(reconnect_seconds)

    def _init_feed_health(self, build: FeedBuildResult) -> None:
        self.feed_health = FeedHealth(
            source=build.source,
            connected=True,
            subscribed_symbols=build.subscribed_symbols,
            last_tick_at=None,
        )

    async def _handle_quote(self, quote: LiveQuote) -> None:
        self.feed_health.last_tick_at = datetime.now(tz=timezone.utc)
        self.feed_health.connected = True
        self.state.connected = True

        closed_bar = self.bar_aggregator.update(quote)
        snapshot = self.indicator_service.update(quote)
        if closed_bar is not None:
            snapshot = self.indicator_service.update(_bar_as_quote(closed_bar))

        regime = self.regime_service.classify(snapshot)
        phase = session_phase(self._market_session)
        self._on_session_phase_change(phase)
        self.orchestrator.process_quote(quote, snapshot, regime, session_phase=phase)
        self.state.bars = self.bar_aggregator.bars_snapshot()
        market_closed = phase in {SessionPhase.CLOSED, SessionPhase.PRE_MARKET}
        self.state.feed_health = self.feed_health.snapshot(
            quotes=self.state.quotes,
            max_stale_ms=self.config.live.risk.max_quote_stale_ms,
            market_closed=market_closed,
        )
        self.state.market_session = {
            "phase": phase.value,
            "timezone": self._market_session.timezone,
            "session_start": self._market_session.session_start.isoformat(timespec="minutes"),
            "session_end": self._market_session.session_end.isoformat(timespec="minutes"),
            "force_exit_time": self._market_session.force_exit_time.isoformat(timespec="minutes"),
        }
        if self.config.live.mode == "live":
            self.state.reconciliation = self.reconciler.sync()
        self._enforce_stale_feed_guard()
        await self._broadcast_state()

    def _on_session_phase_change(self, phase: SessionPhase) -> None:
        if phase == self._last_session_phase:
            return
        previous = self._last_session_phase
        self._last_session_phase = phase
        if phase == SessionPhase.CLOSED and previous not in {None, SessionPhase.CLOSED}:
            self.state.append_event(event("session", "NSE cash session closed — monitoring only", "info"))
        elif phase == SessionPhase.OPEN and previous in {SessionPhase.PRE_MARKET, SessionPhase.CLOSED, None}:
            self.state.append_event(event("session", "NSE session open — automation active", "info"))
        elif phase == SessionPhase.FORCE_EXIT and previous == SessionPhase.OPEN:
            self.state.append_event(event("session", "Force exit window — squaring intraday positions", "warning"))

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            if not hasattr(self, "feed_health"):
                continue
            phase = session_phase(self._market_session)
            self._on_session_phase_change(phase)
            market_closed = phase in {SessionPhase.CLOSED, SessionPhase.PRE_MARKET}
            self.state.market_session = {
                "phase": phase.value,
                "timezone": self._market_session.timezone,
                "session_start": self._market_session.session_start.isoformat(timespec="minutes"),
                "session_end": self._market_session.session_end.isoformat(timespec="minutes"),
                "force_exit_time": self._market_session.force_exit_time.isoformat(timespec="minutes"),
            }
            if hasattr(self, "feed_health"):
                self.state.feed_health = self.feed_health.snapshot(
                    quotes=self.state.quotes,
                    max_stale_ms=self.config.live.risk.max_quote_stale_ms,
                    market_closed=market_closed,
                )
            self._enforce_stale_feed_guard()
            await self._broadcast_state()

    def _enforce_stale_feed_guard(self) -> None:
        health = self.state.feed_health
        if health.get("market_closed"):
            return
        if not health.get("is_stale"):
            return
        if not self.config.live.risk.kill_switch_on_stale_quotes:
            return
        if self.risk_guard.kill_switch:
            return
        self.risk_guard.kill_switch = True
        self.state.controls.kill_switch = True
        self.state.controls.last_risk_reject = "stale_quote_feed"
        stale = ", ".join(health.get("stale_symbols", []))
        self.state.append_event(event("risk", f"Kill switch: stale quotes ({stale})", "danger"))

    async def _broadcast_state(self) -> None:
        if not self.subscribers:
            return
        snapshot = self.state.snapshot()
        stale: set = set()
        for websocket in list(self.subscribers):
            try:
                await websocket.send_json(snapshot)
            except Exception:
                stale.add(websocket)
        self.subscribers.difference_update(stale)


def _bar_as_quote(bar: OhlcvBar) -> LiveQuote:
    return LiveQuote(
        timestamp=bar.closed_at,
        symbol=bar.symbol,
        ltp=bar.close,
        open=bar.open,
        high=bar.high,
        low=bar.low,
        close=bar.close,
        volume=bar.volume,
    )


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "configs" / "live_paper.yaml").exists():
            return parent
    return Path.cwd()


def _market_session_from_config(config: PlatformConfig) -> MarketSessionConfig:
    from vhe.live.feed_factory import _market_session_config

    return _market_session_config(config)
