from __future__ import annotations

from datetime import datetime, timezone

import httpx

from vhe.sentiment.collectors.base import BuzzCollector
from vhe.sentiment.models import BuzzItem
from vhe.sentiment.scoring import lexicon_score
from vhe.sentiment.symbols import match_symbol, search_queries


class HackerNewsCollector(BuzzCollector):
    name = "hackernews"

    def __init__(self, *, max_items: int = 15, timeout_seconds: float = 12.0) -> None:
        self.max_items = max_items
        self.timeout_seconds = timeout_seconds

    def collect(self, symbol: str) -> list[BuzzItem]:
        items: list[BuzzItem] = []
        for query in search_queries(symbol)[:1]:
            url = "https://hn.algolia.com/api/v1/search"
            params = {
                "query": query,
                "tags": "story",
                "numericFilters": f"created_at_i>{_thirty_days_ago_epoch()}",
                "hitsPerPage": str(self.max_items),
            }
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
            except Exception:
                continue

            for hit in payload.get("hits", []):
                title = (hit.get("title") or hit.get("story_title") or "").strip()
                if not title or not match_symbol(title, symbol):
                    continue
                created = datetime.fromtimestamp(int(hit.get("created_at_i") or 0), tz=timezone.utc)
                link = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                engagement = float(hit.get("points") or 0) + float(hit.get("num_comments") or 0) * 2
                items.append(
                    BuzzItem(
                        source=self.name,
                        symbol=symbol,
                        title=title[:240],
                        url=link,
                        engagement=engagement,
                        published_at=created,
                        raw_score=lexicon_score(title),
                    )
                )
        return items[: self.max_items]


def _thirty_days_ago_epoch() -> int:
    now = datetime.now(tz=timezone.utc)
    return int(now.timestamp()) - 30 * 24 * 3600
