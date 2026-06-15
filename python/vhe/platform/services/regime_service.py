from __future__ import annotations

from dataclasses import dataclass

from vhe.config.loader import RegimeConfig
from vhe.platform.services.indicator_service import IndicatorSnapshot
from vhe.strategies.regime import MarketRegime, RegimeDetector, RegimeInputs


@dataclass(slots=True)
class RegimeService:
    config: RegimeConfig
    _detector: RegimeDetector | None = None
    _regimes: dict[str, MarketRegime] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._detector = RegimeDetector(
            range_adx_threshold=self.config.range_adx_threshold,
            trend_adx_threshold=self.config.trend_adx_threshold,
            fair_value_band_pct=self.config.fair_value_band_pct,
            crash_drawdown_pct=self.config.crash_drawdown_pct,
        )
        self._regimes = {}

    def classify(self, snapshot: IndicatorSnapshot) -> MarketRegime:
        assert self._detector is not None
        regime = self._detector.classify(
            RegimeInputs(
                price=snapshot.ltp,
                ema_20=snapshot.ema_20,
                ema_50=snapshot.ema_50,
                adx_14=snapshot.adx_14,
                intraday_drawdown_pct=snapshot.intraday_drawdown_pct,
            )
        )
        self._regimes[snapshot.symbol] = regime
        return regime

    def get(self, symbol: str) -> MarketRegime:
        return self._regimes.get(symbol, MarketRegime.UNKNOWN)

    def snapshot(self) -> dict[str, str]:
        return {symbol: regime.value for symbol, regime in self._regimes.items()}
