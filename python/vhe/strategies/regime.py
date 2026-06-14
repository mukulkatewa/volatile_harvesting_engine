from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MarketRegime(str, Enum):
    RANGE = "RANGE"
    TREND_UP = "TREND_UP"
    TREND_DOWN = "TREND_DOWN"
    CRASH = "CRASH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class RegimeInputs:
    price: float
    ema_20: float
    ema_50: float
    adx_14: float
    intraday_drawdown_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class RegimeDetector:
    range_adx_threshold: float = 20.0
    trend_adx_threshold: float = 25.0
    fair_value_band_pct: float = 0.03
    crash_drawdown_pct: float = -1.5

    def classify(self, inputs: RegimeInputs) -> MarketRegime:
        if inputs.intraday_drawdown_pct <= self.crash_drawdown_pct:
            return MarketRegime.CRASH

        if inputs.adx_14 < self.range_adx_threshold:
            distance = abs(inputs.price - inputs.ema_50) / inputs.ema_50 if inputs.ema_50 else 1.0
            if distance <= self.fair_value_band_pct:
                return MarketRegime.RANGE

        if inputs.adx_14 > self.trend_adx_threshold and inputs.ema_20 > inputs.ema_50 and inputs.price > inputs.ema_50:
            return MarketRegime.TREND_UP

        if inputs.adx_14 > self.trend_adx_threshold and inputs.ema_20 < inputs.ema_50 and inputs.price < inputs.ema_50:
            return MarketRegime.TREND_DOWN

        return MarketRegime.UNKNOWN
