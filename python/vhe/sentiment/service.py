from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone

from vhe.sentiment.collectors.hackernews import HackerNewsCollector
from vhe.sentiment.collectors.last30days_bridge import Last30DaysCollector
from vhe.sentiment.collectors.reddit import RedditCollector
from vhe.sentiment.engine import SentimentEngine
from vhe.sentiment.models import SentimentAction, SentimentSnapshot, SentimentStatus, SymbolSentiment
from vhe.sentiment.scoring import portfolio_snapshot
from vhe.sentiment.store import SentimentStore
from vhe.storage.db import PlatformDatabase


@dataclass(slots=True)
class SentimentConfig:
    enabled: bool = True
    refresh_minutes: float = 15.0
    lookback_days: int = 30
    reddit_enabled: bool = True
    hackernews_enabled: bool = True
    last30days_enabled: bool = True
    last30days_symbols_per_refresh: int = 2
    last30days_search_sources: str = "reddit,hackernews,web"
    last30days_timeout_seconds: float = 90.0
    max_items_per_source: int = 20
    half_life_hours: float = 12.0
    halt_score: float = -0.55
    elevated_score: float = -0.25
    momentum_min_score: float = -0.15
    reduce_size_multiplier: float = 0.5
    widen_spacing_multiplier: float = 1.35


LAST30DAYS_REPO_URL = "https://github.com/mvanhorn/last30days-skill"


