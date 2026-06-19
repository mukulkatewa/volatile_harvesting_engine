from datetime import datetime, timezone

from vhe.sentiment.models import BuzzItem
from vhe.sentiment.trending import filter_buzz_items, is_noise_text, trending_heat


def test_noise_filter_rejects_job_spam() -> None:
    assert is_noise_text("1,000+ Reliance Industries Nse jobs in India")
    assert is_noise_text("Investing in US stocks from India: tax and compliance")


def test_filter_buzz_items_drops_noise() -> None:
    items = [
        BuzzItem(
            source="reddit",
            symbol="RELIANCE",
            title="1,000+ Reliance Industries Nse jobs in India",
            url="",
            engagement=12,
            published_at=datetime.now(tz=timezone.utc),
        ),
        BuzzItem(
            source="reddit",
            symbol="RELIANCE",
            title="Reliance Industries Q4 results beat estimates",
            url="",
            engagement=40,
            published_at=datetime.now(tz=timezone.utc),
            text="RIL record profit rally",
        ),
    ]
    filtered = filter_buzz_items(items)
    assert len(filtered) == 1
    assert "results" in filtered[0].title


def test_trending_heat_rises_with_buzz() -> None:
    low = trending_heat(buzz_volume=0, score=0.0, engagement_total=0.0)
    high = trending_heat(buzz_volume=8, score=0.2, engagement_total=120.0)
    assert high > low
