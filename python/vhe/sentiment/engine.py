from __future__ import annotations

from datetime import datetime, timezone

from vhe.sentiment.collectors.base import BuzzCollector
from vhe.sentiment.models import BuzzItem, SentimentAction, SentimentStatus, SymbolSentiment
from vhe.sentiment.scoring import aggregate_symbol_score


class SentimentEngine:
    def __init__(
        self,
        collectors: list[BuzzCollector],
        *,
        half_life_hours: float,
        halt_score: float,
        elevated_score: float,
        reduce_size_multiplier: float,
        widen_spacing_multiplier: float,
    ) -> None:
        self.collectors = collectors
        self.half_life_hours = half_life_hours
        self.halt_score = halt_score
        self.elevated_score = elevated_score
        self.reduce_size_multiplier = reduce_size_multiplier
        self.widen_spacing_multiplier = widen_spacing_multiplier

    def refresh_symbol(self, symbol: str, *, extra_items: list[BuzzItem] | None = None) -> tuple[SymbolSentiment, list[BuzzItem]]:
        items: list[BuzzItem] = []
        for collector in self.collectors:
            try:
                items.extend(collector.collect(symbol))
            except Exception:
                continue
        if extra_items:
            items.extend(extra_items)
        items = filter_buzz_items(items)
        return self.score_items(symbol, items)

    def score_items(self, symbol: str, items: list[BuzzItem]) -> tuple[SymbolSentiment, list[BuzzItem]]:
        now = datetime.now(tz=timezone.utc)
        if not items:
            sentiment = SymbolSentiment(
                symbol=symbol,
                score=0.0,
                buzz_volume=0,
                status=SentimentStatus.CLEAR,
                action=SentimentAction.ALLOW,
                headline="No recent buzz",
                size_multiplier=1.0,
                spacing_multiplier=1.0,
            )
            return sentiment, []
        sentiment = aggregate_symbol_score(
            items,
            now=now,
            half_life_hours=self.half_life_hours,
            halt_score=self.halt_score,
            elevated_score=self.elevated_score,
            reduce_size_multiplier=self.reduce_size_multiplier,
            widen_spacing_multiplier=self.widen_spacing_multiplier,
        )
        return sentiment, items

    def refresh_watchlist(self, symbols: list[str]) -> dict[str, SymbolSentiment]:
        return {symbol: self.refresh_symbol(symbol)[0] for symbol in symbols}
