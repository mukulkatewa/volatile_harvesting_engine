from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from vhe.sentiment.models import BuzzItem, SymbolSentiment
from vhe.storage.db import PlatformDatabase


class SentimentStore:
    def __init__(self, database: PlatformDatabase | None) -> None:
        self.database = database

    def persist_refresh(
        self,
        *,
        symbols: dict[str, SymbolSentiment],
        items: list[BuzzItem],
    ) -> None:
        if self.database is None:
            return
        now = datetime.now(tz=timezone.utc).isoformat()
        payload = {
            "symbols": {symbol: _symbol_row(row) for symbol, row in symbols.items()},
            "items": [_item_row(item) for item in items[:100]],
            "updated_at": now,
        }
        self.database.save_meta("sentiment_latest", payload)

    def load_latest(self) -> dict[str, Any] | None:
        if self.database is None:
            return None
        return self.database.load_meta("sentiment_latest")


def _symbol_row(row: SymbolSentiment) -> dict[str, Any]:
    return {
        "symbol": row.symbol,
        "score": row.score,
        "buzz_volume": row.buzz_volume,
        "status": row.status.value,
        "action": row.action.value,
        "headline": row.headline,
        "size_multiplier": row.size_multiplier,
        "spacing_multiplier": row.spacing_multiplier,
        "sources": row.sources,
        "top_items": [_item_row(item) for item in row.top_items],
    }


def _item_row(item: BuzzItem) -> dict[str, Any]:
    payload = asdict(item)
    payload["published_at"] = item.published_at.isoformat()
    return payload
