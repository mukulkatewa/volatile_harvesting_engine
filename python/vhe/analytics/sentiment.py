from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SentimentStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CLEAR = "clear"
    ELEVATED = "elevated"
    HALT = "halt"


_DEFAULT_INTEGRATION_PLAN = (
    "Multi-source buzz ingest (Reddit, HN, last30days bridge)",
    "Engagement-weighted score with recency decay",
    "Risk overlay: halt buys, reduce size, widen grid spacing",
    "Momentum requires non-negative sentiment in TREND_UP",
)


@dataclass(frozen=True, slots=True)
class SentimentSnapshot:
    status: SentimentStatus
    headline: str
    detail: str
    symbols_flagged: tuple[str, ...] = ()
    integration_plan: tuple[str, ...] = _DEFAULT_INTEGRATION_PLAN
    last_refresh_at: str | None = None
    sources_active: tuple[str, ...] = ()
    symbols: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "headline": self.headline,
            "detail": self.detail,
            "symbols_flagged": list(self.symbols_flagged),
            "integration_plan": list(self.integration_plan),
            "last_refresh_at": self.last_refresh_at,
            "sources_active": list(self.sources_active),
            "symbols": self.symbols,
        }


def sentiment_snapshot() -> SentimentSnapshot:
    return SentimentSnapshot(
        status=SentimentStatus.NOT_CONFIGURED,
        headline="Sentiment engine starting",
        detail="First refresh cycle will populate Reddit/HN buzz scores.",
    )


def sentiment_snapshot_from_dict(payload: dict) -> SentimentSnapshot:
    status = SentimentStatus(payload.get("status", SentimentStatus.CLEAR.value))
    return SentimentSnapshot(
        status=status,
        headline=str(payload.get("headline") or ""),
        detail=str(payload.get("detail") or ""),
        symbols_flagged=tuple(payload.get("symbols_flagged") or ()),
        integration_plan=tuple(payload.get("integration_plan") or _DEFAULT_INTEGRATION_PLAN),
        last_refresh_at=payload.get("last_refresh_at"),
        sources_active=tuple(payload.get("sources_active") or ()),
        symbols=dict(payload.get("symbols") or {}),
    )
