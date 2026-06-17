from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SentimentStatus(str, Enum):
    NOT_CONFIGURED = "not_configured"
    CLEAR = "clear"
    ELEVATED = "elevated"
    HALT = "halt"


@dataclass(frozen=True, slots=True)
class SentimentSnapshot:
    status: SentimentStatus
    headline: str
    detail: str
    symbols_flagged: tuple[str, ...] = ()
    integration_plan: tuple[str, ...] = (
        "Ingest headlines (RSS / NSE announcements / news API)",
        "Score per-symbol sentiment (−1 to +1) with event decay half-life",
        "Map to risk overlay: widen grid spacing, reduce size, or pause new buys",
        "CRASH regime already covers sharp drawdowns; sentiment covers slow drift",
    )


def sentiment_snapshot() -> SentimentSnapshot:
    """Placeholder until a news feed is wired. Regime engine handles price-based stress."""
    return SentimentSnapshot(
        status=SentimentStatus.NOT_CONFIGURED,
        headline="News sentiment not wired yet",
        detail=(
            "VHE currently uses price-only signals (ADX regime, ATR grid, pair z-score). "
            "A news layer would sit in the risk guard before order submission — not in fill logic."
        ),
    )
