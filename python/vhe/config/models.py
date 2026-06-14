from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class PathsConfig(BaseModel):
    raw_data_dir: Path = Path("data/raw")
    processed_data_dir: Path = Path("data/processed")
    research_data_dir: Path = Path("data/research")
    reports_dir: Path = Path("reports")


class UniverseConfig(BaseModel):
    name: str
    symbols: list[str] = Field(default_factory=list)


class MarketConfig(BaseModel):
    exchange: Literal["NSE"] = "NSE"
    timezone: str = "Asia/Kolkata"
    session_start: str = "09:15"
    session_end: str = "15:30"


class DataConfig(BaseModel):
    source: str = "nse_bhavcopy"
    adjusted_prices: bool = True
    timeframe: str = "1d"
    turnover_threshold_inr: int = 100_000_000
    min_close_price_inr: int = 100


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    environment: str = "dev"
    timezone: str = "Asia/Kolkata"
    paths: PathsConfig = Field(default_factory=PathsConfig)
    universe: UniverseConfig
    market: MarketConfig = Field(default_factory=MarketConfig)
    data: DataConfig = Field(default_factory=DataConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "AppConfig":
        payload = yaml.safe_load(path.read_text()) or {}
        return cls.model_validate(payload)

