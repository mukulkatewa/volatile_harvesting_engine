from __future__ import annotations

import yaml
from pydantic import BaseModel, ConfigDict, Field

from vhe.sentiment.service import SentimentConfig


class SentimentYamlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    refresh_minutes: float = 15.0
    lookback_days: int = 30
    sources: dict[str, bool] = Field(
        default_factory=lambda: {
            "reddit": True,
            "hackernews": True,
            "last30days": True,
        }
    )
    max_items_per_source: int = 20
    half_life_hours: float = 12.0
    halt_score: float = -0.55
    elevated_score: float = -0.25
    momentum_min_score: float = -0.15
    reduce_size_multiplier: float = 0.5
    widen_spacing_multiplier: float = 1.35
    last30days_search_sources: str = "reddit,hackernews,web"
    last30days_symbols_per_refresh: int = 2
    last30days_timeout_seconds: float = 90.0

    @classmethod
    def from_yaml(cls, path) -> SentimentYamlConfig:
        if not path.exists():
            return cls()
        payload = yaml.safe_load(path.read_text()) or {}
        return cls.model_validate(payload)

    def to_service_config(self) -> SentimentConfig:
        sources = self.sources or {}
        return SentimentConfig(
            enabled=self.enabled,
            refresh_minutes=self.refresh_minutes,
            lookback_days=self.lookback_days,
            reddit_enabled=bool(sources.get("reddit", True)),
            hackernews_enabled=bool(sources.get("hackernews", True)),
            last30days_enabled=bool(sources.get("last30days", True)),
            last30days_symbols_per_refresh=self.last30days_symbols_per_refresh,
            last30days_search_sources=self.last30days_search_sources,
            last30days_timeout_seconds=self.last30days_timeout_seconds,
            max_items_per_source=self.max_items_per_source,
            half_life_hours=self.half_life_hours,
            halt_score=self.halt_score,
            elevated_score=self.elevated_score,
            momentum_min_score=self.momentum_min_score,
            reduce_size_multiplier=self.reduce_size_multiplier,
            widen_spacing_multiplier=self.widen_spacing_multiplier,
        )