@dataclass(slots=True)
class SentimentService:
    config: SentimentConfig
    symbols: list[str]
    database: PlatformDatabase | None = None
    engine: SentimentEngine = field(init=False)
    store: SentimentStore = field(init=False)
    _symbols: dict[str, SymbolSentiment] = field(default_factory=dict)
    _last_refresh_at: datetime | None = None
    _sources_active: tuple[str, ...] = ()
    _refresh_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _refresh_task: asyncio.Task | None = None
    _last30days_collector: Last30DaysCollector | None = field(init=False, default=None)
    _last30days_rotation: int = 0

    def __post_init__(self) -> None:
        collectors = []
        if self.config.reddit_enabled:
            collectors.append(RedditCollector(max_items=self.config.max_items_per_source))
        if self.config.hackernews_enabled:
            collectors.append(HackerNewsCollector(max_items=self.config.max_items_per_source))
        if self.config.last30days_enabled:
            bridge = Last30DaysCollector(
                lookback_days=self.config.lookback_days,
                search_sources=self.config.last30days_search_sources,
                timeout_seconds=self.config.last30days_timeout_seconds,
            )
            if bridge.available:
                self._last30days_collector = bridge
        self.engine = SentimentEngine(
            collectors,
            half_life_hours=self.config.half_life_hours,
            halt_score=self.config.halt_score,
            elevated_score=self.config.elevated_score,
            reduce_size_multiplier=self.config.reduce_size_multiplier,
            widen_spacing_multiplier=self.config.widen_spacing_multiplier,
        )
        self.store = SentimentStore(self.database)
        active = [collector.name for collector in collectors]
        if self._last30days_collector is not None:
            active.append(self._last30days_collector.name)
        self._sources_active = tuple(dict.fromkeys(active))

    def start_background(self) -> None:
        if not self.config.enabled:
            return
        if self._refresh_task is not None and not self._refresh_task.done():
            return
        loop = asyncio.get_event_loop()
        self._refresh_task = loop.create_task(self._refresh_loop(), name="vhe-sentiment")

    async def _refresh_loop(self) -> None:
        await asyncio.sleep(3.0)
        while True:
            try:
                await self.refresh_async()
            except Exception:
                pass
            await asyncio.sleep(max(self.config.refresh_minutes * 60, 60))

    async def refresh_async(self) -> SentimentSnapshot:
        async with self._refresh_lock:
            return await asyncio.to_thread(self.refresh_sync)

    def refresh_sync(self) -> SentimentSnapshot:
        if not self.config.enabled:
            return self.snapshot()
        all_items = []
        symbols: dict[str, SymbolSentiment] = {}
        last30days_targets = self._last30days_targets()
        for symbol in self.symbols:
            extra: list[BuzzItem] = []
            if self._last30days_collector is not None and symbol in last30days_targets:
                try:
                    extra = self._last30days_collector.collect(symbol)
                except Exception:
                    extra = []
            row, items = self.engine.refresh_symbol(symbol, extra_items=extra or None)
            symbols[symbol] = row
            all_items.extend(items)
        if self._last30days_collector is not None:
            self._last30days_rotation += self.config.last30days_symbols_per_refresh
        self._symbols = symbols
        self._last_refresh_at = datetime.now(tz=timezone.utc)
        self.store.persist_refresh(symbols=symbols, items=all_items)
        return self.snapshot()

    def _last30days_targets(self) -> set[str]:
        if not self.symbols or self._last30days_collector is None:
            return set()
        count = max(self.config.last30days_symbols_per_refresh, 1)
        start = self._last30days_rotation % len(self.symbols)
        selected: list[str] = []
        for offset in range(len(self.symbols)):
            symbol = self.symbols[(start + offset) % len(self.symbols)]
            selected.append(symbol)
            if len(selected) >= count:
                break
        return set(selected)

    def snapshot(self) -> SentimentSnapshot:
        if not self.config.enabled:
            return SentimentSnapshot(
                status=SentimentStatus.NOT_CONFIGURED,
                headline="Sentiment disabled",
                detail="Enable sentiment in configs/sentiment.yaml.",
            )
        status, headline, detail, flagged = portfolio_snapshot(
            self._symbols,
            last_refresh_at=self._last_refresh_at,
            sources_active=self._sources_active,
        )
        return SentimentSnapshot(
            status=status,
            headline=headline,
            detail=detail,
            symbols_flagged=flagged,
            symbols=dict(self._symbols),
            last_refresh_at=self._last_refresh_at,
            sources_active=self._sources_active,
        )

    def symbol(self, ticker: str) -> SymbolSentiment | None:
        return self._symbols.get(ticker)

    def allows_buy(self, ticker: str) -> bool:
        row = self.symbol(ticker)
        if row is None:
            return True
        return row.action != SentimentAction.HALT

    def size_multiplier(self, ticker: str) -> float:
        row = self.symbol(ticker)
        return row.size_multiplier if row is not None else 1.0

    def spacing_multiplier(self, ticker: str) -> float:
        row = self.symbol(ticker)
        return row.spacing_multiplier if row is not None else 1.0

    def momentum_allowed(self, ticker: str) -> bool:
        row = self.symbol(ticker)
        if row is None:
            return True
        return row.score >= self.config.momentum_min_score

    def to_public_dict(self) -> dict:
        snap = self.snapshot()
        return {
            "status": snap.status.value,
            "headline": snap.headline,
            "detail": snap.detail,
            "symbols_flagged": list(snap.symbols_flagged),
            "last_refresh_at": snap.last_refresh_at.isoformat() if snap.last_refresh_at else None,
            "sources_active": list(snap.sources_active),
            "last30days_available": self._last30days_collector is not None,
            "last30days_repo_url": LAST30DAYS_REPO_URL,
            "last30days_engine_path": str(self._last30days_collector.engine_path) if self._last30days_collector else None,
            "last30days_engine_label": "mvanhorn/last30days-skill",
            "integration_plan": list(snap.integration_plan),
            "symbols": {
                symbol: {
                    "score": row.score,
                    "buzz_volume": row.buzz_volume,
                    "status": row.status.value,
                    "action": row.action.value,
                    "headline": row.headline,
                    "size_multiplier": row.size_multiplier,
                    "spacing_multiplier": row.spacing_multiplier,
                    "sources": row.sources,
                    "top_items": [
                        {
                            "source": item.source,
                            "title": item.title,
                            "url": item.url,
                            "engagement": item.engagement,
                            "published_at": item.published_at.isoformat(),
                        }
                        for item in row.top_items
                    ],
                }
                for symbol, row in snap.symbols.items()
            },
        }
