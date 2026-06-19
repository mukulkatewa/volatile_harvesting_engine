from __future__ import annotations

from datetime import datetime, timezone

import httpx

from vhe.sentiment.collectors.base import BuzzCollector
from vhe.sentiment.models import BuzzItem
from vhe.sentiment.scoring import lexicon_score
from vhe.sentiment.symbols import match_symbol, search_queries


class RedditCollector(BuzzCollector):
    name = "reddit"

    def __init__(self, *, max_items: int = 20, timeout_seconds: float = 12.0) -> None:
        self.max_items = max_items
        self.timeout_seconds = timeout_seconds

    def collect(self, symbol: str) -> list[BuzzItem]:
        items: list[BuzzItem] = []
        headers = {"User-Agent": "vhe-sentiment/1.0 (research; +https://github.com/vhe)"}
        for query in search_queries(symbol)[:1]:
            url = "https://www.reddit.com/search.json"
            params = {"q": query, "sort": "new", "limit": str(self.max_items), "t": "month"}
            try:
                with httpx.Client(timeout=self.timeout_seconds, headers=headers) as client:
                    response = client.get(url, params=params)
                    response.raise_for_status()
                    payload = response.json()
            except Exception:
                continue

            for child in payload.get("data", {}).get("children", []):
                data = child.get("data", {})
                title = (data.get("title") or "").strip()
                selftext = (data.get("selftext") or "").strip()
                text = f"{title} {selftext}".strip()
                if not text or not match_symbol(text, symbol):
                    continue
                created = datetime.fromtimestamp(float(data.get("created_utc") or 0), tz=timezone.utc)
                permalink = data.get("permalink") or ""
                link = f"https://www.reddit.com{permalink}" if permalink.startswith("/") else permalink
                engagement = float(data.get("ups") or 0) + float(data.get("num_comments") or 0) * 2
                items.append(
                    BuzzItem(
                        source=self.name,
                        symbol=symbol,
                        title=title[:240],
                        url=link,
                        engagement=engagement,
                        published_at=created,
                        text=selftext[:500],
                        raw_score=lexicon_score(text),
                    )
                )
        return items[: self.max_items]
