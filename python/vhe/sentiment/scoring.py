from __future__ import annotations

import math
import re
from datetime import datetime, timezone

from vhe.sentiment.models import BuzzItem, SentimentAction, SentimentStatus, SymbolSentiment
from vhe.sentiment.trending import engagement_total, filter_buzz_items, trending_heat

_POSITIVE = (
    "upgrade",
    "bullish",
    "record high",
    "record profit",
    "beat estimates",
    "surge",
    "rally",
    "strong results",
    "outperform",
    "buyback",
    "expansion",
    "growth",
    "breakout",
)
_NEGATIVE = (
    "fraud",
    "scam",
    "downgrade",
    "selloff",
    "sell-off",
    "bankruptcy",
    "investigation",
    "probe",
    "loss",
    "weak",
    "bearish",
    "short report",
    "crash",
    "plunge",
    "decline",
    "concern",
    "warning",
    "default",
    "scandal",
    "halt",
    "insider selling",
)


def lexicon_score(text: str) -> float:
    lowered = text.lower()
    pos = sum(1 for term in _POSITIVE if term in lowered)
    neg = sum(1 for term in _NEGATIVE if term in lowered)
    if pos == 0 and neg == 0:
        return 0.0
    return max(-1.0, min(1.0, (pos - neg) / max(pos + neg, 1)))


def engagement_weight(item: BuzzItem) -> float:
    return math.log1p(max(item.engagement, 0.0))


def recency_weight(*, published_at: datetime, now: datetime, half_life_hours: float) -> float:
    age_hours = max((now - published_at).total_seconds() / 3600.0, 0.0)
    if half_life_hours <= 0:
        return 1.0
    return math.exp(-age_hours / half_life_hours)


def aggregate_symbol_score(
    items: list[BuzzItem],
    *,
    now: datetime,
    half_life_hours: float,
    halt_score: float,
    elevated_score: float,
    reduce_size_multiplier: float,
    widen_spacing_multiplier: float,
) -> SymbolSentiment:
    if not items:
        return SymbolSentiment(
            symbol=items[0].symbol if items else "UNKNOWN",
            score=0.0,
            buzz_volume=0,
            status=SentimentStatus.CLEAR,
            action=SentimentAction.ALLOW,
            headline="No recent buzz",
            size_multiplier=1.0,
            spacing_multiplier=1.0,
        )

    symbol = items[0].symbol
    weighted_sum = 0.0
    weight_total = 0.0
    sources: dict[str, int] = {}
    for item in items:
        item_score = item.raw_score if item.raw_score else lexicon_score(f"{item.title} {item.text}")
        w = engagement_weight(item) * recency_weight(
            published_at=item.published_at, now=now, half_life_hours=half_life_hours
        )
        weighted_sum += item_score * w
        weight_total += w
        sources[item.source] = sources.get(item.source, 0) + 1

    score = weighted_sum / weight_total if weight_total > 0 else 0.0
    score = max(-1.0, min(1.0, score))
    buzz_volume = len(items)

    if score <= halt_score:
        status = SentimentStatus.HALT
        action = SentimentAction.HALT
        headline = f"Negative buzz ({score:+.2f}) — block new risk"
        size_multiplier = 0.0
        spacing_multiplier = widen_spacing_multiplier
    elif score <= elevated_score:
        status = SentimentStatus.ELEVATED
        action = SentimentAction.REDUCE
        headline = f"Cautionary buzz ({score:+.2f}) — reduced size / wider grid"
        size_multiplier = reduce_size_multiplier
        spacing_multiplier = widen_spacing_multiplier
    else:
        status = SentimentStatus.CLEAR
        action = SentimentAction.ALLOW
        headline = f"Neutral/positive buzz ({score:+.2f})"
        size_multiplier = 1.0
        spacing_multiplier = 1.0

    top_items = tuple(sorted(items, key=lambda item: item.engagement, reverse=True)[:5])
    heat = trending_heat(
        buzz_volume=buzz_volume,
        score=score,
        engagement_total=engagement_total(items),
    )
    if buzz_volume > 0 and score >= 0:
        headline = f"Trending buzz ({buzz_volume} signals, heat {heat:.2f})"
    return SymbolSentiment(
        symbol=symbol,
        score=round(score, 3),
        buzz_volume=buzz_volume,
        status=status,
        action=action,
        headline=headline,
        size_multiplier=size_multiplier,
        spacing_multiplier=spacing_multiplier,
        trending_score=heat,
        sources=sources,
        top_items=top_items,
    )


def portfolio_snapshot(
    symbols: dict[str, SymbolSentiment],
    *,
    last_refresh_at: datetime | None,
    sources_active: tuple[str, ...],
) -> tuple[SentimentStatus, str, str, tuple[str, ...]]:
    if not symbols:
        return (
            SentimentStatus.NOT_CONFIGURED,
            "Sentiment engine idle",
            "Waiting for first refresh cycle.",
            (),
        )

    flagged = tuple(sorted(symbol for symbol, row in symbols.items() if row.status != SentimentStatus.CLEAR))
    halt_count = sum(1 for row in symbols.values() if row.status == SentimentStatus.HALT)
    elevated_count = sum(1 for row in symbols.values() if row.status == SentimentStatus.ELEVATED)

    if halt_count:
        status = SentimentStatus.HALT
        headline = f"{halt_count} symbol(s) on sentiment halt"
    elif elevated_count:
        status = SentimentStatus.ELEVATED
        headline = f"{elevated_count} symbol(s) on elevated watch"
    else:
        status = SentimentStatus.CLEAR
        headline = "Social buzz clear across watchlist"

    refresh_note = last_refresh_at.isoformat() if last_refresh_at else "never"
    detail = (
        f"Sources: {', '.join(sources_active) or 'none'}. "
        f"Last refresh: {refresh_note}. "
        f"Flagged: {', '.join(flagged) if flagged else 'none'}."
    )
    return status, headline, detail, flagged
