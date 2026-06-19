from __future__ import annotations

import math
import re

from vhe.sentiment.models import BuzzItem, SentimentAction, SymbolSentiment

NOISE_PATTERNS = re.compile(
    r"\b(jobs? in india|hiring|careers?|job opening|walk[\s-]?in|"
    r"tax and compliance|how to invest in us stocks|"
    r"resume|interview|vacancy|internship)\b",
    re.I,
)


def is_noise_text(text: str) -> bool:
    return bool(NOISE_PATTERNS.search(text))


def filter_buzz_items(items: list[BuzzItem]) -> list[BuzzItem]:
    filtered: list[BuzzItem] = []
    for item in items:
        blob = f"{item.title} {item.text}".strip()
        if not blob or is_noise_text(blob):
            continue
        filtered.append(item)
    return filtered


def trending_heat(*, buzz_volume: int, score: float, engagement_total: float) -> float:
    """0–1 heat score: buzz volume + engagement + directional score."""
    volume_part = min(1.0, math.log1p(max(buzz_volume, 0)) / 2.8)
    engagement_part = min(1.0, math.log1p(max(engagement_total, 0.0)) / 6.0)
    direction_part = max(0.0, min(1.0, (score + 1.0) / 2.0))
    return round(min(1.0, volume_part * 0.45 + engagement_part * 0.35 + direction_part * 0.20), 3)


def engagement_total(items: list[BuzzItem]) -> float:
    return sum(max(item.engagement, 0.0) for item in items)


def rank_symbols(
    symbols: dict[str, SymbolSentiment],
    *,
    min_heat: float = 0.05,
) -> list[tuple[str, float, SymbolSentiment]]:
    rows: list[tuple[str, float, SymbolSentiment]] = []
    for symbol, row in symbols.items():
        if row.action == SentimentAction.HALT:
            continue
        heat = getattr(row, "trending_score", None)
        if heat is None:
            heat = trending_heat(
                buzz_volume=row.buzz_volume,
                score=row.score,
                engagement_total=sum(item.engagement for item in row.top_items),
            )
        if heat >= min_heat or row.buzz_volume > 0:
            rows.append((symbol, heat, row))
    rows.sort(key=lambda item: (item[1], item[2].buzz_volume, item[2].score), reverse=True)
    return rows
