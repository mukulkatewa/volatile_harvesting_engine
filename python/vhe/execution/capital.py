from __future__ import annotations

from dataclasses import dataclass

from vhe.config.loader import CapitalBucketConfig


@dataclass(frozen=True, slots=True)
class CapitalBuckets:
    total: float
    reserve: float
    grid: float
    pair: float
    momentum: float
    deployable: float


@dataclass(frozen=True, slots=True)
class SymbolAllocation:
    symbol: str
    capital: float
    level_capital: float
    max_levels: int


@dataclass(frozen=True, slots=True)
class PairAllocation:
    pair_id: str
    capital: float
    leg_capital: float


@dataclass(slots=True)
class CapitalAllocator:
    total_capital: float
    buckets: CapitalBucketConfig
    max_symbols: int = 2
    max_grid_levels: int = 5
    max_symbol_deploy_pct: float = 0.10

    def compute_buckets(self) -> CapitalBuckets:
        reserve = self.total_capital * self.buckets.reserve_bucket_pct
        grid = self.total_capital * self.buckets.grid_bucket_pct
        pair = self.total_capital * self.buckets.pair_bucket_pct
        momentum = self.total_capital * self.buckets.momentum_bucket_pct
        deployable = self.total_capital - reserve
        return CapitalBuckets(
            total=self.total_capital,
            reserve=reserve,
            grid=grid,
            pair=pair,
            momentum=momentum,
            deployable=deployable,
        )

    def symbol_grid_allocation(self, symbol: str, *, active_symbol_count: int | None = None) -> SymbolAllocation:
        bucket = self.compute_buckets()
        count = max(active_symbol_count or self.max_symbols, 1)
        per_symbol_cap = min(bucket.grid / count, bucket.deployable * self.max_symbol_deploy_pct)
        level_capital = per_symbol_cap / self.max_grid_levels
        return SymbolAllocation(
            symbol=symbol,
            capital=per_symbol_cap,
            level_capital=level_capital,
            max_levels=self.max_grid_levels,
        )

    def pair_allocation(self, pair_id: str) -> PairAllocation:
        bucket = self.compute_buckets()
        leg_capital = bucket.pair / 2
        return PairAllocation(pair_id=pair_id, capital=bucket.pair, leg_capital=leg_capital)

    def momentum_allocation(self) -> float:
        return self.compute_buckets().momentum

    def buckets_snapshot(self) -> dict:
        bucket = self.compute_buckets()
        return {
            "total": round(bucket.total, 2),
            "reserve": round(bucket.reserve, 2),
            "grid": round(bucket.grid, 2),
            "pair": round(bucket.pair, 2),
            "momentum": round(bucket.momentum, 2),
            "deployable": round(bucket.deployable, 2),
            "grid_pct": self.buckets.grid_bucket_pct,
            "pair_pct": self.buckets.pair_bucket_pct,
            "momentum_pct": self.buckets.momentum_bucket_pct,
            "reserve_pct": self.buckets.reserve_bucket_pct,
        }
