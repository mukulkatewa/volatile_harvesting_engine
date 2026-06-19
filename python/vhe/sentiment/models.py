from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SentimentStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CLEAR = "clear"
    ELEVATED = "elevated"
    HALT = "halt"


class SentimentAction(str, Enum):
    ALLOW = "allow"
    REDUCE = "reduce"
    HALT = "halt"


@dataclass(frozen=True, slots=True)
class BuzzItem:
    source: str
    symbol: str
    title: str
    url: str
    engagement: float
    published_at: datetime
    text: str = ""
    raw_score: float = 0.0


@dataclass(frozen=True, slots=True)
class SymbolSentiment:
    symbol: str
    score: float
    buzz_volume: int
    status: SentimentStatus
    action: SentimentAction
    headline: str
    size_multiplier: float
    spacing_multiplier: float
    sources: dict[str, int] = field(default_factory=dict)
    top_items: tuple[BuzzItem, ...] = ()


@dataclass(frozen=True, slots=True)
class SentimentSnapshot:
    status: SentimentStatus
    headline: str
    detail: str
    symbols_flagged: tuple[str, ...] = ()
    symbols: dict[str, SymbolSentiment] = field(default_factory=dict)
    last_refresh_at: datetime | None = None
    sources_active: tuple[str, ...] = ()
    integration_plan: tuple[str, ...] = (
        "Multi-source buzz ingest (Reddit, HN, last30days bridge)",
        "Engagement-weighted score with recency decay",
        "Risk overlay: halt buys, reduce size, widen grid spacing",
        "Momentum requires non-negative sentiment in TREND_UP",
    )
