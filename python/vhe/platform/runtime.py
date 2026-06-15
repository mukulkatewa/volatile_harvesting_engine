from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from vhe.config.loader import PlatformConfig, load_platform_config
from vhe.execution.capital import CapitalAllocator
from vhe.execution.pair_ledger import PairLedger
from vhe.execution.paper import PaperBroker
from vhe.live.feed import SimulatedQuoteFeed
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
    regime_service: RegimeService = field(init=False)
    orchestrator: StrategyOrchestrator = field(init=False)
    database: PlatformDatabase | None = field(init=False)
    feed_task: asyncio.Task | None = None
    subscribers: set = field(default_factory=set)

    @classmethod
    def from_project_root(cls, project_root: Path | None = None) -> PlatformRuntime:
        config = load_platform_config(project_root)
        runtime = cls(config=config)
        runtime.bootstrap()
        return runtime

    def bootstrap(self) -> None:
        live = self.config.live
        self.state.mode = live.mode
        self.state.source = self.config.strategies.feed.source
        self.paper_broker = PaperBroker(initial_cash=live.capital_cap_inr)
        self.pair_ledger = PairLedger()
        self.risk_guard = build_risk_guard(self.config)
        self.capital_allocator = CapitalAllocator(
            total_capital=live.capital_cap_inr,
            buckets=self.config.strategies.capital,
            max_symbols=live.max_symbols,
            max_grid_levels=live.max_grid_levels,
        )
        self.regime_service = RegimeService(config=self.config.strategies.regime)
        db_path = live.storage.sqlite_path
        if not db_path.is_absolute():
            db_path = _project_root() / db_path
        self.database = PlatformDatabase(db_path)
        self.orchestrator = StrategyOrchestrator(
            config=self.config,
            state=self.state,
            paper_broker=self.paper_broker,
            pair_ledger=self.pair_ledger,
            risk_guard=self.risk_guard,
            capital_allocator=self.capital_allocator,
            regime_service=self.regime_service,
            database=self.database,
        )
        self.state.capital = self.capital_allocator.buckets_snapshot()
        self._restore_persisted_events()

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
        self.paper_broker = PaperBroker(initial_cash=live.capital_cap_inr)
        self.pair_ledger = PairLedger()
        self.orchestrator.paper_broker = self.paper_broker
        self.orchestrator.pair_ledger = self.pair_ledger
        self.state.orders.clear()
        self.state.fills.clear()
        self.state.pair_trades.clear()
        self.state.portfolio = self.paper_broker.snapshot(self.state.quotes)
        self.state.controls.last_risk_reject = None
        self.state.append_event(event("control", "Paper account reset"))

    async def start_feed(self) -> None:
        if self.feed_task is not None and not self.feed_task.done():
            return
        self.feed_task = asyncio.create_task(self._run_feed())

    async def _run_feed(self) -> None:
        feed_cfg = self.config.strategies.feed
        feed = SimulatedQuoteFeed(symbols=feed_cfg.symbols, interval_seconds=feed_cfg.interval_seconds)
        self.state.connected = True
        self.state.append_event(event("feed", f"Feed started ({feed_cfg.source})", "info"))
        async for quote in feed.stream():
            snapshot = self.indicator_service.update(quote)
            regime = self.regime_service.classify(snapshot)
            self.orchestrator.process_quote(quote, snapshot, regime)
            await self._broadcast_state()

    async def _broadcast_state(self) -> None:
        if not self.subscribers:
            return
        snapshot = self.state.snapshot()
        stale = set()
        for websocket in self.subscribers:
            try:
                await websocket.send_json(snapshot)
            except RuntimeError:
                stale.add(websocket)
        self.subscribers.difference_update(stale)


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "configs" / "live_paper.yaml").exists():
            return parent
    return Path.cwd()
