from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from vhe.config.models import AppConfig


class BrokerConfig(BaseModel):
    provider: str = "zerodha"
    websocket_enabled: bool = False


class LiveRiskConfig(BaseModel):
    reserve_capital_pct: float = 0.10
    max_daily_loss_pct: float = 0.01
    max_gross_exposure_pct: float = 0.75
    max_single_symbol_qty: int = 100
    kill_switch_on_stale_quotes: bool = True
    max_quote_stale_ms: int = 3000


class StorageConfig(BaseModel):
    sqlite_path: Path = Path("data/vhe_platform.db")
    persist_events: bool = True
    persist_fills: bool = True


class LiveConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = "paper"
    capital_cap_inr: float = 25_000.0
    max_symbols: int = 2
    max_grid_levels: int = 5
    force_exit_time: str = "15:10"
    config_dir: str = "configs"
    broker: BrokerConfig = Field(default_factory=BrokerConfig)
    risk: LiveRiskConfig = Field(default_factory=LiveRiskConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> LiveConfig:
        payload = yaml.safe_load(path.read_text()) or {}
        return cls.model_validate(payload)


class GridStrategyConfig(BaseModel):
    atr_multiplier: float = 0.35
    max_levels: int = 5
    no_buy_above_fair_value_pct: float = 0.03
    min_spacing: float = 0.05


class MomentumStrategyConfig(BaseModel):
    risk_per_trade_inr: float = 62.5
    max_capital_per_trade_inr: float = 3_750.0


class PairStrategyConfig(BaseModel):
    symbol_a: str = "RELIANCE"
    symbol_b: str = "HDFCBANK"
    hedge_ratio: float = 1.0
    mean: float = -0.04
    std: float = 0.006
    entry_z: float = 1.5
    exit_z: float = 0.25
    max_abs_z: float = 3.0


class CapitalBucketConfig(BaseModel):
    grid_bucket_pct: float = 0.50
    pair_bucket_pct: float = 0.25
    momentum_bucket_pct: float = 0.15
    reserve_bucket_pct: float = 0.10

    def validate_total(self) -> None:
        total = self.grid_bucket_pct + self.pair_bucket_pct + self.momentum_bucket_pct + self.reserve_bucket_pct
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"capital buckets must sum to 1.0, got {total}")


class RegimeConfig(BaseModel):
    range_adx_threshold: float = 20.0
    trend_adx_threshold: float = 25.0
    fair_value_band_pct: float = 0.03
    crash_drawdown_pct: float = -1.5


class FeedConfig(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["RELIANCE", "HDFCBANK", "TATAMOTORS", "BEL"])
    interval_seconds: float = 0.75
    source: str = "simulated"


class StrategiesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grid: GridStrategyConfig = Field(default_factory=GridStrategyConfig)
    momentum: MomentumStrategyConfig = Field(default_factory=MomentumStrategyConfig)
    pair: PairStrategyConfig = Field(default_factory=PairStrategyConfig)
    capital: CapitalBucketConfig = Field(default_factory=CapitalBucketConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    feed: FeedConfig = Field(default_factory=FeedConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> StrategiesConfig:
        payload = yaml.safe_load(path.read_text()) or {}
        config = cls.model_validate(payload)
        config.capital.validate_total()
        return config


class PlatformConfig(BaseModel):
    live: LiveConfig
    strategies: StrategiesConfig
    app: AppConfig | None = None

    @property
    def total_capital(self) -> float:
        return self.live.capital_cap_inr


def load_platform_config(project_root: Path | None = None, live_config_name: str = "live_paper.yaml") -> PlatformConfig:
    root = project_root or _find_project_root()
    config_dir = root / "configs"
    live = LiveConfig.from_yaml(config_dir / live_config_name)
    strategies = StrategiesConfig.from_yaml(config_dir / "strategies.yaml")
    app_path = config_dir / "app.yaml"
    app = AppConfig.from_yaml(app_path) if app_path.exists() else None
    return PlatformConfig(live=live, strategies=strategies, app=app)


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / "configs" / "live_paper.yaml").exists():
            return parent
    return Path.cwd()
