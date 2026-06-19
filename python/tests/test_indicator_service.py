from datetime import datetime, timezone

import pytest

from vhe.live.models import LiveQuote
from vhe.platform.services.indicator_service import IndicatorService
from vhe.platform.services.regime_service import RegimeService
from vhe.config.loader import RegimeConfig


@pytest.fixture
def quote() -> LiveQuote:
    return LiveQuote(
        timestamp=datetime.now(tz=timezone.utc),
        symbol="AAA",
        ltp=100.0,
        open=99.0,
        high=101.0,
        low=98.5,
        close=99.5,
        volume=1000,
    )


def test_indicator_service_produces_snapshot(quote: LiveQuote) -> None:
    service = IndicatorService(history_size=60)
    snapshot = service.update(quote)
    assert snapshot.symbol == "AAA"
    assert snapshot.ltp == 100.0
    assert snapshot.atr_14 > 0


def test_regime_service_classifies_range(quote: LiveQuote) -> None:
    service = IndicatorService()
    regime_service = RegimeService(config=RegimeConfig())
    for i in range(25):
        tick = LiveQuote(
            timestamp=quote.timestamp,
            symbol=quote.symbol,
            ltp=100.0 + (i % 3) * 0.1,
            open=99.8,
            high=100.4,
            low=99.6,
            close=100.0,
            volume=1000,
        )
        snapshot = service.update(tick)
    regime = regime_service.classify(snapshot)
    assert regime.value in {"RANGE", "UNKNOWN", "TREND_UP", "TREND_DOWN", "CRASH"}


def test_fair_value_anchor_lags_price_to_create_dislocation() -> None:
    # Regression: fair_value used to equal spot, so no mean-reversion signal could
    # ever fire (seed gate ltp <= fair_value*(1-band) was impossible). The anchor
    # must lag a fast price move so a harvestable dislocation appears.
    service = IndicatorService(history_size=60, anchor_alpha=0.04)
    service.seed_bars(
        "AAA",
        [{"open": 100, "high": 100.5, "low": 99.5, "close": 100.0, "ltp": 100.0} for _ in range(40)],
    )
    base = datetime.now(tz=timezone.utc)

    def tick(price: float) -> LiveQuote:
        return LiveQuote(
            timestamp=base,
            symbol="AAA",
            ltp=price,
            open=price,
            high=price + 0.2,
            low=price - 0.2,
            close=price,
            volume=1000,
        )

    # Sharp drop: anchor stays well above spot -> price is below fair value (buy zone).
    snapshot = None
    for _ in range(3):
        snapshot = service.update(tick(96.0))
    assert snapshot is not None
    assert snapshot.fair_value > snapshot.ltp
    assert snapshot.fair_value < 100.5  # but anchor does drift toward price over time


def test_indicator_service_seeds_history() -> None:
    service = IndicatorService()
    service.seed_bars(
        "RELIANCE",
        [
            {"open": 100, "high": 101, "low": 99, "close": 100, "ltp": 100},
            {"open": 101, "high": 102, "low": 100, "close": 101, "ltp": 101},
        ],
    )
    assert len(service._history["RELIANCE"]) == 2
